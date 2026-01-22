# Pull Request: Automatic Aquarium Feeder Integration

## PR Title
`feat: Add automatic aquarium feeder support with servo-based feeding mechanism`

---

## Description

This PR introduces a new **Feeder** subsystem to TerrariumPI that enables automatic feeding of aquarium inhabitants using a servo-controlled sliding mechanism.

### What's New

- **Feeder Entity**: New database model for managing automatic feeders
- **Servo Driver**: Hardware abstraction for controlling SG90 servo motors
- **Scheduling**: Integrated with TerrariumPI's scheduling system (e.g., morning/night feedings)
- **REST API**: Complete API for managing feeders and feeding schedules
- **Web UI**: New Feeders page with visual management interface
- **Feeding History**: Automatic logging of all feeding events for monitoring

### Use Case

Users can now set up one or more automatic aquarium feeders that:
- Dispense food at configurable times (morning, night, custom)
- Control portion sizes per feeding
- Track feeding history and patterns
- Manually trigger feeding on-demand
- Test servo movement before actual feeding

---

## Implementation Overview

### Architecture

The feature follows TerrariumPI's established patterns:

1. **Database Layer** (`terrariumDatabase.py`):
   - `Feeder` entity for feeder configuration
   - `FeedingHistory` entity for event logging

2. **Hardware Layer** (`hardware/feeder/__init__.py`):
   - `terrariumFeeder` class for servo control
   - PWM-based angle positioning (0-180°)
   - Timed feed sequences with configurable timing

3. **Engine Layer** (`terrariumEngine.py`):
   - Feeder instance management
   - Schedule checking and automatic triggering
   - Callback system for status updates

4. **API Layer** (`terrariumAPI.py`):
   - RESTful endpoints for CRUD operations
   - Manual feed triggering
   - History export (CSV)

5. **Frontend Layer** (`gui/pages/Feeders.svelte`):
   - Feeder management dashboard
   - Schedule configuration UI
   - Real-time feeding trigger and testing

### Key Design Decisions

**Why a new Feeder entity instead of extending Relay?**
- Servo requires precise angle positioning, not binary ON/OFF
- Feeding requires sequential timed operations (rotate → hold → return)
- Natural fit with area-based scheduling
- Extensible for future multi-feeder scenarios

**Why PWM instead of direct GPIO control?**
- SG90 servo requires PWM signal (50Hz frequency)
- Existing PWMOutputDevice infrastructure in gpiozero
- Precise timing control and angle mapping

**Why schedule in JSON instead of separate cron table?**
- Aligns with TerrariumPI's existing patterns (Areas, relay schedules)
- Per-feeder schedule isolation
- Easy to extend with additional feed times

---

## Files Changed

### New Files
- `migrations/002_add_feeder_support.py` - Database schema
- `hardware/feeder/__init__.py` - Feeder hardware driver
- `gui/pages/Feeders.svelte` - Main feeder management page
- `gui/components/feeders/FeedersCard.svelte` - Feeder display card
- `gui/components/feeders/FeedersForm.svelte` - Feeder editor form
- `gui/components/feeders/FeedersSchedule.svelte` - Schedule management (optional)

### Modified Files
- `terrariumDatabase.py`:
  - Added `Feeder` ORM entity
  - Added `FeedingHistory` ORM entity
  - Default settings updated

- `terrariumEngine.py`:
  - Added `self.feeders` dictionary
  - Added `load_feeders()` method
  - Added `callback_feeder()` method
  - Added `check_feeder_schedules()` method
  - Added feeder schedule checking to main loop

- `terrariumAPI.py`:
  - Added 8 new routes under `/api/feeders/*`
  - Added corresponding handler methods
  - No changes to existing routes

- `gui/pages/index.js`:
  - Added import for Feeders page

---

## API Endpoints

