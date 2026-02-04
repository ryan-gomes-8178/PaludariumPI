# Crested Gecko Activity Tracking System - Implementation Strategy

## Executive Summary

This document outlines a comprehensive strategy to leverage your Raspberry Pi
camera and IR illuminator to track and analyze your crested gecko's nighttime
behavior, eventually incorporating AI for activity summaries.

---

## Current System Analysis

### Existing Infrastructure

- **Camera**: Raspberry Pi camera with IR illuminator
- **Current Streaming**: Live HLS streaming via TerrariumPI
  (`rpilive_webcam.sh`)
- **Technology Stack**:
  - FFmpeg for video processing
  - OpenCV (v4.11.0.86) already installed
  - Python 3 environment
  - Gevent web server

### Data Flow

```
RPI Camera → raspivid/rpicam-vid → FFmpeg → HLS Stream → TerrariumPI Web Interface
```

---

## Approach Evaluation

### Option 1: Integrated TerrariumPI Module ❌

**Description**: Extend TerrariumPI directly with motion detection capabilities

**Pros**:

- Single application to manage
- Direct access to camera configuration
- Unified database and UI

**Cons**:

- Tight coupling could impact main system stability
- CPU-intensive processing could affect TerrariumPI responsiveness
- Harder to iterate and debug
- Risk of breaking existing webcam functionality
- Difficult to scale processing independently

**Verdict**: NOT RECOMMENDED - Too risky for main system stability

---

### Option 2: Parallel Video Stream Tap 🔶

**Description**: Create a separate service that taps into the raw camera feed
before TerrariumPI

**Pros**:

- Independent processing pipeline
- No impact on existing streaming
- Can use hardware acceleration

**Cons**:

- Camera can't typically support multiple simultaneous captures
- Complex coordination with TerrariumPI
- Resource contention issues
- May require stopping/starting TerrariumPI webcam

**Verdict**: TECHNICALLY CHALLENGING - Camera resource conflicts

---

### Option 3: HLS Stream Consumer with Separate Service ✅ RECOMMENDED

**Description**: Build an independent microservice that consumes the existing
HLS stream from TerrariumPI and performs motion detection/tracking

**Pros**:

- ✅ Zero impact on TerrariumPI stability
- ✅ Iterative development - start simple, add complexity
- ✅ Independent scaling and resource management
- ✅ Easy to enable/disable without affecting main system
- ✅ Can process at lower FPS to save resources
- ✅ Clear separation of concerns
- ✅ Easy to add multiple analysis pipelines
- ✅ Existing stream already optimized by TerrariumPI
- ✅ RESTful API can integrate back into TerrariumPI UI later

**Cons**:

- Slight latency from HLS segmentation (2-second chunks)
- Dependent on TerrariumPI stream being active
- Need to handle stream availability

**Verdict**: **BEST APPROACH** - Safest, most flexible, and iterative

---

### Option 4: Computer Vision SBC (Coral/Jetson) 🔶

**Description**: Use dedicated AI hardware for processing

**Pros**:

- Hardware-accelerated inference
- No impact on main RPI resources
- Future-ready for advanced AI

**Cons**:

- Additional hardware cost ($60-400)
- Overkill for initial implementation
- Same integration challenges as Option 3

**Verdict**: FUTURE CONSIDERATION - Great for Phase 4+ once basic system works

---

## Recommended Architecture: Gecko Tracking Microservice

### System Design

