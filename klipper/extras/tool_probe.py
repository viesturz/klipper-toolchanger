# Per-tool Z-Probe support
#
# Copyright (C) 2023 Viesturs Zarins <viesturz@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging
from . import probe

class ToolProbe:
    def __init__(self, config):
        self.tool = config.getint('tool')
        self.printer = config.get_printer()
        self.name = config.get_name()
        self.mcu_probe = probe.ProbeEndstopWrapper(config)
        self.probe_offsets = probe.ProbeOffsetsHelper(config)
        self.probe_session = ProbeSessionHelper(config, self.mcu_probe)

        # Crash detection stuff
        pin = config.get('pin')
        buttons = self.printer.load_object(config, 'buttons')
        ppins = self.printer.lookup_object('pins')
        ppins.allow_multi_use_pin(pin.replace('^', '').replace('!', ''))
        buttons.register_buttons([pin], self._button_handler)

        #Register with the endstop
        self.endstop = self.printer.load_object(config, "tool_probe_endstop")
        self.endstop.add_probe(config, self)

    def _button_handler(self, eventtime, is_triggered):
        self.endstop.note_probe_triggered(self, eventtime, is_triggered)

    def get_probe_params(self, gcmd=None):
        return self.probe_session.get_probe_params(gcmd)
    def get_offsets(self):
        return self.probe_offsets.get_offsets()
    def start_probe_session(self, gcmd):
        return self.probe_session.start_probe_session(gcmd)

