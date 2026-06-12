# Wiring & Safety

> ⚠️ This panel switches **120 V / 30 A**. Mains wiring should be done or verified
> by a licensed electrician. Septic wet wells can contain **explosive gas (methane)
> and toxic H₂S** — keep all electronics out of the gas space and seal every
> conduit/cable entry. Confirm whether your wet well is a classified (hazardous)
> location; if so, intrinsically-safe barriers may be required by code.

## Block diagram

```
                          120 VAC service
                               │
              ┌────────────────┼──────────────┐
              │                │               │
        30 A breaker      5 V DIN PSU      (panel power)
         + GFCI                │
              │                ▼
        ┌──────────┐        ESP32 ───┬── I²C ──► ADS1115 ──► 4–20 mA loop ──► submersible level Tx
        │CONTACTOR │◄── coil          ├── GPIO ──► relay module ──► contactor coil
        │  ≥40 A   │                  ├── GPIO ◄── Float 1 (low / OFF)
        └────┬─────┘                  ├── GPIO ◄── Float 2 (control / ON)
             │                        ├── GPIO ◄── Float 3 (HIGH ALARM)
          PUMP (120V/30A)             ├── GPIO ──► buzzer + LEDs
                                      └── WiFi ──► monitoring endpoint (JSON)
```

The ESP32 only drives the **contactor coil** through an opto-isolated relay. The
30 A motor current flows through the contactor — never through the ESP32 or relay.

## ESP32 pin map (matches `config.h.example`)

| Signal | ESP32 pin | Notes |
|--------|-----------|-------|
| I²C SDA (ADS1115) | GPIO 21 | |
| I²C SCL (ADS1115) | GPIO 22 | |
| Float 1 (low/OFF) | GPIO 32 | `INPUT_PULLUP`, switch to GND |
| Float 2 (control) | GPIO 33 | `INPUT_PULLUP`, switch to GND |
| Float 3 (high alarm) | GPIO 25 | `INPUT_PULLUP`, switch to GND |
| Pump relay (→ contactor coil) | GPIO 26 | drives opto-relay |
| Alarm buzzer | GPIO 27 | |
| Run LED | GPIO 14 | |
| Alarm LED | GPIO 12 | |

Floats are dry contacts: one leg to the GPIO, other leg to GND. With
`INPUT_PULLUP`, a closed (tripped) float reads LOW. The firmware's
`FLOAT_ACTIVE_LOW` flag handles either float polarity.

## 4–20 mA level loop scaling

The transmitter is a 2-wire 4–20 mA current loop. Put a **165 Ω** sense resistor
across the ADS1115 input to GND:

```
loop+ (24V) ── transmitter ── loop signal ──┬── ADS1115 A0
                                            165 Ω
                                             │
                                            GND
```

- Voltage at A0 = loop_mA × 165 Ω = **0.66 V (4 mA) … 3.30 V (20 mA)** — within ADS1115 range.
- mA = V / 165
- **depth_inches = (mA − 4) / 16 × LEVEL_RANGE_IN**

Set `LEVEL_RANGE_IN` to your transmitter's full-scale range in inches (e.g. 60 for
a 5 ft sensor). Use `SENSE_OHMS` if you choose a different resistor. Do a two-point
calibration (empty well + known depth) and adjust `LEVEL_RANGE_IN` so the serial
readout matches a tape measure.

## Control thresholds

Set in `config.h`:
- `LEVEL_ON_IN` — pump turns ON above this depth.
- `LEVEL_OFF_IN` — pump turns OFF below this depth (must be < `LEVEL_ON_IN` for hysteresis).
- `MIN_OFF_SECONDS` — anti short-cycle; pump won't restart until elapsed.
- `MAX_RUN_SECONDS` — runtime watchdog; exceeding it raises an alarm (possible dry pump / failed sensor).

## Fail-safe behavior

1. **Float 3 (high) tripped** → alarm + force pump ON + remote alert, regardless of analog reading.
2. **Analog level invalid** (out of 3.5–20.5 mA band, i.e. open/short loop) → fall back to **float-only** control (Float 2 ON, Float 1 OFF) and flag a sensor fault.
3. **Float 1 (low) tripped** → pump OFF (dry-run protection) wins over level/Float 2.
4. **Pump runs longer than `MAX_RUN_SECONDS`** → alarm.
