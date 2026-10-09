"""Tests for the SwitchBot Indoor/Outdoor Thermo-Hygrometer BLE support.

Run from the TerrariumPI directory: venv/bin/python -m pytest tests/ -v

Fixture provenance:
- REAL_*: captured from Ryan's 5 meters on 2026-10-09 with bluepy (hci0, Raspberry Pi 4).
  Expected values are what the decoder returns; compare with the SwitchBot app to validate (see docs).
- UPSTREAM_*: pySwitchBot tests/test_adv_parser.py test_woiosensor_passive_and_active
  https://github.com/sblibs/pySwitchBot (expected 24.6C, 53%, model 'w').
- SPEC_*: built from the documented bit layout, NOT captured from hardware.
  Negative temperatures still need a real capture (put a meter in the freezer, see docs).
"""
import logging

import pytest

from hardware.sensor import switchbot_ble
from hardware.sensor.switchbot_ble import (
    SwitchBotCollector,
    SwitchBotDecodeError,
    decode_io_meter,
    is_switchbot_advert,
)

# Real captures: (mac, manufacturer data incl. company ID, temperature, humidity, fahrenheit display)
REAL = [
    ("ce:1b:c2:86:30:6a", "6909ce1bc286306a240a09965600", 22.9, 86, False),
    ("ce:1b:c5:06:55:39", "6909ce1bc50655393c0a0098d000", 24.0, 80, True),
    ("ce:1b:c3:c6:6a:64", "6909ce1bc3c66a64240a06975200", 23.6, 82, False),
    ("ce:1b:c2:06:1d:8b", "6909ce1bc2061d8b400a04965d00", 22.4, 93, False),
    ("ce:1b:c0:c6:78:5d", "6909ce1bc0c6785d280a08975800", 23.8, 88, False),
]
# Same meter as REAL[3], next frame (counter 0x40 -> 0x41) seen 2 minutes later
REAL_NEXT_FRAME = ("ce:1b:c2:06:1d:8b", "6909ce1bc2061d8b410a01965d00", 22.1, 93)

UPSTREAM_MAC = "aa:bb:cc:dd:ee:ff"
UPSTREAM_MFR = "6909aabbccddeeffe00f06983500"
# bluepy service data hex: UUID 0xfd3d little endian, then model 'w' (0x77), 0x00, battery 0xe4
UPSTREAM_SVC = "3dfd7700e4"

# REAL[0] with byte 8 = 0x03 and byte 9 = 0x05 (sign bit clear): -5.3C
SPEC_NEGATIVE = "6909ce1bc286306a240a03055600"
# REAL[0] with byte 8 = 0x09 and byte 9 = 0x00: -0.9C
SPEC_NEGATIVE_BELOW_ONE = "6909ce1bc286306a240a09005600"


