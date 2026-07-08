"""
MAX30102 心率/血氧传感器 MicroPython 驱动
适用平台: Quectel EC200U (machine.I2C)
参考: SparkFun MAX30105 Library / MAX30100 Arduino Library
"""

I2C_ADDR = 0x57
EXPECTED_PART_ID = 0x15

# 寄存器
REG_INTSTAT1 = 0x00
REG_INTSTAT2 = 0x01
REG_INTENABLE1 = 0x02
REG_INTENABLE2 = 0x03
REG_FIFO_WR_PTR = 0x04
REG_FIFO_OVF = 0x05
REG_FIFO_RD_PTR = 0x06
REG_FIFO_DATA = 0x07
REG_FIFO_CONFIG = 0x08
REG_MODE_CONFIG = 0x09
REG_SPO2_CONFIG = 0x0A
REG_LED1_PA = 0x0C   # RED
REG_LED2_PA = 0x0D   # IR
REG_LED3_PA = 0x0E   # GREEN (MAX30102 无)
REG_PROX_INT_THRESH = 0x10
REG_MULTI_LED1 = 0x11
REG_MULTI_LED2 = 0x12
REG_DIE_TEMP_INT = 0x1F
REG_DIE_TEMP_FRAC = 0x20
REG_DIE_TEMP_CONFIG = 0x21
REG_PROX_INT_THRESH = 0x30
REG_REVISION_ID = 0xFE
REG_PART_ID = 0xFF

# 模式
MODE_HR_ONLY = 0x02
MODE_SPO2_HR = 0x03
MODE_MULTI_LED = 0x07

# 采样率 (SPO2_CONFIG)
SAMPRATE_50 = 0x00
SAMPRATE_100 = 0x01
SAMPRATE_200 = 0x02
SAMPRATE_400 = 0x03
SAMPRATE_800 = 0x04
SAMPRATE_1000 = 0x05
SAMPRATE_1600 = 0x06
SAMPRATE_3200 = 0x07

# 脉宽
PULSE_WIDTH_69 = 0x00   # 15 bit
PULSE_WIDTH_118 = 0x01  # 16 bit
PULSE_WIDTH_215 = 0x02  # 17 bit
PULSE_WIDTH_411 = 0x03  # 18 bit

# ADC 范围
ADC_RANGE_2048 = 0x00
ADC_RANGE_4096 = 0x01
ADC_RANGE_8192 = 0x02
ADC_RANGE_16384 = 0x03

# FIFO 平均采样
SAMPLE_AVG_1 = 0x00
SAMPLE_AVG_2 = 0x20
SAMPLE_AVG_4 = 0x40
SAMPLE_AVG_8 = 0x60
SAMPLE_AVG_16 = 0x80
SAMPLE_AVG_32 = 0xA0


