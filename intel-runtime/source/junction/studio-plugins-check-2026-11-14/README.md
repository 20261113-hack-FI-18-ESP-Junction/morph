# Studio plugins availability check

Observed on November 14, 2026. All times below are UTC.

The Studio Plugins page is responsive again. The initial Docker listing showed `physical-ai-studio-xpu` in `Paused` state. Docker events record a pause at **21:29:11.776** and an unpause at **22:19:15.687**, an interval of about 50 minutes. The reason and actor behind the original pause are unknown.

A separate active Intel reliability session performed `docker unpause physical-ai-studio-xpu` during this investigation. Its [saved recovery record](../morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/verification/intel-reliability-20261114/studio-availability.json) records its preliminary checks and action. This investigation and delegated `/root/inspect_studio` review performed no restart, unpause, hardware command, installation, calibration or configuration change. The container retained PID `100864` and its original start time `17:32:52 UTC`.

Actual checks after recovery passed:

- `http://localhost:7860/plugins`: HTTP 200.
- `/api/plugins`: HTTP 200, listing five plugins. SO101 Robot Plugin is installed at version `0.3.0`.
- `/api/health`: HTTP 200 and `healthy`, with `restart_required: false`.
- A fresh isolated Chromium context rendered the actual Plugins page, obtained its assets/API responses successfully and produced zero JavaScript page errors. The browser made no mutation requests and required no blocked requests.

The user can refresh the existing Plugins tab. Native Studio on port 3000 is a separate instance and also responded during the read-only checks.

Evidence: [complete report](report.json), [browser result](browser-result.json), [screenshot](plugins.png), and [bounded browser check](check-browser.mjs). An exploratory GET to `/api/runtime/sessions` returned 404; that unmatched route was not used to infer session state.

The parent `/root` is responsible for publishing this result and the attributed read-only `/root/inspect_studio` contribution to the shared Mac, then verifying the saved receipt. Notion bookkeeping remains separate from that delivery.

Shared Mac delivery of the parent and delegated review is **confirmed** by [receipt](../morph-intel-transfer/morph-context/context/sync-receipts/7e2675e9-77c4-46b4-896f-0b823e08b1e0.json), read back at `2026-11-14T22:22:42.632962+00:00`. The Notion annotation remains separately pending.
