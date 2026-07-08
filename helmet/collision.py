import time
import config
from config import *

class CollisionResult:
    def __init__(self):
        self.level = 0          # 0=none, 1=mild, 2=moderate, 3=severe
        self.impact_g = 0.0
        self.fall_type = ""     # front/side/back/unknown

class CollisionDetector:
    def __init__(self):
        # Free-fall tracking
        self._in_freefall = False
        self._freefall_start = 0
        self._pending_ff_impact = False
        self._ff_impact_start = 0

        # Direct impact spike confirmation
        self._spike_count = 0
        self._spike_peak = 0.0
        self._spike_peak_ax = 0.0
        self._spike_peak_ay = 0.0
        self._spike_peak_az = 0.0

        self._cooldown_until = 0

    def detect(self, mag, accel_x, accel_y, accel_z, now_ms):
        result = CollisionResult()

        if now_ms < self._cooldown_until:
            return result

        # ── Path A: Free fall detection ──
        if mag < FREE_FALL_THRESHOLD:
            if not self._in_freefall:
                self._in_freefall = True
                self._freefall_start = now_ms
            # Reset direct-impact tracking during free fall
            self._spike_count = 0
            return result

        if self._in_freefall:
            fall_ms = time.ticks_diff(now_ms, self._freefall_start)
            self._in_freefall = False
            if fall_ms >= FREE_FALL_DURATION_MS:
                self._pending_ff_impact = True
                self._ff_impact_start = now_ms

        # ── Check free-fall → impact ──
        if self._pending_ff_impact:
            if time.ticks_diff(now_ms, self._ff_impact_start) > IMPACT_WINDOW_MS:
                self._pending_ff_impact = False
            elif mag >= config.FF_IMPACT_L1:
                result.level = self._classify_ff(mag)
                result.impact_g = mag
                result.fall_type = self._classify_fall(accel_x, accel_y, accel_z)
                self._pending_ff_impact = False
                self._cooldown_until = now_ms + COLLISION_COOLDOWN_MS
                self._spike_count = 0
                return result

        # ── Path B: Direct impact (no free fall prerequisite) ──
        if mag >= config.DIRECT_IMPACT_L1:
            self._spike_count += 1
            if mag > self._spike_peak:
                self._spike_peak = mag
                self._spike_peak_ax = accel_x
                self._spike_peak_ay = accel_y
                self._spike_peak_az = accel_z

            if self._spike_count >= SPIKE_CONFIRM_SAMPLES:
                result.level = self._classify_direct(self._spike_peak)
                result.impact_g = self._spike_peak
                result.fall_type = self._classify_fall(
                    self._spike_peak_ax, self._spike_peak_ay, self._spike_peak_az)
                self._spike_count = 0
                self._spike_peak = 0.0
                self._cooldown_until = now_ms + COLLISION_COOLDOWN_MS
                return result
        else:
            self._spike_count = 0
            self._spike_peak = 0.0

        return result

    def _classify_direct(self, mag):
        if mag >= config.DIRECT_IMPACT_L3:
            return 3
        elif mag >= config.DIRECT_IMPACT_L2:
            return 2
        elif mag >= config.DIRECT_IMPACT_L1:
            return 1
        return 0

    def _classify_ff(self, mag):
        if mag >= config.FF_IMPACT_L3:
            return 3
        elif mag >= config.FF_IMPACT_L2:
            return 2
        elif mag >= config.FF_IMPACT_L1:
            return 1
        return 0

    def _classify_fall(self, x, y, z):
        ax, ay = abs(x), abs(y)
        if ax > ay and ax > abs(z):
            return "front" if x > 0 else "back"
        elif ay > ax and ay > abs(z):
            return "side"
        return "unknown"
