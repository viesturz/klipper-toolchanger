Toolchanger config examples.
The examples here are for specific toolchanger setups. And will likely need to be tweaked for your specific case.

They are all for setups with multiple physical tools, 
the extension code supports arbitrary tool setups but this has been the most prolific use by far.

### Probe on T0

This is the most simple setup - with a bed probe on T0 for homing and probing.
Each toolhead has a tool mounted switch to detect which tool is mounted.

The main limitation is that if Z homing is needed before tool change, 
and T0 is not mounted, the homing will fail. 

Suitable for Fying gantry printers, like Voron 2.4, but should be also adapted for fixed gantry 
systems that do not need Z movement for tool change.

### Per tool probe

Is a config where each tool has a probe and it is used for both tool detection and homing/probing.
This is more versatile, but also more complex.

Suitable for Flyig fixed gantry printers, like Voron 2.4.

### Liftbar

A system where tool change Z movement is handled by a separate lifter rail.
Suitable for fixed gantry printers, like Voron Trident.

### Liftbar + Flying gantry

A system where tools are lowered via a separate lifter rail, but the tool change itself
is handled by only moving the toolhead.