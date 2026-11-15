# Received Intel record contract — reference source

This folder contains the **verified current Intel source transfer** for Jose's takeover. It is separate from the runnable Mac lab in `../station/`. Its files were copied without modification after all transfer and file hashes passed. The initial copy/comparison used only source text and AST inspection. A subsequent independent audit ran the received tests in a guarded, isolated process; the files were not installed into or merged with the Mac lab.

| Provenance | Value |
| --- | --- |
| Request | `00e34e99-cfc8-47bf-ab5d-1d029242f841` |
| Transfer | `8dfe841b-f157-469d-84fe-7586cdcd583f` |
| Manifest note | `b5c45c9c-58ca-521e-a26e-8bd8e2cc0179` |
| Frozen on Intel | November 15, 2026, **03:29:40.570489 CET** |
| Collected on Mac | November 15, 2026, **03:33:51.290670 CET** |
| Static comparison | November 15, 2026, **03:34:56.775389 CET** |
| Source | **17 files, 230,799 bytes** |
| Transfer | **21 chunks, 246,146 bundle bytes** |
| Bundle SHA-256 | `f79c9426e361721aa63aa61038a93cbe1799d63e4a93501858a68112ea553e1b` |

Times are Europe/Ljubljana, UTC+01:00. [manifest.json](manifest.json) and [report.json](report.json) retain the original UTC timestamps, complete paths and individual hashes. [STATIC_COMPARISON.json](STATIC_COMPARISON.json) records the independent static checks and import graph.

Start reading [models.py](source/station/morph_station/models.py), [api.py](source/station/morph_station/api.py), [store.py](source/station/morph_station/store.py) and [schema.sql](source/station/morph_station/schema.sql), then [CONTRACT_COMPARISON.md](CONTRACT_COMPARISON.md). The current API imports the four `analysis*.py` modules, so they are included as its dependency closure. Their presence is not a request to move Gemma product ownership or analyst UI work to Jose.

All relative imports across the eleven received runtime Python files resolve to received files, and the named imported symbols exist in those files under static AST inspection. External imports use the included pinned requirements and standard-library modules, including POSIX `fcntl`. The supplied `test_reviews.py` imports the included `test_store.py`. Those static checks establish completeness. A separate [isolated source audit](verification/REVIEW.md) at **03:35:47.871883 CET** then passed **56 tests**, with **zero provider attempts and zero outbound socket attempts**. It confirmed the three command/voice 503 stubs, null goal state, empty actions and no created sessions/events. [Current-source OpenAPI](verification/current-source-openapi.json), [record schema](verification/current-source-record-schema.json) and [empty snapshot](verification/empty-source-snapshot.json) were generated from the received source in temporary local data. They are not captures from Intel ports 8000 or 52197. The audit artifacts are copied unchanged; its runner records canonical-workspace paths and needs those paths adjusted before standalone reuse.

**Keep using `../run.sh` to run the Mac simulation/control lab.** Do not add this folder to that launcher's `PYTHONPATH` or copy its `api.py`, models, store or schema over the lab. The two trees document distinct source snapshots. The current Intel API includes analyst registration and review behavior absent from the Mac foundation, and Intel reports that running main API `8000` predates those analyst routes. Isolated Intel API `52197` reportedly matches the current source's analyst route presence. Running-service OpenAPI bytes are not part of this source transfer.

The received source still has no mission/control dispatcher, online provider/voice modules or physical adapter. Its `/api/v1/commands` and voice endpoints return unavailable responses. An actual mission service must be agreed and implemented on Intel before Jose can send learned-task requests through the other team's NVIDIA tunnel. Source receipt is complete for this focused record-contract delivery; that implementation gap remains.
