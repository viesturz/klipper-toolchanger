# Support for toolchnagers
#
# Copyright (C) 2023 Viesturs Zarins <viesturz@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import ast, bisect
from unittest.mock import sentinel

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
DETECT_UNAVAILABLE = -1
DETECT_ABSENT = 0
DETECT_PRESENT = 1

class Toolchanger:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.config = config
        self.gcode_macro = self.printer.load_object(config, 'gcode_macro')
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode_move = self.printer.load_object(config, 'gcode_move')

        self.name = config.get_name()
        self.params = get_params_dict(config)
        init_options = {'home': INIT_ON_HOME,
                        'manual': INIT_MANUAL, 'first-use': INIT_FIRST_USE}
        self.initialize_on = config.getchoice(
            'initialize_on', init_options, 'first-use')
        self.verify_tool_pickup = config.getboolean('verify_tool_pickup', True)
        self.require_tool_present = config.getboolean('require_tool_present', False)
        self.transfer_fan_speed = config.getboolean('transfer_fan_speed', True)
        self.uses_axis = config.get('uses_axis', 'xyz').lower()
        home_options = {'abort': ON_AXIS_NOT_HOMED_ABORT,
                        'home': ON_AXIS_NOT_HOMED_HOME}
        self.on_axis_not_homed = config.getchoice('on_axis_not_homed',
                                                  home_options, 'abort')
        self.initialize_gcode = self.gcode_macro.load_template(
            config, 'initialize_gcode', '')
        self.default_before_change_gcode = self.gcode_macro.load_template(
            config, 'before_change_gcode', '')
        self.default_after_change_gcode = self.gcode_macro.load_template(
            config, 'after_change_gcode', '')

        # Read all the fields that might be defined on toolchanger.
        # To avoid throwing config error when no tools configured.
        config.get('pickup_gcode', None)
        config.get('dropoff_gcode', None)
        config.getfloat('gcode_x_offset', None)
        config.getfloat('gcode_y_offset', None)
        config.getfloat('gcode_z_offset', None)
        config.get('t_command_restore_axis', None)
        config.get('extruder', None)
        config.get('fan', None)
        config.get_prefix_options('params_')

        self.status = STATUS_UNINITALIZED
        self.active_tool = None
        self.detected_tool = None
        self.has_detection = False
        self.tools = {}
        self.tool_numbers = []  # Ordered list of registered tool numbers.
        self.tool_names = []  # Tool names, in the same order as numbers.
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
        if not self.require_tool_present:
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
        self.gcode.register_command("VERIFY_TOOL_DETECTED",
                                    self.cmd_VERIFY_TOOL_DETECTED)
        self.fan_switcher = None

    def require_fan_switcher(self):
        if not self.fan_switcher:
            self.fan_switcher = FanSwitcher(self, self.config)

    def _handle_home_rails_begin(self, homing_state, rails):
        if self.initialize_on == INIT_ON_HOME and self.status == STATUS_UNINITALIZED:
            self.initialize(self.detected_tool)

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
                'tool': self.active_tool.name if self.active_tool else None,
                'tool_number': self.active_tool.tool_number if self.active_tool else -1,
                'detected_tool': self.detected_tool.name if self.detected_tool else None,
                'detected_tool_number': self.detected_tool.tool_number if self.detected_tool else -1,
                'tool_numbers': self.tool_numbers,
                'tool_names': self.tool_names,
                'has_detection': self.has_detection,
                }

    def assign_tool(self, tool, number, prev_number, replace=False):
        if number in self.tools and not replace:
            raise Exception('Duplicate tools with number %s' % (number,))
        if prev_number in self.tools:
            del self.tools[prev_number]
            self.tool_numbers.remove(prev_number)
            self.tool_names.remove(tool.name)
        self.tools[number] = tool
        position = bisect.bisect_left(self.tool_numbers, number)
        self.tool_numbers.insert(position, number)
        self.tool_names.insert(position, tool.name)

        self.has_detection = any([t.detect_state != DETECT_UNAVAILABLE for t in self.tools.values()])
        all_detection = all([t.detect_state != DETECT_UNAVAILABLE for t in self.tools.values()])
        if self.has_detection and not all_detection:
            raise self.config.error("Some tools missing detection pin")

    cmd_INITIALIZE_TOOLCHANGER_help = "Initialize the toolchanger"

    def cmd_INITIALIZE_TOOLCHANGER(self, gcmd):
        tool = self.gcmd_tool(gcmd, self.detected_tool)
        self.initialize(tool)

    cmd_SELECT_TOOL_help = 'Select active tool'

    def cmd_SELECT_TOOL(self, gcmd):
        tool_name = gcmd.get('TOOL', None)
        if tool_name:
            tool = self.printer.lookup_object(tool_name)
            if not tool:
                raise gcmd.error("Select tool: TOOL=%s not found" % (tool_name))
            restore_axis = gcmd.get('RESTORE_AXIS', tool.t_command_restore_axis)
            self.select_tool(gcmd, tool, restore_axis)
            return
        tool_nr = gcmd.get_int('T', None)
        if tool_nr is not None:
            tool = self.lookup_tool(tool_nr)
            if not tool:
                raise gcmd.error("Select tool: T%d not found" % (tool_nr))
            restore_axis = gcmd.get('RESTORE_AXIS', tool.t_command_restore_axis)
            self.select_tool(gcmd, tool, restore_axis)
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

        if select_tool or self.has_detection:
            self._configure_toolhead_for_tool(select_tool)
            if select_tool:
                self.run_gcode('after_change_gcode', select_tool.after_change_gcode, extra_context)
                self._set_tool_gcode_offset(select_tool, 0.0)
            if self.require_tool_present and self.active_tool is None:
                raise self.gcode.error(
                    '%s failed to initialize, require_tool_present set and no tool present after initialization' % (
                    self.name,))

        if should_run_initialize:
            if self.status == STATUS_INITIALIZING:
                self.status = STATUS_READY
                self.gcode.respond_info('%s initialized, active %s' %
                                        (self.name,
                                         self.active_tool.name if self.active_tool else None))
            else:
                raise self.gcode.error('%s failed to initialize, error: %s' %
                                       (self.name, self.error_message))

    def select_tool(self, gcmd, tool, restore_axis):
        if self.status == STATUS_UNINITALIZED and self.initialize_on == INIT_FIRST_USE:
            self.initialize(self.detected_tool)
        if self.status != STATUS_READY:
            raise gcmd.error(
                "Cannot select tool, toolchanger status is %s" % (self.status,))

        if self.active_tool == tool:
            gcmd.respond_info(
                'Tool %s already selected' % tool.name if tool else None)
            return

        self.ensure_homed(gcmd)
        self.status = STATUS_CHANGING
        gcode_status = self.gcode_move.get_status()
        gcode_position = gcode_status['gcode_position']
        current_z_offset = gcode_status['homing_origin'][2]
        extra_z_offset = current_z_offset - (self.active_tool.gcode_z_offset if self.active_tool else 0.0)

        extra_context = {
            'dropoff_tool': self.active_tool.name if self.active_tool else None,
            'pickup_tool': tool.name if tool else None,
            'restore_position': self._position_with_tool_offset(
                gcode_position, restore_axis, tool, extra_z_offset),
            'start_position': self._position_with_tool_offset(
                gcode_position, 'xyz', tool, extra_z_offset)
        }

        self.gcode.run_script_from_command(
            "SAVE_GCODE_STATE NAME=_toolchange_state")

        before_change_gcode = self.active_tool.before_change_gcode if self.active_tool else self.default_before_change_gcode
        self.run_gcode('before_change_gcode', before_change_gcode, extra_context)
        self.gcode.run_script_from_command("SET_GCODE_OFFSET X=0.0 Y=0.0 Z=0.0")

        if self.active_tool:
            self.run_gcode('tool.dropoff_gcode',
                           self.active_tool.dropoff_gcode, extra_context)

        self._configure_toolhead_for_tool(tool)
        if tool is not None:
            self.run_gcode('tool.pickup_gcode',
                           tool.pickup_gcode, extra_context)
            if self.has_detection and self.verify_tool_pickup:
                self.validate_detected_tool(tool, gcmd)
            self.run_gcode('after_change_gcode',
                           tool.after_change_gcode, extra_context)

        self._restore_axis(gcode_position, restore_axis, tool)

        self.gcode.run_script_from_command(
            "RESTORE_GCODE_STATE NAME=_toolchange_state MOVE=0")
        # Restore state sets old gcode offsets, fix that.
        if tool is not None:
            self._set_tool_gcode_offset(tool, extra_z_offset)

        self.status = STATUS_READY
        if tool:
            gcmd.respond_info(
                'Selected tool %s (%s)' % (str(tool.tool_number), tool.name))
        else:
            gcmd.respond_info('Tool unselected')

    def test_tool_selection(self, gcmd, restore_axis):
        if self.status != STATUS_READY:
            raise gcmd.error(
                "Cannot test tool, toolchanger status is %s" % (self.status,))
        tool = self.active_tool
        if not tool:
            raise gcmd.error("Cannot test tool, no active tool")

        self.status = STATUS_CHANGING
        gcode_position = self.gcode_move.get_status()['gcode_position']
        extra_context = {
            'dropoff_tool': self.active_tool.name if self.active_tool else None,
            'pickup_tool': tool.name if tool else None,
            'restore_position': self._position_with_tool_offset(
                gcode_position, restore_axis, None),
            'start_position': self._position_with_tool_offset(
                gcode_position, 'xyz', tool)
        }

        self.gcode.run_script_from_command("SET_GCODE_OFFSET X=0.0 Y=0.0 Z=0.0")

        self.run_gcode('tool.dropoff_gcode',
                       self.active_tool.dropoff_gcode, extra_context)
        self.run_gcode('tool.pickup_gcode',
                       tool.pickup_gcode, extra_context)

        self._restore_axis(gcode_position, restore_axis, None)
        self.status = STATUS_READY
        gcmd.respond_info('Tool testing done')

    def lookup_tool(self, number):
        return self.tools.get(number, None)

    def get_selected_tool(self):
        return self.active_tool

    def note_detect_change(self, tool):
        detected = None
        detected_names = []
        for tool in self.tools.values():
            if tool.detect_state == DETECT_PRESENT:
                detected = tool
                detected_names.append(tool.name)
        if len(detected_names) > 1:
            self.gcode.respond_info("Multiple tools detected: %s" % (detected_names,))
            detected = None
        self.detected_tool = detected

    def require_detected_tool(self, gcmd):
        if self.detected_tool is not None:
            return self.detected_tool
        detected = None
        detected_names = []
        for tool in self.tools.values():
            if tool.detect_state == DETECT_PRESENT:
                detected = tool
                detected_names.append(tool.name)
        if len(detected_names) > 1:
            raise gcmd.error("Multiple tools detected: %s" % (detected_names,))
        if detected is None:
            raise gcmd.error("No tool detected")
        return detected

    def validate_detected_tool(self, expected, gcmd):
        actual = self.require_detected_tool(gcmd)
        if actual != expected:
            expected_name = expected.name if expected else "None"
            actual_name = actual.name if actual else "None"
            raise gcmd.error("Expected tool %s but active is %s" % (expected_name, actual_name))

    def cmd_VERIFY_TOOL_DETECTED(self, gcmd):
        expected = self.gcmd_tool(gcmd, self.active_tool)
        if not self.has_detection:
            return
        toolhead = self.printer.lookup_object('toolhead')
        toolhead.wait_moves()
        # Wait some to allow tool sensors to update
        toolhead.dwell(.2)
        self.validate_detected_tool(expected, gcmd)

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

    def _position_with_tool_offset(self, position, axis, tool, extra_z_offset = 0.0):
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
                    offset = tool.gcode_z_offset + extra_z_offset
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

    class sentinel: pass

    def gcmd_tool(self, gcmd, default=sentinel, extra_number_arg=None):
        tool_name = gcmd.get('TOOL', None)
        tool_number = gcmd.get_int('T', None)
        if tool_number is None and extra_number_arg:
            tool_number = gcmd.get_int(extra_number_arg, None)
        tool = None
        if tool_name:
            tool = self.printer.lookup_object(tool_name)
        if tool_number is not None:
            tool = self.lookup_tool(tool_number)
            if not tool:
                raise gcmd.error('Tool #%d is not assigned' % (tool_number))
        if tool is None:
            if default == sentinel:
                raise gcmd.error('Missing TOOL=<name> or T=<number>')
            tool = default
        return tool

