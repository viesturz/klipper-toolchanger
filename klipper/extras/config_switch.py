import os
import logging

class ConfigSwitch:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        ## Register Commands
        self.gcode.register_command('SAVE_CONFIG_MODE',
                                    self.cmd_SAVE_CONFIG_MODE,
                                    desc=self.cmd_SAVE_CONFIG_MODE_help)


    cmd_SAVE_CONFIG_MODE_help = "..."
    def cmd_SAVE_CONFIG_MODE(self, gcmd):
        ## Variables
        home_dir = os.path.expanduser("~")
        destination = ""
        record = False

        printer_config = os.path.join(home_dir, "printer_data/config/printer.cfg")
        config_dir = os.path.join(home_dir, "printer_data/config/config/")
        config_multi = os.path.join(config_dir, "config_multi.cfg")
        config_single = os.path.join(config_dir, "config_single.cfg")

        ## Make the config folder, if it is not already there
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True) 
        
        with open(printer_config) as file:
            for line in file:
                ## Set destination file
                if "variable_dock:" in line.strip():
                    if "True" in line.strip():
                        destination = config_multi
                        with open(destination, 'w'):
                            pass
                    elif "False" in line.strip():
                        destination = config_single
                        with open(destination, 'w'):
                            pass
                    else:
                        raise gcmd.error("[variable_dock: ] must be 'True' or 'False'")
                
        with open(printer_config) as file:
            if destination != "":
                for line in file:
                    ## Record point begin / end
                    if "#;<" in line.strip():
                        record = True
                    if "#;>" in line.strip():
                        record = False
                    
                    ## Start / Stop record
                    if record is True:
                        with open(destination, 'a') as savefile:
                            savefile.write(line)
                
                if "config_multi" in destination:
                    self.gcode.respond_info("Section variables saved to config/config_multi.cfg")
                elif "config_single" in destination:
                    self.gcode.respond_info("Section variables saved to config/config_single.cfg")


def load_config(config):
    return ConfigSwitch(config)
