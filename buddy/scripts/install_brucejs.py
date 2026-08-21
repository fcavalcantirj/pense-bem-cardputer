#!/usr/bin/env python3
"""Install a BruceJS app over Bruce's USB serial CLI and verify its MD5."""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import time

import serial


def read_until(device: serial.Serial, marker: str, timeout: float = 8.0) -> str:
    deadline = time.monotonic() + timeout
    chunks: list[bytes] = []
    wanted = marker.encode()
    while time.monotonic() < deadline:
        chunk = device.read(device.in_waiting or 1)
        if chunk:
            chunks.append(chunk)
            if wanted in b"".join(chunks):
                return b"".join(chunks).decode("utf-8", "replace")
        else:
            time.sleep(0.02)
    output = b"".join(chunks).decode("utf-8", "replace")
    raise TimeoutError(f"Bruce CLI did not emit {marker!r}:\n{output}")


def command(device: serial.Serial, value: str, marker: str = "# ") -> str:
    device.write(value.encode() + b"\n")
    device.flush()
    return read_until(device, marker)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--source", required=True, type=pathlib.Path)
    parser.add_argument("--dest", default="/BruceJS/Games/PenseBem.js")
    parser.add_argument("--run", action="store_true", help="Launch the app after verification.")
    args = parser.parse_args()

    payload = args.source.read_bytes()
    if not payload.endswith(b"\n"):
        payload += b"\n"
    if b"\nEOF\n" in payload or payload.startswith(b"EOF\n"):
        raise ValueError("source contains Bruce CLI's reserved EOF line")

    expected_md5 = hashlib.md5(payload, usedforsecurity=False).hexdigest()
    parent = str(pathlib.PurePosixPath(args.dest).parent)

    with serial.Serial(args.port, 115200, timeout=0.2) as device:
        time.sleep(1.0)
        device.reset_input_buffer()
        device.write(b"\n")
        try:
            read_until(device, "# ", timeout=3.0)
        except TimeoutError:
            pass

        current = ""
        for part in pathlib.PurePosixPath(parent).parts[1:]:
            current += "/" + part
            command(device, f"storage mkdir {current}")

        device.write(f"storage write {args.dest} {len(payload)}\n".encode())
        device.flush()
        read_until(device, "Reading input data from serial buffer until EOF")
        # Bruce's USB serial RX buffer is deliberately small.  A single large
        # write can overrun it while _readFileFromSerial() processes lines,
        # and Bruce still reports "File written" for the truncated prefix.
        # Pace small chunks so the receiver can drain its buffer. Minified JS
        # can be one long line, so line-level pacing alone is not sufficient.
        # The stat check below makes any loss a hard failure.
        for line in payload.splitlines(keepends=True):
            for offset in range(0, len(line), 128):
                device.write(line[offset : offset + 128])
                device.flush()
                time.sleep(0.01)
        device.write(b"EOF\n")
        device.flush()
        written = read_until(device, "# ", timeout=15.0)
        if "File written:" not in written:
            raise RuntimeError(f"Bruce did not confirm the write:\n{written}")

        stat = command(device, f"storage stat {args.dest}")
        size_match = re.search(r"Size:\s*(\d+)", stat)
        if not size_match:
            raise RuntimeError(f"Bruce did not report the installed file size:\n{stat}")
        remote_size = int(size_match.group(1))
        if remote_size != len(payload):
            raise RuntimeError(
                f"Bruce file size mismatch: expected {len(payload)}, got {remote_size}\n{stat}"
            )

        # Bruce 1.16.1 implements storage md5 through readSmallFile(), whose
        # SAFE_STACK_BUFFER_SIZE limit is 4096 bytes on ESP32-S3.  Asking it to
        # hash a larger file blocks the UI on a "File is too big" dialog.  The
        # serial writer already receives an exact byte count, so verify that
        # count through storage stat and reserve MD5 for files Bruce can hash.
        if len(payload) <= 4096:
            verified = command(device, f"storage md5 {args.dest}")
            if expected_md5.lower() not in verified.lower():
                raise RuntimeError(
                    f"Bruce MD5 mismatch: expected {expected_md5}\n{verified}"
                )
            verification = f"md5 {expected_md5}"
        else:
            verification = "remote size verified; Bruce MD5 limit is 4096 bytes"

        print(f"installed {args.dest} ({len(payload)} bytes, {verification})")

        if args.run:
            device.write(f"js run_from_file {args.dest}\n".encode())
            device.flush()
            print("launch requested")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