class FanSwitcher:
    def __init__(self, toolchanger, config):
        self.toolchanger = toolchanger
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.config = config
        self.has_multi_fan = bool(config.get_prefix_sections('multi_fan'))
        self.has_printer_fan = bool(config.has_section('fan'))
        self.pending_speed = None
        self.active_fan = None
        self.transfer_fan_speed = toolchanger.transfer_fan_speed
        if self.has_printer_fan:
            raise config.error("Cannot use tool fans together with [fan], use [fan_generic] for tool fans.")
        if not self.has_multi_fan and not self.has_printer_fan:
            self.gcode.register_command("M106", self.cmd_M106)
            self.gcode.register_command("M107", self.cmd_M107)

    def activate_fan(self, fan):
        if self.has_multi_fan:
            # Legacy multi-fan support
            self.gcode.run_script_from_command("ACTIVATE_FAN FAN='%s'" % (fan.name,))
            return
        if self.active_fan == fan or not self.transfer_fan_speed:
            return

        speed_to_set = self.pending_speed
        if self.active_fan:
            speed_to_set = self.active_fan.get_status(0)['speed']
            self.gcode.run_script_from_command("SET_FAN_SPEED FAN='%s' SPEED=%s" % (self.active_fan.fan_name, 0.0))
        self.active_fan = fan
        if speed_to_set is not None:
            if self.active_fan:
                self.pending_speed = None
                self.gcode.run_script_from_command("SET_FAN_SPEED FAN='%s' SPEED=%s" % (self.active_fan.fan_name, speed_to_set))
            else:
                self.pending_speed = speed_to_set

    def cmd_M106(self, gcmd):
        tool = self.toolchanger.gcmd_tool(gcmd, default=self.toolchanger.active_tool, extra_number_arg='P')
        speed = gcmd.get_float('S', 255., minval=0.) / 255.
        self.set_speed(speed, tool)
    def cmd_M107(self, gcmd):
        tool = self.toolchanger.gcmd_tool(gcmd, default=self.toolchanger.active_tool, extra_number_arg='P')
        self.set_speed(0.0, tool)
    def set_speed(self, speed, tool):
        if tool and tool.fan:
            self.gcode.run_script_from_command("SET_FAN_SPEED FAN='%s' SPEED=%s" % (tool.fan.fan_name, speed))
        else:
            self.pending_speed = speed

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
