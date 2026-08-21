#!/usr/bin/env python3
"""Update only Pense Bem's API URL in device NVS over USB serial."""

from __future__ import annotations

import argparse
import sys
import time

import serial

from push import _drain, _interrupt, _paste


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()

    encoded = args.url.rstrip("/").encode("utf-8")
    if len(encoded) > 96 or not encoded.startswith((b"http://", b"https://")):
        print("API URL must be http(s) and at most 96 UTF-8 bytes.", file=sys.stderr)
        return 2

    script = "\n".join(
        (
            "import esp32",
            "nvs = esp32.NVS('pensebem')",
            "nvs.set_blob('api_url', {!r})".format(encoded),
            "nvs.commit()",
            "print('PENSE_BEM_API_OK')",
        )
    )

    device = serial.Serial(args.port, 115200, timeout=1.0)
    try:
        # This is an intentional REPL transaction, not a boot/reset probe.
        # Do not toggle native-USB DTR/RTS or erase the existing Wi-Fi blobs.
        time.sleep(0.3)
        _interrupt(device)
        _drain(device, wait=0.2)
        output = _paste(device, script, settle=0.8)
        if "PENSE_BEM_API_OK" not in output or "Traceback" in output:
            print("Device rejected the API URL update.", file=sys.stderr)
            return 1
        print("Pense Bem API URL updated; Wi-Fi settings preserved.")
        try:
            _paste(device, "import machine\nmachine.reset()", settle=0.1)
        except (OSError, serial.SerialException):
            pass
    finally:
        device.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
