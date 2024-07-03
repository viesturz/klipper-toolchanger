# klipper-toolchanger

This repository is a fork of [klipper-toolchanger](https://github.com/viesturz/klipper-toolchanger), for [Tapchanger](https://github.com/viesturz/tapchanger).

It contains all the lastest codes that is compatible with [MissChanger](https://github.com/VIN-y/MissChanger). For further documentation, please go to that repository.

# Installation

To install this plugin, run the installation script using the following command over SSH. This script will download this GitHub repository to your RaspberryPi home directory, and symlink the files in the Klipper extra folder.

```
wget -O - https://raw.githubusercontent.com/VIN-y/klipper-toolchanger/main/install.sh | bash
```

Then, add the following to your moonraker.conf to enable automatic updates:

```
[update_manager klipper-toolchanger]
type: git_repo
channel: dev
path: ~/klipper-toolchanger
origin: https://github.com/VIN-y/klipper-toolchanger.git
managed_services: klipper
primary_branch: main
install_script: install.sh
```

# Components

* [multi fan](/descriptions/multi_fan.md) - multiple primary part fans.
* [toolchanger](/descriptions/toolchanger.md) - tool management support.
* [tool probe](/descriptions/tool_probe.md) - per tool Z probe.
* [rounded path](/descriptions/rounded_path.md) - rounds the travel path corners for fast non-print moves.
* [tools calibrate](/descriptions/tools_calibrate.md) - support for contact based XYZ offset calibration probes.
* [config_switch](/descriptions/config_switch.md) - allow the printer to be toggled between with-dock (multi-toolhead) and no-dock (single toolhead).
