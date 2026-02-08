# Tool probe

A per-tool Z endstop and crash detection support. Allows using any tool to home Z.

# Configuration 

```
[stepper_z]
endstop_pin: probe:z_virtual_endstop

[toolchanger]

[tool T1]
detection_pin: ^et1:PB6
probe: tool_probe T1

[tool_probe T1]
pin: ^et1:PB6
# Extra probe Z offset, NOT tool offset. 
z_offset: 0.0
speed: 5.0
samples: 3
samples_result: median
sample_retract_dist: 2.0
samples_tolerance: 0.02
samples_tolerance_retries: 3    
```

# Gcodes
Implements the regular [Probe commands](https://www.klipper3d.org/G-Codes.html#probe) .
