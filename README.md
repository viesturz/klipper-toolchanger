# klipper-toolchanger

## This is a fork of Viesturz's Klipper-Toolchanger software
## This is/or will be modified to also work with my verion of a toolchanger, that uses Klicky-Probe as Z-Probe, that I named Klicky-Changer.
## Use this page only for the klipper-toolchanger installation, the hardware and configs for Klicky-Changer can be found here: (SOON)


# Installation

To install this plugin, run the installation script using the following command over SSH. This script will download this GitHub repository to your RaspberryPi home directory, and symlink the files in the Klipper extra folder.

```
wget -O - https://raw.githubusercontent.com/printicus/klipper-toolchanger/main/install.sh | bash
```

Then, add the following to your moonraker.conf to enable automatic updates:
```
[update_manager klipper-toolchanger]
type: git_repo
channel: dev
path: ~/klipper-toolchanger
origin: https://github.com/printicus/klipper-toolchanger.git
managed_services: klipper
primary_branch: main
```
