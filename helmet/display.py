import machine
import time
from st7735 import LCD
import config
from config import *

# WS2812 helper: set all LEDs to (r, g, b) on a strip
def _fill_strip(np, r, g, b):
    for i in range(len(np)):
        np[i] = (r, g, b)
    np.write()

class DisplayManager:
    def __init__(self):
        # LCD
        self._lcd = None
        self._lcd_off = False
        self._last_bat_warn = 0

        # WS2812 strips
        self._led_left = None
        self._led_right = None
        self._buzzer = None
        self._light_mode = "auto"   # "auto" | "warning" | "emergency"

    def init_lcd(self):
        try:
            spi = machine.SPI(1, baudrate=20000000, polarity=0, phase=0)
            self._lcd = LCD(spi, dc_pin=LCD_DC, cs_pin=LCD_CS)
            self._lcd.set_rotation(LCD_ROTATION)
            self._lcd.fill_screen(self._lcd.BLACK)
            return True
        except Exception as e:
            print(f"[DISP] LCD init failed: {e}")
            return False

    def init_leds(self):
        try:
            from ws2812 import NeoPixel
            self._led_left = NeoPixel(PIN_LED_LEFT, LED_COUNT)
            self._led_right = NeoPixel(PIN_LED_RIGHT, LED_COUNT)
            self._buzzer = machine.Pin(PIN_BUZZER, machine.Pin.OUT)
            self._led_left.write()
            self._led_right.write()
            return True
        except Exception as e:
            print(f"[DISP] LED init failed: {e}")
            return False

    def update_display(self, sensor_data, collision_level, stats=None):
        if not self._lcd:
            return
        if self._lcd_off:
            return
        lcd = self._lcd
        lcd.fill_screen(lcd.BLACK)

        # Row 1: Status
        status = "RIDING" if sensor_data.get("mag", 1) > 0.3 else "IDLE"
        if collision_level > 0:
            status = f"ALERT L{collision_level}"
        if self._lcd_off:
            status = "SLEEP"
        color = lcd.GREEN if collision_level == 0 else (lcd.YELLOW if collision_level == 1 else lcd.RED)
        lcd.show_string(0, 0, f"Status: {status}", color, lcd.BLACK)

        # Row 2: Temp / Humi
        t = sensor_data.get("temp")
        h = sensor_data.get("humi")
        if t is not None:
            lcd.show_string(0, 18, f"Temp: {t:.1f}C  Hum: {h:.0f}%", lcd.WHITE, lcd.BLACK)

        # Row 3: Accel
        mag = sensor_data.get("mag", 0)
        lcd.show_string(0, 36, f"G: {mag:.2f}g", lcd.CYAN, lcd.BLACK)

        # Row 4: Battery
        bat = sensor_data.get("bat", 0)
        bat_color = lcd.GREEN if bat > 50 else (lcd.YELLOW if bat > 20 else lcd.RED)
        lcd.show_string(0, 54, f"Bat: {bat}%", bat_color, lcd.BLACK)

        # Row 5: Speed / Distance
        speed = stats.speed if stats else 0
        dist = stats.distance_km if stats else 0
        lcd.show_string(0, 72, f"Spd:{speed:.1f}  D:{dist:.2f}km", lcd.WHITE, lcd.BLACK)

        # Row 6: Altitude / Lux
        alt = stats.altitude if stats else 0
        lux = sensor_data.get("lux", 0)
        lcd.show_string(0, 90, f"Alt:{alt}m  Lux:{int(lux)}", lcd.WHITE, lcd.BLACK)

        # Row 7: Heart Rate / SpO2
        bpm = sensor_data.get("bpm", 0)
        spo2 = sensor_data.get("spo2", 0)
        bpm_str = str(bpm) if bpm and bpm > 0 else "--"
        spo2_str = str(spo2) if spo2 and spo2 > 0 else "--"
        lcd.show_string(0, 108, f"HR:{bpm_str}bpm  SpO2:{spo2_str}%", lcd.WHITE, lcd.BLACK)

        lcd.flush()

    def lcd_off(self):
        self._lcd_off = True
        if self._lcd:
            self._lcd.fill_screen(self._lcd.BLACK)
            self._lcd.flush()

    def lcd_on(self):
        self._lcd_off = False

    def _lux_to_brightness(self, lux):
        """将环境光映射到灯带亮度: 越暗越亮, >=阈值全灭"""
        if lux >= config.LIGHT_THRESHOLD_LUX:
            return 0
        ratio = 1.0 - lux / config.LIGHT_THRESHOLD_LUX
        return max(0, min(config.LED_BRIGHTNESS, int(config.LED_BRIGHTNESS * ratio)))

    def auto_light(self, lux):
        """按当前 light_mode 和环境光照控制灯带。每 ~500ms 调用。"""
        if self._led_left is None:
            return

        if self._light_mode == "emergency":
            # 红色常亮, 直到 main 流程恢复 auto
            _fill_strip(self._led_left, config.LED_BRIGHTNESS, 0, 0)
            _fill_strip(self._led_right, config.LED_BRIGHTNESS, 0, 0)
            return

        if self._light_mode == "warning":
            # 橙色常亮, 距离过近
            b = config.LED_BRIGHTNESS
            _fill_strip(self._led_left, b, b // 3, 0)
            _fill_strip(self._led_right, b, b // 3, 0)
            return

        # auto: 亮度随环境光比例调节
        b = self._lux_to_brightness(lux)
        _fill_strip(self._led_left, b, b, b)
        _fill_strip(self._led_right, b, b, b)

    def set_light_mode(self, mode):
        """切换灯光模式: 'auto' / 'warning' / 'emergency'"""
        self._light_mode = mode

    def sos_blink(self, enable):
        if self._led_left is None or self._led_right is None:
            return
        if enable:
            for _ in range(20):
                _fill_strip(self._led_left, config.LED_BRIGHTNESS, 0, 0)
                _fill_strip(self._led_right, config.LED_BRIGHTNESS, 0, 0)
                time.sleep(0.1)
                _fill_strip(self._led_left, 0, 0, 0)
                _fill_strip(self._led_right, 0, 0, 0)
                time.sleep(0.1)
        else:
            _fill_strip(self._led_left, 0, 0, 0)
            _fill_strip(self._led_right, 0, 0, 0)
