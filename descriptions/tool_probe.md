# Tool probe

A per-tool Z endstop and crash detection support. Allows using any tool to home Z.

# Configuration 

```
[stepper_z]
endstop_pin: probe:z_virtual_endstop

[tool_probe_endstop]
crash_mintime: 0.5 # seconds to wait before announcing a crash, if the probe stops 
  #triggering before this, no crash is reported. 
crash_gcode:
    RESPOND TYPE=error MSG='Tool not detected, expected {printer.toolchanger.tool_number}. Pausing the print.' 
    M84
    TURN_OFF_HEATERS

[tool_probe T1]
pin: !et1:PB6
tool: 1
z_offset:  -0.75
speed: 5.0
samples: 3
samples_result: median
sample_retract_dist: 2.0
samples_tolerance: 0.02
samples_tolerance_retries: 3    
```

# Status

## tool_probe_endstop 
Implements the regular [Probe params](https://www.klipper3d.org/Status_Reference.html#probe) and the following:

- active_tool_probe - name of the active `tool_probe`
- active_tool_number - number of the active tool as detected by the probe
- active_tool_probe_z_offset - z-offset of the active tool probe

# Gcodes

Implements the regular [Probe commands](https://www.klipper3d.org/G-Codes.html#probe) and the following.

### SET_ACTIVE_TOOL_PROBE
`SET_ACTIVE_TOOL_PROBE T=<tool_nr>`: Manually set the active probe 

### DETECT_ACTIVE_TOOL_PROBE
`DETECT_ACTIVE_TOOL_PROBE`: Detects the active probe based on the one that is **not** triggered.

### START_TOOL_PROBE_CRASH_DETECTION
`START_TOOL_PROBE_CRASH_DETECTION [T=<tool_nr>]`: Start detecting tool crashes. 
When the tool probe triggers the `tool_probe_endstop.crash_gcode` is run.

### STOP_TOOL_PROBE_CRASH_DETECTION
`STOP_TOOL_PROBE_CRASH_DETECTION`: Stops the crash detection.
