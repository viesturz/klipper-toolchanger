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
        record = False
        destination = ""

        printer_config = os.path.join(home_dir, "printer_data/config/printer.cfg")
        config_dir = os.path.join(home_dir, "printer_data/config/config-test/")
        tc_config_multi_file = os.path.join(config_dir, "tc_config_multi.cfg")
        tc_config_single_file = os.path.join(config_dir, "tc_config_single.cfg")

        ## Make the config folder, if it is not already there
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True) 
        
        with open(printer_config) as file:
            for line in file:
                ## set destination file
                if "variable_dock:" in line.strip():
                    if "True" in line.strip():
                        destination = tc_config_multi_file
                    elif "False" in line.strip():
                        destination = tc_config_single_file
                    else:
                        raise gcmd.error("[variable_dock: ] must be 'True' or 'False'")
            
            if destination != "":
                # self.gcode.respond_info(destination)
                with open(destination, 'w') as file:
                    pass

                for line in file:
                    ## Record point begin / end
                    if "#;<" in line.strip() and record == False:
                        record = True
                    if "#;>" in line.strip() and record == True :
                        record = False                
                    
                    ## Start / Stop record
                    if record == True:
                        with open(destination, 'a') as file:
                            file.write(line)



def load_config(config):
    return ConfigSwitch(config)
