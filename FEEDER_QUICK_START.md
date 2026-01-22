# Aquarium Feeder - Quick Start Implementation Guide

This guide provides a streamlined, step-by-step path to implement the aquarium feeder feature in the fastest way possible.

---

## Implementation Roadmap (MVP - 2-3 hours)

### Phase 1: Database Setup (15 min)

1. **Create migration file** `migrations/002_add_feeder_support.py`
   - Copy code from `FEEDER_IMPLEMENTATION_CODE.md` section 1

2. **Update `terrariumDatabase.py`**
   - Add Feeder class
   - Add FeedingHistory class
   - (Code provided in section 2)

3. **Verify migration**
   ```bash
   python terrariumPI.py  # Should run migration on startup
   sqlite3 data/terrariumpi.db ".schema" | grep feeder
   ```

### Phase 2: Hardware Driver (30 min)

1. **Create** `hardware/feeder/__init__.py`
   - Copy complete class from `FEEDER_IMPLEMENTATION_CODE.md` section 3
   - This is the core servo control logic

2. **Verify imports in `terrariumEngine.py`**
   ```python
   from hardware.feeder import terrariumFeeder
   ```

### Phase 3: Engine Integration (20 min)

1. **Add to `terrariumEngine.__init__`**
   ```python
   self.feeders = {}
   self.load_feeders()  # Call in __init__
   ```

2. **Add three methods** to `terrariumEngine` class
   - `load_feeders()` - Initialize feeders from database
   - `callback_feeder()` - Record feeding in history
   - `check_feeder_schedules()` - Check if should feed now

3. **Add to main engine loop**
   - In `_Engine__run` method, call `self.check_feeder_schedules()` every iteration

### Phase 4: API Routes (30 min)

1. **Update `terrariumAPI.routes()` method**
   - Add 8 new route definitions (copy from section 5)

2. **Add 8 handler methods** to terrariumAPI class
   - `feeder_list()`, `feeder_detail()`, `feeder_add()`, `feeder_update()`, `feeder_delete()`
   - `feeder_manual_feed()`, `feeder_test()`, `feeder_history()`
   - (Complete code in section 5)

### Phase 5: Frontend UI (45 min)

1. **Create** `gui/pages/Feeders.svelte`
   - Main page showing list of feeders
   - Add/Edit/Delete buttons
   - Manual feed button

2. **Create** `gui/components/feeders/FeedersCard.svelte`
   - Display individual feeder
   - Quick actions

3. **Create** `gui/components/feeders/FeedersForm.svelte`
   - Form for adding/editing feeders
   - Schedule configuration
   - Servo timing config

4. **Update** `gui/pages/index.js`
   ```javascript
   import Feeders from './Feeders.svelte';
   // Add to routes
   ```

### Phase 6: Testing & Verification (30 min)

See **Testing Instructions** in `FEEDER_PR_DESCRIPTION.md`

---

## File-by-File Checklist

### ✅ New Files (Create these)

```
□ migrations/002_add_feeder_support.py (code provided)
□ hardware/feeder/__init__.py (code provided)
□ gui/pages/Feeders.svelte (code provided)
□ gui/components/feeders/FeedersCard.svelte (code provided)
□ gui/components/feeders/FeedersForm.svelte (code provided)
```

### ✅ Modified Files (Edit these)

```
□ terrariumDatabase.py
  - Add Feeder class (after line ~300)
  - Add FeedingHistory class (after Feeder)

□ terrariumEngine.py
  - Add self.feeders = {} in __init__
  - Add load_feeders() method
  - Add callback_feeder() method
  - Add check_feeder_schedules() method
  - Import terrariumFeeder at top
  - Call check_feeder_schedules() in main loop

□ terrariumAPI.py
  - Add feeder routes in routes() method
  - Add all 8 handler methods

□ gui/pages/index.js
  - Import Feeders component
  - Add to route exports
```

---

## Minimal Test Script

Before deploying, run this to verify basic functionality:

**File:** `test_feeder_basic.py`

