"""WS2812 灯带驱动 (基于 machine.bitstream)"""

import machine
import time


# WS2812 时序 (ns: 高电平, 低电平)
# 不同固件可能需要微调
# 编码 (t0h_ns, t0l_ns, t1h_ns, t1l_ns)
_ENCODING = (350, 800, 700, 600)


class NeoPixel:
    """兼容 neopixel.NeoPixel 接口的 WS2812 驱动。"""

    def __init__(self, pin, n):
        self._pin = machine.Pin(pin, machine.Pin.OUT)
        self._n = n
        self._buf = bytearray(n * 3)

    def __len__(self):
        return self._n

    def __setitem__(self, idx, color):
        """color = (r, g, b)"""
        if not (0 <= idx < self._n):
            return
        r, g, b = color[:3]
        # WS2812 数据顺序: G, R, B
        i = idx * 3
        self._buf[i] = g
        self._buf[i + 1] = r
        self._buf[i + 2] = b

    def __getitem__(self, idx):
        if not (0 <= idx < self._n):
            return (0, 0, 0)
        i = idx * 3
        return (self._buf[i + 1], self._buf[i], self._buf[i + 2])

    def write(self):
        """发送数据到灯带。"""
        # bitstream(pin, mode, (t0h, t0l, t1h, t1l), data)
        machine.bitstream(self._pin, 0, _ENCODING, self._buf)
        # WS2812 需要 >280us 的低电平复位才能锁存
        self._pin.value(0)
        time.sleep_us(300)

    def fill(self, r, g, b):
        """全部灯设为同一颜色。"""
        gb = g
        rb = r
        bb = b
        buf = self._buf
        n3 = self._n * 3
        for i in range(0, n3, 3):
            buf[i] = gb
            buf[i + 1] = rb
            buf[i + 2] = bb
