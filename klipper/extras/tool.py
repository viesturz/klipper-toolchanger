# Support for toolchnagers
#
# Copyright (C) 2023 Viesturs Zarins <viesturz@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

from . import toolchanger

class Tool:
    def __init__(self, config):
        self.config = config
        printer = config.get_printer()
        toolchanger_name = config.get('toolchanger', 'toolchanger')
        self.toolchanger = printer.load_object(config, toolchanger_name)
        self.base = toolchanger.ToolBase(self)
        self.tool_number = config.getint('tool_number', -1, minval=0)
        self.main_toolchanger = printer.load_object(config, 'toolchanger')

        self.gcode = printer.lookup_object('gcode')
        self.gcode.register_mux_command("ASSIGN_TOOL", "TOOL", self.base.name,
                                        self.cmd_ASSIGN_TOOL,
                                        desc=self.cmd_ASSIGN_TOOL_help)
        if self.tool_number >= 0:
            self.assign_tool(self.tool_number)

        printer.register_event_handler("klippy:connect",
                                       self.base.handle_connect)

    def get_name(self):
        return self.config.get_name()

    def get(self, name, default_value):
        return self.config.get(name,
                               self.toolchanger.config.get(name, default_value))

    def getfloat(self, name, default_value):
        return self.config.getfloat(name, self.toolchanger.config.getfloat(name,
                                                                           default_value))

    def getboolean(self, name, default_value):
        return self.config.getboolean(name,
                                      self.toolchanger.config.getboolean(name,
                                                                         default_value))

    def get_params(self):
        return self.toolchanger.params | toolchanger.get_params_dict(self.config)

    def update_status(self, changes):
        # Nothing here
        pass

    def get_status(self, eventtime):
        return self.base.get_status()

    cmd_ASSIGN_TOOL_help = 'Assign tool to tool number'

    def cmd_ASSIGN_TOOL(self, gcmd):
        self.assign_tool(gcmd.getint('N', minval=0), replace=True)

    def assign_tool(self, number, replace=False):
        prev_number = self.base.tool_number
        self.base.tool_number = number
        self.main_toolchanger.assign_tool(self.base, number, prev_number, replace)
        self._register_t_gcode(number)

    def _register_t_gcode(self, number):
        name = 'T%d' % (number)
        desc = 'Select tool %d' % (number)
        existing = self.gcode.register_command(name, None)
        if existing:
            # Do not mess with existing
            self.gcode.register_command(name, existing, dec=desc)
        else:
            # Register equivalent to a gcode macro calling "SELECT_TOOL Tn"
            tc = self.base.main_toolchanger
            axis = self.base.t_command_restore_axis
            func = lambda gcmd: tc.select_tool(
                gcmd, tc.lookup_tool(number), axis)
            self.gcode.register_command(name, func, desc=desc)


def load_config_prefix(config):
    return Tool(config)
