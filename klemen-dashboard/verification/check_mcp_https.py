"""Real TLS Mac MCP relay with unique synthetic station ID and local fake GET API.

Requires the canonical workspace's context MCP runtime. This does not access Intel,
modify private pairing, or connect to a real station/robot/provider. Temporary
requests use a unique mac-three-host-test UUID and expire through the relay.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from uuid import uuid4

parser=argparse.ArgumentParser()
parser.add_argument('--workspace',required=True,type=Path)
parser.add_argument('--pairing-folder',required=True,type=Path)
args=parser.parse_args()
workspace=args.workspace.resolve()
package=Path(__file__).resolve().parents[1]
station_id='mac-three-host-test-'+str(uuid4())
worker_path=package.parent/'intel-runtime/transport/station_worker.py'
spec=importlib.util.spec_from_file_location('verified_station_worker',worker_path)
worker_module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=worker_module
spec.loader.exec_module(worker_module)
mcp=worker_module.MCPClient.from_pairing(args.pairing_folder.resolve())
mcp.initialize()
station_token=secrets.token_urlsafe(48)
body=json.dumps({'sourceMode':'simulation','payload':'x'*91_000},separators=(',',':')).encode()
csv=b'section,recordType,id,dataJson\nrecords,session,synthetic,{}\n'
sse=b'id: 1\nevent: record.created\ndata: {"sequence":1}\n\n'
requests=[]
class FakeStation(BaseHTTPRequestHandler):
    def log_message(self,*_args): pass
    def do_GET(self):
        if self.headers.get('Authorization')!='Bearer '+station_token:
            self.send_error(401);return
        requests.append(self.path)
        if self.path.startswith('/api/v1/events'):
            output=sse;content='text/event-stream'
        elif 'format=csv' in self.path:
            output=csv;content='text/csv'
        else: output=body;content='application/json'
        self.send_response(200)
        self.send_header('Content-Type',content)
        self.send_header('Content-Length',str(len(output)))
        self.end_headers();self.wfile.write(output)
http=ThreadingHTTPServer(('127.0.0.1',0),FakeStation)
thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
worker=worker_module.StationWorker(mcp,worker_module.StationHTTP(f'http://127.0.0.1:{http.server_port}',station_token),station_id=station_id)
result={'checkedAt':datetime.now(timezone.utc).isoformat(),'scope':'Node adapter -> existing Mac TLS MCP -> packaged worker -> local synthetic GET API -> MCP chunks -> Node. Not Intel, provider or physical verification.','stationId':station_id}
with tempfile.TemporaryDirectory(prefix='morph-node-mcp-') as temp:
    script=Path(temp)/'probe.mts'
    module=(package/'dashboard/server/mcpStationTransport.ts').as_posix()
    script.write_text('''import { createHash } from 'node:crypto';
import { createMcpStationFetch, createMcpToolClient, MCP_PROXY_ORIGIN } from '''+json.dumps(module)+''';
const callTool=createMcpToolClient(process.argv[2]);
const fetch=createMcpStationFetch({callTool,stationId:process.argv[3]});
const json=await fetch(MCP_PROXY_ORIGIN+'/api/v1/sessions/sim%3Acaptured/export?format=json');
const jsonBody=await json.text();
const csv=await fetch(MCP_PROXY_ORIGIN+'/api/v1/sessions/sim%3Acaptured/export?format=csv');
const csvBody=await csv.text();
const sse=await fetch(MCP_PROXY_ORIGIN+'/api/v1/events?after=0&once=true');
const sseBody=await sse.text();
const missingFetch=createMcpStationFetch({callTool,stationId:process.argv[3]+'-missing',timeoutMs:750,pollMs:100});
const missing=await missingFetch(MCP_PROXY_ORIGIN+'/api/v1/sessions');
const results={jsonStatus:json.status,jsonBytes:Buffer.byteLength(jsonBody),jsonSha256:createHash('sha256').update(jsonBody).digest('hex'),csvStatus:csv.status,csvBytes:Buffer.byteLength(csvBody),sseStatus:sse.status,sseBytes:Buffer.byteLength(sseBody),missingWorkerStatus:missing.status};
console.log(JSON.stringify(results));
if(json.status!==200||csv.status!==200||sse.status!==200||missing.status!==503) process.exitCode=1;
''')
    child=subprocess.Popen([str(workspace/'.junction-setup/node/bin/node'),str(package/'dashboard/node_modules/tsx/dist/cli.mjs'),str(script),str(args.pairing_folder.resolve()),station_id],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    rounds=[]
    try:
        deadline=time.monotonic()+25
        while child.poll() is None and time.monotonic()<deadline:
            outcome=worker.run_once(limit=8)
            if outcome['claimed']:rounds.append(outcome)
            time.sleep(.025)
        stdout,stderr=child.communicate(timeout=2)
        if child.returncode:raise RuntimeError('Node MCP roundtrip failed; synthetic data only')
        observed=json.loads(stdout)
        if observed['jsonSha256']!=hashlib.sha256(body).hexdigest() or observed['jsonBytes']!=len(body) or observed['csvBytes']!=len(csv) or observed['sseBytes']!=len(sse):
            raise RuntimeError('Roundtrip bytes did not match synthetic source')
        if sum(r['completed'] for r in rounds)!=3 or any(r['failed'] or r['expired'] for r in rounds):raise RuntimeError('Synthetic worker did not complete exactly three reads')
        result.update(status='passed',node=observed,syntheticWorkerRounds=rounds,httpGetPaths=requests,tlsVerificationEnabled=True,rawJsonBytes=len(body),jsonBase64Parts=3,sharedServerModified=False,pairingModified=False,actualIntelAccess=False)
    finally:
        if child.poll() is None:child.terminate();child.wait(timeout=3)
        http.shutdown();http.server_close();thread.join(timeout=3)
(package/'verification/mcp-https-roundtrip.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
