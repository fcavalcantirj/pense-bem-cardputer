#!/usr/bin/env python3
"""Store Pense Bem Wi-Fi/API settings in device NVS without logging secrets."""

from __future__ import annotations

import argparse
import getpass
import sys
import time

import serial

from push import _drain, _hard_reset, _interrupt, _paste


def _prompt_bytes(label: str, capacity: int, *, secret: bool = False) -> bytes:
    while True:
        value = getpass.getpass(label) if secret else input(label)
        encoded = value.encode("utf-8")
        if len(encoded) <= capacity and (value or secret):
            return encoded
        print(f"Use 1-{capacity} UTF-8 bytes.", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure Pense Bem Wi-Fi and LAN API settings in device NVS."
    )
    parser.add_argument("--port", required=True)
    args = parser.parse_args()

    ssid = _prompt_bytes("Wi-Fi SSID (hidden): ", 32, secret=True)
    password = _prompt_bytes("Wi-Fi password (hidden): ", 64, secret=True)
    while True:
        api_url = _prompt_bytes("API URL (for example http://192.168.1.5:18080): ", 96)
        if api_url.startswith((b"http://", b"https://")):
            api_url = api_url.rstrip(b"/")
            break
        print("API URL must begin with http:// or https://.", file=sys.stderr)

    # Values exist only in this process and the serial stream. `_paste` returns
    # the echoed script, but we intentionally never display that buffer.
    script = "\n".join(
        (
            "import esp32",
            "nvs = esp32.NVS('pensebem')",
            "nvs.set_blob('wifi_ssid', {!r})".format(ssid),
            "nvs.set_blob('wifi_pass', {!r})".format(password),
            "nvs.set_blob('api_url', {!r})".format(api_url),
            "nvs.commit()",
            "boot_nvs = esp32.NVS('uiflow')",
            "boot_nvs.set_u8('boot_option', 0)",
            "boot_nvs.commit()",
            "print('PENSE_BEM_CONFIG_OK')",
        )
    )

    device = serial.Serial(args.port, 115200, timeout=1.0)
    try:
        _hard_reset(device)
        time.sleep(2.0)
        _interrupt(device)
        _drain(device, wait=0.2)
        output = _paste(device, script, settle=0.8)
        if "PENSE_BEM_CONFIG_OK" not in output or "Traceback" in output:
            print("Device rejected the NVS configuration.", file=sys.stderr)
            return 1
        print("Pense Bem Wi-Fi/API settings saved to device NVS.")
        # A DTR/RTS reset is unreliable on Cardputer-Adv native USB and can
        # leave the launcher image frozen while the device is still at `>>>`.
        # Ask MicroPython itself to reset; losing the serial port here is the
        # expected success path.
        try:
            _paste(device, "import machine\nmachine.reset()", settle=0.1)
        except (OSError, serial.SerialException):
            pass
    finally:
        device.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
