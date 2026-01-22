# TerrariumPI Aquarium Feeder Implementation Guide

## Executive Summary

This guide provides a **minimal viable product (MVP)** implementation for integrating an automatic aquarium feeder with a SG90 servo motor into TerrariumPI. The approach leverages the existing PWM-dimmer relay infrastructure to control the servo with scheduled feeding events.

**Total Implementation Time:** ~2-3 hours  
**Complexity Level:** Medium  
**Files to Modify/Create:** ~12 files  

---

## Architecture Decision & Design Approach

### Why NOT a Relay?
While the servo *could* be controlled through the relay system, treating it as a traditional relay is problematic:
- Traditional relays are binary (ON/OFF)
- Servo requires **specific angle positions** (0°, 90°, 180°)
- Servo requires **timed hold positions** (rotate, pause, rotate back)

### Chosen Approach: **Feeder Entity** (Recommended for MVP)

Instead of forcing the servo into the relay model, we'll create a **dedicated Feeder entity** that:
1. **Uses the PWM relay backend** to control the servo motor
2. **Encapsulates feeding logic** (rotate CW, pause, rotate CCW)
3. **Integrates with Area scheduling** (like lights/water temperature control)
4. **Stores feeding history** (for monitoring consumption patterns)

**Benefits:**
- Clean separation of concerns
- Extensible for multiple feeders
- Natural fit with TerrariumPI's scheduling system (Areas)
- Can add nutritional tracking later

---

## High-Level Architecture

### Database Schema Changes
```
New Entity: Feeder
├── id (UUID)
├── enclosure_id (FK to Enclosure)
├── name (string)
├── hardware (PWM relay address/GPIO pin)
├── schedule (JSON - cron-like schedules)
├── servo_config (JSON - timing and angles)
│   ├── feed_angle: 90
│   ├── rest_angle: 0
│   ├── feed_duration: 1500ms (time to hold at feed angle)
│   ├── rotate_speed: 1000ms (time to rotate 90 degrees)
│   └── portion_size: 1 (grams, for tracking)
└── history (Set of FeedingHistory)

New Entity: FeedingHistory
├── feeder_id (FK)
├── timestamp
├── status (success|failed|partial)
└── portion_size
```

### Backend API Changes
```
POST   /api/feeders/                         - List all feeders
GET    /api/feeders/<id>/                    - Get feeder detail
POST   /api/feeders/                         - Create new feeder
PUT    /api/feeders/<id>/                    - Update feeder
DELETE /api/feeders/<id>/                    - Delete feeder
POST   /api/feeders/<id>/feed/                - Trigger immediate feeding
POST   /api/feeders/<id>/test/                - Test servo movement
GET    /api/feeders/<id>/history/<period>/   - Get feeding history
```

### Frontend Changes
```
gui/pages/
└── Feeders.svelte                (Main page for feeder management)

gui/components/
├── feeders/
│   ├── FeedersCard.svelte        (Display individual feeders)
│   ├── FeedersForm.svelte        (Add/edit feeder)
│   ├── FeedersHistory.svelte     (View feeding history)
│   └── FeedersSchedule.svelte    (Schedule management)
```

### Backend Engine Changes
```
terrariumEngine.py
├── self.feeders = {}             (Dictionary of feeder instances)
└── load_feeders()                (Initialize feeders from DB)

New File: hardware/feeder/__init__.py
├── terrariumFeeder class         (Base feeder implementation)
└── Hardware abstraction for servo control
```

---

## Step-by-Step Implementation

### Phase 1: Database Schema (15 minutes)

Create migration file for new Feeder and FeedingHistory entities.

**File:** `migrations/002_add_feeder_support.py`

### Phase 2: Backend Database Models (20 minutes)

**File:** `terrariumDatabase.py` - Add Feeder and FeedingHistory ORM entities

### Phase 3: Hardware Feeder Driver (30 minutes)

**File:** `hardware/feeder/__init__.py` - Create terrariumFeeder class

This class will:
- Inherit from base feeder pattern
- Control PWM relay (servo)
- Implement feed/rest sequences
- Handle servo timing

### Phase 4: Engine Integration (20 minutes)

**File:** `terrariumEngine.py`
- Add feeders dictionary
- Load feeders from database on startup
- Add scheduling logic (execute at scheduled times)

### Phase 5: REST API Endpoints (30 minutes)