class MAX30102:
    def __init__(self, i2c, addr=I2C_ADDR):
        self.i2c = i2c
        self.addr = addr
        self.active_leds = 2  # RED + IR

    # ── 底层 I2C ──

    def _read_reg(self, reg):
        buf = self.i2c.readfrom_mem(self.addr, reg, 1)
        return buf[0]

    def _write_reg(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes([val]))

    def _read_burst(self, reg, length):
        return self.i2c.readfrom_mem(self.addr, reg, length)

    def _bitmask(self, reg, mask, val):
        cur = self._read_reg(reg)
        cur = (cur & mask) | val
        self._write_reg(reg, cur)

    # ── 初始化 ──

    def begin(self):
        """初始化并验证传感器"""
        part_id = self._read_reg(REG_PART_ID)
        if part_id != EXPECTED_PART_ID:
            raise RuntimeError(
                f"MAX30102 not found: part_id=0x{part_id:02X}, expected 0x{EXPECTED_PART_ID:02X}"
            )
        self.soft_reset()
        return True

    def soft_reset(self):
        """软复位"""
        self._write_reg(REG_MODE_CONFIG, 0x40)
        # 等待复位完成 (超时 100ms)
        import utime
        t0 = utime.ticks_ms()
        while utime.ticks_diff(utime.ticks_ms(), t0) < 100:
            if not (self._read_reg(REG_MODE_CONFIG) & 0x40):
                break
            utime.sleep_ms(1)

    # ── 配置 ──

    def setup(self, power_level=0x1F, sample_avg=4, led_mode=2,
              sample_rate=100, pulse_width=411, adc_range=4096):
        """一站式配置"""
        # FIFO 平均
        avg_map = {1: SAMPLE_AVG_1, 2: SAMPLE_AVG_2, 4: SAMPLE_AVG_4,
                   8: SAMPLE_AVG_8, 16: SAMPLE_AVG_16, 32: SAMPLE_AVG_32}
        self._bitmask(REG_FIFO_CONFIG, 0x1F, avg_map.get(sample_avg, SAMPLE_AVG_4))
        # FIFO rollover
        self._bitmask(REG_FIFO_CONFIG, 0xEF, 0x10)
        # LED 模式
        if led_mode == 3:
            self._write_reg(REG_MODE_CONFIG, MODE_MULTI_LED)
        elif led_mode == 2:
            self._write_reg(REG_MODE_CONFIG, MODE_SPO2_HR)
        else:
            self._write_reg(REG_MODE_CONFIG, MODE_HR_ONLY)
        self.active_leds = led_mode
        # ADC 范围
        adc_map = {2048: ADC_RANGE_2048, 4096: ADC_RANGE_4096,
                   8192: ADC_RANGE_8192, 16384: ADC_RANGE_16384}
        self._bitmask(REG_SPO2_CONFIG, 0x9F, adc_map.get(adc_range, ADC_RANGE_4096) << 5)
        # 采样率
        rate_map = {50: SAMPRATE_50, 100: SAMPRATE_100, 200: SAMPRATE_200,
                    400: SAMPRATE_400, 800: SAMPRATE_800, 1000: SAMPRATE_1000,
                    1600: SAMPRATE_1600, 3200: SAMPRATE_3200}
        self._bitmask(REG_SPO2_CONFIG, 0xE3, rate_map.get(sample_rate, SAMPRATE_100) << 2)
        # 脉宽
        pw_map = {69: PULSE_WIDTH_69, 118: PULSE_WIDTH_118,
                  215: PULSE_WIDTH_215, 411: PULSE_WIDTH_411}
        self._bitmask(REG_SPO2_CONFIG, 0xFC, pw_map.get(pulse_width, PULSE_WIDTH_411))
        # LED 电流
        self._write_reg(REG_LED1_PA, power_level)
        self._write_reg(REG_LED2_PA, power_level)
        # Multi-LED slot
        if led_mode >= 1:
            self._write_reg(REG_MULTI_LED1, 0x01)  # slot1 = RED
        if led_mode >= 2:
            self._write_reg(REG_MULTI_LED1, 0x21)  # slot1=RED, slot2=IR
        self.clear_fifo()

    def set_pa_red(self, val):
        self._write_reg(REG_LED1_PA, val)

    def set_pa_ir(self, val):
        self._write_reg(REG_LED2_PA, val)

    # ── FIFO ──

    def clear_fifo(self):
        self._write_reg(REG_FIFO_WR_PTR, 0)
        self._write_reg(REG_FIFO_OVF, 0)
        self._write_reg(REG_FIFO_RD_PTR, 0)

    def get_wr_ptr(self):
        return self._read_reg(REG_FIFO_WR_PTR)

    def get_rd_ptr(self):
        return self._read_reg(REG_FIFO_RD_PTR)

    def available(self):
        """FIFO 中可用样本数"""
        wr = self.get_wr_ptr()
        rd = self.get_rd_ptr()
        if wr == rd:
            return 0
        n = (wr - rd) & 0x1F
        return n

    def read_fifo(self):
        """读所有可用样本, 返回 [(red, ir), ...]"""
        n = self.available()
        if n == 0:
            return []
        samples = []
        for _ in range(n):
            data = self._read_burst(REG_FIFO_DATA, self.active_leds * 3)
            red = (data[0] << 16) | (data[1] << 8) | data[2]
            red &= 0x3FFFF
            ir = 0
            if self.active_leds >= 2:
                ir = (data[3] << 16) | (data[4] << 8) | data[5]
                ir &= 0x3FFFF
            samples.append((red, ir))
        return samples

    # ── 温度 ──

    def read_temp(self):
        """读取芯片温度 (°C)"""
        self._write_reg(REG_DIE_TEMP_CONFIG, 0x01)
        import utime
        t0 = utime.ticks_ms()
        while utime.ticks_diff(utime.ticks_ms(), t0) < 100:
            if not (self._read_reg(REG_DIE_TEMP_CONFIG) & 0x01):
                break
            utime.sleep_ms(1)
        temp_int = self._read_reg(REG_DIE_TEMP_INT)
        temp_frac = self._read_reg(REG_DIE_TEMP_FRAC)
        # temp_int 是 signed 8-bit
        if temp_int > 127:
            temp_int -= 256
        return temp_int + temp_frac * 0.0625

    # ── 便捷方法 ──

    def get_hr_spo2_ready(self):
        """检查是否有新数据 (通过 INTSTAT1 寄存器)"""
        st = self._read_reg(REG_INTSTAT1)
        return bool(st & 0x40)  # DATA_RDY bit

    def shutdown(self):
        self._bitmask(REG_MODE_CONFIG, 0x7F, 0x80)

    def wakeup(self):
        self._bitmask(REG_MODE_CONFIG, 0x7F, 0x00)


