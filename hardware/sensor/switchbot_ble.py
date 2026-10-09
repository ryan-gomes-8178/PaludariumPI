# -*- coding: utf-8 -*-
"""Shared SwitchBot Bluetooth LE decoder and advertisement collector.

Helper module for switchbot_sensor.py. The filename deliberately does not end with
'_sensor.py', so the hardware loader does not register it as a sensor driver.

Supported device: SwitchBot Indoor/Outdoor Thermo-Hygrometer (model 'w', W3400010).

The meter broadcasts its measurement in manufacturer specific data (AD type 0xFF),
company ID 0x0969. Payload after the company ID is 12 bytes:

  [0:6]  device MAC address
  [6]    frame counter (increments on new data)
  [7]    unknown
  [8]    bits 0-3: temperature decimal (0.1 C)
  [9]    bit 7: temperature sign (1 = positive), bits 0-6: whole degrees C
  [10]   bit 7: display unit is Fahrenheit, bits 0-6: relative humidity %
  [11]   unknown

Layout source: pySwitchBot switchbot/adv_parsers/meter.py + _sensor_th.py (model 'w'),
confirmed against captures from real hardware (see tests/test_switchbot_ble.py).
The Indoor/Outdoor meter does not always send service data, so the model byte is
usually not available. Advertisements are only accepted when the payload layout
matches exactly, and rejected when service data reports a different model.
"""
import terrariumLogging

logger = terrariumLogging.logging.getLogger(__name__)

import os
import re
import threading
import time
from datetime import datetime, timezone

COMPANY_ID = 0x0969
PAYLOAD_LENGTH = 12
SUPPORTED_MODELS = {"w": "Indoor/Outdoor Thermo-Hygrometer"}
# 16-bit service data UUIDs used by SwitchBot (new and legacy)
SERVICE_UUIDS = ("fd3d", "0d00")
# Device specification is -40C to 60C. Allow some margin, anything outside is a decoding error
TEMPERATURE_RANGE = (-40.0, 85.0)

# Readings older than this are stale and will not be returned. Override with env SWITCHBOT_MAX_AGE (seconds)
DEFAULT_STALE_AFTER = 180

# bluepy AD types
_AD_MANUFACTURER = 255
_AD_SERVICE_DATA_16 = 22

_MAC_REGEX = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")


class SwitchBotDecodeError(ValueError):
    pass


class SwitchBotBluetoothError(Exception):
    pass


def normalize_mac(mac):
    value = str(mac).strip().lower().replace("-", ":")
    if not _MAC_REGEX.match(value):
        raise ValueError(f"Invalid Bluetooth MAC address '{mac}'")

    return value


def is_switchbot_advert(mfr_hex, svc_hex=None):
    mfr_hex = (mfr_hex or "").lower()
    svc_hex = (svc_hex or "").lower()
    # Company ID and 16-bit UUIDs are little endian on the air
    return mfr_hex.startswith(COMPANY_ID.to_bytes(2, "little").hex()) or any(
        svc_hex.startswith(bytes.fromhex(uuid)[::-1].hex()) for uuid in SERVICE_UUIDS
    )


def model_from_service_data(svc_hex):
    """Return the SwitchBot model character from 16-bit service data, or None when not available."""
    if not svc_hex:
        return None

    try:
        raw = bytes.fromhex(svc_hex)
    except ValueError:
        return None

    if len(raw) < 3 or raw[1::-1].hex() not in SERVICE_UUIDS:
        return None

    # Highest bit is the encryption flag
    return chr(raw[2] & 0b01111111)


def decode_io_meter(mac, mfr_hex, svc_hex=None):
    """Decode an Indoor/Outdoor Thermo-Hygrometer advertisement.

    mfr_hex: manufacturer data as hex including the company ID (bluepy getValueText(255))
    svc_hex: optional 16-bit service data as hex (bluepy getValueText(22))

    Raises SwitchBotDecodeError with the reason when the advertisement is not a valid measurement.
    """
    mac = normalize_mac(mac)

    if not mfr_hex:
        raise SwitchBotDecodeError("no manufacturer data")

    try:
        raw = bytes.fromhex(mfr_hex)
    except ValueError:
        raise SwitchBotDecodeError("manufacturer data is not valid hex")

    if len(raw) < 2 or int.from_bytes(raw[:2], "little") != COMPANY_ID:
        raise SwitchBotDecodeError("not a SwitchBot advertisement")

    payload = raw[2:]
    if len(payload) != PAYLOAD_LENGTH:
        raise SwitchBotDecodeError(f"unexpected payload length {len(payload)}, expected {PAYLOAD_LENGTH}")

    if payload[0:6].hex(":") != mac:
        raise SwitchBotDecodeError(f"payload address {payload[0:6].hex(':')} does not match device {mac}")

    model = model_from_service_data(svc_hex)
    if model is not None and model not in SUPPORTED_MODELS:
        raise SwitchBotDecodeError(f"unsupported SwitchBot model '{model}'")

    decimal = payload[8] & 0b00001111
    if decimal > 9:
        raise SwitchBotDecodeError(f"invalid temperature decimal {decimal}")

    whole = payload[9] & 0b01111111
    sign = 1 if payload[9] & 0b10000000 else -1
    temperature = round(sign * (whole + decimal / 10), 1)
    humidity = payload[10] & 0b01111111

    if whole == 0 and decimal == 0 and humidity == 0:
        raise SwitchBotDecodeError("empty measurement (0C and 0%)")

    if humidity > 100:
        raise SwitchBotDecodeError(f"humidity {humidity}% out of range")

    if not TEMPERATURE_RANGE[0] <= temperature <= TEMPERATURE_RANGE[1]:
        raise SwitchBotDecodeError(f"temperature {temperature}C out of range")

    return {
        "device_id": mac,
        "temperature_c": temperature,
        "humidity_pct": humidity,
        "fahrenheit_display": bool(payload[10] & 0b10000000),
        "frame": payload[6],
        "model_confirmed": model is not None,
    }


