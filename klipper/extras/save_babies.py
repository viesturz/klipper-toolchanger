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
        offset = gcmd.get_float('OFFSET', 0.0)

        self.gcode.respond_info("#*# z_offset = %f" % z_offset)

        self.save_babysteps(gcmd)

    def save_babysteps(self, gcmd):
        ## Variables
        home_dir = os.path.expanduser("~")
        printer_config = os.path.join(home_dir, "printer_data/config/printer_test.cfg")
        destination = os.path.join(home_dir, "printer_data/config/printer_test_0.cfg")

        # active_tool_z_offset = self.active_tool.gcode_z_offset
        # babystep = bstep
        # z_offset = 0.0

        # ## Save session variables
        # with open(printer_config) as file:
        #     if destination != "":
        #         with open(destination, 'w'):
        #             pass
                
        #         for line in file:
        #             ## Calculate value
        #             if "#*# z_offset =" in line.strip():
        #                 for word in line.split():
        #                     if word != "#*#" and word != "z_offset" and word != "=":
        #                         z_offset = float(word) 

        #                 self.gcode.respond_info("#*# z_offset = %f" % z_offset)

        #                 ## Start / Stop record
        #                 with open(destination, 'a') as savefile:
        #                     savefile.write("#*# z_offset = " + str(z_offset) + "\n")

        #             else:
        #                 with open(destination, 'a') as savefile:
        #                     savefile.write(line)

def load_config(config):
    return SaveBabies(config)
