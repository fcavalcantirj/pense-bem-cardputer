#!/usr/bin/env python3
"""Probe Cardputer HTTPS heap after releasing the launcher's BLE stack."""

from __future__ import annotations

import argparse
import time

import serial

from push import _drain, _interrupt, _paste


DEVICE_SCRIPT = r'''
import bluetooth
import esp32
import gc
import network
import requests2
import time

def pbprobe_heap(label):
    gc.collect()
    print('PBPROBE MP_HEAP_' + label, gc.mem_free())
    try:
        print('PBPROBE IDF_HEAP_' + label, esp32.idf_heap_info(esp32.HEAP_DATA))
    except Exception as exc:
        print('PBPROBE IDF_HEAP_ERROR_' + label, repr(exc))

def pbprobe_blob(key, cap):
    data = bytearray(cap)
    size = esp32.NVS('pensebem').get_blob(key, data)
    return bytes(data[:size]).decode('utf-8')

ssid = pbprobe_blob('wifi_ssid', 32)
password = pbprobe_blob('wifi_pass', 64)
api_url = pbprobe_blob('api_url', 96).rstrip('/')

ble = bluetooth.BLE()
gc.collect()
print('PBPROBE BLE_ACTIVE', ble.active())
pbprobe_heap('BEFORE_BLE_OFF')
ble.active(False)
del ble
pbprobe_heap('AFTER_BLE_OFF')

sta = network.WLAN(network.STA_IF)
if not sta.active():
    sta.active(True)
try:
    sta.disconnect()
except Exception:
    pass
time.sleep_ms(500)
sta.connect(ssid, password)
started = time.ticks_ms()
while not sta.isconnected() and time.ticks_diff(time.ticks_ms(), started) < 15000:
    time.sleep_ms(100)
print('PBPROBE WIFI', sta.isconnected())
if sta.isconnected():
    pbprobe_heap('AFTER_WIFI')
    try:
        response = requests2.post(
            api_url + '/api/v2/atari/sessions',
            json={'code': '991', 'client': 'atari8', 'protocol': 1},
            headers={'Content-Type': 'application/json'},
        )
        print('PBPROBE POST_STATUS', response.status_code)
        print('PBPROBE POST_BYTES', len(response.content))
        pbprobe_heap('AFTER_POST')
        try:
            response.close()
        except Exception:
            pass
    except Exception as exc:
        print('PBPROBE POST_ERROR', repr(exc))
        pbprobe_heap('AFTER_POST_ERROR')
print('PBPROBE DONE')
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    args = parser.parse_args()

    device = serial.Serial(args.port, 115200, timeout=1.0)
    try:
        time.sleep(0.3)
        _interrupt(device)
        _drain(device, wait=0.2)
        output = _paste(device, DEVICE_SCRIPT, settle=20.0)
        lines = [line for line in output.splitlines() if "PBPROBE" in line]
        print("\n".join(lines))
        post_ok = any("PBPROBE POST_STATUS 201" in line for line in lines)
        return 0 if post_ok else 1
    finally:
        try:
            _paste(device, "import machine\nmachine.reset()", settle=0.1)
        except (OSError, serial.SerialException):
            pass
        device.close()


if __name__ == "__main__":
    raise SystemExit(main())
