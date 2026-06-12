"""Copy to config.py and fill in. config.py is git-ignored -- never commit secrets."""

# ---- WiFi/network is handled by the Pi OS; just set the endpoint ----
MONITOR_URL = "http://192.168.1.50:8123/api/webhook/septic"
MONITOR_TOKEN = ""            # optional bearer token; "" if none
POST_INTERVAL_S = 15.0

# ---- GPIO pins (BCM numbering). See docs/WIRING.md ----
PIN_FLOAT_LOW = 17            # Float 1: low / pump OFF (dry-run)
PIN_FLOAT_CTRL = 27           # Float 2: control / pump ON backup
PIN_FLOAT_HIGH = 22           # Float 3: HIGH-LEVEL ALARM
PIN_PUMP_RELAY = 23           # -> opto relay -> contactor coil
PIN_LED_RUN = 24
PIN_LED_ALARM = 25
PIN_BUZZER = 5

# Floats are dry contacts to GND with internal pull-up -> tripped reads pressed.
FLOAT_ACTIVE_LOW = True

# ---- Level sensor scaling (4-20 mA loop on ADS1115) ----
ADS_CHANNEL = 0
SENSE_OHMS = 165.0
LEVEL_RANGE_IN = 60.0         # transmitter full-scale in inches (5 ft = 60)
LOOP_MIN_MA = 4.0
LOOP_MAX_MA = 20.0
LOOP_VALID_MIN_MA = 3.5       # below -> open/short -> sensor fault
LOOP_VALID_MAX_MA = 20.5

# ---- Control thresholds (inches) ----
LEVEL_ON_IN = 30.0
LEVEL_OFF_IN = 12.0           # must be < LEVEL_ON_IN
MIN_OFF_SECONDS = 60.0        # anti short-cycle
MAX_RUN_SECONDS = 600.0       # runtime watchdog -> alarm
