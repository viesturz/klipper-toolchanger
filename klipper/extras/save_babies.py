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

    cmd_SAVE_BABYSTEPS_help = "Save z-babysteps to printer.cfg"
    def cmd_SAVE_BABYSTEPS(self, gcmd):
        ## Variables
        z_offset = gcmd.get_float('OFFSET', 0.0)
        self.gcode.respond_info("Babystep = %f" % z_offset)
        if z_offset != 0.0:
            self.save_babysteps(gcmd, z_offset)

    def save_babysteps(self, gcmd, babystep):
        ## Variables
        home_dir = os.path.expanduser("~")
        printer_config = os.path.join(home_dir, "printer_data/config/printer_test.cfg")
        # ## Input test
        # self.gcode.respond_info("Babystep = %f" % babystep)

        ## offset calculation
        if float(babystep) != 0.0:
            ## Save session variables
            with open(printer_config) as file:                    
                for line in file:
                    if "#*# [tool_probe T" in line.strip():
                        section = ((line.replace("#*# [", "")).replace("]", "")).replace("\n", "")
 
                    ## Calculate value
                    if "#*# z_offset =" in line.strip():
                        for word in line.split():
                            if word != "#*#" and word != "z_offset" and word != "=":
                                z_offset = float(word)

                    # if section and z_offset:
                        self.gcode.respond_info("%s | z_offset = %f" % (section, z_offset))

            # self.gcode.run_script_from_command("_CURRENT_OFFSET")
            # self.gcode.run_script_from_command("TOOL_CALIBRATE_SAVE_TOOL_OFFSET SECTION="tool T{}" ATTRIBUTE=z_offset VALUE={}")

def load_config(config):
    return SaveBabies(config)
