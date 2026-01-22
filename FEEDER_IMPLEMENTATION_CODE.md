# Aquarium Feeder - Complete Implementation Code

This document contains all the exact code blocks needed to implement the aquarium feeder feature.

## 1. Database Migration File

**File:** `migrations/002_add_feeder_support.py`

```python
"""
Add support for automatic aquarium feeders
"""

steps = [
    # Create feeder_status type
    "CREATE TABLE feeder(id TEXT PRIMARY KEY, enclosure TEXT NOT NULL, name TEXT NOT NULL, hardware TEXT NOT NULL, enabled BOOLEAN DEFAULT 1, servo_config TEXT NOT NULL, schedule TEXT NOT NULL, notification BOOLEAN DEFAULT 1, FOREIGN KEY(enclosure) REFERENCES enclosure(id))",
    
    "CREATE TABLE feeder_history(feeder TEXT NOT NULL, timestamp TEXT NOT NULL, status TEXT NOT NULL, portion_size REAL DEFAULT 0, PRIMARY KEY(feeder, timestamp), FOREIGN KEY(feeder) REFERENCES feeder(id))",
]

def forward(backend):
    cursor = backend.cursor()
    for step in steps:
        cursor.execute(step)

def backward(backend):
    cursor = backend.cursor()
    cursor.execute("DROP TABLE IF EXISTS feeder_history")
    cursor.execute("DROP TABLE IF EXISTS feeder")
```

## 2. Database ORM Models

**File:** `terrariumDatabase.py` - Add these classes at the end (before the final functions)

```python
class Feeder(db.Entity):
    """Automatic aquarium feeder entity"""
    
    id = orm.PrimaryKey(str, default=terrariumUtils.generate_uuid)
    enclosure = orm.Required(lambda: Enclosure)
    name = orm.Required(str)
    hardware = orm.Required(str)  # GPIO pin number or hardware address
    
    enabled = orm.Optional(bool, default=True)
    notification = orm.Optional(bool, default=True)
    
    # Servo configuration as JSON
    # {
    #   "feed_angle": 90,
    #   "rest_angle": 0,
    #   "rotate_duration": 1000,  # milliseconds
    #   "feed_hold_duration": 1500,  # milliseconds
    #   "portion_size": 1.0
    # }
    servo_config = orm.Required(orm.Json)
    
    # Schedule as JSON
    # {
    #   "morning": {"time": "08:00", "enabled": true, "portion_size": 1.0},
    #   "night": {"time": "20:00", "enabled": true, "portion_size": 1.0}
    # }
    schedule = orm.Required(orm.Json, default={})
    
    # Feeding history
    history = orm.Set("FeedingHistory")
    
    def to_dict(self, only=None, exclude=None, with_collections=False, with_lazy=False, related_objects=False):
        data = copy.deepcopy(super().to_dict(only, exclude, with_collections, with_lazy, related_objects))
        # Add computed fields if needed
        return data
    
    def __repr__(self):
        return f"Feeder '{self.name}' for enclosure '{self.enclosure.name}'"


class FeedingHistory(db.Entity):
    """Record of each feeding event"""
    
    feeder = orm.Required("Feeder")
    timestamp = orm.Required(datetime)
    status = orm.Required(str)  # 'success', 'failed', 'partial'
    portion_size = orm.Optional(float, default=0)  # in grams or portions
    
    orm.PrimaryKey(feeder, timestamp)
    
    def __repr__(self):
        return f"Feeding {self.feeder.name} at {self.timestamp} - {self.status}"
```

## 3. Hardware Feeder Driver

**File:** `hardware/feeder/__init__.py` (create new file)

