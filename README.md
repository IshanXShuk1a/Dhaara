# DHAARA - AI-Powered Adaptive Traffic Management System

DHAARA is an adaptive traffic-signal control platform designed for modern intelligent transportation systems (ITS). It detects and tracks vehicles per lane, computes explainable traffic-pressure scores per direction, decides which direction should receive the next GREEN phase and for how long, transitions the signal through a safety-enforced finite state machine (FSM), detects and grants emergency priority to approaching ambulances via temporal confirmation, tracks helmet compliance as an independent road-safety signal, coordinates regional traffic corridors across multiple intersections, and exposes live operational telemetry over REST and WebSocket to a Next.js control dashboard.

---

## 1. Complete System Architecture & Pipeline

```text
CAMERA / VIDEO (RTSP, File, Webcam, or Simulation Source)
        ↓
VIDEO INGESTION (services/cv/video_source.py)
        ↓
OBJECT DETECTION (services/cv/detector.py: YOLODetector | SimulationDetector)
        ↓
CV HEURISTIC CLASSIFIERS
  ├─ AmbulanceDetector (services/cv/ambulance_detector.py - livery & strobe peak analysis)
  └─ HelmetDetector (services/cv/helmet_detector.py - head crop & HSV spatial analysis)
        ↓
OBJECT TRACKING (services/cv/tracker.py: CentroidIoUTracker - persistent track IDs)
        ↓
LANE ASSIGNMENT (services/cv/lane_assigner.py - polygon ROI, speed, stopped/waiting time)
        ↓
LANE INTELLIGENCE ENGINE (services/lanes/lane_intelligence.py)
  └─ Computes Traffic Pressure (0-100) & classifies FREE, LOW, MODERATE, HIGH, CONGESTED
        ↓
DECISION & SAFETY ENGINES (Parallel & Decoupled)
  ├─ Ambulance Confirmation (services/emergency/ambulance_confirmation.py - N qualifying frames)
  │    └─ Emergency Manager (services/emergency/emergency_manager.py - DETECTED -> CONFIRMED -> PRIORITY_ACTIVE -> PASSED -> RESOLVED)
  ├─ Traffic Decision Engine (services/decision/decision_engine.py + fairness.py - pressure-driven selection & starvation prevention)
  └─ Helmet Analyzer (services/safety/helmet_analyzer.py - safety stats & violation events; STRICTLY decoupled from signal timing)
        ↓
SIGNAL SAFETY STATE MACHINE (services/signals/signal_fsm.py)
  └─ Strictly enforces GREEN -> YELLOW -> ALL_RED -> GREEN (no green-to-green transitions)
        ↓
SIGNAL HARDWARE ABSTRACTION CONTROLLER (services/signals/signal_controller.py)
  ├─ SimulationSignalController (in-memory test & simulation driver)
  └─ HardwareSignalController (interface for physical NEMA TS2, 170, 2070 traffic controllers)
        ↓
INTERSECTION CONTROLLER (services/controllers/intersection_controller.py)
  └─ Autonomous controller per intersection; owns its own tracker, FSM, and emergency state
        ↓
REGIONAL TRAFFIC COORDINATOR (services/controllers/regional_coordinator.py)
  └─ Aggregates multi-intersection corridor state, green waves, and regional network telemetry
        ↓
FASTAPI REST & WEBSOCKET ENGINE (app/api/routes/*.py, app/api/websocket.py)
        ↓
NEXT.JS OPERATOR DASHBOARD (frontend/src/app, src/components)
```

---

## 2. Key Modules & Implementations

### A. Computer Vision & Heuristic Analyzers
1. **Video Ingestion:** `VideoSource` abstraction supporting uploaded files (`UploadedVideoSource`), webcams (`WebcamSource`), RTSP streams (`RTSPVideoSource`), and scripted simulation (`SimulationSource`).
2. **YOLO Detection & Heuristic Integration:** `YOLODetector` integrates `ultralytics` YOLO models. Vehicles classified as `car`, `bus`, `truck`, or `motorcycle` pass through specialized heuristic filters:
   - `AmbulanceDetector`: Analyzes vehicle livery, HSV red/orange emergency tone distribution, white body ratio, and top-quarter emergency light bar luminance peaks to identify ambulances without requiring proprietary custom models.
   - `HelmetDetector`: Crops the upper 30% head region of detected motorcycle riders, analyzes HSV skin tone vs specular reflection/protective helmet coloration, and emits `HELMET`, `NO_HELMET`, or `UNKNOWN`.
