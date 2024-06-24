# Tools calibrate

An extension to calibrate tool offsets with a nozzle contact probe.
Works by bumping the nozzle into the probe form multiple angles to pinpoint the nozzle location.

See [Nozzle Align](https://github.com/viesturz/NozzleAlign) repo for some sensor ideas.

### Configuration

See the [example](/examples/calibrate-offsets.cfg) folder for a full example.

```
[tools_calibrate]
pin: ^!PF5
travel_speed: 20  # Speed (in mm/sec) when positioning for XY probing
spread: 5  # mms to travel sideways when positioning for XY probes
lower_z: 1.0  # mms to lower nozzle down when positioning for XY probes
lift_z: 1.0 # mms to lift nozzle up when positioning for XY probes
speed: 2  # Probe speed
lift_speed: 4 # Speed (in mm/sec) for all Z moves when probing
final_lift_z: 6 # Z Lift after probing done, should be greater than any Z variance between tools
sample_retract_dist: 2
samples_tolerance: 0.05
samples: 5
samples_result: median # median, average

# Settings for nozzle probe calibration - optional.
probe: probe # name of the nozzle probe to use

trigger_to_bottom_z: 0.25 # Offset from probe trigger to vertical motion bottoms out. 
# decrease if the nozzle is too high, increase if too low.

idex_vars_macro: DC_VARS # Default not set. Allows exporting of offsets to gcode macro vars
# Assumes the offsets are named "offset_x", etc. This allows IDEX setups to use the calibration
# as a standalone component
```

### Clean your nozzles 

The calibration accuracy is as good as your nozzles are clean. 
Clean all nozzles throughly before calibrating.

### Calibrating tool offsets

- First position the nozzle approximately above the probe - the probe will find the center on it's own within 1-2 mm.

- The first tool has all offsets to 0 and is used as a baseline for other tools. Run ```TOOL_LOCATE_SENSOR``` to calibrate nozzle location for tool 0.

- For every other tool, run ```TOOL_CALIBRATE_TOOL_OFFSET``` to measure the offset from the first tool.

All probing moves and final offsets will be printed in the console.

### Calibrating nozzle bed probe.

- Do the first two steps from above to ensure the probe is precisely under the nozzle.

- Run TOOL_CALIBRATE_PROBE_OFFSET - to measure Z offset from nozzle triggering the probe to tool's nozzle probe activating.

All probing moves and final offsets will be printed in the console.


## Troubleshooting

- **Probe triggered prior to movement**, the nozzle is not touching the probe
  - Check if the probe is triggering without touching - use a multimiter to check for continuity and if it changes when pressing down on the probe.
  - Check if the pin is configured correctly. The example configuration is for active low with a pullup. Depending how you have wired it, you might need remove the **^!** for active-high.
- **Probe triggered prior to movement**, the nozzle is touching the probe, could have probed a few times already
  - Likely the initial position was too far off-center. Try to position it more accurately.
  - The probe is lowered too much and/or not enough sideways - tweak ```lower_z``` and ```spread```