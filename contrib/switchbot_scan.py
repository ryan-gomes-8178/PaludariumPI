#!/usr/bin/env python3
"""List SwitchBot Bluetooth LE advertisements and decode Indoor/Outdoor Thermo-Hygrometer readings.

Use it to discover meters, match MAC addresses to physical devices, compare readings with the
SwitchBot app, and capture raw data for troubleshooting. Works completely offline.

Run from the TerrariumPI directory with its virtual environment:

  venv/bin/python contrib/switchbot_scan.py                 # 20 second scan, table output
  venv/bin/python contrib/switchbot_scan.py --duration 60   # longer scan
  venv/bin/python contrib/switchbot_scan.py --json          # raw + decoded data as JSON
  venv/bin/python contrib/switchbot_scan.py --active        # active scan (requests scan responses)
"""
import argparse
import json
import logging
import sys
import time
import types
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Use plain logging. The TerrariumPI logging setup writes to the live log files and sends notifications.
terrariumLogging = types.ModuleType("terrariumLogging")
terrariumLogging.logging = logging
sys.modules.setdefault("terrariumLogging", terrariumLogging)

from bluepy.btle import Scanner, BTLEException  # noqa: E402
from hardware.sensor.switchbot_ble import (  # noqa: E402
    decode_io_meter,
    helper_path,
    is_switchbot_advert,
    model_from_service_data,
    SwitchBotDecodeError,
)


def scan(hci, duration, passive):
    """Scan in 1 second steps. Restart the bluepy helper when it dies, for example when the running
    TerrariumPI engine cleans up bluepy helper processes."""
    devices = {}
    start = time.time()
    scanner = None
    while time.time() - start < duration:
        try:
            if scanner is None:
                scanner = Scanner(hci)
                scanner.clear()
                scanner.start(passive=passive)

            scanner.process(1.0)
            for device in scanner.getDevices():
                devices[device.addr] = device

        except (BTLEException, OSError) as ex:
            if "permission" in f"{getattr(ex, 'emsg', '')} {ex}".lower():
                raise
            print(f"Bluetooth helper stopped ({ex!r}), restarting scan ...", file=sys.stderr)
            scanner = None
            time.sleep(1)

    if scanner is not None:
        try:
            scanner.stop()
        except Exception:
            pass

    return list(devices.values())


def main():
    parser = argparse.ArgumentParser(description="Scan for SwitchBot BLE thermo-hygrometers")
    parser.add_argument("--duration", type=float, default=20, help="scan time in seconds (default 20)")
    parser.add_argument("--hci", type=int, default=0, help="Bluetooth adapter number (default 0 = hci0)")
    parser.add_argument("--active", action="store_true", help="use active scanning")
    parser.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args()

    if not args.json:
        print(f"Scanning hci{args.hci} for {args.duration:.0f} seconds ...")

    try:
        devices = scan(args.hci, args.duration, not args.active)
    except BTLEException as ex:
        print(f"Bluetooth scan failed: {ex}", file=sys.stderr)
        if "permission" in f"{getattr(ex, 'emsg', '')} {ex}".lower():
            print(
                f"Fix: sudo setcap 'cap_net_raw,cap_net_admin+eip' {helper_path()}",
                file=sys.stderr,
            )
        return 2

    captured_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for device in devices:
        mfr = device.getValueText(255)
        svc = device.getValueText(22)
        if not is_switchbot_advert(mfr, svc):
            continue

        row = {
            "mac": device.addr,
            "rssi": device.rssi,
            "manufacturer_data": mfr,
            "service_data": svc,
            "model": model_from_service_data(svc),
            "captured_at": captured_at,
        }
        try:
            row["decoded"] = decode_io_meter(device.addr, mfr, svc)
        except SwitchBotDecodeError as ex:
            row["rejected"] = str(ex)

        rows.append(row)

    rows.sort(key=lambda row: row["mac"])

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(f"Found {len(rows)} SwitchBot devices ({len(devices)} Bluetooth devices total)\n")
        print(f"{'MAC address':<19}{'RSSI':>6}{'Temp C':>9}{'Hum %':>7}  Status")
        for row in rows:
            if "decoded" in row:
                data = row["decoded"]
                status = "OK" + (" (app shows Fahrenheit)" if data["fahrenheit_display"] else "")
                print(f"{row['mac']:<19}{row['rssi']:>6}{data['temperature_c']:>9.1f}{data['humidity_pct']:>7}  {status}")
            else:
                print(f"{row['mac']:<19}{row['rssi']:>6}{'-':>9}{'-':>7}  rejected: {row['rejected']}")
            print(f"{'':<19}raw mfr={row['manufacturer_data']} svc={row['service_data'] or '-'}")

    return 0 if any("decoded" in row for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