```
┌─────────────────────────────────────────────────────────────────┐
│                         TerrariumPI System                      │
│  ┌──────────────┐                                              │
│  │ RPI Camera + │──→ FFmpeg ──→ HLS Stream (/webcam/*.m3u8)   │
│  │ IR Illum.    │                     │                         │
│  └──────────────┘                     │                         │
└───────────────────────────────────────┼─────────────────────────┘
                                        │
                                        ↓ (HTTP/File System)
┌─────────────────────────────────────────────────────────────────┐
│              Gecko Tracking Service (New)                       │
│                                                                  │
│  ┌─────────────────┐    ┌──────────────────┐                   │
│  │ Stream Consumer │ ─→ │ Motion Detection │                   │
│  │  (HLS Reader)   │    │   (OpenCV)       │                   │
│  └─────────────────┘    └──────────────────┘                   │
│                                   │                              │
│                                   ↓                              │
│  ┌─────────────────┐    ┌──────────────────┐                   │
│  │ SQLite Database │ ←─ │ Tracking Engine  │                   │
│  │ (Activity Log)  │    │ (Hotspot/Path)   │                   │
│  └─────────────────┘    └──────────────────┘                   │
│                                   │                              │
│                                   ↓                              │
│  ┌─────────────────┐    ┌──────────────────┐                   │
│  │   REST API      │ ←─ │ Analytics Engine │                   │
│  │  (Flask/FastAPI)│    │ (Statistics)     │                   │
│  └─────────────────┘    └──────────────────┘                   │
│                                                                  │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ↓ (API Integration - Phase 4)
                    TerrariumPI Dashboard
                    (New UI Panel for Gecko Activity)
```

---

## Iterative Implementation Plan

### **Phase 1: Foundation - Stream Consumer & Basic Motion Detection**

**Duration**: 1-2 days  
**Goal**: Prove the concept with basic motion detection

#### Deliverables:

1. **Standalone Python Service**
   - Reads HLS stream from TerrariumPI
   - Processes frames at 1-5 FPS
   - Implements background subtraction (MOG2)
   - Detects motion events (binary: motion/no-motion)
   - Logs to console with timestamps

2. **Technology Stack**:
   - Python 3
   - OpenCV for video processing
   - `ffmpeg-python` or `opencv` for HLS reading
   - Simple logging framework

3. **Success Criteria**:
   - Service can read HLS stream reliably
   - Detects when gecko moves
   - Runs independently from TerrariumPI
   - Resource usage < 25% CPU on RPI

#### Files Created:

```
gecko-tracking/
├── requirements.txt
├── main.py                    # Entry point
├── stream_consumer.py         # HLS stream reader
├── motion_detector.py         # OpenCV motion detection
└── config.yaml               # Configuration
```

---

### **Phase 2: Motion Tracking & Data Persistence**

**Duration**: 2-3 days  
**Goal**: Track individual movements and store data

#### Deliverables:

1. **Enhanced Motion Detection**
   - Blob detection for gecko body
   - Centroid tracking
   - Movement vector calculation (direction, speed)
   - Filter out false positives (IR reflections, etc.)

2. **Data Storage**
   - SQLite database for activity logs
   - Schema:
     ```sql
     CREATE TABLE motion_events (
         id INTEGER PRIMARY KEY,
         timestamp DATETIME,
         centroid_x INTEGER,
         centroid_y INTEGER,
         blob_size INTEGER,
         movement_vector TEXT,  -- JSON: {dx, dy, magnitude}
         confidence REAL,
         frame_reference TEXT   -- Optional: save frame
     );
     ```

3. **Basic Visualization**
   - Generate heatmap overlays
   - Export daily activity plots (matplotlib)

#### New Files:

```
gecko-tracking/
├── database.py               # SQLite operations
├── tracker.py                # Object tracking logic
├── visualizer.py             # Heatmap generation
└── data/
    └── gecko_activity.db
```

---

### **Phase 3: Activity Analysis & Insights**

**Duration**: 3-5 days  
**Goal**: Extract meaningful behavior patterns

#### Deliverables:

1. **Spatial Analysis**
   - **Hotspots**: Identify frequently visited zones
   - **Rest spots**: Detect stationary periods (>5 mins)
   - **Feeding zone correlation**: Cross-reference with known feeder location
   - **Movement paths**: Track sequential movements

2. **Temporal Analysis**
   - Activity timeline (hourly breakdown)
   - Peak activity hours
   - Night-to-night comparison
   - Activity duration statistics

3. **REST API**
   - Flask/FastAPI server
   - Endpoints:
     - `GET /api/activity/today` - Today's summary
     - `GET /api/activity/range?start=&end=` - Date range
     - `GET /api/heatmap?date=` - Heatmap image
     - `GET /api/stats/weekly` - Weekly statistics
     - `GET /api/events/latest?limit=50` - Recent events

4. **Configuration System**
   - Define zones of interest (feeding, basking, hide)
   - Sensitivity tuning
   - Schedule (nighttime-only processing)

#### New Files:

```
gecko-tracking/
├── api/
│   ├── __init__.py
│   ├── app.py                # FastAPI/Flask app
│   └── routes.py             # API endpoints
├── analytics/
│   ├── spatial.py            # Hotspot/path analysis
│   ├── temporal.py           # Time-based stats
│   └── zone_detector.py      # Zone correlation
├── config/
│   └── zones.json            # Defined zones
└── static/
    └── heatmaps/             # Generated images
```

---

### **Phase 4: TerrariumPI Integration**

**Duration**: 2-3 days  
**Goal**: Surface insights in TerrariumPI dashboard

#### Deliverables:

1. **API Bridge**
   - TerrariumPI proxy endpoints to gecko-tracking service
   - Authentication/authorization

2. **UI Dashboard Panel**
   - New tab/section in TerrariumPI web interface
   - Display real-time activity status
   - Show heatmaps and statistics
   - Activity timeline widget

3. **Database Cross-Reference**
   - Correlate gecko activity with:
     - Temperature/humidity logs
     - Feeding schedules
     - Light cycles

#### Modified Files:

```
TerrariumPI/
├── terrariumAPI.py           # Add proxy endpoints
├── terrariumWebserver.py     # Add routes
└── gui/
    ├── pages/
    │   └── GeckoActivity.svelte  # New page
    └── components/
        ├── HeatmapViewer.svelte
        └── ActivityTimeline.svelte
```

---

### **Phase 5: AI-Powered Insights (Future)**

**Duration**: 1-2 weeks  
**Goal**: Natural language activity summaries

#### Deliverables:

1. **Behavior Classification**
   - Train/use ML model to classify activities:
     - Hunting
     - Exploring
     - Resting
     - Eating
     - Grooming

2. **Activity Summarization**
   - Use local LLM (Ollama) or cloud API (OpenAI)
   - Generate daily reports:
     - "Tonight, your gecko was active for 3.5 hours, primarily exploring the
       upper left quadrant. Visited the feeding station at 11:45 PM for
       approximately 8 minutes."

3. **Anomaly Detection**
   - Alert for unusual patterns
   - Health monitoring indicators

---

## Technical Specifications

### Resource Requirements

#### Raspberry Pi Considerations:

- **Minimum**: RPI 4 with 2GB RAM
- **Recommended**: RPI 4 with 4GB+ RAM
- **Processing Load**: ~15-30% CPU for motion detection at 2 FPS
- **Storage**: ~100MB/week for activity database

#### Optimization Strategies:

1. **Frame Rate Limiting**: Process 1-5 FPS (vs. 30 FPS stream)
2. **Region of Interest**: Only analyze terrarium area
3. **Adaptive Sensitivity**: Lower during inactivity
4. **Scheduled Processing**: Only run during nighttime hours
5. **Hardware Acceleration**: Use OpenCV with OpenCL/NEON where available

---

### Motion Detection Algorithm

#### Background Subtraction (Phase 1):

```python
# MOG2 Background Subtractor
bg_subtractor = cv2.createBackgroundSubtractorMOG2(
    history=500,           # Frames to consider for background
    varThreshold=16,       # Threshold for shadow detection
    detectShadows=True     # Ignore shadows (IR artifacts)
)

# Apply
fg_mask = bg_subtractor.apply(frame)
```

#### Object Tracking (Phase 2):

```python
# Find contours
contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# Filter by area (gecko size)
MIN_GECKO_SIZE = 1000  # pixels
MAX_GECKO_SIZE = 8000

for cnt in contours:
    area = cv2.contourArea(cnt)
    if MIN_GECKO_SIZE < area < MAX_GECKO_SIZE:
        # Calculate centroid
        M = cv2.moments(cnt)
        cx = int(M['m10'] / M['m00'])
        cy = int(M['m01'] / M['m00'])
        # Track this position
```

---

## Development Environment Setup

### Directory Structure:

```
TerrariumPI/                    # Your existing project
└── ...

gecko-tracking/                 # New sibling directory
├── .env                       # Environment variables
├── .gitignore
├── README.md
├── requirements.txt
├── config.yaml               # Main configuration
├── docker-compose.yml        # Optional: containerize
├── main.py                   # Service entry point
├── src/
│   ├── __init__.py
│   ├── stream_consumer.py
│   ├── motion_detector.py
│   ├── tracker.py
│   ├── database.py
│   ├── visualizer.py
│   └── api/
│       ├── __init__.py
│       └── app.py
├── data/
│   ├── gecko_activity.db
│   └── heatmaps/
├── logs/
│   └── gecko_tracking.log
└── tests/
    └── ...
```

---

## Configuration Management

### config.yaml Example:

```yaml
# Gecko Tracking Configuration

# Stream Source
stream:
  url: 'http://localhost:8090/webcam/camera1/stream.m3u8'
  fps_target: 2 # Process every N frames
  timeout: 30 # Reconnect timeout

# Motion Detection
motion:
  sensitivity: 16
  min_area: 1000
  max_area: 8000
  history_frames: 500
  region_of_interest:
    enabled: true
    x: 0
    y: 0
    width: 640
    height: 480

# Tracking
tracking:
  stationary_threshold: 5 # Minutes before considering "at rest"
  max_tracking_distance: 100 # Pixels

# Zones (defined coordinates)
zones:
  feeding:
    name: 'Feeding Station'
    x: 100
    y: 200
    radius: 50
  basking:
    name: 'Basking Spot'
    x: 500
    y: 100
    radius: 80
  hide:
    name: 'Hide Box'
    x: 300
    y: 400
    radius: 70

# Schedule
schedule:
  enabled: true
  start_time: '20:00' # 8 PM
  end_time: '08:00' # 8 AM

# Database
database:
  path: './data/gecko_activity.db'
  backup_enabled: true
  backup_interval: 'daily'

# API
api:
  enabled: true
  host: '0.0.0.0'
  port: 5001
  cors_enabled: true

# Logging
logging:
  level: 'INFO'
  file: './logs/gecko_tracking.log'
```

---

## Integration Points with TerrariumPI

### 1. Stream Access

- **Method**: HTTP request to existing HLS endpoint
- **URL Pattern**: `http://localhost:8090/webcam/{camera_id}/stream.m3u8`
- **No modifications needed** to TerrariumPI

### 2. API Integration (Phase 4)

Add proxy endpoints to [terrariumAPI.py](terrariumAPI.py):

```python
# In terrariumAPI.py
import requests

GECKO_TRACKING_API = "http://localhost:5001/api"

@app.route('/api/gecko/activity/today')
def gecko_activity_today():
    response = requests.get(f"{GECKO_TRACKING_API}/activity/today")
    return response.json()

@app.route('/api/gecko/heatmap')
def gecko_heatmap():
    date = request.args.get('date', 'today')
    response = requests.get(f"{GECKO_TRACKING_API}/heatmap", params={'date': date})
    return response.content, 200, {'Content-Type': 'image/png'}
```

### 3. UI Integration

Create new Svelte component in
[gui/pages/GeckoActivity.svelte](gui/pages/GeckoActivity.svelte)

### 4. Data Correlation

Query TerrariumPI's database to correlate gecko activity with environmental
conditions:

```python
# Example: Get temperature during high activity
SELECT
    g.timestamp,
    g.centroid_x,
    g.centroid_y,
    t.value as temperature,
    h.value as humidity
FROM gecko_tracking.motion_events g
LEFT JOIN terrariumpi.sensor_data t ON t.timestamp BETWEEN g.timestamp - 300 AND g.timestamp
LEFT JOIN terrariumpi.sensor_data h ON h.timestamp BETWEEN g.timestamp - 300 AND g.timestamp
WHERE t.sensor_type = 'temperature'
  AND h.sensor_type = 'humidity'
```

---

## Risk Mitigation

### Potential Issues & Solutions:

| Risk                                   | Impact | Mitigation                                                                                                                         |
| -------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| High CPU usage affects TerrariumPI     | High   | 1. Frame rate limiting<br>2. Scheduled processing (nighttime only)<br>3. Process priority (nice value)<br>4. Hardware acceleration |
| HLS stream unavailable                 | Medium | 1. Retry logic with exponential backoff<br>2. Graceful degradation<br>3. Email alerts on prolonged failure                         |
| False positives (IR reflections, etc.) | Low    | 1. Size filtering<br>2. Shadow detection<br>3. Temporal consistency checks<br>4. Zone-based filtering                              |
| Database growth                        | Low    | 1. Automatic archival of old data<br>2. Aggregated statistics<br>3. Configurable retention policy                                  |
| Service crashes                        | Medium | 1. Systemd service with auto-restart<br>2. Comprehensive error handling<br>3. Watchdog monitoring                                  |