# ── 信号处理滤波器 ──

class DCRemover:
    """高通滤波器：瞬时去除 DC 偏置，输出 AC 分量
       参考 MAX30100 Arduino Library: y[n] = x[n] - (1-alpha) * y[n-1]"""
    def __init__(self, alpha=0.95):
        self.alpha = alpha
        self.dcw = 0

    def step(self, x):
        olddcw = self.dcw
        self.dcw = x + self.alpha * self.dcw
        return self.dcw - olddcw


class LowPassFilter:
    """6Hz 低通 Butterworth 滤波器 (Fs=100Hz, Fc=6Hz, order=1)
       参考 MAX30100 Filters.h"""
    def __init__(self):
        self.v = [0.0, 0.0]

    def step(self, x):
        self.v[0] = self.v[1]
        self.v[1] = 0.2452372752527856 * x + 0.5095254494944288 * self.v[0]
        return self.v[0] + self.v[1]


# ── 心跳检测状态机 ──
# 参考 MAX30100_BeatDetector.cpp 的 5-state 实现
# 状态: INIT (2s静默) → WAITING (阈值追踪) → FOLLOWING_SLOPE (跟踪上升沿)
#       → MAYBE_DETECTED (确认波峰) → MASKING (200ms 不应期)

SAMPLE_PERIOD_MS = 10       # 采样周期 100Hz, 用于阈值衰减速率

class BeatDetector:
    STATE_INIT = 0
    STATE_WAITING = 1
    STATE_FOLLOWING_SLOPE = 2
    STATE_MAYBE_DETECTED = 3
    STATE_MASKING = 4

    def __init__(self):
        self.state = self.STATE_INIT
        self._init_samples = 0
        self.threshold = 20            # BEATDETECTOR_MIN_THRESHOLD
        self.beat_period = 0           # EMA 平滑后的心跳周期 (ms)
        self.last_max_value = 0        # 上一个波峰的幅值
        self.ts_start = 0              # 启动时间戳
        self.ts_last_beat = 0          # 上次心跳时间
        self.beat_detected_flag = False

    def reset(self):
        self.state = self.STATE_INIT
        self._init_samples = 0
        self.threshold = 20
        self.beat_period = 0
        self.last_max_value = 0
        self.ts_last_beat = 0
        self.ts_start = 0

    def add_sample(self, sample, now_ms):
        """输入滤波后的脉搏信号（已经镜像+低通），返回是否检测到心跳"""
        if self.ts_start == 0:
            self.ts_start = now_ms
        return self._check_for_beat(sample, now_ms)

    def _check_for_beat(self, sample, now_ms):
        beat = False

        if self.state == self.STATE_INIT:
            # 静默 50 个样本让 DCRemover 收敛
            self._init_samples += 1
            if self._init_samples >= 50:
                self.state = self.STATE_WAITING
                self._init_samples = 0

        elif self.state == self.STATE_WAITING:
            if sample > self.threshold:
                self.threshold = min(sample, 800)  # MAX_THRESHOLD
                self.state = self.STATE_FOLLOWING_SLOPE

            if self.ts_last_beat and (now_ms - self.ts_last_beat > 5000):
                self.beat_period = 0
                self.last_max_value = 0

            self._decay_threshold()

        elif self.state == self.STATE_FOLLOWING_SLOPE:
            if sample < self.threshold:
                self.state = self.STATE_MAYBE_DETECTED
            else:
                self.threshold = min(sample, 800)

        elif self.state == self.STATE_MAYBE_DETECTED:
            if sample + 30 < self.threshold:   # STEP_RESILIENCY
                beat = True
                self.last_max_value = sample
                self.state = self.STATE_MASKING
                delta = now_ms - self.ts_last_beat
                # 只接受 30~200 BPM 的有效间隔
                if 300 <= delta <= 2000 and self.ts_last_beat > 0:
                    if self.beat_period == 0:
                        self.beat_period = delta
                    else:
                        self.beat_period = 0.3 * delta + 0.7 * self.beat_period
                self.ts_last_beat = now_ms
            else:
                self.state = self.STATE_FOLLOWING_SLOPE

        elif self.state == self.STATE_MASKING:
            if now_ms - self.ts_last_beat > 200:  # MASKING_HOLDOFF
                self.state = self.STATE_WAITING
            self._decay_threshold()

        return beat

    def _decay_threshold(self):
        """阈值渐进衰减"""
        if self.last_max_value > 0 and self.beat_period > 0:
            self.threshold -= self.last_max_value * 0.7 / (self.beat_period / SAMPLE_PERIOD_MS)
        else:
            self.threshold *= 0.995             # THRESHOLD_DECAY_FACTOR

        if self.threshold < 20:                  # MIN_THRESHOLD
            self.threshold = 20

    @property
    def bpm(self):
        """根据 EMA 平滑后的周期计算心率，仅返回 30~200 合理范围"""
        if self.beat_period > 0:
            b = round(60000.0 / self.beat_period)
            return b if 30 <= b <= 200 else 0
        return 0


