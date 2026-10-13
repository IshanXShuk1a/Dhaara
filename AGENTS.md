# Project working rules

These rules apply throughout this repository. Read `README.md`, `architecture.md` and the latest entries in `changes.md` before changing behaviour.

## Scope and implementation

- Reproduce reported bugs and identify their cause before editing. Make the smallest complete fix; preserve working behaviour and unrelated local changes.
- Keep signal decisions in the backend. Preserve paired EW/NS outputs, yellow clearance, fairness and full receiving phases unless the user explicitly changes those requirements.
- Keep live video, `IMAGE-DEMO` and `SIMULATION-LAB` sources, controllers, clocks and records isolated. Educational controls must not modify live signals or persisted live analytics.
- Never invent measured detections, counts, flashing-light evidence or physical calibration. Label scripted traffic, still images and explicit demo inputs accurately.
- Use existing configuration and abstractions. Avoid new dependencies, frameworks or large refactors for a local bug.
- Validate API inputs before changing state. Keep frontend state consistent with server responses, reconnects and source changes.

## Documentation and change records

- Maintain `README.md` for setup, usage and supported behaviour.
- Maintain `architecture.md` as the current system design: components, data flow, interfaces, state ownership, timing, persistence and limitations.
- Maintain `changes.md` for each meaningful change: date, problem, fix, affected behaviour and actual validation. Record unfinished checks honestly; do not claim an unrun check passed.
- Update relevant documentation in the same task as code changes. Keep documentation consistent with the implementation; distinguish current design from historical changes.
- Do not record secrets, access tokens, private user data or generated runtime databases in documentation or source control.

## Verification and delivery

- Add focused regression coverage for behaviour fixes. Use isolated test databases and fixtures; do not test against the user's live data.
- From `backend/`, use `..\.venv\Scripts\python.exe -m pytest app/tests -q --basetemp=.pytest_cache/test_tmp` for backend checks. Run narrower tests while implementing and the relevant full suite before delivery.
- If Windows denies access to `.pytest_cache`, use `--basetemp=.cache/test_tmp -o cache_dir=.cache/pytest_cache` within this repository. Use the approved execution environment if sandbox restrictions prevent OpenCV or local server verification.
- From `frontend/`, run `npx tsc --noEmit --incremental false` and `npm run build` for frontend changes. Verify affected browser flows, including responsive layout and error states when relevant.
- For signal changes, cover paired outputs, yellow, cancellation, timing and emergency conditions. Preserve simulation controls when WebGL is unavailable.
- Keep temporary scripts, screenshots, databases and model weights out of tracked source. Stop temporary servers when verification ends.
- Report concrete changes, checks and remaining limitations concisely. Do not commit, publish or deploy unless requested.
