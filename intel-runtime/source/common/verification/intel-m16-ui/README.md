# Intel M16 UI and client verification

Updated **2026-11-14T19:47:37.689927+00:00**. Author: `/root/reconcile`. Scope: software and explicitly labeled simulation.

The existing Morph UI now supports independent reference labeling, atomic audited review/late confirmation, complete selected-session filters and pagination, and read-only historical event replay. The canonical backend remains authoritative. Stable IDs, author/time/reason, before/after values, physical confirmation prerequisites and expected revisions are validated by its new transaction.

## Verified checks

| Check | Result | Evidence |
| --- | --- | --- |
| Shared client/store regression | 47 passed; zero failures/errors | [JUnit](client-tests.xml) |
| Projection/history/proxy and pending-review checks | 24 passed; zero failures/errors | [JUnit](frontend-tests.xml) |
| Canonical client compilation | Passed | `morph-station/node_modules/.bin/tsc -p HachingJunction/station/web-client/tsconfig.json` |
| Frontend typecheck | Passed after the final UI edits | `npm --prefix morph-station run typecheck` |
| Real local browser/API workflow | Passed: 8 scenario groups, 144 browser requests, zero JavaScript errors | [Final browser report](../intel-m16-browser/runs/acceptance-05/browser-results.json) |

The proxy exposes one dedicated review POST with explicit JSON intent, a 64-KiB request bound and existing local Host/Origin protection. Provider/control/general ingestion routes remain unavailable. An uncertain submission retains its exact payload in browser-tab session storage and offers an identical explicit retry. A conflict refresh obtains fresh validated cycle detail before replacing the editing base. An independent code review found and fixed the earlier stale-props refresh risk before acceptance.

History combines outcome/retry, cycle/object ID, label status, model, error and inclusive UTC date filters. All pages derive from the complete coherent session export. Playback displays original event payloads/revisions and retains saved-session totals; it never recomputes historical outcomes or writes records. JSON exports the frozen replay; CSV remains available from the ordinary record source.

The test runner initially encountered an incorrect relative executable path and a TypeScript union for test headers; both were corrected. Passing JUnit artifacts are the final results, rather than claims inferred from an attempted command. The existing Intel/Studio environments, old source tree, calibration and captures were preserved. No camera, robot, training or provider integration is certified by these checks.

## Independent browser findings during acceptance

The dashboard agent exercised a real local API/proxy/browser workflow on a separate M16 fixture. It verified a committed late confirmation and recovery from a deliberately lost response by retrying the exact review payload; the isolated retry fixture retained 1/1 correct cycle and 1/2 successful attempts. That run then found a keyboard defect: after saving disabled the focused submit button, focus could move to the document body and Escape no longer reached the drawer listener. The drawer now listens for keyboard events at document scope while open, removes the listener on close, and returns outside Tab focus to the modal. TypeScript validation passed after the fix. The final browser rerun passed all eight scenario groups; the keyboard fix is included in that acceptance.

A separate code review found and removed the stale-props conflict-refresh risk: refresh now returns validated current `CycleDetail`, which directly becomes the editing base. Draft choices remain available for review, and pending request IDs are cleared only after the fresh read succeeds.


## Final software acceptance — 2026-11-14T19:54:10.556266+00:00

Independent acceptance used Chromium **159.0.8154.6** against a dedicated simulation-only API and the actual dashboard proxy. [The final browser result](../intel-m16-browser/runs/acceptance-05/browser-results.json) passed **8 scenario groups** with **144 browser requests** and **zero JavaScript errors**:

- A late operator confirmation atomically updated the original finished cycle and second attempt, preserving the failed first attempt and all audit values.
- A deliberately lost HTTP response after commit retained the exact tab-local payload. The identical browser retry returned duplicate without adding any records or events.
- Replay stepped, played, paused and sought original events, kept saved totals fixed, exported the frozen JSON trace and exposed no review form. Its event sequence was unchanged.
- Twelve-cycle history paginated **5 / 5 / 2**, combined independent-label/error/model/inclusive-UTC-date filters, reset pagination after filtering and fit a **390 px** viewport.
- An independent label was added to the original in-progress cycle without adding an attempt or changing its outcome.
- A concurrent change produced a visible **HTTP 409** with no partial mutation. One explicit refresh loaded current revisions, preserved the draft and allowed successful resubmission.
- An unreadable stored draft was blocked until explicitly cleared, without sending it.
- Only the explicit JSON review route accepted POST. Missing intent, foreign origin, generic ingestion, commands and voice routes were rejected; browser requests contained no Authorization header.

The [complete recovered-session export](../intel-m16-browser/runs/acceptance-05/recovered-session-export.json) has schema version 1, **1 cycle**, **2 attempts**, **1 failed attempt**, **1 successful attempt**, **1 retry**, **1 recovered cycle**, **0 first-attempt successes**, **5 audit corrections** and **19 saved events**. Its end-to-end ratio is **1 / 1** and physical-execution ratio **1 / 2**. These are deterministic simulation measurements, not physical robot reliability. The browser suite's overall event sequence changed **68 → 83** only through its intentional review/label/concurrent-edit checks; read-only replay, rejected requests and identical retries added none.

Inspect [the saved late confirmation](../intel-m16-browser/runs/acceptance-05/saved-late-confirmation.png), [desktop replay](../intel-m16-browser/runs/acceptance-05/replay-desktop.png), [mobile history filters](../intel-m16-browser/runs/acceptance-05/history-filters-mobile.png), [revision conflict](../intel-m16-browser/runs/acceptance-05/revision-conflict.png), and [frozen JSON export](../intel-m16-browser/runs/acceptance-05/browser-replay-export.json). Earlier failed acceptance runs remain preserved. Run 02 exposed the Escape defect; runs 03 and 04 required harness expectation corrections (missing intent correctly returns 415, and the later label cycle must appear in the expected record set). Run 05 is the passing final result.

The dedicated acceptance services were stopped; [cleanup evidence](../intel-m16-browser/runs/acceptance-05/cleanup.json) is retained. Test runtime tokens and private data directories are excluded from the transferable source/evidence manifest. [Source hashes](source-manifest.json) record the reviewed implementation and documentation. Root status and shared-context/Notion receipts track service upgrade and task synchronization separately. This completes the tested M16 software behavior; later hardware/provider integration remains outside this acceptance.