### Feeder Management
```
GET    /api/feeders/                    - List all feeders
POST   /api/feeders/                    - Create new feeder
GET    /api/feeders/<id>/               - Get feeder detail
PUT    /api/feeders/<id>/               - Update feeder
DELETE /api/feeders/<id>/               - Delete feeder
```

### Feeder Operations
```
POST   /api/feeders/<id>/feed/          - Trigger immediate feeding
POST   /api/feeders/<id>/test/          - Test servo movement
GET    /api/feeders/<id>/history/       - Get feeding history (default: last day)
GET    /api/feeders/<id>/history/<period>/  - Get history for period (hour|day|week|month|year)
```

### Request/Response Examples

**Create Feeder**
```json
POST /api/feeders/
{
  "enclosure": "enc-123",
  "name": "Main Tank Feeder",
  "hardware": "17",
  "enabled": true,
  "servo_config": {
    "feed_angle": 90,
    "rest_angle": 0,
    "rotate_duration": 1000,
    "feed_hold_duration": 1500,
    "portion_size": 1.0
  },
  "schedule": {
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
}
```

**Manual Feed**
```json
POST /api/feeders/feed-123/feed/
{
  "portion_size": 1.5
}

Response:
{
  "status": "success",
  "message": "Feeder 'Main Tank Feeder' completed feed sequence successfully",
  "timestamp": 1705843200.0,
  "portion_size": 1.5
}
```

**Get Feeding History**
```json
GET /api/feeders/feed-123/history/day/

Response:
{
  "data": [
    {
      "timestamp": 1705824000.0,
      "status": "success",
      "portion_size": 1.0
    },
    {
      "timestamp": 1705867200.0,
      "status": "success",
      "portion_size": 1.0
    }
  ]
}
```

---

## Configuration Guide

### Servo Configuration Parameters

```javascript
servo_config: {
  feed_angle: 90,              // Angle to open mechanism (degrees, 0-180)
  rest_angle: 0,              // Angle to close mechanism (degrees, 0-180)
  rotate_duration: 1000,      // Time to rotate (milliseconds)
  feed_hold_duration: 1500,   // Time to hold at feed position (milliseconds)
  portion_size: 1.0           // Default portion per feeding (grams/units)
}
```

### Schedule Configuration

```javascript
schedule: {
  morning: {
    time: "08:00",           // HH:MM format, 24-hour
    enabled: true,           // Whether this schedule is active
    portion_size: 1.0        // Portion size for this feeding
  },
  night: {
    time: "20:00",
    enabled: true,
    portion_size: 1.0
  }
}
```

### GPIO Pin Requirements

- Use any GPIO pin that supports PWM output
- No conflicts with other hardware (sensors, relays, buttons)
- Common choices: GPIO 17, 18, 27, 22
- Power requirements: 5V for servo power, GPIO logic levels (3.3V)

### Hardware Wiring

```
SG90 Servo:
- Brown wire  → GND (Pin 6, 9, 14, 20, 25, 30, 34, 39)
- Red wire    → 5V (Pin 2, 4)
- Orange wire → GPIO (user specified, e.g., GPIO 17 = Pin 11)
```

---

## Testing Instructions

### Pre-Testing Checklist
- [ ] Raspberry Pi is running and accessible
- [ ] SG90 servo is properly wired to GPIO pin
- [ ] Servo has adequate 5V power supply
- [ ] TerrariumPI database is backed up
- [ ] No other services using the selected GPIO pin

### Unit Testing

1. **Database Migration Test**
   ```bash
   # Run migration
   python -c "from terrariumDatabase import init; init('test')"
   # Verify tables exist:
   sqlite3 data/terrariumpi.db ".tables" | grep feeder
   ```

2. **Hardware Driver Test**
   ```bash
   # Create a simple test script
   python test_feeder.py
   ```

### Integration Testing

