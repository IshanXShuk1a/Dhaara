# DHAARA - Smart Traffic Management

This document describes the current design and replaces earlier independent-direction signal logic.

## Signal and scoring rules

East and West share one phase (EW); North and South share the other (NS). Both directions in the active pair are GREEN; the opposite pair is RED. Every change passes through a configurable yellow interval (default 3 seconds): the outgoing pair becomes YELLOW while the other stays RED, then the outgoing pair turns RED and the receiving pair becomes GREEN. One immutable signal state owns both paired outputs and the phase clock.

Four independent videos are sampled repeatedly in one shared YOLO inference batch. Only current detections whose bounding-box centers lie inside their camera's measurement polygon contribute. Vehicles behind the far boundary and missed tracks do not count.

Per-direction score:

```text
score = 2 * cars + 1.5 * autos/rickshaws + 1 * two-wheelers
EW = (East score + West score) / 2
NS = (North score + South score) / 2
```

Buses, trucks and ambulances currently use the car weight (2); bicycles use the two-wheeler weight (1). Custom YOLO labels such as `auto`, `autorickshaw`, `auto_rickshaw`, `rickshaw`, `motorbike` and `scooter` are normalized before scoring. Standard COCO YOLOv8n does not distinguish rickshaws: separate rickshaw recognition requires custom-trained weights. The dashboard reports unsupported rickshaw recognition rather than inventing counts. A missing custom model produces an error.

- Normal operation alternates 70-second GREEN phases between EW and NS, even if the same pair remains denser. The yellow interval follows green and the next 70-second green timer starts when yellow finishes. Re-requesting the current pair never restarts its timer.
- At initial startup, a pair leading by at least **20 points** can receive the first phase; smaller differences start with EW.
- Early switching requires the current green pair's average score to remain **<=5 for 3 seconds**, the opposing pair to lead by **at least 20 points**, and **more than 20 seconds** remaining.
- The pair opened early receives a full **70-second green phase after yellow**. It cannot be cut short by another demand switch; normal alternation resumes at its expiry.
- Incomplete camera data disables demand-based switching. Normal timed alternation continues; missing input is not treated as an empty road.
- An ambulance can override demand/timing only while its identity and **flashing emergency lights** are confirmed. A visible ambulance with lights off receives no special green. Red/blue roof-beacon evidence must show repeated on/off transitions across frames; steady markings, headlights and steady light bars do not confirm flashing. Stopped ambulances can qualify. Ambulance priority can use the whole directional camera feed; the 30-foot boundary still limits traffic scores. Emergency priority ends when the visible flashing evidence ends, and the normal phase clock resumes.

Yellow applies to normal timer changes, early switches, manual commands and ambulance priority. Repeated requests cannot restart or bypass yellow. If ambulance flashing evidence ends while its request is pending, yellow still completes and the previous green timer resumes without granting delayed ambulance priority.

ADAPTIVE applies these demand rules. FIXED uses the same paired timer without early demand switching. MANUAL holds the selected pair; a confirmed flashing ambulance can still receive priority. Selecting either EAST/WEST maps to EW, and NORTH/SOUTH maps to NS. Signal output currently uses `SimulationSignalController`.

## Camera setup and the 30-foot boundary

Copy `backend/.env.example` to `backend/.env` and supply four distinct footage paths:

```dotenv
EAST_VIDEO=./videos/east.mp4
WEST_VIDEO=./videos/west.mp4
NORTH_VIDEO=./videos/north.mp4
SOUTH_VIDEO=./videos/south.mp4
MODEL_PATH=./models_store/yolov8n.pt
```

Relative paths resolve under `backend/`. Missing files remain OFFLINE; they do not substitute another camera or synthetic traffic. Automatic regional demo nodes have been removed. Previously seeded demo nodes are removed only if they contain no configured real cameras or non-simulated traffic records. The Simulation page uses a separate educational runtime; it cannot replace the dashboard's camera sources or control its live intersection.

Each camera needs a convex four-point normalized polygon ordered **far-left, far-right, near-right, near-left**. Mark the far edge at a surveyed **30 ft (9.144 m)** from the traffic signal. The default trapezoid is an initial boundary, not proof of physical distance: camera perspective alone cannot establish feet or meters without road measurements.

ADMIN users can select **Set 30 ft boundary** on a camera, redraw the four corners on its frame, and save. Changes persist and apply live. The API also supports:

```text
GET /api/intersections/{id}/lanes
PUT /api/intersections/{id}/lanes
```

PUT requires all four directions. An entry looks like:

```json
{"direction":"EAST","polygon":[[0.35,0.20],[0.65,0.20],[0.90,0.90],[0.10,0.90]],"coordinate_space":"normalized","pixels_per_meter":8,"length_m":9.144,"capacity_vehicles":25}
```

