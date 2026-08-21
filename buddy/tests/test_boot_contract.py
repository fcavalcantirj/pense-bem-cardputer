#!/usr/bin/env python3
"""Regression checks for the dedicated UIFlow Pense Bem fallback boot."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    installer = (ROOT / ".claude/skills/m5-onboard/scripts/install_apps.py").read_text()
    pusher = (ROOT / "buddy/scripts/push.py").read_text()
    configurator = (ROOT / "buddy/scripts/configure_pense_bem.py").read_text()
    entrypoint = (ROOT / "buddy/device/main.py").read_text()

    assert "nvs.set_u8('boot_option', 0)" in installer
    assert "nvs.set_u8('boot_option', 2)" not in installer
    assert "nvs.set_u8('boot_option', 0)" in pusher
    assert "boot_nvs.set_u8('boot_option', 0)" in configurator

    tree = ast.parse(entrypoint)
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imported == {"sys", "pense_bem"}
    assert '"/flash/apps"' in entrypoint

    print("UIFlow dedicated Pense Bem boot contract: ok")


if __name__ == "__main__":
    main()