```python
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
    DEFAULT_MIN_PULSE = 0.5 / 1000  # 0.5ms in seconds
    DEFAULT_MAX_PULSE = 2.5 / 1000  # 2.5ms in seconds
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
            # Convert to BCM pin number if needed
            bcm_pin = terrariumUtils.to_BCM_port_number(str(gpio_pin))
            
            self._device = PWMOutputDevice(
                bcm_pin,
                frequency=self.DEFAULT_FREQUENCY,
                initial_value=0
            )
            logger.info(f"Loaded feeder {self.name} on GPIO {gpio_pin}")
        except Exception as e:
            logger.error(f"Failed to load feeder hardware: {e}")
            raise terrariumFeederHardwareException(f"Cannot load GPIO {self.hardware}: {e}")
    
    def _angle_to_pwm(self, angle):
        """
        Convert servo angle (0-180) to PWM pulse value (0-1)
        
        SG90 servo ranges:
        - 0° = 0.5ms pulse (0.025 on 0-1 scale at 50Hz)
        - 90° = 1.5ms pulse (0.075 on 0-1 scale at 50Hz)
        - 180° = 2.5ms pulse (0.125 on 0-1 scale at 50Hz)
        """
        pulse_ms = self.DEFAULT_MIN_PULSE + (angle / 180.0) * (self.DEFAULT_MAX_PULSE - self.DEFAULT_MIN_PULSE)
        # Convert to 0-1 scale for gpiozero (period = 1/frequency)
        period = 1.0 / self.DEFAULT_FREQUENCY
        pwm_value = pulse_ms / period
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
                except:
                    pass
                
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
                except:
                    pass
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
```

## 4. Engine Integration

**File:** `terrariumEngine.py` - Add to the class

In the `__init__` method, add after other hardware initialization:

```python
        # Feeder initialization
        self.feeders = {}
```

Add this new method to the class:

```python
    def load_feeders(self):
        """Load all feeders from database"""
        from terrariumDatabase import Feeder as FeedersDB
        from hardware.feeder import terrariumFeeder
        
        self.feeders = {}
        
        @orm.db_session
        def _load():
            for feeder_data in orm.select(f for f in FeedersDB):
                try:
                    feeder = terrariumFeeder(
                        feeder_data.id,
                        feeder_data.enclosure.id,
                        feeder_data.hardware,
                        feeder_data.name,
                        feeder_data.servo_config,
                        feeder_data.schedule,
                        callback=self.callback_feeder
                    )
                    self.feeders[feeder_data.id] = feeder
                    logger.info(f"Loaded feeder: {feeder_data.name}")
                except Exception as e:
                    logger.error(f"Failed to load feeder {feeder_data.name}: {e}")
        
        _load()
    
    def callback_feeder(self, feeder_id, status, portion_size):
        """Callback when feeder operation completes"""
        from terrariumDatabase import Feeder, FeedingHistory
        
        @orm.db_session
        def _update():
            try:
                feeder = Feeder[feeder_id]
                FeedingHistory(
                    feeder=feeder,
                    timestamp=datetime.now(),
                    status=status,
                    portion_size=portion_size if status == 'success' else 0
                )
                orm.commit()
            except Exception as e:
                logger.error(f"Failed to record feeding history: {e}")
        
        _update()
    
    def check_feeder_schedules(self):
        """Check if any feeders should be fed based on schedule"""
        from terrariumDatabase import Feeder
        
        @orm.db_session
        def _check():
            for feeder_id, feeder in self.feeders.items():
                try:
                    feeder_db = Feeder[feeder_id]
                    if not feeder_db.enabled:
                        continue
                    
                    schedule = feeder_db.schedule
                    now = datetime.now()
                    current_time = now.strftime("%H:%M")
                    
                    for feed_name, feed_config in schedule.items():
                        if not feed_config.get('enabled', True):
                            continue
                        
                        if feed_config.get('time') == current_time:
                            # Check if we already fed in this minute
                            last_history = feeder_db.history.filter(
                                lambda h: h.timestamp >= now - timedelta(minutes=1)
                            ).order_by(orm.desc(FeedingHistory.timestamp)).first()
                            
                            if not last_history:
                                portion = feed_config.get('portion_size', feeder_db.servo_config.get('portion_size', 1.0))
                                # Run in thread to avoid blocking
                                threading.Thread(
                                    target=feeder.feed,
                                    args=(portion,),
                                    daemon=True
                                ).start()
                except Exception as e:
                    logger.error(f"Error checking feeder schedule: {e}")
        
        _check()
```

Add to the main engine loop (in the `_Engine__run` method, add this check):

```python
            self.check_feeder_schedules()
```

Add imports at top of terrariumEngine.py if not already present:

```python
from hardware.feeder import terrariumFeeder, terrariumFeederException
```

## 5. REST API Endpoints

**File:** `terrariumAPI.py` - Add these routes and methods

