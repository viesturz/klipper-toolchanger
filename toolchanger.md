# klipper-toolchanger

Toolchanging extension for Klipper.
Provides the basic structure and links into GCodes.  

Not opinionated how the tool change happens and suitable for physical tools as well as MMUs. 
All the actual tool changing motions to be provided as gcode macros.

# Status

 * Single toolchanger works well. 

TODO: 

 * Cascading tools support.
 * Save current tool on restart.

# Lifecycle

This is the overall lifecycle of the toolchanger.

The initialization can be done either manually from PRINT_START or automatically
on home or first toolchange.

![Lifecycle](/Lifecycle.png)

The exact sequence how each step is executed:
![Sequence](/Sequence.png)

# Config

### [toolchanger]

Configures common tool changing parameters. 
More than one toolchanger can be configured, with arbitrary names.
The unnamed toolchanger is always considered the main one and others can be 
connected to a tool in the main toolchanger.

Any parameter that can be set on a tool, can be set on the toolchanger as well
and will provide a default value for all of its tools.

```
[toolchanger]
# save_current_tool: false
  #  If set, saves currently selected tool and makes it available for 
  # initialize gcode.
# initialize_gcode: 
  #  Gcode to run on initialize. Typically used for homing any motors, or 
  #  reselecting saved tool.
# initialize_on: first-use
  # When this toolchanger gets initialized.
  #  - manual: only when INITIALIZE_TOOLCHANGER is called.
  #  - home: when homing the printer.
  #  - first-use: on first toolchange command.
# verify_tool_pickup: True
  # If tool detection is available, will verify tool presence after pickp_gcode
# require_tool_present: False
  # Raise error if no tool present on init or on unmount. 
  # Use in case the tool contains crucial sensors for the printer to operate/home.  
# uses_axis: xyz 
  # Axis used by the tool change process
# on_axis_not_homed: abort
  # When required axis are not homed
  # - abort: aborts the command
  # - home: attempts to home the axis
# params_*: 
  # Extra params to pass to pickup/dropoff gcode. Accessible in the gcode via
  # `toolchanger.params_name`.
  # Also will be copied to any tools for this toolchanger with local
  # values overriding. 
# before_change_gcode:
  # Common gcode to run before any tool change   
# after_change_gcode:
  # Common gcode to run after any tool change.
  # EG: To set custom input shaping, accelerations, etc.  
# error_gcode:
  # If specified, this gcode is run on failures instead of erroring out Klipper 
  # Typical use would be to pause the print and put INITIALIZE_TOOLCHANGER in the resume macro to reset toolchanger.
# recover_gcode:
  # Experimental, if specified, this gcode is run on `INITIALIZE_TOOLCHANGER RECOVER=1` to recover the position.
  # Should not generally be necessary, but adds optional extra control.
# parent_tool:
  # Name of a parent tool. Marks this toolchanger as a child, meaning the parent tool
  # will be selected in order to select any tool attached to this.
  # Can be used for chaining multiple filament/tool changing techniques,
  # like IDEX plus an MMU attached to one of the hotends.
# parent_mounting_mode: parent-first 
  # How to mount parent when the tool is selected:
  # - parent-first - mount parent and then child
  # - child-first - mount child before parent can be mounted
# parent_unmounting_mode: lazy 
  # How to unmount parent when the tool is deselected:
  # - child-first - unmount child and then parent
  # - parent-first - unmount parent and then child
  # - lazy - no dot unmount the child unless a needed to mount a sibling
# transfer_fan_speed: True
  # When tre, fan speed is transferred during toolchange. When false, fan speeds are not changed during toolchange.     
```

### [tool]

