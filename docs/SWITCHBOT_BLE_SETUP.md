# SwitchBot Indoor/Outdoor Thermo-Hygrometer (Bluetooth LE) setup

This guide shows how to use SwitchBot Indoor/Outdoor Thermo-Hygrometers (model W3400010)
as TerrariumPI temperature and humidity sensors. Everything runs locally on the Raspberry Pi
through its built-in Bluetooth. No Home Assistant, SwitchBot cloud, SwitchBot Hub or internet
connection is needed.

## How it works

- The meter broadcasts temperature and humidity in Bluetooth LE advertisements every few seconds.
  TerrariumPI listens with a short passive scan. It does not connect or pair, and the meter's
  battery life is not affected.
- One scan reads every meter in range. The temperature and humidity sensors of the same meter
  share that data. With all meters in range, the update loop does one scan of about 4 seconds every
  30 seconds.
- A reading is only used while it is fresh: at most 180 seconds old by default. When a meter stops
  advertising, TerrariumPI stops recording values for it. It never records zero or an old value.
  After 5 minutes without data the sensor shows an error. If every sensor of an area is in error,
  that area switches its relays off (see [Safety](#safety)).
- Code: `hardware/sensor/switchbot_sensor.py` (driver) and `hardware/sensor/switchbot_ble.py`
  (decoder and shared scanner). Diagnostic tool: `contrib/switchbot_scan.py`.

Run all commands below from the TerrariumPI directory, for example `cd ~/Desktop/TerrariumPI`.

## 1. Bluetooth on the Raspberry Pi

Check that the built-in adapter is up:

```sh
hcitool dev                       # should list: hci0  XX:XX:XX:XX:XX:XX
systemctl is-active bluetooth     # should print: active
```

If `hci0` is missing:

```sh
sudo systemctl enable --now bluetooth
sudo hciconfig hci0 up
grep -n "dtoverlay=disable-bt" /boot/config.txt   # must NOT be present (Bookworm: /boot/firmware/config.txt)
```

The user that runs TerrariumPI must be in the `bluetooth` group (`install.sh` does this):

```sh
id -nG | grep -w bluetooth || sudo usermod -a -G bluetooth "$USER"
```

## 2. Bluetooth permission for the scanner (important)

TerrariumPI scans through the `bluepy-helper` program. This program needs two Linux capabilities
to scan without running as root:

```sh
sudo setcap 'cap_net_raw,cap_net_admin+eip' venv/lib/python3*/site-packages/bluepy/bluepy-helper
/sbin/getcap venv/lib/python3*/site-packages/bluepy/bluepy-helper
# expected: ... cap_net_admin,cap_net_raw=eip
```

`install.sh` already does this. **Reinstalling or rebuilding the virtual environment removes the
capabilities**, and every Bluetooth sensor then fails. TerrariumPI logs this error with the fix
command:

```
SwitchBot Bluetooth scan on hci0 was denied. The bluepy helper needs network capabilities. Fix with: sudo setcap ...
```

## 3. Python dependencies

No new packages are needed. The driver uses `bluepy`, which is already in `requirements.txt`.
For running the automated tests:

```sh
venv/bin/pip install -r requirements-dev.txt
venv/bin/python -m pytest tests/ -v
```

## 4. Systemd and Docker

**Native install (systemd):** no changes needed. To change the freshness limit (default 180 seconds):

```sh
sudo systemctl edit terrariumpi
# add:
# [Service]
# Environment=SWITCHBOT_MAX_AGE=180
sudo systemctl restart terrariumpi
```

**Docker:** `bluepy` talks to the Bluetooth adapter through raw HCI sockets, not through BlueZ/D-Bus.
So BLE needs no D-Bus mount, no `/dev` mount and no privileged mode. It needs the host network and
two capabilities:

```yaml
services:
  terrariumpi:
    network_mode: host # HCI sockets are only reachable from the host network namespace
    cap_add:
      - NET_ADMIN
      - NET_RAW
    environment:
      SWITCHBOT_MAX_AGE: "180"
```

The default `contrib/docker-compose.yaml` already uses `network_mode: host` and `privileged: true`
(for GPIO, I2C and camera), and that covers BLE as well. The minimal setup above is for when you want
to drop `privileged`. The Bluetooth adapter must be up on the host (step 1). The Docker setup has not
been tested with real meters yet.

**Alternative:** if BLE inside TerrariumPI is ever not workable, run `contrib/switchbot_scan.py --json`
on the host from a timer, and read the values with a TerrariumPI *Script sensor*. The native
driver is simpler and recommended.

## 5. Find your meters

Power the meters on (pull the battery tab) and place them within a few meters of the Pi. Then run:

```sh
venv/bin/python contrib/switchbot_scan.py --duration 20
```

Example output:

```
Found 5 SwitchBot devices (34 Bluetooth devices total)

MAC address          RSSI   Temp C  Hum %  Status
ce:1b:c0:c6:78:5d     -68     23.6     88  OK
                   raw mfr=6909ce1bc0c6785d290a06975800 svc=-
ce:1b:c5:06:55:39     -68     23.8     79  OK (app shows Fahrenheit)
                   raw mfr=6909ce1bc50655393d0a0897cf00 svc=-
```

- `OK`: a valid Indoor/Outdoor Thermo-Hygrometer reading.
- `rejected: ...`: a SwitchBot device that is not supported, or bad data. The reason is shown.
- Exit code 0 means at least one valid meter was found, 1 means none were found, and 2 means a
  Bluetooth error.

To find out which MAC belongs to which meter, open the SwitchBot app, then select the meter,
**Settings (gear) → Device Info**. The app shows the **BLE MAC**. You can also warm one meter in
your hand and run the scan again; that meter's temperature goes up.

Write the MAC on a label on each meter.

## 6. Add the temperature sensor

**Automatic:** in the TerrariumPI web interface open **Sensors → Scan sensors**. Each meter found is
added as two sensors named `SwitchBot <last 5 of MAC> temperature` and `... humidity`. TerrariumPI also
scans at startup. Rename the sensors afterwards (step 8).

**Manual:** **Sensors → New sensor**, then:

| Field    | Value                                                |
| -------- | ---------------------------------------------------- |
| Hardware | `SwitchBot Indoor/Outdoor Thermo-Hygrometer (BLE)`   |
| Type     | `Temperature`                                        |
| Address  | the meter MAC, e.g. `ce:1b:c2:86:30:6a`               |
| Name     | e.g. `Paludarium canopy temperature`                 |

Set **Limit min / Limit max** to the physically possible range (for example 40 and 110 °F). Readings
outside this range are stored and shown as out-of-range errors. Note that out-of-range values are
still included in area averages (see [Safety](#safety)). Set **Alarm min / Alarm max** to the range you
want for your animals.

If you have more than one Bluetooth adapter, add the adapter number to the address, for example
`ce:1b:c2:86:30:6a,1` for `hci1`. Without it, `hci0` is used.

## 7. Add the humidity sensor

Same as step 6, with **Type** `Humidity` and the **same address**. Typical limits are 0 and 100 %.
Both sensors share one scan.

## 8. Multiple meters

Repeat steps 6 and 7 for each MAC, or use **Scan sensors** once. Give every sensor a name that tells
where it is, for example `Canopy`, `Water line` or `Room`. You can add every meter to an
enclosure area. The area then uses the average of its sensors, and a single meter without data is
left out.

TerrariumPI scans for new sensors at every startup. A **deleted** sensor is added again at the next
startup when its meter is still in range, for example a neighbour's meter. Use **Exclude** on the
Sensors page instead of delete for meters you do not want.

## 9. Check the readings against the SwitchBot app

1. Open the meter in the SwitchBot app and note the temperature and humidity.
2. At the same time run `venv/bin/python contrib/switchbot_scan.py --duration 10`.
3. The values must match: temperature to 0.1 °C and humidity to 1 %. The app may show °F; TerrariumPI
   converts to your configured unit. `(app shows Fahrenheit)` only tells which unit the meter's display
   uses.
4. Compare with the TerrariumPI dashboard. The dashboard updates every 30 seconds. With an offset set
   in the sensor calibration, the dashboard value is shifted by that offset.

Also check a cold reading: put a meter in the freezer for 30 minutes and run the scan with `--json`.
Negative temperatures are decoded according to the protocol spec, but they have not been checked with
a real meter yet. Please save the output.

## 10. Troubleshooting

| Symptom | Check | Fix |
| ------- | ----- | --- |
| Hardware type not in the list | `hcitool dev` shows no adapter | Step 1. Bluetooth sensors are hidden when no adapter is found. Restart TerrariumPI after fixing |
| Log: `scan on hci0 was denied` | `/sbin/getcap .../bluepy-helper` is empty | Step 2 |
| Log: `No fresh data from SwitchBot meter ...: not heard since TerrariumPI started` | Run `contrib/switchbot_scan.py --duration 60` | Wrong MAC address, meter out of range, or battery empty. RSSI below -90 is too weak; move the Pi or meter |
| Log: `... Last advertisement was rejected: unsupported SwitchBot model` | The device is not an Indoor/Outdoor meter | Only W3400010 is supported |
| A removed meter or a neighbour's meter keeps coming back | It is added again by the startup scan | Use **Exclude** instead of delete |
| Values stop for a few minutes and then come back | `journalctl -u terrariumpi` or `log/terrariumpi.log` | Normal on weak signal. Values come back on their own, with a `... is back` log line |
| `Bluetooth helper stopped ... restarting scan` in the scan tool | TerrariumPI cleans up `bluepy` helpers once per update round | Harmless. The scan restarts automatically |
| Scan tool says `Permission Denied` but `getcap` is OK | `rfkill list` (if installed) | `sudo rfkill unblock bluetooth` |

Useful log commands:

```sh
grep -i switchbot log/terrariumpi.log | tail -20
journalctl -u terrariumpi -f | grep -i -E "switchbot|bluetooth"
```

## 11. Sensor freshness and unavailable readings

- **The meter is advertising:** TerrariumPI records a value every 30 seconds.
- **No advertisement for up to 180 seconds** (`SWITCHBOT_MAX_AGE`): TerrariumPI keeps recording the
  last valid reading.
- **No advertisement for more than 180 seconds:**
  - No values are recorded and the dashboard keeps the last value.
  - The log shows `No fresh data from SwitchBot meter ...` once, then at most every 10 minutes.
- **No value for 5 minutes:**
  - The sensor shows an error in the web interface.
  - It is left out of area averages.
  - If **all** sensors of an area are in error, the area turns its relays **off** and logs
    `All sensors for area ... are in an error state`.
- **The meter is back:** recording starts again and the log shows `SwitchBot meter ... is back`.

To check by hand when a meter was last heard, run the scan tool. The `--json` output includes a
`captured_at` timestamp for each meter.

## Safety

These meters can control heaters, ventilation and misting. Before using them for automation:

1. Fill in **Limit min / Limit max** on every SwitchBot sensor (steps 6 and 7), so a bad value shows
   up as an error in the web interface. TerrariumPI still includes out-of-range values in area
   averages, so limits make problems visible but do not keep them out of relay control.
2. Set **Max diff** on the sensors. A sudden jump bigger than this is ignored for up to 4 updates,
   and the previous value is kept.
3. Use at least two sensors per area, ideally including a wired sensor (BME280). The area then keeps
   working when one meter drops out.
4. Keep a hardware thermostat or thermal cut-off on every heater. Software safety cannot replace it.
5. Only areas in **sensor** mode switch relays off when all sensors fail. Areas that run on timers or
   weather keep switching on schedule.
6. Test the failure path once: remove the battery from a meter that is the only sensor in a test area.
   After about 5 minutes the area must report the sensor error and switch its relays off.

## Protocol reference

The meter puts its data in manufacturer specific data, company ID `0x0969`. The 12 bytes after the
company ID are:

| Bytes | Meaning |
| ----- | ------- |
| 0-5   | Meter MAC address |
| 6     | Frame counter |
| 8     | Bits 0-3: tenths of °C |
| 9     | Bit 7: sign (1 = positive), bits 0-6: whole °C |
| 10    | Bit 7: display shows °F, bits 0-6: humidity % |

Source: [pySwitchBot](https://github.com/sblibs/pySwitchBot) `adv_parsers/meter.py` (model `w`). This
was confirmed with captures from real meters, which are stored as test fixtures in
`tests/test_switchbot_ble.py`. The meters checked do not send the SwitchBot service data with the
model code. The driver therefore accepts an advertisement only when the layout matches exactly (length,
company ID, MAC address inside the data, valid ranges). It rejects the advertisement when service data
reports a different model.
