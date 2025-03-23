# Copyright (C) 2024 Chinh Nhan Vo <nhanvo29@proton.me>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
import os
import logging

class SaveBabies:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        ## Register Commands
        self.gcode.register_command('SAVE_BABYSTEPS', self.cmd_SAVE_BABYSTEPS, desc=self.cmd_SAVE_BABYSTEPS_help)

    cmd_SAVE_BABYSTEPS_help = "[OFFSET=] | Save z-babysteps to config"
    def cmd_SAVE_BABYSTEPS(self, gcmd):
        ## Variables
        z_offset = gcmd.get_float('OFFSET', 0.0)
        ## Command
        if z_offset != 0.0:
            self.save_babysteps(gcmd, z_offset)
        else:
            self.gcode.respond_info("No gcode_z_offset saved")

    def save_babysteps(self, gcmd, babystep):
        ## Variables
        home_dir = os.path.expanduser("~")
        printer_config = os.path.join(home_dir, "printer_data/config/printer.cfg")
        bbs = float(babystep)

        if bbs != 0.0:
            with open(printer_config) as file:
                for line in file:
                    ## find the section variable
                    if "#*# [tool_probe" in line.strip():
                        section = ((line.replace("#*# [", "")).replace("]", "")).replace("\n", "")
                    
                    ## find the z_offset variable and apply the baby-step.
                    if "#*# z_offset =" in line.strip():
                        for word in line.split():
                            if word != "#*#" and word != "z_offset" and word != "=":
                                current_z_offset = float(word)
                                z_offset = current_z_offset - bbs
                        
                        ## [printer.cfg] always checked for error on start-up. It can be reliably expected that the "section" variable is figured
                        ## out before the "current_z_offset" is determined. Therefore, there is no need for further checking function... I think.
                        if section != "tool_probe_endstop":
                            self.gcode.run_script_from_command("TOOL_CALIBRATE_SAVE_TOOL_OFFSET SECTION=\"%s\" ATTRIBUTE=z_offset VALUE=%f" % (section, z_offset))
                            self.gcode.respond_info("[%s] | z_offset = %f" % (section, z_offset))

def load_config(config):
    return SaveBabies(config)
