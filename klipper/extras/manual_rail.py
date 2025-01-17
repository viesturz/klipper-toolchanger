# Support for a manual controlled stepper
#
# Copyright (C) 2019-2021  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import stepper, chelper
from . import force_move

# Like ManualStepper, but is a multi stepper rail with min/max and homing.
class ManualRail:
    def __init__(self, config):
        self.printer = config.get_printer()
        if config.get('endstop_pin', None) is not None:
            self.can_home = True
            self.rail = stepper.LookupMultiRail(config)
            self.steppers = self.rail.get_steppers()
        else:
            self.can_home = False
            self.rail = stepper.PrinterStepper(config)
            self.steppers = [self.rail]
        self.velocity = config.getfloat('velocity', 5., above=0.)
        self.accel = self.homing_accel = config.getfloat('accel', 0., minval=0.)
        self.next_cmd_time = 0.
        # Setup iterative solver
        ffi_main, ffi_lib = chelper.get_ffi()
        self.trapq = ffi_main.gc(ffi_lib.trapq_alloc(), ffi_lib.trapq_free)
        self.trapq_append = ffi_lib.trapq_append
        self.trapq_finalize_moves = ffi_lib.trapq_finalize_moves
        self.rail.setup_itersolve('cartesian_stepper_alloc', b'x')
        self.rail.set_trapq(self.trapq)
        # Register commands
        rail_name = config.get_name().split()[1]
        gcode = self.printer.lookup_object('gcode')
        gcode.register_mux_command('MANUAL_RAIL', "RAIL",
                                   rail_name, self.cmd_MANUAL_RAIL,
                                   desc=self.cmd_MANUAL_RAIL_help)
    def sync_print_time(self):
        toolhead = self.printer.lookup_object('toolhead')
        print_time = toolhead.get_last_move_time()
        if self.next_cmd_time > print_time:
            toolhead.dwell(self.next_cmd_time - print_time)
        else:
            self.next_cmd_time = print_time
    def do_enable(self, enable):
        self.sync_print_time()
        stepper_enable = self.printer.lookup_object('stepper_enable')
        if enable:
            for s in self.steppers:
                se = stepper_enable.lookup_enable(s.get_name())
                se.motor_enable(self.next_cmd_time)
        else:
            for s in self.steppers:
                se = stepper_enable.lookup_enable(s.get_name())
                se.motor_disable(self.next_cmd_time)
        self.sync_print_time()
    def do_set_position(self, setpos):
        self.rail.set_position([setpos, 0., 0.])
    def do_move(self, movepos, speed, accel, sync=True):
        self.sync_print_time()
        cp = self.rail.get_commanded_position()
        dist = movepos - cp
        axis_r, accel_t, cruise_t, cruise_v = force_move.calc_move_time(
            dist, speed, accel)
        self.trapq_append(self.trapq, self.next_cmd_time,
                          accel_t, cruise_t, accel_t,
                          cp, 0., 0., axis_r, 0., 0.,
                          0., cruise_v, accel)
        self.next_cmd_time = self.next_cmd_time + accel_t + cruise_t + accel_t
        self.rail.generate_steps(self.next_cmd_time)
        self.trapq_finalize_moves(self.trapq, self.next_cmd_time + 99999.9,
                                  self.next_cmd_time + 99999.9)
        toolhead = self.printer.lookup_object('toolhead')
        toolhead.note_mcu_movequeue_activity(self.next_cmd_time)
        if sync:
            self.sync_print_time()
    def do_homing_move(self, accel):
        if not self.can_home:
            raise self.printer.command_error(
                "No endstop for this manual stepper")
        self.homing_accel = accel
        position_min, position_max = self.rail.get_range()
        hi = self.rail.get_homing_info()
        start_pos = hi.position_endstop
        if hi.positive_dir:
            start_pos -= 1.5 * (hi.position_endstop - position_min)
        else:
            start_pos += 1.5 * (position_max - hi.position_endstop)
        self.do_set_position(start_pos)
        pos = [hi.position_endstop, 0., 0., 0.]
        endstops = self.rail.get_endstops()
        phoming = self.printer.lookup_object('homing')
        phoming.manual_home(self, endstops, pos, hi.speed, True, True)
        # Perform second home
        if hi.retract_dist:
            retract_dist = -hi.retract_dist if hi.positive_dir else hi.retract_dist
            self.do_move(hi.position_endstop + retract_dist, hi.speed, accel)
            self.do_set_position(hi.position_endstop + retract_dist * 1.5)
            phoming.manual_home(self, endstops, pos, hi.second_homing_speed, True, True)
    cmd_MANUAL_RAIL_help = "Command a manually configured rail"
    def cmd_MANUAL_RAIL(self, gcmd):
        enable = gcmd.get_int('ENABLE', None)
        if enable is not None:
            self.do_enable(enable)
        setpos = gcmd.get_float('SET_POSITION', None)
        if setpos is not None:
            self.do_set_position(setpos)
        speed = gcmd.get_float('SPEED', self.velocity, above=0.)
        accel = gcmd.get_float('ACCEL', self.accel, minval=0.)
        home = gcmd.get_int('HOME', 0)
        if home:
            self.do_enable(1)
            self.do_homing_move(accel=accel)
        elif gcmd.get_float('MOVE', None) is not None:
            movepos = gcmd.get_float('MOVE')
            sync = gcmd.get_int('SYNC', 1)
            if self.rail.position_min is not None and movepos < self.rail.position_min:
                raise gcmd.error('Stepper %s move to %s below min %s' % (self.rail.get_name(), movepos, self.rail.position_min))
            if self.rail.position_max is not None and movepos > self.rail.position_max:
                raise gcmd.error('Stepper %s move to %s above max %s' % (self.rail.get_name(), movepos, self.rail.position_max))
            self.do_move(movepos, speed, accel, sync)
        elif gcmd.get_int('SYNC', 0):
            self.sync_print_time()

    def get_status(self, eventtime):
        stepper_enable = self.printer.lookup_object('stepper_enable')
        enable = stepper_enable.lookup_enable(self.steppers[0].get_name())
        return {'position': self.rail.get_commanded_position(),
                'enabled': enable.is_motor_enabled()}

    # Toolhead wrappers to support homing
    def flush_step_generation(self):
        self.sync_print_time()
    def get_position(self):
        return [self.rail.get_commanded_position(), 0., 0., 0.]
    def set_position(self, newpos, homing_axes=()):
        self.do_set_position(newpos[0])
    def get_last_move_time(self):
        self.sync_print_time()
        return self.next_cmd_time
    def dwell(self, delay):
        self.next_cmd_time += max(0., delay)
    def drip_move(self, newpos, speed, drip_completion):
        self.do_move(newpos[0], speed, self.homing_accel)
    def get_kinematics(self):
        return self
    def get_steppers(self):
        return self.steppers
    def calc_position(self, stepper_positions):
        return [stepper_positions[self.rail.get_name()], 0., 0.]

# Dummy object for multi stepper setup
class DummyStepper():
    def get_status(self, eventtime):
        return {}

def load_config_prefix(config):
    name = config.get_name()
    # Return a dummy if this is a secondary motor in a multi-motor setup.
    for i in range(1,99):
        if name.endswith(str(i)) and config.has_section(name[:-len(str(i))]):
            return DummyStepper()
    return ManualRail(config)