Defines a tool that can be selected.
Normally a tool has an assigned extruder, fans and associated printer config,
like pressure advance. But can be purely virtual, like slot in an MMU unit.
See [command reference](G-Codes.md#toolchanger) for how to control tools.

All gcode macros below have the following context available:
* tool - currently active tool or None if no tool. This is the actual object, not a name, so can use directly, ie `tool.fan`.
* toolchanger - same as printer.toolchanger.
* dropoff_tool - name of the tool that is being dopped off, or None if not a dropoff operation.
* pickup_tool - name of the tool that is being picked up, or None if not a dropoff operation.
* restore_position.X .Y .Z - coordinates to restore the position to after toolchange. 
   Only the ones requested are set. A G0 to the coordinates is automatically run after the toolchange.
   This is primarily for path optimization. 
   Adjusted to account for tool offsets.
* start_position.X .Y .Z - coordinates before toolchange, regardless of what is requested. 
   Adjusted to account for tool offsets. 

```
[tool tool_name]
# toolchanger: toolchanger
  # Which toolchanger this tool belongs to.
# extruder:
  # Name of the extruder to activate when this tool is selected.
  # If not specified, will use parent's extruder.
# extruder_stepper: 
  # Name of extruder stepper to use for filament motion.
  # When set the main extruder is only used for temperature control.
  # Useful for Y type multi extruder hotends.  
# fan: 
  # Name of the fan to use as print cooling fan when this tool is selected.
  # If not set, uses parent fan or does nothing.
# detection_pin: 
  # Pin to use for tool presence detection.
# tool_number: 
  # Tool number to register this tool as.
  # When set, creates the T<n> macro and changes M104/M109 T<n> to target this tool.
  # Can be overwritten in runtime using [ASSIGN_TOOL](G-Codes.md#ASSIGN_TOOL) command.
# pickup_gcode:
  # Gcode to run to pick up this tool, if empty, there is no pickup code.
  # The gocode can use `tool` and `toolchanger` variables to access
  # [their status](Status_Reference.md#tool).
# dropoff_gcode:
  # Gcode to run to drop off this tool, if empty, there is no dropoff code.
# gcode_x_offset: 0
# gcode_y_offset: 0
# gcode_z_offset: 0
  # The XYZ gcode offset of the toolhead. If set, overrides offset defined 
  # by the parent. If set, even to 0, indicates the offset on that axis is 
  # relevant for this tool and any adjustments will be attributed to this tool.  
# params_*: 
  # Extra params to pass to pickup/dropoff gcode. Accessible in the gcode via
  # `tool.params_name`.
  # Some example params:
  #  params_dock_x: 10.0
  #  params_dock_y: 50.0
  #  params_input_shaper_freq_x: 100
  #  params_retract_mm: 8 
# t_command_restore_axis: XYZ
   # Which axis to restore with the T<n> command, see SELECT_TOOL for command for more info.
```

# Gcodes

### [toolchanger]

The following commands are available when toolchanger is loaded.

### INITIALIZE_TOOLCHANGER
`INITIALIZE_TOOLCHANGER [TOOLCHANGER=toolchanger] [TOOL_NAME=<name>] [T=<number>] [RECOVER=0]`: 
Initializes or Re-initializes the toolchanger state. Sets toolchanger status to `ready`.

The default behavior is to auto-initialize on first tool selection call.
Always needs to be manually re-initialized after a `SELECT_TOOL_ERROR`. 
If `TOOL_NAME` is specified, sets the active tool without performing any tool change
gcode. The after_change_gcode is always called. `TOOL_NAME` with empty name unselects
tool.

Experimental: If `RECOVER=1` is specified, `recover_gcode` is run and toolehad is moved to restore_axis position. 

### ASSIGN_TOOL
`ASSIGN_TOOL TOOL=<name> N=<number>`: Assign tool to specific tool number.
Overrides any assignments set up by `tool.tool_number`.
Sets up a corresponding T<n> and M104/M109 T<index> commands.
Does *not* change the active tool.

### SELECT_TOOL
`SELECT_TOOL TOOL=<name> [RESTORE_AXIS=xyz]`: Select the active tool.
The toolhead will be moved to the previous position on any axis specified in
`RESTORE_AXIS` value. Slicer Gcode normally use `T0`, `T1`, `T2`,... to select a tool.
Printer config should contain macros to map them to corresponding tool names,
or set `tool.tool_number:` to auto register a T macro.

The selection sequence is as follows:

- gcode state is saved
- toolchanger.before_change_gcode is run
- current extruder and fan are deactivated, if changed
- current_tool.dropoff_gcode is run - if a tool is currently selected
- new_tool.pickup_gcode is run
- new extruder and fan are activated, if changed
- toolchanger.after_change_gcode is run
- gcode state is restored, without move
- new tool is moved to the gcode position, according to RESTORE_AXIS

If the tools have parents, their corresponding dropoff/pickup gcode is also run.  

### SELECT_TOOL_ERROR
`SELECT_TOOL_ERROR [MESSAGE=]`: Signals failure to select a tool. 
Can be called from within tool macros during SELECT_TOOL and will abort any
remaining tool change steps and put the toolchanger starting the selection in
`ERROR` state. Then runs `error_gcode` if one is provided, 

### UNSELECT_TOOL
`UNSELECT_TOOL [RESTORE_AXIS=]`: Unselect active tool without selecting a new one.

Performs only the first part of select tool, leaving the printer with no tool 
selected.

### VERIFY_TOOL_DETECTED
`VERIFY_TOOL_DETECTED [TOOL=<name>] [T=<number>] [ASYNC=0]`: Check if detected tool 
matches the expected tool. Shutdown Klipper if not. 
Does nothing if tool detection pin is not configured.
If ASYNC=0, will wait until any queued moves are complete, causing the toolhead to come to a stop for a bit.   
If ASYNC=1, will return immediately and perform the check in background after all previous moves are finished.
A verification failure will:
 - abort in-progress toolchange, put the toolchanger in `ERROR` state.
 - Run`error_gcode` if one is provided. 

### SET_TOOL_TEMPERATURE
`SET_TOOL_TEMPERATURE [TOOL=<name>] [T=<number>]  TARGET=<temp> [WAIT=0]`: Set tool temperature.

### TEST_TOOL_DOCKING
`TEST_TOOL_DOCKING`: Dock and undock current tool.

### SET_TOOL_PARAMETER
`SET_TOOL_PARAMETER [TOOL=<name>] [T=<number>]  PARAMETER=parameter_<name> VALUE=<value>`: 
Change tool parameter in runtime.
Defaults to current tool if tool not specified.

### SAVE_TOOL_PARAMETER
`SAVE_TOOL_PARAMETER [TOOL=<name>] [T=<number>]  PARAMETER=parameter_<name>`: 
Saves the tool parameter to pending config changes.
Defaults to current tool if tool not specified.

### RESET_TOOL_PARAMETER
`RESET_TOOL_PARAMETER [TOOL=<name>] [T=<number>]  PARAMETER=parameter_<name> VALUE=<value>`: 
Resets a parameter to its original value.
Defaults to current tool if tool not specified.

# Gcodes if *fan* is specified for any of tools

### M106 
`M106 S<speed> [P<tool number>] [T<tool number>] [TOOL=<tool name>] `: Set fan speed. 
If P not specified sets speed for the current tool fan.
If `toolchanger.transfer_fan_speed` is enabled, current tool fan speed is transferred to the new tool on tool change.

### M107 
`M107 [P<tool number>] [T<tool number>] [TOOL=<tool name>] `: Stop fan.
With no parameters stops the current tool fan.

# Status

## tool

The following information is available in the `tool` object:
 - `name`: The tool name, eg 'tool T0'.
 - `tool_number`: The assigned tool number or -1 if not assigned.
 - `toolchanger`: The name of the toolchanger this tool is attached to. 
 - `extruder`: Name of the extruder used for this tool.
 - `fan`: Full name of the fan to be used as part cooling fan for this tool, use [fan_generic] fans.
 - `active`: If this tool is currently the selected tool.
 - `mounted`: If this tool is currently mounted, the tool may be mounted but
   not selected. Some reasons for that can be that a child tool is selected, or
   lazy unmounting is configured.  
 - `mounted_child`: The child tool which is currently mounted, or empty.
 - `params_*`: Set of values specified using params_*.
 - `gcode_x_offset`: current X offset.
 - `gcode_y_offset`: current Y offset.
 - `gcode_z_offset`: current Z offset.

## toolchanger

The following information is available in the `toolchanger` object:
 - `status`: One of 'uninitialized', 'ready', 'changing', 'error'.
 - `tool`: Name of currently selected/changed tool, or empty.
 - `tool_number`: Number of the currently selected tool, or -1.
 - `detected_tool`: Name of currently detected tool, or empty.
 - `detected_tool_number`: Number of the currently detected tool, or -1.
 - `tool_numbers`: List of assigned tool numbers, eg [0,1,2].
 - `tool_names`: List of tool names corresponding the assigned numbers.
