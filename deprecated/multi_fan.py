# Support multiple part cooling fans.
#
# Copyright (C) 2023-2023  Viesturs Zarins <viesturz@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

from . import fan


# Part cooler fan that is switchable between multiple fans.
# Handles M106 M107 and routes to the active fan.
# Cannot be used at the same time as [fan].
class MultiFan:
    def __init__(self, config):
        self.fan = fan.Fan(config)
        self.name = config.get_name()
        self.fan_name = self.name.split()[-1]

        for k,f in config.get_printer().lookup_objects(module='multi_fan'):
            self.controller = f.controller
            break
        else:
            self.controller = MultiFanController(config)
        self.controller.activate_fan_if_not_present(self.fan)

        gcode = config.get_printer().lookup_object('gcode')
        gcode.register_mux_command("ACTIVATE_FAN", "FAN",
                            self.fan_name, self.cmd_ACTIVATE_FAN,
                            desc=self.cmd_ACTIVATE_FAN_help)
        gcode.register_mux_command("ACTIVATE_FAN", "FAN",
                            self.name, self.cmd_ACTIVATE_FAN,
                            desc=self.cmd_ACTIVATE_FAN_help)
    def get_status(self, eventtime):
        return self.fan.get_status(eventtime)
    cmd_ACTIVATE_FAN_help = 'Set this fan as the active printer fan'
    def cmd_ACTIVATE_FAN(self, gcmd):
        self.controller.activate_fan(self.fan)

class MultiFanController:
    def __init__(self, config):
        self.active_fan = None
        self.requested_speed = None
        gcode = config.get_printer().lookup_object('gcode')
        gcode.register_command("M106", self.cmd_M106)
        gcode.register_command("M107", self.cmd_M107)
    def activate_fan_if_not_present(self, fan):
        if not self.active_fan:
            self.active_fan = fan
    def activate_fan(self, fan):
        # Set new active fan and move the set speed to that fan.
        if self.active_fan == fan:
            return
        if self.active_fan and self.requested_speed is not None:
            self.active_fan.set_speed_from_command(0.)
        self.active_fan = fan
        if self.active_fan and self.requested_speed is not None:
            self.active_fan.set_speed_from_command(self.requested_speed)
    def cmd_M106(self, gcmd):
        # Set fan speed
        self.requested_speed = gcmd.get_float('S', 255., minval=0.) / 255.
        if self.active_fan:
            self.active_fan.set_speed_from_command(self.requested_speed)
    def cmd_M107(self, gcmd):
        # Turn fan off
        self.requested_speed = 0.
        if self.active_fan:
            self.active_fan.set_speed_from_command(self.requested_speed)

def load_config_prefix(config):
    return MultiFan(config)