3. **Centroid + IoU Tracker:** Assigns persistent integer track IDs, updates bounding box kinematics, computes instantaneous velocity, and tolerates frame occlusions (configurable `max_missed_frames`).
4. **Lane Assigner:** Projects track centroids into configurable lane polygons using ray casting (`point_in_polygon`), calculates lane-specific stopped states, and measures waiting time accumulation.
5. **Overlay Renderer:** Generates real-time annotated visual frames with lane boundaries, semi-transparent status heat fill, vehicle bounding boxes, track IDs, speed vectors, ambulance emergency tags, and helmet violation badges. Toggles for boxes, IDs, lane polygons, and occupancy heat fill can be adjusted on the fly.

### B. Traffic Intelligence & Decision Engine
1. **Explainable Traffic Pressure Formula:**
   $$\text{Pressure} = w_{\text{occ}} \cdot O + w_{\text{queue}} \cdot \left(\frac{Q}{Q_{\max}}\right) + w_{\text{wait}} \cdot \left(\frac{W}{W_{\max}}\right) + w_{\text{count}} \cdot \left(\frac{C}{C_{\max}}\right) + w_{\text{speed}} \cdot \max\left(0, 1 - \frac{S}{S_{\text{free}}}\right)$$
   Normalized to `[0, 100]` and classified into `FREE`, `LOW`, `MODERATE`, `HIGH`, or `CONGESTED`.
2. **Decision Engine & Starvation Prevention:**
   - Evaluates real-time pressure across all approaches.
   - Dynamic green time allocation: scales from `minimum_green_s` up to `maximum_green_s` based on measured demand.
   - `FairnessTracker`: Prevents approach starvation by enforcing `consecutive_priority_limit` (default: 3 wins max before an approach is temporarily skipped in favor of waiting traffic).
   - Generates explicit human-readable reasons stating vehicle count, queue length, waiting time, and pressure percentage.

### C. Signal Safety FSM & Signal Modes
1. **Guaranteed Safe Transitions:**
   - States: `GREEN -> YELLOW -> ALL_RED -> GREEN`.
   - Direct GREEN-to-GREEN transitions are structurally impossible.
   - Enforces configurable `minimum_green_s` before terminating green, unless safely overridden by an emergency vehicle with forced early yellow.
2. **Signal Modes:**
   - `ADAPTIVE`: Dynamic, AI-driven traffic pressure decisions.
   - `FIXED`: Rigid 30-second fixed-time cycling per approach.
   - `MANUAL`: Operator hold/override for specific approaches (e.g. VIP convoy or traffic police intervention).

### D. Emergency Vehicle Priority (Ambulance)
1. **Temporal Confirmation Tracker:**
   - Single-frame detections are marked as `CANDIDATE`.
   - An ambulance is only `CONFIRMED` after qualifying across $N$ frames (default: 8 frames) within a sliding time window (default: 4.0s).
   - Directional vector analysis verifies that the ambulance is actively approaching the intersection center.
2. **Emergency Lifecycle:**
   `DETECTED -> CONFIRMED -> PRIORITY_REQUESTED -> PRIORITY_ACTIVE -> PASSED -> RESOLVED`.
3. **FSM Preemption:** Triggers safe early termination of the conflicting phase (with standard yellow and clearance all-red) to provide green wave priority.

### E. Independent Road Safety (Helmet Compliance)
- `HelmetAnalyzer` tracks motorcycle helmet compliance as a distinct safety signal.
- Deliberately decoupled from signal control: a helmet violation **never alters signal timing** or phase selection.
- Generates timestamped, track-referenced `SafetyEvent` records stored in the database and displayed on the safety dashboard.

### F. Regional Corridor Coordination & Multi-Intersection
- `RegionalTrafficCoordinator` monitors multiple intersections across city zones (seeded with `OD-BBSR-001`, `OD-BBSR-002`, `OD-BBSR-003`, and `OD-BBSR-004`).
- Computes corridor-wide throughput, average network delay, and overall network health (`ONLINE`, `HIGH_TRAFFIC`, `EMERGENCY`).
- Supports future green wave progression offsets between adjacent controllers.

---

## 3. Repository Structure