In the `routes()` method, add these route definitions:

```python
        # Feeder API
        bottle_app.route(
            "/api/feeders/<feeder:path>/history/<period:re:(hour|day|week|month|year|custom)>/",
            "GET",
            self.feeder_history,
            apply=self.authentication(False),
            name="api:feeder_history_period",
        )
        bottle_app.route(
            "/api/feeders/<feeder:path>/history/",
            "GET",
            self.feeder_history,
            apply=self.authentication(False),
            name="api:feeder_history",
        )
        bottle_app.route(
            "/api/feeders/<feeder:path>/feed/",
            "POST",
            self.feeder_manual_feed,
            apply=self.authentication(),
            name="api:feeder_manual_feed",
        )
        bottle_app.route(
            "/api/feeders/<feeder:path>/test/",
            "POST",
            self.feeder_test,
            apply=self.authentication(),
            name="api:feeder_test",
        )
        bottle_app.route(
            "/api/feeders/<feeder:path>/",
            "GET",
            self.feeder_detail,
            apply=self.authentication(False),
            name="api:feeder_detail",
        )
        bottle_app.route(
            "/api/feeders/<feeder:path>/",
            "PUT",
            self.feeder_update,
            apply=self.authentication(),
            name="api:feeder_update",
        )
        bottle_app.route(
            "/api/feeders/<feeder:path>/",
            "DELETE",
            self.feeder_delete,
            apply=self.authentication(),
            name="api:feeder_delete",
        )
        bottle_app.route(
            "/api/feeders/",
            "GET",
            self.feeder_list,
            apply=self.authentication(False),
            name="api:feeder_list",
        )
        bottle_app.route(
            "/api/feeders/",
            "POST",
            self.feeder_add,
            apply=self.authentication(),
            name="api:feeder_add",
        )
```

Add these methods to the terrariumAPI class (before the final comment or at a logical location):

