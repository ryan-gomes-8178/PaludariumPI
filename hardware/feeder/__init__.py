# -*- coding: utf-8 -*-
"""
Aquarium feeder hardware driver for servo-based feeding mechanism

This module provides control for automatic aquarium feeders using a servo motor
that rotates to dispense food.
"""

import terrariumLogging
logger = terrariumLogging.logging.getLogger(__name__)

import time
import threading
from datetime import datetime
from gpiozero import PWMOutputDevice
from terrariumUtils import terrariumUtils

# Import gpiozero exceptions for specific error handling
try:
    from gpiozero.exc import (
        GPIODeviceError,
        GPIOPinInUse,
        PinInvalidPin,
        PinPWMUnsupported
    )
except ImportError:
    # Fallback if gpiozero.exc is not available
    GPIODeviceError = Exception
    GPIOPinInUse = Exception
    PinInvalidPin = Exception
    PinPWMUnsupported = Exception


class terrariumFeederException(Exception):
    """Base exception for feeder errors"""
    pass


class terrariumFeederHardwareException(terrariumFeederException):
    """Hardware-related feeder exception"""
    pass


class terrariumFeeder(object):
    """
    Servo-based aquarium feeder controller
    
    Controls a SG90 servo motor to dispense food at scheduled times.
    The servo rotates 90 degrees clockwise to open a sliding mechanism
    and releases food, then rotates back to rest position to refill.
    """
    
    # Default servo parameters (SG90 standard)
    DEFAULT_MIN_PULSE = 1.0  # 1ms in milliseconds (0°)
    DEFAULT_MAX_PULSE = 2.0  # 2ms in milliseconds (180°)
    DEFAULT_FREQUENCY = 50  # Hz
    
    def __init__(self, feeder_id, enclosure_id, hardware, name, servo_config, schedule, callback=None):
        """
        Initialize a feeder instance
        
        Args:
            feeder_id (str): Unique identifier
            enclosure_id (str): Parent enclosure ID
            hardware (str): GPIO pin number (as string or int)
            name (str): Human-readable name
            servo_config (dict): Servo timing and angle configuration
            schedule (dict): Feeding schedule
            callback (callable): Callback function for status updates
        """
        self.id = feeder_id
        self.enclosure_id = enclosure_id
        self.hardware = str(hardware)
        self.name = name
        self.servo_config = servo_config
        self.schedule = schedule
        self.callback = callback
        
        self._device = None
        self._lock = threading.Lock()
        self._last_feed_time = None
        
        # Load hardware PWM device
        self.load_hardware()
    
    def load_hardware(self):
        """Initialize PWM device for servo control"""
        try:
            gpio_pin = int(self.hardware)
            
            self._device = PWMOutputDevice(
                gpio_pin,
                frequency=self.DEFAULT_FREQUENCY,
                initial_value=0
            )
            logger.info(f"Loaded feeder {self.name} on GPIO {gpio_pin}")
        except ValueError as e:
            error_msg = f"Invalid GPIO pin number '{self.hardware}'. Please provide a valid GPIO pin number: {e}"
            logger.error(error_msg)
            raise terrariumFeederHardwareException(error_msg)
        except GPIOPinInUse as e:
            error_msg = f"GPIO pin {self.hardware} is already in use by another process or device. Please use a different pin or stop the conflicting process: {e}"
            logger.error(error_msg)
            raise terrariumFeederHardwareException(error_msg)
        except PinInvalidPin as e:
            error_msg = f"GPIO pin {self.hardware} is not a valid pin for this Raspberry Pi model: {e}"
            logger.error(error_msg)
            raise terrariumFeederHardwareException(error_msg)
        except PinPWMUnsupported as e:
            error_msg = f"PWM is not supported on GPIO pin {self.hardware}. Please use a PWM-capable pin: {e}"
            logger.error(error_msg)
            raise terrariumFeederHardwareException(error_msg)
        except PermissionError as e:
            error_msg = f"Permission denied accessing GPIO pin {self.hardware}. Please run with appropriate permissions or add user to gpio group: {e}"
            logger.error(error_msg)
            raise terrariumFeederHardwareException(error_msg)
        except Exception as e:
            # Generic fallback for any other unhandled exceptions
            error_msg = f"Failed to initialize GPIO pin {self.hardware}. Check hardware connections and system configuration: {e}"
            logger.error(error_msg)
            raise terrariumFeederHardwareException(error_msg)
    
    def _angle_to_pwm(self, angle):
        """
        Convert servo angle (0-180) to PWM duty cycle (0-1)
        
        SG90 servo ranges:
        - 0° = 1.0ms pulse (0.05 duty cycle at 50Hz)
        - 90° = 1.5ms pulse (0.075 duty cycle at 50Hz)
        - 180° = 2.0ms pulse (0.10 duty cycle at 50Hz)
        
        At 50Hz frequency, period = 20ms
        Duty cycle = (pulse_width_ms / 20ms) * 100 / 100
        """
        # Calculate pulse width in milliseconds (1.0-2.0ms range)
        pulse_ms = self.DEFAULT_MIN_PULSE + (angle / 180.0) * (self.DEFAULT_MAX_PULSE - self.DEFAULT_MIN_PULSE)
        # Convert to duty cycle (0-1 scale) at 50Hz
        # Period at 50Hz = 20ms, so duty cycle = pulse_ms / 20
        pwm_value = pulse_ms / 20.0
        return max(0.0, min(1.0, pwm_value))
    
    def feed(self, portion_size=None):
        """
        Execute feeding sequence:
        1. Rotate servo to feed angle (opens mechanism)
        2. Hold for feed_hold_duration
        3. Rotate servo back to rest angle (closes mechanism)
        
        Args:
            portion_size (float): Optional override portion size
            
        Returns:
            dict: Status of feeding operation
        """
        with self._lock:
            try:
                portion = portion_size or self.servo_config.get('portion_size', 1.0)
                
                logger.info(f"Feeder '{self.name}' starting feed sequence (portion: {portion})")
                
                # Extract timing from config
                rotate_duration = self.servo_config.get('rotate_duration', 1000) / 1000.0  # Convert ms to seconds
                feed_hold_duration = self.servo_config.get('feed_hold_duration', 1500) / 1000.0
                feed_angle = self.servo_config.get('feed_angle', 90)
                rest_angle = self.servo_config.get('rest_angle', 0)
                
                # Step 1: Rotate to feed position
                feed_pwm = self._angle_to_pwm(feed_angle)
                self._device.value = feed_pwm
                logger.debug(f"Feeder '{self.name}' rotating to {feed_angle}° (PWM: {feed_pwm:.3f})")
                time.sleep(rotate_duration)
                
                # Step 2: Hold position to allow food to fall
                logger.debug(f"Feeder '{self.name}' holding at feed position for {feed_hold_duration}s")
                time.sleep(feed_hold_duration)
                
                # Step 3: Return to rest position
                rest_pwm = self._angle_to_pwm(rest_angle)
                self._device.value = rest_pwm
                logger.debug(f"Feeder '{self.name}' returning to {rest_angle}° (PWM: {rest_pwm:.3f})")
                time.sleep(rotate_duration)
                
                # Center servo (stop sending pulses)
                self._device.value = 0
                
                self._last_feed_time = datetime.now()
                
                status_msg = f"Feeder '{self.name}' completed feed sequence successfully"
                logger.info(status_msg)
                
                if self.callback:
                    self.callback(self.id, 'success', portion)
                
                return {
                    'status': 'success',
                    'message': status_msg,
                    'timestamp': self._last_feed_time.timestamp(),
                    'portion_size': portion
                }
                
            except Exception as e:
                error_msg = f"Feeder '{self.name}' feed sequence failed: {e}"
                logger.error(error_msg)
                
                # Stop servo movement on error
                try:
                    self._device.value = 0
                except Exception as servo_error:
                    logger.warning(f"Failed to stop servo for feeder '{self.name}': {servo_error}")
                
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
        Test servo movement - rotate to feed position and back without waiting
        
        Returns:
            dict: Test result
        """
        with self._lock:
            try:
                feed_angle = self.servo_config.get('feed_angle', 90)
                rest_angle = self.servo_config.get('rest_angle', 0)
                rotate_duration = self.servo_config.get('rotate_duration', 1000) / 1000.0
                
                # Quick test rotation
                feed_pwm = self._angle_to_pwm(feed_angle)
                self._device.value = feed_pwm
                time.sleep(rotate_duration)
                
                rest_pwm = self._angle_to_pwm(rest_angle)
                self._device.value = rest_pwm
                time.sleep(rotate_duration)
                
                # Stop servo
                self._device.value = 0
                
                logger.info(f"Feeder '{self.name}' test movement completed successfully")
                
                return {
                    'status': 'success',
                    'message': f"Test movement completed for {self.name}"
                }
                
            except Exception as e:
                error_msg = f"Feeder '{self.name}' test movement failed: {e}"
                logger.error(error_msg)
                try:
                    self._device.value = 0
                except Exception as servo_error:
                    logger.warning(f"Failed to stop servo for feeder '{self.name}': {servo_error}")
                return {
                    'status': 'failed',
                    'message': error_msg
                }
    
    def stop(self):
        """Stop servo and cleanup"""
        try:
            if self._device:
                self._device.value = 0
                self._device.close()
                logger.info(f"Feeder '{self.name}' stopped")
        except Exception as e:
            logger.error(f"Error stopping feeder '{self.name}': {e}")
    
    def __repr__(self):
        return f"Feeder '{self.name}' on GPIO {self.hardware}"