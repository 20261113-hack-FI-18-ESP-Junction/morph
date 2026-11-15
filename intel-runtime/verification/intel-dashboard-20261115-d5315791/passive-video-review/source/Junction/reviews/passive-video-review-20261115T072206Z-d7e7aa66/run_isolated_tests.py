"""Run the original bridge unittest suite in the authorized review-only venv.

The source/tests remain unchanged. An additional audit hook prohibits nonloopback
network destinations and permits only the two tests' inert Python child commands.
It does not grant access to Studio, media services, devices or model providers.
"""
from __future__ import annotations

import ast
import contextlib
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import sys
import time
import unittest
import xml.etree.ElementTree as ET

REVIEW = Path(__file__).resolve().parent
PAYLOAD = REVIEW / 'payload'
PACKAGE = PAYLOAD / 'intel-runtime/media-bridge'
EXPECTED_TEST_HASH = '1a242920d07e845f07fa04f548e5706b8d0eb9a63560fe932799cac3efda6d42'
assert sys.prefix == str(REVIEW / 'test-env')
assert hashlib.sha256((PACKAGE / 'tests/test_bridge.py').read_bytes()).hexdigest() == EXPECTED_TEST_HASH
manifest = json.loads((REVIEW / 'incoming/context/coordination/live-video-20261115-d7e7aa66-1470-4587-a2f9-5a37dadc7da6/MANIFEST.json').read_text())


def verify_payload():
    for item in manifest['files']:
        raw = (PAYLOAD / item['targetPath']).read_bytes()
        assert len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256']


verify_payload()
syntax = []
for path in sorted(PAYLOAD.rglob('*.py')):
    ast.parse(path.read_text(), filename=str(path))
    syntax.append(str(path.relative_to(PAYLOAD)))
dependencies = {name: importlib.metadata.version(name) for name in ('Pillow', 'websockets')}
assert dependencies == {'Pillow': '13.0.0', 'websockets': '17.4'}
runtime_temp = REVIEW / 'test-temp'
runtime_temp.mkdir(mode=0o700, exist_ok=False)
os.environ['TMPDIR'] = str(runtime_temp)
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.chdir(PACKAGE)
sys.path.insert(0, str(PACKAGE))
audit_counts = {'loopbackBinds': 0, 'loopbackConnects': 0, 'inertChildStarts': 0}


def audit(event, args):
    if event in {'socket.bind', 'socket.connect'}:
        address = args[1]
        if not (isinstance(address, tuple) and address[0] == '127.0.0.1'
                and isinstance(address[1], int)):
            raise RuntimeError('Review tests may use literal IPv4 loopback only')
        if event == 'socket.bind':
            if address[1] != 0:
                raise RuntimeError('Review tests may bind ephemeral fixture ports only')
            audit_counts['loopbackBinds'] += 1
        else:
            audit_counts['loopbackConnects'] += 1
    elif event == 'subprocess.Popen':
        executable, argv = args[:2]
        if not (executable == sys.executable
                and list(argv) == [sys.executable, '-c', 'import time; time.sleep(60)']):
            raise RuntimeError('Only inert, test-owned Python child processes are permitted')
        audit_counts['inertChildStarts'] += 1


sys.addaudithook(audit)


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []
        self.started = {}

    def startTest(self, test):
        self.started[test.id()] = time.monotonic()
        super().startTest(test)

    def stopTest(self, test):
        duration = time.monotonic() - self.started.pop(test.id())
        self.records.append({'id': test.id(), 'seconds': duration})
        super().stopTest(test)


suite = unittest.defaultTestLoader.discover(str(PACKAGE / 'tests'))
assert suite.countTestCases() == 25
started_at = datetime.now(timezone.utc).isoformat()
started_mono = time.monotonic()
log = io.StringIO()
with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
    result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=RecordedResult).run(suite)
duration = time.monotonic() - started_mono
verify_payload()
failures = {test.id(): detail for test, detail in result.failures}
errors = {test.id(): detail for test, detail in result.errors}
skips = {test.id(): detail for test, detail in result.skipped}
xml = ET.Element('testsuites', tests=str(result.testsRun), failures=str(len(failures)),
                 errors=str(len(errors)), skipped=str(len(skips)), time=str(duration))
group = ET.SubElement(xml, 'testsuite', name='original_passive_video_bridge',
                      tests=str(result.testsRun), failures=str(len(failures)),
                      errors=str(len(errors)), skipped=str(len(skips)), time=str(duration))
for record in result.records:
    classname, name = record['id'].rsplit('.', 1)
    element = ET.SubElement(group, 'testcase', classname=classname, name=name, time=str(record['seconds']))
    for tag, mapping in (('failure', failures), ('error', errors), ('skipped', skips)):
        if record['id'] in mapping:
            ET.SubElement(element, tag).text = mapping[record['id']]
ET.indent(xml)
(REVIEW / 'bridge-tests.xml').write_bytes(ET.tostring(xml, encoding='utf-8', xml_declaration=True) + b'\n')
(REVIEW / 'bridge-tests.log').write_text(log.getvalue())
report = {
    'status': 'passed' if result.wasSuccessful() else 'failed',
    'startedAt': started_at, 'completedAt': datetime.now(timezone.utc).isoformat(),
    'durationSeconds': duration, 'agent': '/root/adoption_receiver_review',
    'designatedReporter': '/root', 'interpreter': sys.executable, 'python': sys.version.split()[0],
    'command': [sys.executable, '-B', str(Path(__file__).resolve())],
    'workingDirectory': str(PACKAGE), 'temporaryDirectory': str(runtime_temp),
    'dependencies': dependencies, 'tests': {'run': result.testsRun,
        'failures': len(failures), 'errors': len(errors), 'skipped': len(skips)},
    'records': result.records, 'networkAudit': audit_counts,
    'syntaxParsedFiles': syntax, 'all60PayloadHashesUnchanged': True,
    'originalTestSHA256': EXPECTED_TEST_HASH,
    'temporaryFilesRemaining': [str(path.relative_to(runtime_temp)) for path in runtime_temp.rglob('*')],
    'activeStationEnvironmentModified': False, 'activeSourceModified': False,
    'actualBridgeStarted': False, 'actualFFmpegStarted': False, 'mediaMtxStarted': False,
    'studioAccessed': False, 'hardwareAccessed': False, 'providerCalls': 0,
    'scope': 'Original tests with synthetic JPEGs, ephemeral loopback fixture servers and two inert test-owned Python children only.',
}
with (REVIEW / 'bridge-test-result.json').open('x') as handle:
    json.dump(report, handle, indent=2)
    handle.write('\n')
print(json.dumps({key: value for key, value in report.items() if key != 'records'}, indent=2))
raise SystemExit(0 if result.wasSuccessful() else 1)