```text
code/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/        # REST endpoints (health, auth, intersections, lanes, traffic, signals, video, emergency, safety, analytics, simulation, events, config)
│   │   │   └── websocket.py   # High-throughput real-time WebSocket handler (/ws/intersections/{id})
│   │   ├── core/              # Config, domain parameters, JWT auth with native bcrypt, logging, state
│   │   ├── database/          # SQLAlchemy session management and SQLite/Postgres DB setup
│   │   ├── models/            # Database ORM models (snapshots, signals, decisions, emergencies, safety, events)
│   │   ├── schemas/           # Pydantic schemas for requests and responses
│   │   ├── services/
│   │   │   ├── analytics/     # Regional and intersection historical aggregation service
│   │   │   ├── controllers/   # Autonomous IntersectionController & RegionalTrafficCoordinator
│   │   │   ├── cv/            # Ingestion, YOLODetector, AmbulanceDetector, HelmetDetector, Tracker, LaneAssigner, OverlayRenderer
│   │   │   ├── decision/      # TrafficDecisionEngine & FairnessTracker
│   │   │   ├── emergency/     # Ambulance temporal confirmation & EmergencyManager
│   │   │   ├── lanes/         # LaneIntelligenceEngine & traffic pressure formulas
│   │   │   ├── safety/        # HelmetAnalyzer & safety metrics
│   │   │   ├── signals/       # SignalFSM, SimulationSignalController, HardwareSignalController
│   │   │   ├── simulation/    # Scripted scenario engine for testing and demonstrations
│   │   │   └── event_bus.py   # In-process pub/sub event bus with DB persistence
│   │   ├── tests/             # Unit and integration test suites (signal FSM, tracker, decision, CV detectors, modes, API)
│   │   └── main.py            # FastAPI application assembly, lifespan lifecycle, background control loop
│   ├── scripts/
│   │   ├── generate_synthetic_video.py  # Generates synthetic test video backdrop
│   │   └── run_pipeline_demo.py         # Full end-to-end integration demo runner
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── app/               # Next.js App Router pages (Dashboard, Intersections, Analytics, Emergencies, Safety, Simulation, Settings, Login)
    │   ├── components/        # UI components (DecisionCard, SignalCard, LiveVideoCard, LaneCard, KpiCard, PressureChart, EventTimeline)
    │   └── lib/               # Typed API client, WebSocket subscription hook, AuthContext, IntersectionContext
    ├── package.json
    ├── tailwind.config.ts
    └── .env.local.example
```

---

## 4. Setup & Running Instructions

### Backend (FastAPI + Python 3.10+)

1. Navigate to the backend directory and activate the virtual environment:
   ```bash
   cd backend
   # Linux / macOS:
   python3 -m venv .venv && source .venv/bin/activate
   # Windows PowerShell:
   python -m venv .venv; .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment:
   ```bash
   cp .env.example .env
   ```

4. Generate synthetic test video (optional, for environments without real camera feeds):
   ```bash
   python scripts/generate_synthetic_video.py ./videos/sample_intersection.mp4
   ```

5. Launch the backend server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

   *Default Credentials:*
   - **Username:** `admin`
   - **Password:** `dhaara-admin` (auto-seeded on initial startup)

### Frontend (Next.js 14 + React 18 + Tailwind CSS)

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   npm install
   ```

2. Configure environment:
   ```bash
   cp .env.local.example .env.local
   # Ensure NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
   ```

3. Launch development server:
   ```bash
   npm run dev
   ```
   Open `http://localhost:3000` in your browser.

---

## 5. Judge Demonstration Guide (6 Live Scenarios)

The DHAARA dashboard includes an interactive **Simulation & Manual Control Console** at `/simulation` designed specifically for live demonstrations and judging evaluations.

### Scenario 1: Heavy Traffic Congestion & Autonomous Dynamic Signal Shift
1. Navigate to **Simulation** (`/simulation`).
2. Under "Presets", click **"Heavy South Traffic"** (sets South vehicles to 28, others to 2-4).
3. Return to **Dashboard** (`/`).
4. **Observe:**
   - The South approach lane card turns red (`CONGESTED`), with Queue Length and Traffic Pressure spiking above 80%.
   - The **Decision Card** explains: *"Selected SOUTH for 48s. Highest traffic pressure (86.4%). Queue length: 52.0m. Average waiting time: 44.0s."*
   - The **Signal Card** safely transitions: North turns YELLOW (3s) -> ALL_RED (2s) -> South turns GREEN.

### Scenario 2: Traffic Demand Shift & Dynamic Re-allocation
1. In `/simulation`, click **"Heavy East Traffic"** (East vehicles spike to 27, South returns to normal).
2. Return to `/`.
3. **Observe:**
   - Traffic pressure immediately recalculates for the East approach.
   - When the South green timer completes (or maximum green is reached), the Decision Engine allocates the next green phase to East.
   - The **Pressure Chart** displays the real-time pressure crossover.

