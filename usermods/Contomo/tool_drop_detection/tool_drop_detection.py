# Tool-Drop Detection (v1.12)

from __future__ import annotations
import math, statistics, collections, types, copy, re
from typing import Dict, Deque, List, Tuple, Sequence, Union
from . import adxl345


_Number = Union[float, Tuple[float, float, float]]

# ───────────────────────────── constants ──────────────────────────────
MAX_POLL_FREQ = 20.0                        # Hz - upper ceiling we will clamp to
FREEFALL_MS2   = 9.80665 * 1000.0           # 1 g in mm/s^2
_DWELL_GRAB    = 0.1                        # dwell for one-shot queries
_RATE_CHOICES  = adxl345.QUERY_RATES        # supported BW_RATE values
_STATISTIC_FN  = statistics.median
# ───────────────────────────── helpers ────────────────────────────────

def _vector_to_angles(vector, defaults = {}):
    (ax, ay, az) = vector
    if not (ax or ay or az):
        return 0.0, 0.0
    pitch        = math.degrees(math.atan2(-ax, math.hypot(ay, az)))  - defaults.get('base_pitch', 0.0)
    roll         = math.degrees(math.atan2(ay, az))                   - defaults.get('base_roll', 0.0)
    return ((pitch + 180) % 360) - 180, ((roll + 180) % 360) - 180

def _vector_angle(v0, defaults = {}): # 5$ if you can manage to get a divide by 0, not guarding it.
    v1 = defaults.get('base_vector', (0.0, -1.0, 0.0))
    dot = sum(a*b for a,b in zip(v0, v1))
    mag0 = math.sqrt(sum(a*a for a in v0))
    mag1 = math.sqrt(sum(a*a for a in v1))
    arg = max(-1.0, min(1.0, dot/(mag0*mag1)))# 0.9 + 0.1 = 1.0000001 thats pretty based.... -> math.acos(1.0000001) is apparently illegal
    return math.degrees(math.acos(arg))

def _angle_diffrence(a0, a1):
    diff = ((a0 - a1 + 180) % 360) - 180
    return diff

# ---------------------------------------------------------------------------
def _raw_to_vector(raw_vector, defaults = {}):
    gx, gy, gz = (axis / 1.0 / (defaults.get('base_g', 1.0) * FREEFALL_MS2) for axis in raw_vector)
    return (gx, gy, gz)

def _vector_to_magnitude(vector):
    (gx, gy, gz) = vector
    magnitude = math.sqrt(gx**2 + gy**2 + gz**2)
    return magnitude

def _strip_timestamps(samples):
    """ .accel_x, .accel_y, .accel_z, .time -> plain (x, y, z) tuples"""
    return [(s.accel_x, s.accel_y, s.accel_z) for s in samples]

def _average_samples(samples: Sequence[Tuple[float, float, float]], amount: int = 0):
    """Collapse a list [(x y z)] to (x,y,z) | first <-(-) amount (+)-> last"""
    if not samples:
        return (0.0, 0.0, 0.0)
    # pick the window according to the rule above
    window = (samples[:amount] if amount > 0 else samples[amount:] if amount < 0 else samples)

    xs, ys, zs = zip(*window)
    return (_STATISTIC_FN(xs), _STATISTIC_FN(ys), _STATISTIC_FN(zs))

