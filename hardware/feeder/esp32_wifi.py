# -*- coding: utf-8 -*-
"""
ESP32 WiFi Wireless Feeder Driver

This module provides control for wireless automatic feeders using ESP32-C3 boards
that communicate over WiFi using a simple REST API.
"""

import terrariumLogging
logger = terrariumLogging.logging.getLogger(__name__)

import threading
import requests
from datetime import datetime


class terrariumESP32WiFiFeederException(Exception):
    """Base exception for ESP32 WiFi feeder errors"""
    pass


class terrariumESP32WiFiFeederConnectionException(terrariumESP32WiFiFeederException):
    """Connection-related feeder exception"""
    pass


class terrariumESP32WiFiFeeder(object):
    """
    ESP32 WiFi-based wireless aquarium feeder controller
    
    Communicates with an ESP32-C3 board over WiFi using HTTP REST API.
    The ESP32 handles the servo control logic locally.
    """
    
    def __init__(self, feeder_id, enclosure_id, hardware, name, servo_config, schedule, callback=None):
        """
        Initialize an ESP32 WiFi feeder instance
        
        Args:
            feeder_id (str): Unique identifier
            enclosure_id (str): Parent enclosure ID
            hardware (str): ESP32 IP address (e.g., "192.168.1.100")
            name (str): Human-readable name
            servo_config (dict): Servo timing and angle configuration (sent to ESP32)
            schedule (dict): Feeding schedule
            callback (callable): Callback function for status updates
        """
        self.id = feeder_id
        self.enclosure_id = enclosure_id
        self.hardware = str(hardware)  # IP address
        self.name = name
        self.servo_config = servo_config
        self.schedule = schedule
        self.callback = callback
        
        self._lock = threading.Lock()
        self._last_feed_time = None
        self._base_url = f"http://{self.hardware}"
        self._timeout = 5  # 5 second timeout for HTTP requests
        
        # Validate ESP32 is reachable
        self.load_hardware()
    
    def load_hardware(self):
        """Validate ESP32 is reachable"""
        try:
            response = requests.get(
                f"{self._base_url}/status",
                timeout=self._timeout
            )
            response.raise_for_status()
            status = response.json()
            logger.info(f"Loaded ESP32 WiFi feeder '{self.name}' at {self.hardware} (Battery: {status.get('battery_percent', 'N/A')}%)")
        except requests.exceptions.Timeout:
            error_msg = f"ESP32 feeder '{self.name}' at {self.hardware} is not responding (timeout)"
            logger.error(error_msg)
            raise terrariumESP32WiFiFeederConnectionException(error_msg)
        except requests.exceptions.ConnectionError:
            error_msg = f"Cannot connect to ESP32 feeder '{self.name}' at {self.hardware}. Check IP address and network."
            logger.error(error_msg)
            raise terrariumESP32WiFiFeederConnectionException(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to communicate with ESP32 feeder '{self.name}': {e}"
            logger.error(error_msg)
            raise terrariumESP32WiFiFeederConnectionException(error_msg)
    
    def feed(self, portion_size=None):
        """
        Execute feeding sequence via ESP32
        
        Args:
            portion_size (float): Optional override portion size
            
        Returns:
            dict: Status of feeding operation
        """
        with self._lock:
            try:
                portion = portion_size or self.servo_config.get('portion_size', 1.0)
                
                logger.info(f"ESP32 feeder '{self.name}' triggering feed sequence (portion: {portion})")
                
                # Send feed command with servo config to ESP32
                payload = {
                    'feed_angle': self.servo_config.get('feed_angle', 90),
                    'rest_angle': self.servo_config.get('rest_angle', 0),
                    'rotate_duration': self.servo_config.get('rotate_duration', 1000),
                    'feed_hold_duration': self.servo_config.get('feed_hold_duration', 1500),
                    'portion_size': portion
                }
                
                response = requests.post(
                    f"{self._base_url}/feed",
                    json=payload,
                    timeout=15  # Longer timeout for feed operation
                )
                response.raise_for_status()
                result = response.json()
                
                self._last_feed_time = datetime.now()
                
                status_msg = f"ESP32 feeder '{self.name}' completed feed sequence: {result.get('message', 'success')}"
                logger.info(status_msg)
                
                if self.callback:
                    self.callback(self.id, 'success', portion)
                
                return {
                    'status': 'success',
                    'message': status_msg,
                    'timestamp': self._last_feed_time.timestamp(),
                    'portion_size': portion,
                    'esp32_response': result
                }
                
            except requests.exceptions.Timeout:
                error_msg = f"ESP32 feeder '{self.name}' feed command timed out"
                logger.error(error_msg)
                
                if self.callback:
                    self.callback(self.id, 'failed', 0)
                
                return {
                    'status': 'failed',
                    'message': error_msg,
                    'timestamp': datetime.now().timestamp(),
                    'portion_size': 0
                }
                
            except Exception as e:
                error_msg = f"ESP32 feeder '{self.name}' feed sequence failed: {e}"
                logger.error(error_msg)
                
                if self.callback:
                    self.callback(self.id, 'failed', 0)
                
                return {
                    'status': 'failed',
                    'message': error_msg,
                    'timestamp': datetime.now().timestamp(),
                    'portion_size': 0
                }
    
    def test_movement(self):
        """
        Test servo movement via ESP32
        
        Returns:
            dict: Test result
        """
        with self._lock:
            try:
                payload = {
                    'feed_angle': self.servo_config.get('feed_angle', 90),
                    'rest_angle': self.servo_config.get('rest_angle', 0),
                    'rotate_duration': self.servo_config.get('rotate_duration', 1000)
                }
                
                response = requests.post(
                    f"{self._base_url}/test",
                    json=payload,
                    timeout=10
                )
                response.raise_for_status()
                result = response.json()
                
                logger.info(f"ESP32 feeder '{self.name}' test movement completed successfully")
                
                return {
                    'status': 'success',
                    'message': f"Test movement completed for {self.name}",
                    'esp32_response': result
                }
                
            except Exception as e:
                error_msg = f"ESP32 feeder '{self.name}' test movement failed: {e}"
                logger.error(error_msg)
                return {
                    'status': 'failed',
                    'message': error_msg
                }
    
    def get_status(self):
        """
        Get current status from ESP32 (battery, WiFi, last feed, etc.)
        
        Returns:
            dict: ESP32 status information
        """
        try:
            response = requests.get(
                f"{self._base_url}/status",
                timeout=self._timeout
            )
            response.raise_for_status()
            status = response.json()
            
            return {
                'online': True,
                'battery_percent': status.get('battery_percent', None),
                'battery_voltage': status.get('battery_voltage', None),
                'wifi_rssi': status.get('wifi_rssi', None),
                'last_feed': status.get('last_feed_timestamp', None),
                'error_state': status.get('error', None),
                'uptime_seconds': status.get('uptime', None)
            }
            
        except Exception as e:
            logger.warning(f"Failed to get status from ESP32 feeder '{self.name}': {e}")
            return {
                'online': False,
                'error': str(e)
            }
    
    def stop(self):
        """Cleanup (ESP32 handles its own shutdown)"""
        try:
            logger.info(f"ESP32 feeder '{self.name}' stopped (ESP32 remains powered)")
        except Exception as e:
            logger.error(f"Error stopping ESP32 feeder '{self.name}': {e}")
    
    def __repr__(self):
        return f"ESP32 WiFi Feeder '{self.name}' at {self.hardware}"
