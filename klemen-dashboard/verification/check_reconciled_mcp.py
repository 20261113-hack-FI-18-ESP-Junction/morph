"""Isolated TLS MCP/worker/Node integration; never connects to Intel or providers.

Requires this package's installed dashboard dependencies and the adjacent
communication package's existing Python requirements. All temporary files,
synthetic credentials and relay state are created here and removed on exit.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', default='node')
    parser.add_argument('--communication', type=Path)
    args = parser.parse_args()
    package = Path(__file__).resolve().parents[1]
    communication = (args.communication or package.parent / 'communication').resolve()
    worker_path = communication / 'context_mcp/station_worker.py'
    spec = importlib.util.spec_from_file_location('reconciled_station_worker', worker_path)
    worker_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = worker_module
    spec.loader.exec_module(worker_module)
    station_id = 'local-reconciled-' + str(uuid4())
    station_token = secrets.token_urlsafe(48)
    large_json = json.dumps({'sourceMode': 'simulation', 'payload': 'x' * 91000}, separators=(',', ':')).encode()
    csv = b'section,recordType,id,dataJson\nrecords,session,synthetic,{}\n'
    sse = b'id: 1\nevent: record.created\ndata: {"sequence":1}\n\n'
    review_body = '{\n  "id": "review:1", "eventId": "event:1", "reason": "Late review: Živjo ✓"\n}'
    analysis_body = '{ "requestId": "analysis:1", "question": "Explain saved evidence." }'
    requests = []

    class FakeStation(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, status, body, content='application/json'):
            self.send_response(status)
            self.send_header('Content-Type', content)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            if self.headers.get('Authorization') != 'Bearer ' + station_token:
                self.reply(401, b'{"detail":"synthetic authentication failed"}')
                return False
            return True

        def do_GET(self):
            if not self.authorized():
                return
            requests.append({'method': 'GET', 'path': self.path})
            if self.path.startswith('/api/v1/events'):
                self.reply(200, sse, 'text/event-stream')
            elif self.path.startswith('/api/v1/analysis/context'):
                ids = parse_qs(urlsplit(self.path).query).get('sessionIds')
                self.reply(200, json.dumps({'sessionIds': ids}).encode())
            elif 'format=csv' in self.path:
                self.reply(200, csv, 'text/csv')
            else:
                self.reply(200, large_json)

        def do_POST(self):
            if not self.authorized():
                return
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            requests.append({'method': 'POST', 'path': self.path, 'body': body.decode('utf-8'),
                             'bodySha256': hashlib.sha256(body).hexdigest()})
            if self.path.endswith('/review'):
                self.reply(200, b'{"duplicate":false,"accepted":"review"}')
            elif json.loads(body)['requestId'] == 'analysis:conflict':
                self.reply(409, b'{"detail":{"code":"selection_changed","message":"Refresh saved evidence."}}')
            else:
                self.reply(202, b'{"accepted":"analysis","requestId":"analysis:1"}')

    api = ThreadingHTTPServer(('127.0.0.1', 0), FakeStation)
    api_thread = threading.Thread(target=api.serve_forever, daemon=True)
    api_thread.start()
    server = child = None
    result = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'scope':
              'Isolated Node adapter -> temporary authenticated TLS MCP -> staged worker -> local synthetic API. No Intel, provider, robot or existing MCP access.',
              'stationId': station_id}
    try:
        with tempfile.TemporaryDirectory(prefix='.reconciled-mcp-', dir=package / 'verification') as temporary:
            temp = Path(temporary)
            pairing = temp / 'pairing'
            pairing.mkdir(mode=0o700)
            project = temp / 'project'
            project.mkdir()
            (project / 'AGENTS.md').write_text('# Synthetic isolated verification project\n')
            cert, key = pairing / 'morph-ca.pem', temp / 'server-key.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                            '-subj', '/CN=localhost', '-addext', 'subjectAltName=IP:127.0.0.1,DNS:localhost',
                            '-keyout', str(key), '-out', str(cert)], check=True, capture_output=True)
            key.chmod(0o600)
            with socket.socket() as reservation:
                reservation.bind(('127.0.0.1', 0))
                port = reservation.getsockname()[1]
            mcp_token = secrets.token_urlsafe(48)
            token_file = temp / 'token'
            token_file.write_text(mcp_token)
            token_file.chmod(0o600)
            connection = pairing / 'connection.json'
            connection.write_text(json.dumps({'url': f'https://127.0.0.1:{port}/mcp', 'token': mcp_token}))
            connection.chmod(0o600)
            with (temp / 'server.log').open('w') as server_log:
                server = subprocess.Popen([sys.executable, str(communication / 'context_mcp/server.py'),
                    '--root', str(project), '--transport', 'http', '--host', '127.0.0.1', '--port', str(port),
                    '--token-file', str(token_file), '--tls-cert', str(cert), '--tls-key', str(key),
                    '--enable-station-relay'], stdout=server_log, stderr=server_log)
                ready = False
                for _ in range(100):
                    if server.poll() is not None:
                        diagnostic = (temp / 'server.log').read_text()[-2000:]
                        raise RuntimeError('Isolated MCP server exited before becoming ready: ' + diagnostic.replace(mcp_token, '[redacted]'))
                    try:
                        with socket.create_connection(('127.0.0.1', port), timeout=.1):
                            ready = True
                            break
                    except OSError:
                        time.sleep(.05)
                if not ready:
                    raise RuntimeError('Isolated MCP server did not become ready')
                mcp = worker_module.MCPClient.from_pairing(pairing)
                mcp.initialize()
                worker = worker_module.StationWorker(mcp, worker_module.StationHTTP(
                    f'http://127.0.0.1:{api.server_port}', station_token), station_id=station_id, allow_writes=True)
                script = temp / 'probe.mts'
                script.write_text('''import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createMcpStationFetch, createMcpToolClient, MCP_PROXY_ORIGIN } from ''' +
                    json.dumps((package / 'dashboard/server/mcpStationTransport.ts').as_posix()) + ''';
const rpc = createMcpToolClient(process.argv[2]);
const enqueues = [], readyPages = [];
const callTool = async (name, args, signal) => {
  const result = await rpc(name, args, signal);
  if (name.startsWith('enqueue_')) enqueues.push({tool:name,method:args.method ?? 'GET',path:args.path,intent:args.intent,query:args.query});
  if (name === 'read_station_response' && result.state === 'ready') readyPages.push({offset:result.offset,next:result.next_offset});
  return result;
};
const read = createMcpStationFetch({callTool, stationId:process.argv[3], pollMs:25});
const status = {};
const get = async (label,path) => { const r = await read(MCP_PROXY_ORIGIN+path); status[label]=r.status; return await r.text(); };
const jsonBody = await get('json','/api/v1/sessions/sim%3Acaptured/export?format=json');
const csvBody = await get('csv','/api/v1/sessions/sim%3Acaptured/export?format=csv');
const sseBody = await get('sse','/api/v1/events?after=0&once=true');
const context = JSON.parse(await get('context','/api/v1/analysis/context?kind=session_comparison&sessionIds=baseline&sessionIds=adaptive&sourceMode=simulation&baselineSessionId=baseline&adaptiveSessionId=adaptive'));
assert.deepEqual(context.sessionIds,['baseline','adaptive']);
const post = async (label,path,body,intent,fetcher=read) => { const r=await fetcher(MCP_PROXY_ORIGIN+path,{method:'POST',body,headers:{'Content-Type':'application/json','X-Morph-Intent':intent}});status[label]=r.status;return await r.text(); };
const review = ''' + json.dumps(review_body, ensure_ascii=False) + ''';
const analysis = ''' + json.dumps(analysis_body) + ''';
assert.equal(await post('review','/api/v1/cycles/demo%3Aretry/review',review,'record-review'),'{"duplicate":false,"accepted":"review"}');
assert.equal(await post('analysis','/api/v1/analysis/reports',analysis,'evidence-analysis'),'{"accepted":"analysis","requestId":"analysis:1"}');
assert.equal(await post('conflict','/api/v1/analysis/reports',analysis.replace('analysis:1','analysis:conflict'),'evidence-analysis'),'{"detail":{"code":"selection_changed","message":"Refresh saved evidence."}}');
const missing = createMcpStationFetch({callTool,stationId:process.argv[3]+'-missing',timeoutMs:750,pollMs:50});
const unavailable = await missing(MCP_PROXY_ORIGIN+'/api/v1/sessions'); status.missingRead=unavailable.status; await unavailable.text();
assert.match(await post('missingPost','/api/v1/analysis/reports',analysis,'evidence-analysis',missing),/outcome is unknown/);
assert.deepEqual(status,{json:200,csv:200,sse:200,context:200,review:200,analysis:202,conflict:409,missingRead:503,missingPost:503});
assert.equal(enqueues.length,9);
console.log(JSON.stringify({status,enqueues,readyPages,jsonBytes:Buffer.byteLength(jsonBody),jsonSha256:createHash('sha256').update(jsonBody).digest('hex'),csvBody,sseBody,tlsVerificationEnabled:true}));
''')
                child = subprocess.Popen([args.node, str(package / 'dashboard/node_modules/tsx/dist/cli.mjs'),
                    str(script), str(pairing), station_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                rounds = []
                deadline = time.monotonic() + 30
                while child.poll() is None and time.monotonic() < deadline:
                    outcome = worker.run_once(limit=1)
                    if outcome['claimed']:
                        rounds.append(outcome)
                    time.sleep(.025)
                stdout, stderr = child.communicate(timeout=2)
                if child.returncode:
                    raise RuntimeError('Node integration assertions failed: ' + stderr[-2000:])
                observed = json.loads(stdout)
                assert observed['jsonBytes'] == len(large_json)
                assert observed['jsonSha256'] == hashlib.sha256(large_json).hexdigest()
                assert observed['csvBody'].encode() == csv and observed['sseBody'].encode() == sse
                assert observed['readyPages'][:3] == [{'offset': 0, 'next': 60000}, {'offset': 60000, 'next': 120000}, {'offset': 120000, 'next': None}]
                assert sum(item['completed'] for item in rounds) == 7
                assert not any(item['failed'] or item['expired'] for item in rounds)
                posts = [request for request in requests if request['method'] == 'POST']
                assert len(posts) == 3 and posts[0]['body'] == review_body and posts[1]['body'] == analysis_body
                assert posts[2]['body'] == analysis_body.replace('analysis:1', 'analysis:conflict')
                for item in posts:
                    del item['body']
                assert len(requests) == 7
                result.update(status='passed', node=observed, syntheticWorkerRounds=rounds,
                              localApiRequests=requests, completedAt=datetime.now(timezone.utc).isoformat(),
                              actualIntelAccess=False, providerCalls=False, existingMcpModified=False,
                              sourceSha256={name: hashlib.sha256((communication / 'context_mcp' / name).read_bytes()).hexdigest()
                                            for name in ('server.py', 'station_relay.py', 'station_worker.py')},
                              adapterSha256=hashlib.sha256((package / 'dashboard/server/mcpStationTransport.ts').read_bytes()).hexdigest())
                server.terminate()
                server.wait(timeout=5)
                server = None
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
        if server is not None and server.poll() is None:
            server.terminate()
            server.wait(timeout=5)
        api.shutdown()
        api.server_close()
        api_thread.join(timeout=3)
    (package / 'verification/reconciled-mcp-roundtrip.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'completedRequests': len(requests), 'nodeStatuses': result['node']['status']}))


if __name__ == '__main__':
    main()
