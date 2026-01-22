# File Checklist & Creation Instructions

## Complete File Listing

### 📄 Documentation Files (Already Created)

```
✅ AQUARIUM_FEEDER_IMPLEMENTATION_GUIDE.md
   └─ Architecture, design decisions, implementation phases
   └─ ~600 lines

✅ FEEDER_IMPLEMENTATION_CODE.md
   └─ Complete, production-ready code for all components
   └─ ~1200 lines (includes all code blocks)

✅ FEEDER_PR_DESCRIPTION.md
   └─ PR template, API docs, testing guide, deployment
   └─ ~800 lines

✅ FEEDER_QUICK_START.md
   └─ Fast implementation path, checklist, troubleshooting
   └─ ~700 lines

✅ IMPLEMENTATION_SUMMARY.md
   └─ Overview, timeline, file reference
   └─ ~500 lines

✅ VISUAL_REFERENCE.md
   └─ Diagrams, data flows, quick reference tables
   └─ ~700 lines

📌 CREATE_FILES_CHECKLIST.md (this file)
   └─ Instructions for creating implementation files
```

---

## Code Files to Create (8 New Files)

### 1️⃣ Database Migration

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

**Status:** Copy from `FEEDER_IMPLEMENTATION_CODE.md` section 1

---

### 2️⃣ Hardware Driver

**File:** `hardware/feeder/__init__.py`

**Status:** Copy from `FEEDER_IMPLEMENTATION_CODE.md` section 3 (~300 lines)

**Create:** New directory first: `mkdir -p hardware/feeder/`

---

### 3️⃣ Frontend - Main Page

**File:** `gui/pages/Feeders.svelte`

**Status:** Copy from `FEEDER_IMPLEMENTATION_CODE.md` section 6 (~180 lines)

---

### 4️⃣ Frontend - Feeder Card Component

**File:** `gui/components/feeders/FeedersCard.svelte`

**Status:** Copy from `FEEDER_IMPLEMENTATION_CODE.md` section 7 (~130 lines)

**Create:** New directory first: `mkdir -p gui/components/feeders/`

---

### 5️⃣ Frontend - Feeder Form Component

**File:** `gui/components/feeders/FeedersForm.svelte`

**Status:** Copy from `FEEDER_IMPLEMENTATION_CODE.md` section 7 (~350 lines)

---

### 6️⃣ Database Models

**File:** `terrariumDatabase.py`

**Status:** Add to end of file (before final functions) - `FEEDER_IMPLEMENTATION_CODE.md` section 2

**Lines to add:** ~80 lines (two ORM classes)

---

### 7️⃣ Engine Integration

**File:** `terrariumEngine.py`

**Status:** Add 3 methods + 1 init + imports - `FEEDER_IMPLEMENTATION_CODE.md` section 4

**Lines to add:** ~100 lines

---

### 8️⃣ API Endpoints

**File:** `terrariumAPI.py`

**Status:** Add 8 routes + 8 methods - `FEEDER_IMPLEMENTATION_CODE.md` section 5

**Lines to add:** ~280 lines (routes + handlers)

---

## Creation Steps (In Order)

### Step 1: Create Directories

```bash
# Create feeder hardware directory
mkdir -p hardware/feeder

# Create feeder components directory
mkdir -p gui/components/feeders
```

**Verification:**
```bash
ls -la hardware/feeder/
ls -la gui/components/feeders/
```

---

### Step 2: Create Database Migration

**File:** `migrations/002_add_feeder_support.py`

1. Create file
2. Copy code from `FEEDER_IMPLEMENTATION_CODE.md` section 1
3. Save and verify exists: `ls -la migrations/002_add_feeder_support.py`

**Test:**
```bash
python -c "import migrations" # Should import without error
```

---

### Step 3: Create Hardware Driver

**File:** `hardware/feeder/__init__.py`

1. Create file
2. Copy complete terrariumFeeder class from `FEEDER_IMPLEMENTATION_CODE.md` section 3
3. Save (~300 lines)

**Verification:**
```bash
python -c "from hardware.feeder import terrariumFeeder; print('OK')"
```

---

### Step 4: Create Frontend Components

**File:** `gui/pages/Feeders.svelte`

1. Create file
2. Copy from `FEEDER_IMPLEMENTATION_CODE.md` section 6
3. Save

**File:** `gui/components/feeders/FeedersCard.svelte`