# ── SpO2 计算器 ──
# 参考 MAX30100_SpO2Calculator: 累加多拍的 AC^2，用 RMS 比查表
# LUT 来自 TI Application Note SLAA274b
SPO2_LUT = (100,100,100,100,99,99,99,99,99,99,98,98,98,98,
            98,97,97,97,97,97,97,96,96,96,96,96,96,95,95,
            95,95,95,95,94,94,94,94,94,93,93,93,93,93)

class SpO2Calculator:
    def __init__(self):
        self.spo2 = 0
        self.reset()

    def reset(self):
        self.ir_ac_sq_sum = 0
        self.red_ac_sq_sum = 0
        self.samples = 0
        self.beats = 0

    def update(self, ir_ac, red_ac, beat_detected):
        self.ir_ac_sq_sum += ir_ac * ir_ac
        self.red_ac_sq_sum += red_ac * red_ac
        self.samples += 1

        if beat_detected:
            self.beats += 1
            if self.beats >= 4:   # CALCULATE_EVERY_N_BEATS
                new_spo2 = 0
                if self.ir_ac_sq_sum > 0 and self.samples > 0:
                    ratio = 100.0 * _log(self.red_ac_sq_sum / self.samples) / _log(self.ir_ac_sq_sum / self.samples)
                    idx = -1
                    if ratio > 66:
                        idx = int(ratio) - 66
                    elif ratio > 50:
                        idx = int(ratio) - 50
                    if 0 <= idx < len(SPO2_LUT):
                        new_spo2 = SPO2_LUT[idx]
                self.reset()
                self.spo2 = new_spo2


__math_log = None
def _log(x):
    global __math_log
    if __math_log is None:
        import math
        __math_log = math.log
    return __math_log(x)


# ── 主算法类 ──

class HeartRateMonitor:
    """基于 MAX30100 Arduino Library 状态机的心率/血氧算法
       处理流水线: raw → DCRemover(高通) → 镜像 → LowPass(6Hz) → BeatDetector → BPM
                                                               ↕
                                                          SpO2Calculator
    """

    def __init__(self):
        self.ir_dc_remover = DCRemover(0.95)
        self.red_dc_remover = DCRemover(0.95)
        self.lpf = LowPassFilter()
        self.beat_detector = BeatDetector()
        self.spo2_calc = SpO2Calculator()
        self._signal_ok = False
        self._ir_ac = 0
        self._red_ac = 0
        self._last_filtered = 0

    def reset(self):
        self.ir_dc_remover = DCRemover(0.95)
        self.red_dc_remover = DCRemover(0.95)
        self.lpf = LowPassFilter()
        self.beat_detector.reset()
        self.spo2_calc.reset()
        self._signal_ok = False

    def process(self, red, ir, now_ms):
        if ir < 10000:
            self._signal_ok = False
            return

        self._signal_ok = True

        # 1. DCRemover → 瞬时输出 AC 分量
        ir_ac = self.ir_dc_remover.step(ir)
        red_ac = self.red_dc_remover.step(red)
        self._ir_ac = ir_ac
        self._red_ac = red_ac

        # 2. 镜像(负脉搏信号更干净) + 低通滤波 → 送心跳检测
        #    参考: "the cleanest monotonic spike is below zero"
        filtered = self.lpf.step(-ir_ac)
        self._last_filtered = filtered

        # 3. 心跳检测 (5-state 状态机)
        beat = self.beat_detector.add_sample(filtered, now_ms)

        # 4. SpO2 累加计算 (仅在有心跳时才出数)
        if self.beat_detector.bpm > 0:
            self.spo2_calc.update(ir_ac, red_ac, beat)

    @property
    def bpm(self):
        return self.beat_detector.bpm if self._signal_ok else 0

    @property
    def spo2(self):
        return self.spo2_calc.spo2 if (self._signal_ok and self.bpm > 0) else 0

    @property
    def has_signal(self):
        return self._signal_ok

