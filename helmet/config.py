# MQTT
MQTT_BROKER = "cn-xy.starryfrp.com"
MQTT_PORT = 1883
MQTT_USER = "helmet"
MQTT_PASS = "helmet"
DEVICE_ID = "helmet"
MQTT_CLIENT_ID = DEVICE_ID

# MQTT topics (ref: 下位机与服务器MQTT通信协议)
TOPIC_GPS = b"device/" + DEVICE_ID.encode() + b"/gps"
TOPIC_TELEMETRY = b"device/" + DEVICE_ID.encode() + b"/telemetry"
TOPIC_ALERT = b"device/" + DEVICE_ID.encode() + b"/alert"
TOPIC_STATUS = b"device/" + DEVICE_ID.encode() + b"/status"
TOPIC_RECORDING = b"device/" + DEVICE_ID.encode() + b"/recording"
TOPIC_CMD = b"device/" + DEVICE_ID.encode() + b"/cmd"
TOPIC_CONFIG = b"device/" + DEVICE_ID.encode() + b"/config"

# QoS
QOS_TELEMETRY = 1
QOS_ALERT = 1
QOS_STATUS = 1

# Collision thresholds
FREE_FALL_THRESHOLD = 0.4       # g, below this = free fall
FREE_FALL_DURATION_MS = 60      # ms, minimum free fall duration
IMPACT_WINDOW_MS = 500          # ms, window after free fall to catch impact

# Direct impact (no free fall needed) — catches side-swipes, rear-ends
DIRECT_IMPACT_L1 = 2.0          # g
DIRECT_IMPACT_L2 = 3.0          # g
DIRECT_IMPACT_L3 = 4.0          # g

# Free-fall + impact (lower thresholds, free fall already confirms)
FF_IMPACT_L1 = 1.5              # g
FF_IMPACT_L2 = 2.5              # g
FF_IMPACT_L3 = 3.5              # g

# Spike confirmation: direct impact needs 3 consecutive samples (wide pulse)
# Free-fall impact only needs 1 (free fall itself is the confirmation)
SPIKE_CONFIRM_SAMPLES = 2       # direct impact
FF_SPIKE_CONFIRM_SAMPLES = 1    # free-fall impact (already confirmed by fall)
COLLISION_COOLDOWN_MS = 5000    # 5s between alerts

# Upload intervals
UPLOAD_INTERVAL_MS = 30000      # 30s normal (MQTT publish is slow, don't block loop)
GPS_INTERVAL_MS = 10000         # 10s GPS
IDLE_INTERVAL_MS = 60000        # 60s when parked
KEEPALIVE_S = 60                # MQTT keepalive

# Light control — WS2812 strips
LIGHT_THRESHOLD_LUX = 400       # lux below which auto light turns on
LED_COUNT = 9                   # number of WS2812 LEDs per strip
LED_BRIGHTNESS = 128            # max brightness (0-255), lower = dimmer

# Battery
BAT_ADC_MAX = 4095
BAT_VOLT_MAX = 3.3              # max battery voltage (LiFePO4)
BAT_VOLT_MIN = 2.5              # empty voltage
BAT_LOW_1 = 50                  # % first warning
BAT_LOW_2 = 20                  # % critical
# LiFePO4 discharge curve: (voltage, percentage)
# Detailed at 0.5C, 25°C
BAT_CURVE = [
    (3.30, 100), (3.29, 98),  (3.28, 95),  (3.27, 91),
    (3.26, 87),  (3.25, 82),  (3.24, 77),  (3.23, 72),
    (3.22, 67),  (3.21, 62),  (3.20, 58),  (3.19, 54),
    (3.18, 50),  (3.17, 46),  (3.16, 42),  (3.15, 38),
    (3.14, 35),  (3.13, 32),  (3.12, 29),  (3.11, 26),
    (3.10, 23),  (3.09, 20),  (3.08, 18),  (3.07, 16),
    (3.06, 14),  (3.05, 12),  (3.04, 10),  (3.03, 9),
    (3.02, 8),   (3.01, 7),   (3.00, 6),   (2.95, 4),
    (2.90, 3),   (2.80, 1),   (2.50, 0),
]

# SOS
SOS_AUTO_TIMEOUT_S = 10         # auto SOS after 10s no response

# Sampling
SAMPLE_INTERVAL_MS = 20         # 50Hz for accelerometer

# Pin mapping
PIN_LED_LEFT = "D3"             # PWM left light
PIN_LED_RIGHT = "D5"            # PWM right light
PIN_BUZZER = "D6"               # PWM buzzer
PIN_VIBRATE = "C0"              # vibration motor (active high)
PIN_SOS = "D2"                  # interrupt button
PIN_SOS2 = "C11"                # 备用 SOS 按键 (低电平触发)
PIN_BAT_ADC = "A0"              # battery voltage
PIN_LIGHT_ADC = "C5"            # onboard light sensor

# Distance sensor (ADC)
PIN_DIST_ADC = "A3"             # distance sensor ADC pin
DIST_WARN_THRESHOLD = 1.0       # m, voice alert when closer than this
DIST_WARN_COOLDOWN_S = 10       # seconds between distance alerts

# Speed warning
SPEED_WARN_THRESHOLD = 30        # km/h, TTS alert when exceeding
SPEED_WARN_COOLDOWN_S = 30       # seconds between alerts

#4iuu Emergency
EMERGENCY_NUM = "19741108515"     # 紧急联系人号码

# Power saving
IDLE_TIMEOUT_MS = 300000        # 5min idle → power save mode
DEEP_IDLE_TIMEOUT_MS = 1800000  # 30min idle → deep sleep
POWER_SAVE_INTERVAL_MS = 100    # 10Hz in power save mode
IDLE_ACCEL_THRESHOLD = 0.3      # acceleration variance threshold for idle detection

# BLE
BLE_NAME = "Helmet_001"
BLE_SERVICE_UUID = 0xFFF0
BLE_CHAR_UUID = 0xFFF1

# OTA
OTA_SERVER = "http://101.37.104.185:47729/ota/"

# Logging
LOG_DIR = "SD:helmet/"
LOG_INTERVAL_S = 5              # 5s between log entries
44444444444444444444444444444444444444444444



# Recording
RECORD_DURATION_S = 10

# LCD
LCD_DC = "F12"
LCD_CS = "D14"
LCD_ROTATION = 1