```python
    # Feeders
    @orm.db_session(sql_debug=DEBUG, show_values=DEBUG)
    def feeder_list(self):
        from terrariumDatabase import Feeder
        return {
            "data": [
                self.feeder_detail(feeder.id)
                for feeder in Feeder.select(lambda f: not f.id in self.webserver.engine.settings["exclude_ids"])
            ]
        }
    
    @orm.db_session(sql_debug=DEBUG, show_values=DEBUG)
    def feeder_detail(self, feeder):
        from terrariumDatabase import Feeder
        try:
            feeder_obj = Feeder[feeder]
            return feeder_obj.to_dict()
        except orm.core.ObjectNotFound:
            raise HTTPError(status=404, body=f"Feeder with id {feeder} does not exist.")
        except Exception as ex:
            raise HTTPError(status=500, body=f"Error getting feeder {feeder} detail. {ex}")
    
    @orm.db_session(sql_debug=DEBUG, show_values=DEBUG)
    def feeder_add(self):
        from terrariumDatabase import Feeder, Enclosure
        try:
            # Verify enclosure exists
            _ = Enclosure[request.json["enclosure"]]
            
            feeder = Feeder(
                enclosure=Enclosure[request.json["enclosure"]],
                name=request.json["name"],
                hardware=request.json["hardware"],
                servo_config=request.json.get("servo_config", {
                    "feed_angle": 90,
                    "rest_angle": 0,
                    "rotate_duration": 1000,
                    "feed_hold_duration": 1500,
                    "portion_size": 1.0
                }),
                schedule=request.json.get("schedule", {})
            )
            orm.commit()
            
            # Load feeder into engine
            self.webserver.engine.load_feeders()
            
            return self.feeder_detail(feeder.id)
        except orm.core.ObjectNotFound:
            raise HTTPError(status=404, body=f'Enclosure with id {request.json.get("enclosure")} does not exist.')
        except Exception as ex:
            raise HTTPError(status=500, body=f"Feeder could not be added. {ex}")
    
    @orm.db_session(sql_debug=DEBUG, show_values=DEBUG)
    def feeder_update(self, feeder):
        from terrariumDatabase import Feeder
        try:
            feeder_obj = Feeder[feeder]
            feeder_obj.name = request.json.get("name", feeder_obj.name)
            feeder_obj.enabled = request.json.get("enabled", feeder_obj.enabled)
            feeder_obj.servo_config = request.json.get("servo_config", feeder_obj.servo_config)
            feeder_obj.schedule = request.json.get("schedule", feeder_obj.schedule)
            feeder_obj.notification = request.json.get("notification", feeder_obj.notification)
            orm.commit()
            
            # Reload feeder into engine
            self.webserver.engine.load_feeders()
            
            return self.feeder_detail(feeder_obj.id)
        except orm.core.ObjectNotFound:
            raise HTTPError(status=404, body=f"Feeder with id {feeder} does not exist.")
        except Exception as ex:
            raise HTTPError(status=500, body=f"Error updating feeder {feeder}. {ex}")
    
    @orm.db_session(sql_debug=DEBUG, show_values=DEBUG)
    def feeder_delete(self, feeder):
        from terrariumDatabase import Feeder
        try:
            feeder_obj = Feeder[feeder]
            message = f"Feeder {feeder_obj.name} is deleted."
            
            # Stop feeder hardware
            if feeder in self.webserver.engine.feeders:
                self.webserver.engine.feeders[feeder].stop()
                del self.webserver.engine.feeders[feeder]
            
            feeder_obj.delete()
            orm.commit()
            
            return {"message": message}
        except orm.core.ObjectNotFound:
            raise HTTPError(status=404, body=f"Feeder with id {feeder} does not exist.")
        except Exception as ex:
            raise HTTPError(status=500, body=f"Error deleting feeder {feeder}. {ex}")
    
    @orm.db_session(sql_debug=DEBUG, show_values=DEBUG)
    def feeder_manual_feed(self, feeder):
        try:
            if feeder not in self.webserver.engine.feeders:
                raise HTTPError(status=404, body=f"Feeder with id {feeder} is not loaded.")
            
            portion_size = request.json.get("portion_size") if request.json else None
            result = self.webserver.engine.feeders[feeder].feed(portion_size)
            
            return result
        except HTTPError:
            raise
        except Exception as ex:
            raise HTTPError(status=500, body=f"Error triggering feed: {ex}")
    
    @orm.db_session(sql_debug=DEBUG, show_values=DEBUG)
    def feeder_test(self, feeder):
        try:
            if feeder not in self.webserver.engine.feeders:
                raise HTTPError(status=404, body=f"Feeder with id {feeder} is not loaded.")
            
            result = self.webserver.engine.feeders[feeder].test_movement()
            
            return result
        except HTTPError:
            raise
        except Exception as ex:
            raise HTTPError(status=500, body=f"Error testing feeder: {ex}")
    
    @orm.db_session(sql_debug=DEBUG, show_values=DEBUG)
    def feeder_history(self, feeder, action="history", period="day"):
        from terrariumDatabase import Feeder, FeedingHistory
        
        try:
            feeder_obj = Feeder[feeder]
            
            if "hour" == period:
                period_days = 1 / 24
            elif "day" == period:
                period_days = 1
            elif "week" == period:
                period_days = 7
            elif "month" == period:
                period_days = 31
            elif "year" == period:
                period_days = 365
            else:
                period_days = 1
            
            start_date = datetime.now() - timedelta(days=period_days)
            
            history = [
                {
                    "timestamp": item.timestamp.timestamp(),
                    "status": item.status,
                    "portion_size": item.portion_size
                }
                for item in feeder_obj.history.filter(lambda h: h.timestamp >= start_date)
            ]
            
            if "export" == action:
                csv_data = [";".join(["timestamp", "status", "portion_size"])]
                for data_point in history:
                    data_point["timestamp"] = datetime.fromtimestamp(data_point["timestamp"])
                    csv_data.append(";".join([str(value) for value in data_point.values()]))
                
                response.headers["Content-Type"] = "application/csv"
                response.headers["Content-Disposition"] = f"attachment; filename={feeder_obj.name}_{period}.csv"
                return "\n".join(csv_data)
            
            return {"data": history}
        
        except orm.core.ObjectNotFound:
            raise HTTPError(status=404, body=f"Feeder with id {feeder} does not exist.")
        except Exception as ex:
            raise HTTPError(status=500, body=f"Error getting feeder history: {ex}")
```

---

## 6. Frontend Page Component

**File:** `gui/pages/Feeders.svelte` (create new file)

