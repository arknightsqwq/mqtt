from config import *

class BLEManager:
    def __init__(self):
        self._ble = None
        self._started = False
        self._connected = False

    def _str_to_hex(self, s):
        return ''.join('%02X' % b for b in s.encode())

    def _deinit_hw(self):
        try:
            self._ble.stop()
        except:
            pass
        try:
            self._ble.deinit()
        except:
            pass

    def init(self):
        try:
            from quectel import BLE
            self._ble = BLE()
            # Clear any leftover BLE state from previous failed init
            self._deinit_hw()
            import utime
            utime.sleep_ms(200)

            if not self._ble.init(self._cb):
                return False

            self._ble.set_dataformat(self._ble.DATAFMT_STRING)

            # Retry start() to work around EC200U QBTPWR=1 CME ERROR:4 timing issue
            for i in range(5):
                try:
                    self._ble.start(BLE_NAME)
                    break
                except Exception as e:
                    print(f"[BLE] start attempt {i+1}/5 failed: {e}")
                    self._deinit_hw()
                    utime.sleep_ms(1000)
                    if not self._ble.init(self._cb):
                        return False
                    self._ble.set_dataformat(self._ble.DATAFMT_STRING)
                    utime.sleep_ms(500)
            else:
                print("[BLE] All start attempts failed")
                return False

            self._ble.add_service(0, BLE_SERVICE_UUID, True)
            props = self._ble.PROP_READ | self._ble.PROP_NOTIFY
            self._ble.add_character(0, 0, props, BLE_CHAR_UUID)
            self._ble.set_character_value(0, 0,
                self._ble.PERM_READ | self._ble.PERM_WRITE,
                BLE_CHAR_UUID, 244, self._str_to_hex("READY"))
            self._ble.add_descriptor(0, 0,
                self._ble.PERM_READ | self._ble.PERM_WRITE,
                0x2902, "0000")

            self._ble.advertise()
            self._started = True
            print(f"[BLE] Broadcasting as {BLE_NAME}")
            return True
        except Exception as e:
            print(f"[BLE] Init failed: {e}")
            self._deinit_hw()
            return False

    def _cb(self, evt):
        from quectel import BLE
        if evt.get("event") == BLE.EVT_CONNECTED:
            self._connected = True
            print("[BLE] Phone connected")
        elif evt.get("event") == BLE.EVT_DISCONNECTED:
            self._connected = False
            print("[BLE] Phone disconnected, restarting advertising")
            try:
                self._ble.advertise()
            except:
                pass

    def notify(self, data_str):
        if not self._started or not self._connected:
            return
        try:
            self._ble.notify(BLE_CHAR_UUID, len(data_str), data_str)
        except:
            # Phone may have disconnected without EVT_DISCONNECTED
            self._connected = False
            try:
                self._ble.advertise()
            except:
                pass

    def is_connected(self):
        return self._connected

    def deinit(self):
        if self._started:
            try:
                self._ble.stop()
                self._ble.deinit()
            except:
                pass
