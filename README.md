# klipper-toolchanger

An assortment of Klipper extensions that I have made while working on [Tapchanger](https://github.com/viesturz/tapchanger)

# Installation

```
 git clone https://github.com/viesturz/klipper-toolchanger.git klipper-toolchanger
 ln -s ~/klipper-toolchanger/klipper/extras/* ~/klipper/klippy/extras/
 sudo systemctl restart klipper
```

Add the [macros.cfg](/macros.cfg) to your printer config.

# Components

* [Multi fan](/multi_fan.md) - multiple primary part fans.
* [Toolchanger](/toolchanger.md) - tool management support.
* [Tool probe](/tool_probe.md) - per tool Z probe.
* [Rounded path](/rounded_path.md) - rounds the travel path corners for fast non-print moves.
* [Tools calibrate](/tools_calibrate.md) - support for contact based XYZ offset calibration probes.
