# Final code publication review

Reviewed 2026-11-15T08:04:29.407192+00:00. Groups 04–07 are ready for exact-path staging. [The inventory](publication-ready-groups-4-7-20261115T080429Z.json) records all 32 exact source paths, baseline and final SHA-256 values, dependencies and review limits. The original comparison baseline is `f8759fd7ab5e64ad3f77a27ea1d190cd4b980500`; observed HEAD is `11ee3d51cade623525c15b9de152b599ada2da33`.

| Group | Files | Suggested subject |
| --- | ---: | --- |
| 04-webrtc-viewer-gateway | 11 | Add isolated WebRTC monitoring with bounded media sessions |
| 05-records-history-selection | 4 | Keep session selection, saved history and exports coherent |
| 06-evidence-dashboard-ui | 8 | Refine inspection and history views around recorded evidence |
| 07-local-launchers | 9 | Add isolated station and synthetic demo launchers with readiness checks |

No private runtime files, actual credentials or missing dependency declarations were found. All 68 files in the already committed dependency groups match their reviewed hashes. The new missing-selection-field checker regression was reproduced as an `invalid-contract` result without network access after the root fix. TCP restart retains active-listener refusal and now permits immediate restart after an owned listener closes.

Root owns final test output and the group 08 documentation/evidence freeze. New station-tools evidence is included in that pending scope. Preserve historical manifests and intermediate results; this review supersedes earlier pending code hashes without rewriting their snapshots. No source, service or Git mutations were made by this review.