```svelte
<script>
  import { onMount } from 'svelte';
  import FeedersCard from '../components/feeders/FeedersCard.svelte';
  import FeedersForm from '../components/feeders/FeedersForm.svelte';
  import { apiCall } from '../helpers/api';

  let feeders = [];
  let showForm = false;
  let selectedFeeder = null;
  let loading = true;
  let error = '';

  onMount(() => {
    loadFeeders();
  });

  async function loadFeeders() {
    try {
      loading = true;
      const response = await apiCall('/api/feeders/', 'GET');
      feeders = response.data || [];
    } catch (e) {
      error = e.message;
      console.error('Error loading feeders:', e);
    } finally {
      loading = false;
    }
  }

  function handleAddFeeder() {
    selectedFeeder = null;
    showForm = true;
  }

  function handleEditFeeder(feeder) {
    selectedFeeder = feeder;
    showForm = true;
  }

  function handleFormClose() {
    showForm = false;
    selectedFeeder = null;
  }

  function handleFormSave() {
    loadFeeders();
    handleFormClose();
  }

  function handleDeleteFeeder(feeder) {
    if (confirm(`Are you sure you want to delete ${feeder.name}?`)) {
      apiCall(`/api/feeders/${feeder.id}/`, 'DELETE')
        .then(() => loadFeeders())
        .catch(e => {
          error = e.message;
          console.error('Error deleting feeder:', e);
        });
    }
  }
</script>

<div class="feeders-page">
  <div class="page-header">
    <h1>Aquarium Feeders</h1>
    <button class="btn btn-primary" on:click={handleAddFeeder}>+ Add Feeder</button>
  </div>

  {#if error}
    <div class="alert alert-danger">{error}</div>
  {/if}

  {#if loading}
    <p>Loading feeders...</p>
  {:else if feeders.length === 0}
    <p class="text-muted">No feeders configured yet.</p>
  {:else}
    <div class="feeders-grid">
      {#each feeders as feeder (feeder.id)}
        <FeedersCard
          {feeder}
          on:edit={() => handleEditFeeder(feeder)}
          on:delete={() => handleDeleteFeeder(feeder)}
          on:reload={loadFeeders}
        />
      {/each}
    </div>
  {/if}

  {#if showForm}
    <FeedersForm
      feeder={selectedFeeder}
      on:close={handleFormClose}
      on:save={handleFormSave}
    />
  {/if}
</div>

<style>
  .feeders-page {
    padding: 20px;
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 30px;
  }

  .feeders-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 20px;
  }
</style>
```

## 7. Frontend Components

**File:** `gui/components/feeders/FeedersCard.svelte` (create new file)

```svelte
<script>
  import { createEventDispatcher } from 'svelte';
  import { apiCall } from '../../helpers/api';

  export let feeder;

  const dispatch = createEventDispatcher();
  let isFeedingNow = false;

  async function triggerManualFeed() {
    try {
      isFeedingNow = true;
      await apiCall(`/api/feeders/${feeder.id}/feed/`, 'POST', {});
      dispatch('reload');
    } catch (e) {
      console.error('Feed error:', e);
    } finally {
      isFeedingNow = false;
    }
  }

  async function testServo() {
    try {
      await apiCall(`/api/feeders/${feeder.id}/test/`, 'POST', {});
    } catch (e) {
      console.error('Test error:', e);
    }
  }
</script>

<div class="feeder-card">
  <div class="card-header">
    <h3>{feeder.name}</h3>
    <div class="status">
      {#if feeder.enabled}
        <span class="badge badge-success">Enabled</span>
      {:else}
        <span class="badge badge-secondary">Disabled</span>
      {/if}
    </div>
  </div>

  <div class="card-body">
    <div class="info-row">
      <label>Enclosure:</label>
      <span>{feeder.enclosure}</span>
    </div>
    <div class="info-row">
      <label>GPIO:</label>
      <span>{feeder.hardware}</span>
    </div>
    <div class="info-row">
      <label>Portion Size:</label>
      <span>{feeder.servo_config.portion_size}g</span>
    </div>
  </div>

  <div class="card-actions">
    <button
      class="btn btn-sm btn-success"
      on:click={triggerManualFeed}
      disabled={isFeedingNow}
    >
      {isFeedingNow ? 'Feeding...' : 'Feed Now'}
    </button>
    <button class="btn btn-sm btn-info" on:click={testServo}>
      Test
    </button>
    <button class="btn btn-sm btn-warning" on:click={() => dispatch('edit')}>
      Edit
    </button>
    <button class="btn btn-sm btn-danger" on:click={() => dispatch('delete')}>
      Delete
    </button>
  </div>
</div>

<style>
  .feeder-card {
    border: 1px solid #ddd;
    border-radius: 8px;
    overflow: hidden;
  }

  .card-header {
    background-color: #f5f5f5;
    padding: 15px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .card-header h3 {
    margin: 0;
    font-size: 18px;
  }

  .card-body {
    padding: 15px;
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    font-size: 14px;
  }

  .info-row label {
    font-weight: bold;
    color: #666;
  }

  .card-actions {
    padding: 15px;
    background-color: #f9f9f9;
    display: flex;
    gap: 5px;
    flex-wrap: wrap;
  }

  .btn {
    flex: 1;
    min-width: 70px;
  }
</style>
```

