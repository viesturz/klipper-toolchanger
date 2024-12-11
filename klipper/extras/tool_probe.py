# Per-tool Z-Probe support
#
# Copyright (C) 2023 Viesturs Zarins <viesturz@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
# Contribution 2024 by Justin F. Hallett <thesin@southofheaven.org>
import logging
from .probe import PrinterProbe, ProbeSessionHelper, ProbeEndstopWrapper, ProbeOffsetsHelper, calc_probe_z_average

class ToolProbe(PrinterProbe):
    def __init__(self, config):
        self.tool = config.getint('tool')
        self.name = config.get_name()
        
        self.printer = config.get_printer()
        self.mcu_probe = ProbeEndstopWrapper(config)
        # Handled in tool_probe_endstop
        #self.cmd_helper = ProbeCommandHelper(config, self,
        #                                     self.mcu_probe.query_endstop)
        self.probe_offsets = ProbeOffsetsHelper(config)
        self.probe_session = ProbeSessionHelper(config, self.mcu_probe)

        # Crash detection stuff
        pin = config.get('pin')
        buttons = self.printer.load_object(config, 'buttons')
        ppins = self.printer.lookup_object('pins')
        ppins.allow_multi_use_pin(pin.replace('^', '').replace('!', ''))
        buttons.register_buttons([pin], self._button_handler)

        # Register with the endstop
        self.endstop = self.printer.load_object(config, "tool_probe_endstop")
        self.endstop.add_probe(config, self)
    def _button_handler(self, eventtime, is_triggered):
        self.endstop.note_probe_triggered(self, eventtime, is_triggered)


# Helper to track multiple probe attempts in a single command
class ProbeSessionHelper(ProbeSessionHelper):
    def __init__(self, config, mcu_probe):
        self.drop_first_result = config.getboolean("drop_first_result", False)
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
        # Handled in tool_probe_endstop
        # self.homing_helper = HomingViaProbeHelper(config, mcu_probe)
        # Configurable probing speeds
        self.speed = config.getfloat('speed', 5.0, above=0.)
        self.lift_speed = config.getfloat('lift_speed', self.speed, above=0.)
        # Multi-sample support (for improved accuracy)
        self.sample_count = config.getint('samples', 1, minval=1)
        self.sample_retract_dist = config.getfloat('sample_retract_dist', 2.,
                                                   above=0.)
        atypes = ['median', 'average']
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
    def run_probe(self, gcmd, check_drop=True):
        if not self.multi_probe_pending:
            self._probe_state_error()
        params = self.get_probe_params(gcmd)
        toolhead = self.printer.lookup_object('toolhead')
        probexy = toolhead.get_position()[:2]
        retries = 0
        positions = []
        sample_count = params['samples']
        first_probe = True
        while len(positions) < sample_count:
            # Probe position
            pos = self._probe(params['probe_speed'])
            if check_drop and self.drop_first_result and first_probe:
                gcmd.respond_info("dropping probe result, settling")
            else:
                positions.append(pos)
                # Check samples tolerance
                z_positions = [p[2] for p in positions]
                if max(z_positions)-min(z_positions) > params['samples_tolerance']:
                    if retries >= params['samples_tolerance_retries']:
                        raise gcmd.error("Probe samples exceed samples_tolerance")
                    gcmd.respond_info("Probe samples exceed tolerance. Retrying...")
                    retries += 1
                    positions = []
            first_probe = False
            # Retract
            if len(positions) < sample_count:
                toolhead.manual_move(
                    probexy + [pos[2] + params['sample_retract_dist']],
                    params['lift_speed'])
        # Calculate result
        epos = calc_probe_z_average(positions, params['samples_result'])
        self.results.append(epos)


def load_config_prefix(config):
    return ToolProbe(config)
