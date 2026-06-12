// Septic Lift Station Monitor & Pump Controller (ESP32)
//
// - Continuous level in inches from a 4-20 mA submersible transmitter (via ADS1115)
// - 3 redundant sewage-rated float switches (low / control / high-alarm)
// - Pump control via opto relay -> contactor (120 V / 30 A pump)
// - Remote monitoring: POSTs JSON status over WiFi
//
// Copy config.h.example -> config.h and fill in your values before flashing.
// See docs/WIRING.md for the panel, pinout, and 4-20 mA scaling math.

#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <ADS1X15.h>
#include "config.h"

ADS1115 ads(0x48);

// ---- runtime state ----
bool   pumpOn         = false;
bool   alarmActive    = false;
bool   sensorFault    = false;
float  levelInches    = 0.0;
float  loopMA         = 0.0;
uint32_t pumpStartedAt = 0;   // millis() when pump last turned on
uint32_t pumpStoppedAt = 0;   // millis() when pump last turned off
uint32_t lastPostAt    = 0;

// ---------- helpers ----------
bool floatTripped(int pin) {
  int v = digitalRead(pin);
  return FLOAT_ACTIVE_LOW ? (v == LOW) : (v == HIGH);
}

void setPump(bool on) {
  if (on == pumpOn) return;
  pumpOn = on;
  digitalWrite(PIN_PUMP_RELAY, on ? HIGH : LOW);
  digitalWrite(PIN_LED_RUN,    on ? HIGH : LOW);
  if (on) pumpStartedAt = millis();
  else    pumpStoppedAt = millis();
  Serial.printf("[PUMP] %s\n", on ? "ON" : "OFF");
}

void setAlarm(bool on) {
  alarmActive = on;
  digitalWrite(PIN_LED_ALARM, on ? HIGH : LOW);
  digitalWrite(PIN_BUZZER,    on ? HIGH : LOW);
}

// Read the 4-20 mA loop and convert to inches. Sets sensorFault on out-of-band.
void readLevel() {
  int16_t raw = ads.readADC(ADS_CHANNEL);
  float volts = ads.toVoltage(raw);     // volts at the sense resistor
  loopMA = (volts / SENSE_OHMS) * 1000.0;

  if (loopMA < LOOP_VALID_MIN_MA || loopMA > LOOP_VALID_MAX_MA) {
    sensorFault = true;                 // open/short loop -> trust floats instead
    return;
  }
  sensorFault = false;
  float frac = (loopMA - LOOP_MIN_MA) / (LOOP_MAX_MA - LOOP_MIN_MA);
  if (frac < 0) frac = 0;
  levelInches = frac * LEVEL_RANGE_IN;
}

// Decide pump state. Priority: high alarm > dry-run > level/float control.
void controlLogic() {
  bool fLow  = floatTripped(PIN_FLOAT_LOW);
  bool fCtrl = floatTripped(PIN_FLOAT_CTRL);
  bool fHigh = floatTripped(PIN_FLOAT_HIGH);

  // 1) High-level alarm: independent overflow protection.
  if (fHigh) {
    setAlarm(true);
    setPump(true);
    return;
  }

  // 2) Dry-run protection always wins to keep liquid OFF the pump.
  if (fLow) {
    setPump(false);
    // alarm only clears once water is back above the OFF threshold path below
  }

  uint32_t now = millis();
  bool offLongEnough = (now - pumpStoppedAt) >= (MIN_OFF_SECONDS * 1000UL);

  bool wantOn;
  if (sensorFault) {
    // 3) Analog level lost -> float-only control.
    wantOn = fCtrl && !fLow;
  } else {
    // 4) Normal: hysteresis on inches.
    if (pumpOn) wantOn = levelInches > LEVEL_OFF_IN;
    else        wantOn = levelInches >= LEVEL_ON_IN;
  }

  if (fLow) wantOn = false;             // dry-run override

  if (wantOn && !pumpOn && offLongEnough) setPump(true);
  else if (!wantOn && pumpOn)             setPump(false);

  // 5) Runtime watchdog.
  if (pumpOn && (now - pumpStartedAt) >= (MAX_RUN_SECONDS * 1000UL)) {
    setAlarm(true);
  } else if (!fHigh && !sensorFault) {
    setAlarm(false);
  }
}

void publishStatus() {
  if (WiFi.status() != WL_CONNECTED) return;

  StaticJsonDocument<384> doc;
  doc["level_inches"] = round(levelInches * 10) / 10.0;
  doc["loop_mA"]      = round(loopMA * 100) / 100.0;
  doc["pump_on"]      = pumpOn;
  doc["alarm"]        = alarmActive;
  doc["sensor_fault"] = sensorFault;
  doc["float_low"]    = floatTripped(PIN_FLOAT_LOW);
  doc["float_ctrl"]   = floatTripped(PIN_FLOAT_CTRL);
  doc["float_high"]   = floatTripped(PIN_FLOAT_HIGH);
  doc["uptime_s"]     = millis() / 1000;

  String body;
  serializeJson(doc, body);

  HTTPClient http;
  http.begin(MONITOR_URL);
  http.addHeader("Content-Type", "application/json");
  if (strlen(MONITOR_TOKEN) > 0)
    http.addHeader("Authorization", String("Bearer ") + MONITOR_TOKEN);
  int code = http.POST(body);
  Serial.printf("[POST] %d  %s\n", code, body.c_str());
  http.end();
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[WiFi] connecting");
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
    delay(500); Serial.print(".");
  }
  Serial.println(WiFi.status() == WL_CONNECTED
                 ? "\n[WiFi] connected: " + WiFi.localIP().toString()
                 : "\n[WiFi] FAILED (will retry; control still runs locally)");
}

void setup() {
  Serial.begin(115200);
  delay(200);

  pinMode(PIN_FLOAT_LOW,  INPUT_PULLUP);
  pinMode(PIN_FLOAT_CTRL, INPUT_PULLUP);
  pinMode(PIN_FLOAT_HIGH, INPUT_PULLUP);
  pinMode(PIN_PUMP_RELAY, OUTPUT);
  pinMode(PIN_BUZZER,     OUTPUT);
  pinMode(PIN_LED_RUN,    OUTPUT);
  pinMode(PIN_LED_ALARM,  OUTPUT);
  digitalWrite(PIN_PUMP_RELAY, LOW);    // pump OFF on boot

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  if (!ads.begin()) Serial.println("[ADS1115] not found — sensor will read as fault");
  ads.setGain(1);                       // +/-4.096 V range fits 0.66-3.30 V loop signal

  pumpStoppedAt = millis();
  connectWiFi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();

  readLevel();
  controlLogic();

  if (millis() - lastPostAt >= POST_INTERVAL_MS) {
    publishStatus();
    lastPostAt = millis();
  }
  delay(250);
}