**File:** `gui/components/feeders/FeedersForm.svelte` (create new file)

```svelte
<script>
  import { createEventDispatcher } from 'svelte';
  import { apiCall } from '../../helpers/api';

  export let feeder = null;

  const dispatch = createEventDispatcher();
  let formData = feeder ? { ...feeder } : {
    name: '',
    enclosure: '',
    hardware: '',
    enabled: true,
    servo_config: {
      feed_angle: 90,
      rest_angle: 0,
      rotate_duration: 1000,
      feed_hold_duration: 1500,
      portion_size: 1.0
    },
    schedule: {
      morning: { time: '08:00', enabled: true, portion_size: 1.0 },
      night: { time: '20:00', enabled: true, portion_size: 1.0 }
    }
  };

  let enclosures = [];
  let isSaving = false;
  let error = '';

  async function loadEnclosures() {
    try {
      const response = await apiCall('/api/enclosures/', 'GET');
      enclosures = response.data || [];
    } catch (e) {
      console.error('Error loading enclosures:', e);
    }
  }

  async function handleSubmit() {
    try {
      isSaving = true;
      error = '';

      if (feeder) {
        // Update
        await apiCall(`/api/feeders/${feeder.id}/`, 'PUT', formData);
      } else {
        // Create
        await apiCall('/api/feeders/', 'POST', formData);
      }

      dispatch('save');
    } catch (e) {
      error = e.message;
      console.error('Form error:', e);
    } finally {
      isSaving = false;
    }
  }

  function handleCancel() {
    dispatch('close');
  }

  onMount(loadEnclosures);
</script>

<div class="modal-overlay" on:click={handleCancel}>
  <div class="modal" on:click|stopPropagation>
    <div class="modal-header">
      <h2>{feeder ? 'Edit' : 'Add'} Feeder</h2>
      <button class="btn-close" on:click={handleCancel}>&times;</button>
    </div>

    <form on:submit|preventDefault={handleSubmit}>
      {#if error}
        <div class="alert alert-danger">{error}</div>
      {/if}

      <div class="form-group">
        <label for="name">Name:</label>
        <input
          id="name"
          type="text"
          bind:value={formData.name}
          required
          placeholder="e.g., Main Tank Feeder"
        />
      </div>

      <div class="form-group">
        <label for="enclosure">Enclosure:</label>
        <select id="enclosure" bind:value={formData.enclosure} required>
          <option value="">Select an enclosure</option>
          {#each enclosures as enc (enc.id)}
            <option value={enc.id}>{enc.name}</option>
          {/each}
        </select>
      </div>

      <div class="form-group">
        <label for="hardware">GPIO Pin:</label>
        <input
          id="hardware"
          type="text"
          bind:value={formData.hardware}
          required
          placeholder="e.g., 17"
        />
      </div>

      <div class="form-group">
        <label>
          <input type="checkbox" bind:checked={formData.enabled} />
          Enabled
        </label>
      </div>

      <div class="form-section">
        <h4>Servo Configuration</h4>

        <div class="form-row">
          <div class="form-group">
            <label for="feed_angle">Feed Angle:</label>
            <input
              id="feed_angle"
              type="number"
              bind:value={formData.servo_config.feed_angle}
              min="0"
              max="180"
            />
          </div>

          <div class="form-group">
            <label for="rest_angle">Rest Angle:</label>
            <input
              id="rest_angle"
              type="number"
              bind:value={formData.servo_config.rest_angle}
              min="0"
              max="180"
            />
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="rotate_duration">Rotate Duration (ms):</label>
            <input
              id="rotate_duration"
              type="number"
              bind:value={formData.servo_config.rotate_duration}
              min="100"
            />
          </div>

          <div class="form-group">
            <label for="feed_hold_duration">Feed Hold Duration (ms):</label>
            <input
              id="feed_hold_duration"
              type="number"
              bind:value={formData.servo_config.feed_hold_duration}
              min="100"
            />
          </div>
        </div>

        <div class="form-group">
          <label for="portion_size">Portion Size (g):</label>
          <input
            id="portion_size"
            type="number"
            bind:value={formData.servo_config.portion_size}
            min="0.1"
            step="0.1"
          />
        </div>
      </div>

      <div class="form-section">
        <h4>Feeding Schedule</h4>

        {#each Object.entries(formData.schedule) as [schedName, schedData] (schedName)}
          <div class="schedule-item">
            <div class="form-row">
              <div class="form-group">
                <label for="{schedName}-time">
                  {schedName.charAt(0).toUpperCase() + schedName.slice(1)} Time:
                </label>
                <input
                  id="{schedName}-time"
                  type="time"
                  bind:value={schedData.time}
                />
              </div>

              <div class="form-group">
                <label for="{schedName}-portion">Portion Size:</label>
                <input
                  id="{schedName}-portion"
                  type="number"
                  bind:value={schedData.portion_size}
                  min="0.1"
                  step="0.1"
                />
              </div>

              <div class="form-group checkbox">
                <label>
                  <input type="checkbox" bind:checked={schedData.enabled} />
                  Enabled
                </label>
              </div>
            </div>
          </div>
        {/each}
      </div>

      <div class="form-actions">
        <button type="button" class="btn btn-secondary" on:click={handleCancel}>
          Cancel
        </button>
        <button type="submit" class="btn btn-primary" disabled={isSaving}>
          {isSaving ? 'Saving...' : 'Save'}
        </button>
      </div>
    </form>
  </div>
</div>

<style>
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .modal {
    background: white;
    border-radius: 8px;
    width: 90%;
    max-width: 600px;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    border-bottom: 1px solid #eee;
  }

  .btn-close {
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #666;
  }

  form {
    padding: 20px;
  }

  .form-group {
    margin-bottom: 15px;
  }

  .form-group label {
    display: block;
    margin-bottom: 5px;
    font-weight: 500;
  }

  .form-group input[type='text'],
  .form-group input[type='number'],
  .form-group input[type='time'],
  .form-group select {
    width: 100%;
    padding: 8px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 14px;
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 15px;
  }

  .form-section {
    margin-top: 20px;
    padding-top: 20px;
    border-top: 1px solid #eee;
  }

  .form-section h4 {
    margin-top: 0;
    margin-bottom: 15px;
  }

  .schedule-item {
    margin-bottom: 15px;
    padding: 10px;
    background-color: #f9f9f9;
    border-radius: 4px;
  }

  .checkbox {
    display: flex;
    align-items: center;
  }

  .checkbox input[type='checkbox'] {
    margin-right: 8px;
    width: auto;
  }

  .form-actions {
    display: flex;
    gap: 10px;
    margin-top: 20px;
    padding-top: 20px;
    border-top: 1px solid #eee;
  }

  .form-actions button {
    flex: 1;
  }
</style>
```

---

## Required Imports

Add these to `terrariumAPI.py` if not already present:

```python
from terrariumDatabase import Feeder, FeedingHistory
from datetime import datetime, timedelta
```

Add these to `terrariumEngine.py` if not already present:

```python
from terrariumDatabase import Feeder, FeedingHistory
```

---

## Notes

- All servo angles are in degrees (0-180)
- All timing values are in milliseconds
- PWM frequency for SG90 servo is 50Hz (standard)
- Schedule times must be in HH:MM format (24-hour)
- Feeding history is automatically recorded in the database
- Multiple feeders are fully supported
- Thread-safe feeding operations (uses locks)

