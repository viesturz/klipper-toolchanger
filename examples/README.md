Toolchanger config examples.
The examples here are for specific toolchanger setups. And will likely need to be tweaked for your specific case.

They are all for setups with multiple physical tools, 
the extension code supports arbitrary tool setups but this has been the most prolific use by far.

# Klipper setup 

Each setup is a combination of 3 parts: 

## Z probing

### Shuttle mounted regular probe

TODO: need an example for this.

*Shuttle mounted cartographer probe* or other eddy current probe.
The simplest setup, compatible with all printer types, but requires wiring routed to the shuttle in addition to each tool.
Is a good combination together with a CPAP cooling also permanently mounted on the shuttle.
Each toolhead has a basic switch to detect if the tool is mounted.

### Probe on T0

This is the next simplest setup - with a bed probe on T0 for homing and probing.
Each toolhead has a basic switch to detect if the tool is mounted.

The main limitation is that if Z homing is needed before tool change, and T0 is not mounted, the homing will fail. 

Suitable for Fying gantry printers, like Voron 2.4, but might be also adapted for fixed gantry 
systems that do not need Z movement for tool change.

### Per tool probe

Is a config where each tool has a separate Z probe and it is used for both tool detection and homing/probing.
This is more versatile, but also more complex.

Suitable for Flyig fixed gantry printers, like Voron 2.4.

## Dock location

### Fixed dock

Simplest mechanical design, but means that the dock stays in the print area, potentially limiting available area.

### Liftbar

A system where tool change Z movement is handled by a separate lifter rail.
Suitable for fixed gantry printers, like Voron Trident.

### Liftbar + Flying gantry

A system where tools are lowered via a separate lifter rail, but the tool change itself
is handled by only moving the toolhead.

## Tool mounting system

Select a mounting routine, depending on your tool mounting system.

### TapChanger
```
  params_dropoff_path: [{'z':0, 'y':4}, {'z':0, 'y':0}, {'z':-7.3, 'y':0}, {'z':-11.2, 'y':3.5}, {'z':-13.2, 'y':8}]
  params_pickup_path: [{'z':-13.2, 'y':8}, {'z':-11.2, 'y':3.5}, {'z':-7.3, 'y':0}, {'z':3, 'y':0, 'f':0.5, 'verify':1},  {'z':0, 'y':0}, {'z':0, 'y':4}]
```

### StealthChanger
``` 
  params_dropoff_path: [{'z':3.5, 'y':4}, {'z':0, 'y':0}, {'z':-12, 'y':0}]
  params_pickup_path: [{'z':-12, 'y':2}, {'z':-12, 'y':0}, {'z':1.5, 'y':0, 'f':0.5, 'verify':1}, {'z':0.5, 'y':2.5, 'f':0.5}, {'z':8, 'y':8}, ]  
```

### ClickChanger

```
  params_dropoff_path: [{'z':0, 'y':10}, {'z':0, 'y':0}, {'z':-8, 'y':0}, {'z':-9, 'y':3}]
  params_pickup_path: [{'z':-9, 'y':3}, {'z':-8, 'y':0}, {'z':-4, 'y':0}, {'z':1, 'f':0.5, 'verify':1}, {'z':0}, {'y':10, 'z':0}]
```

# Slicer setup

Gcodes for Prusa/Orca and derivatives

Start:
```gcode
PRINT_START  EXTRUDER={first_layer_temperature[initial_tool]} {if is_extruder_used[0]}T0_TEMP={first_layer_temperature[0]}{endif} {if is_extruder_used[1]}T1_TEMP={first_layer_temperature[1]}{endif} {if is_extruder_used[2]}T2_TEMP={first_layer_temperature[2]}{endif} {if is_extruder_used[3]}T3_TEMP={first_layer_temperature[3]}{endif} {if is_extruder_used[4]}T4_TEMP={first_layer_temperature[4]}{endif} {if is_extruder_used[5]}T5_TEMP={first_layer_temperature[5]}{endif}  BED=[bed_temperature_initial_layer_single] TOOL=[initial_tool] CHAMBER=[chamber_temperature]
```

Before Tool change/ Change filament 
```gcode
M104 S{temperature[next_extruder]} T[next_extruder] ; set new tool temperature so it can start heating while changing
```

After layer change:
```gcode
;AFTER_LAYER_CHANGE
;[layer_z]
VERIFY_TOOL_DETECTED ASYNC=1 ; Check after each layer if the tool is still attached
```