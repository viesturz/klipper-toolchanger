# klipper-toolchanger

An assortment of Klipper extensions that I have made while working on [Tapchanger](https://github.com/viesturz/tapchanger)

# Installation

To install this plugin, run the installation script using the following command over SSH. This script will download this GitHub repository to your RaspberryPi home directory, and symlink the files in the Klipper extra folder.

```
wget -O - https://raw.githubusercontent.com/VIN-y/klipper-toolchanger/test-machine/install.sh | bash
```

Then, add the following to your moonraker.conf to enable automatic updates:
```
[update_manager klipper-toolchanger]
type: git_repo
channel: dev
path: ~/klipper-toolchanger
origin: https://github.com/VIN-y/klipper-toolchanger.git
managed_services: klipper
primary_branch: test-machine
install_script: install.sh
```
Add the [macros.cfg](/macros.cfg) to your printer config.

# Components

* [Multi fan](/multi_fan.md) - multiple primary part fans.
* [Toolchanger](/toolchanger.md) - tool management support.
* [Tool probe](/tool_probe.md) - per tool Z probe.
* [Rounded path](/rounded_path.md) - rounds the travel path corners for fast non-print moves.
* [Tools calibrate](/tools_calibrate.md) - support for contact based XYZ offset calibration probes.
