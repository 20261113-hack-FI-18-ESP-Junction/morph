# Intel Linux software bring-up

This runbook starts the existing records backend and connected Morph dashboard. It does not connect the robot, start training, open a camera or call a model provider. Continue with [START_HERE.md](START_HERE.md) for the complete physical and adaptive workflow.

Commands below run in Bash on Intel Linux. Replace a path placeholder with the actual extracted folder. Keep `HachingJunction/` and `morph-station/` as siblings with those exact names. The frontend lockfile uses a local link to `../HachingJunction/station/web-client`.

## 1. Inspect and preserve the existing Intel installation

1. Extract into a new directory alongside current Intel work. Read the package's `AGENTS.md`, `START_HERE.md` and the Intel project's existing instructions before editing or installing anything.
2. Identify the current Studio environment, storage/settings, calibration, camera configuration, model weights, recordings and `ROBOT_GAMEPLAN.md` if present. Preserve those files and recorded failures. This ZIP does not contain their Intel-local versions.
3. Compare existing application sources with the package manifest. Reconcile changes; do not replace a whole working tree with this snapshot or move the active Studio data directory to the new package.
4. Inspect existing processes and ports. Reuse a known current service or select another port deliberately. Do not stop a robot/Studio process just to free a port.

From the extracted package root:

```bash
export MORPH_BUNDLE="$(pwd -P)"
python3 verify_bundle.py
python3 scripts/preflight.py --require-linux
```

The preflight reads runtime versions, the expected source layout and Linux listening-port metadata for ports 3000, 8000 and 7860. It reports override variable names without values. It does not make network requests, install software or access serial/camera devices. A missing runtime is a prerequisite to resolve, not a reason to reinstall Studio.

## 2. Select local runtimes

- Use the already installed **Python 3.12** reported by the Intel handoff, if it is still available. Keep the records application in its own virtual environment, separate from Studio and Anomalib. Earlier Intel reporting found that Python 3.12 validated the existing MCP certificate, while the host's Python 3.14 rejected it; retain TLS verification and use the working interpreter for that pairing.
- Use an existing **Node 24** toolchain when available, matching the Mac's tested TypeScript runtime. This runbook also permits Node **22.12 or newer** because it executes TypeScript tests through the locally installed `tsx`. The bundled Vite 8.3.8 and React plugin lock entries declare `^20.19.0 || >=22.12.0`; the selected bring-up path does not use Node 20. These are the recorded package requirements, not a claim about the latest available releases.
- Use npm with the bundled `package-lock.json`. Do not run Bun and npm installs interchangeably. Install native dependencies on Linux; do not copy Mac `node_modules`, virtual environments or caches.

Check the selected executables without displaying environment secrets:

```bash
python3.12 --version
node --version
npm --version
```

If a runtime is absent, inspect the Intel machine's already approved package manager/toolchain before installing it. Preserve system Python and working robotics environments. A registry/download failure must be reported with its actual error; do not substitute package versions or use `--force` to hide a dependency conflict.

## 3. Install and build the application

The following environment creation is for a fresh extracted folder where `.junction-setup/station-intel` does not exist. If that path already exists, inspect it, verify its Python version and reuse it only if it is the intended records environment. Do not recreate an unrelated environment in place.

```bash
cd "$MORPH_BUNDLE/HachingJunction"
python3.12 -m venv .junction-setup/station-intel
export MORPH_PYTHON="$MORPH_BUNDLE/HachingJunction/.junction-setup/station-intel/bin/python"
"$MORPH_PYTHON" -m pip install --disable-pip-version-check -r station/requirements.txt
"$MORPH_PYTHON" -m pip check
```

`MORPH_PYTHON` is the supported override in `station/run.sh`; no Mac activation script is needed. The requirements contain FastAPI/Pydantic/Uvicorn and software-test dependencies, not Studio, Torch or robot packages.