```python
#!/usr/bin/env python3
"""Basic feeder functionality test"""

import sys
import time
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from terrariumDatabase import init as init_db, db, Feeder, Enclosure
from pony import orm

# Initialize database
init_db("4.14.0")

@orm.db_session
def test_feeder_creation():
    """Test creating a feeder"""
    try:
        # Get or create test enclosure
        enclosure = orm.select(e for e in Enclosure).first()
        if not enclosure:
            print("ERROR: No enclosure found. Create one first via web UI.")
            return False
        
        # Create test feeder
        feeder = Feeder(
            enclosure=enclosure,
            name="Test Feeder",
            hardware="17",
            servo_config={
                "feed_angle": 90,
                "rest_angle": 0,
                "rotate_duration": 1000,
                "feed_hold_duration": 1500,
                "portion_size": 1.0
            },
            schedule={
                "morning": {"time": "08:00", "enabled": True, "portion_size": 1.0}
            }
        )
        orm.commit()
        
        print(f"✓ Created feeder: {feeder}")
        
        # Try to retrieve it
        retrieved = Feeder[feeder.id]
        print(f"✓ Retrieved feeder: {retrieved}")
        
        # Clean up
        feeder.delete()
        orm.commit()
        print("✓ Deleted feeder")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_feeder_creation()
    sys.exit(0 if success else 1)
```

Run with:
```bash
python test_feeder_basic.py
```

Expected output:
```
✓ Created feeder: Feeder 'Test Feeder' on GPIO 17
✓ Retrieved feeder: Feeder 'Test Feeder' on GPIO 17
✓ Deleted feeder
```

---

## Common Issues & Solutions

### Issue: Migration fails
**Solution:**
- Check `migrations/` directory exists
- Verify `002_add_feeder_support.py` has correct SQL syntax
- Check database is not locked: `lsof data/terrariumpi.db`

### Issue: Feeder doesn't load in engine
**Solution:**
- Check `hardware/feeder/__init__.py` exists
- Verify `from hardware.feeder import terrariumFeeder` in engine
- Check logs: `tail -f log/terrariumpi.log | grep feeder`

### Issue: Servo doesn't move
**Solution:**
- Verify GPIO pin is correct (common: 17, 18, 27, 22)
- Check servo has 5V power (test with multimeter)
- Verify no other hardware using that GPIO
- Test: `gpio readall` to see pin state
- Run servo test via API: `POST /api/feeders/<id>/test/`

### Issue: API returns 404 on feeder routes
**Solution:**
- Verify routes added to `bottle_app.route()` in `routes()` method
- Restart TerrariumPI after code changes
- Check route decorator has correct path
- Verify authentication parameter correct

### Issue: UI doesn't show Feeders page
**Solution:**
- Check `gui/pages/Feeders.svelte` created
- Verify `gui/pages/index.js` imports Feeders
- Check browser console for JavaScript errors
- Clear browser cache (Ctrl+Shift+Delete)
- Restart TerrariumPI webserver

### Issue: Database migration already exists error
**Solution:**
- Migration file must be numbered higher than latest
- Check existing migrations: `ls migrations/`
- Use next number: `002_` if latest is `001_`

---

## Before Going Live

### Hardware Checklist
- [ ] Servo has 5V power supply (not USB, need actual 5V PSU)
- [ ] Servo signal wire on correct GPIO pin
- [ ] Servo moves to 0° and 90° smoothly
- [ ] Mechanism dispenses food when at 90°
- [ ] Mechanism refills when returning to 0°
- [ ] No mechanical binding or grinding sounds

### Software Checklist
- [ ] Database migration runs without errors
- [ ] Feeders page loads in web UI
- [ ] Can create feeder via UI
- [ ] API returns feeder data correctly
- [ ] Manual feed triggers via UI
- [ ] Servo moves smoothly via API
- [ ] Feeding history recorded in database
- [ ] Schedule triggers correctly (test with time set 2 min in future)
- [ ] Multiple feeders work independently
- [ ] Deleting feeder cleans up hardware

