"""Private backup and read-only checks shared by the reviewed transition tools."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import sqlite3
import stat
import time
import urllib.error
import urllib.request

ROOT = Path('/home/intel/Documents/Junction')
REVIEW = Path(__file__).resolve().parent
ADOPTION = ROOT / 'reviews/intel-adoption-20261115T051202Z-b71f04ec'
PROJECT = ROOT / 'morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/HachingJunction'
PYTHON = ROOT / 'morph-intel-transfer/morph-context/.junction-setup/python/bin/python'
DATA = PROJECT / 'station/.data'
DATABASE = DATA / 'station.sqlite3'
EVIDENCE = DATA / 'evidence'
TOKEN = DATA / 'api-token'
SERVICE_PID = 188282
SERVICE_TICKS = 10907663
PRESERVED = {'stationWorker': (417036, 14287604), 'fiveMinuteWatcher': (279692, 11717397),
             'dashboard': (188283, 10907663)}
ORIGIN = 'http://127.0.0.1:8000'
MAIN_ARGUMENTS = ['-m', 'morph_station', 'serve', '--host', '127.0.0.1', '--port', '8000']
API_HASH = '3ab02fc234add63fc1150db6c107324dafe68266cfdaad453c554e7753e7845a'
STORE_HASH = 'd099d4b67269df66be6b09a24941ac71044f3de20e6d151dcded2f3e3bc59939'
WORKER_HASH = 'bfadd54fb186dffa4bbf0f21a95c0d815bb187833a57a3e382a7b6efc72c0bc2'
WATCHER_HASH = '901491c5fd6a522c73591990bd4f7ee0d5c91f287d861c3b052cc2c4b1fb4dbd'
TABLES = ('schema_migrations', 'records', 'events', 'revisions', 'request_receipts', 'review_requests', 'sqlite_sequence')


class Blocked(Exception):
    """A fixed, credential-free reason requiring review."""


def require(condition, code):
    if not condition:
        raise Blocked(code)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def private_json(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
        json.dump(value, output, indent=2, sort_keys=True, allow_nan=False)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())


def private_directory(path):
    path = Path(path)
    path.mkdir(mode=0o700, exist_ok=False)
    return path


def regular_owned(path, private=False):
    info = Path(path).lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid(), 'unexpected_file_type_or_owner')
    if private:
        require(stat.S_IMODE(info.st_mode) == 0o600, 'private_file_mode_required')
    return info


def process_identity(pid, expected_ticks=None):
    proc = Path('/proc') / str(pid)
    fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
    ticks = int(fields[19])
    require(fields[0] != 'Z', 'expected_process_is_zombie')
    require(expected_ticks is None or ticks == expected_ticks, 'expected_process_identity_changed')
    require(proc.stat().st_uid == os.getuid(), 'expected_process_owner_changed')
    boot = next(int(line.split()[1]) for line in Path('/proc/stat').read_text().splitlines() if line.startswith('btime '))
    return {'pid': pid, 'startTicks': ticks, 'startedAt': datetime.fromtimestamp(boot + ticks / os.sysconf('SC_CLK_TCK'), timezone.utc).isoformat(),
            'cwd': os.readlink(proc / 'cwd'), 'executable': os.readlink(proc / 'exe')}


def process_arguments(pid):
    return [os.fsdecode(part) for part in (Path('/proc') / str(pid) / 'cmdline').read_bytes().split(b'\0') if part]


def owns_main_socket(pid):
    inodes = set()
    for source in ('/proc/net/tcp', '/proc/net/tcp6'):
        for line in Path(source).read_text().splitlines()[1:]:
            fields = line.split()
            if fields[3] == '0A' and fields[1] == '0100007F:1F40':
                inodes.add(fields[9])
    owned = set()
    for fd in (Path('/proc') / str(pid) / 'fd').iterdir():
        try:
            link = os.readlink(fd)
        except FileNotFoundError:
            continue
        if link.startswith('socket:['):
            owned.add(link[8:-1])
    return bool(inodes & owned)


def main_port_listening():
    for source in ('/proc/net/tcp', '/proc/net/tcp6'):
        for line in Path(source).read_text().splitlines()[1:]:
            fields = line.split()
            if fields[3] == '0A' and int(fields[1].rsplit(':', 1)[1], 16) == 8000:
                return True
    return False


def source_guard():
    require(sha(PROJECT / 'station/morph_station/api.py') == API_HASH, 'dashboard_api_hash_changed')
    require(sha(PROJECT / 'station/morph_station/store.py') == STORE_HASH, 'dashboard_store_hash_changed')
    before = json.loads((REVIEW / 'station-source-baseline.json').read_text())
    for entry in before['preservedFiles']:
        require(sha(PROJECT / entry['path']) == entry['sha256'], 'preserved_station_source_changed')
    require(sha(ROOT / 'mcp-runtime-20261115T051202Z/station_worker.py') == WORKER_HASH, 'worker_source_changed')
    require(sha(ROOT / 'scripts/watch_mac_context.py') == WATCHER_HASH, 'watcher_source_changed')


def preserved_guard():
    identities = {name: process_identity(pid, ticks) for name, (pid, ticks) in PRESERVED.items()}
    expected_worker = json.loads((ADOPTION / 'station-worker-launch.json').read_text())['argv']
    require(process_arguments(PRESERVED['stationWorker'][0]) == expected_worker, 'worker_arguments_changed')
    require('--allow-record-writes' not in expected_worker, 'worker_must_remain_get_only')
    watcher = process_arguments(PRESERVED['fiveMinuteWatcher'][0])
    require('--interval' in watcher and watcher[watcher.index('--interval') + 1] == '300', 'watcher_interval_changed')
    return identities


def service_guard(pid=SERVICE_PID, ticks=SERVICE_TICKS, require_listener=True):
    source_guard()
    identity = process_identity(pid, ticks)
    require(Path(identity['cwd']) == PROJECT, 'station_working_directory_changed')
    require(Path(identity['executable']).resolve() == PYTHON.resolve(), 'station_interpreter_changed')
    argv = process_arguments(pid)
    require(argv[1:] == MAIN_ARGUMENTS and Path(argv[0]).resolve() == PYTHON.resolve(), 'station_arguments_changed')
    if require_listener:
        require(owns_main_socket(pid), 'station_does_not_own_loopback_8000')
    else:
        require(not main_port_listening(), 'recovery_requires_no_port_8000_listener')
    raw_environment = (Path('/proc') / str(pid) / 'environ').read_bytes()
    environment = dict(os.fsdecode(part).split('=', 1) for part in raw_environment.split(b'\0') if b'=' in part)
    require('MORPH_API_TOKEN' not in environment, 'unexpected_station_environment_token_override')
    require(environment.get('MORPH_TOKEN_FILE') == str(TOKEN), 'station_token_file_changed')
    require(environment.get('MORPH_DATA_DIR') == str(DATA), 'station_data_directory_changed')
    require(Path(environment.get('MORPH_DB_PATH', DATA / 'station.sqlite3')) == DATABASE, 'station_database_changed')
    require(Path(environment.get('MORPH_EVIDENCE_DIR', DATA / 'evidence')) == EVIDENCE, 'station_evidence_directory_changed')
    regular_owned(TOKEN, private=True)
    regular_owned(DATABASE)
    identity['argv'] = argv
    return identity, environment, preserved_guard()


def readonly_database(path, immutable=False):
    suffix = '?mode=ro&immutable=1' if immutable else '?mode=ro'
    connection = sqlite3.connect(Path(path).resolve().as_uri() + suffix, uri=True, timeout=10)
    connection.execute('PRAGMA query_only=ON')
    return connection


def consistent_backup(source, target):
    regular_owned(source)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.close(descriptor)
    start = time.monotonic()

    def bounded_backup(status, remaining, total):
        require(time.monotonic() - start < 20, 'read_only_backup_deadline_exceeded')

    src = readonly_database(source)
    dst = sqlite3.connect(target, timeout=10)
    try:
        src.backup(dst, pages=128, progress=bounded_backup, sleep=0.05)
        result = dst.execute('PRAGMA integrity_check').fetchone()[0]
        require(result == 'ok', 'backup_integrity_check_failed')
        dst.commit()
    finally:
        dst.close()
        src.close()
    regular_owned(target, private=True)
    with Path(target).open('rb') as handle:
        os.fsync(handle.fileno())
    return {'path': str(target), 'sha256': sha(target), 'bytes': Path(target).stat().st_size,
            'sourceOpenedWith': 'mode=ro; query_only=ON', 'mode': '0600',
            'integrityCheck': 'ok', 'createdAt': timestamp(), 'retainedWithoutFurtherWrites': True}


def ledger_summary(path, immutable=False):
    db = readonly_database(path, immutable=immutable)
    try:
        db.execute('BEGIN')
        present = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        require(set(TABLES) <= present, 'canonical_table_missing')
        tables = {}
        for table in TABLES:
            columns = [row[1] for row in db.execute('PRAGMA table_info("' + table + '")')]
            order = ','.join('"' + column.replace('"', '""') + '"' for column in columns)
            result = hashlib.sha256()
            count = 0
            for row in db.execute('SELECT * FROM "' + table + '" ORDER BY ' + order):
                normalized = [{'base64': base64.b64encode(value).decode()} if isinstance(value, bytes) else value for value in row]
                result.update(json.dumps(normalized, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode() + b'\n')
                count += 1
            tables[table] = {'count': count, 'sha256': result.hexdigest(), 'columns': columns}
        kinds = {row[0]: row[1] for row in db.execute('SELECT kind,COUNT(*) FROM records GROUP BY kind ORDER BY kind')}
        modes = {row[0]: row[1] for row in db.execute("SELECT json_extract(payload,'$.sourceMode'),COUNT(*) FROM records WHERE kind='session' GROUP BY json_extract(payload,'$.sourceMode')")}
        sequence = db.execute('SELECT COALESCE(MAX(sequence),0) FROM events').fetchone()[0]
        schema = db.execute('PRAGMA schema_version').fetchone()[0]
        schema_text = list(db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"))
        schema_hash = hashlib.sha256(json.dumps(schema_text, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        return {'tables': tables, 'recordsByKind': kinds, 'sessionsBySourceMode': modes,
                'lastEventSequence': sequence, 'sqliteSchemaVersion': schema, 'sqliteSchemaSha256': schema_hash}
    finally:
        db.close()


def same_canonical(left, right):
    """Compare all persisted rows and SQL schema across separate databases.

    SQLite's internal schema cookie is local to a database file and changed from
    8 to 1 in the observed backup. Check that cookie before/after on each same
    database separately. The actual schema_migrations rows and SQL schema hash
    remain required here, along with every canonical row and event cursor.
    """
    return {key: value for key, value in left.items() if key != 'sqliteSchemaVersion'} == {
        key: value for key, value in right.items() if key != 'sqliteSchemaVersion'}


def evidence_manifest(directory=EVIDENCE):
    root_info = Path(directory).lstat()
    require(stat.S_ISDIR(root_info.st_mode), 'evidence_root_is_not_regular_directory')
    files = []
    for path in sorted(Path(directory).rglob('*')):
        info = path.lstat()
        require(not stat.S_ISLNK(info.st_mode), 'evidence_symlink_requires_review')
        if stat.S_ISDIR(info.st_mode):
            continue
        require(stat.S_ISREG(info.st_mode), 'evidence_nonregular_file_requires_review')
        files.append({'relativePath': str(path.relative_to(directory)), 'bytes': info.st_size,
                      'sha256': sha(path), 'mode': oct(stat.S_IMODE(info.st_mode))})
    manifest_hash = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'directory': str(directory), 'fileCount': len(files), 'files': files, 'manifestSha256': manifest_hash}


def response_summary(path, status, body):
    result = {'method': 'GET', 'path': path, 'status': status, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
    try:
        value = json.loads(body)
    except (ValueError, UnicodeError):
        result['json'] = False
        return result
    result['json'] = True
    if isinstance(value, dict):
        result['topLevelKeys'] = sorted(value)
        if path == '/health':
            result['health'] = {key: value.get(key) for key in ('status', 'schemaVersion', 'hardwareIntegrated', 'providersIntegrated', 'dashboardRead')}
        if path == '/api/v1/schema':
            result['capabilities'] = value.get('capabilities')
            result['responseSchemas'] = sorted(value.get('responses', {}))
        if path == '/openapi.json':
            result['version'] = value.get('info', {}).get('version')
            result['dashboardPresent'] = '/api/v1/dashboard' in value.get('paths', {})
            result['analystPresent'] = '/api/v1/analysis/reports' in value.get('paths', {})
        if path.startswith('/api/v1/dashboard') and status == 200:
            result['sourceMode'] = value.get('sourceMode')
            result['sessionCount'] = value.get('sessions', {}).get('total')
            result['cycleCount'] = value.get('recentCycles', {}).get('total')
            result['lastEventSequence'] = value.get('lastEventSequence')
            result['selectionPresent'] = value.get('selectedSessionId') is not None
    elif isinstance(value, list):
        result['itemCount'] = len(value)
    return result


def direct_get(path, token):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(ORIGIN + path, headers={'Authorization': 'Bearer ' + token}, method='GET')
    try:
        response = opener.open(request, timeout=3)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        body = response.read(4 * 1024 * 1024 + 1)
        require(len(body) <= 4 * 1024 * 1024, 'response_exceeds_preflight_bound')
        return response_summary(path, response.status, body)


def draining_service_guard():
    """Inspect the exact old process after its recorded SIGTERM without requiring a listener."""
    return service_guard(require_listener=False)


def owned_draining_connections(pid):
    """Return connection metadata only; no socket reads, closes or payloads."""
    owned = set()
    for descriptor in (Path('/proc') / str(pid) / 'fd').iterdir():
        try:
            value = os.readlink(descriptor)
        except FileNotFoundError:
            continue
        if value.startswith('socket:['):
            owned.add(value[8:-1])
    connections = []
    for source in ('/proc/net/tcp', '/proc/net/tcp6'):
        for line in Path(source).read_text().splitlines()[1:]:
            fields = line.split()
            if fields[9] in owned and int(fields[1].rsplit(':', 1)[1], 16) == 8000:
                require(fields[3] != '0A', 'draining_process_still_has_listener')
                connections.append({'local': fields[1], 'remote': fields[2], 'state': fields[3], 'inode': fields[9]})
    return connections


def analyst_snapshot(expected_owner=None):
    """Inspect default analyst storage and kernel lock metadata without acquiring a lock.

    The fixed serve argv passes no explicit analysis directory; create_app uses
    DATABASE.parent/analysis. Never construct AnalysisService during inspection.
    Existing reports/indices must need no recovery writes before starting.
    """
    directory = DATABASE.parent / 'analysis'
    result = {'path': str(directory), 'exists': directory.exists(), 'files': [],
              'pendingReports': 0, 'reportCount': 0, 'lockOwners': []}
    if not directory.exists():
        require(not directory.is_symlink(), 'analyst_directory_symlink')
        require(expected_owner is None, 'replacement_analyst_directory_missing')
        return result
    info = directory.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid(), 'analyst_directory_type_or_owner_changed')
    reports, indices = {}, {}
    for path in sorted(directory.rglob('*')):
        info = path.lstat()
        require(not stat.S_ISLNK(info.st_mode), 'analyst_storage_symlink_requires_review')
        if stat.S_ISDIR(info.st_mode):
            continue
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid(), 'analyst_storage_type_or_owner_changed')
        relative = str(path.relative_to(directory))
        result['files'].append({'relativePath': relative, 'bytes': info.st_size, 'sha256': sha(path)})
        if path.suffix == '.json' and path.parent.name in ('reports', 'requests'):
            require(info.st_size <= 1024 * 1024, 'analyst_saved_json_exceeds_bound')
            try:
                value = json.loads(path.read_text())
            except (ValueError, UnicodeError):
                raise Blocked('analyst_saved_json_invalid') from None
            require(isinstance(value, dict), 'analyst_saved_json_invalid')
            if path.parent.name == 'reports':
                require(value.get('reportId') == path.stem and re.fullmatch(r'[a-f0-9-]{36}', path.stem), 'analyst_saved_report_identity_invalid')
                require(value.get('status') in {'ready', 'rejected', 'failed', 'interrupted', 'queued', 'running'}, 'analyst_saved_report_status_invalid')
                if value['status'] in {'queued', 'running'}:
                    result['pendingReports'] += 1
                reports[path.stem] = value
            else:
                indices[path.stem] = value
    require(result['pendingReports'] == 0, 'analyst_unfinished_reports_require_review')
    for identifier, report in reports.items():
        request = report.get('request')
        require(isinstance(request, dict) and isinstance(request.get('requestId'), str), 'analyst_saved_request_invalid')
        request_key = hashlib.sha256(json.dumps(request['requestId'], sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        require(request_key in indices and indices[request_key].get('reportId') == identifier, 'analyst_missing_request_index_requires_review')
    for value in indices.values():
        require(value.get('reportId') in reports and isinstance(value.get('fingerprint'), str) and re.fullmatch(r'[a-f0-9]{64}', value['fingerprint']), 'analyst_invalid_request_index_requires_review')
    result['reportCount'] = len(reports)
    lock = directory / 'worker.lock'
    if lock.exists():
        info = lock.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid(), 'analyst_lock_type_or_owner_changed')
        key = (os.major(info.st_dev), os.minor(info.st_dev), info.st_ino)
        for line in Path('/proc/locks').read_text().splitlines():
            parts = line.split()
            if len(parts) < 6 or '->' in parts:
                continue
            try:
                major, minor, inode = parts[5].split(':')
                observed = (int(major, 16), int(minor, 16), int(inode))
            except (ValueError, IndexError):
                continue
            if observed == key:
                require(parts[4].isdigit(), 'analyst_lock_owner_unresolved')
                result['lockOwners'].append(int(parts[4]))
    if expected_owner is None:
        require(not result['lockOwners'], 'analyst_worker_lock_already_owned')
    else:
        require(result['lockOwners'] == [expected_owner], 'replacement_analyst_worker_not_owned')
    return result


def backup_file_manifest(manifest, destination):
    """Copy the exact inspected evidence/analyst files privately without changing originals."""
    source = Path(manifest.get('directory', manifest.get('path')))
    target = private_directory(destination)
    files = []
    for entry in manifest['files']:
        relative = Path(entry['relativePath'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'backup_relative_path_invalid')
        original = source / relative
        copied = target / relative
        copied.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(original, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            metadata = os.fstat(descriptor)
            require(stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.getuid(), 'backup_source_type_or_owner_changed')
            require(metadata.st_size == entry['bytes'], 'backup_source_size_changed')
            output_descriptor = os.open(copied, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(output_descriptor, 'wb') as output:
                observed = hashlib.sha256()
                byte_count = 0
                while True:
                    block = os.read(descriptor, 1024 * 1024)
                    if not block:
                        break
                    observed.update(block)
                    byte_count += len(block)
                    require(byte_count <= entry['bytes'], 'backup_source_grew_during_read')
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
            require(byte_count == entry['bytes'] and observed.hexdigest() == entry['sha256'], 'backup_source_content_changed')
            require(sha(copied) == entry['sha256'], 'retained_file_backup_mismatch')
            files.append({'relativePath': str(relative), 'bytes': byte_count, 'sha256': observed.hexdigest()})
        finally:
            os.close(descriptor)
    return {'source': str(source), 'directory': str(target), 'fileCount': len(files),
            'files': files, 'createdAt': timestamp(), 'mode': 'private 0700 directories and 0600 files',
            'originalsModified': False, 'retainedWithoutFurtherWrites': True}


def verify_file_backup(backup):
    for entry in backup['files']:
        path = Path(backup['directory']) / entry['relativePath']
        regular_owned(path, private=True)
        require(path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256'], 'retained_file_backup_changed')
