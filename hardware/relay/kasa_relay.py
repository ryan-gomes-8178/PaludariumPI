import terrariumLogging

logger = terrariumLogging.logging.getLogger(__name__)

from . import terrariumRelay
from terrariumUtils import terrariumUtils, terrariumAsync, terrariumCache

# pip install python-kasa
from kasa import Discover, Credentials
from kasa.klaptransport import KlapTransport, KlapTransportV2
from kasa.iot import IotPlug, IotStrip
import asyncio

# Global device cache to prevent multiple simultaneous connections to the same device
_device_connection_cache = {}
_device_connection_lock = asyncio.Lock()


class terrariumRelayTPLinkKasa(terrariumRelay):
    HARDWARE = "tplinkkasa"
    NAME = "Kasa Smart"

    URL = "^\d{1,3}\.\d{1,3}\.\d{1,3}(,\d{1,3})?$"

    def _load_hardware(self):
        async def __load_hardware(ip, credentials=None):
            # Use global device cache to avoid multiple simultaneous connections
            global _device_connection_cache, _device_connection_lock
            
            async with _device_connection_lock:
                cache_key = ip
                
                # Check if we already have a connection to this device
                if cache_key in _device_connection_cache:
                    cached_device = _device_connection_cache[cache_key]
                    # Verify the cached device is still valid
                    try:
                        await asyncio.wait_for(cached_device.update(), timeout=2.0)
                        logger.debug(f"Reusing cached connection for Kasa device at {ip}")
                        return cached_device
                    except Exception as e:
                        logger.debug(f"Cached connection invalid for {ip}, reconnecting: {e}")
                        _device_connection_cache.pop(cache_key, None)
                
                # Create new connection via discovery
                logger.debug(f"Discovering Kasa device at {ip}")
                device = await asyncio.wait_for(
                    Discover.discover_single(ip, credentials=credentials, timeout=5),
                    timeout=10
                )
                logger.debug(f"Device discovered: {device}")
                
                # python-kasa 0.7.7 routes IOT.KLAP devices to KlapTransport (v1 MD5 hash)
                # even when the device advertises login_version=2 (v2 SHA-based hash). HS300
                # firmware updated mid-2026 to KLAP v2; without this swap, handshake fails with
                # AuthenticationError. Fixed in python-kasa 0.8+ but that requires Python 3.11+.
                if credentials is not None:
                    ctype = device.config.connection_type
                    if (ctype.encryption_type.value == "KLAP"
                            and ctype.login_version == 2
                            and type(device.protocol._transport) is KlapTransport):
                        device.config.credentials = credentials
                        device.protocol._transport = KlapTransportV2(config=device.config)
                        logger.info(f"Swapped to KlapTransportV2 for {ip} (KLAP login_version=2)")

                # python-kasa 0.7.7 mis-classifies multi-outlet KLAP v2 strips (e.g. HS300
                # after mid-2026 firmware) as IotPlug, leaving children empty and causing
                # KeyError 'relay_state' on state reads. Detect via sys_info.child_num and
                # re-instantiate as IotStrip. Fixed in python-kasa 0.8+ (Python 3.11+ only).
                await device.update()
                child_num = device.sys_info.get("child_num", 0)
                if isinstance(device, IotPlug) and child_num > 0:
                    device = IotStrip(host=ip, config=device.config, protocol=device.protocol)
                    await device.update()
                    logger.info(f"Re-classified {ip} as IotStrip (child_num={child_num})")
                
                # Cache the device connection
                _device_connection_cache[cache_key] = device
                
                return device

        self._device["device"] = None
        # Input format should be either:
        # - [IP],[POWER_SWITCH_NR]
        # Optional credentials stored in calibration data as:
        # {"username": "user@example.com", "password": "password"}
        # If no credentials are provided, device will use empty/default credentials (local-only mode)

        # Use an internal caching for speeding things up.
        self.__state_cache = terrariumCache()
        self.__asyncio = terrariumAsync()

        address = self._address
        
        # Get credentials from calibration data if available
        credentials = None
        if self.calibration and isinstance(self.calibration, dict):
            username = self.calibration.get("username", "").strip()
            password = self.calibration.get("password", "").strip()
            if username and password:
                credentials = Credentials(username=username, password=password)
                logger.info(f"Using stored credentials for Kasa device at {address[0]}")
        
        try:
            self._device["device"] = self.__asyncio.run(__load_hardware(address[0], credentials))
            self._device["switch"] = 0 if len(address) == 1 else int(address[1]) - 1
        except Exception as ex:
            logger.error(f"Error loading {self} at address {address[0]}: {ex}")

        return self._device["device"]

    def _set_hardware_value(self, state):
        async def __set_hardware_state(state):
            await self.device.update()
            plug = self.device if not self.device.is_strip else self.device.children[self._device["switch"]]

            if state != 0.0:
                await plug.turn_on()
            else:
                await plug.turn_off()

            return state

        data = self.__asyncio.run(__set_hardware_state(state))

        # Update the cache after relay change
        self._get_hardware_value(True)

        return data == state

    def _get_hardware_value(self, force=False):
        async def __get_hardware_state():
            data = []
            await self.device.update()

            plugs = [self.device] if not self.device.is_strip else self.device.children
            for plug in plugs:
                data.append(plug.is_on)

            return data

        try:
            data = self.__state_cache.get_data(self._address[0])

            if data is None or force:
                data = self.__asyncio.run(__get_hardware_state())
                self.__state_cache.set_data(self._address[0], data, cache_timeout=20)

            return (
                self.ON
                if len(data) >= self._device["switch"] and terrariumUtils.is_true(data[self._device["switch"]])
                else self.OFF
            )
        except RuntimeError as err:
            logger.exception(err)
        except Exception as ex:
            logger.exception(ex)

        return None

    @staticmethod
    def _scan_relays(callback=None):
        async def __scan():
            found_devices = []

            devices = await Discover.discover()
            for ip_address in devices:
                device = devices[ip_address]

                try:
                    await device.update()
                except Exception as ex:
                    logger.warning(ex)
                    continue

                if device.is_strip:
                    for counter in range(1, len(device.children) + 1):
                        found_devices.append(
                            terrariumRelay(
                                None,
                                terrariumRelayTPLinkKasa.HARDWARE,
                                f"{device.host},{counter}",
                                f"Channel {device.children[counter-1].alias}",
                                {},
                                callback=callback,
                            )
                        )

                else:
                    found_devices.append(
                        terrariumRelay(
                            None,
                            terrariumRelayTPLinkKasa.HARDWARE,
                            f"{device.host}",
                            f"Channel {device.alias}",
                            {},
                            callback=callback,
                        )
                    )

            return found_devices

        found_devices = []
        __asyncio = terrariumAsync()
        found_devices = __asyncio.run(__scan())

        for device in found_devices:
            yield device
