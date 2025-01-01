# klipper-toolchanger

This repository is a fork of [viesturz/klipper-toolchanger](https://github.com/viesturz/klipper-toolchanger), for [Tapchanger](https://github.com/viesturz/tapchanger), and [DraftShift/klipper-toolchanger](https://github.com/DraftShift/klipper-toolchanger), for DraftShift.

It contains all the latest codes that is compatible with [MissChanger](https://github.com/VIN-y/MissChanger). For further documentation, please go to that repository.

# Installation

To install this plugin, run the installation script using the following command over SSH. This script will download this GitHub repository to your RaspberryPi home directory, and symlink the files in the Klipper extra folder.

```
wget -O - https://raw.githubusercontent.com/VIN-y/klipper-toolchanger/alpha/install.sh | bash
```

*Note 1: You will need a `FIRMWARE_RESTART` whenever there is an update for the add-on.* *Note 2: This command can also be used for a clean install of the extension.*

# Components

* [toolchanger](/descriptions/toolchanger.md) - tool management support.
* [tool probe](/descriptions/tool_probe.md) - per tool Z probe.
* [rounded path](/descriptions/rounded_path.md) - rounds the travel path corners for fast non-print moves.
* [tools calibrate](/descriptions/tools_calibrate.md) - support for contact based XYZ offset calibration probes.
* [config_switch](/descriptions/config_switch.md) - allow the printer to be toggled between with-dock (multi-toolhead) and no-dock (single toolhead).