### Scenario 3: Ambulance Emergency Priority & Temporal Confirmation
1. In `/simulation`, find "Emergency Vehicle Injection".
2. Select Approach **WEST** and click **"Spawn Approaching Ambulance"**.
3. Return to `/` or open `/emergencies`.
4. **Observe:**
   - TopBar displays a pulsing **`PRIORITY: CONFIRMED`** badge.
   - The Emergency Card moves through `DETECTED -> CONFIRMED -> PRIORITY_REQUESTED -> PRIORITY_ACTIVE`.
   - The Signal FSM terminates any conflicting green with safety clearances (YELLOW -> ALL_RED) and grants immediate priority GREEN to WEST.
   - When the ambulance passes, priority clears and normal adaptive control resumes.

### Scenario 4: Helmet Violation & Safety Decoupling Verification
1. In `/simulation`, find "Road Safety Injection".
2. Select Approach **NORTH**, choose Status **"NO HELMET"**, and click **"Report Helmet Observation"**.
3. Return to `/` or open `/safety`.
4. **Observe:**
   - The KPI card "Helmet Violations" increments.
   - The Event Timeline logs a `HELMET_VIOLATION` event with track ID and confidence.
   - **Crucial Safety Assertion:** The active signal phase and countdown are **completely unaffected**, proving that motorcycle safety monitoring runs in parallel without interfering with signal safety.

### Scenario 5: Police & Operator Manual Override
1. In `/simulation`, scroll to "Police & Operator Manual Signal Override".
2. Select **MANUAL** mode, pick Target Approach **NORTH**, and click **"Apply Mode & Override"**.
3. Return to `/`.
4. **Observe:**
   - The TopBar mode indicator switches to **`MANUAL`**.
   - The Signal Card holds GREEN on NORTH indefinitely.
   - When finished, switch mode back to **`ADAPTIVE`** to re-engage automated pressure-based decisions.

### Scenario 6: Regional Corridor Network Monitoring
1. Click **Intersections** (`/intersections`) or **Analytics** (`/analytics`).
2. **Observe:**
   - City-wide regional corridor view with 4 active nodes (`OD-BBSR-001`, `OD-BBSR-002`, `OD-BBSR-003`, `OD-BBSR-004`).
   - Live status badges reflecting `ONLINE`, `HIGH_TRAFFIC`, or `EMERGENCY`.
   - Aggregated network-wide vehicle count, average network delay, and throughput metrics.

---

## 6. Real Hardware vs. Simulation Architecture

DHAARA is architected so that the simulation engine is strictly an input adapter for demonstrations and testing; the core intelligence and safety pipeline is identical in production.

| Pipeline Component | Simulation Mode (Judge Demo) | Real-World Production Deployment |
|---|---|---|
| **Video Source** | `SimulationSource` / `UploadedVideoSource` reading looped MP4 | `RTSPVideoSource` connecting to 4K H.264/H.265 IP traffic cameras via ONVIF/RTSP |
| **Object Detection** | `SimulationDetector` generating parameterized detections | `YOLODetector` executing YOLOv8/YOLOv11 on edge NVIDIA Jetson or discrete GPU |
| **Emergency Detection** | Scripted ambulance triggers or livery/strobe analysis | Real-time siren acoustic sensors (CAN bus) + camera livery strobe peak analysis |
| **Signal Controller** | `SimulationSignalController` mutating internal state | `HardwareSignalController` communicating over NTCIP 1202 / NEMA TS2 / 170 / 2070 controller cabinets |
| **Lane Sensors** | Bounding box spatial projection into polygon ROIs | Calibrated camera homography matrices + inductive loop detector telemetry |
| **Data Persistence** | Local SQLite (`dhaara.db`) | High-availability PostgreSQL with TimescaleDB time-series indexing |

---

## 7. Automated Test Suite

Run the unit test suite:
```bash
cd backend
python -m unittest discover -s app/tests -p "test_*.py" -v
```

Tests cover:
- `test_signal_fsm.py`: Guaranteed color sequence (`GREEN -> YELLOW -> ALL_RED -> GREEN`), minimum green enforcement, emergency preemption.
- `test_lane_intelligence.py`: Pressure formula boundary conditions, explainable reason generation, speed weighting.
- `test_emergency.py`: Ambulance temporal confirmation window, sliding frame threshold, emergency state lifecycle.
- `test_decision_engine.py`: Pressure-based direction selection, green time scaling, fairness starvation prevention.
- `test_tracker_and_lanes.py`: Persistent track ID assignment, occlusion tolerance, stopped vehicle accumulation.
- `test_helmet_analyzer.py`: Helmet compliance rate calculation, single-event emission, architectural decoupling guard.
- `test_cv_detectors_and_modes.py`: Ambulance heuristic classifier, helmet head crop classifier, FIXED and MANUAL controller modes.
- `test_signal_controller.py`: Hardware abstraction interface validation.
