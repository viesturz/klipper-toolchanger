# Feature

- Enables you to read 'live' values from the accelerometers
- Allows you to run templates similarly to the `[tool_probe_endstop]` `crash_gcode` on specific events.
- You have good accelerometers! Why not use them?

## Background

currently there is no actual way to obtain any accel values inside of macros. query prints to console, and the other dump to files.



## How it works

TDD_POLLING_START
TDD_POLLING_STOP
TDD_POLLING_RESET
TDD_QUERY
TDD_REFERENCE_DUMP
TDD_REFERENCE_SET
TDD_REFERENCE_RESET
TDD_START
TDD_STOP



# Accellerometer polling/tool drop detection

## objects/stats avalible inside of printer.tool_drop_detection object

- **rotation**
rotation{'pitch':0.000,'yaw':0.000}
- **magnitude** -> total acceleration, absolute in g. avalible as:
'magnitude': 0.000
- **vector** -> the data retrieved from our accel. avalible as:
'vector':{'x':0.000,'y':0.000,'z':0.000}
- **session** -> data from our start stop session, peak, norm and current in g abs.
'session':{'peak': 0.000, 'norm': 0.000, 'current': 0.000}

## config

### general
- sample_results: [ median | average ] (default: median) -> *norm* (the way to calculate our current accel.)
- decimals: [ 0 - 10 ] (default: 3) -> *the amount of decimals to pack into our objects*
- accelerometer: [comma seperated names] (default: none)

### crash/drop detection
- peak_g_threshold: [ 0.1 - 25 ] (default: 5) -> *if defined enables also triggering crash gcode when a peak higher than this is detected (instant)*
- rotational thresholding *(the threshold in rotation at which to trigger the crash gcode)*
 - either:  rotation_threshold: [0.0 - 180.0] (±abs, vector to vector)
 - or:      pitch_threshold and/or roll_threshold (±abs, actual rotation angles)
- crash_mintime: [ 0.0 - 100.0 ] (default 1.0) -> *how long the angle has to be exceeded to be considered dropped* (high g events remain instant)
- crash_gcode: gcode template to be executed when THRESHOLD exceeded. provided with extra context: [ie: 'ACCEL':T1]

### unrelated/toys *(will always use pitch_threshold, roll_threshold)*
- angle_exceed: gcode template to be ran when the angle gets exceeded
- angle_return: gcode template to be ran when the angle returns to normal.
- hysterisis: [0.0-180.0] (default: 5.0) Hysterisis between those two templates executing.

(unsure if this works?)
- polling_freq: [1-max] (default: 1) -> *the frequency at which at ask the mcu for values*
- polling_rate: [see adxl345] (default: 50) -> *the frequency the accelerometer is spitting out values to mcu*

## commands

# ---[ testing ]
 - TDD_QUERY_ASYNC/TDD_QUERY [/ACCEL=NAME/]
-> single query, either querying all or just those provided. comma seperated list.
action: responds with the rotation, magnitude and vector in the console,
all rounded to two decimals without updating the tool_drop_detection object.

 - TDD_DUMP_ROTATIONS [/ACCEL=NAME/]
-> single query, either querying all or just those provided. comma seperated list replied to copy into config.
default_$NAME$: [g:?.??, p:?.??, r:?.??]


# ---[ drop detection ]
 - TDD_STOP [/ACCEL=NAME/]
-> stops tool drop detection for that tool or all

 - TDD_START [ACCEL=NAME] ([LIMIT_PITCH=0.0-180.0] [LIMIT_ROLL=0.0-180.0]) or [LIMIT_ANGLE=0.0-180.0] optional: [/CRASH_MINTIME=0.0-100.0/] [/LIMIT_G=0.0-25/]
where LIMIT_ANGLE is the angle between the two vectors. limits again relative to our config objects previously set by obtaining an offset to our 0.0.0 angles with TDD_DUMP_ROTATIONS
-> starts tool drop detection for that tool or all, everything provided optional to config.

# ---[ polling ]
 - TDD_POLLING_START [/ACCEL/] [/FREQ/] [/RATE/]
-> starts the high speed polling for that tool or all, freq, interval provided to overwrite internal settings.
will update the info in session accordingly. 
will also update the acceleration vector, the magnitutde, and the rotation that can be retrieved.

 - TDD_POLLING_RESET [/ACCEL/]
-> resets the info in session for that tool or all.

 - TDD_POLLING_STOP [/ACCEL/]
-> stops the polling for that tool or all.