1. Create file
2. Copy from `FEEDER_IMPLEMENTATION_CODE.md` section 7 (first component)
3. Save

**File:** `gui/components/feeders/FeedersForm.svelte`

1. Create file
2. Copy from `FEEDER_IMPLEMENTATION_CODE.md` section 7 (second component)
3. Save

**Verification:**
```bash
ls -la gui/pages/Feeders.svelte
ls -la gui/components/feeders/FeedersCard.svelte
ls -la gui/components/feeders/FeedersForm.svelte
```

---

### Step 5: Update terrariumDatabase.py

**File:** `terrariumDatabase.py`

1. Open in editor
2. Go to end of file (before final functions)
3. Add Feeder ORM class from `FEEDER_IMPLEMENTATION_CODE.md` section 2
4. Add FeedingHistory ORM class from same section
5. Save

**Verification:**
```bash
python -c "from terrariumDatabase import Feeder, FeedingHistory; print('OK')"
```

---

### Step 6: Update terrariumEngine.py

**File:** `terrariumEngine.py`

1. At top, add import: `from hardware.feeder import terrariumFeeder, terrariumFeederException`
2. In `__init__` method, add after other hardware: `self.feeders = {}`
3. Add three methods from `FEEDER_IMPLEMENTATION_CODE.md` section 4:
   - `load_feeders()`
   - `callback_feeder()`
   - `check_feeder_schedules()`
4. In main loop (`_Engine__run`), add call: `self.check_feeder_schedules()`
5. Save

**Verification:**
```bash
python -c "from terrariumEngine import terrariumEngine; print('OK')"
```

---

### Step 7: Update terrariumAPI.py

**File:** `terrariumAPI.py`

1. At top, add import: `from terrariumDatabase import Feeder, FeedingHistory`
2. In `routes()` method, add all 8 route definitions from `FEEDER_IMPLEMENTATION_CODE.md` section 5
3. Add 8 handler methods from same section:
   - `feeder_list()`
   - `feeder_detail()`
   - `feeder_add()`
   - `feeder_update()`
   - `feeder_delete()`
   - `feeder_manual_feed()`
   - `feeder_test()`
   - `feeder_history()`
4. Save

**Verification:**
```bash
python -c "from terrariumAPI import terrariumAPI; print('OK')"
```

---

### Step 8: Update gui/pages/index.js

**File:** `gui/pages/index.js`

1. Add import: `import Feeders from './Feeders.svelte';`
2. Add to exports (if file uses export pattern): `export { Feeders };`
3. Or add to route definitions if using router
4. Save

**Verification:**
```bash
grep -n "Feeders" gui/pages/index.js # Should show your additions
```

---

## Testing After Each Step

### After Step 2 (Migration)
```bash
# Run TerrariumPI to apply migration
python terrariumPI.py

# Verify tables created
sqlite3 data/terrariumpi.db ".tables" | grep feeder
# Should show: feeder feeder_history
```

### After Step 3 (Hardware Driver)
```bash
python -c "from hardware.feeder import terrariumFeeder; print(terrariumFeeder.__doc__[:50])"
# Should print first 50 chars of docstring
```

### After Step 5 (Database)
```bash
python -c "
from pony import orm
from terrariumDatabase import db, Feeder, FeedingHistory
print('Feeder:', Feeder)
print('FeedingHistory:', FeedingHistory)
"
```

### After Step 6 (Engine)
```bash
# Check engine starts without error
python -c "
import sys
sys.path.insert(0, '.')
from terrariumEngine import terrariumEngine
print('Engine imports OK')
"
```

### After Step 7 (API)
```bash
# Check API loads
python -c "from terrariumAPI import terrariumAPI; print('API loads OK')"
```

---

## Pre-Deployment Checklist

- [ ] All 5 new files created (migration, driver, 3 components)
- [ ] 3 files updated (database, engine, API)
- [ ] 1 file updated (pages index)
- [ ] No syntax errors in any file
- [ ] Database migration runs without errors
- [ ] Engine starts with feeder support
- [ ] API endpoints accessible
- [ ] Frontned components load

---

## File Size Reference

Expected file sizes after implementation:

