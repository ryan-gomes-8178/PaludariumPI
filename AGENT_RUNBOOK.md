# AGENT_RUNBOOK.md — PaludariumPI (agent onboarding & troubleshooting runbook)

> **For AI agents (and humans) working in this repo.** Read this first. It is a
> verified map of how PaludariumPI is built, where its data lives, how to run it
> off a Raspberry Pi (sandbox), how to inspect its database, and how to SSH in and
> fix it on a device. Claims marked **(verified)** were reproduced on this
> machine; claims marked **(static)** are from reading the code, not executed.
>
> *Note: this was requested as `CLAUDE.md`, but in this environment `CLAUDE.md` is a
> protected agent-instruction file and cannot be written by the agent; per the request's
> "or tangential file" option, the same content lives here. To make it the canonical
> name, `git mv AGENT_RUNBOOK.md CLAUDE.md` (a human) or point your agent config at
> `AGENT_RUNBOOK.md`.*

PaludariumPI is a **rebrand/fork of [theyosh/TerrariumPI](https://github.com/theyosh/TerrariumPI)**:
software for home automation of a terrarium / paludarium / aquarium / greenhouse on a
Raspberry Pi. It controls relays (heaters, lights, sprayers, pumps, feeders…) and
reads sensors (temperature, humidity, CO₂, pH, light, UV, distance, …) to keep an
enclosure at set points, with a web UI and a notification system.

Current version: **4.14.0** (`terrariumPI.py:2`). Upstream lineage matters — many
file names, the service name (`terrariumpi`), the DB file (`terrariumpi.db`), and
the gettext domain (`terrariumpi`) still use the upstream spelling.

---

## Table of contents
1. [Decision tree — what do you actually need?](#decision-tree)
2. [Architecture at a glance](#architecture-at-a-glance)
3. [Repo map](#repo-map)
4. [Runtime model & boot sequence](#runtime-model--boot-sequence)
5. [The database (how to look at it)](#the-database-how-to-look-at-it)
6. [Known bug: fresh DB crashes on init](#known-bug-fresh-db-crashes-on-init-verified)
7. [Encryption (SALT / Fernet) — read-only caveats](#encryption-salt--fernet-read-only-caveats)
8. [SSH into the device & service ops](#ssh-into-the-device--service-ops)
9. [Running off-Pi / in a sandbox](#running-off-pi--in-a-sandbox)
10. [Docker](#docker)
11. [Frontend (Svelte GUI) build](#frontend-svelte-gui-build)
12. [API surface](#api-surface)
13. [Tests & CI](#tests--ci)
14. [Troubleshooting playbook](#troubleshooting-playbook)
15. [Conventions, gotchas & cheat sheet](#conventions-gotchas--cheat-sheet)

---

## Decision tree

| I need to… | Go to |
|---|---|
| Inspect / query the SQLite DB on a device | [§5 The database](#the-database-how-to-look-at-it) |
| SSH in and start/stop/restart/debug the service | [§8 SSH & service ops](#ssh-into-the-device--service-ops) |
| Run the app without real hardware (dev/emulation) | [§9 Sandbox](#running-off-pi--in-a-sandbox) |
| Build or change the web UI | [§11 Frontend](#frontend-svelte-gui-build) |
| Add/fix a hardware driver | [§3 Repo map → `hardware/`](#repo-map) |
| Understand the HTTP/WebSocket API | [§12 API surface](#api-surface) |
| "Won't start on a fresh clone" / DB errors | [§6 Known bug](#known-bug-fresh-db-crashes-on-init-verified) |
| "Can't read a value / looks encrypted" | [§7 Encryption](#encryption-salt--fernet-read-only-caveats) |
| "Something is broken on the device" | [§14 Troubleshooting](#troubleshooting-playbook) |

---

## Architecture at a glance

```
                 ┌──────────────────────────────────────────────┐
  Browser  ───►  │  Svelte 4 SPA  (gui/ → built to public/)      │  HTTP + WS
                 │  gui/providers/api.js · websocket.js · stores  │
                 └───────────────▲───────────────────────────────┘
                                 │  :8090  (bottle + gevent)
   ┌─────────────────────────────┴───────────────────────────────┐
   │  terrariumWebserver.py  (routes / live/ · /login/ · /api/*)   │
   │     terrariumAPI.py (118 /api/ routes) · terrariumAuthAPI.py  │
   └─────────────────────────────▲───────────────────────────────┘
                                 │
   ┌─────────────────────────────┴───────────────────────────────┐
   │  terrariumEngine.py  — the control loop (a background thread) │
   │  loads settings, sensors, relays, buttons, webcams, feeders,  │
   │  enclosures from the DB and drives hardware each round        │
   └─────────────────────────────▲───────────────────────────────┘
                                 │  reads/writes
   ┌─────────────────────────────┴───────────────────────────────┐
   │  terrariumDatabase.py  — SQLite (Pony ORM) + yoyo-migrations  │
   │  file: data/terrariumpi.db  (WAL, synchronous=OFF)            │
   └─────────────────────────────▲───────────────────────────────┘
                                 │  drives
   ┌─────────────────────────────┴───────────────────────────────┐
   │  hardware/  — driver plugins, loaded dynamically by name       │
   │  GPIO via gpiozero + pigpiod  ·  I2C 1-Wire BT  network relays │
   └──────────────────────────────────────────────────────────────┘
```

- **Language / runtime:** Python 3 (Pi: 3.7 buster / 3.9 bullseye / 3.11 bookworm),
  **gevent** (must `monkey.patch_all()` first), **bottle** + `bottle.ext.websocket`
  for HTTP/WebSocket, **Pony ORM** over **SQLite**, **yoyo-migrations**, **Svelte 4**
  frontend built with **rollup**.
- **Entry point:** `terrariumPI.py` → `terrariumEngine.terrariumEngine(version).stop()`.
- **Hardware layer:** `hardware/` driver plugins, discovered by filename and registered
  by a `HARDWARE` string, loaded via `terrariumUtils.loadHardwareDrivers`
  (`terrariumUtils.py:546`). GPIO uses `gpiozero` with the `pigpio` pin factory
  (or `rgpio` on Pi 5), backed by the **`pigpiod`** daemon.
- **One process, one DB, one web port (8090).** The engine loop runs in a thread;
  the webserver (a blocking `bottle.run`) is started last in `__init__`.

---

## Repo map

### Top-level Python (the backend)
| File | Role |
|---|---|
| `terrariumPI.py` | Entry point: `gevent.monkey.patch_all()`, gettext, engine start. |
| `terrariumEngine.py` | **The heart.** Boot sequence, the `__engine_loop`, load_* for every entity, system stats, feeder/enclosure logic. (~2300 lines) |
| `terrariumDatabase.py` | DB: Pony entities (tables), `init()` (yoyo + mapping + defaults), `recover()`. |
| `terrariumWebserver.py` | bottle app, HTTP routes, `/live/` websocket, auth cookie/session. |
| `terrariumAPI.py` | All `/api/*` routes (118) — CRUD for areas/sensors/relays/buttons/webcams/feeders/notifications/etc. |
| `terrariumAuthAPI.py` | Auth routes (`/api/login`, 2FA, `/api/auth/*`). |
| `terrariumAuth.py` | Login, password hashing (bcrypt), 2FA (pyotp), session tokens. |
| `terrariumNotification.py` | Notification services (email, Telegram, webhook, display) + broadcast. |
| `terrariumArea.py` | Per-area control logic (lights/humidity/temperature/watertank modes). |
| `terrariumEnclosure.py` | Enclosure-level logic. |
| `terrariumCalendar.py` | iCal (icalendar/icalevents) schedules for hardware replacement. |
| `terrariumCloud.py` | Meross cloud sync. |
| `terrariumAudio.py` | Audio playback (pyalsaaudio). |
| `terrariumUtils.py` | Shared helpers: encryption (Fernet/SALT), unit conversions, GPIO↔BCM mapping, dynamic hardware loading, `get_script_data`, bluetooth checks. |
| `terrariumLogging.py` | Logging config loader + rotating/compressing handler + notification-on-warning. |
| `rollup.config.js` | Frontend build config. |

### Directories
| Path | What |
|---|---|
| `gui/` | Svelte 4 SPA source: `App.svelte`, `main.js`, `pages/`, `components/`, `stores/`, `providers/`, `constants/`, `modals/`, `locale/`. |
| `hardware/` | Driver plugins: `sensor/`, `relay/`, `button/`, `display/`, `feeder/`, `webcam/`, `io_expander.py`. |
| `migrations/` | yoyo-migrations (`.sql` + `.py`). Applied on every boot. |
| `contrib/` | Ops/DB scripts, docker-compose files, remote-access templates, service unit example, watchdog. |
| `docs/` | Jekyll site source + `_faq/` troubleshooting articles + setup guides. |
| `tests/` | `conftest.py` + `test_switchbot_ble.py` (the only real test). |
| `locales/` | gettext `.po`/`.mo` translations. |
| `3rdparty/` | git submodules (relay8-rpi, energenie-connect0r, chirp-rpi, AtlasScientific, voltcraft). |
| `data/` | Runtime DB (`terrariumpi.db`, gitignored) + `.database-env`. |
| `log/` | Log files (on device, symlinks to `/dev/shm`). |
| `Dockerfile.{bookworm,bullseye,buster}` | Container build per Debian. |
| `run.sh` | Container entrypoint / device bootstrap (enables i2c/1-wire/camera, starts pigpiod). |
| `install.sh` | Device installer (apt + venv + systemd + udev + bluepy setcap). |
| `rebuild_and_deploy.sh` | Rebuild GUI + restart service + Cloudflare cache purge. |
| `.env.dev.json` / `.env.prod.json` | Frontend build-time env (title, API_URL). |
| `logging.cfg` | Logging config (copy to `log/logging.custom.cfg` to override). |
| `requirements.txt` / `requirements-dev.txt` | Runtime deps / pytest. |

---

## Runtime model & boot sequence

`terrariumPI.py` (verified): `gevent.monkey.patch_all()` **must run first**, then
`gettext.install("terrariumpi","locales/")`, then
`terrariumEngine = terrariumEngine(__version__); terrariumEngine.stop()`.

`terrariumEngine.__init__(version)` (`terrariumEngine.py:74`, in order, verified by
reading):
1. **SALT** ← `grep -i serial /proc/cpuinfo` → `os.environ["SALT"]` (lines **113–115**) — *crashes off-Pi*.
2. **device** ← `/proc/device-tree/model` (line **124**) — *crashes off-Pi*.
3. **os_version** ← `/etc/os-release` (line **125**) — *crashes on macOS; OK on Linux*.
4. `init_db(version)` (line **129**) → `terrariumDatabase.init()`: apply yoyo
   migrations, `db.bind`+`db.generate_mapping()` (check_tables=True by default), then
   `create_defaults()` (~35 `Setting` rows).
5. systemd `READY=1` notify (line 132); `self.running = True`.
6. `load_settings` (142) → sets `GPIOZERO_PIN_FACTORY` (136); auth (145);
   notification + `load_services` + broadcast startup (148–151); webserver object (154);
   calendar (157).
7. Load power/water (163), **feeders** (170), **sensors** (175), **relays** (189),
   **buttons** (203), **webcams** (209), **enclosures** (215) — each `__load_existing_*`.
8. Start the **log-tail** thread and the **`__engine_loop`** thread (228–232).
9. `self.webserver.start()` (235) — **blocking** `bottle.run(...,
   server=GeventWebSocketServer)`; this is where the process lives.
10. `stop()` (238) runs on Ctrl-C / SIGINT.

**The control loop** `__engine_loop` (`terrariumEngine.py:1397`, static): loops on
`self.__engine["exit"]` (a `threading.Event`); each round it sends a systemd
`WATCHDOG=1`, then a `ThreadPoolExecutor` runs `_update_sensors`, `_update_relays`,
`_update_buttons`, `_update_webcams`, `__update_checker` **in parallel**, then
`_update_enclosures()`, `check_feeder_schedules()`, `motd()`, and
`terrariumUtils.kill_bluetooth_helper_processes()`. A sensor/relay that fails to read or
load is **logged and skipped, not fatal** — the loop keeps running.

**Stop path** `stop()` (`terrariumEngine.py:1848`): sets `running=False`, signals the
exit event, terminates the logtail, joins threads, stops each enclosure/button/relay/etc.

---

## The database (how to look at it)

- **Location:** `data/terrariumpi.db` (SQLite; `terrariumDatabase.py:15`). Advanced
  PRAGMAs live in `data/.database-env` (dotenv, `terrariumDatabase.py:16`). The file is
  **gitignored** — it only exists on a running device.
- **Engine:** Pony ORM. On connect it sets `WAL` journal, `synchronous=OFF`,
  `auto_vacuum=NONE`, `cache_size=-10000`, `temp_store=MEMORY`
  (`terrariumDatabase.py:21–34`), then merges any `data/.database-env` overrides.
- **Migration tool:** `yoyo-migrations==9.0.0` over `migrations/`, applied by
  `init()` before mapping.
- **Schema (verified via a real `.schema` dump):** 16 app tables + 4 yoyo bookkeeping
  tables.

| Table | Key columns | Notes |
|---|---|---|
| `Enclosure` | id (uuid PK), name, image, description | Root object. Owns areas/doors/webcams/feeders/zones/events. |
| `Area` | id, enclosure(FK→Enclosure CASCADE), name, type, mode, **setup JSON**, state JSON | A functional unit (lights/watertank/sensor group). `type` ∈ {lights, watertank, sensor types…}. |
| `Button` | id, hardware, name, address, calibration JSON, enclosure(FK SET NULL), notification | A door/opening; live value from `ButtonHistory`. |
| `ButtonHistory` | button(FK CASCADE), timestamp, value | Append-only; newest within **65 min** = live value. |
| `Sensor` | id, hardware, type, name, address, limit_min/max, alarm_min/max, max_diff, exclude_avg, calibration, notification | Live value from `SensorHistory`. |
| `SensorHistory` | sensor(FK CASCADE), timestamp, value, limit_min/max, alarm_min/max, exclude_avg, out_of_range | One row/minute (`update()` upserts on the minute; VALUE_MODE=2 averages). |
| `Relay` | id, hardware, name, address, wattage, flow, manual_mode, replacement, calibration, webcam(weak ref), notification | `is_dimmer` if hardware ends `-dimmer`; `value` 0–100 %. |
| `RelayHistory` | relay(FK CASCADE), timestamp, value, wattage, flow | `value` = % ; wattage/flow = actuals. |
| `Webcam` | id, hardware, name, address, width, height, rotation, awb, archive/motion/markers JSON, enclosure(FK SET NULL), notification | `is_live` if hardware ends `-live`. |
| `Audiofile` / `Playlist` / `Audiofile_Playlist` | … | M2M audio library + playlists. |
| `Setting` | id (PK), value | Key/value config; `create_defaults()` seeds ~35 rows (host, port=8090, username=admin, **password = bcrypt hash**, currency, indicators, version, …). |
| `NotificationMessage` / `NotificationService` / `NotificationMessage_NotificationService` | … | Messages M2M with services; `NotificationService.setup` holds (encrypted) credentials. |

**Quirk (verified):** some `Optional(str)` fields materialize as `NOT NULL TEXT`
(Pony 0.7.19 behaviour) — e.g. `Enclosure.image`/`description` — pass `""`, not `NULL`.

### Reading the live DB safely
The engine keeps the DB open in **WAL + `synchronous=OFF`** mode with a live writer.
A reader must **not** take a write lock:
```bash
# Preferred: read-only connection that still sees WAL data
sqlite3 -readonly -header -column data/terrariumpi.db "SELECT ..."
# or
sqlite3 data/terrariumpi.db "PRAGMA query_only=ON; SELECT ...;"
```

**Verified example queries** (run against the device's `data/terrariumpi.db`):
```sql
-- A. enclosures
SELECT id,name FROM Enclosure ORDER BY name;
-- B. sensors + latest value (join on newest SensorHistory row)
SELECT s.name,s.type,h.value,h.timestamp,h.out_of_range
  FROM Sensor s JOIN SensorHistory h ON h.sensor=s.id
 WHERE h.timestamp=(SELECT MAX(timestamp) FROM SensorHistory WHERE sensor=s.id);
-- C. relays + current state
SELECT r.name,r.hardware,r.wattage,h.value AS pct,h.wattage AS cur_W,h.flow AS cur_flow
  FROM Relay r JOIN RelayHistory h ON h.relay=r.id
 WHERE h.timestamp=(SELECT MAX(timestamp) FROM RelayHistory WHERE relay=r.id);
-- D. settings (encrypted ids show as Fernet blobs — see §7)
SELECT id,value FROM Setting ORDER BY id;
-- E. notification services (token is encrypted; raw key via json_extract)
SELECT id,type,name,enabled,rate_limit FROM NotificationService;
-- F. power/water right now
SELECT SUM(h.wattage) AS W, SUM(h.flow) AS L_per_min
  FROM RelayHistory h JOIN
    (SELECT relay,MAX(timestamp) ts FROM RelayHistory GROUP BY relay) x
    ON h.relay=x.relay AND h.timestamp=x.ts;
```
Pony snippet (run inside the project venv; every read needs a `db_session`):
```python
import terrariumDatabase as T
from pony import orm
T.db.bind(provider='sqlite', filename='data/terrariumpi.db')
T.db.generate_mapping(check_tables=True)   # use check_tables=False on a broken fresh DB (see §6)
with orm.db_session:
    for s in T.Sensor.select():   print(s.name, s.value, s.error)
    for r in T.Relay.select():    print(r.name, r.value, r.is_on, r.current_wattage, r.current_flow)
    for st in T.Setting.select(): print(st.id, st.value)
    for n in T.NotificationService.select(): print(n.to_dict()['setup'])  # to_dict() decrypts when SALT is set
```
> **Live-value caveat (verified):** `Sensor.value`/`Relay.value`/`Button.value` return
> **`None`** if the newest sample is older than the max-age window — **Sensor 5 min,
> Relay/Button 65 min**. So a value can look "missing" even though history exists.

### DB maintenance scripts (`contrib/`, run in the venv; most need the service STOPPED)
| Script | Purpose | Run |
|---|---|---|
| `db_cleanup.py` | Purge `SensorHistory`/`ButtonHistory` older than 60 weeks + orphans, then `VACUUM INTO`. **Refuses if the webserver is up** (checks `:8090`). | `./db_cleanup.py` (interactive `yes`) |
| `fix_db.py` | Repair a **corrupt** DB (`sqlite3 .dump \| sed … COMMIT \; sqlite3 new`). Leaves `data/terrariumpi.db.broken`. | `./fix_db.py [-d path]` |
| `copy_relay_history.py` | Import relay history from a **v3** install into a v4 DB. | `./copy_relay_history.py <old settings.cfg> <old history.db> <new terrariumpi.db>` |
| `duplicate_switch.py` | "Script relay": toggle one physical relay via HTTP to drive several logical relays. | edit RELAY_ID/USERNAME/PASSWORD, run |
| `sensors_diff.py` | "Script sensor": print `|sensor1 - sensor2|` via the API. | edit `SENSORS[]`/`TERRARIUMPI_SERVER`, run |
| `script_sensor.py` | Trivial example "script sensor" (prints a random int) — replace with real logic. | — |

The in-code equivalent of `fix_db.py` is `terrariumDatabase.recover()` (uses the SQLite
backup API, `terrariumDatabase.py:112`).

---

## Known bug: fresh DB crashes on init **(verified)**

On a **freshly cloned / first-install** database, `terrariumDatabase.init(version)`
**crashes** with:
```
OperationalError: no such table: Feeder
```
**Root cause (verified):** the tables `Feeder`, `FeedingHistory`, `MonitoringZone`, and
`MonitoringEvent` are declared as Pony entities, but their migrations —
`migrations/002_add_feeder_support.py` and `migrations/0006_add_monitoring_tables.py` —
use the **legacy** `def forward(backend)` / `def backward(backend)` style. **yoyo 9.0.0
does not execute that style** (it only runs steps registered via `step()`/`group()`),
so both migrations **run but do nothing** (verified: only yoyo bookkeeping tables get
created). Because `generate_mapping()` uses `check_tables=True` (Pony default), the
missing `Feeder` table aborts init. As a second defect, migration `002` and `0002` both
carry version **2**, so `_yoyo_version` ends with a single `version 2` row.

- **Reproduce:** in a venv with `pony==0.7.19` + `yoyo-migrations==9.0.0`:
  `python -c "import terrariumDatabase as T; T.init('4.14.0')"` → crash.
- **Who is affected:** only **brand-new** databases. Long-running devices already have
  these tables (created by an older yoyo), so they keep working. This bites first-time
  installs / "fresh sandbox" runs — exactly the case this runbook targets.
- **Fixes (pick one; not applied here — behaviour change):**
  1. Rewrite the two `.py` migrations using yoyo's modern API
     (`from yoyo import step` + `MIGRATIONS = [step(sql1), step(sql2)]`) and give each a
     unique, sequential version (resolve the `002`/`0002` collision).
  2. Replace the two `.py` migrations with equivalent `.sql` files (`.sql` migrations
     *do* run under yoyo 9.x).
  3. Sandbox workaround: `check_tables=False` in `generate_mapping`, then
     `CREATE TABLE IF NOT EXISTS` the 4 missing tables first.

> This is the single most likely "why won't a fresh clone start?" answer — check it first.

---

## Encryption (SALT / Fernet) — read-only caveats

- **Algorithm:** symmetric **Fernet**. Key =
  `Fernet(base64.urlsafe_b64encode(f'{SALT:0>32}'))` (`terrariumUtils.py:153–158`).
- **`SALT` = the Raspberry Pi CPU serial** — derived at boot from
  `grep -i serial /proc/cpuinfo` (`terrariumEngine.py:113`). It is **device-bound**.
- **`encrypt()`/`decrypt()` both swallow errors and return the input unchanged**
  (`terrariumUtils.py:160–174`). Consequence: with the wrong/absent SALT,
  `decrypt("gAAAAA…")` returns the **ciphertext**, so encrypted fields look like random
  `gAAAAA…` strings and are **undecryptable** unless you reconstruct the key from that
  device's serial.
- **Encrypted fields:** `Setting.value` for `weather_source`,
  `meross_cloud_username`, `meross_cloud_password`, `unsplash_access_key`; and
  `NotificationService.setup` keys `username`, `password`, `user_key`, `api_token`,
  `access_secret`, `token`, `allowed_users`. Empty values stay empty.
- **The admin login is NOT Fernet-encrypted** — `Setting` id `password` is a **bcrypt
  hash** (`terrariumUtils.generate_password`) and is **irrecoverable**.
- **Moving a DB to a different Pi** changes `SALT` → prior encrypted values become
  undecryptable. To decrypt in raw SQLite you can't; run inside the app (which sets
  `SALT` from the serial) or rebuild the Fernet key from the serial.

---

## SSH into the device & service ops

**Deployment:** the device runs TerrariumPI as a **systemd service** `terrariumpi`,
templated from `contrib/terrariumpi.service.example` by `install.sh`
(`ExecStart=<dir>/venv/bin/python <dir>/terrariumPI.py`, `Restart=always`,
`RestartSec=5`, `KillSignal=SIGINT`, `Type=notify`, `TimeoutStartSec=1800`,
`WatchdogSec=180`). Default user **`pi`**, home **`/home/pi/TerrariumPI`**
(Pi Zero runs as root). Logs live under `log/` — on the device these are **symlinks to
`/dev/shm/terrariumpi*.log`** (tmpfs, lost on reboot; archived nightly to the SD card).

**Connect:** `ssh pi@<raspberry-ip>` (the README's canonical user is `pi`).

**Service control** (`docs/_faq/systemd.md`):
```bash
sudo service terrariumpi start|stop|restart
sudo systemctl status|is-active|enable|disable terrariumpi
journalctl -u terrariumpi -f            # or tail the log files below
```

**Logs** (`docs/_faq/logging.md`):
- `log/terrariumpi.log` — INFO; `log/terrariumpi.access.log` — web access;
  `log/terrariumpi.debug.log` — DEBUG (opt-in).
- To change logging: `cp logging.cfg log/logging.custom.cfg`, add `fileHandlerDebug`
  (debug) or `syslogHandler` (syslog) to `[logger_root]` handlers, then `service
  terrariumpi restart`. Warnings/errors are also turned into user notifications.

**Debug mode** (`docs/_faq/debug.md`) — see full errors on the console:
```bash
sudo service terrariumpi stop
cd /home/pi/TerrariumPI && source venv/bin/activate
python terrariumPI.py            # console mode; "up and running …:8090" = ready
# Ctrl+C once to stop
```

**Watchdogs:** `contrib/watchdog.sh` (crontab `* * * * *`) kills the process if the
log isn't updated within 600 s; in Docker, `contrib/docker_health.py` checks `motd.sh`
freshness. **Reboot/restart/shutdown** can be triggered from the web UI (the user is
granted NOPASSWD `reboot`/`shutdown`/`pigpiod restart` in `/etc/sudoers.d/020_terrariumpi`).

**Default login: `admin` / `password`** — change it immediately (`docs/_faq/login.md`).
Local UI: `http://<pi-ip>:8090`. The user's public domain is **`paludariumpi.dev`**
(behind Cloudflare; see `rebuild_and_deploy.sh`). For safe remote access use a tunnel or
reverse proxy — `docs/_faq/remote_access.md` + `contrib/remote-access/` (Cloudflare
Tunnel or Caddy examples). **Never expose plain HTTP to the internet.**

---

## Running off-Pi / in a sandbox

This app is written for a Raspberry Pi. It **can** run elsewhere, but it has Pi-specific
assumptions. **Recommendation order:**
1. **SSH into the real device** — most faithful; use it for real hardware/DB work.
2. **Docker** (§10) — faithful emulation of the Pi runtime.
3. **Dev GUI-only** (§11) — fastest when you only touch the frontend.

### What runs fine off-Pi with no hardware
The DB layer, the web UI, settings, notifications, calendar, enclosures, and the engine
loop all work. A sensor/relay that can't load or read is **logged and skipped**, so with
an **empty DB** nothing is instantiated and the loop just iterates. You do **not** need
hardware to see the UI come up.

### Off-Pi blockers that crash `init()` **(static; confirmed by reading the cited lines)**
| # | Item | Location | Effect |
|---|---|---|---|
| 1 | `SALT` from `grep -i serial /proc/cpuinfo` | `terrariumEngine.py:113–115` | **CRASH** — `get_script_data` returns `None` off-Pi → `None.decode()` → `AttributeError`. |
| 2 | device model `/proc/device-tree/model` | `terrariumEngine.py:124` | **CRASH** — `FileNotFoundError` on x86/Linux/macOS. |
| 3 | OS version `/etc/os-release` | `terrariumEngine.py:125` | **CRASH on macOS** (file missing); OK on Linux. |
| 4 | `isRaspberryPI5()` re-reads device-tree | `terrariumUtils.py:597` (called at `terrariumEngine.py:336`) | **CRASH** — must patch **in addition** to #2. |

### Off-Pi blockers that degrade gracefully (non-fatal)
- **Per-driver Pi-only imports** (e.g. `RPi.GPIO` in `hardware/button/ldr_button.py:6`,
  `pigpio` in `dhtxx_sensor.py`): `loadHardwareDrivers` wraps **each** file import in
  try/except (`terrariumUtils.py:553`) → the driver is logged and **skipped**.
- **gpiozero pin factory** (`terrariumEngine.py:336`): needs `pigpiod` or `RPi.GPIO`;
  without it, GPIO devices **error but the loop continues**. Keep
  `GPIOZERO_PIN_FACTORY=pigpio` off-Pi (NOT `rgpio`, which needs Pi 5 firmware).
- **I2C/serial `/dev` opens** → sensor read fails, logged. **`pigpiod`**
  (`run.sh:157–160`) → same. **Bluetooth** (`hcitool`/`bluepy`,
  `terrariumUtils.py:522–528`): `bluetooth_available()` returns `False` → BT sensors
  filtered out. **`sdnotify`** → no-ops off systemd. **`sudo reboot/shutdown`** → only
  user-triggered.
- **Import-time hardware deps** in `hardware/sensor/__init__.py:16,19,22`
  (gpiozero, smbus2, bluepy.btle), `hardware/button/__init__.py:18`,
  `hardware/io_expander.py:8` (i2crelay): **CRASH at import if the package is missing.**
  On **macOS** several have **no wheels** (`smbus2`, `pyalsaaudio`, `RPi.GPIO`, `pigpio`,
  `pyownet`, `smbus`) → **use x86 Linux, not macOS**, for a backend sandbox.

### Minimal recipe to boot the backend off-Pi
1. Use **x86 Linux** (kernel-only deps won't build on macOS).
2. Satisfy GPIO: `pigpiod -l` locally **or** point at a real Pi's daemon:
   `export PIGPIOD_ADDRESS=<pi-host>:8888 PIGPIOD_PORT=8888` (keep `GPIOZERO_PIN_FACTORY=pigpio`).
3. Neutralise the three `/proc` reads (patch the repo **or** inject via
   `sitecustomize.py` on `PYTHONPATH` — no repo edit):
   - `terrariumEngine.py:113` → `os.environ.setdefault('SALT','dev-sandbox')`
   - `terrariumEngine.py:124` → on `FileNotFoundError`, `self.device='x86-dev'`
   - `terrariumEngine.py:125` → guard the `/etc/os-release` read
   - `terrariumUtils.py:597` `isRaspberryPI5()` → return `False` on exception
4. Handle the **§6 fresh-DB crash** (`check_tables=False` + create the 4 missing tables,
   or apply a real migration fix).
5. `source venv/bin/activate && python terrariumPI.py` → UI on `http://localhost:8090`.

**pip dep split** (verified from `requirements.txt`):
- **Pi/kernel-only** (Linux/arm, won't build on macOS): `RPi.GPIO`, `pigpio`,
  `pigpio_dht`, `pyalsaaudio`, `pyownet`, `smbus`, `smbus2`, `RPi.bme280`, `lib8relay`,
  `SM8relind`, `SM4relind`, `pylibftdi`, `bluepy`.
- **Cross-platform** (Linux & macOS): `bottle`, `gevent`, `bottle_websocket`, `pony`,
  `jinja2`, `retry`, `bcrypt`, `cryptography`, `pyotp`, `qrcode`, `Pillow`, `numpy`,
  `opencv-python-headless`, `piexif`, `requests`, `python-kasa`, `meross-iot`,
  `PCA9685-driver`, `pywemo`, `sensirion-i2c-driver`, `sensirion-i2c-sht`, `bme680`,
  `Adafruit-Blinka`, `adafruit-circuitpython-sht31d`, `mitemp_bt`, `func_timeout`,
  `sdnotify`, `psutil`, `icalendar`, `pydantic`.

---

## Docker

Dockerfiles per Debian: `Dockerfile.{bookworm,bullseye,buster}` (final stage
`python:3.11-slim-bookworm`; 3rd-party submodules cloned in the builder).
- **Entrypoint** `["/bin/bash","/TerrariumPI/run.sh"]`,
  **CMD** `["/opt/venv/bin/python","/TerrariumPI/terrariumPI.py"]`
  (`Dockerfile.bookworm:121–122`); **HEALTHCHECK** runs `contrib/docker_health.py`
  (`:119`).
- `run.sh` (entrypoint) edits `/boot/config.txt` & `/boot/cmdline.txt` (or
  `/boot/firmware/*` on bookworm) to enable i2c/1-wire/camera/serial/CO₂, starts
  `pigpiod -l` if TCP 8888 is closed, then `exec "$@"`. Env toggles:
  `ENABLE_I2C`, `ENABLE_1_WIRE`, `ENABLE_CAMERA`, `ENABLE_SERIAL`,
  `ENABLE_CO2_SENSORS`, `AUTO_REBOOT`.
- `contrib/docker-compose.yaml`: mounts `/dev:/dev`, `/etc/modules`,
  `/boot{,/firmware}/*`, `/run/udev`; `network_mode: host`; `privileged: true`;
  `cap_add: [NET_ADMIN]`; `init: true`; `stop_signal: SIGINT`.
  `contrib/docker-compose.public-access.yaml` adds an nginx reverse proxy.
- **CI** `.github/workflows/docker-image-matrix.yml`: on release + `workflow_dispatch`,
  builds the matrix **buster/bullseye/bookworm × java on/off**, `platform
  linux/arm/v7`, via QEMU on `ubuntu-latest`; tags `theyosh/terrariumpi:<os>[-java]`.
- Example run (needs host `/dev` + privileged; still hits the §9 `/proc` blockers
  unless the host provides them):
  ```bash
  docker run --rm -v /dev:/dev --privileged --network host --init \
    -e ENABLE_I2C=true theyosh/terrariumpi:bookworm
  ```
- **Rebuild + deploy to the device** (`rebuild_and_deploy.sh`): `npm run build` →
  `setcap` the `bluepy*-helper` → `systemctl restart terrariumpi.service` →
  (optionally) purge Cloudflare cache. It reports both the local `:8090` and
  `paludariumpi.dev` URLs.

---

## Frontend (Svelte GUI) build

- **Source:** `gui/` (Svelte 4). **Build:** rollup (`rollup.config.js`, root).
- **Scripts** (`package.json`):
  | Command | What |
  |---|---|
  | `npm run dev` | Watch build + auto-start + livereload (`.env.dev.json`). |
  | `npm run build:dev` | One-shot dev build (`.env.dev.json`). |
  | `npm run build` | **Prod** (`MIX_ENV=prod NODE_ENV=prod`, `--max-old-space-size=1536`, `.env.prod.json`) → minify + gzip. |
  | `npm run start` | `npx serve -n -l 5000 public` (serves the built `public/` on `:5000`). |
  | `npm run format` | `prettier --write ./docs ./gui *.md`. |
- **Prereq:** `npm install` (CI does `npm install --force && ./gui/patch.sh`;
  `gui/patch.sh` patches AdminLTE/bootstrap/svelte-adminlte SCSS). **Node version:** no
  `.nvmrc` / no `package.json` `engines`; CI uses `node lts/*` (unverified locally).
- **Env files:** `.env.dev.json` sets `BASE_HTML_TITLE="TerrariumPI -DEV-"` and
  `API_URL="http://localhost:8090/"`; `.env.prod.json` sets only the title (no `API_URL`
  → the SPA falls back to `window.location.origin`).
- **Output → `public/`** (gitignored). **API_URL wiring:** `gui/constants/urls.js`
  derives `ApiUrl` from `process.env.API_URL || AppUrl` and
  `WebsocketUrl = ${ApiUrl}/live/` (http→ws); `gui/providers/api.js` exposes ~90 async
  helpers over `${ApiUrl}/api` using HTTP Basic auth; `gui/providers/websocket.js` opens
  `websocketStore(${WebsocketUrl})`; both feed writable stores in
  `gui/stores/terrariumpi.js`, consumed by `gui/App.svelte` and `gui/pages/*`.
- **Makefile:** `make gui` = `npm install` + `npm run build`.

---

## API surface

**HTTP + WebSocket** on port **8090** (bottle + gevent; default host `0.0.0.0`).
- **`/api/*`** — 118 routes in `terrariumAPI.py` (registered `terrariumAPI.py:83`), each
  wrapped in `self.authentication()`. Major groups: `/api/areas/`,
  `/api/sensors/` (`+ /scan /hardware /history /export`), `/api/relays/`
  (`+ /on /off /<n> /manual /scan`), `/api/buttons/`, `/api/feeders/`
  (`+ /feed /test /scan`), `/api/webcams/` (`+ /archive`), `/api/calendar/`,
  `/api/enclosures/`, `/api/monitoring/zones|events/`,
  `/api/notification/services|messages/` (`+ /types`), `/api/audio/files|hardware/`,
  `/api/playlists/`, `/api/displays/`, `/api/settings/`, `/api/system_status/`,
  `/api/weather/` (`+ /forecast`), `/api/logfile/download/`, and system actions
  `POST /api/restart|reboot|shutdown/`.
- **Auth API** (`terrariumAuthAPI.py`, registered at `terrariumWebserver.py:489`):
  `POST /api/login`, `POST /api/login/2fa`, `POST /api/logout`,
  `GET /api/auth/2fa/setup`, `GET /api/auth/verify`, `GET /api/auth/notifications`.
- **WebSocket:** `/live/` (`bottle.ext.websocket.GeventWebSocketServer`,
  `terrariumWebserver.py:492`) streams `systemstats`, sensor/relay/button updates,
  `logline`, and power/water.
- **Non-`/api` routes** (`terrariumWebserver.py`): `/` (SPA, authenticated),
  `/login/`, `/background`, `/live/`.
- The SPA consumes the API through `gui/providers/{api,websocket}.js` →
  `gui/stores/terrariumpi.js` (see §11).

---

## Tests & CI

- **Runner:** `pytest==8.3.5` (`requirements-dev.txt`).
  `pip install -r requirements-dev.txt && python -m pytest tests/ -v`.
- **`tests/conftest.py`:** puts the repo root on `sys.path` (`:6`) and **stubs
  `terrariumLogging`** with plain `logging` (`:10–12`) so importing backend code doesn't
  open live log files or fire user notifications.
- **The suite is small / hardware-oriented:** `tests/test_switchbot_ble.py` is the only
  real test — unit tests for `hardware/sensor/switchbot_ble.py`
  (`decode_io_meter`, `is_switchbot_advert`, `SwitchBotCollector`) using
  `FakeScanner`/`FakeRadio`/`FakeClock`; a `sensor_module` fixture auto-skips when
  `"switchbot"` isn't in `available_hardware` (no BT on the host). **To add a test:**
  drop `tests/test_*.py` next to `conftest.py`; for hardware-free logic reuse the
  fake pattern, for sensor integration use `sensor_module`.
- **Workflows** (`.github/workflows/`):
  | Workflow | Trigger | Does |
  |---|---|---|
  | `black.yml` | push to `4.x.y.z` (`**/*.py`) + dispatch | Lint **Black** (`psf/black@stable`, `-l 120 -t py37`); auto-commit + force-push. |
  | `codeql-analysis.yml` | push/PR to `main`,`3.x.y.z`,`4.x.y.z` | CodeQL security scan (JS + Python). |
  | `docker-image-matrix.yml` | release + dispatch | Build/push multi-arch Docker images. |
  | `pages-deploy.yml` | push to `main` (`docs/**`,`Gemfile.lock`) + dispatch | Jekyll build of `docs/` → GitHub Pages. |
  | `svelte-gui.yml` | push to `main`,`4.x.y.z` (`gui/**`,`*.json`,`**/*.js`) + dispatch | Node LTS: `npm install --force && ./gui/patch.sh`, `npm run format`, `npm run build`, then commit + force-push `public/`. |
- **Formatting:** Prettier (`npm run format`) for JS/Svelte/MD (`.prettierrc`:
  `printWidth 120`, single quotes, `tabWidth 2`, `svelteSortOrder
  options-styles-scripts-markup`; `.md` → `printWidth 80`); **Black** for Python
  (`-l 120 -t py37`) — enforced **in CI only**, not in `requirements-dev.txt`
  (local: `pipx run black -l 120 -t py37 <files>`).

---

## Troubleshooting playbook

**Symptom → first move**
| Symptom | Likely cause / fix |
|---|---|
| Fresh clone won't start; `no such table: Feeder` | **§6** — fix the no-op `.py` migrations / `check_tables=False`. |
| `database disk image is malformed` | Stop service → `cd contrib && ./fix_db.py` → start. Or `terrariumDatabase.recover()`. Backup at `data/terrariumpi.db.broken` (`docs/_faq/malformed_database.md`). |
| Value looks "missing" but history exists | Live-value window: Sensor 5 min, Relay/Button 65 min (§5). |
| A value/credential looks like `gAAAAA…` | Encrypted; wrong/absent SALT (§7). Can't decrypt without the device serial. |
| `python terrariumPI.py` crashes at startup off-Pi | The `/proc` reads (§9 blockers 1–4). Patch or use Docker/the device. |
| GPIO devices all error off-Pi | No `pigpiod`/`PIGPIOD_ADDRESS` (§9). |
| Bluetooth sensors absent | No `hcitool`/BT adapter (`bluetooth_available()` False). |
| Service won't start / keeps restarting | `journalctl -u terrariumpi -f`; run in **debug mode** (§8); check `TimeoutStartSec=1800` / `WatchdogSec=180` in the unit. |
| Web UI stale after a GUI change | Run `rebuild_and_deploy.sh` (build + restart + **Cloudflare cache purge**). |
| Can't reach it remotely | Use a tunnel/reverse proxy (`docs/_faq/remote_access.md`); never expose HTTP. |

**Run debug mode** (`docs/_faq/debug.md`): stop the service, `cd` into the install
dir, `source venv/bin/activate`, `python terrariumPI.py`; "…is up and running at
address: http://…:8090 in Ns" means it's ready; **Ctrl+C once** to stop.

**Known-harmless log noise** (`docs/_faq/known_errors.md`): bottle *"Absolute template
path names are deprecated"* (TerrariumPI doesn't use bottle templates — ignore);
cryptography *Python 3.7 no longer supported* (only old **buster** OS — ignore).

**More FAQ** in `docs/_faq/`: `systemd`, `login`, `remote_access`,
`reset_authentication`, `reset_webgui`, `kasa_authentication`, `remote_data`,
`upgrading`, `clean_database`, `tune_database`, `delete_data`, `backup`, `restoring`,
`re-use_relays`, `energenie`, `unsplash`. **Setup guides:**
`docs/PUBLIC_ACCESS_SETUP.md`, `docs/SWITCHBOT_BLE_SETUP.md`,
`docs/GECKO_TRACKING_STRATEGY.md`, `KASA_CREDENTIALS_GUIDE.md`.

---

## Conventions, gotchas & cheat sheet

- **GPIO numbering is physical (1–40)** everywhere in the UI/DB; the software translates
  to BCM for supported devices (`terrariumUtils.to_BCM_port_number`). The analog
  **MCP3008** is expected on physical GPIO **19, 21, 23, 24** (channels 0–7).
- **gevent must be patched first** — `terrariumPI.py:4–6` (`monkey.patch_all()`).
- **Version source of truth:** `__version__` in `terrariumPI.py` (`Makefile`, CI, and
  `install.sh` derive the version from it).
- **Logs are on tmpfs** (`/dev/shm`) → lost on reboot; only the nightly archive survives.
- **`SALT` is device-bound** — don't move a DB across Pi without re-entering encrypted
  values (§7).
- **Encrypted DB fields** are Fernet-protected and silently pass-through on a bad key
  (§7). **The login password is bcrypt-hashed and irrecoverable.**
- **Hardware drivers** self-register via a `HARDWARE` class attribute and are discovered
  by filename through `loadHardwareDrivers` (`terrariumUtils.py:546`); a bad driver file
  is logged and skipped (`:553`), not fatal.
- **Formatters:** Black `-l 120 -t py37`; Prettier `printWidth 120` / single quotes /
  2-space (`.md` → 80).
- **The `.py` migrations are broken under yoyo 9.x** and there's a `002`/`0002` version
  collision — fix before relying on a fresh DB (§6).

**Cheat sheet**
```bash
# device service
sudo service terrariumpi start|stop|restart; sudo systemctl status terrariumpi
journalctl -u terrariumpi -f
# inspect DB (read-only, WAL-safe)
sqlite3 -readonly -header -column data/terrariumpi.db "SELECT id,name FROM Enclosure;"
# debug run
cd /home/pi/TerrariumPI && source venv/bin/activate && python terrariumPI.py
# rebuild GUI + redeploy
./rebuild_and_deploy.sh
# tests
pip install -r requirements-dev.txt && python -m pytest tests/ -v
# frontend
npm install && npm run dev        # dev watch on :5000 (API_URL=localhost:8090)
npm run build && npm run start    # prod build + serve public/ on :5000
```

---

### What was verified vs. not
- **Verified by running here:** the §6 fresh-DB crash (`OperationalError: no such table:
  Feeder`), the yoyo-9 `.py`-migration no-op, the real `.schema` dump and query results,
  the encryption pass-through behaviour, the `forward(backend)` no-op under
  `yoyo-migrations==9.0.0`, the Docker entrypoint/CMD/HEALTHCHECK, and the API route
  counts (118 + 6).
- **Static analysis (read, not executed):** the §9 off-Pi crash/degrade classifications
  and the frontend wiring/CI table. The off-Pi *backend* path was **not** run on a real
  x86/Linux host here; treat it as a starting recipe, not a tested one.