def helper_path():
    try:
        import bluepy

        return os.path.join(os.path.dirname(bluepy.__file__), "bluepy-helper")
    except Exception:
        return "venv/lib/python3*/site-packages/bluepy/bluepy-helper"


class SwitchBotCollector(object):
    """Collects SwitchBot advertisements from short BLE scans and caches the latest valid reading per device.

    One scan stores every meter that is heard, so multiple devices and multiple sensor types share scans.
    """

    SCAN_DURATION = 12  # Max seconds per scan. Meters advertise every few seconds
    REUSE_WINDOW = 25  # Readings or scan attempts younger than this do not trigger a new scan
    SCAN_LOCK_TIMEOUT = 15
    LOG_REPEAT = 600  # Repeat the same warning at most every 10 minutes

    def __init__(self, scanner_factory=None, clock=time.time):
        self.__scanner_factory = scanner_factory
        self.__clock = clock

        self.__lock = threading.Lock()
        self.__scan_lock = threading.Lock()

        self.__readings = {}
        self.__rejections = {}
        self.__scan_attempts = {}
        self.__last_full_scan = float("-inf")
        # Meters that are used by sensors (mac -> last read). A scan continues until all of them are heard
        self.__known = {}
        self.__seen_updates = {}

        self.__logged = {}
        self.__stale = set()
        self.__bluetooth_failing = False

    @property
    def stale_after(self):
        try:
            value = float(os.environ.get("SWITCHBOT_MAX_AGE", DEFAULT_STALE_AFTER))
        except ValueError:
            value = DEFAULT_STALE_AFTER

        return value if value > 0 else DEFAULT_STALE_AFTER

    def _scanner(self, hci):
        if self.__scanner_factory is None:
            from bluepy.btle import Scanner

            return Scanner(hci)

        return self.__scanner_factory(hci)

    def __log_throttled(self, key, level, message):
        now = self.__clock()
        with self.__lock:
            if now - self.__logged.get(key, float("-inf")) < self.LOG_REPEAT:
                return
            self.__logged[key] = now

        logger.log(level, message)

    def __store(self, entry):
        mfr = entry.getValueText(_AD_MANUFACTURER)
        svc = entry.getValueText(_AD_SERVICE_DATA_16)
        if not is_switchbot_advert(mfr, svc):
            return False

        # bluepy keeps updating the same scan entry. Only handle new advertisement data
        update = (entry.addr, getattr(entry, "updateCount", None), mfr, svc)
        if self.__seen_updates.get(entry.addr) == update:
            return entry.addr in self.__readings

        self.__seen_updates[entry.addr] = update

        try:
            reading = decode_io_meter(entry.addr, mfr, svc)
        except (SwitchBotDecodeError, ValueError) as ex:
            logger.debug(f"Ignored SwitchBot advertisement from {entry.addr}: {ex}. Data: {mfr} {svc or ''}")
            with self.__lock:
                self.__rejections[entry.addr] = str(ex)
            return False

        now = self.__clock()
        reading["rssi"] = entry.rssi
        reading["last_seen"] = now
        reading["last_seen_iso"] = datetime.fromtimestamp(now, timezone.utc).isoformat()

        with self.__lock:
            self.__readings[reading["device_id"]] = reading
            self.__rejections.pop(reading["device_id"], None)

        return True

    def __log_bluetooth_error(self, hci, ex):
        self.__bluetooth_failing = True
        error = f"{getattr(ex, 'emsg', '')} {ex}".lower()
        if "permission" in error:
            self.__log_throttled(
                "bluetooth-permission",
                terrariumLogging.logging.ERROR,
                f"SwitchBot Bluetooth scan on hci{hci} was denied. The bluepy helper needs network capabilities. "
                f"Fix with: sudo setcap 'cap_net_raw,cap_net_admin+eip' {helper_path()}",
            )
        else:
            self.__log_throttled(
                f"bluetooth-error-{hci}",
                terrariumLogging.logging.ERROR,
                f"SwitchBot Bluetooth scan on hci{hci} failed: {ex}",
            )

    def scan(self, hci=0, duration=None, wanted=None):
        """Run one BLE scan and cache all valid SwitchBot readings.

        With 'wanted' MAC addresses the scan stops as soon as all of them are heard.
        Raises SwitchBotBluetoothError when Bluetooth fails.
        """
        duration = self.SCAN_DURATION if duration is None else duration
        wanted = set(normalize_mac(mac) for mac in (wanted or []))

        if not self.__scan_lock.acquire(timeout=self.SCAN_LOCK_TIMEOUT):
            logger.debug("Another SwitchBot scan is still running. Using cached readings.")
            return 0

        try:
            # Another scan could have delivered the wanted data while we were waiting
            if wanted and all(self.get(mac, self.REUSE_WINDOW) is not None for mac in wanted):
                return 0

            start = self.__clock()
            with self.__lock:
                for mac in wanted:
                    self.__scan_attempts[mac] = start

            found = set()
            # A device heard again with unchanged data is still a fresh sighting
            self.__seen_updates = {}
            scanner = self._scanner(hci)
            try:
                scanner.clear()
                # Passive scanning: the meters put all data in the advertisement, no scan requests needed
                scanner.start(passive=True)
                while True:
                    scanner.process(1.0)
                    for entry in scanner.getDevices():
                        if self.__store(entry):
                            found.add(entry.addr)

                    if wanted and wanted <= found:
                        break

                    if self.__clock() - start >= duration:
                        with self.__lock:
                            self.__last_full_scan = self.__clock()
                        break

            except Exception as ex:
                self.__log_bluetooth_error(hci, ex)
                raise SwitchBotBluetoothError(str(ex)) from ex

            finally:
                try:
                    # Also stops the bluepy-helper process
                    scanner.stop()
                except Exception:
                    pass

            if self.__bluetooth_failing:
                self.__bluetooth_failing = False
                with self.__lock:
                    self.__logged = {k: v for k, v in self.__logged.items() if not k.startswith("bluetooth-")}
                logger.info(f"SwitchBot Bluetooth scanning on hci{hci} is working again.")

            logger.debug(f"SwitchBot scan on hci{hci} found {len(found)} meters in {self.__clock() - start:.1f} seconds")
            return len(found)

        finally:
            self.__scan_lock.release()

    def get(self, mac, max_age=None):
        """Return a copy of the cached reading when it is younger than max_age (default: stale_after)."""
        mac = normalize_mac(mac)
        max_age = self.stale_after if max_age is None else max_age
        with self.__lock:
            reading = self.__readings.get(mac)

        if reading is None or self.__clock() - reading["last_seen"] > max_age:
            return None

        return dict(reading)

    def devices(self, max_age=None):
        with self.__lock:
            macs = list(self.__readings.keys())

        return [reading for reading in (self.get(mac, max_age) for mac in macs) if reading is not None]

    def rejection(self, mac):
        with self.__lock:
            return self.__rejections.get(normalize_mac(mac))

    def __may_scan(self, mac):
        with self.__lock:
            last_attempt = max(self.__scan_attempts.get(mac, float("-inf")), self.__last_full_scan)

        return self.__clock() - last_attempt >= self.REUSE_WINDOW

    def read(self, mac, hci=0):
        """Return the latest valid and fresh reading for a meter, or None.

        Scans only when there is no recent reading and no recent scan attempt for this meter,
        so a missing meter does not block the sensor update loop with repeated scans.
        """
        mac = normalize_mac(mac)
        now = self.__clock()
        with self.__lock:
            self.__known[mac] = now
            # Forget meters that are not read anymore (removed sensors)
            self.__known = {key: value for key, value in self.__known.items() if now - value < self.LOG_REPEAT}
            wanted = set(self.__known)

        reading = self.get(mac, self.REUSE_WINDOW)
        if reading is None:
            if self.__may_scan(mac):
                try:
                    # One scan refreshes all meters in use, so the other sensors read from the cache
                    self.scan(hci, wanted=wanted)
                except SwitchBotBluetoothError:
                    # Already logged. Fall back to the cached data if still fresh
                    pass

            reading = self.get(mac)

        self.__track_freshness(mac, reading)
        return reading

    def __track_freshness(self, mac, reading):
        if reading is not None:
            if mac in self.__stale:
                self.__stale.discard(mac)
                with self.__lock:
                    self.__logged.pop(f"stale-{mac}", None)
                logger.info(
                    f"SwitchBot meter {mac} is back: {reading['temperature_c']}C, {reading['humidity_pct']}% "
                    f"(rssi {reading['rssi']})"
                )
            return

        with self.__lock:
            last = self.__readings.get(mac)
        message = f"No fresh data from SwitchBot meter {mac}: " + (
            "not heard since TerrariumPI started"
            if last is None
            else f"last valid reading {self.__clock() - last['last_seen']:.0f} seconds ago (limit {self.stale_after:.0f} seconds)"
        )
        reason = self.rejection(mac)
        if reason is not None:
            message += f". Last advertisement was rejected: {reason}"

        self.__stale.add(mac)
        self.__log_throttled(f"stale-{mac}", terrariumLogging.logging.WARNING, message)


# Shared by all SwitchBot sensors in this process
collector = SwitchBotCollector()