def _parse_default_line(raw: str) -> Dict[str, _Number]:
    """
    Parse a user-supplied default line such as one of the following:
        "[g:1.0, p:0.0°, r:-93.24°, vec:(0,0,1)]"
        "g=1    p:-1.5   r:90   v:(0,0,1)"
        "g 1  pitch -2  roll 45  vector 0,0,1"
    """
    if not raw:
        return {}

    # Strip outer [ ] and collapse whitespace
    raw = raw.strip().lstrip('[').rstrip(']')

    # Split on commas OR runs of ≥2 spaces
    tokens = re.split(r'\s*,\s*|\s{2,}', raw)

    out: Dict[str, _Number] = {}
    for tok in tokens:
        if not tok:
            continue

        # Accept "key:value", "key=value", or "key value"
        parts = re.split(r'[:=\s]', tok, maxsplit=1)
        if len(parts) != 2:
            continue
        key, val = parts[0].strip().lower(), parts[1].strip()

        # Normalise verbose keys to their single-letter form
        key_map = {'pitch': 'p','roll':  'r','vector': 'v','vec':   'v','g':'g'}
        key = key_map.get(key, key)
        if key == 'v':
            nums = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', val)
            if len(nums) >= 3:
                out['v'] = tuple(float(n) for n in nums[:3])
            continue
        m = re.search(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', val)
        if m:
            out[key] = float(m.group())

    return out

# ───────────────────────────── main object ────────────────────────────
class ToolDropDetection:
    def __init__(self, cfg):
        self.printer = cfg.get_printer()
        # ── event handlers ───────────────────────────────────────────────────────────
        self.printer.register_event_handler("klippy:connect",           self._klippy_connect)
        self.printer.register_event_handler("klippy:ready",             self._klippy_ready)
        self.printer.register_event_handler("klippy:firmware_restart",  self._reset)
        self.printer.register_event_handler("homing:home_rails_begin",  self._on_home_begin)
        self.printer.register_event_handler("homing:home_rails_end",    self._on_home_end)

        self.startup_report = ""

        self._homing = False

        self.gcode = self.printer.lookup_object('gcode')
        self.gcode_macro = gcode_macro = self.printer.load_object(cfg, 'gcode_macro')

        # ─────────────────────────────────────────────────[ config ]─────────────────────────────────────────────────
        # ────| primary
        raw_accelerometers          = cfg.getlist ('accelerometer',         '') # Parse ALL accelerometer entries (multi-line or comma-separated)
        self.def_freq               = cfg.getfloat('polling_freq',          1.00,   minval=0.01,    maxval=MAX_POLL_FREQ)
        req_rate                    = cfg.getint  ('polling_rate',          10) # checked/adjusted later

        # ────| crash detection stuff (disabled if not set)
        self.peak_g_thr             = cfg.getfloat('peak_g_threshold',      None,   minval=0.01)
        self.rot_threshold          = cfg.getfloat('rotation_threshold',    None,   minval=0.0,     maxval=180.0)
        self.pitch_threshold        = cfg.getfloat('pitch_threshold',       None,   minval=0.0,     maxval=180.0)
        self.roll_threshold         = cfg.getfloat('roll_threshold',        None,   minval=0.0,     maxval=180.0)

        self.drop_mintime           = cfg.getfloat('drop_mintime',          1.0,    minval=0.0)
        self.drop_template          = gcode_macro.load_template(cfg, 'crash_gcode', '')

        # ────| angle checking stuff
        self.hysteresis             = cfg.getfloat('angle_hysteresis',      5.0,    minval=0.1,     maxval=180.0)
        self.angle_exceed_template = self.gcode_macro.load_template(cfg, 'angle_exceed_gcode', '')
        self.angle_return_template = self.gcode_macro.load_template(cfg, 'angle_return_gcode', '')

        # ────| secondary
        self.decimals               = cfg.getint('decimals', 3, minval=0, maxval=10)

        self.session_time           = cfg.getfloat('session_time',          1.00,   minval=0.01,    maxval=60)
        self.current_samples        = cfg.getint  ('current_samples',       10,      minval=0)

        statistics_mode = {'median': statistics.median,'mean'  : statistics.mean,}
        global _STATISTIC_FN 
        _STATISTIC_FN = cfg.getchoice('samples_result', statistics_mode, 'median')
        # ────| ensure valid if not errored before.
        self.def_rate = min(_RATE_CHOICES, key=lambda x: abs(x - req_rate))
        if self.def_rate != req_rate:
            self.startup_report += f"[tool_drop_detection] polling_rate {req_rate} Hz is not " f"supported; using closest {self.def_rate} Hz instead."
        

        raw_acc = [n.strip() for line in raw_accelerometers for n in str(line).split(',') if n.strip()]
        if not raw_acc:
            raise cfg.error("tool_drop_detection: the 'accelerometer' option must list at least one "
                            "ADXL345 section/alias (e.g. 'T1,T2' or multiple lines).")

        # ── build two-way name maps ───────────────────────────────────────────────
        self._build_name_mappings(raw_acc)

        # ── prepare per-axis defaults ──────────────────────────
        self.config_defaults = {}
        self.defaults = {}

        for short in self.full_to_short.values():
            raw_def = cfg.get(f"default_{short}", None)
            vals = _parse_default_line(raw_def) if raw_def else {}

            self.defaults[short] = {
                'base_g'      : vals.get('g', 1.0),
                'base_pitch'  : vals.get('p', 0.0),
                'base_roll'   : vals.get('r', 0.0),
                'base_vector' : vals.get('v', (0.0, 0.0, 1.0)),
            }
            self.config_defaults[short] = copy.deepcopy(self.defaults[short])

        self.readers: Dict[str, _Reader] = {
            short: _Reader(self.printer, full)
            for full, short in self.full_to_short.items()
        }
        self.pollers: Dict[str, _Poller] = {}  # ── created on TDD_POLLING_START

        # ── shared UI data store, keyed by SHORT alias ─────────────────────────────
        self._data = {
            short: {
                'current':  {            # set by _cmd_query  / poller
                    'vector':    {'x': 0, 'y': 0, 'z': 0},
                    'magnitude': 0,
                    'rotation':  {'pitch': 0, 'roll': 0, 'vector': 0},
                },
                
                'default':  {                # reference baseline
                    'base_g'     : 1.0,
                    'base_vector': {'x': 0, 'y': 0, 'z': 0},
                    'base_pitch' : 0.0,
                    'base_roll'  : 0.0,
                },
                
                'session':  {            # -------- continuously updated by pollers -------------------- 
                    'peak': 0,           # max-g seen
                    'magnitude': 0,      # rolling avg-g
                    'rotation': {'pitch': 0, 'roll': 0, 'vector': 0},
                },
            }
            for short in self.full_to_short.values()
        }

        self.printer.add_object('tool_drop_detection', self) # dunno

        # ── register gcode commands ───────────────────────────────────────────────────────────
        self.gcode.register_command('TDD_POLLING_START',    self._cmd_polling_start,        desc=self.cmd_TDD_POLLING_START_help)
        self.gcode.register_command('TDD_POLLING_STOP',     self._cmd_polling_stop,         desc=self.cmd_TDD_POLLING_STOP_help)
        self.gcode.register_command('TDD_POLLING_RESET',    self._cmd_polling_reset,        desc=self.cmd_TDD_POLLING_RESET_help)
        self.gcode.register_command('TDD_QUERY',            self._cmd_query,                desc=self.cmd_TDD_QUERY_help)
        self.gcode.register_command('TDD_REFERENCE_DUMP',   self._cmd_dump_reference,       desc=self.cmd_TDD_REFERENCE_DUMP_help)
        self.gcode.register_command('TDD_REFERENCE_SET',    self._cmd_set_reference,        desc=self.cmd_TDD_REFERENCE_SET_help)
        self.gcode.register_command('TDD_REFERENCE_RESET',  self._cmd_reset_reference,      desc=self.cmd_TDD_REFERENCE_RESET_help)
        self.gcode.register_command('TDD_START',            self._cmd_start_crash_detect,   desc=self.cmd_TDD_START_help)
        self.gcode.register_command('TDD_STOP',             self._cmd_stop_crash_detect,    desc=self.cmd_TDD_STOP_help)


    def _build_name_mappings(self, raw_acc):
        self.name_to_full: Dict[str,str] = {}
        self.full_to_short: Dict[str,str] = {}
        for raw in raw_acc:
            parts = raw.split(None, 1)
            if len(parts) == 2:
                full  = raw
                short = parts[1] # already "adxl345 Tn"
            else:
                
                short = raw
                full  = f"adxl345 {short}" # assume 'T1' == 'adxl345 T1'

            # register both lookups
            self.name_to_full[raw] = full
            self.name_to_full[full] = full
            self.full_to_short[full] = short

    def _klippy_ready(self): # i dunno if this even works
        if self.startup_report:
            self.gcode.respond_info(self.startup_report)
            self.startup_report = ""

    # ─── homing handlers ────────────────────────────────────────────
    def _on_home_begin(self, *_):
        self._homing = True
        for p in self.pollers.values(): # fast flush so we don’t accumulate unread samples
            p.helper.request_start_time = self.printer.get_reactor().monotonic()

    def _on_home_end(self, *_):
        self._homing = False
        for p in self.pollers.values():
            p.reset() # clear windows so readings not polluted by stale data

    # ─── COMMON CONVERSION ────────────────────────────────────────────────────
    def _build_context(self, accel_name, pitch, roll, angle, mag, peak):
        """Return the dict passed to templates"""
        rnd = self.decimals
        return {
            'accelerometer':    accel_name,       # NOT accel*l*erometer (words are hard)
            'pitch':            round(pitch,    rnd),
            'roll':             round(roll,     rnd),
            'vector':           round(angle,    rnd),
            'magnitude':        round(mag,      rnd),
            'peak':             round(peak,     rnd),
        }
    # for UI / REST ------------------------------------------------------
    def get_status(self, *_):
        return self._data

    def run_gcode(self, template, extra_context):
        # template is a template object, not raw string!!
        ctx = { **template.create_template_context(),
                **extra_context }
        template.run_gcode_from_command(ctx)
    
    def _targets(self, gcmd) -> List[str]:
        acc = gcmd.get('ACCEL', '').strip()
        if not acc:
            return list(self.readers) #all
        else:
            requested = [n.strip() for n in acc.split(',') if n.strip()]
            unknown = [n for n in requested if n not in self.readers]
            if unknown:
                raise gcmd.error(f"Unknown accelerometer(s) requested in ACCEL: {', '.join(unknown)}")
            return requested

    def _klippy_connect(self): # once up actually get it 
        self.chips: Dict[str,object] = {}
        # resolve each full section name from name_to_full
        for full in set(self.name_to_full.values()):
            chip = self.printer.lookup_object(full, default=None)
            if chip is None:
                raise self.printer.config.error(f"tool_drop_detection: cannot find accelerometer section '{full}'")
            self.chips[full] = chip

    def _rate(self, gcmd): #todo add accelerometer type
        rate_req = int(gcmd.get('RATE', self.def_rate))
        rate = min(_RATE_CHOICES, key=lambda x: abs(x - rate_req))
        if rate != rate_req:
            gcmd.respond_info(f"RATE {rate_req} not supported, using {rate}")
        return rate

    # ─── POLLING COMMANDS ──────────────────────────────────────────────────────────────────────────
    cmd_TDD_POLLING_START_help = """[ACCEL] [FREQ] [RATE] - Start polling accelerometer(s) \
    optional frequency and data rate to overwrite config defined."""
    def _cmd_polling_start(self, gcmd):
        wait = gcmd.get('ASYNC', 'TRUE') == 'FALSE'

        freq_req = float(gcmd.get('FREQ', self.def_freq))
        freq = min(freq_req, MAX_POLL_FREQ)
        if freq != freq_req:
            gcmd.respond_info(f"FREQ clamped to {freq} Hz (MAX_POLL_FREQ)")

        rate = self._rate(gcmd)

        started = []
        for n in self._targets(gcmd):
            if n not in self.pollers:
                self.pollers[n] = _Poller(self, n, freq, rate)
                started.append(n)

        if started:
            msg = ", ".join(f"{n} (freq={freq} Hz, rate={rate} Hz)"
                            for n in started)
            gcmd.respond_info("Started: " + msg)
        else:
            gcmd.respond_info("Started: none")

    cmd_TDD_POLLING_STOP_help = '[ACCEL] - Stop polling accelerometer(s)'
    def _cmd_polling_stop(self, gcmd):
        stopped: List[str] = []
        for n in self._targets(gcmd):
            p = self.pollers.pop(n, None)
            if p:
                p.stop(); stopped.append(n)
        gcmd.respond_info('Stopped: ' + (', '.join(stopped) if stopped else 'none'))

    cmd_TDD_POLLING_RESET_help = '[ACCEL] - Reset polling session data'
    def _cmd_polling_reset(self, gcmd):
        r = []
        for n in self._targets(gcmd):
            if n in self.pollers: 
                self.pollers[n].reset()
                r.append(n)

        gcmd.respond_info('Session reset for: ' + ', '.join(r))
            

    def _reset(self):
        _ = None
        #for n in self._targets(None):
            #p = self.pollers.pop(n, None)
            #if p:
                #p.stop();
    # ─────────────────────────────────────────────────────────────────────────────

    cmd_TDD_START_help = 'optional [ACCEL=…] [LIMIT_G=<g-force>] [LIMIT_ANGLE=<deg>] [LIMIT_PITCH=<deg>] [LIMIT_ROLL=<deg>] Start crash detection with optional limits'
    def _cmd_start_crash_detect(self, gcmd):  
        targets = self._targets(gcmd)

        lim_angle = gcmd.get_float('LIMIT_ANGLE', None)
        lim_pitch = gcmd.get_float('LIMIT_PITCH', None)
        lim_roll  = gcmd.get_float('LIMIT_ROLL',  None)
        lim_g     = gcmd.get_float('LIMIT_G',     None)

        # ── 3  Derive effective thresholds with clear precedence ─────────────────
        g_limit = lim_g if lim_g is not None else self.peak_g_thr

        if lim_angle is not None:
            # A vector-angle limit overrides any pitch/roll pair.
            angle_limit = lim_angle
            pitch_limit = roll_limit = None
            if lim_pitch is not None or lim_roll is not None:
                gcmd.respond_info("LIMIT_ANGLE overrides LIMIT_PITCH / LIMIT_ROLL")
        elif lim_pitch is not None or lim_roll is not None:
            # At least one axis-specific limit supplied.
            angle_limit = None
            pitch_limit = lim_pitch
            roll_limit  = lim_roll
        else:
            # No CLI parameters - fall back to config defaults.
            angle_limit = self.rot_threshold
            pitch_limit = self.pitch_threshold
            roll_limit  = self.roll_threshold

        # Fail fast if nothing configured at all.
        if g_limit is None and angle_limit is None and pitch_limit is None and roll_limit is None:
            raise gcmd.error("No crash-detection limits supplied and nothing configured")

        # ── 4  Program each poller & echo armed thresholds ───────────────────────
        for name in targets:
            poller = self.pollers.get(name)
            if poller is None:
                gcmd.respond_info(f"failed to arm {name}, not polling.")
                continue

            # reset state & install limits
            poller.drop_enabled = True
            poller.drop_timer   = None
            poller.g_limit      = g_limit
            poller.angle_limit  = angle_limit
            poller.pitch_limit  = pitch_limit
            poller.roll_limit   = roll_limit

            # build a concise per-accel confirmation message
            msg = [f"armed {name}"]
            if g_limit is not None:
                msg.append(f"±{g_limit} g")
            if angle_limit is not None:
                msg.append(f"vector ±{angle_limit}°")
            else:
                if pitch_limit is not None:
                    msg.append(f"pitch ±{pitch_limit}°")
                if roll_limit is not None:
                    msg.append(f"roll ±{roll_limit}°")
            gcmd.respond_info(" | ".join(msg))


    cmd_TDD_STOP_help = '[ACCEL] - Disarms both high-G and angular crash detection for specified accelerometer(s)'
    def _cmd_stop_crash_detect(self, gcmd):
        targets = self._targets(gcmd)
        # Determine if this even maeks sense
        active = []
        for n in targets:
            p = self.pollers.get(n)
            if p and p.drop_enabled:
                active.append(n)
        if not active:
            gcmd.respond_info("Cannot disable drop detection, inactive.")
            return
        # Disarm thresholds and timers for active targets
        for n in active:
            p = self.pollers.get(n)
            if p:
                p.drop_enabled = False
                p.drop_timer   = None
                p.g_limit       = None
                p.angle_limit   = None
                p.pitch_limit   = None
                p.roll_limit    = None
        gcmd.respond_info("Drop detection disabled for: " + ",".join(active))


    cmd_TDD_REFERENCE_RESET_help = '[ACCEL] - Reset reference baseline to config defaults'
    def _cmd_reset_reference(self, gcmd):
        for short in self._targets(gcmd) or self.readers:
            self.defaults[short] = copy.deepcopy(self.config_defaults[short])
            self._data[short]['default'].update(self.defaults[short])


    cmd_TDD_REFERENCE_SET_help = '[ACCEL] - Set reference baseline data from the current session'
    def _cmd_set_reference(self, gcmd):
        stored, targets = 0, self._targets(gcmd) or list(self.readers)
        for short in targets:
            poll  = self.pollers.get(short)
            if poll:                                # reuse live window
                poll._update_reference(poll.xyz_history)
            else:                                   # one-shot reader
                samples = self.readers[short].window(1)
                if not samples:
                    gcmd.respond_info(f"[TDD] no data from '{short}'"); continue
                tmp = types.SimpleNamespace(parent=self, short=short, dec=self.decimals, defaults=self.defaults[short]) #hack
                _Poller._update_reference(tmp, samples)   # type: ignore # static method call
            stored += 1
        gcmd.respond_info(f"[tool_drop_detection] stored {stored} reference set(s)")


    cmd_TDD_REFERENCE_DUMP_help = '[ACCEL] - Dump current reference baseline data to console for copying'
    def _cmd_dump_reference(self, gcmd):
        for short in self._targets(gcmd) or self._data:
            d = self.defaults.get(short, {})
            bg  = round(d.get('base_g',     0.0), 3)
            bp  = round(d.get('base_pitch', 0.0), 3)
            br  = round(d.get('base_roll',  0.0), 3)
            bv  = d.get('base_vector', (0.0,0.0,0.0))
            vx,vy,vz = (round(bv[i], 3) for i in range(3))

            gcmd.respond_info(f"default_{short}: [g:{bg}  p:{bp}°  r:{br}°  vec:({vx},{vy},{vz})]")


    cmd_TDD_QUERY_help = '[ACCEL] - Query current accelerometer orientation data, prints to console and updates objects current'
    def _cmd_query(self: ToolDropDetection, gcmd):
        targets = self._targets(gcmd) or list(self.readers)
        for short in targets:
            poll = self.pollers.get(short)
            if poll:
                raw = list(poll.xyz_history)
                tup_samples = _strip_timestamps(raw) if raw and hasattr(raw[0], "accel_x") else raw
            else:
                tup_samples = self.readers[short].window(_DWELL_GRAB)
                if not tup_samples:
                    gcmd.respond_info(f"[TDD] no data from '{short}'");
                    continue
            
            tmp = types.SimpleNamespace(parent=self, short=short, dec=self.decimals, defaults=self.defaults[short])
            avrg = _average_samples(tup_samples, -self.current_samples)
            if poll:
                poll._update_current(avrg)
            else:
                _Poller._update_current(tmp, avrg) #hack

            cur = self._data[short]['current']
            rot = cur['rotation']
            gcmd.respond_info(
                f"[{short}] mag={cur['magnitude']}g  "
                f"pitch={rot['pitch']}° roll={rot['roll']}° "
                f"angle={rot['vector']}°"
            )


def load_config(cfg):
    return ToolDropDetection(cfg)

# ───────────────────────────── one-shot / window reader ──────────────
class _Reader:
    def __init__(self, printer, name):
        self.printer, self.name = printer, name
        self._chip = None

    def _chip_obj(self):
        if self._chip is None:
            self._chip = (
                self.printer.lookup_object(self.name, default=None)
                or self.printer.lookup_object(f"adxl345 {self.name}", default=None) # dunno which one works too lazy to check
            )
        return self._chip

    def _capture(self, dwell_s):
        """Low-level helper: open client → dwell → close → return raw list."""
        chip = self._chip_obj()
        if chip is None:
            return []
        helper = chip.start_internal_client()
        self.printer.lookup_object('toolhead').dwell(dwell_s)
        helper.finish_measurements()
        samples = helper.get_samples()
        helper.is_finished = True
        return samples

    def grab(self, dwell: float = _DWELL_GRAB):# -> None | tuple[Any, Any, Any]:
        """Return **one** (x,y,z) tuple or None."""
        sam = self._capture(dwell)
        return None if not sam else (
            sam[-1].accel_x, sam[-1].accel_y, sam[-1].accel_z)

    def window(self, duration_s: float = 1.0):# -> list[tuple[Any, Any, Any]]:
        """Return **list**[tuple(x,y,z)] gathered over ‘duration_s’."""
        raw = self._capture(duration_s)
        return [(s.accel_x, s.accel_y, s.accel_z) for s in raw]

# ───────────────────────────── continuous poller ──────────────────────
class _Poller:
    def __init__(self, parent, name: str, freq: float, rate: int):
        self.parent = parent
        self.name = name

        #self.test = 0

        self.full   = parent.name_to_full[name]
        self.short  = parent.full_to_short[self.full]
        self.chip   = parent.chips[self.full]

        self.overrun = 0
        self.dec = parent.decimals
        self.period = 1.0 / freq

        self.outside = False  # -> angle_exceed_gcode|angle_return_gcode

        self.drop_enabled = False      # TDD_START arms this
        self.drop_timer   = None       # used for hit-and-run logic

        self.defaults  = parent.defaults[name]
        # ─── WINDOW FOR AVREAGING─────────────────────────────────────────────────────────
        self.xyz_history: Deque[Tuple[float,float,float]] = collections.deque(maxlen=max(1, int(parent.session_time * freq)))

        # ensure correct BW_RATE
        self.prev_rate = getattr(self.chip, 'data_rate', rate)
        if rate != self.prev_rate:
            self.chip.set_reg(0x2C, adxl345.QUERY_RATES[rate]) #fix guard against non adxl
            self.chip.data_rate = rate

        self.angle_limit, self.pitch_limit, self.roll_limit, self.g_limit = None, None, None, None

        self.toolhead = self.parent.printer.lookup_object('toolhead') 
        self.helper = self.chip.start_internal_client()
        self.reactor = parent.printer.get_reactor()
        self.timer = self.reactor.register_timer(self._tick, self.reactor.monotonic())
        


        # ─── PRIME WINDOW ─────────────────────────────────────────────────────────
        # ALREADY DONE IN ADXL INTERALLY WITH """self.chip.start_internal_client()"""
        #
        #now = self.toolhead.get_last_move_time()
        #self.helper.request_start_time = now
        #self.helper.request_end_time   = now
    
    def _update_reference(self, xyz_samples):
        if not xyz_samples:
            return
        avrg        = _average_samples(xyz_samples)
        raw_vec     = _raw_to_vector(avrg, self.defaults)
        pitch, roll = _vector_to_angles(raw_vec, {})
        mag_g       = _vector_to_magnitude(raw_vec)

        # update the canonical defaults
        new_ref = {
            'base_g'     : round(mag_g, self.dec),
            'base_pitch' : round(pitch, self.dec),
            'base_roll'  : round(roll, self.dec),
            'base_vector': tuple(round(axis, self.dec) for axis in raw_vec),
        }
        self.defaults.update(new_ref)                # local fast-path
        self.parent.defaults[self.short].update(new_ref)
        self.parent._data[self.short]['default'].update(new_ref)

        if hasattr(self, 'xyz_history'):             # reset rolling window
            self.xyz_history.clear()

    def _update_current(self: _Poller, avrg_xyz: Tuple[float, float, float]):
        vector          = _raw_to_vector(avrg_xyz, self.defaults)
        pitch, roll     = _vector_to_angles(vector, self.defaults)
        mag             = _vector_to_magnitude(vector)
        angle           = _vector_angle(vector, self.defaults)

        (gx, gy, gz) = vector
        current = self.parent._data[self.short]['current']
        current['magnitude'] = round(mag, self.dec)
        current['vector'] = {'x': round(gx, self.dec), 'y': round(gy, self.dec), 'z': round(gz, self.dec)}
        current['rotation'] = {'pitch':round(pitch, self.dec), 'roll':round(roll, self.dec), 'vector':round(angle , self.dec)}

        # ─── UPDATE STATE ───────────────────────────────────────
    def _update_session(self, xyz_samples):
        session = self.parent._data[self.short]['session']
        self.xyz_history.append(_average_samples(xyz_samples)) # add to rolling history
        sess_raw = _average_samples(self.xyz_history)

        raw_mags = (_vector_to_magnitude(_raw_to_vector(v, self.defaults)) for v in xyz_samples)
        max_raw  = max(raw_mags)  # highest magnitude in this batch
        peak     = max(session['peak'], max_raw)

        vector      = _raw_to_vector(sess_raw, self.defaults)
        pitch, roll = _vector_to_angles(vector, self.defaults)
        mag         = _vector_to_magnitude(vector)
        angle       = _vector_angle(vector, self.defaults)

        session['magnitude'] = round(mag, self.dec)
        session['peak'] =  round(peak, self.dec)
        session['rotation']  = {'pitch': round(pitch, self.dec), 'roll': round(roll, self.dec), 'vector': round(angle, self.dec)}

    def _check_angle_exceed(self, angle, pitch, roll, ctx):
        hyst      = self.parent.hysteresis        # hysteresis band
        tp        = self.parent.pitch_threshold   # may be None
        tr        = self.parent.roll_threshold
        tv        = self.parent.rot_threshold     # vector-angle threshold (deg)

        use_pr = (tp is not None) or (tr is not None)   # “pitch or roll?”
        use_tv = (not use_pr) and (tv is not None)      # “vector only”

        # ─── evaluate thresholds ------------------------------------------
        # initialise so they are always defined
        pitch_over = roll_over = angle_over = False
        pitch_back = roll_back = True        # True so they don’t veto `back`
        angle_back = True

        if use_pr:
            pitch_over = tp is not None and abs(pitch) >= tp
            roll_over  = tr is not None and abs(roll)  >= tr

            pitch_back = tp is None or abs(pitch) < (tp - hyst)
            roll_back  = tr is None or abs(roll)  < (tr - hyst)

            # angle_* are neutral when pitch/roll are active
            angle_over = False
            angle_back = True

        elif use_tv:
            angle_over = angle is not None and angle >= tv
            angle_back = angle is None or angle < (tv - hyst)

            # pitch/roll are neutral when vector is active
            pitch_over = roll_over = False
            pitch_back = roll_back = True

        else:
            return

        # ─── state machine & templating -----------------------------------
        over = pitch_over or roll_over or angle_over
        back = pitch_back and roll_back and angle_back

        if over and not self.outside:
            self.outside = True
            if self.parent.angle_exceed_template:
                self.parent.run_gcode(self.parent.angle_exceed_template, ctx)

        elif back and self.outside:
            self.outside = False
            if self.parent.angle_return_template:
                self.parent.run_gcode(self.parent.angle_return_template, ctx)

    def _check_drop(self, angle, pitch, roll, peak, context):
        # ─── PEAK-G drop detection (instant) ───────────────────────────
        if not self.parent.drop_template:
            return
        
        if self.g_limit is not None and peak >= self.g_limit:
            self.drop_enabled = False # disable after triggering.
            self.parent.run_gcode(self.parent.drop_template, context)

        # ─── crash gcode threshold drop detection ────────────────────────
        if self.drop_enabled:
            if self.angle_limit is not None:
                over_ang = angle is not None and angle >= self.angle_limit
            else:
                over_ang = False
                if self.pitch_limit is not None and abs(pitch) >= self.pitch_limit:
                    over_ang = True
                if self.roll_limit is not None and abs(roll) >= self.roll_limit:
                    over_ang = True

            if over_ang:
                now = self.reactor.monotonic()
                if self.drop_timer is None:
                    self.drop_timer = now
                elif (now - self.drop_timer) >= self.parent.drop_mintime:
                    self.drop_enabled = False
                    self.parent.run_gcode(self.parent.drop_template, context)
            else:
                self.drop_timer = None
    # ─── POLLER TICK ───────────────────────────────────────────────────
    def _tick(self, ev):
        # ──────────────────── dont bug MCUs while homing
        if self.parent._homing:
            return ev + self.period
        # ──────────────────── timing stuffs ────────────────────
        #self.helper.request_end_time = self.reactor.monotonic() # NEVER self.toolhead.get_last_move_time() # NEVER self.reactor.monotonic()

        cur_pt = self.toolhead.mcu.estimated_print_time(self.reactor.monotonic())
        self.helper.request_end_time = cur_pt


        try:
            samples = self.helper.get_samples()
        except TimeoutError as e: # message adxl not responding
            self.parent.gcode.respond_info(f"'{self.full}' timeout")
            #self.helper.request_start_time = self.helper.request_end_time
            return ev + self.period
        except Exception as e:
            self.stop() # dunno if we fail here, may we fail there? eh what gives, error is shifted
            self.helper.request_start_time = self.helper.request_end_time # tells it "give up on previous"
            self.parent.gcode.respond_info(f"'{self.full}' not responding - {e}")
            return self.reactor.NEVER 

        if not samples:
            return ev + self.period
        
        # ──────────────────── actual values get gotten, set last time etc... ────────────────────
        sample_ts = samples[-1].time
        self.helper.request_start_time = sample_ts # tell it to void anything before "samples[-1].time" (we got that now, dont need it again)

        #if (self.test % 100):
        #    self.parent.gcode.respond_info(f'sample_ts: {sample_ts}, cur_pt: {cur_pt}, reactor: {self.reactor.monotonic()}')
        #    self.test = 0
        #self.test = self.test + 1

        while self.helper.msgs and self.helper.msgs[0]['data'][-1][0] < sample_ts: #todo check if this actually needed? cant hurt i think. (prob very needed)
            self.helper.msgs.pop(0)


        xyz_samples = _strip_timestamps(samples)
        
        current_average = _average_samples(xyz_samples, -self.parent.current_samples)
    
        # ────────────────────
        cur_vector          = _raw_to_vector(current_average, self.defaults)
        cur_pitch, cur_roll = _vector_to_angles(cur_vector, self.defaults)
        cur_mag             = _vector_to_magnitude(cur_vector)
        cur_vector_angle    = _vector_angle(cur_vector, self.defaults)

        
        self._update_session(xyz_samples)#──[ session always rolling with time.
       
        self._update_current(current_average)#──[ current ones, always fairly up to date.

        cur_peak = max(_vector_to_magnitude(_raw_to_vector(v, self.defaults)) for v in xyz_samples)
        template_context = self.parent._build_context(self.name, cur_pitch, cur_roll, cur_vector_angle, cur_mag, cur_peak)
        
        self._check_angle_exceed(cur_vector_angle, cur_pitch, cur_roll, template_context)
        self._check_drop(cur_vector_angle, cur_pitch, cur_roll, cur_peak, template_context)
            
        now = self.reactor.monotonic()
        if now - ev > self.period * 1.2: # 20% too late!
            self.overrun += 1
            if self.overrun >= 5:  # five consecutive overruns -> chillax
                self.period *= 2   # halve the polling frequency
                self.overrun = 0   # could also reduce poling rate, but idk if that would kill adxl while polling lol
                self.parent.gcode.respond_info(f"oops, dont die on me! (reactor too busy) throttled {self.full} to {1/self.period:.1f} Hz)")
        else:
            self.overrun = 0

        return ev + self.period

    def reset(self):
        self.xyz_history.clear()
        # self.helper.msgs.clear() #todo maybe this too? just cause... idk?
        sess = self.parent._data[self.short]['session']
        sess['peak']      = 0
        sess['magnitude'] = 0
        sess['rotation']  = {'pitch': 0, 'roll': 0, 'vector': 0}
        
    def stop(self):
        self.xyz_history.clear()
        self.chip.set_reg(0x2C, adxl345.QUERY_RATES[self.prev_rate]) #fix isnt this really dumb?
        r = self.reactor
        if self.timer:
            r.update_timer(self.timer, r.NEVER)
        r.register_callback(lambda e=None: self.helper.finish_measurements())
