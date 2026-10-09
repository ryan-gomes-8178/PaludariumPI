# -*- coding: utf-8 -*-
import terrariumLogging

logger = terrariumLogging.logging.getLogger(__name__)

from . import terrariumSensor, terrariumBluetoothSensor, terrariumSensorLoadingException

# Shared decoder and scanner, so temperature and humidity of all meters use the same BLE scans
from . import switchbot_ble


class terrariumSwitchBotSensor(terrariumBluetoothSensor):
    HARDWARE = "switchbot"
    TYPES = ["temperature", "humidity"]
    NAME = "SwitchBot Indoor/Outdoor Thermo-Hygrometer (BLE)"

    # A scan can take up to SwitchBotCollector.SCAN_DURATION seconds
    _UPDATE_TIME_OUT = 20

    def _load_hardware(self):
        address = self._address
        try:
            mac = switchbot_ble.normalize_mac(address[0])
        except ValueError as ex:
            raise terrariumSensorLoadingException(f"{ex} for sensor {self}")

        # No Bluetooth connection is needed, the meter broadcasts its data. So a meter that is not heard yet still loads.
        return (mac, address[1])

    def _get_data(self):
        reading = switchbot_ble.collector.read(*self.device)
        if reading is None:
            # No fresh valid data. Never return old or made up values
            return None

        return {"temperature": reading["temperature_c"], "humidity": reading["humidity_pct"]}

    @staticmethod
    def _scan_sensors(unit_value_callback=None, trigger_callback=None, **kwargs):
        try:
            switchbot_ble.collector.scan(0)
        except switchbot_ble.SwitchBotBluetoothError:
            # Already logged by the collector
            return

        for reading in switchbot_ble.collector.devices():
            for sensor_type in __class__.TYPES:
                yield terrariumSensor(
                    None,
                    __class__.HARDWARE,
                    sensor_type,
                    reading["device_id"],
                    f"SwitchBot {reading['device_id'][-5:]} {sensor_type}",
                    unit_value_callback=unit_value_callback,
                    trigger_callback=trigger_callback,
                )
