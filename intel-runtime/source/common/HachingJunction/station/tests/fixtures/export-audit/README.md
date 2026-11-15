# Portable export-audit test fixtures

These three files are exact copies of the manifest-verified simulation acceptance exports delivered in `Morph-Mac-Offline-Evidence-20261114-01a1dbfa.zip`. They make the audit tests independent of the original Mac workspace and the external Intel review folder.

Source archive SHA-256: `09fcdd95aa561e798b59e7cc4e36e528773a2920c3d22c1ace9f64a95f4e85e3`.

| Relative path | Bytes | SHA-256 |
| --- | ---: | --- |
| `context/verification/m16-closure-1cf186e8-ce90-4cbb-a953-6611e0bdcb98/browser-replay-export.json` | 42490 | `c2f524137d2ede92aa9a6451103b9133260e61b455ed8f207fd1827a3edb4175` |
| `context/verification/m16-closure-1cf186e8-ce90-4cbb-a953-6611e0bdcb98/recovered-session-export.json` | 42490 | `b9b1ebb96928b1d2442491f6d08f7f5b36669de130d57d3b81d7f7e78971d0d8` |
| `station/verification/sample-export.json` | 97061 | `a05702877fe967562fd1439d836fdae9aec95610c6ba031c6919af1174b8067d` |

The adjacent `MANIFEST.json` retains the original source paths, source-manifest hash and copy time. Original identifiers, timestamps, records, revisions, corrections, metrics and raw bytes are preserved. In particular, the two M16 exports differ in their original top-level `exportedAt`; no synthetic replacement or normalization was performed.

These are saved simulation fixtures. They do not establish physical execution, original-media verification, a new browser replay or current provider behavior. Tests load copies in memory for negative mutations; the fixture files remain unchanged.

An explicit `MORPH_AUDIT_FIXTURE_ROOT` still overrides this directory using the same relative layout. The default is resolved from `test_export_audit.py`, so a normal test run needs no external directory or environment variable.
