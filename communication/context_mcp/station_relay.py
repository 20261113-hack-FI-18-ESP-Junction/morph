"""Bounded relay for station reads and explicit audited review/analysis requests.

This transport stores short-lived response bytes, never canonical robot records.
Only an opted-in worker can claim the two allowed record/analysis POST routes.
Robot commands, lifecycle operations and camera capture remain unavailable.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
from uuid import UUID, uuid4

MAX_BODY = 4 * 1024 * 1024
MAX_CHUNK = 60_000
MAX_PARTS = 94
REQUEST_TTL = 30
MAX_ACTIVE = 128
MAX_REQUEST_BODY = 65_536
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}\Z")
MIME_TYPES = {'application/json', 'text/event-stream', 'text/csv', 'text/plain',
              'image/png', 'image/jpeg', 'image/webp', 'application/octet-stream'}

def identifier(value: str) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value) or value in {'.', '..'}:
        raise ValueError('Invalid station, worker or record identifier')
    return value

def aware(value: str) -> datetime:
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError('Timestamp must include its timezone')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timestamp must include its timezone')
    return result

def iso(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat()

def read_target(path: str, query: dict) -> tuple[str, dict]:
    if not isinstance(path, str) or len(path) > 300 or any(c in path for c in '%?#\\\r\n'):
        raise ValueError('Only explicit Station GET paths are permitted')
    fixed = {
        '/api/v1/schema': set(), '/api/v1/station/snapshot': {'sessionId'},
        '/api/v1/sessions': set(), '/api/v1/metrics': {'includeSimulation'},
        '/api/v1/cameras': set(), '/api/v1/events': {'after', 'once', 'limit'},
        '/api/v1/analysis/context': {'kind', 'sessionIds', 'cycleId', 'sourceMode',
            'comparisonSpecId', 'baselineSessionId', 'adaptiveSessionId'},
        '/api/v1/analysis/reports': {'sessionId', 'cycleId', 'limit'},
        '/api/v1/cycles': {'sessionId', 'objectId', 'outcome', 'sourceMode', 'includeSimulation',
            'hasRetry', 'errorCode', 'modelId', 'referenceStatus', 'startedAfter', 'startedBefore',
            'offset', 'limit'},
    }
    allowed = fixed.get(path)
    if allowed is None:
        match = re.fullmatch(r'/api/v1/sessions/([^/]+)/(metrics|export)', path)
        if match:
            identifier(match[1])
            allowed = {'includeSimulation'} if match[2] == 'metrics' else {'format'}
        else:
            match = re.fullmatch(r'/api/v1/(cycles|evidence|analysis/reports)/([^/]+)', path)
            if not match:
                raise ValueError('This path is outside the Station read allowlist')
            identifier(match[2])
            allowed = set()
    if not isinstance(query, dict) or set(query) - allowed:
        raise ValueError('Unsupported Station query parameter')
    clean = {}
    for key, value in query.items():
        if key == 'sessionIds':
            values = value if isinstance(value, list) else [value]
            if not 1 <= len(values) <= 2:
                raise ValueError('Analysis requires one or two session identifiers')
            clean[key] = [identifier(item) for item in values]
            continue
        if not isinstance(value, str) or len(value) > 300 or any(ord(c) < 32 for c in value):
            raise ValueError('Query values must be bounded plain strings')
        clean[key] = value
    for key in {'limit', 'offset', 'after'} & clean.keys():
        if not re.fullmatch(r'\d{1,12}', clean[key]):
            raise ValueError('Invalid integer query parameter')
        if key == 'limit' and not 1 <= int(clean[key]) <= 1000:
            raise ValueError('Invalid query limit')
    if 'format' in clean and clean['format'] not in {'json', 'csv'}:
        raise ValueError('Only JSON and CSV exports are permitted')
    if path == '/api/v1/events':
        clean['once'] = 'true'
        clean['limit'] = str(min(int(clean.get('limit', '100')), 500))
    return path, clean


def request_target(method, path, query=None, body=None, intent=None):
    """Validate the transport envelope; Intel retains full domain validation."""
    query = {} if query is None else query
    if not isinstance(query, dict) or not isinstance(path, str):
        raise ValueError('Request path and query have invalid types')
    if method == 'GET':
        if body is not None or intent is not None:
            raise ValueError('GET requests cannot contain write data')
        path, query = read_target(path, query)
        return path, query, None, None
    if method != 'POST' or query:
        raise ValueError('Only explicit record/analysis POST requests are allowed')
    if path == '/api/v1/analysis/reports':
        expected_intent, required_ids = 'evidence-analysis', ('requestId',)
    else:
        match = re.fullmatch(r'/api/v1/cycles/([^/]+)/review', path or '')
        if not match:
            raise ValueError('Station write path is not allowed')
        identifier(match[1])
        expected_intent, required_ids = 'record-review', ('id', 'eventId')
    if intent != expected_intent:
        raise ValueError('The matching explicit write intent is required')
    try:
        encoded_body = body.encode('utf-8') if isinstance(body, str) else None
    except UnicodeError as error:
        raise ValueError('Invalid UTF-8 request body') from error
    if encoded_body is None or len(encoded_body) > MAX_REQUEST_BODY:
        raise ValueError('A bounded UTF-8 JSON request body is required')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON keys are not allowed')
            result[key] = value
        return result
    def invalid_constant(_):
        raise ValueError('Non-finite JSON numbers are not allowed')
    try:
        value = json.loads(body, object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (ValueError, RecursionError) as error:
        raise ValueError('Invalid JSON request body') from error
    if not isinstance(value, dict):
        raise ValueError('The request body must be a JSON object')
    for key in required_ids:
        identifier(value.get(key))
    return path, {}, body, intent


class StationRelay:
    def __init__(self, root: Path, clock=time.time):
        self.root = Path(root).resolve()
        self.db_path = self.root / '.junction-setup/context-share/station-relay.sqlite3'
        self.clock = clock

    @contextmanager
    def db(self):
        current = self.root
        for part in self.db_path.relative_to(self.root).parts:
            current = current / part
            if current.is_symlink():
                raise ValueError('Relay storage may not follow symlinks')
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        self.db_path.chmod(0o600)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('''CREATE TABLE IF NOT EXISTS reads (
                request_id TEXT PRIMARY KEY, station_id TEXT NOT NULL, path TEXT NOT NULL,
                query TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL,
                worker_id TEXT, claim_id TEXT, metadata TEXT, body_base64 TEXT, completed REAL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS parts (
                request_id TEXT NOT NULL REFERENCES reads(request_id) ON DELETE CASCADE,
                part_index INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY(request_id,part_index))''')
            db.execute('BEGIN IMMEDIATE')
            columns = {row[1] for row in db.execute('PRAGMA table_info(reads)')}
            for column, declaration in {'method': "TEXT NOT NULL DEFAULT 'GET'",
                    'request_body': 'TEXT', 'intent': 'TEXT', 'request_body_sha256': 'TEXT'}.items():
                if column not in columns:
                    db.execute(f'ALTER TABLE reads ADD COLUMN {column} {declaration}')
            # Expired responses cannot be served as fresh. Release their bytes promptly.
            now = self.clock()
            db.execute('DELETE FROM parts WHERE request_id IN (SELECT request_id FROM reads WHERE expires<=?)', (now,))
            db.execute("UPDATE reads SET state='expired',body_base64=NULL,request_body=NULL WHERE expires<=?", (now,))
            db.execute('DELETE FROM reads WHERE created<?', (now - 3600,))
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def row(db, station_id, request_id):
        identifier(station_id)
        request_id = str(UUID(request_id))
        row = db.execute('SELECT * FROM reads WHERE request_id=? AND station_id=?',
                         (request_id, station_id)).fetchone()
        if row is None:
            raise ValueError('Unknown station read request')
        return row

    @staticmethod
    def state(row):
        return {'request_id': row['request_id'], 'state': row['state'], 'expires_at': iso(row['expires'])}

    def enqueue(self, station_id, request_id, path, query=None):
        return self.enqueue_request(station_id, request_id, 'GET', path, query)

    def enqueue_request(self, station_id, request_id, method, path, query=None, body=None, intent=None):
        identifier(station_id)
        request_id = str(UUID(request_id))
        path, query, body, intent = request_target(method, path, query, body, intent)
        raw = json.dumps(query, sort_keys=True, separators=(',', ':'))
        body_hash = hashlib.sha256(body.encode()).hexdigest() if body is not None else None
        with self.db() as db:
            existing = db.execute('SELECT * FROM reads WHERE request_id=?', (request_id,)).fetchone()
            if existing:
                if (existing['station_id'], existing['path'], existing['query'], existing['method'],
                        existing['intent'], existing['request_body_sha256']) != (station_id, path, raw, method, intent, body_hash):
                    raise ValueError('Request UUID already has different content')
                return self.state(existing)
            if db.execute("SELECT COUNT(*) FROM reads WHERE state!='expired'").fetchone()[0] >= MAX_ACTIVE:
                raise ValueError('Station read queue is full; retry later')
            now = self.clock()
            db.execute('''INSERT INTO reads(request_id,station_id,path,query,state,created,expires,
                method,request_body,intent,request_body_sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                (request_id, station_id, path, raw, 'queued', now, now + REQUEST_TTL, method, body, intent, body_hash))
            return self.state(self.row(db, station_id, request_id))

    def claim(self, station_id, worker_id, limit=8, supports_writes=False):
        identifier(station_id)
        identifier(worker_id)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 16:
            raise ValueError('Claim limit must be 1 to 16')
        if type(supports_writes) is not bool:
            raise ValueError('Worker write capability must be explicit')
        with self.db() as db:
            rows = db.execute("SELECT * FROM reads WHERE station_id=? AND state='queued' AND (method='GET' OR ?) ORDER BY created,request_id LIMIT ?",
                              (station_id, supports_writes, limit)).fetchall()
            result = []
            for row in rows:
                claim_id = str(uuid4())
                db.execute("UPDATE reads SET state='claimed',worker_id=?,claim_id=? WHERE request_id=?",
                           (worker_id, claim_id, row['request_id']))
                item = {'request_id': row['request_id'], 'path': row['path'],
                    'query': json.loads(row['query']), 'claim_id': claim_id, 'expires_at': iso(row['expires'])}
                if supports_writes:
                    item.update(method=row['method'], body=row['request_body'], intent=row['intent'])
                result.append(item)
            return {'requests': result, 'checked_at': iso(self.clock())}

    def submit(self, station_id, request_id, worker_id, claim_id, part_index, part_count,
               status_code, content_type, body_base64, response_sha256, captured_at):
        identifier(worker_id)
        claim_id = str(UUID(claim_id))
        if (not isinstance(part_index, int) or isinstance(part_index, bool)
                or not isinstance(part_count, int) or isinstance(part_count, bool)
                or not 1 <= part_count <= MAX_PARTS or not 0 <= part_index < part_count):
            raise ValueError('Invalid response part numbers')
        if not isinstance(body_base64, str) or len(body_base64) > MAX_CHUNK:
            raise ValueError('Response part exceeds transport limit')
        try:
            base64.b64decode(body_base64, validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError('Invalid base64 response part') from error
        if not isinstance(status_code, int) or isinstance(status_code, bool) or not 200 <= status_code <= 599 or 300 <= status_code <= 399:
            raise ValueError('Invalid response status; redirects must not be relayed')
        if not isinstance(content_type, str) or len(content_type) > 150 or any(ord(c) < 32 or ord(c) == 127 for c in content_type) or content_type.split(';')[0].strip().lower() not in MIME_TYPES:
            raise ValueError('Unsupported response media type')
        if not isinstance(response_sha256, str) or not re.fullmatch('[a-f0-9]{64}', response_sha256):
            raise ValueError('Invalid response digest')
        captured = aware(captured_at).timestamp()
        if captured > self.clock() + 10:
            raise ValueError('Response timestamp is in the future')
        metadata = json.dumps({'part_count': part_count, 'status_code': status_code,
            'content_type': content_type, 'response_sha256': response_sha256,
            'captured_at': captured_at}, sort_keys=True)
        with self.db() as db:
            row = self.row(db, station_id, request_id)
            if row['state'] not in {'claimed', 'ready'}:
                raise ValueError('Read is not claimed or has expired')
            if row['worker_id'] != worker_id or row['claim_id'] != claim_id:
                raise ValueError('Response does not match the active claim')
            if captured < row['created'] - 5:
                raise ValueError('Response predates this read request')
            if row['metadata'] is not None and row['metadata'] != metadata:
                raise ValueError('Response metadata changed between parts')
            old = db.execute('SELECT body FROM parts WHERE request_id=? AND part_index=?', (request_id, part_index)).fetchone()
            if old and old[0] != body_base64:
                raise ValueError('Response part conflicts with an existing part')
            if not old:
                db.execute('INSERT INTO parts VALUES(?,?,?)', (request_id, part_index, body_base64))
            db.execute('UPDATE reads SET metadata=? WHERE request_id=?', (metadata, request_id))
            parts = db.execute('SELECT part_index,body FROM parts WHERE request_id=? ORDER BY part_index', (request_id,)).fetchall()
            if len(parts) == part_count:
                encoded = ''.join(part['body'] for part in parts)
                try:
                    raw = base64.b64decode(encoded, validate=True)
                except ValueError as error:
                    raise ValueError('Response parts do not form one base64 body') from error
                if len(raw) > MAX_BODY or hashlib.sha256(raw).hexdigest() != response_sha256:
                    raise ValueError('Response bytes exceed the limit or fail SHA-256')
                if row['state'] != 'ready':
                    db.execute("UPDATE reads SET state='ready',body_base64=?,completed=? WHERE request_id=?",
                               (encoded, self.clock(), request_id))
            return self.state(self.row(db, station_id, request_id))

    def read(self, station_id, request_id, offset=0, limit=MAX_CHUNK):
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0 or not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_CHUNK:
            raise ValueError('Invalid response pagination')
        with self.db() as db:
            row = self.row(db, station_id, request_id)
            result = self.state(row)
            if row['state'] == 'ready':
                body = row['body_base64']
                if offset > len(body):
                    raise ValueError('Offset is beyond response')
                metadata = json.loads(row['metadata'])
                metadata.pop('part_count')
                result.update(metadata)
                result.update({'body_base64': body[offset:offset + limit], 'offset': offset,
                    'next_offset': offset + limit if offset + limit < len(body) else None,
                    'completed_at': iso(row['completed'])})
            return result
