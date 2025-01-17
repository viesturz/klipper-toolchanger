# Manual rail

Like manual stepper, but supports multiple motors and regular homing logic.

# Config

### [manual_rail rail]
Defines a new rail, that is not part of the normal XYZ kinematic.

```
[manual_rail my_rail]
#step_pin:
#dir_pin:
#enable_pin:
#microsteps:
#rotation_distance:
#   See the "stepper" section for a description of these parameters.
#velocity:
#   Set the default velocity (in mm/s) for the stepper. This value
#   will be used if a MANUAL_STEPPER command does not specify a SPEED
#   parameter. The default is 5mm/s.
#accel:
#   Set the default acceleration (in mm/s^2) for the stepper. An
#   acceleration of zero will result in no acceleration. This value
#   will be used if a MANUAL_RAIL command does not specify an ACCEL
#   parameter. The default is zero.
#endstop_pin:
#   Endstop switch detection pin. If specified, then one may perform
#   "homing moves" by adding a HOME=1 parameter to
#   MANUAL_RAIL movement commands.
#position_min: 0
#   Minimum valid distance (in mm) the user may command the stepper to
#   move to.  The default is 0mm.
position_endstop:
#   Location of the endstop (in mm). This parameter must be provided
#   for the X, Y, and Z steppers on cartesian style printers.
position_max:
#   Maximum valid distance (in mm) the user may command the stepper to
#   move to. This parameter must be provided for the X, Y, and Z
#   steppers on cartesian style printers.
#homing_speed: 5.0
#   Maximum velocity (in mm/s) of the stepper when homing. The default
#   is 5mm/s.
#homing_retract_dist: 5.0
#   Distance to backoff (in mm) before homing a second time during
#   homing. Set this to zero to disable the second home. The default
#   is 5mm.
#homing_retract_speed:
#   Speed to use on the retract move after homing in case this should
#   be different from the homing speed, which is the default for this
#   parameter
#second_homing_speed:
#   Velocity (in mm/s) of the stepper when performing the second home.
#   The default is homing_speed/2.
#homing_positive_dir:
#   If true, homing will cause the stepper to move in a positive
#   direction (away from zero); if false, home towards zero. It is
#   better to use the default than to specify this parameter. The
#   default is true if position_endstop is near position_max and false
#   if near position_min.
```

# Gcodes

#### MANUAL_RAIL
`MANUAL_RAIL RAIL=config_name [ENABLE=[0|1]]
[SET_POSITION=<pos>] [SPEED=<speed>] [ACCEL=<accel>] [MOVE=<pos>]
[HOME=1] [SYNC=0]`: This command will alter the
state of the rail. Use the ENABLE parameter to enable/disable the
steppers. Use the SET_POSITION parameter to force the rail to think
it is at the given position. Use the MOVE parameter to request a
movement to the given position. If SPEED and/or ACCEL is specified
then the given values will be used instead of the defaults specified
in the config file. If an ACCEL of zero is specified then no
acceleration will be performed. If HOME=1 is specified then a homing 
move will be perfomed, and the position will be ignored. 
Normally future G-Code commands will be scheduled to run after the
move completes, however if a move uses SYNC=0 
then future G-Code movement commands may run in parallel with the
rail movement.
