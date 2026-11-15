# Disposable local dashboard demonstration

For the complete records and synthetic video stack, run `npm run demo:all` from `dashboard/`. Its supervisor starts and checks the four owned services together, selects unused internal loopback ports, and cleans them up on Ctrl+C. Use `npm run demo:all -- --port 3102` when the default port is occupied. [Working-system guide](../WORKING_SYSTEM.md) also covers the separate actual Intel connection and GET-only checker. The simpler `npm run demo` command below remains available for records-only work or an independently managed video publisher.

This explicit development command runs the actual modified Intel Station backend and the dashboard's normal same-origin proxy against a newly created temporary SQLite database. It does not connect to Intel, the live Mac MCP, a provider, or hardware. The ordinary `dev` and `start` commands retain their MCP transport.

From the `dashboard` directory, after installing its dependencies and building the sibling `station-client` package:

```bash
npm run demo
```

The default URL is `http://127.0.0.1:3101`. Select **Simulation** in the dashboard. Live mode correctly has no records. To use another available loopback port:

```bash
npm run demo -- --port 3102
```

The launcher uses the project's prepared Python runtime when it finds one in a parent workspace; otherwise it uses the Python that launched it. An explicit Python override is supported:

```bash
MORPH_DEMO_PYTHON=/absolute/path/to/python npm run demo
```

That interpreter needs the Intel Station package's existing dependencies. No packages are installed automatically. The dashboard's installed `tsx`, Vite, and proxy implementation are used directly.

The launcher chooses a separate free backend port, generates a mode-0600 token in an owned temporary directory, and passes its file path only to the local server. It builds a minimal child environment and does not load project `.env` files, provider configuration, pairing material, or an existing database. The Vite environment and cache directories also point to the disposable directory. Both the demonstration records proxy and backend reject every records API method other than GET. The backend receives an explicitly disabled model-provider implementation. The separate optional media gateway supports only its own receive-only video negotiation and session cleanup; it never forwards these requests to the records backend.

Existing deterministic simulation cases are seeded through the canonical store. The empty open fixture is closed as **unverified**, preserving its record. One additional, latest recovered-success fixture contains two attempts (one failed), a generated 640 × 480 brick diagram, frame-linked inspection/model/decision records, execution acknowledgment and finish times, and a synthetic operator confirmation. Its provider and policy IDs explicitly identify simulation. The diagram is not a photograph; no recorded fixture result establishes physical performance.

Keep that command running during browser review. **Ctrl+C** stops only its owned child process groups and removes the temporary database, images, logs and token. An occupied dashboard port is rejected; the launcher does not stop or replace another service.

In a second terminal, run the cross-layer read check against the active demo:

```bash
npm run demo:check
# Or the alternate port:
npm run demo:check -- 3102
```

The check uses the real Station TypeScript client and application wrapper. It validates the new bounded response and saved image, confirms simulation is absent in live mode, verifies ordinary refresh performs no session export, opens history through an explicit full export, and confirms frozen replay leaves event sequence and metrics unchanged. It makes only GET requests. Browser screenshots from this harness are software/simulation evidence, never proof of a live Intel-to-Mac deployment or physical robot cycle.

Implementation: [Python launcher](tools/run_local_demo.py), [demonstration server](dashboard/tools/demoServer.ts), [cross-layer check](dashboard/tools/checkLocalDemo.ts). The backend contract is documented in [INTEL_DASHBOARD_API.md](../intel-runtime/source/common/HachingJunction/station/INTEL_DASHBOARD_API.md).

## Optional simulation video

The default demo leaves video unconfigured. To add the separately started synthetic MediaMTX/bridge stack, follow [LIVE_VIDEO.md](LIVE_VIDEO.md) and pass its explicit private gateway file:

```bash
npm run demo -- --media-config /absolute/private/path/dashboard-media.json
```

The demo server requires `sourceMode: simulation`, loopback WHEP/status endpoints and no external ICE servers. It rejects a live or remote media configuration. The launcher passes this file path only to its dashboard child; the backend still receives its minimal isolated environment. The file itself must belong to the current user and have mode 0600. `npm run demo` never imports an ambient `MORPH_MEDIA_CONFIG_FILE`.

Stopping the demo closes its known media viewer sessions and lets bounded negotiations finish cleanup before the owned child process deadline. It does not stop a separately started publisher or MediaMTX server. Their launcher/operator owns them.
