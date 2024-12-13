# Config Switch

This extension provide the means to quickly convert the config from a tool-changer to a traditional single tool-head printer.

## Added Console Command

| Command              | Description                                |
| -------------------- | ------------------------------------------ |
| `SAVE_CONFIG_MODE`   | Save session variables in **printer.cfg**. |
| `TOGGLE_CONFIG_MODE` | Detect and toggle current session config.  |

## Details

#### SAVE_CONFIG_MODE

1. The recording point is marked with `#;<` and can be closed with `#;>`.

2. The command relies on a macro variable, `variable_dock:`, in **printer.cfg** to determine where to save the config to. Therefore, it requires the following macro in **printer.cfg**, among the session variables:
   
   ```
   [gcode_macro _home]
   variable_xh: 175.0
   variable_yh: 235.0
   variable_zh: 10.0
   variable_dock: True
   gcode:
       RESPOND TYPE=echo MSG='Print area centre: {xh}, {yh}, {zh}'
       RESPOND TYPE=echo MSG='Number of TH: {no_of_toolhead}'
   ```
   
   This variable `variable_dock:` can be either `True` for `False`.

3. The session variables will be safe to `config/config_wt_dock.cfg` or `config/config_no_dock.cfg`

4. It is recommended that you put all of your session variables at the bottom of **printer.cfg**, just before the section for `SAVE_CONFIG`.

#### TOGGLE_CONFIG_MODE

1. Toggle the session variables between that are saved in `config/config_wt_dock.cfg` and `config/config_no_dock.cfg`, if they are available.

2. If either `config/config_wt_dock.cfg` and `config/config_no_dock.cfg` are not yet available. Please build that config (in **printer.cfg**), with the right `variable_dock:` value,  then use `SAVE_CONFIG_MODE` to create the save file.

3. The command needs to be follow up with `FIRMWARE_RESTART` it implement the new settings. It is suggested that you have the following macro in your config:
   
   ```
   [gcode_macro PRINTER_CONFIG_TOGGLE]
   gcode:
       M400
       SAVE_CONFIG_MODE
       M400
       TOGGLE_CONFIG_MODE
       M400
       FIRMWARE_RESTART
   ```
