# Reviewed source transfer through MCP

The source sender and receiver are unchanged from the reviewed Mac helpers used on November 15, 2026. They use Python's standard library and immutable notes with stable UUIDs, source paths and SHA-256 hashes. They do not execute, install or adopt received code.

An MCP request does not wake Intel's agent. An active team member or agent must read it and run the sender. No unattended synchronizer is installed.

## Sender on Intel

Read the request and helper through the existing MCP, following every page and checking the reported hash. Prepare an explicit reviewed set of source paths in a new frozen outbox:

```bash
python3.12 source_response.py prepare \
  --root /ABSOLUTE/CURRENT/SOURCE \
  --include station/morph_station \
  --request-id REQUEST_UUID --transfer-id NEW_TRANSFER_UUID \
  --output /ABSOLUTE/NEW/OUTBOX
python3.12 source_response.py verify --output /ABSOLUTE/NEW/OUTBOX
python3.12 source_response.py send --output /ABSOLUTE/NEW/OUTBOX \
  --pairing /ABSOLUTE/EXISTING/PRIVATE/PAIRING
```

Use repeated `--include` values and separate transfers for different source roots. Preserve the request ID, transfer ID and outbox on retries. Send publishes manifest/chunk notes, reads them back and rejects redacted or changed content.

Hidden files, credentials, dependency caches, runtime data, symbolic links and unsupported binary files are excluded. Tests containing synthetic authentication strings may be rejected by conservative checks. Record omissions honestly; do not rewrite or encode rejected files to bypass checks. Any separate reviewed artifact transfer needs its own explicit scope and provenance.

## Collector on Mac

From this communication package, after all notes are present in the canonical Mac context:

```bash
python3.12 context/coordination/three-host-20261115/collect_source_response.py \
  --notes /ABSOLUTE/CANONICAL/context/notes \
  --manifest-note-id MANIFEST_UUID --request-id REQUEST_UUID \
  --output /ABSOLUTE/NEW/INCOMING
```

Always pass the actual request ID: the preserved helper's historical default is the earlier Jose request. The output must not already exist. The collector validates request/transfer identity, deterministic note IDs, chunk/bundle/file sizes and hashes, source paths and the 20 MB limit before writing an isolated source tree. It rejects missing, changed, secret, duplicate, traversing, symlinked or unsupported inputs.

Successful transfer proves byte receipt. Independent code review, application tests, adoption, current service inspection and physical verification are separate steps. The eleven-group remaining-source receipt reconciled 110 transferred files and 124 declared reuses; an additional exact CSV reuse brought the current inventory to 235 of 240 files. The reviewed supplement supplies two exact artifacts, bringing original receipt to 237 of 240 files. Three tests remain redacted review copies rather than original-source receipts.

