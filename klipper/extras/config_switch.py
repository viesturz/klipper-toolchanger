import os
import logging

class ConfigSwitch:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')

        self.gcode.register_command('SAVE_CONFIG_MODE',
                                    self.cmd_SAVE_CONFIG_MODET,
                                    desc=self.cmd_SAVE_CONFIG_MODE_help)


    cmd_SAVE_CONFIG_MODE_help = "..."
    def cmd_SAVE_CONFIG_MODE(self, gcmd):
        record_point = False
        self.gcode.respond_info("Record point:", record_point)

        home_dir = os.path.expanduser("~")

        config_dir = os.path.join(home_dir, "printer_data/config/config1")
        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir)  

        printer_config = os.path.join(home_dir, "printer_data/config/printer.cfg")

        tc_config_multi = os.path.join(storage_dir, f"tc_config_multi.cfg")
        tc_config_single = os.path.join(storage_dir, f"tc_config_single.cfg")

        with open(printer_config) as file:
            for line in file:
                if "#;#" in string and record_point == False :
                    record_point = True
                    self.gcode.respond_info("Record point:", record_point)
                if "#;#" in string and record_point == True :
                    record_point = False
                    self.gcode.respond_info("Record point:", record_point)


def load_config_switch(config):
    return ConfigSwitch(config)