### Security Checklist
- [ ] Feeder API requires authentication (check apply=self.authentication())
- [ ] Non-admin users cannot create/edit feeders
- [ ] Sensitive config not logged
- [ ] No hardcoded GPIO pins in frontend

---

## Performance Notes

- Database: ~50KB per 1000 feeding records (can add cleanup task later)
- CPU: Schedule check runs 1x per minute (~0.1% CPU)
- Memory: Each feeder instance ~2MB (negligible)
- Concurrent Feedings: Queued (one at a time)

---

## What You Should Know

### Why This MVP Design?

1. **Simple**: Minimal new code, maximum reuse of existing patterns
2. **Safe**: Doesn't touch relay/sensor/button code
3. **Extensible**: Easy to add features later (nutrition tracking, etc.)
4. **Testable**: Can test each component independently

### Why Not Include [X]?

- **Nutrition tracking**: Can add later with weight sensor
- **Custom schedules**: Start with 2 predefined (morning/night)
- **Mobile app**: Use REST API directly
- **Conditional feeding**: Can add sensor integration later
- **Multiple food types**: One mechanism per feeder for MVP

### Why This Architecture?

- **Feeder vs Relay**: Feeders need precise control, not binary
- **PWM servo**: Industry standard, well-supported
- **Schedule in JSON**: Aligns with TerrariumPI patterns
- **History tracking**: Enables future analytics

---

## Next Steps After MVP

Once MVP is working:

1. **Add sensor integration**
   - Feed only if water temp > 20°C
   - Feed only if CO2 < 50ppm

2. **Add nutrition tracking**
   - Manual log of food amount
   - Dashboard showing consumption

3. **Add alerts**
   - Email/Telegram when feed fails
   - Food tank low warning

4. **Add analytics**
   - Feeding patterns over time
   - Consumption trends

5. **Add mobile support**
   - Phone notification on feed
   - Remote trigger via push

---

## Support Resources

### Documentation Files
- `AQUARIUM_FEEDER_IMPLEMENTATION_GUIDE.md` - Architecture overview
- `FEEDER_IMPLEMENTATION_CODE.md` - Complete code
- `FEEDER_PR_DESCRIPTION.md` - Testing guide
- This file - Quick start

### TerrariumPI Resources
- `README.md` - Project overview
- `terrariumEngine.py` - Engine patterns to follow
- `hardware/relay/__init__.py` - Similar hardware pattern
- `terrariumAPI.py` - API endpoint patterns

### External Resources
- SG90 Servo: https://www.electronicwings.com/nodemcu/servo-motor-esp8266
- gpiozero PWM: https://gpiozero.readthedocs.io/en/stable/api_boards.html#pwmoutputdevice
- Pony ORM: https://docs.ponyorm.org/

---

## Quick Reference: Code Locations

| What | Where | Lines |
|------|-------|-------|
| Servo PWM logic | `hardware/feeder/__init__.py` | 60-100 |
| Feed sequence | `hardware/feeder/__init__.py` | 140-200 |
| Schedule check | `terrariumEngine.py` | Added method |
| API routes | `terrariumAPI.py` | routes() method |
| DB models | `terrariumDatabase.py` | End of file |

---

## Version Control

When committing, use:

```bash
git add .
git commit -m "feat: add aquarium feeder support

- New Feeder entity for servo-based feeding
- PWM servo control with configurable timing
- Automatic scheduling and manual triggers
- Feeding history tracking
- Web UI for feeder management
- 8 new REST API endpoints

Closes #XXX"
```

---

## Still Have Questions?

1. **Architecture question?** → See `AQUARIUM_FEEDER_IMPLEMENTATION_GUIDE.md`
2. **Code question?** → See `FEEDER_IMPLEMENTATION_CODE.md`
3. **Testing question?** → See `FEEDER_PR_DESCRIPTION.md`
4. **How to implement?** → This file (Quick Start)

---

Good luck with your aquarium feeder implementation! 🐠