1. **API Endpoint Test**
   ```bash
   # Get enclosures to use in feeder creation
   curl -X GET http://localhost:8090/api/enclosures/ -H "Authorization: Bearer TOKEN"
   
   # Create a test feeder
   curl -X POST http://localhost:8090/api/feeders/ \
     -H "Authorization: Bearer TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "enclosure": "ENC-ID-HERE",
       "name": "Test Feeder",
       "hardware": "17",
       "servo_config": {...}
     }'
   ```

2. **Manual Feed Test**
   ```bash
   curl -X POST http://localhost:8090/api/feeders/FEEDER-ID/feed/ \
     -H "Authorization: Bearer TOKEN" \
     -d '{"portion_size": 1.0}'
   
   # Observe servo should:
   # 1. Rotate to feed position (~1 second)
   # 2. Hold at feed position (~1.5 seconds)
   # 3. Return to rest position (~1 second)
   ```

3. **Servo Test Endpoint**
   ```bash
   curl -X POST http://localhost:8090/api/feeders/FEEDER-ID/test/ \
     -H "Authorization: Bearer TOKEN"
   
   # Same movement pattern as feed, but doesn't record history
   ```

4. **Web UI Test**
   - Navigate to http://localhost:8090
   - New "Feeders" page should appear in navigation
   - Can create feeder without errors
   - Can view feeder details
   - Can manually trigger feed from UI
   - Servo performs feeding sequence

5. **Scheduling Test**
   ```bash
   # Set schedule time to 1 minute in future
   # Wait for scheduled time
   # Observe servo triggers automatically
   # Check /api/feeders/FEEDER-ID/history/ shows entry
   ```

6. **History Export Test**
   ```bash
   curl -X GET http://localhost:8090/api/feeders/FEEDER-ID/history/day/ \
     -H "Authorization: Bearer TOKEN"
   
   # Should show CSV format with timestamp|status|portion_size
   ```

### Edge Cases to Test

- [ ] Multiple feeders on different GPIO pins
- [ ] Disable schedule and verify no auto-feeding
- [ ] Edit feeder while TerrariumPI is running
- [ ] Delete feeder - ensure hardware is cleanly stopped
- [ ] GPIO pin in use by another device - should error gracefully
- [ ] Servo not powered - should timeout gracefully
- [ ] Change schedule time and verify new time triggers
- [ ] Export history to CSV and verify format

### Regression Testing

Ensure existing features still work:
- [ ] Relays still toggle correctly
- [ ] Sensors still read values
- [ ] Buttons still register presses
- [ ] Webcams still capture images
- [ ] Calendar events still trigger
- [ ] Areas/enclosures still function
- [ ] Authentication still works
- [ ] Database backups still work

---

## Rollback Instructions

If issues occur after deployment:

1. **Disable feeders temporarily**
   ```bash
   # Comment out feeder loading in terrariumEngine.py:
   # self.load_feeders()  # Temporarily disabled
   
   # Restart TerrariumPI
   ```

2. **Full rollback (preserve data)**
   ```bash
   # Backup current database
   cp data/terrariumpi.db data/terrariumpi.db.backup
   
   # Revert all feeder files and code changes
   git revert <commit-hash>
   
   # Restart TerrariumPI
   ```

3. **Complete removal**
   ```bash
   # Revert feeder-related database changes
   sqlite3 data/terrariumpi.db "DROP TABLE feeder_history; DROP TABLE feeder;"
   
   # Remove feeder code files
   rm -rf hardware/feeder/
   rm gui/pages/Feeders.svelte
   rm -rf gui/components/feeders/
   
   # Restart TerrariumPI
   ```

---

## Monitoring & Maintenance

### Logs to Monitor
```bash
tail -f log/terrariumpi.log | grep -i feeder
```

Look for:
- Feeder loading errors on startup
- Schedule execution messages
- Servo movement logs
- Hardware errors

### Database Maintenance

1. **Feeding History Cleanup** (optional - add later)
   ```sql
   -- Remove feeding history older than 90 days
   DELETE FROM feeder_history 
   WHERE timestamp < datetime('now', '-90 days');
   ```