Install frontend tools first, then compile the shared client before compiling the frontend. `npm ci` can create the local package link before the client's generated `dist` exists. The compiler below is the frontend's installed dependency, so no global `tsc` is required.

```bash
cd "$MORPH_BUNDLE/morph-station"
npm ci --include=dev
./node_modules/.bin/tsc -p ../HachingJunction/station/web-client/tsconfig.json
npm run typecheck
npm run build
```

Do not use `npm run preview` as the connected product server: the records proxy belongs to `server.ts`. Use `npm start` below. During later source development, `npm run dev` runs the same proxy with Vite middleware.

## 4. Verify software before hardware integration

These checks use temporary records or fixture data. Save new Intel reports separately from the included Mac evidence.

```bash
mkdir -p "$MORPH_BUNDLE/verification"
cd "$MORPH_BUNDLE/HachingJunction"
PYTHONPATH=station "$MORPH_PYTHON" -m pytest station/tests --junitxml="$MORPH_BUNDLE/verification/intel-backend-tests.xml"
"$MORPH_BUNDLE/morph-station/node_modules/.bin/tsx" --test --test-reporter=junit --test-reporter-destination="$MORPH_BUNDLE/verification/intel-client-tests.xml" station/web-client/tests/*.test.ts
cd "$MORPH_BUNDLE/morph-station"
npm test
npm run test:prototype
cd "$MORPH_BUNDLE"
"$MORPH_PYTHON" scripts/check_client_http.py
```

`check_client_http.py` runs the existing canonical client HTTP check with the installed local `tsx`, replacing only its Mac-specific Node executable lookup and report destination. It intentionally creates an isolated temporary simulation database and an empty live bookkeeping session, starts and stops two owned local API processes, and tests restart/reconnection without touching `station/.data`, providers or hardware. Its result is saved to `verification/intel-client-http.json`.

Expected Mac baseline counts were 48 backend cases, 45 shared client/store cases, 17 projection/proxy cases and 11 retained prototype cases. The client HTTP report recorded 22 assertions across two server starts. Record the actual Intel results; a matching count alone is not proof of success. Test expectations may legitimately change after a documented implementation change.

## 5. Initialize and start the records API

Use a dedicated terminal for the new application. Set the absolute package path again in every new terminal; exported variables are not shared between terminals. If you intentionally reuse an existing live records database, inspect and back it up first, preserve its evidence directory/token and adapt these paths instead of seeding it.

For a fresh package's new records data, use:

```bash
export MORPH_BUNDLE="/absolute/path/to/Morph-Intel-Handoff-TIMESTAMP"
export MORPH_PYTHON="$MORPH_BUNDLE/HachingJunction/.junction-setup/station-intel/bin/python"
export MORPH_DATA_DIR="$MORPH_BUNDLE/HachingJunction/station/.data"
export MORPH_TOKEN_FILE="$MORPH_DATA_DIR/api-token"
unset MORPH_API_TOKEN MORPH_DB_PATH MORPH_EVIDENCE_DIR
cd "$MORPH_BUNDLE/HachingJunction"
bash station/run.sh init
bash station/run.sh serve --host 127.0.0.1 --port 8000
```

The `unset` affects this dedicated shell only and ensures a previously inherited credential/database override does not silently select another service's data. `init` preserves an existing token and prints its path, never the token. `serve` does not initialize, seed, connect hardware or move the robot.

If port 8000 is occupied, select an unused port using `--port`, then use the same origin in the frontend and `--url` in CLI requests. Do not expose the API on all network interfaces for this first bring-up.

## 6. Start the connected dashboard

In a second dedicated terminal:

```bash
export MORPH_BUNDLE="/absolute/path/to/Morph-Intel-Handoff-TIMESTAMP"
export MORPH_STATION_ORIGIN=http://127.0.0.1:8000
export MORPH_TOKEN_FILE="$MORPH_BUNDLE/HachingJunction/station/.data/api-token"
unset MORPH_API_TOKEN
export PORT=3000
cd "$MORPH_BUNDLE/morph-station"
npm start
```

