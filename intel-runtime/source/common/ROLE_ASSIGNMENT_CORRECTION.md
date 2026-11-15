# SO-101 role assignment correction

Owner correction recorded on **November 14, 2026 at 20:43 UTC**. This document accompanies the frozen source/evidence archives and supersedes their earlier reversed role assignment.

| Physical role | Controller serial | Preserved native Studio robot UUID |
| --- | --- | --- |
| Leader | `5B91030668` | `83327155-dc5a-491a-a265-4eaf5c812c1b` |
| Follower | `5AE6075066` | `2a1b5cc1-8e89-457e-8828-4d6d065f4ca6` |

The current connection map is [robot-connections.json](../../robot-connections.json). The owner said the previous serial assignments were reversed. The earlier role-based statement that the follower works while the owner investigates leader communication follows these corrected roles. This association is derived from the correction; it is not new physical verification.

The two persisted registrations in **native Studio on port 3000**, project **Morph SO-101 Workstation**, now match this table. GET read-back at **20:46:00 UTC** confirmed exactly two updates changing only `name` and `type`. Each serial retained its UUID, full payload, port hint, calibration value and timestamps. Both updates were preceded by empty-session and unchanged-baseline checks. Project, environment, camera and dataset metadata were preserved. [Studio evidence](verification/intel-studio-role-correction-20261114T204500Z/README.md).

Container Studio on port **7860** is a separate instance with no projects at the check. Morph on port **3001** has no persistent assignment for these serials. The user owns current arm diagnostics. Resolve current paths by stable serial identity and coordinate port ownership before future device use; this correction did not open either arm or any camera.

Current root, imported and active handoff guides were updated. Historical USB presence, numeric measurements, original captures and probe filenames remain associated with the serial actually observed. Dated reports, sent outbox payloads and sync receipts preserve their original bytes and are superseded only in their role interpretation. [Owner correction and previous-file backups](verification/role-correction-20261114T204324Z/correction.json), [guide propagation audit](verification/role-correction-20261114T204324Z/guide-propagation.json).

The following archives remain unchanged. Include this correction notice when forwarding or interpreting either M16 archive; do not treat the old operator-update mapping as current configuration.

| Archive | SHA-256 |
| --- | --- |
| Original `Morph-Intel-Handoff-20261114T191514Z.zip` | `19c62fa19259b0d25b7ef65daa8bb6358b2fdd1eeb1a66af7afce7d6c9512173` |
| `intel-m16-source-and-evidence-20261114.zip` | `1e304628d9aa832c493bac67f3c53a335cc2a6bb7b736d4352d756f99a8ad987` |
| `intel-m16-source-and-evidence-20261114-final.zip` | `e5bc07eb3bb8e19ae3976b3af75f40cb6ebec353de1e7a40131e8e46f3226c97` |

Shared delivery and Notion read-back are confirmed and tracked separately in [the synchronization ledger](HachingJunction/NOTION_SYNC.md). All four agents' work was saved/read back in checkpoint `49e052b3-7155-40db-9bc1-d2acc2de0939` at 20:52:18 UTC. Current Mac guides directly show the corrected roles at 20:52:59 UTC. The Mac Notion ledger confirms update `e907ed5a-48d6-4a6c-a910-b21ffdcd7bf8` with Notion read-back at 20:47:40 UTC; M08 remains In progress. The ledger was retrieved at 20:53:28 UTC. No hardware acceptance is inferred from this identity correction.
