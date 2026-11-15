# Intel reliability review — November 14, 2026

The owner requested a working dashboard and coordinated repairs using multiple agents. This review covers the current Intel application and the isolated Gemma evidence analyst. Robot diagnosis remains owner-led. All test records are saved simulation; no robot motion, calibration, serial command or camera capture was performed.

The user-facing analyst dashboard is **http://127.0.0.1:50139**, with its records API on **52197**. Existing Morph **3001/8000** remains available. Native Studio **3000** and container Studio **7860** are separate applications.

## Reproduced defects and repairs

- Malformed analyst report files could prevent the entire station API from starting. Invalid files now remain preserved, healthy evidence stays readable and explicit storage warnings block unsafe new analysis.
- Final-save failures, request-index crash windows and queued shutdown races could undermine job recovery. The worker now preserves request identity and reports uncertain persistence; concurrent duplicate requests create one invocation.
- Blank or malformed comparison metadata could wrongly establish matching conditions or raise an exception. Compatibility requires reviewed, nonempty metadata and controlled validation.
- Ordinary historical revisions were labelled as correction audits. Context now distinguishes record history and actual corrections.
- Switching analysis modes lost question drafts. Drafts now persist separately for the selected cycle or ordered session pair across navigation and reload.
- Malformed report data could blank the dashboard. Runtime response validation contains invalid analysis data while retaining canonical facts and healthy reports. Storage/read failures disable new requests until recovery.
- An analysis request could wait indefinitely for response headers or body. A bounded deadline preserves the exact pending request identity; recovery needs an explicit action and does not silently create another paid request.
- The shared Mac watcher assumed every note was JSON. Markdown documents now receive verified snapshots and review entries; canonical UUID handoffs retain strict identity and immutability checks.

Before-fix failures and browser observations are preserved in `backend-before.xml` and `analyst-review-2026-11-14T22-11-15-181Z/`. Subsequent versions and actual model replies are retained separately; a structurally accepted reply is not assumed semantically correct.

## Verified service recovery

Container Studio was paused at 21:29:11 UTC. Before resuming it, a read-only copy of its frozen database passed `quick_check` and showed zero projects, configured cameras, robots, calibrations and jobs. No WAL existed. The inspected logs showed ordinary health requests. The original pause actor and purpose remain unknown.

`docker unpause physical-ai-studio-xpu` resumed the same process without a restart or configuration change. At 22:19:28 UTC, both its root page and health endpoint returned HTTP 200; native Studio, main Morph and the analyst preview also returned 200. See [the exact evidence](studio-availability.json). Restoring web availability does not establish physical acceptance.

The repaired Mac watcher was replaced through its identity-checked helper as one process, PID 279692, at 22:14:03 UTC. Successful polls completed at 22:14:28, 22:19:16 and 22:24:27 UTC. Eighteen offline tests passed. [Watcher evidence](watcher/verification.json) records hashes, before/after tests and process identity. Incoming polling, local review and outgoing Mac/Notion delivery remain distinct.

## Validation and evidence boundaries

Frontend and proxy verification passed 59 tests; the analyst subset passed 33. The final text adjustment passed the analyst suite and type checking again. The production UI was built into this directory, preserving the colleague's existing deployment. Eight Chromium fault/reconnect/navigation checks and four broad dashboard navigation checks passed, including 390- and 1440-pixel layouts, with no page errors or accidental provider requests.

The canonical database contains 69 event rows with maximum event sequence 126. Byte-normalized exports and canonical ledger hashes are compared separately; sequence 126 is not a row count. Analysis reports live outside canonical records. The upgrade retained the user's existing database and all saved reports, with backups under `runs/deployed-01/`.

The v9 evaluation and its independent semantic review are preserved in [review-01](runs/review-01/semantic-review-v9.md). They exposed population/citation ambiguity and overly strong absence-only hypotheses despite four structural passes. One separate real browser submission correctly recovered its persisted rejection after navigation and reload, with one request and no retry. These findings motivated an additional bounded v10 revision; final v10 results must be recorded before claiming its acceptance.

ElevenLabs access, Scribe/microphone acceptance, matched physical comparison data, training, detector/dispatcher/adapter work and physical acceptance remain open. M20/M21/M23/M24 retain their original dependencies and acceptance criteria. The analyst cannot dispatch robot tasks, create reference labels or modify canonical outcomes.

## Ownership and shared reporting

Root owns integration, actual provider checks, deployment, watcher recovery and Studio availability. `/root/gemma_backend` owns analyst service/context/provider validation and semantic review. `/root/gemma_ui` owns analyst UI and browser verification. `/root/gemma_shared` publishes the attributed start, meaningful checkpoints and final handoff through the existing shared Mac connection and verifies saved notes.

Exact outgoing payloads and receipts are retained in the workspace's `context/outbox/` and `context/sync-receipts/`. Shared notes contain attributed results and selected evidence; publishing a note does not automatically transfer or mirror Intel source files. Notion status is tracked separately in `HachingJunction/NOTION_SYNC.md`.
