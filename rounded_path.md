# Rounded path

Automatic rounded corners for fast non-printing moves.
Typical usage is a chain of move commands that need to be fast but can afford to not be fully accurate.  

TODO: add image.

# Configuration

```
[rounded_path]
resolution: 0.2 # the length of a circle approximation segments.
replace_g0: False # Use at your own risk
```

# Gcodes

`ROUNDED_G0 [X=<x>] [Y=<y>] [Z=<z>] [F=<f>] D=<distance>`: 
Move the toolhead and round for this position allow a maximum deflection `distance` to round the path.

# Usage

The rounded path chain **must always end with D=0** to allow computing the final move.

Example usage:
```
    ROUNDED_G0 Y=30 D=5 F=1000
    ROUNDED_G0 X=100 D=30
    ROUNDED_G0 Y=100 D=30
    ROUNDED_G0 X=200 D=30
    ROUNDED_G0 Y=200 D=30
    ROUNDED_G0 X=100 Y=100 Z=10 D=0     
```

# Limitations
This currently only optimizes on segment by segment basis, 
and practically the rounding radius is limited by half segment length. 