# Helper to track multiple probe attempts in a single command
class ProbeSessionHelper:
    def __init__(self, config, mcu_probe):
        self.printer = config.get_printer()
        self.mcu_probe = mcu_probe
        gcode = self.printer.lookup_object('gcode')
        self.dummy_gcode_cmd = gcode.create_gcode_command("", "", {})
        # Infer Z position to move to during a probe
        if config.has_section('stepper_z'):
            zconfig = config.getsection('stepper_z')
            self.z_position = zconfig.getfloat('position_min', 0.,
                                               note_valid=False)
        else:
            pconfig = config.getsection('printer')
            self.z_position = pconfig.getfloat('minimum_z_position', 0.,
                                               note_valid=False)
        # Configurable probing speeds
        self.speed = config.getfloat('speed', 5.0, above=0.)
        self.lift_speed = config.getfloat('lift_speed', self.speed, above=0.)
        # Multi-sample support (for improved accuracy)
        self.sample_count = config.getint('samples', 1, minval=1)
        self.sample_retract_dist = config.getfloat('sample_retract_dist', 2.,
                                                   above=0.)
        atypes = {'median': 'median', 'average': 'average'}
        self.samples_result = config.getchoice('samples_result', atypes,
                                               'average')
        self.samples_tolerance = config.getfloat('samples_tolerance', 0.100,
                                                 minval=0.)
        self.samples_retries = config.getint('samples_tolerance_retries', 0,
                                             minval=0)
        # Session state
        self.multi_probe_pending = False
        self.results = []
        # Register event handlers
        self.printer.register_event_handler("gcode:command_error",
                                            self._handle_command_error)
    def _handle_command_error(self):
        if self.multi_probe_pending:
            try:
                self.end_probe_session()
            except:
                logging.exception("Multi-probe end")
    def _probe_state_error(self):
        raise self.printer.command_error(
            "Internal probe error - start/end probe session mismatch")
    def start_probe_session(self, gcmd):
        if self.multi_probe_pending:
            self._probe_state_error()
        self.mcu_probe.multi_probe_begin()
        self.multi_probe_pending = True
        self.results = []
        return self
    def end_probe_session(self):
        if not self.multi_probe_pending:
            self._probe_state_error()
        self.results = []
        self.multi_probe_pending = False
        self.mcu_probe.multi_probe_end()
    def get_probe_params(self, gcmd=None):
        if gcmd is None:
            gcmd = self.dummy_gcode_cmd
        probe_speed = gcmd.get_float("PROBE_SPEED", self.speed, above=0.)
        lift_speed = gcmd.get_float("LIFT_SPEED", self.lift_speed, above=0.)
        samples = gcmd.get_int("SAMPLES", self.sample_count, minval=1)
        sample_retract_dist = gcmd.get_float("SAMPLE_RETRACT_DIST",
                                             self.sample_retract_dist, above=0.)
        samples_tolerance = gcmd.get_float("SAMPLES_TOLERANCE",
                                           self.samples_tolerance, minval=0.)
        samples_retries = gcmd.get_int("SAMPLES_TOLERANCE_RETRIES",
                                       self.samples_retries, minval=0)
        samples_result = gcmd.get("SAMPLES_RESULT", self.samples_result)
        return {'probe_speed': probe_speed,
                'lift_speed': lift_speed,
                'samples': samples,
                'sample_retract_dist': sample_retract_dist,
                'samples_tolerance': samples_tolerance,
                'samples_tolerance_retries': samples_retries,
                'samples_result': samples_result}
    def _probe(self, speed):
        toolhead = self.printer.lookup_object('toolhead')
        curtime = self.printer.get_reactor().monotonic()
        if 'z' not in toolhead.get_status(curtime)['homed_axes']:
            raise self.printer.command_error("Must home before probe")
        pos = toolhead.get_position()
        pos[2] = self.z_position
        try:
            epos = self.mcu_probe.probing_move(pos, speed)
        except self.printer.command_error as e:
            reason = str(e)
            if "Timeout during endstop homing" in reason:
                reason += probe.HINT_TIMEOUT
            raise self.printer.command_error(reason)
        # Allow axis_twist_compensation to update results
        self.printer.send_event("probe:update_results", epos)
        # Report results
        gcode = self.printer.lookup_object('gcode')
        gcode.respond_info("probe at X=%.3f Y=%.3f is z=%.6f"
                           % (epos[0], epos[1], epos[2]))
        return epos[:3]
    def run_probe(self, gcmd):
        if not self.multi_probe_pending:
            self._probe_state_error()
        params = self.get_probe_params(gcmd)
        toolhead = self.printer.lookup_object('toolhead')
        probexy = toolhead.get_position()[:2]
        retries = 0
        positions = []
        sample_count = params['samples']
        sample_retries = params['samples_tolerance_retries']
        while len(positions) < (sample_count * sample_retries):
            # Probe position
            pos = self._probe(params['probe_speed'])
            positions.append(pos)
            more_ok = len(positions) < (sample_count * sample_retries)
            peaks = self.find_sample_peak(gcmd, positions, params['samples_tolerance'], params['samples'])
            if len(peaks) == 1:
                peak = peaks[0]
                if len(peak) >= params['samples']:
                    gcmd.respond_info(f"Peak in data found: {explain_peak(peak)}")
                    positions = list(pos for pos in positions if peak[0] <= pos[2] <= peak[-1])
                    break
            else:
                best_peak, next_best_peak = peaks
                best_text = explain_peak(best_peak)
                next_best_text = explain_peak(next_best_peak)
                next_step = "need more data..." if more_ok else "giving up"
                gcmd.respond_info(f"Found {best_text}; but also {next_best_text}; {next_step}")
            # Retract
            toolhead.manual_move(
                probexy + [pos[2] + params['sample_retract_dist']],
                params['lift_speed'],
            )
            if not more_ok:
                raise gcmd.error(f"Results too scattered even after {len(positions)} sample(s): {','.join(pos[2].__format__('.6f') for pos in positions)}")
        # Calculate result
        epos = probe.calc_probe_z_average(positions, params['samples_result'])
        self.results.append(epos)
    def pull_probed_results(self):
        res = self.results
        self.results = []
        return res
    def find_sample_peak(self, gcmd, positions, window, margin):
        """Finds a significant "peak" within the list of positions.

        This is a brute force approach to find a peak, which could probably be
        replaced by something like a K shortest path routing tree with the
        probe positions, which should allow there to always be a result, with
        just the tolerance narrowing and without the O(N^2) loop here.  Or at
        least preserve the computed results in this function and only recalculate
        the windows within the tolerance of the new probe value.

        Parameters:

        :param positions: the list of position objects from each sample

        :param window: samples must be within this window to be considered towards
                       the same peak

        :param margin: the window must have the most measurements in it vs any
                       other (non–overlapping) window, by this many samples

        Returns:

        List[List[float]] - one list, too short: insufficient data
                            one list, 'margin' or longer: winner found!
                            two lists: would-be winner found (position 0), but
                              runner-up (position 1) too many for it to win
        """
        top_window = []
        all_windows = []
        windows = []

        def shift_windows(pos_z):
            while len(windows) > 0 and windows[0][0] < (pos_z - window):
                shifted_window, windows[:] = windows[0], windows[1:]
                #gcmd.respond_info("find_sample_peak: shifting window: %s" % (shifted_window,))
                all_windows.append(shifted_window)

        for position in sorted(positions, key=lambda pos: pos[2]):
            pos_z = position[2]
            # every point starts a new window, unless it is the same as the previous reading
            if not windows or (windows and windows[-1][-1] < pos_z):
                windows.append([pos_z])
            shift_windows(pos_z)
            for nearby_window in windows[:-1]:
                nearby_window.append(pos_z)

        shift_windows(pos_z + window + 0.01)

        all_windows.sort(key=lambda w: -len(w))
        top_window = all_windows[0]
        top_start = top_window[0]
        top_end = top_start + window
        top_count = len(top_window)
        for runner_up_window in all_windows[1:]:
            if top_count - len(runner_up_window) >= margin:
                break
            window_start = runner_up_window[0]
            if window_start > top_end:
                return [top_window, runner_up_window]
            window_end = window_start + window
            if window_end < top_start:
                return [top_window, runner_up_window]
        return [top_window]


def explain_peak(z_positions):
    if len(z_positions) == 1:
        return f"1 result at {z_positions[0]:.6f}"
    if len(z_positions) == 2:
        return f"2 results at {z_positions[0]:.6f} and {z_positions[1]:.6f}"
    return f"{len(z_positions)} results between {z_positions[0]:.6f} and {z_positions[-1]:.6f}"



def load_config_prefix(config):
    return ToolProbe(config)