Persisted boundaries take precedence over environment defaults on later starts. `pixels_per_meter` applies to optional speed diagnostics, not weighted scoring.

## Dashboard and records

The dashboard contains paired green/yellow countdowns, four feeds, ROI class counts and lane scores, EW/NS average scores, the current denser pair and ambulance flashing-light status. Charts, forecast data, the old sidebar control panel, fake notifications and inactive search controls are removed.

Master View shows all four feeds. Direction tabs show one full independent camera frame. Boundary overlays, snapshot downloads and fullscreen remain available. Snapshot images are sampled from video for processing; per-frame image files are not continuously written to disk.

Measured lane/pair scores and the denser pair are recorded about every two seconds and on phase changes using the existing structured database event log. Live records are bounded in memory; persisted records survive restart. Educational simulation records remain in the lab's memory and never enter the live database event log or dashboard.

```text
GET /api/intersections/{id}/traffic
GET /api/intersections/{id}/traffic/scores/history
GET /api/intersections/{id}/signal
GET /api/video/frame?intersection_id={id}&direction=EAST
WS  /ws/intersections/{id}
```

Frames retain the full camera perspective. Unavailable cameras return HTTP 503. REST and WebSocket output include weighted lane scores, class counts, pair averages, denser-pair records and paired GREEN/YELLOW/RED maps.

## Educational simulation

Open **Simulation** to explore the WebGL 3D intersection: moving cars, E/W/N/S road labels, crosswalks, paired traffic lights, buildings and trees. Drag to orbit, scroll/pinch to zoom, or select the top view. Case buttons demonstrate balanced traffic, either busy pair and both nearly-empty-green situations. Pause, restart and 1×/2×/5×/10× speeds operate the simulation clock. Ambulance controls demonstrate lights on versus off. Approaching cars stop on red/yellow; vehicles already crossing clear the junction. The scene is a schematic miniature, not a calibrated camera or road model.

`SIMULATION-LAB` is a separate in-memory controller, detector, scenario provider and virtual clock. It uses the production tracking, ROI scoring, paired decision and yellow-transition pipeline, but it has no uploaded camera inputs and is excluded from live intersection lists and regional coordination. All authenticated users, including VIEWER users, can operate this lab; permission to change real signals remains restricted to operators.

The presets are balanced traffic (8 cars in each direction), busy NS (18 cars each in N/S and 4 each in E/W), busy EW (the inverse), and two early-switch cases (2 cars each on the green pair, 18 each on the red pair, and 40 seconds of green remaining). Preset demand is replenished for a repeatable lesson rather than presented as a camera measurement. Pair scores are computed from the scripted detections with the same car weight of 2. Early-switch cases show 3 seconds of empty-demand confirmation, 3 seconds of yellow and a full 70-second receiving phase. Normal timer alternation remains active even when one pair stays busier.

```text
GET  /api/simulation/state
POST /api/simulation/scenario  {"scenario":"balanced"}
POST /api/simulation/control   {"paused":false,"speed":5}
POST /api/simulation/reset
POST /api/simulation/ambulance {"direction":"NORTH","lights_active":true}
WS   /ws/intersections/SIMULATION-LAB
```

Scenario names are `balanced`, `ns_busy`, `ew_busy`, `empty_ew` and `empty_ns`. Speed values are 1, 2, 5 and 10; speed and pause only affect the lab. REST and WebSocket snapshots add `simulation` metadata with the scenario, reset identifier, target counts, paused state, speed, elapsed virtual time and visible ambulance. Ambulance demonstrations render flashing roof pixels through the existing temporal beacon detector; an ambulance with lights off does not receive priority. Simulation routes reject real intersection IDs, and video routes reject the lab ID.

## Run on Windows PowerShell

Install dependencies once from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
```

Configure the four paths and boundaries. Start the backend:

```powershell
Set-Location D:\Github\Dhaara\backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Start the frontend in another terminal:

```powershell
Set-Location D:\Github\Dhaara\frontend
npm ci
npm run dev
```

Open http://localhost:3000. Initial login: `admin` / `dhaara-admin`.

## Validation

```powershell
# From backend/
..\.venv\Scripts\python.exe -m pytest app/tests -q --basetemp=.pytest_cache/test_tmp
..\.venv\Scripts\python.exe scripts/run_pipeline_demo.py
# From frontend/
npx tsc --noEmit --incremental false
npm run build
```

Tests cover class weights, pair means, timing and early-switch boundaries, persistent empty demand, full receiving phases, missing cameras, paired outputs, flashing-light confirmation, source isolation, ROI exclusion, database records and API/WebSocket output. Synthetic beacon tests verify the temporal algorithm; real ambulance identification and flashing-light accuracy still require validation against camera footage.