```
New Files:
  migrations/002_add_feeder_support.py ......... ~50 lines
  hardware/feeder/__init__.py ................ ~300 lines
  gui/pages/Feeders.svelte .................. ~180 lines
  gui/components/feeders/FeedersCard.svelte .. ~130 lines
  gui/components/feeders/FeedersForm.svelte .. ~350 lines
  Total new: ~1010 lines

Modified Files:
  terrariumDatabase.py +80 lines
  terrariumEngine.py +100 lines
  terrariumAPI.py +280 lines
  gui/pages/index.js +2 lines
  Total additions: ~462 lines

Grand Total: ~1472 lines of code
```

---

## Common Creation Mistakes to Avoid

❌ **Don't:** Copy just the code without the complete context
✅ **Do:** Copy entire sections from `FEEDER_IMPLEMENTATION_CODE.md`

❌ **Don't:** Create hardware/feeder as file instead of directory
✅ **Do:** Create as directory: `mkdir -p hardware/feeder/`

❌ **Don't:** Mix old and new code when updating existing files
✅ **Do:** Add new code at logical locations (end of file, etc.)

❌ **Don't:** Forget imports when adding to terrariumEngine.py and terrariumAPI.py
✅ **Do:** Add imports at very top of files

❌ **Don't:** Skip testing after each step
✅ **Do:** Verify each step works before moving to next

---

## File Dependency Order

```
1. migrations/002_add_feeder_support.py
   └─ Must run first (database schema)

2. terrariumDatabase.py (add ORM models)
   └─ Depends on: migration

3. hardware/feeder/__init__.py
   └─ Depends on: gpiozero (external), utils

4. terrariumEngine.py (add feeder support)
   └─ Depends on: hardware/feeder, database models

5. terrariumAPI.py (add endpoints)
   └─ Depends on: database models, engine

6. gui/pages/Feeders.svelte
7. gui/components/feeders/*.svelte
   └─ Frontend, no dependencies (loads separately)

8. gui/pages/index.js
   └─ Depends on: Feeders.svelte existing
```

**Important:** Follow this order!

---

## Minimal Test After All Files Created

```bash
#!/bin/bash

echo "=== Testing Aquarium Feeder Implementation ==="

# Test 1: Can Python import all modules?
echo -n "Testing imports... "
python3 << 'EOF'
try:
    from terrariumDatabase import Feeder, FeedingHistory
    from hardware.feeder import terrariumFeeder
    from terrariumEngine import terrariumEngine
    from terrariumAPI import terrariumAPI
    print("✓ All imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    exit(1)
EOF

# Test 2: Does database migration work?
echo -n "Testing database migration... "
python3 << 'EOF'
try:
    from terrariumDatabase import init
    init("test")
    print("✓ Database migration OK")
except Exception as e:
    print(f"✗ Database error: {e}")
    exit(1)
EOF

# Test 3: Do Svelte files exist?
echo -n "Testing Svelte files... "
if [ -f "gui/pages/Feeders.svelte" ] && \
   [ -f "gui/components/feeders/FeedersCard.svelte" ] && \
   [ -f "gui/components/feeders/FeedersForm.svelte" ]; then
    echo "✓ All Svelte files exist"
else
    echo "✗ Missing Svelte files"
    exit 1
fi

echo ""
echo "=== All Tests Passed ==="
echo "Ready for full testing!"
```

Save as `test_feeder_setup.sh`, then:
```bash
chmod +x test_feeder_setup.sh
./test_feeder_setup.sh
```

---

## Quick Copy-Paste Summary

For each file, locate section in `FEEDER_IMPLEMENTATION_CODE.md`:

| File | Section | Lines |
|------|---------|-------|
| migrations/002_add_feeder_support.py | 1 | 20 |
| hardware/feeder/__init__.py | 3 | 300 |
| gui/pages/Feeders.svelte | 6 | 180 |
| gui/components/feeders/FeedersCard.svelte | 7.1 | 130 |
| gui/components/feeders/FeedersForm.svelte | 7.2 | 350 |
| terrariumDatabase.py (append) | 2 | 80 |
| terrariumEngine.py (append methods) | 4 | 100 |
| terrariumAPI.py (append routes/methods) | 5 | 280 |

---

## Next Actions

1. **Read** `FEEDER_QUICK_START.md` for implementation overview
2. **Follow** file creation steps above in order
3. **Copy** code from `FEEDER_IMPLEMENTATION_CODE.md` section by section
4. **Test** after each step using verification commands
5. **Validate** using test script above
6. **Deploy** following `FEEDER_PR_DESCRIPTION.md`

---

You're ready to implement! 🚀

