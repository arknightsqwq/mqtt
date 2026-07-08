import time
from config import *

class RideStats:
    def __init__(self):
        self.speed = 0.0
        self.distance_km = 0.0
        self.max_speed = 0.0
        self.avg_speed = 0.0
        self.altitude = 0
        self._last_time = 0
        self._sample_count = 0
        self._riding = False

    def update(self, gps, now_s):
        if not gps:
            self._riding = False
            return

        speed_ms = gps.get("speed", 0)
        alt = gps.get("altitude", 0)
        self.speed = speed_ms * 3.6  # m/s → km/h

        if self.speed > 0.5:
            self._riding = True
        if self.speed > self.max_speed:
            self.max_speed = self.speed

        # Distance from speed × time integration
        if self._last_time > 0:
            dt = now_s - self._last_time
            if 0 < dt < 10:
                self.distance_km += self.speed * dt / 3600.0

        self.altitude = int(alt) if alt else 0
        self._last_time = now_s
        self._sample_count += 1
        self.avg_speed = self.distance_km / max(1, self._sample_count * 5) * 3600

    def reset_trip(self):
        self.distance_km = 0.0
        self.max_speed = 0.0
        self.avg_speed = 0.0
        self._sample_count = 0
        self._last_time = 0

    def is_riding(self):
        return self._riding
