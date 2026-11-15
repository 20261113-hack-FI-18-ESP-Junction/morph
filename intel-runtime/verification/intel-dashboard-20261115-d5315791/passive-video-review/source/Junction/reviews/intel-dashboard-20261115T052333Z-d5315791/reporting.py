"""Publish immutable task metadata notes through the existing verified MCP client."""
from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/home/intel/Documents/Junction')
REVIEW = Path(__file__).resolve().parent
CONTEXT = ROOT / 'morph-intel-transfer/morph-context/context'
CLIENT = ROOT / 'morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/HachingJunction/context/verification/intel-continuation/sync_shared_context.py'


def load_client():
    spec = importlib.util.spec_from_file_location('existing_shared_context', CLIENT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Client()


def publish(payload_path: Path):
    raw = payload_path.read_bytes()
    payload = json.loads(raw)
    assert set(payload) == {'note_id', 'title', 'content', 'author', 'evidence', 'status'}
    assert len(payload['content']) < 24000
    destination = CONTEXT / 'outbox' / (payload['note_id'] + '.json')
    if destination.exists():
        assert json.loads(destination.read_bytes()) == payload, 'Immutable outbox conflict'
    else:
        destination.write_bytes(raw)
    client = load_client()
    saved = client.call('save_handoff', **payload)
    record = client.read(saved['path'])
    parsed = json.loads(record['content'])
    assert not record.get('redacted'), 'Readback was redacted'
    assert all(parsed.get(key) == value for key, value in payload.items()), 'Readback mismatch'
    receipt = {'note_id': payload['note_id'], 'shared_path': saved['path'],
               'saved_at': parsed['saved_at'], 'read_context_sha256': record['sha256'],
               'confirmed_at': datetime.now(timezone.utc).isoformat(),
               'created': saved['created'], 'six_payload_fields_match': True,
               'shared_server': client.server_name, 'tls_verification': True}
    target = REVIEW / 'receipts' / destination.name
    target.parent.mkdir(exist_ok=True)
    data = (json.dumps(receipt, indent=2) + '\n').encode()
    target.write_bytes(data)
    (CONTEXT / 'sync-receipts' / destination.name).write_bytes(data)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('payload', type=Path)
    args = parser.parse_args()
    print(json.dumps(publish(args.payload), indent=2))
