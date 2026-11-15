# Station data over the existing Mac MCP

Prepared November 15, 2026 for the [three-host architecture](../context/THREE_HOST_ARCHITECTURE.md). The Mac hosts the existing TLS MCP endpoint. Intel runs a foreground worker against its fixed local records API. Klemen's dashboard uses a server-side MCP adapter.

## Protocol

1. Reads use `enqueue_station_read(station_id, request_id, path, query)`.
2. Explicit writes use `enqueue_station_request(station_id, request_id, method, path, query, body, intent)`. `body` is the exact JSON text as a string, not a parsed object; omit it for GET. `query` maps keys to strings, except `sessionIds` accepts one or two strings and preserves repeated URL parameters.
3. Legacy workers use `claim_station_reads` and can claim GET requests only. A worker started with `--allow-record-writes` uses `claim_station_requests(..., supports_writes=true)`.
4. A worker performs one station request, then returns exact response bytes through `submit_station_read_chunk`. The historical tool name is retained for compatibility with both methods.
5. The dashboard polls `read_station_response`, verifies SHA-256 and preserves Intel's HTTP status and structured response.

| Method | Route | Required intent |
| --- | --- | --- |
| GET | Records, schema, snapshot, sessions, metrics, cycles, camera descriptors, finite events, exports and evidence | None |
| GET | `/api/v1/analysis/context`, `/api/v1/analysis/reports`, `/api/v1/analysis/reports/{id}` | None |
| POST | `/api/v1/cycles/{id}/review` | `record-review` |
| POST | `/api/v1/analysis/reports` | `evidence-analysis` |

Reviews are audited record corrections. Analysis can call Intel's configured evidence provider after an explicit user action. Neither route grants robot control. Commands, mission/session lifecycle writes, voice credentials, camera capture and arbitrary URLs are excluded.

Both server and worker independently validate the route and write envelope. JSON bodies are limited to 65,536 UTF-8 bytes, must be objects without duplicate keys or nonfinite numbers, and require stable application IDs (`id` plus `eventId` for review; `requestId` for analysis). Intel retains full record revision, domain, evidence and provider validation.

## Delivery and failure behavior

A stable request UUID identifies immutable method, path, query, exact body hash and intent. Duplicate submissions return the original state; changed content conflicts. Claims are issued once. Requests expire after 30 seconds and are never automatically replayed, including after restart. The migration preserves existing GET rows. Expiry removes request/response payloads while retaining identity hashes.

Station HTTP has a 15-second timeout and refuses redirects. The dashboard adapter polls at most 35 seconds; its analysis client allows 40 seconds for the envelope. Responses are bounded to 4 MiB and split into base64 chunks of at most 60,000 characters. Oversized data returns an explicit error. Continuous video and large artifacts require a separate transport.

There is no automatic POST retry. A lost or invalid station response after sending a POST is reported as `station_write_outcome_unknown`; inspect authoritative records before deciding whether to retry. If only an MCP response-chunk acknowledgment is lost, the worker may resend the identical chunk once without repeating the station request. A claim expiring after execution likewise does not prove the operation failed.

The relay cache is under `.junction-setup/context-share/station-relay.sqlite3`. It contains temporary transport data, never canonical station records. Source transfer is [a separate hash-checked workflow](../context/coordination/three-host-20261115/README.md).

## Mac adoption

Install with `python3.12 context_mcp/bootstrap.py` from this package. Use the existing approved address, token and TLS files. After reviewing the source and coordinating replacement of the old process, start from this package with explicit existing canonical root:

```bash
.junction-setup/context-mcp/bin/python context_mcp/server.py \
  --root /ABSOLUTE/EXISTING/CANONICAL/WORKSPACE \
  --transport http --host YOUR_MAC_ADDRESS --port 8765 \
  --token-file /ABSOLUTE/PRIVATE/token \
  --tls-cert /ABSOLUTE/PRIVATE/server-cert.pem \
  --tls-key /ABSOLUTE/PRIVATE/server-key.pem \
  --enable-station-relay
```

These are adoption instructions, not a claim of a completed restart. The published root's `bash context_mcp/run.sh` serves its minimal public context; it does not merge or restore the canonical Mac history. Preserve pairing and certificate validation.

## Intel worker

Use the existing owner-only private pairing directory (`connection.json` and `morph-ca.pem`) and actual station token. From this package:

```bash
python3.12 context_mcp/station_worker.py \
  --pairing-folder /ABSOLUTE/PRIVATE/morph-intel-pairing \
  --station-url http://127.0.0.1:8000 \
  --token-file /ABSOLUTE/STATION/TOKEN \
  --station-id intel-main --once
```

Use `--serve` for foreground polling. Add `--allow-record-writes` only when intentionally enabling review and evidence analysis. The default remains read-only. `MORPH_PAIRING_FOLDER`, `MORPH_STATION_URL` and `MORPH_TOKEN_FILE` provide path/origin defaults; server environment `MORPH_API_TOKEN` takes precedence over the token file. There is no token CLI argument.

One claim per round is the default; limits 1–8 are accepted. Polling defaults to two seconds. No daemon, Station API, simulation, microphone or robot process is launched. With write opt-in, a claimed analysis request may reach the already configured Intel provider.

The dashboard and worker must share the same station ID (default `intel-main`). The Klemen package's `MORPH_CONTEXT_PAIRING_DIR` remains server-side. Preserve source-mode labels and configure the authoritative station, never a simulator labeled as hardware.

## Verification boundary

[Saved software checks](VERIFICATION.md) use temporary stores, fake station/provider transports and authenticated in-process MCP. They cover legacy compatibility, two-session selection, restricted writes, duplicate/conflicting IDs, expiry, migration, exact-byte round trips and lost acknowledgments. Real deployment and a three-host run remain unverified by this publication.

