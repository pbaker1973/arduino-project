#!/usr/bin/env python3
"""Septic Lift Station Monitor & Pump Controller (Raspberry Pi).

Same behavior as the ESP32 firmware:
  - Continuous level in inches from a 4-20 mA submersible transmitter (via ADS1115)
  - 3 redundant sewage-rated float switches (low / control / high-alarm)
  - Pump control via opto relay -> contactor (120 V / 30 A pump)
  - Remote monitoring: POSTs JSON status over the network

Wiring matches docs/WIRING.md (BCM pin numbers below). The Pi NEVER switches the
pump motor directly -- a GPIO drives an opto relay that drives the contactor coil.

Setup:
    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    cp config.example.py config.py   # then edit config.py (git-ignored)
    python3 septic_monitor.py

Enable I2C via raspi-config for the ADS1115.
"""

import logging
import time

import requests
import board
import busio
from gpiozero import Button, OutputDevice
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

import config as C

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("septic")


class SepticController:
    def __init__(self):
        # Floats: dry contacts to GND. pull_up=True -> pressed/tripped == is_pressed.
        self.float_low = Button(C.PIN_FLOAT_LOW, pull_up=True)
        self.float_ctrl = Button(C.PIN_FLOAT_CTRL, pull_up=True)
        self.float_high = Button(C.PIN_FLOAT_HIGH, pull_up=True)

        self.pump = OutputDevice(C.PIN_PUMP_RELAY, active_high=True, initial_value=False)
        self.led_run = OutputDevice(C.PIN_LED_RUN, initial_value=False)
        self.led_alarm = OutputDevice(C.PIN_LED_ALARM, initial_value=False)
        self.buzzer = OutputDevice(C.PIN_BUZZER, initial_value=False)

        # ADS1115 on I2C for the 4-20 mA loop.
        i2c = busio.I2C(board.SCL, board.SDA)
        self.ads = ADS.ADS1115(i2c)
        self.ads.gain = 1  # +/-4.096 V, fits the 0.66-3.30 V loop signal
        self.level_chan = AnalogIn(self.ads, getattr(ADS, f"P{C.ADS_CHANNEL}"))

        self.pump_on = False
        self.alarm = False
        self.sensor_fault = False
        self.level_in = 0.0
        self.loop_ma = 0.0
        self.pump_started = 0.0
        self.pump_stopped = time.monotonic()
        self.last_post = 0.0

    # ---- float helper (handles either polarity) ----
    def tripped(self, btn: Button) -> bool:
        return btn.is_pressed if C.FLOAT_ACTIVE_LOW else not btn.is_pressed

    # ---- pump / alarm actuation ----
    def set_pump(self, on: bool):
        if on == self.pump_on:
            return
        self.pump_on = on
        self.pump.value = on
        self.led_run.value = on
        now = time.monotonic()
        if on:
            self.pump_started = now
        else:
            self.pump_stopped = now
        log.info("PUMP %s", "ON" if on else "OFF")

    def set_alarm(self, on: bool):
        self.alarm = on
        self.led_alarm.value = on
        self.buzzer.value = on

    # ---- read 4-20 mA loop -> inches ----
    def read_level(self):
        volts = self.level_chan.voltage
        self.loop_ma = (volts / C.SENSE_OHMS) * 1000.0
        if not (C.LOOP_VALID_MIN_MA <= self.loop_ma <= C.LOOP_VALID_MAX_MA):
            self.sensor_fault = True  # open/short loop -> trust floats
            return
        self.sensor_fault = False
        frac = (self.loop_ma - C.LOOP_MIN_MA) / (C.LOOP_MAX_MA - C.LOOP_MIN_MA)
        frac = max(0.0, frac)
        self.level_in = frac * C.LEVEL_RANGE_IN

    # ---- control logic: high-alarm > dry-run > level/float ----
    def control(self):
        f_low = self.tripped(self.float_low)
        f_ctrl = self.tripped(self.float_ctrl)
        f_high = self.tripped(self.float_high)

        # 1) High-level alarm: independent overflow protection.
        if f_high:
            self.set_alarm(True)
            self.set_pump(True)
            return

        now = time.monotonic()
        off_long_enough = (now - self.pump_stopped) >= C.MIN_OFF_SECONDS

        if self.sensor_fault:
            # 3) Analog lost -> float-only control.
            want_on = f_ctrl and not f_low
        else:
            # 4) Normal hysteresis on inches.
            want_on = (self.level_in > C.LEVEL_OFF_IN) if self.pump_on \
                else (self.level_in >= C.LEVEL_ON_IN)

        if f_low:  # 2) dry-run protection always wins
            want_on = False

        if want_on and not self.pump_on and off_long_enough:
            self.set_pump(True)
        elif not want_on and self.pump_on:
            self.set_pump(False)

        # 5) Runtime watchdog.
        if self.pump_on and (now - self.pump_started) >= C.MAX_RUN_SECONDS:
            self.set_alarm(True)
        elif not f_high and not self.sensor_fault:
            self.set_alarm(False)

    # ---- publish status ----
    def publish(self):
        payload = {
            "level_inches": round(self.level_in, 1),
            "loop_mA": round(self.loop_ma, 2),
            "pump_on": self.pump_on,
            "alarm": self.alarm,
            "sensor_fault": self.sensor_fault,
            "float_low": self.tripped(self.float_low),
            "float_ctrl": self.tripped(self.float_ctrl),
            "float_high": self.tripped(self.float_high),
            "uptime_s": int(time.monotonic()),
        }
        headers = {"Content-Type": "application/json"}
        if C.MONITOR_TOKEN:
            headers["Authorization"] = f"Bearer {C.MONITOR_TOKEN}"
        try:
            r = requests.post(C.MONITOR_URL, json=payload, headers=headers, timeout=5)
            log.info("POST %s %s", r.status_code, payload)
        except requests.RequestException as e:
            log.warning("POST failed (control still runs locally): %s", e)

    def run(self):
        log.info("Septic monitor starting")
        try:
            while True:
                self.read_level()
                self.control()
                now = time.monotonic()
                if now - self.last_post >= C.POST_INTERVAL_S:
                    self.publish()
                    self.last_post = now
                time.sleep(0.25)
        except KeyboardInterrupt:
            log.info("Shutting down; pump OFF")
        finally:
            self.set_pump(False)
            self.set_alarm(False)


if __name__ == "__main__":
    SepticController().run()