---

## Testing Strategy

### Phase 1 Testing:

- [ ] Stream consumption reliability (24-hour test)
- [ ] CPU/memory usage profiling
- [ ] Motion detection accuracy (manual verification)
- [ ] Frame rate consistency

### Phase 2 Testing:

- [ ] Database write performance
- [ ] Tracking accuracy across frames
- [ ] False positive rate measurement
- [ ] Heatmap generation correctness

### Phase 3 Testing:

- [ ] API response times
- [ ] Zone detection accuracy
- [ ] Statistical calculation verification
- [ ] Multi-day data integrity

### Phase 4 Testing:

- [ ] TerrariumPI integration (no regressions)
- [ ] UI responsiveness
- [ ] Cross-database queries
- [ ] End-to-end workflow

---

## Deployment

### Systemd Service (Linux):

```ini
# /etc/systemd/system/gecko-tracking.service
[Unit]
Description=Gecko Activity Tracking Service
After=network.target terrariumpi.service
Requires=terrariumpi.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/gecko-tracking
ExecStart=/home/pi/gecko-tracking/venv/bin/python main.py
Restart=always
RestartSec=10
Nice=10  # Lower priority than TerrariumPI

[Install]
WantedBy=multi-user.target
```

### Commands:

```bash
sudo systemctl enable gecko-tracking
sudo systemctl start gecko-tracking
sudo systemctl status gecko-tracking
```

---

## Future Enhancements

### Short-term (3-6 months):

- Mobile app notifications for unusual activity
- Integration with feeding logs from TerrariumPI
- Weight correlation (if using smart scale)
- Multi-camera support for larger enclosures

### Long-term (6-12 months):

- Behavior classification ML model
- Health anomaly detection
- Automated highlight reels (video clips of interesting behavior)
- Community data sharing (anonymized behavioral benchmarks)
- Integration with veterinary records

---

## Success Metrics

### Phase 1:

- ✅ Service runs continuously for 7+ days
- ✅ Motion detection accuracy > 90%
- ✅ CPU usage < 25%

### Phase 2:

- ✅ Database stores 1 week of data without issues
- ✅ Heatmaps visually correlate with observed behavior
- ✅ False positive rate < 5%

### Phase 3:

- ✅ API response time < 500ms
- ✅ Zone detection accuracy > 85%
- ✅ Statistics match manual observations

### Phase 4:

- ✅ TerrariumPI dashboard shows gecko data
- ✅ No performance degradation to TerrariumPI
- ✅ User can navigate insights intuitively

---

## Recommended First Steps

1. **Create Project Directory**:

   ```bash
   cd /home/honestliepi/Desktop
   mkdir gecko-tracking
   cd gecko-tracking
   ```

2. **Set Up Virtual Environment**:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Base Dependencies**:

   ```bash
   pip install opencv-python-headless numpy requests pyyaml
   ```

4. **Create Initial Files**:
   - `main.py` - Entry point with basic stream reading
   - `config.yaml` - Configuration
   - `requirements.txt` - Dependencies

5. **Test Stream Access**:
   - Verify you can read the HLS stream URL from TerrariumPI
   - Display frames to confirm video pipeline works

6. **Implement Basic Motion Detection**:
   - Use OpenCV's MOG2 background subtractor
   - Log motion events to console
   - Validate accuracy by observing gecko at night

---

## Conclusion

The **HLS Stream Consumer approach (Option 3)** provides the best balance of:

- **Safety**: No risk to TerrariumPI stability
- **Flexibility**: Easy to iterate and enhance
- **Scalability**: Can grow from basic motion detection to advanced AI
- **Integration**: Clean API-based integration with TerrariumPI

By following the phased approach, you'll have a working motion detection system
within a week, with full analytics within 2-3 weeks, and AI-powered insights as
a future enhancement.

---

**Next Steps**: Ready to begin Phase 1 implementation when you are!
