"""Dedicated Cardputer-Adv boot entrypoint for Pense Bem.

UIFlow must use ``uiflow.boot_option=0`` so boot.py returns directly here.
This entrypoint deliberately imports no launcher animation, Wi-Fi helper, or
Bluetooth module. In particular, NimBLE must never be activated: on UIFlow
2.5.1 deactivating BLE does not return its native ESP-IDF heap blocks, and
requests2/mbedTLS then fails HTTPS with ``OSError(12)``.
"""

import sys


for _path in ("/flash", "/flash/apps"):
    if _path not in sys.path:
        sys.path.insert(0, _path)


# pense_bem.py owns hardware initialization, keyboard settling, game mode,
# Wi-Fi, error presentation, and the reset lifecycle. Importing it runs run().
import pense_bem  # noqa: F401,E402
