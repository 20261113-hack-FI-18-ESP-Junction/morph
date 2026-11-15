# StationClient verification and source history

The reconciled publication was checked on November 15, 2026: **47 client/store tests passed**, with no failures or skips, and the TypeScript build passed. See [the current JUnit result](../verification/reconciled-client-tests.xml) and [package verification](../VERIFICATION.md). The tests use the received synthetic fixtures and do not contact Intel, providers or physical hardware.

Coverage includes coherent snapshot/event watermarks, duplicate/out-of-order events, reconnection, aborts, timeout handling, source/session changes, preserved unavailable fields, metric denominators, authenticated evidence, review identifiers and exact payload retention. Explicit retry preserves the original application request; automatic mutation retry is absent.

## Historical source evidence

The received source document records Mac M15 verification on November 14, 2026: 45 client/store tests, 22 HTTP checks, 17 projection/proxy tests, 12 production-proxy checks and desktop/mobile browser checks. That session used an isolated simulated API plus an empty live session and retained its original event count. Its original evidence paths begin `station/web-client/verification/` in the canonical workspace. Those artifacts and backend smoke layout are not bundled here.

The same source document records an Intel M16 continuation at **2026-11-14T19:47:37.689927+00:00**, with 47 client/store tests, 24 frontend/proxy tests and eight browser/API scenario groups. Original Intel evidence paths are `verification/intel-m16-ui/client-tests.xml`, `verification/intel-m16-ui/frontend-tests.xml` and `verification/intel-m16-ui/README.md`. These are attributed historical source claims; this package does not independently rerun those browser scenarios or include their original reports.

The former M15 statement that review/replay was still future work is superseded by the received M16 source. The current publication preserves review/replay plus the newer analyst UI and adds the Mac MCP transport boundary. It has no live camera, motion or provider verification claim. A successful records connection is not a connected robot.

[README.md](README.md) contains the portable checks. The original document hash remains in [source reconciliation](../SOURCE_RECONCILIATION.json), so historical evidence and current packaging edits remain distinguishable.
