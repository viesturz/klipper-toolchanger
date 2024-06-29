import os
import logging

class ConfigSwitch:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')

        self.gcode.register_command('SAVE_CONFIG_MODE',
                                    self.cmd_SAVE_CONFIG_MODE,
                                    desc=self.cmd_SAVE_CONFIG_MODE_help)


    cmd_SAVE_CONFIG_MODE_help = "..."
    def cmd_SAVE_CONFIG_MODE(self, gcmd):
        home_dir = os.path.expanduser("~")
        config_dir = os.path.join(home_dir, "printer_data/config/config-test/")
        record_point = False

        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True) 

        printer_config = os.path.join(home_dir, "printer_data/config/printer.cfg")

        tc_config_multi_file = os.path.join(config_dir, f"tc_config_multi.cfg")
        tc_config_single_file = os.path.join(config_dir, f"tc_config_single.cfg")

        with open(printer_config) as file:
            self.gcode.respond_info("Record point: " + str(record_point))
            # for line in file:

            #     if "#;<" in string and record_point == False :
            #         record_point = True
            #         self.gcode.respond_info("Record point: " + str(record_point))

            #     if "#;>" in string and record_point == True :
            #         record_point = False
            #         self.gcode.respond_info("Record point: " + str(record_point))


def load_config(config):
    return ConfigSwitch(config)
