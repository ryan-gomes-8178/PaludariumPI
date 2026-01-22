# Aquarium Feeder - Visual Reference & Diagrams

This document provides visual diagrams and quick reference charts for the aquarium feeder implementation.

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TERRARIUMPI SYSTEM                              │
└─────────────────────────────────────────────────────────────────────────┘

                              USER INTERFACES
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                           │
│  ┌────────────────────────┐              ┌──────────────────────────┐   │
│  │    Web Browser (UI)     │              │   Mobile/Terminal (API) │   │
│  │                        │              │                         │   │
│  │  Feeders Page          │              │  REST calls             │   │
│  │  - List feeders        │              │  - Create feeder        │   │
│  │  - Create/Edit forms   │◄────HTTP────►│  - Trigger feed         │   │
│  │  - Schedule config     │              │  - Get history          │   │
│  │  - Manual feed button  │              │                         │   │
│  │  - Test button         │              │                         │   │
│  └────────────────────────┘              └──────────────────────────┘   │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
                                      ▲
                                      │ HTTP/REST
                                      ▼
                   ┌──────────────────────────────────┐
                   │   Bottle Web Framework (API)     │
                   │                                  │
                   │ Routes: /api/feeders/*           │
                   │ Handlers: feeder_* methods       │
                   │ Authentication: Required         │
                   └────────────┬─────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
         ┌────────────┐  ┌────────────┐  ┌────────────┐
         │  Database  │  │   Engine   │  │  Hardware  │
         │            │  │            │  │            │
         │ Feeder ORM │  │ Schedule   │  │ Servo      │
         │ History    │  │ Manage     │  │ Control    │
         │ Enclosure  │  │ Timing     │  │            │
         └────────────┘  └────────────┘  └────────────┘

                           CORE COMPONENTS
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                           │
│  DATABASE LAYER (SQLite + Pony ORM)                                      │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                                                                 │    │
│  │  Feeder Table:              FeedingHistory Table:              │    │
│  │  ├─ id (UUID)              ├─ feeder_id (FK)                  │    │
│  │  ├─ enclosure_id (FK)      ├─ timestamp (datetime)             │    │
│  │  ├─ name (string)          ├─ status (success/failed)         │    │
│  │  ├─ hardware (GPIO)        └─ portion_size (float)            │    │
│  │  ├─ servo_config (JSON)                                        │    │
│  │  ├─ schedule (JSON)         One feeder has many history       │    │
│  │  └─ enabled (bool)          entries (one per feed action)      │    │
│  │                                                                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ENGINE LAYER (Python threading)                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                                                                 │    │
│  │  On Startup:                                                   │    │
│  │  └─► load_feeders() ──► Load all from database ──► Instantiate  │    │
│  │                                                                 │    │
│  │  Main Loop (every iteration):                                  │    │
│  │  └─► check_feeder_schedules() ──► Check if time to feed ──────► │    │
│  │                                   Trigger feed in thread        │    │
│  │                                                                 │    │
│  │  On Feed Complete:                                             │    │
│  │  └─► callback_feeder() ──► Record in FeedingHistory            │    │
│  │                                                                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  HARDWARE LAYER (gpiozero + PWM)                                        │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                                                                 │    │
│  │  terrariumFeeder Class:                                        │    │
│  │                                                                 │    │
│  │  feed() ──┬─► Rotate to feed_angle (PWM signal)               │    │
│  │           │                                                    │    │
│  │           ├─► Hold for feed_hold_duration (ms)                │    │
│  │           │                                                    │    │
│  │           └─► Rotate to rest_angle (PWM signal)               │    │
│  │                                                                 │    │
│  │  test_movement() ──► Quick test without recording              │    │
│  │                                                                 │    │
│  │  _angle_to_pwm(angle) ──► Convert 0-180° to PWM value (0-1)   │    │
│  │                                                                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────────┐
                    │   Hardware (GPIO Pin + PWM) │
                    │          (GPIO 17)          │
                    └────────────┬────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────────┐
                    │   SG90 Servo Motor          │
                    │   - Brown: GND              │
                    │   - Red: 5V                 │
                    │   - Orange: PWM Signal      │
                    └────────────┬────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────────┐
                    │   Feeding Mechanism         │
                    │   - Opens @ 90°             │
                    │   - Closes @ 0°             │
                    │   - Dispenses food          │
                    └─────────────────────────────┘
```

---

## Data Flow Diagram: Scheduled Feeding

```
TIME: 08:00 (Morning schedule time)
      ▼
┌─────────────────────────────────┐
│ Engine Main Loop Iteration      │
│ (runs every second)             │
└──────────────┬──────────────────┘
               │
               ▼
    ┌──────────────────────────┐
    │ check_feeder_schedules() │
    │ Get current time: 08:00  │
    └──────────────┬───────────┘
                   │
         Query database:
         SELECT * FROM feeder
         WHERE enabled=true
                   │
                   ▼
        ┌──────────────────────┐
        │ For each feeder:     │
        │ schedule['morning']  │
        │ time = 08:00? ✓      │
        └──────────┬───────────┘
                   │
    Check if already fed this minute:
    SELECT * FROM feeder_history
    WHERE timestamp > now-1min
                   │
                   ▼ (No recent history found)
        ┌──────────────────────┐
        │ Trigger feeding in   │
        │ background thread    │
        │ (don't block main)   │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ terrariumFeeder      │
        │ .feed()              │
        │ (portion_size=1.0)   │
        └──────────┬───────────┘
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
    ┌────────────┐      ┌──────────────┐
    │ Rotate to  │      │ Hold 1.5s    │
    │ 90° (1s)   │      │ Food falls   │
    └────────────┘      └──────────────┘
         │                   │
         └─────────┬─────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ Rotate back to 0°    │
        │ (1s)                 │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ callback_feeder()    │
        │ status='success'     │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ INSERT FeedingHistory│
        │ feeder_id: FEEDER-1  │
        │ timestamp: 08:00:15  │
        │ status: success      │
        │ portion: 1.0         │
        └──────────────────────┘
                   │
                   ▼ (repeat next scheduled time)
        "✓ Feeding recorded"
```

---

## File Structure Diagram

```
TerrariumPI/
│
├── migrations/
│   ├── 001_*.py (existing)
│   └── 002_add_feeder_support.py ◄─── NEW
│
├── hardware/
│   ├── sensor/
│   ├── relay/
│   ├── button/
│   ├── webcam/
│   └── feeder/ ◄───────────────────── NEW DIRECTORY
│       └── __init__.py ◄───────────── NEW (terrariumFeeder class)
│
├── gui/
│   ├── pages/
│   │   ├── Relays.svelte
│   │   ├── Sensors.svelte
│   │   └── Feeders.svelte ◄────────── NEW
│   │
│   └── components/
│       ├── feeders/ ◄───────────────── NEW DIRECTORY
│       │   ├── FeedersCard.svelte ◄── NEW
│       │   ├── FeedersForm.svelte ◄── NEW
│       │   └── FeedersSchedule.svelte  (optional)
│       │
│       └── ... (other components)
│
├── terrariumDatabase.py ◄───────────── MODIFIED (add Feeder + FeedingHistory)
├── terrariumEngine.py ◄─────────────── MODIFIED (add feeder methods)
├── terrariumAPI.py ◄──────────────────MODIFIED (add feeder routes)
│
└── data/
    └── terrariumpi.db (Feeder & FeedingHistory tables added)
```

---

## Servo PWM Timing Diagram

```
50Hz PWM Signal (Standard for SG90 servo)

Period = 1/50Hz = 20ms

│                    20ms (one period)
│◄──────────────────────────────────────┤
│                                        │
├────────────────────────────────────────┼────────────────────
│                                        │
│ Pulse high                  Pulse low  │
│◄────────┤                  ├───────────┤
│  0.5ms   1.5ms   2.5ms               │
│  ├──────────┤    ├──────────┤        │
│  0°        90°   180°                │
│                                      │
│ Higher pulse = Higher angle          │
│ Lower pulse = Lower angle            │


Our Feeder Configuration:

├─ rest_angle: 0° = 0.5ms pulse ────────► Low PWM signal
├─ feed_angle: 90° = 1.5ms pulse ───────► Mid PWM signal
└─ unused: 180° = 2.5ms pulse ──────────► High PWM signal

gpiozero PWMOutputDevice:
  value = 0.0  ──► 0% duty → All low (0ms pulse) ──► Stop signal
  value = 0.025 ──► 2.5% duty → 0.5ms pulse ──────► 0° (rest)
  value = 0.075 ──► 7.5% duty → 1.5ms pulse ──────► 90° (feed)
  value = 0.125 ──► 12.5% duty → 2.5ms pulse ─────► 180°

Our implementation uses _angle_to_pwm() to calculate these values
```

---

## API Request/Response Flow

```
CLIENT (curl, browser, mobile)
   │
   ▼
═══════════════════════════════════════════════════════════
   POST /api/feeders/
   Authorization: Bearer TOKEN
   Content-Type: application/json
   
   {
     "enclosure": "enc-123",
     "name": "Tank Feeder",
     "hardware": "17",
     ...config...
   }
═══════════════════════════════════════════════════════════
   │
   ▼
BOTTLE FRAMEWORK (routes & decorators)
   │
   ├─► authentication() ──► Validate token
   │
   ▼
TERRARIUMAPI.feeder_add() method
   │
   ├─► Validate enclosure exists
   │
   ├─► Create Feeder object
   │   INSERT INTO feeder (...)
   │
   ├─► Commit to database
   │
   ├─► Load into engine
   │   engine.load_feeders()
   │
   ▼
RESPONSE ◄─────────────────┐
═══════════════════════════│═════════════════════════════════
   200 OK                 │
   Content-Type: application/json
   
   {
     "id": "feeder-abc123",
     "enclosure": "enc-123",
     "name": "Tank Feeder",
     ...
   }
═══════════════════════════════════════════════════════════
   ▲
   │
CLIENT receives response
```

---

## Schedule Matching Logic

```
Database record:
schedule = {
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

Check at runtime:
Current time: 08:00:45 ──┐
                         ├─► Format as "HH:MM" ──► "08:00"
                         │
                         ├─► Compare with schedule["morning"]["time"]
                         │   "08:00" == "08:00" ✓
                         │
                         ├─► Check enabled flag ✓
                         │
                         ├─► Check if already fed in last minute
                         │   SELECT * FROM feeder_history
                         │   WHERE timestamp > now - 1min
                         │   (to prevent duplicate feeding)
                         │
                         └─► TRIGGER FEED!

Current time: 08:01:00 ──┐
                         ├─► "08:01" != "08:00"
                         └─► SKIP (no match)

Current time: 20:00:00 ──┐
                         ├─► "20:00" == "20:00" ✓
                         ├─► Check schedule["night"]["time"]
                         └─► TRIGGER FEED!
```

---

## Feeder States & Transitions

```
┌──────────────────────────────────┐
│      FEEDER STATES               │
└──────────────────────────────────┘

               ┌────────────┐
               │   IDLE     │ ◄─── Initial state
               │ (servo=0°) │ ◄─── After feeding complete
               └─────┬──────┘
                     │
                     │ Manual feed trigger
                     │ Schedule time reached
                     │ API POST /feed/
                     ▼
               ┌────────────┐
               │  ROTATING  │ ──► Servo rotating to 90°
               │ (0° → 90°) │     Duration: rotate_duration ms
               └─────┬──────┘
                     │
                     ▼
               ┌────────────┐
               │  FEEDING   │ ──► Servo at 90°, food falling
               │ (holding)  │     Duration: feed_hold_duration ms
               └─────┬──────┘
                     │
                     ▼
               ┌────────────┐
               │ RESTORING  │ ──► Servo rotating back to 0°
               │ (90° → 0°) │     Duration: rotate_duration ms
               └─────┬──────┘
                     │
                     ▼
               ┌────────────┐
               │   IDLE     │ ──► Wait for next schedule/trigger
               │ (servo=0°) │
               └────────────┘
                     ▲
                     │
              (if error occurs anywhere,
               go directly to IDLE,
               record status='failed')
```

---

## Database Schema Relationship

```
┌────────────────────────────────┐
│         ENCLOSURE              │
│                                │
│ id ──────────┐                 │
│ name         │                 │
│ image        │                 │
│ description  │                 │
└────────────┬─┘                 │
             │                   │
             │ 1:N               │
             │ (one enclosure    │
             │  many feeders)    │
             │                   │
             ▼                   │
┌────────────────────────────────┐
│          FEEDER                │
│                                │
│ id ──────────┐                 │
│ enclosure_id ┼───────────► FK to Enclosure
│ name         │                 │
│ hardware     │                 │
│ servo_config │                 │
│ schedule     │                 │
│ enabled      │                 │
│ notification │                 │
└────────────┬─┘                 │
             │                   │
             │ 1:N               │
             │ (one feeder       │
             │  many history)    │
             │                   │
             ▼                   │
┌────────────────────────────────┐
│      FEEDER_HISTORY            │
│                                │
│ feeder_id ───────────────► FK to Feeder
│ timestamp                      │
│ status                         │
│ portion_size                   │
│                                │
│ PK = (feeder_id, timestamp)   │
└────────────────────────────────┘


Example query:
  SELECT fh.* FROM feeder_history fh
  JOIN feeder f ON fh.feeder_id = f.id
  JOIN enclosure e ON f.enclosure_id = e.id
  WHERE e.id = 'enc-123'
  AND fh.timestamp > datetime('now', '-7 days')
  ORDER BY fh.timestamp DESC;

(Get all feeding history for an enclosure in the last 7 days)
```

---

## Component Interaction Diagram

```
┌──────────────────────────────────────────────────┐
│         FEEDERS PAGE (Svelte)                    │
│                                                  │
│  Displays list of feeders                        │
│  ├─ Load feeders on mount                        │
│  ├─ Show loading spinner                         │
│  └─ Render FeedersCard for each                  │
└──────────────────────────────────────────────────┘
           │                          │
           │                          │
    [Edit button]              [Delete button]
           │                          │
           ▼                          ▼
    ┌──────────────┐         ┌──────────────┐
    │ FeedersForm  │         │ Confirm      │
    │ (Modal)      │         │ Delete       │
    │              │         │              │
    │ • Edit fields│         │ Delete via   │
    │ • Save       │         │ API          │
    │ • Cancel     │         └──────────────┘
    └──────────────┘
           │
           │ (also shows FeedersCard)
           │
           ▼
    ┌──────────────┐
    │ FeedersCard  │
    │ (Reusable)   │
    │              │
    │ • Name       │ ◄─── [Feed Now button]
    │ • Status     │      (POST /api/feeders/<id>/feed/)
    │ • Details    │
    │ • Actions    │ ◄─── [Test button]
    │              │      (POST /api/feeders/<id>/test/)
    │ • Edit       │
    │ • Delete     │
    │ • Feed Now   │
    │ • Test       │
    └──────────────┘
           │
           └─────► All call REST API endpoints
                   (/api/feeders/*)
```

---

## Thread Safety Model

```
Single Main Thread (Engine Loop):
  ├─► Checks schedule every iteration
  ├─► Never blocks
  └─► Spawns feeding in background thread

Background Thread (Feed Operation):
  ├─► Acquires lock (self._lock)
  ├─► Rotates servo (blocks ~3.5 seconds)
  ├─► Updates state
  ├─► Releases lock
  └─► Calls callback

Callback (Async):
  ├─► Records history in database
  └─► Updates UI via WebSocket (optional)

Result:
  ✓ Feed operation doesn't block engine
  ✓ Multiple feeders safe (each has own lock)
  ✓ Schedule checking always responsive
  ✓ No race conditions (serialized database writes)
```

---

## Configuration Validation Flow

```
User submits form
        │
        ▼
┌─────────────────────────┐
│ Frontend Validation     │
├─────────────────────────┤
│ • Name not empty?       │
│ • Enclosure selected?   │
│ • GPIO is number?       │
│ • Angles 0-180?         │
│ • Timings > 0?          │
└────────┬────────────────┘
         │ If valid
         ▼
POST /api/feeders/
         │
         ▼
┌─────────────────────────┐
│ Backend Validation      │
├─────────────────────────┤
│ • Authentication check  │
│ • Enclosure exists?     │
│ • Hardware available?   │
│ • GPIO not in use?      │
│ • Config valid JSON?    │
└────────┬────────────────┘
         │ If valid
         ▼
┌─────────────────────────┐
│ Hardware Initialization │
├─────────────────────────┤
│ • Load GPIO device      │
│ • Test PWM signal       │
│ • Return to rest state  │
└────────┬────────────────┘
         │ If successful
         ▼
┌─────────────────────────┐
│ Store in Database       │
│ Load into Engine        │
│ Return 200 + feeder data│
└─────────────────────────┘
```

---

## Quick Reference Tables

### Servo Parameter Reference

| Parameter | Range | Default | Unit | Notes |
|-----------|-------|---------|------|-------|
| feed_angle | 0-180 | 90 | degrees | Angle to open mechanism |
| rest_angle | 0-180 | 0 | degrees | Angle to close mechanism |
| rotate_duration | 100-3000 | 1000 | ms | Time to rotate 90° |
| feed_hold_duration | 100-5000 | 1500 | ms | Time to hold at feed position |
| portion_size | 0.1-10.0 | 1.0 | g/units | Food amount per feeding |

### Common GPIO Pins (Raspberry Pi)

| Pin | BCM | Available | Notes |
|-----|-----|-----------|-------|
| 11 | 17 | ✓ | Most common, good for servo |
| 12 | 18 | ✓ | PWM capable |
| 16 | 23 | ✓ | Safe default |
| 18 | 24 | ✓ | Safe default |
| 22 | 27 | ✓ | Safe default |
| 13 | 22 | ? | Check for conflicts |

### HTTP Status Codes

| Code | Meaning | When |
|------|---------|------|
| 200 | OK | Successful operation |
| 201 | Created | Feeder created |
| 400 | Bad Request | Invalid input |
| 401 | Unauthorized | Missing/invalid token |
| 404 | Not Found | Feeder doesn't exist |
| 500 | Server Error | Hardware error |

---

## Performance Characteristics

```
Feed Operation Timing:
├─ Rotate to feed angle: ~1000ms
├─ Hold for feeding: ~1500ms
├─ Rotate back to rest: ~1000ms
├─ Motor stop signal: ~100ms
└─ Total: ~3.6 seconds

Schedule Check Timing:
├─ Run every main loop iteration: ~1 second
├─ Database query: ~10ms
├─ Time comparison: <1ms
└─ Feed thread spawn: <1ms

Database Operations:
├─ Insert feeder: ~50ms
├─ Update feeder: ~30ms
├─ Query feeders: ~20ms
├─ Insert history: ~40ms
└─ Query history: ~15ms

Memory Usage:
├─ Per feeder instance: ~2MB
├─ 10 feeders: ~20MB
├─ Database file (10k history): ~5MB
└─ Total overhead: minimal (<50MB)
```

---

End of Visual Reference

