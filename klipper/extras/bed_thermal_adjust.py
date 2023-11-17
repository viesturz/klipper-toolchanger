# Thermal loss adjustment for heated bed.
#
# Copyright (C) 2023-2023  Viesturs Zarins <viesturz@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

UPDATE_TIME = 1.0
UPDATE_TOLERANCE = 0.3

class BedThermalAdjust:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.heater_bed = self.printer.load_object(config, "heater_bed")
        self.chamber_sensor_name = config.get("chamber_temperature_sensor", None)
        self.chamber_sensor = None
        self.ambient_temp = 0.0
        self.use_startup_temp = config.getboolean("use_startup_temperature", False)
        if not self.chamber_sensor_name and not self.use_startup_temp:
            self.ambient_temp = config.getfloat("fixed_chamber_temperature",
                                                minval=0.0, maxval=100)
        self.max_heater_temp = self.heater_bed.heater.max_temp
        self.requested_temp = 0.0
        self.temp_drop = config.getfloat("temperature_drop_per_degree",
                                         above=0.0, below=1.0)

        # Remove heated bed commands
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command("M140", None)
        self.gcode.register_command("M190", None)
        # Register our commands
        self.gcode.register_command("M140", self.cmd_M140)
        self.gcode.register_command("M190", self.cmd_M190)

        self.printer.register_event_handler("klippy:connect",
                                            self.handle_connect)
        self.printer.register_event_handler("klippy:ready", self.handle_ready)

    def handle_connect(self):
        if self.chamber_sensor_name:
            self.chamber_sensor = self.printer.lookup_object(self.chamber_sensor_name)

    def handle_ready(self):
        if self.chamber_sensor:
            reactor = self.printer.get_reactor()
            reactor.register_timer(self.callback, reactor.monotonic() + UPDATE_TIME)

    def callback(self, eventtime):
        self.ambient_temp = round(float(self.chamber_sensor.get_temp(eventtime)[0]), 1)
        bed_status = self.heater_bed.get_status(0)
        if bed_status['target'] > 0.0:
            # Update only if the heated bed is still active
            self.update_heater_bed()
        return eventtime + UPDATE_TIME

    def cmd_M140(self, gcmd, wait=False):
        # Set Bed Temperature
        self.requested_temp = gcmd.get_float('S', 0.)
        if self.requested_temp > 0 and self.use_startup_temp and self.ambient_temp == 0.0:
            # first time the bed is heating, grab ambient temp
            self.ambient_temp = round(float(self.heater_bed.get_status(0)['temperature']),1)
        self.update_heater_bed(wait)
    def cmd_M190(self, gcmd):
        # Set Bed Temperature and Wait
        self.cmd_M140(gcmd, wait=True)

    def to_surface_temp(self, heater_temp):
        if heater_temp <= 0:
            return heater_temp
        return heater_temp - max((heater_temp - self.ambient_temp) * self.temp_drop, 0.0)

    def to_heater_temp(self, surface_temp):
        if surface_temp <= 0:
            return surface_temp
        # Inverse of the above
        # s = h - (h - AA) * D = h - h*D + AA*D = h * (1 - D) + AA * D
        # h = (s - AA * D) / (1 - D)
        return max(surface_temp, min(self.max_heater_temp, (surface_temp - self.ambient_temp * self.temp_drop) / (1.0 - self.temp_drop)))

    def get_status(self, eventtime):
        bed_status = self.heater_bed.get_status(eventtime)
        return {'temperature': round(self.to_surface_temp(bed_status['temperature']), 2),
                'target': self.requested_temp,
                'ambient': self.ambient_temp,
                'power': bed_status['power']}

    def update_heater_bed(self, wait=False):
        new_heater_temp = int(self.to_heater_temp(self.requested_temp))
        current_heater_temp = float(self.heater_bed.get_status(0)['target'])
        if wait or abs(current_heater_temp - new_heater_temp) > UPDATE_TOLERANCE:
            self.requested_heater_temp = new_heater_temp
            gcmd = self.gcode.create_gcode_command("M140", "M140", {"S": "%0.1f" % (new_heater_temp, )})
            self.heater_bed.cmd_M140(gcmd, wait=wait)

def load_config(config):
    return BedThermalAdjust(config)