**File:** `terrariumAPI.py`
- Add all /api/feeders/* routes
- Implement CRUD operations
- Add history export

### Phase 6: Frontend UI (45 minutes)

**Files:** Multiple Svelte components for feeder management

### Phase 7: Testing & Documentation (30 minutes)

---

## Implementation Details by File

### 1. Database Migration File

**Path:** `migrations/002_add_feeder_support.py`

Creates the Feeder and FeedingHistory tables.

### 2. Feeder ORM Models

**Path:** `terrariumDatabase.py` (append to file)

```python
class Feeder(db.Entity):
    id = orm.PrimaryKey(str, default=terrariumUtils.generate_uuid)
    enclosure = orm.Required(lambda: Enclosure)
    name = orm.Required(str)
    hardware = orm.Required(str)  # GPIO pin for PWM
    
    enabled = orm.Optional(bool, default=True)
    
    # Servo configuration as JSON
    servo_config = orm.Required(orm.Json)
    # Schedule as JSON: {"morning": "08:00", "night": "20:00"}
    schedule = orm.Required(orm.Json, default={})
    
    notification = orm.Optional(bool, default=True)
    
    history = orm.Set("FeedingHistory")
    
    def to_dict(self):
        return copy.deepcopy(super().to_dict())

class FeedingHistory(db.Entity):
    feeder = orm.Required("Feeder")
    timestamp = orm.Required(datetime)
    status = orm.Required(str)  # 'success', 'failed', 'partial'
    portion_size = orm.Optional(float, default=0)
    
    orm.PrimaryKey(feeder, timestamp)
```

### 3. Hardware Feeder Driver

**Path:** `hardware/feeder/__init__.py`

This is the core of the implementation. It will:
- Use GPIO to control the servo via PWM relay
- Implement the feed sequence
- Handle timing and error conditions

### 4. Engine Integration

**Path:** `terrariumEngine.py`

Add to `__init__`:
```python
self.feeders = {}
```

Add method:
```python
def load_feeders(self):
    """Load all feeders from database"""
    for feeder_data in orm.select(f for f in Feeder):
        self.feeders[feeder_data.id] = terrariumFeeder(feeder_data)
```

Add to main loop:
```python
self._check_feeder_schedules()
```

### 5. REST API Endpoints

**Path:** `terrariumAPI.py`

Add routes for:
- `GET /api/feeders/` - List feeders
- `POST /api/feeders/` - Create feeder
- `GET /api/feeders/<id>/` - Get feeder detail
- `PUT /api/feeders/<id>/` - Update feeder
- `DELETE /api/feeders/<id>/` - Delete feeder
- `POST /api/feeders/<id>/feed/` - Manual feed
- `POST /api/feeders/<id>/test/` - Test servo
- `GET /api/feeders/<id>/history/<period>/` - History export

### 6. Frontend Components

**Path:** `gui/pages/Feeders.svelte`

Main page showing:
- List of feeders
- Status indicators
- Quick action buttons

**Path:** `gui/components/feeders/FeedersForm.svelte`

Form for creating/editing feeders with:
- Name input
- Hardware selection (GPIO pins)
- Schedule configuration (time picker for morning/night)
- Servo timing config (angles, rotation time, hold time)

**Path:** `gui/components/feeders/FeedersSchedule.svelte`

Visual schedule builder showing:
- Feeding times per day
- Quick enable/disable
- Test feed button

---

## Configuration Examples

### Servo Config (JSON)
```json
{
  "feed_angle": 90,
  "rest_angle": 0,
  "rotate_duration": 1000,
  "feed_hold_duration": 1500,
  "portion_size": 1.0,
  "return_to_rest": true
}
```

### Schedule Config (JSON)
```json
{
  "morning": {
    "time": "08:00",
    "enabled": true,
    "portion_size": 1.0
  },
  "night": {
    "time": "20:00",
    "enabled": true,
    "portion_size": 1.0
  }
}
```

---

## Testing Checklist

- [ ] Database migration runs without errors
- [ ] Feeder can be created via API
- [ ] Manual feed trigger rotates servo correctly
- [ ] Servo returns to rest position
- [ ] Feeding history is recorded
- [ ] Schedule triggers feeding at correct times
- [ ] UI displays feeders correctly
- [ ] UI allows schedule editing
- [ ] Multiple feeders can be created
- [ ] Feeder can be deleted cleanly

---

## Future Enhancements (Not MVP)

1. **Multiple food types** - Different schedules for different feeders
2. **Nutrition tracking** - Monitor what/how much was fed
3. **Consumption patterns** - Analytics dashboard
4. **Integration with sensors** - Condition feeding on water parameters
5. **Mobile notifications** - Alert on feed success/failure
6. **Variable portion sizes** - AI-driven feeding adjustments
7. **Backup battery** - Solar-powered feeder support

---

## Deployment Notes

### Hardware Requirements
- GPIO pin available for PWM signal
- SG90 servo connected to 5V, GND, and GPIO pin
- Power supply rated for servo draw

### GPIO Configuration
- Use GPIO pin that supports PWM output
- Ensure no conflicts with other hardware
- Default frequency: 50Hz (standard for servo)

### Software Requirements
- `gpiozero` library (already installed)
- `pigpio` daemon running (for PWM legacy mode)

---

## Rollback Strategy

If integration causes issues:
1. Remove Feeder routes from `terrariumAPI.py`
2. Revert database migration
3. Remove feeder loading from `terrariumEngine.py`
4. Remove `hardware/feeder/` directory

All existing functionality remains intact.

---

## Success Criteria

✅ **MVP Success:**
1. Feeder can be created with schedule
2. Servo rotates at scheduled times
3. Feeding history is recorded
4. UI allows basic management
5. Multiple feeders supported

✅ **No Breaking Changes:**
1. All existing features work
2. No regression in relay/sensor/button functionality
3. Database migrations are reversible

---

