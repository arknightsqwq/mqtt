import machine
import time
from quectel import Audio
from config import *

class AlarmManager:
    def __init__(self):
        self.audio = Audio()
        self._audio_ok = False
        self._buzzer = None
        self._vibrate = None
        self._sos_pin = None
        self._sos_triggered = False
        self._sos_time = 0
        # Voice call
        self._voice = None
        self._voice_ok = False
        self._voice_active = False
        self._incoming_call = False

    def init(self):
        # Audio (TTS + recording)
        try:
            if self.audio.init(lambda evt: None):
                self._audio_ok = True
                print("[ALARM] Audio ready")
        except Exception as e:
            print(f"[ALARM] Audio init failed: {e}")

        # Buzzer
        try:
            self._buzzer = machine.Pin(PIN_BUZZER, machine.Pin.OUT)
        except Exception as e:
            print(f"[ALARM] Buzzer init failed: {e}")

        # Vibration motor
        try:
            self._vibrate = machine.Pin(PIN_VIBRATE, machine.Pin.OUT)
        except Exception as e:
            print(f"[ALARM] Vibrate init failed: {e}")

        # SOS buttons (pull-up, falling edge)
        try:
            self._sos_pin = machine.Pin(PIN_SOS, machine.Pin.IN, machine.Pin.PULL_UP)
            self._sos_pin.irq(trigger=machine.Pin.IRQ_FALLING, handler=self._sos_handler)
        except Exception as e:
            print(f"[ALARM] SOS pin init failed: {e}")
        try:
            _pin2 = machine.Pin(PIN_SOS2, machine.Pin.IN, machine.Pin.PULL_UP)
            _pin2.irq(trigger=machine.Pin.IRQ_FALLING, handler=self._sos_handler)
            print(f"[ALARM] SOS2 pin ({PIN_SOS2}) ready")
        except Exception as e:
            print(f"[ALARM] SOS2 pin init failed: {e}")

        # Voice call (EC200U cellular)
        try:
            from quectel import Voice
            self._voice = Voice()
            self._voice.init(self._voice_cb)
            self._voice_ok = True
            print("[ALARM] Voice call ready")
        except Exception as e:
            print(f"[ALARM] Voice init failed: {e}")

        return True

    # ── Voice call ──

    def _voice_cb(self, id, direction, state, number):
        from quectel import Voice as V
        if direction == V.DIR_MT and state == V.STATE_INCOMING:
            self._incoming_call = True
            self._voice_active = True
        elif state == V.STATE_IDLE or state == V.STATE_END:
            self._voice_active = False
            self._incoming_call = False

    def is_call_active(self):
        return self._voice_active

    def hangup_all(self):
        """Hang up any active call and wait for modem to settle."""
        if not self._voice_ok:
            return
        try:
            self._voice.hangup()
            self._voice_active = False
            self._incoming_call = False
            time.sleep_ms(500)
        except Exception as e:
            print("[ALARM] hangup_all failed: {}".format(e))

    def emergency_call(self, number):
        if not self._voice_ok:
            print("[ALARM] Voice not available")
            return False
        try:
            self._voice_active = True
            self._voice.dial(number)
            print(f"[ALARM] Dialing {number}...")
            # Wait up to 20s for the call (ring + talk briefly)
            for _ in range(20):
                time.sleep(1)
                if not self._voice_active:
                    break
            # Hang up
            try:
                self._voice.hangup()
            except:
                pass
            self._voice_active = False
            print("[ALARM] Call ended")
            return True
        except Exception as e:
            print(f"[ALARM] Call failed: {e}")
            self._voice_active = False
            return False

    # ── Crash scene recording ──

    def record_scene(self, filepath):
        if not self._audio_ok:
            print("[ALARM] Audio not available for recording")
            return False
        try:
            # Stop any lingering TTS
            try:
                self.audio.tts_stop()
            except:
                pass
            time.sleep_ms(300)
            print(f"[ALARM] Recording {RECORD_DURATION_S}s to {filepath}...")
            self.audio.record_start(filepath)
            for _ in range(RECORD_DURATION_S):
                time.sleep(1)
            # Let firmware finish SD write before issuing stop
            time.sleep_ms(500)
            self.audio.record_stop()
            print("[ALARM] Recording saved")
            return True
        except Exception as e:
            print(f"[ALARM] Recording failed: {e}")
            # Reset audio state after failure so subsequent ops can proceed
            try:
                self.audio.tts_stop()
                time.sleep_ms(200)
            except:
                pass
            return False

    # ── SOS ──

    def _sos_handler(self, pin):
        if self._sos_triggered:
            return
        time.sleep_ms(50)
        if pin.value() == 0:
            self._sos_triggered = True
            self._sos_time = time.time()
            print("[ALARM] SOS button pressed!")

    def check_sos(self):
        return self._sos_triggered, self._sos_time

    def clear_sos(self):
        self._sos_triggered = False

    # ── TTS ──

    def play_tts(self, message):
        if not self._audio_ok:
            return
        try:
            self.audio.tts_play(message)
        except Exception as e:
            print(f"[ALARM] TTS failed: {e}")

    # ── Buzzer ──

    def buzzer_on(self):
        if self._buzzer:
            self._buzzer.value(1)

    def buzzer_off(self):
        if self._buzzer:
            self._buzzer.value(0)

    def buzzer_alert(self, count=3):
        for _ in range(count):
            self.buzzer_on()
            time.sleep(0.2)
            self.buzzer_off()
            time.sleep(0.2)

    # ── Vibration motor ──

    def vibrate_on(self):
        if self._vibrate:
            self._vibrate.value(1)

    def vibrate_off(self):
        if self._vibrate:
            self._vibrate.value(0)

    # ── Combined alerts ──

    def collision_alarm(self, level):
        if level >= 3:
            msg = "检测到严重碰撞，正在发送求助信息"
            self.buzzer_alert(5)
        elif level == 2:
            msg = "检测到碰撞，请确认是否安全"
            self.buzzer_alert(3)
        else:
            msg = "请注意骑行安全"
            self.buzzer_alert(1)
        self.play_tts(msg)
        return msg

    def sos_alarm(self):
        msg = "SOS 求助已发出，请等待救援"
        self.buzzer_alert(5)
        self.play_tts(msg)
        return msg

    def low_battery_alarm(self, level=1):
        if level >= 2:
            self.buzzer_alert(3)
            self.play_tts("电池电量严重不足，请立即充电")
        else:
            self.buzzer_alert(1)
            self.play_tts("电池电量不足，请及时充电")

    def deinit(self):
        self.buzzer_off()
        self.vibrate_off()
        if self._voice_ok:
            try:
                self._voice.hangup()
                self._voice.deinit()
            except:
                pass
        if self._audio_ok:
            try:
                self.audio.deinit()
            except:
                pass
