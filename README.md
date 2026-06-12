# Septic Lift Station Monitor & Pump Controller

An ESP32-based controller for a septic effluent **lift station** that pumps up to
field lines. It provides:

- **True liquid level in inches** via a submersible (vented) pressure level transmitter
- **3 redundant float switches** as fail-safe control + high-level alarm
- **Pump control** of a 120 V / 30 A pump through a properly sized contactor
- **Remote monitoring over WiFi** (level, pump state, float states, alarms)

> ⚠️ **Safety first.** This drives a 3 HP mains pump in a corrosive, potentially
> explosive (H₂S / methane) environment near sewage. Read [`docs/WIRING.md`](docs/WIRING.md)
> before wiring anything. Have a licensed electrician verify the line side. The
> ESP32 **never** switches the pump motor directly — a contactor does.

## How level + floats work together

The pressure transmitter gives you the real elevation (inches). The 3 floats are
independent, mechanical, and keep working even if the ESP32 or the analog sensor
fails:

| Element            | Role                                                  |
|--------------------|-------------------------------------------------------|
| Pressure transmitter | Continuous elevation in inches (primary readout)     |
| Float 1 (low)      | Dry-run protection — pump OFF                          |
| Float 2 (control)  | Backup pump-ON trigger if analog level is lost         |
| Float 3 (high)     | Independent HIGH-LEVEL ALARM (overflow protection)     |

Control normally runs off the inches value with hysteresis (ON at `LEVEL_ON_IN`,
OFF at `LEVEL_OFF_IN`). If the analog sensor reads invalid, the firmware falls
back to float-only control. Float 3 forces an alarm + pump-on regardless.

## Repo layout

```
docs/PARTS.md                            Bill of materials with model numbers
docs/WIRING.md                           Wiring + safety, pinout, sensor scaling math
src/septic_lift_monitor/                 ESP32 firmware (Arduino sketch folder)
src/septic_lift_monitor/config.h.example Copy to config.h; secrets/calibration
homeassistant/                           HA package + Lovelace dashboard card
.github/workflows/build.yml              CI: compiles the sketch on every push
```

## Quick start

1. Build the panel per `docs/WIRING.md`.
2. `cp src/septic_lift_monitor/config.h.example src/septic_lift_monitor/config.h`
   and fill in WiFi + calibration + endpoint.
3. Flash `src/septic_lift_monitor/septic_lift_monitor.ino` with the Arduino IDE /
   arduino-cli (board: *ESP32 Dev Module*; libs: `ADS1X15`, `ArduinoJson`).
4. Watch the serial monitor for calibration, then mount and test with the
   floats before trusting the analog level.

## Remote monitoring / deployment note

The firmware POSTs status as JSON to whatever endpoint you configure — point it
at Home Assistant, ThingsBoard, or a small cloud service. **Secrets (WiFi
password, endpoint token) live in `config.h`, which is git-ignored — never
hard-code them into committed source.**

If this monitoring service grows into a deployed/production app, Nucor's internal
architecture guidance can help you do hosting, authentication, and secrets the
approved way. Ask and I'll pull it in.
