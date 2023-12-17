# Multi Fan

Multiple part cooling fans support. If find this useful, please comment the pull request: https://github.com/Klipper3d/klipper/pull/6341

# Config

### [multi_fan first_fan]
Configure the fan the same as a regular `[fan]`.
One may define any number of sections with a "multi_fan" prefix.
The prefixless fan is active on startup.
ACTIVATE_FAN gcode command switches the fan that is used for cooling.

# Gcodes

#### ACTIVATE_FAN

`ACTIVATE_FAN FAN=fan_name` Selects the active printer fan that reacts to
M106/M107 gcodes. Current fan speed is transferred over to the new fan.

