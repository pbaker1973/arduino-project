# Bill of Materials

Tailored to: **WiFi at the tank · 120 V / 30 A pump · continuous elevation in inches · 3 floats.**

Model numbers are representative starting points — confirm voltage/amp ratings and
local plumbing/electrical code before buying.

## Controller & monitoring
| Qty | Item | Example / notes |
|----|------|-----------------|
| 1 | ESP32 dev board | ESP32-WROOM-32 DevKitC. WiFi reaches the tank, so no cellular needed. |
| 1 | 16-bit ADC | Adafruit ADS1115 (I²C) — reads the 4–20 mA loop cleanly; ESP32's own ADC is too noisy. |
| 1 | RTC (optional) | DS3231 — timestamps events if WiFi drops. |
| 1 | 5 V DIN-rail PSU | Mean Well HDR-15-5 (or quality USB adapter) for the ESP32. **Separate from pump circuit.** |

## Continuous level sensor (the "inches")
| Qty | Item | Notes |
|----|------|-------|
| 1 | Submersible **vented** level transmitter, 4–20 mA, sewage-rated | e.g. 0–5 ft (≈60 in) range, PVDF/316SS, vented cable so readings track true depth regardless of barometric pressure. Pick a range that covers your wet-well depth. |
| 1 | 165 Ω precision resistor (0.1%) | Converts 4–20 mA → 0.66–3.30 V for the ADS1115. (Or a dedicated 4–20 mA receiver module.) |

> Scaling: depth_in = (mA − 4) / 16 × RANGE_IN. With 165 Ω, voltage = mA × 0.165.
> Calibration constants live in `config.h`.

## Float switches (sewage-rated — required)
| Qty | Item | Role |
|----|------|------|
| 3 | Mechanical float switch rated for **septic/sewage** (wide-angle tethered) | Float 1 = low/OFF (dry-run), Float 2 = control/ON backup, Float 3 = high alarm. |
| 3 | 10 kΩ resistors | Pull-ups for the float GPIO inputs. |
| 1 | 4-channel opto-isolated input module (optional) | Extra isolation between floats and ESP32. |

## Pump switching (120 V / 30 A — sized properly)
| Qty | Item | Notes |
|----|------|-------|
| 1 | **Definite-purpose contactor, ≥40 A, 120 V coil** | e.g. 2-pole 40 A DP contactor. The 30 A motor must be switched by a contactor, **not** a hobby relay. |
| 1 | Opto-isolated relay module (1-ch, 5 V coil drive) | ESP32 GPIO → relay → contactor coil. |
| 1 | Flyback diode / RC snubber | Across the contactor coil. |
| 1 | 30 A motor-rated breaker **or** fuses | Per pump nameplate + code. |
| 1 | GFCI protection (30 A) | Wet location — required. |

## Enclosure, gas & corrosion protection (septic-specific)
| Qty | Item | Notes |
|----|------|-------|
| 1 | **NEMA 4X** polycarbonate/fiberglass enclosure | Mount **away from / above** the wet well, never over the gas space. |
| — | Cable glands + **conduit sealing fittings** | Septic gas migrates up cables and corrodes electronics — seal every entry. |
| 1 | Surge protector on sensor/float runs | Long outdoor runs. |
| — | DIN rail, terminal blocks, ferrules, wire | Panel build-out. |

## Local indication / alerting
| Qty | Item | Notes |
|----|------|-------|
| 3 | Status LEDs (+ resistors) | Power / pump-run / alarm. |
| 1 | Piezo buzzer | Local high-level alarm. |
| — | Remote alerts | Via the monitoring endpoint (push/email/SMS) — especially the high-level alarm. |

## Required Arduino libraries
- `ADS1X15` (level ADC)
- `ArduinoJson` (status payload)
- `WiFi` / `HTTPClient` (built into ESP32 core)