class FakeClock:
    def __init__(self, now=1_800_000_000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeEntry:
    def __init__(self, addr, mfr, svc=None, rssi=-70, update_count=1):
        self.addr = addr
        self.rssi = rssi
        self.updateCount = update_count
        self.__data = {255: mfr, 22: svc}

    def getValueText(self, adtype):
        return self.__data.get(adtype)


class FakeScanner:
    """Mimics bluepy Scanner. 'rounds' is a list with the entries heard per process() call."""

    def __init__(self, clock, rounds=None, error=None):
        self.clock = clock
        self.rounds = list(rounds or [])
        self.error = error
        self.devices = {}
        self.process_calls = 0
        self.stopped = False

    def clear(self):
        self.devices = {}

    def start(self, passive=False):
        assert passive is True
        if self.error is not None:
            raise self.error

    def process(self, timeout):
        self.process_calls += 1
        self.clock.advance(timeout)
        if self.rounds:
            for entry in self.rounds.pop(0):
                self.devices[entry.addr] = entry

    def getDevices(self):
        return list(self.devices.values())

    def stop(self):
        self.stopped = True


class FakeRadio:
    """Scanner factory that hands out a prepared scanner per scan and counts scans."""

    def __init__(self, clock):
        self.clock = clock
        self.queue = []
        self.scanners = []

    def add_scan(self, rounds=None, error=None):
        self.queue.append(FakeScanner(self.clock, rounds, error))

    def __call__(self, hci):
        scanner = self.queue.pop(0) if self.queue else FakeScanner(self.clock)
        self.scanners.append(scanner)
        return scanner

    @property
    def scans(self):
        return len(self.scanners)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def radio(clock):
    return FakeRadio(clock)


@pytest.fixture
def collector(radio, clock, monkeypatch):
    monkeypatch.delenv("SWITCHBOT_MAX_AGE", raising=False)
    return SwitchBotCollector(scanner_factory=radio, clock=clock)


def entries(*captures):
    return [FakeEntry(capture[0], capture[1]) for capture in captures]


# 1 + 2: valid temperature and humidity, real hardware


@pytest.mark.parametrize("mac,mfr,temperature,humidity,fahrenheit", REAL)
def test_decode_real_captures(mac, mfr, temperature, humidity, fahrenheit):
    data = decode_io_meter(mac, mfr)
    assert data["temperature_c"] == temperature
    assert data["humidity_pct"] == humidity
    assert data["fahrenheit_display"] is fahrenheit
    assert data["device_id"] == mac
    assert data["model_confirmed"] is False


def test_decode_real_next_frame():
    mac, mfr, temperature, humidity = REAL_NEXT_FRAME
    data = decode_io_meter(mac, mfr)
    assert (data["temperature_c"], data["humidity_pct"], data["frame"]) == (temperature, humidity, 0x41)


def test_decode_upstream_fixture_with_model():
    data = decode_io_meter(UPSTREAM_MAC, UPSTREAM_MFR, UPSTREAM_SVC)
    assert data["temperature_c"] == 24.6
    assert data["humidity_pct"] == 53
    assert data["model_confirmed"] is True


def test_decode_upstream_fixture_passive_only():
    data = decode_io_meter(UPSTREAM_MAC, UPSTREAM_MFR)
    assert (data["temperature_c"], data["humidity_pct"]) == (24.6, 53)


def test_mac_is_case_insensitive():
    assert decode_io_meter(REAL[0][0].upper(), REAL[0][1])["temperature_c"] == 22.9


# 3: negative temperatures (spec derived)


def test_decode_negative_temperature():
    assert decode_io_meter(REAL[0][0], SPEC_NEGATIVE)["temperature_c"] == -5.3


def test_decode_negative_temperature_below_one_degree():
    assert decode_io_meter(REAL[0][0], SPEC_NEGATIVE_BELOW_ONE)["temperature_c"] == -0.9


# 4: malformed packets


@pytest.mark.parametrize(
    "mfr,reason",
    [
        (None, "no manufacturer data"),
        ("", "no manufacturer data"),
        ("zz09", "not valid hex"),
        ("6909", "payload length 0"),
        ("4c00ce1bc286306a240a09965600", "not a SwitchBot"),  # Apple company ID
        ("6909ce1bc286306a240a099656", "payload length 11"),  # Truncated
        ("6909ce1bc286306a240a0996560000", "payload length 13"),  # Too long
        ("6909aabbccddeeff240a09965600", "does not match device"),  # Other device MAC
        ("6909ce1bc286306a240a0a965600", "invalid temperature decimal"),  # Decimal nibble 10
        ("6909ce1bc286306a240a00000000", "empty measurement"),
        ("6909ce1bc286306a240a00806500", "humidity 101%"),
        ("6909ce1bc286306a240a00d65600", "out of range"),  # +86.0C
        ("6909ce1bc286306a240a00295600", "out of range"),  # -41.0C
    ],
)
def test_decode_rejects_malformed(mfr, reason):
    with pytest.raises(SwitchBotDecodeError, match=reason):
        decode_io_meter(REAL[0][0], mfr)


def test_decode_rejects_invalid_mac():
    with pytest.raises(ValueError):
        decode_io_meter("not-a-mac", REAL[0][1])


# 5: unknown or unsupported SwitchBot devices


@pytest.mark.parametrize("model", ["T", "i", "4", "H"])
def test_decode_rejects_other_models(model):
    svc = "3dfd" + ord(model).to_bytes(1, "little").hex() + "00e4"
    with pytest.raises(SwitchBotDecodeError, match="unsupported SwitchBot model"):
        decode_io_meter(UPSTREAM_MAC, UPSTREAM_MFR, svc)


def test_encrypted_flag_does_not_hide_model():
    # Highest bit of the model byte is the encryption flag: 0xf7 is still model 'w'
    assert decode_io_meter(UPSTREAM_MAC, UPSTREAM_MFR, "3dfdf700e4")["model_confirmed"] is True


def test_switchbot_advert_detection():
    assert is_switchbot_advert(REAL[0][1])
    assert is_switchbot_advert(None, UPSTREAM_SVC)
    assert is_switchbot_advert(None, "000d7700e4")
    assert not is_switchbot_advert("4c000215", None)
    assert not is_switchbot_advert(None, None)


def test_collector_ignores_other_devices(collector, radio):
    radio.add_scan(
        [
            [
                FakeEntry("11:22:33:44:55:66", "4c000215aabb"),  # Apple beacon
                FakeEntry("aa:bb:cc:dd:ee:ff", UPSTREAM_MFR, "3dfd6900e4"),  # Meter Plus
            ]
        ]
    )
    collector.scan(0, duration=1)
    assert collector.devices() == []
    assert "unsupported SwitchBot model" in collector.rejection("aa:bb:cc:dd:ee:ff")


# 6: missing advertisements


def test_missing_meter_returns_none_and_warns_once(collector, radio, clock, caplog):
    caplog.set_level(logging.WARNING, logger=switchbot_ble.logger.name)
    radio.add_scan([[]] * 20)
    assert collector.read(REAL[0][0]) is None
    assert radio.scanners[0].stopped
    # Scan gave up after its duration, not before
    assert radio.scanners[0].process_calls == SwitchBotCollector.SCAN_DURATION

    # Retries within the reuse window do not scan again, so the update loop is not blocked
    assert collector.read(REAL[0][0]) is None
    assert collector.read(REAL[0][0]) is None
    assert radio.scans == 1

    clock.advance(SwitchBotCollector.REUSE_WINDOW)
    assert collector.read(REAL[0][0]) is None
    assert radio.scans == 2

    warnings = [r for r in caplog.records if "No fresh data" in r.getMessage()]
    assert len(warnings) == 1
    assert "not heard since TerrariumPI started" in warnings[0].getMessage()


def test_missing_meter_reports_rejection_reason(collector, radio, caplog):
    caplog.set_level(logging.WARNING, logger=switchbot_ble.logger.name)
    radio.add_scan([[FakeEntry(REAL[0][0], "6909ce1bc286306a240a00000000")]])
    assert collector.read(REAL[0][0]) is None
    assert "empty measurement" in caplog.records[-1].getMessage()


# 7: stale cached readings


def test_stale_reading_is_not_returned(collector, radio, clock):
    radio.add_scan([entries(REAL[0])])
    assert collector.read(REAL[0][0])["temperature_c"] == 22.9

    clock.advance(170)
    # Meter stopped advertising: cached value still valid within 180 seconds
    assert collector.get(REAL[0][0])["temperature_c"] == 22.9

    clock.advance(11)
    assert collector.get(REAL[0][0]) is None
    assert collector.read(REAL[0][0]) is None


def test_stale_limit_is_configurable(collector, radio, clock, monkeypatch):
    monkeypatch.setenv("SWITCHBOT_MAX_AGE", "60")
    radio.add_scan([entries(REAL[0])])
    collector.read(REAL[0][0])
    clock.advance(61)
    assert collector.get(REAL[0][0]) is None


@pytest.mark.parametrize("value", ["abc", "-5", "0"])
def test_invalid_stale_limit_uses_default(collector, monkeypatch, value):
    monkeypatch.setenv("SWITCHBOT_MAX_AGE", value)
    assert collector.stale_after == switchbot_ble.DEFAULT_STALE_AFTER


def test_reading_timestamp(collector, radio, clock):
    radio.add_scan([entries(REAL[0])])
    reading = collector.read(REAL[0][0])
    assert reading["last_seen"] == clock.now
    assert reading["last_seen_iso"].endswith("+00:00")
    assert reading["rssi"] == -70


def test_unchanged_data_in_new_scan_refreshes_last_seen(collector, radio, clock):
    radio.add_scan([entries(REAL[0])])
    radio.add_scan([entries(REAL[0])])
    collector.scan(0, wanted=[REAL[0][0]])
    first = collector.get(REAL[0][0])["last_seen"]
    clock.advance(100)
    collector.scan(0, wanted=[REAL[0][0]])
    assert collector.get(REAL[0][0])["last_seen"] == first + 101


def test_recovery_is_logged(collector, radio, clock, caplog):
    caplog.set_level(logging.INFO, logger=switchbot_ble.logger.name)
    radio.add_scan([])
    assert collector.read(REAL[0][0]) is None
    clock.advance(SwitchBotCollector.REUSE_WINDOW)
    radio.add_scan([entries(REAL[0])])
    assert collector.read(REAL[0][0])["humidity_pct"] == 86
    assert "is back" in caplog.records[-1].getMessage()


# 8: multiple devices


def test_one_scan_serves_all_meters(collector, radio, clock):
    # First update round: all meters heard in the first scan
    radio.add_scan([entries(*REAL)])
    for mac, _, temperature, humidity, _ in REAL:
        reading = collector.read(mac)
        assert (reading["temperature_c"], reading["humidity_pct"]) == (temperature, humidity)

    assert radio.scans == 1
    assert len(collector.devices()) == 5

    # Next update round (engine loop is 30 seconds): one scan continues until every meter in use is heard
    clock.advance(30)
    radio.add_scan([entries(*REAL[:2]), entries(*REAL[2:])] + [[]] * 20)
    for mac, *_ in REAL:
        assert collector.read(mac) is not None

    assert radio.scans == 2
    assert radio.scanners[1].process_calls == 2


def test_scan_stops_early_when_wanted_meter_is_heard(collector, radio):
    radio.add_scan([entries(REAL[0])] + [[]] * 20)
    collector.scan(0, wanted=[REAL[0][0]])
    assert radio.scanners[0].process_calls == 1


def test_newer_frame_replaces_reading(collector, radio, clock):
    radio.add_scan([entries(REAL[3])])
    assert collector.read(REAL[3][0])["temperature_c"] == 22.4
    clock.advance(SwitchBotCollector.REUSE_WINDOW + 1)
    radio.add_scan([[FakeEntry(REAL_NEXT_FRAME[0], REAL_NEXT_FRAME[1], update_count=2)]])
    assert collector.read(REAL[3][0])["temperature_c"] == 22.1


# 10: Bluetooth errors and recovery


class FakeManagementError(Exception):
    """Shaped like bluepy BTLEManagementError for 'le on' without capabilities."""

    def __init__(self):
        super().__init__("Failed to execute management command 'le on'")
        self.emsg = "Permission Denied"


def test_permission_error(collector, radio, clock, caplog):
    caplog.set_level(logging.INFO, logger=switchbot_ble.logger.name)
    radio.add_scan(error=FakeManagementError())
    assert collector.read(REAL[0][0]) is None
    assert radio.scanners[0].stopped

    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "setcap 'cap_net_raw,cap_net_admin+eip'" in errors[0].getMessage()

    # Errors repeat at most every LOG_REPEAT seconds
    for _ in range(3):
        clock.advance(SwitchBotCollector.REUSE_WINDOW)
        radio.add_scan(error=FakeManagementError())
        assert collector.read(REAL[0][0]) is None
    assert len([r for r in caplog.records if r.levelno == logging.ERROR]) == 1

    # Recovery
    clock.advance(SwitchBotCollector.REUSE_WINDOW)
    radio.add_scan([entries(REAL[0])])
    assert collector.read(REAL[0][0])["temperature_c"] == 22.9
    messages = [r.getMessage() for r in caplog.records]
    assert any("working again" in message for message in messages)


def test_disconnect_during_scan_keeps_fresh_cache(collector, radio, clock):
    radio.add_scan([entries(REAL[0])])
    collector.read(REAL[0][0])
    clock.advance(60)
    radio.add_scan(error=RuntimeError("bluepy helper died"))
    # Scan fails, but the 60 second old reading is still within the stale limit
    assert collector.read(REAL[0][0])["temperature_c"] == 22.9


def test_scan_error_raises_bluetooth_error(collector, radio):
    radio.add_scan(error=RuntimeError("No such adapter"))
    with pytest.raises(switchbot_ble.SwitchBotBluetoothError):
        collector.scan(0)


# TerrariumPI integration (needs the TerrariumPI virtual environment)


@pytest.fixture
def sensor_module():
    from hardware.sensor import terrariumSensor

    if "switchbot" not in terrariumSensor.available_hardware:
        pytest.skip("Bluetooth not available on this machine, so Bluetooth sensors are hidden")

    return terrariumSensor


def test_driver_is_registered_and_others_unchanged(sensor_module):
    hardware = sensor_module.available_hardware
    assert hardware["switchbot"].TYPES == ["temperature", "humidity"]
    for existing in ["LYWSD03MMC", "mitemp", "miflora", "script", "remote"]:
        assert existing in hardware


# 9: two sensor instances sharing one physical device


def test_temperature_and_humidity_share_one_scan(sensor_module, monkeypatch, radio, clock):
    shared = SwitchBotCollector(scanner_factory=radio, clock=clock)
    monkeypatch.setattr(switchbot_ble, "collector", shared)
    radio.add_scan([entries(REAL[1])])

    temperature = sensor_module(None, "switchbot", "temperature", REAL[1][0], "Test temp")
    humidity = sensor_module(None, "switchbot", "humidity", REAL[1][0], "Test hum")
    for sensor in (temperature, humidity):
        sensor._sensor_cache.clear_data(sensor._sensor_cache_key)

    assert temperature.update() == 24.0
    assert humidity.update() == 80
    assert radio.scans == 1
    assert temperature.id != humidity.id


def test_sensor_without_data_reports_no_value(sensor_module, monkeypatch, radio, clock):
    shared = SwitchBotCollector(scanner_factory=radio, clock=clock)
    monkeypatch.setattr(switchbot_ble, "collector", shared)
    radio.add_scan([[]] * 20)

    sensor = sensor_module(None, "switchbot", "temperature", REAL[4][0], "Missing")
    sensor._sensor_cache.clear_data(sensor._sensor_cache_key)
    # No zero or old value: update() returns None and the engine skips this measurement
    assert sensor.update() is None
    assert sensor.value is None


def test_sensor_rejects_invalid_address(sensor_module):
    from hardware.sensor import terrariumSensorLoadingException

    with pytest.raises(terrariumSensorLoadingException):
        sensor_module(None, "switchbot", "temperature", "not-a-mac", "Bad")


def test_scan_sensors_yields_both_types(sensor_module, monkeypatch, radio, clock):
    shared = SwitchBotCollector(scanner_factory=radio, clock=clock)
    monkeypatch.setattr(switchbot_ble, "collector", shared)
    radio.add_scan([entries(*REAL)] + [[]] * 20)

    found = list(sensor_module.available_hardware["switchbot"]._scan_sensors())
    assert len(found) == 10
    assert {(sensor.address, sensor.type) for sensor in found} == {
        (mac, sensor_type) for mac, *_ in REAL for sensor_type in ("temperature", "humidity")
    }
