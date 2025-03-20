# Support for toolchangers
#
# Copyright (C) 2023 Viesturs Zarins <viesturz@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
# Contribution 2024 by Justin F. Hallett <thesin@southofheaven.org>

import ast, bisect

STATUS_UNINITALIZED = 'uninitialized'
STATUS_INITIALIZING = 'initializing'
STATUS_READY = 'ready'
STATUS_CHANGING = 'changing'
STATUS_ERROR = 'error'
INIT_ON_HOME = 0
INIT_MANUAL = 1
INIT_FIRST_USE = 2
ON_AXIS_NOT_HOMED_ABORT = 0
ON_AXIS_NOT_HOMED_HOME = 1
XYZ_TO_INDEX = {'x': 0, 'X': 0, 'y': 1, 'Y': 1, 'z': 2, 'Z': 2}
INDEX_TO_XYZ = 'XYZ'

class Toolchanger:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.config = config
        self.gcode_macro = self.printer.load_object(config, 'gcode_macro')
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode_move = self.printer.load_object(config, 'gcode_move')

        self.name = config.get_name()
        self.params = get_params_dict(config)
        init_options = {'home': INIT_ON_HOME, 'manual': INIT_MANUAL, 'first-use': INIT_FIRST_USE}
        self.initialize_on = config.getchoice('initialize_on', init_options, 'first-use')
        self.uses_axis = config.get('uses_axis', 'xyz').lower()
        home_options = {'abort': ON_AXIS_NOT_HOMED_ABORT, 'home': ON_AXIS_NOT_HOMED_HOME}
        self.on_axis_not_homed = config.getchoice('on_axis_not_homed', home_options, 'abort')
        self.initialize_gcode = self.gcode_macro.load_template(config, 'initialize_gcode', '')
        self.default_before_change_gcode = self.gcode_macro.load_template(config, 'before_change_gcode', '')
        self.default_after_change_gcode = self.gcode_macro.load_template(config, 'after_change_gcode', '')

        # Read all the fields that might be defined on toolchanger.
        # To avoid throwing config error when no tools configured.
        config.get('pickup_gcode', None)
        config.get('dropoff_gcode', None)
        config.getfloat('gcode_x_offset', None)
        config.getfloat('gcode_y_offset', None)
        config.getfloat('gcode_z_offset', None)
        config.get('t_command_restore_axis', None)
        self.homing_current = config.getfloat('homing_current', 0.5)
        self.stepper_driver = config.get('stepper_driver', 'tmc5160')
        self.sensorless_x = config.getboolean('sensorless_x', False)
        self.sensorless_y = config.getboolean('sensorless_y', False)
        self.homing_usetap = config.getboolean('homing_usetap', True)
        self.homing_toolless = config.getboolean('homing_toolless', False)
        self.tools_preheat = config.getboolean('tools_preheat', True)
        self.homing_rebound_y = config.getfloat('homing_rebound_y', config.getfloat('homing_safe_y', 20.0))
        config.get('extruder', None)
        config.get('fan', None)
        config.get_prefix_options('params_')

        self.status = STATUS_UNINITALIZED
        self.active_tool = None
        self.tools = {}
        self.tool_numbers = [] # Ordered list of registered tool numbers.
        self.tool_names = [] # Tool names, in the same order as numbers.
        self.error_message = ''

        self.printer.register_event_handler("homing:home_rails_begin",
                                            self._handle_home_rails_begin)
        self.printer.register_event_handler('klippy:connect',
                                            self._handle_connect)
        self.printer.register_event_handler("klippy:shutdown",
                                            self._handle_shutdown)
        self.gcode.register_command("INITIALIZE_TOOLCHANGER",
                                    self.cmd_INITIALIZE_TOOLCHANGER,
                                    desc=self.cmd_INITIALIZE_TOOLCHANGER_help)
        self.gcode.register_command("SET_TOOL_TEMPERATURE",
                                    self.cmd_SET_TOOL_TEMPERATURE,
                                    desc=self.cmd_SET_TOOL_TEMPERATURE_help)
        self.gcode.register_command("SELECT_TOOL",
                                    self.cmd_SELECT_TOOL,
                                    desc=self.cmd_SELECT_TOOL_help)
        self.gcode.register_command("SELECT_TOOL_ERROR",
                                    self.cmd_SELECT_TOOL_ERROR,
                                    desc=self.cmd_SELECT_TOOL_ERROR_help)
        self.gcode.register_command("UNSELECT_TOOL",
                                    self.cmd_UNSELECT_TOOL,
                                    desc=self.cmd_UNSELECT_TOOL_help)
        self.gcode.register_command("TEST_TOOL_DOCKING",
                                    self.cmd_TEST_TOOL_DOCKING,
                                    desc=self.cmd_TEST_TOOL_DOCKING_help)
        self.gcode.register_command("SET_TOOL_PARAMETER",
                                    self.cmd_SET_TOOL_PARAMETER)
        self.gcode.register_command("RESET_TOOL_PARAMETER",
                                    self.cmd_RESET_TOOL_PARAMETER)
        self.gcode.register_command("SAVE_TOOL_PARAMETER",
                                    self.cmd_SAVE_TOOL_PARAMETER)

    def _handle_home_rails_begin(self, homing_state, rails):
        if self.initialize_on == INIT_ON_HOME and self.status == STATUS_UNINITALIZED:
            self.initialize()

    def _handle_connect(self):
        self.status = STATUS_UNINITALIZED
        self.active_tool = None

    def _handle_shutdown(self):
        self.status = STATUS_UNINITALIZED
        self.active_tool = None

    def get_status(self, eventtime):
        return {**self.params,
                'name': self.name,
                'status': self.status,
                'homing_usetap': self.homing_usetap,
                'homing_current': self.homing_current,
                'stepper_driver': self.stepper_driver,
                'sensorless_x': self.sensorless_x,
                'sensorless_y': self.sensorless_y,
                'homing_usetap': self.homing_usetap,
                'homing_toolless': self.homing_toolless,
                'homing_rebound_y': self.homing_rebound_y,
                'tools_preheat': self.tools_preheat,
                'tool': self.active_tool.name if self.active_tool else None,
                'tool_number': self.active_tool.tool_number if self.active_tool else -1,
                'tool_numbers': self.tool_numbers,
                'tool_names': self.tool_names,
                }

    def assign_tool(self, tool, number, prev_number, replace=False):
        if number in self.tools and not replace:
            raise Exception('Duplicate tools with number %s' % (str(number)))
        if prev_number in self.tools:
            del self.tools[prev_number]
            self.tool_numbers.remove(prev_number)
            self.tool_names.remove(tool.name)
        self.tools[number] = tool
        position = bisect.bisect_left(self.tool_numbers, number)
        self.tool_numbers.insert(position, number)
        self.tool_names.insert(position, tool.name)

    cmd_INITIALIZE_TOOLCHANGER_help = "Initialize the toolchanger"

    def cmd_INITIALIZE_TOOLCHANGER(self, gcmd):
        tool_name = gcmd.get('TOOL', None)
        tool_number = gcmd.get_int('T', None)
        tool = None
        if tool_name:
            tool = self.printer.lookup_object(tool_name)
        if tool_number is not None:
            tool = self.lookup_tool(tool_number)
            if not tool:
                raise gcmd.error('Tool #%d is not assigned' % (tool_number))
        self.initialize(tool)

    cmd_SELECT_TOOL_help = 'Select active tool'

    def cmd_SELECT_TOOL(self, gcmd):
        tool_name = gcmd.get('TOOL', None)
        if tool_name:
            tool = self.printer.lookup_object(tool_name)
            if not tool:
                raise gcmd.error("Select tool: TOOL=%s not found" % (tool_name))
            restore_axis = gcmd.get('RESTORE_AXIS', tool.t_command_restore_axis)
            force_pickup = gcmd.get('FORCE_PICKUP', None)
            self.select_tool(gcmd, tool, restore_axis, force_pickup)
            return
        tool_nr = gcmd.get_int('T', None)
        if tool_nr is not None:
            tool = self.lookup_tool(tool_nr)
            if not tool:
                raise gcmd.error("Select tool: T%d not found" % (tool_nr))
            restore_axis = gcmd.get('RESTORE_AXIS', tool.t_command_restore_axis)
            force_pickup = gcmd.get('FORCE_PICKUP', None)
            self.select_tool(gcmd, tool, restore_axis, force_pickup)
            return
        raise gcmd.error("Select tool: Either TOOL or T needs to be specified")

    cmd_SET_TOOL_TEMPERATURE_help = 'Set temperature for tool'

    def cmd_SET_TOOL_TEMPERATURE(self, gcmd):
        temp = gcmd.get_float('TARGET', 0.)
        wait = gcmd.get_int('WAIT', 0) == 1
        tool = self._get_tool_from_gcmd(gcmd)
        if not tool.extruder:
            raise gcmd.error(
                "SET_TOOL_TEMPERATURE: No extruder specified for tool %s" % (
                    tool.name))
        heaters = self.printer.lookup_object('heaters')
        heaters.set_temperature(tool.extruder.get_heater(), temp, wait)

    def _get_tool_from_gcmd(self, gcmd):
        tool_name = gcmd.get('TOOL', None)
        tool_nr = gcmd.get_int('T', None)
        if tool_name:
            tool = self.printer.lookup_object(tool_name)
        elif tool_nr is not None:
            tool = self.lookup_tool(tool_nr)
            if not tool:
                raise gcmd.error(
                    "SET_TOOL_TEMPERATURE: T%d not found" % (tool_nr))
        else:
            tool = self.active_tool
            if not tool:
                raise gcmd.error(
                    "SET_TOOL_TEMPERATURE: No tool specified and no active tool")
        return tool


    cmd_SELECT_TOOL_ERROR_help = "Abort tool change and mark the active toolchanger as failed"

    def cmd_SELECT_TOOL_ERROR(self, gcmd):
        if self.status != STATUS_CHANGING and self.status != STATUS_INITIALIZING:
            gcmd.respond_info(
                'SELECT_TOOL_ERROR called while not selecting, doing nothing')
            return
        self.status = STATUS_ERROR
        self.error_message = gcmd.get('MESSAGE', '')

    cmd_UNSELECT_TOOL_help = "Unselect active tool without selecting a new one"

    def cmd_UNSELECT_TOOL(self, gcmd):
        if not self.active_tool:
            return
        restore_axis = gcmd.get('RESTORE_AXIS',
                                self.active_tool.t_command_restore_axis)
        self.select_tool(gcmd, None, restore_axis)

    cmd_TEST_TOOL_DOCKING_help = "Unselect active tool and select it again"

    def cmd_TEST_TOOL_DOCKING(self, gcmd):
        if not self.active_tool:
            raise gcmd.error("Cannot test tool, no active tool")
        restore_axis = gcmd.get('RESTORE_AXIS',
                                self.active_tool.t_command_restore_axis)
        self.test_tool_selection(gcmd, restore_axis)

    def initialize(self, select_tool=None):
        if self.status == STATUS_CHANGING:
            raise Exception('Cannot initialize while changing tools')

        # Initialize may be called from within the intialize gcode
        # to set active tool without performing a full change
        should_run_initialize = self.status != STATUS_INITIALIZING

        extra_context = {
            'dropoff_tool': None,
            'pickup_tool': select_tool.name if select_tool else None,
        }

        if should_run_initialize:
            self.status = STATUS_INITIALIZING
            self.run_gcode('initialize_gcode', self.initialize_gcode, extra_context)

        if select_tool:
            self._configure_toolhead_for_tool(select_tool)
            after_change_gcode = select_tool.after_change_gcode if select_tool.after_change_gcode else self.default_after_change_gcode
            self.run_gcode('after_change_gcode', after_change_gcode, extra_context)
            self._set_tool_gcode_offset(select_tool, 0.0)

        if should_run_initialize:
            if self.status == STATUS_INITIALIZING:
                self.status = STATUS_READY
                self.gcode.respond_info('%s initialized, active %s' %(self.name, self.active_tool.name if self.active_tool else None))
            else:
                raise self.gcode.error('%s failed to initialize, error: %s' %(self.name, self.error_message))

    def select_tool(self, gcmd, tool, restore_axis, force_pickup=None):
        if not force_pickup:
            if self.status == STATUS_UNINITALIZED and self.initialize_on == INIT_FIRST_USE:
                self.initialize()

            if self.status != STATUS_READY:
                raise gcmd.error("Cannot select tool, toolchanger status is " + self.status)

            if self.active_tool == tool:
                gcmd.respond_info('Tool %s already selected' % tool.name if tool else None)
                return

        self.ensure_homed(gcmd)
        self.status = STATUS_CHANGING
        toolhead_position = self.gcode_move.get_status()['position']
        gcode_position = self.gcode_move.get_status()['gcode_position']
        extra_z_offset = toolhead_position[2] - gcode_position[2] - self.active_tool.gcode_z_offset if self.active_tool else 0.0

        extra_context = {
            'dropoff_tool': self.active_tool.name if self.active_tool else None,
            'pickup_tool': tool.name if tool else None,
            'restore_position': self._position_with_tool_offset(gcode_position, restore_axis, tool),
            'start_position': self._position_with_tool_offset(gcode_position, 'xyz', tool)
        }

        self.gcode.run_script_from_command("SAVE_GCODE_STATE NAME=_toolchange_state")
        self.gcode.run_script_from_command("SET_GCODE_OFFSET X=0.0 Y=0.0 Z=0.0 MOVE=0")
        # self.gcode.run_script_from_command("_fan_speed TOOL=%d" %(tool.tool_number))

        if not force_pickup:
            before_change_gcode = self.active_tool.before_change_gcode if self.active_tool and self.active_tool.before_change_gcode else self.default_before_change_gcode
            self.run_gcode('before_change_gcode', before_change_gcode, extra_context)

        if not force_pickup and self.active_tool:
            self.gcode.run_script_from_command("STOP_TOOL_PROBE_CRASH_DETECTION")
            self.run_gcode('tool.dropoff_gcode', self.active_tool.dropoff_gcode, extra_context)
            self.gcode.run_script_from_command("DETECT_ACTIVE_TOOL_PROBE")


        self._configure_toolhead_for_tool(tool)
        if tool is not None:
            self.run_gcode('tool.pickup_gcode',tool.pickup_gcode, extra_context)
            self.gcode.run_script_from_command("DETECT_ACTIVE_TOOL_PROBE")
            after_change_gcode = tool.after_change_gcode if tool.after_change_gcode else self.default_after_change_gcode
            self.run_gcode('after_change_gcode', after_change_gcode, extra_context)

        self._restore_axis(gcode_position, restore_axis, tool)

        self.gcode.run_script_from_command("RESTORE_GCODE_STATE NAME=_toolchange_state MOVE=0")
        # Restore state sets old gcode offsets, fix that.

        if tool is not None:
            self._set_tool_gcode_offset(tool, extra_z_offset)

        if not force_pickup:
            self.status = STATUS_READY
        if tool:
            gcmd.respond_info(
                'Selected tool %s (%s)' % (str(tool.tool_number), tool.name))
        else:
            gcmd.respond_info('Tool unselected')

    def test_tool_selection(self, gcmd, restore_axis):
        if self.status != STATUS_READY:
            raise gcmd.error(
                "Cannot test tool, toolchanger status is " + self.status)
        tool = self.active_tool
        if not tool:
            raise gcmd.error("Cannot test tool, no active tool")

        self.status = STATUS_CHANGING
        gcode_position = self.gcode_move.get_status()['gcode_position']
        extra_context = {
            'dropoff_tool': self.active_tool.name if self.active_tool else None,
            'pickup_tool': tool.name if tool else None,
            'restore_position': self._position_with_tool_offset(gcode_position, restore_axis, None),
            'start_position': self._position_with_tool_offset(gcode_position, 'xyz', tool)
        }

        self.gcode.run_script_from_command("SET_GCODE_OFFSET X=0.0 Y=0.0 Z=0.0")
        self.run_gcode('tool.dropoff_gcode', self.active_tool.dropoff_gcode, extra_context)
        self.gcode.run_script_from_command("DETECT_ACTIVE_TOOL_PROBE")
        self.run_gcode('tool.pickup_gcode', tool.pickup_gcode, extra_context)
        self.gcode.run_script_from_command("DETECT_ACTIVE_TOOL_PROBE")

        self._restore_axis(gcode_position, restore_axis, None)
        self.status = STATUS_READY
        gcmd.respond_info('Tool testing done')

    def lookup_tool(self, number):
        return self.tools.get(number, None)

    def get_selected_tool(self):
        return self.active_tool

    def _configure_toolhead_for_tool(self, tool):
        if self.active_tool:
            self.active_tool.deactivate()
        self.active_tool = tool
        if self.active_tool:
            self.active_tool.activate()

    def _set_tool_gcode_offset(self, tool, extra_z_offset):
        if tool is None:
            return
        if tool.gcode_x_offset is None and tool.gcode_y_offset is None and tool.gcode_z_offset is None:
            return
        cmd = 'SET_GCODE_OFFSET'
        if tool.gcode_x_offset is not None:
            cmd += ' X=%f' % (tool.gcode_x_offset,)
        if tool.gcode_y_offset is not None:
            cmd += ' Y=%f' % (tool.gcode_y_offset,)
        if tool.gcode_z_offset is not None:
            cmd += ' Z=%f' % (tool.gcode_z_offset + extra_z_offset,)
        self.gcode.run_script_from_command(cmd)
        mesh = self.printer.lookup_object('bed_mesh')
        if mesh and mesh.get_mesh():
            self.gcode.run_script_from_command(
                'BED_MESH_OFFSET X=%.6f Y=%.6f ZFADE=%.6f' %
                (-tool.gcode_x_offset, -tool.gcode_y_offset,
                 -tool.gcode_z_offset))

    def _position_with_tool_offset(self, position, axis, tool):
        result = {}
        for i in axis:
            index = XYZ_TO_INDEX[i]
            v = position[index]
            if tool:
                offset = 0.
                if index == 0:
                    offset = tool.gcode_x_offset
                elif index == 1:
                    offset = tool.gcode_y_offset
                elif index == 2:
                    offset = tool.gcode_z_offset
                v += offset
            result[INDEX_TO_XYZ[index]] = v
        return result

    def _restore_axis(self, position, axis, tool):
        if not axis:
            return
        pos = self._position_with_tool_offset(position, axis, tool)
        self.gcode_move.cmd_G1(self.gcode.create_gcode_command("G0", "G0", pos))

    def run_gcode(self, name, template, extra_context):
        current_status = self.status
        curtime = self.printer.get_reactor().monotonic()
        try:
            context = {
                **template.create_template_context(),
                'tool': self.active_tool.get_status(
                    curtime) if self.active_tool else {},
                'toolchanger': self.get_status(curtime),
                **extra_context,
            }
            template.run_gcode_from_command(context)
        except Exception as e:
            raise Exception("Script running error: %s" % (str(e)))
        if current_status != self.status:
            raise Exception(
                "Unexpected status during %s, status = %s, message = %s, aborting" % (
                    name, self.status, self.error_message))

    def cmd_SET_TOOL_PARAMETER(self, gcmd):
        tool = self._get_tool_from_gcmd(gcmd)
        name = gcmd.get("PARAMETER")
        if name in tool.params and name not in tool.original_params:
            tool.original_params[name] = tool.params[name]
        value = ast.literal_eval(gcmd.get("VALUE"))
        tool.params[name] = value

    def cmd_RESET_TOOL_PARAMETER(self, gcmd):
        tool = self._get_tool_from_gcmd(gcmd)
        name = gcmd.get("PARAMETER")
        if name in tool.original_params:
            tool.params[name] = tool.original_params[name]

    def cmd_SAVE_TOOL_PARAMETER(self, gcmd):
        tool = self._get_tool_from_gcmd(gcmd)
        name = gcmd.get("PARAMETER")
        if name not in tool.params:
            raise gcmd.error('Tool does not have parameter %s' % (name))
        configfile = self.printer.lookup_object('configfile')
        configfile.set(tool.name, name, tool.params[name])


    def ensure_homed(self, gcmd):
        if not self.uses_axis:
            return

        toolhead = self.printer.lookup_object('toolhead')
        curtime = self.printer.get_reactor().monotonic()
        homed = toolhead.get_kinematics().get_status(curtime)['homed_axes']
        needs_homing = any(axis not in homed for axis in self.uses_axis)
        if not needs_homing:
            return

        # Wait for current moves to finish to ensure we are up-to-date
        # This stalls the movement pipeline, so only do that if homing is needed
        toolhead.wait_moves()
        curtime = self.printer.get_reactor().monotonic()
        homed = toolhead.get_kinematics().get_status(curtime)['homed_axes']
        axis_to_home = list(filter(lambda a: a not in homed, self.uses_axis))
        if not axis_to_home:
            return

        if self.on_axis_not_homed == ON_AXIS_NOT_HOMED_ABORT:
            raise gcmd.error(
                "Cannot perform toolchange, axis not homed. Required: %s, homed: %s" % (
                self.uses_axis, homed))
        # Home the missing axis
        axis_str = " ".join(axis_to_home).upper()
        gcmd.respond_info('Homing%s before toolchange' % (axis_str,))
        self.gcode.run_script_from_command("G28 %s" % (axis_str,))

        # Check if now we are good
        toolhead.wait_moves()
        curtime = self.printer.get_reactor().monotonic()
        homed = toolhead.get_kinematics().get_status(curtime)['homed_axes']
        axis_to_home = list(filter(lambda a: a not in homed, self.uses_axis))
        if axis_to_home:
            raise gcmd.error(
                "Cannot perform toolchange, required axis still not homed after homing move. Required: %s, homed: %s" % (
                    self.uses_axis, homed))


def get_params_dict(config):
    result = {}
    for option in config.get_prefix_options('params_'):
        try:
            result[option] = ast.literal_eval(config.get(option))
        except ValueError as e:
            raise config.error(
                "Option '%s' in section '%s' is not a valid literal" % (
                    option, config.get_name()))
    return result


def load_config(config):
    return Toolchanger(config)


def load_config_prefix(config):
    return Toolchanger(config)