Open `http://127.0.0.1:3000` on Intel. A fresh database should show no eligible Live data. All three views should share the selected source/session. The proxy reads the token server-side; do not paste it into the browser, source, a URL or a `VITE_` environment variable. Missing authentication, backend disconnection and unavailable hardware should be visible as such.

If port 3000 is occupied, select another `PORT` and open that address. The included dashboard smoke wrapper accepts the chosen port. Both servers bind to loopback. For Mac viewing, use an existing verified SSH connection and explicit local forwarding; choose free ports on both ends. Forwarding the UI alone is sufficient because its server-side proxy accesses the Intel-local API. This package does not establish SSH accounts or a tunnel.

## 7. Optional explicit simulation acceptance

In a third terminal, set the same `MORPH_BUNDLE`, `MORPH_PYTHON`, `MORPH_DATA_DIR` and `MORPH_TOKEN_FILE` as the API terminal, and clear the same unrelated overrides. Seed only the new bring-up database deliberately:

```bash
cd "$MORPH_BUNDLE/HachingJunction"
bash station/run.sh seed-demo --prefix intel-bringup
bash station/run.sh request /api/v1/sessions
bash station/run.sh request '/api/v1/metrics?includeSimulation=true'
cd "$MORPH_BUNDLE"
"$MORPH_PYTHON" scripts/check_dashboard_http.py --port 3000
```

For a nondefault API port, add `--url http://127.0.0.1:CHOSEN_PORT` to `request`. For a nondefault dashboard port, pass it to `check_dashboard_http.py`. Reusing the same simulation prefix is idempotent. Opening the UI never seeds it. In the UI, deliberately select Simulation and the `intel-bringup:session` session; Live remains separate.

For this fixture, the expected session values are 2/4 confirmed correct finished cycles, 3/5 confirmed successful finished attempts, one retry/recovered cycle and one additional inspection. The fixture image is a 1×1 synthetic PNG, not a real camera capture. The proxy check reads existing data and deliberately sends blocked POST probes; it must leave the persisted event sequence unchanged. It saves `verification/intel-dashboard-http.json`, preserving the original Mac report. Run it on the bring-up simulation service, before future motion routes are implemented.

Review desktop and narrow-screen views, the retry trace, exports, empty Live state, stale/disconnected state and reconnection. Capture actual screenshots and test results. Never describe this as a verified physical cycle.

## 8. Continue the Intel integration

Follow the task dependencies and acceptance gates in [START_HERE.md](START_HERE.md). Locate and reuse the actual Studio installation before running setup scripts. `HachingJunction/setup/run-studio.sh` assumes Studio and storage under that checkout's `.junction-setup`; it is not a discovery launcher for another installation. `setup/setup-intel.sh` performs package synchronization and is only for a missing or deliberately repaired isolated profile after the existing setup is inspected. Its `--preflight` is the inventory-only mode.

The prepared target checks can inspect the host without opening devices:

```bash
cd "$MORPH_BUNDLE/HachingJunction"
python3.12 setup/check-intel.py --require-host --output "$MORPH_BUNDLE/verification/intel-host.json"
```

Synthetic `--runtime` checks must use the actual selected Studio/Anomalib interpreter. Their successful CPU/GPU/NPU operation does not verify that a particular learned policy or anomaly detector is supported on that device.

The next physical work is an actual local dispatcher and Studio/controller/camera adapters that persist real events through the canonical API. The current dashboard's disabled movement, voice, camera, correction and replay controls are unfinished integration boundaries; do not turn them into fake successes to make the UI appear complete. Keep the existing provider requirements and physical acceptance definitions.

After each meaningful step, update the existing Notion task and publish a verified shared-Mac handoff as described in `HachingJunction/context/INTEL_CODEX.md`. If that connection is unavailable, retain the exact pending note/update and continue independent work. At session end, stop only processes started and owned by this session; record any intentionally retained service and its purpose.
