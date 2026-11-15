"""Authenticated same-server event lifecycle with legacy context and relay tools."""
from pathlib import Path
import sys
import tempfile
import unittest
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import create_server, http_app
from starlette.testclient import TestClient


class HandoffMCPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='morph-event-mcp-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'AGENTS.md').write_text('# Isolated MCP event fixture\n')
        self.token = 'synthetic-event-transport-' + 'z' * 32

    def client(self, enabled=True):
        app = http_app(create_server(self.root, enable_station_relay=True,
                                    enable_handoff_events=enabled), self.token, '127.0.0.1', 8765)
        return TestClient(app, base_url='http://127.0.0.1:8765')

    def rpc(self, client, method, params=None):
        response = client.post('/mcp', headers={'Authorization': 'Bearer ' + self.token,
            'Accept': 'application/json, text/event-stream'}, json={'jsonrpc': '2.0', 'id': 1,
            'method': method, 'params': params or {}})
        self.assertEqual(response.status_code, 200)
        return response.json()['result']

    def call(self, client, name, arguments, error=False):
        result = self.rpc(client, 'tools/call', {'name': name, 'arguments': arguments})
        self.assertEqual(bool(result.get('isError')), error, result)
        return result if error else result['structuredContent']

    def note(self, client, author='Synthetic test publisher'):
        identifier = str(uuid4())
        saved = self.call(client, 'save_handoff', {'note_id': identifier, 'title': 'Synthetic event test',
            'content': 'Software transport fixture only. No physical or provider result.',
            'author': author, 'evidence': 'Isolated test fixture.', 'status': 'handoff'})
        read = self.call(client, 'read_context', {'path': saved['path']})
        return {'note_id': identifier, 'origin': 'intel', 'target': 'mac', 'note_sha256': read['sha256']}

    def test_disabled_events_preserve_legacy_catalog_and_saves_do_not_publish(self):
        with self.client(False) as client:
            names = {t['name'] for t in self.rpc(client, 'tools/list')['tools']}
            self.assertEqual(len(names), 11)
            self.assertNotIn('publish_handoff_event', names)
            self.note(client)
        with self.client() as client:
            state = self.call(client, 'poll_handoff_events', {'target': 'mac', 'consumer_id': 'test'})
            self.assertEqual(state['events'], [])

    def test_auth_catalog_and_full_durable_lifecycle(self):
        with self.client() as client:
            self.assertEqual(client.post('/mcp', json={}).status_code, 401)
            self.assertEqual(client.post('/mcp', headers={'Authorization': 'Bearer synthetic-invalid'}, json={}).status_code, 401)
            names = {t['name'] for t in self.rpc(client, 'tools/list')['tools']}
            self.assertEqual(len(names), 17)
            args = self.note(client)
            published = self.call(client, 'publish_handoff_event', args)
            self.assertTrue(published['created'])
            self.assertFalse(self.call(client, 'publish_handoff_event', args)['created'])
            event = published['event']
            self.assertIsNone(event['received_at'])
            poll = self.call(client, 'poll_handoff_events', {'target': 'mac', 'consumer_id': 'test'})
            self.assertEqual(len(poll['events']), 1)
            self.assertIsNone(poll['events'][0]['received_at'])
            claim = self.call(client, 'claim_handoff_event', {'target': 'mac', 'consumer_id': 'test', 'event_id': event['event_id']})['event']
            self.assertIsNotNone(claim['received_at'])
            self.assertIsNone(claim['processed_at'])
            ident = {'target': 'mac', 'consumer_id': 'test', 'event_id': event['event_id'], 'claim_id': claim['claim_id']}
            self.assertTrue(self.call(client, 'renew_handoff_event', ident)['renewed'])
            completion = {**ident, 'outcome': 'processed', 'result_sha256': 'd' * 64}
            self.assertFalse(self.call(client, 'complete_handoff_event', completion)['duplicate'])
            self.assertTrue(self.call(client, 'complete_handoff_event', completion)['duplicate'])
        with self.client() as client:
            final = self.call(client, 'read_handoff_event', {'target': 'mac', 'event_id': event['event_id']})['event']
            self.assertEqual(final['state'], 'processed')
            self.assertIsNotNone(final['processed_at'])
            self.assertEqual(final['result_sha256'], 'd' * 64)

    def test_idle_receipt_and_wrong_hash_rejected_without_work(self):
        with self.client() as client:
            args = self.note(client, 'Codex on Mac | scheduled project review')
            self.call(client, 'publish_handoff_event', args, error=True)
            normal = self.note(client)
            self.call(client, 'publish_handoff_event', {**normal, 'note_sha256': '0' * 64}, error=True)
            self.assertEqual(self.call(client, 'poll_handoff_events', {'target': 'mac', 'consumer_id': 'test'})['events'], [])


if __name__ == '__main__':
    unittest.main()