2. **Database Optimization**
   ```bash
   sqlite3 data/terrariumpi.db "VACUUM;"
   ```

### Performance Notes

- Feeder schedule check runs every 60 seconds (configurable)
- Feeding operation blocks for ~3.5 seconds (rotate + hold + return)
- No impact on other subsystems (separate thread)
- Database queries are indexed by feeder_id

---

## Known Limitations & Future Work

### Current Limitations
1. Schedule supports only predefined times (morning/night)
2. No conditional feeding based on sensor values
3. No support for multiple servo angles in sequence
4. Portion sizes are placeholder values (not actual weight measurement)

### Future Enhancements
- [ ] Custom scheduling (cron-like syntax)
- [ ] Sensor-based feeding (feed if water temp > X)
- [ ] Nutrition tracking dashboard
- [ ] Multiple food types/reservoirs
- [ ] Feeding statistics and trends
- [ ] Mobile push notifications on feed
- [ ] AI-driven feeding adjustments
- [ ] Integration with water quality monitoring

---

## Reviewers Checklist

- [ ] Code follows TerrariumPI patterns and conventions
- [ ] No breaking changes to existing functionality
- [ ] Database migration is reversible
- [ ] API endpoints are consistent with existing routes
- [ ] Error handling is comprehensive
- [ ] Logging is appropriate (not too verbose)
- [ ] Hardware cleanup on shutdown
- [ ] Thread safety (locks used correctly)
- [ ] UI is responsive and intuitive
- [ ] Documentation is clear and complete

---

## Questions for Reviewers

1. Should we add a REST endpoint to list available GPIO pins?
2. Should we support additional servo types (e.g., continuous rotation)?
3. Should feeding history auto-cleanup after N days?
4. Should we add webhooks for feeding events?
5. Should we support concurrent feedings or queue them?

---

## Deployment Notes

### First-Time Setup
1. Apply database migration
2. Load TerrariumPI with new code
3. Restart TerrariumPI service
4. Verify feeder page loads in web UI
5. Create first feeder via API or web UI
6. Test manual feeding
7. Verify feeding history recorded

### Upgrade from Previous Version
1. Backup database: `cp data/terrariumpi.db data/terrariumpi.db.bak`
2. Pull new code
3. Restart TerrariumPI (migration runs automatically)
4. Verify no errors in logs
5. Existing feeders (if any) will load automatically

### Production Considerations
- Test servo timing with actual food dispensing
- Adjust `rotate_duration` and `feed_hold_duration` based on mechanical response
- Monitor servo power supply under continuous operation
- Use quality servo with metal gears for long-term reliability
- Consider adding backup power (UPS) for critical feeders

---

## Summary of Changes

| Component | Change Type | Details |
|-----------|------------|---------|
| Database | New | Feeder and FeedingHistory entities |
| Hardware | New | Servo driver in hardware/feeder/ |
| Engine | Modified | Added feeder management and scheduling |
| API | New | 8 new endpoints under /api/feeders/ |
| Frontend | New | Feeders page and components |
| Total LOC | ~800 | New code |
| Total Files | +8 | New files, 3 modified |

---

## Commit Message

```
feat: Add automatic aquarium feeder support

- New Feeder entity for managing servo-based feeders
- PWM-based servo control with configurable angles and timing
- Automatic scheduling (morning/night or custom times)
- Feeding history tracking and export
- Web UI for feeder management
- REST API for full feeder control
- Support for multiple feeders per enclosure

This feature allows users to set up automatic aquarium feeders
that dispense food at scheduled times. The implementation uses
the SG90 servo motor with a sliding mechanism that opens to
release food and closes to refill.

Fixes: #XXX (if applicable)
```

---

## Contact & Support

For questions or issues:
- Review the AQUARIUM_FEEDER_IMPLEMENTATION_GUIDE.md for architectural details
- Check FEEDER_IMPLEMENTATION_CODE.md for code examples
- Consult TerrariumPI documentation for similar features (relays, sensors)

