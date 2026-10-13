# Changes

## 2026-10-13 — Behaviour audit and project documentation

- Added root `AGENTS.md` with scope, evidence, testing, documentation and change-log maintenance rules.
- Added `architecture.md` describing the current backend, frontend, processing pipeline, runtime isolation, signal rules, evidence sources, interfaces and persistence.
- Fixed ambulance image selection resetting demo lights to OFF. Selecting or swapping into Heavy / ambulance now starts the labelled 12-second lights-ON input on the first click. Detected identity and yellow clearance remain required; Lights off still tests the non-emergency case. Added camera input labels and paused-play guidance.
- Fixed stale image controls and simulation snapshots after a backend restart: both educational runtimes expose immutable session identifiers; frontend revision/reset ordering applies within a session. A new lab session resets the rendered vehicles.
- Fixed paused image sources retaining old counts after a file edit. Reloaded images and measurements now refresh without advancing the virtual clock.
- Fixed lab ambulance commands returning previous detections while paused. Responses now include a zero-duration observation; same-direction lights changes preserve vehicle identity. Explicit OFF clears old beacon history and cancels pending emergency priority through the existing yellow-clearance path. Visual light toggles preserve queues.
- Restricted ROI writes to live inputs so preset measurement polygons cannot be altered or written to the live database through the lane API.
- Preserved vehicle weights, paired scores, 70-second green, 3-second yellow, demand threshold, early-switch persistence, full-phase protection, live video evidence and live records.
- Regression evidence: nine new targeted checks failed before fixes; all 34 image/lab checks then passed. Complete backend suite: **168 passed** (dependency deprecation warnings remain). TypeScript and the frontend production build passed.
- Production browser verification used the actual supplied images and YOLO: first-click ambulance input, yellow then priority green, OFF while paused, input labels, old/new session stream events, five lab presets, lighting without signal changes, paused lab detection, fullscreen, 390-pixel mobile layout and controls with WebGL unavailable passed without page errors.
- Test databases, harnesses and screenshots remain ignored/local. Windows sandbox restrictions required approved local execution for OpenCV, generated build files and browser/server verification; no deployment or commit was performed.

## 2026-10-13 — Traffic Playground presentation

- Added detailed vehicles, urban buildings, landscaping, procedural road/paving textures, reflective materials and softer shadows.
- Added daylight, golden-hour and night presentation, smooth camera transitions and fullscreen.
- Preserved vehicle movement, queue spacing, crossing protection, scenario counts and signal logic.
- Verified TypeScript, production build, all five browser scenarios, early yellow switching, pause/speed, ambulance controls, mobile layout and WebGL fallback controls.

## 2026-10-02 — Image-based traffic demonstration

- Added real YOLO detections on the four supplied images, six EW/NS-swappable presets, an automatic tour, speed/pause, score records and signal history.
- Kept `IMAGE-DEMO` separate from live sources, live analytics and `SIMULATION-LAB`; labelled static images and explicit demo emergency light input.
- Preserved paired 70-second green phases, yellow clearance, early switching and full receiving-phase protection.
- Historical verification: 159 backend tests, TypeScript, production build and desktop/mobile browser checks passed at that stage. These counts are historical, not the current audit result.
