#!/usr/bin/env python3
"""Explicit, TLS-verified shared-context checkpoint reader and publisher.

Reads the existing private pairing in memory. Does not copy credentials, change
Codex configuration, synchronize source files, or write Notion. Invoke manually
for a meaningful checkpoint; an outbox payload is immutable across retries.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone


PROJECT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
PAIRING = Path('/home/intel/Documents/Junction/morph-intel-transfer/morph-intel-pairing')


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Shared endpoint redirected; credentials were not forwarded')


class Client:
    def __init__(self):
        self.connection = json.loads((PAIRING / 'connection.json').read_text())
        tls = ssl.create_default_context(cafile=str(PAIRING / 'morph-ca.pem'))
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=tls))
        self.headers = {'Authorization': 'Bearer ' + self.connection['token'],
                        'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
        self.sequence = 0
        hello = self.request('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
                             'clientInfo': {'name': 'morph-intel-continuation-reporting', 'version': '1.0'}})
        self.headers['MCP-Protocol-Version'] = hello['protocolVersion']
        self.server_name = hello['serverInfo']['name']
        self.request('notifications/initialized', notification=True)

    def request(self, method, params=None, notification=False):
        self.sequence += 1
        payload = {'jsonrpc': '2.0', 'method': method}
        if not notification:
            payload['id'] = self.sequence
        if params is not None:
            payload['params'] = params
        req = urllib.request.Request(self.connection['url'], data=json.dumps(payload).encode(), headers=self.headers)
        try:
            with self.opener.open(req, timeout=20) as response:
                body = response.read()
            result = json.loads(body) if body else {}
            if 'error' in result:
                raise RuntimeError('MCP returned a JSON-RPC error: ' + str(result['error'].get('code')))
            return result.get('result', {})
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'Shared context returned HTTP {error.code}') from None
        except urllib.error.URLError as error:
            reason = str(error.reason)
            for value in self.connection.values():
                if isinstance(value, str):
                    reason = reason.replace(value, '[private connection value]')
            raise RuntimeError('Shared context connection failed: ' + reason) from None

    def call(self, name, **arguments):
        result = self.request('tools/call', {'name': name, 'arguments': arguments})
        if result.get('isError'):
            raise RuntimeError(f'Shared tool {name} returned an error; inspect the server without logging credentials')
        if 'structuredContent' not in result:
            raise RuntimeError(f'Shared tool {name} omitted structured content')
        return result['structuredContent']

    def read(self, path):
        offset, chunks, hashes = 0, [], set()
        while True:
            result = self.call('read_context', path=path, offset=offset, limit=24000)
            chunks.append(result['content'])
            hashes.add(result['sha256'])
            if result['next_offset'] is None:
                break
            if result['next_offset'] <= offset:
                raise RuntimeError('Shared read pagination did not advance')
            offset = result['next_offset']
        content = ''.join(chunks)
        digest = hashlib.sha256(content.encode()).hexdigest()
        if hashes != {digest}:
            raise RuntimeError('Shared file changed during pagination or hash mismatch')
        return {**result, 'content': content, 'offset': 0, 'sha256': digest}


def read_checkpoint(client, label):
    destination = EVIDENCE / label
    overview = client.call('get_project_context')
    save(destination / 'get-project-context.json', overview)
    paths = ['AGENTS.md', 'context/INTEL_CODEX.md', 'context/START_HERE.md', 'context/CHAT_CONTEXT.md',
             'PHYSICAL_AI_TASK_PLAN.md', 'NOTION_SYNC.md']
    files = []
    for path in paths:
        result = client.read(path)
        target = destination / 'shared-context' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result['content'], encoding='utf-8')
        local = PROJECT / path
        files.append({'path': path, 'sha256': result['sha256'],
                      'matches_local': local.is_file() and hashlib.sha256(local.read_bytes()).hexdigest() == result['sha256'],
                      'redacted': result['redacted']})
    offset, pages, notes = 0, 0, []
    while True:
        result = client.call('list_context', prefix='context/notes/', offset=offset, limit=100)
        pages += 1
        for entry in result['files']:
            record = client.read(entry['path'])
            parsed = json.loads(record['content'])
            target = destination / 'shared-context' / entry['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(record['content'], encoding='utf-8')
            notes.append({'path': entry['path'], 'note_id': parsed['note_id'], 'title': parsed['title'],
                          'saved_at': parsed['saved_at'], 'sha256': record['sha256']})
        if result['next_offset'] is None:
            break
        offset = result['next_offset']
    tools = client.request('tools/list')
    report = {'observed_at': now(), 'server': client.server_name, 'tls_verification': True,
              'files': files, 'catalog_pages': pages, 'notes_read': len(notes), 'notes': notes,
              'shared_tools': [item['name'] for item in tools['tools']],
              'notion_sync': 'unavailable: no Notion connector exposed in this Intel task or shared context tool list'}
    save(destination / 'context-read-report.json', report)
    print(json.dumps(report, indent=2))


def publish(client, payload_path):
    payload_path = payload_path.resolve()
    if payload_path.parent != (PROJECT / 'context/outbox').resolve():
        raise ValueError('Publish only an existing project outbox payload')
    payload = json.loads(payload_path.read_text(encoding='utf-8'))
    if set(payload) != {'note_id', 'title', 'content', 'author', 'evidence', 'status'}:
        raise ValueError('The outbox must contain exactly the six protocol fields')
    result = client.call('save_handoff', **payload)
    record = client.read(result['path'])
    parsed = json.loads(record['content'])
    if any(parsed.get(key) != value for key, value in payload.items()):
        raise RuntimeError('Saved payload differs on read-back; preserve outbox and inspect redaction')
    receipt = {'note_id': payload['note_id'], 'shared_path': result['path'], 'saved_at': parsed['saved_at'],
               'read_context_sha256': record['sha256'], 'confirmed_at': now(), 'created': result['created'],
               'six_payload_fields_match': True, 'shared_server': client.server_name,
               'tls_verification': True, 'notion_sync': 'pending; separate connector required'}
    save(PROJECT / 'context/sync-receipts' / payload_path.name, receipt)
    print(json.dumps(receipt, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--read-checkpoint')
    action.add_argument('--publish', type=Path)
    args = parser.parse_args()
    if args.read_checkpoint and ('/' in args.read_checkpoint or args.read_checkpoint in {'.', '..'}):
        raise ValueError('Use a simple checkpoint name')
    client = Client()
    if args.read_checkpoint:
        read_checkpoint(client, args.read_checkpoint)
    else:
        publish(client, args.publish)


if __name__ == '__main__':
    main()
