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
        record = False

        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True) 

        printer_config = os.path.join(home_dir, "printer_data/config/printer.cfg")

        tc_config_multi_file = os.path.join(config_dir, f"tc_config_multi.cfg")
        tc_config_single_file = os.path.join(config_dir, f"tc_config_single.cfg")

        with open(printer_config) as file:
            for line in file:
                if "variable_dock:" in line.strip():
                    if "False" in line.strip():
                        self.gcode.respond_info("Dock is installed...")
                    elif "True" in line.strip():
                        self.gcode.respond_info("Dock is not installed...")

            for line in file:
                ## Record point begin / end
                if "#;<" in line.strip() and record == False:
                    record = True
                if "#;>" in line.strip() and record == True :
                    record = False

                # self.gcode.respond_info("Record: " + str(record))



def load_config(config):
    return ConfigSwitch(config)
