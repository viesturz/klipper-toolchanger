# Per-tool Z-Probe support
#
# Copyright (C) 2025 Viesturs Zarins <viesturz@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging
from . import probe

class ToolProbe:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.tool_number = config.getint('tool', None)
        self.name = config.get_name()

        pin = config.get('pin')
        ppins = self.printer.lookup_object('pins')
        ppins.allow_multi_use_pin(pin.replace('^', '').replace('!', ''))

        self.mcu_probe = probe.ProbeEndstopWrapper(config)
        self.probe_offsets = probe.ProbeOffsetsHelper(config)
        self.param_helper = probe.ProbeParameterHelper(config)

        if self.tool_number is not None:
            # Crash detection stuff
            buttons = self.printer.load_object(config, 'buttons')
            buttons.register_buttons([pin], self._button_handler)
            #Register with the endstop
            self.endstop = self.printer.load_object(config, "tool_probe_endstop")
            self.endstop.add_probe(config, self)

    def _button_handler(self, eventtime, is_triggered):
        self.endstop.note_probe_triggered(self, eventtime, is_triggered)

def load_config_prefix(config):
    return ToolProbe(config)
