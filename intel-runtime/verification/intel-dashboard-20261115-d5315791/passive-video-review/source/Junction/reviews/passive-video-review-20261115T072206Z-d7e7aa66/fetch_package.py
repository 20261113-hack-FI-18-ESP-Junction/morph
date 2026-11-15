"""Fetch the pinned passive video handoff into this review directory only.

The existing TLS-verified client performs read_context calls only. Every page,
whole-file hash and manifest byte count is checked before an immutable write.
No application source, service, hardware or coordination event is modified.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import sys

REVIEW = Path(__file__).resolve().parent
ROOT = Path('/home/intel/Documents/Junction')
REPORTING = ROOT / 'reviews/intel-dashboard-20261115T052333Z-d5315791/reporting.py'
PACKAGE = 'context/coordination/live-video-20261115-d7e7aa66-1470-4587-a2f9-5a37dadc7da6'
NOTE = 'context/notes/d7e7aa66-1470-4587-a2f9-5a37dadc7da6.json'
PINS = {
    NOTE: '623b8c971f2d6edfecefd2ad964793118554fc0c6f7e0c845b41133892ea9c97',
    PACKAGE + '/README.md': 'b42883a6fa825f44b967e761a2401985ceee9380e41d62b3fdccb2980b3f3263',
    PACKAGE + '/MANIFEST.json': '56d265d92dda855578ea94468b46481ea5e9213ed0b7349b5b2455f1f9b2dc72',
}


def now():
    return datetime.now(timezone.utc).isoformat()


def check(condition, code):
    if not condition:
        raise RuntimeError(code)


def relative_path(value):
    check(isinstance(value, str), 'path_type_invalid')
    path = PurePosixPath(value)
    check(not path.is_absolute() and '..' not in path.parts and str(path) == value,
          'path_invalid')
    return path


def write_once(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists():
        check(path.is_file() and not path.is_symlink() and path.read_bytes() == raw,
              'immutable_review_file_conflict')
        return
    with path.open('xb') as handle:
        handle.write(raw)
    path.chmod(0o600)


def save_json(path, data):
    write_once(path, (json.dumps(data, indent=2, ensure_ascii=False) + '\n').encode())


def fetch(client, shared_path, expected_hash, expected_bytes=None, target_path=None):
    relative = relative_path(shared_path)
    check(re.fullmatch(r'[0-9a-f]{64}', expected_hash) is not None, 'pin_invalid')
    offset, chunks, pages = 0, [], []
    total = None
    while True:
        result = client.call('read_context', path=shared_path, offset=offset, limit=24000)
        check(result.get('path') == shared_path and result.get('offset') == offset,
              'response_identity_mismatch')
        check(result.get('redacted') is False and isinstance(result.get('content'), str),
              'redacted_or_nontext_response')
        check(type(result.get('total_characters')) is int
              and 0 <= result['total_characters'] <= 2_000_000, 'size_invalid')
        if total is None:
            total = result['total_characters']
        check(result['total_characters'] == total, 'size_changed_between_pages')
        check(result.get('sha256') == expected_hash, 'advertised_hash_mismatch')
        content = result['content']
        check(len(content) <= 24000 and offset + len(content) <= total, 'page_size_invalid')
        following = result.get('next_offset')
        if following is None:
            check(offset + len(content) == total, 'last_page_incomplete')
        else:
            check(type(following) is int and following == offset + len(content)
                  and following > offset, 'pagination_invalid')
        pages.append({key: result[key] for key in (
            'path', 'offset', 'next_offset', 'total_characters', 'sha256', 'redacted')})
        chunks.append(content)
        if following is None:
            break
        offset = following
    text = ''.join(chunks)
    raw = text.encode('utf-8')
    check(len(text) == total and hashlib.sha256(raw).hexdigest() == expected_hash,
          'full_content_hash_mismatch')
    check(expected_bytes is None or len(raw) == expected_bytes, 'manifest_byte_count_mismatch')
    original = REVIEW / 'incoming' / relative
    write_once(original, raw)
    if target_path is not None:
        write_once(REVIEW / 'payload' / relative_path(target_path), raw)
    receipt = {
        'path': shared_path, 'targetPath': target_path, 'localPath': str(original),
        'sha256': expected_hash, 'bytes': len(raw), 'pageCount': len(pages), 'pages': pages,
        'readAt': now(), 'server': client.server_name, 'tlsVerification': True,
        'fullContentHashVerified': True, 'expectedHashCompared': True,
        'manifestByteCountCompared': expected_bytes is not None,
        'readOnlyTool': 'read_context', 'interpreter': sys.executable,
    }
    receipt_path = REVIEW / 'readbacks' / (hashlib.sha256(shared_path.encode()).hexdigest() + '.json')
    if receipt_path.exists():
        existing = json.loads(receipt_path.read_text())
        check(all(existing.get(key) == receipt[key] for key in (
            'path', 'targetPath', 'sha256', 'bytes', 'pages', 'fullContentHashVerified')),
              'prior_receipt_conflict')
    else:
        save_json(receipt_path, receipt)
    return receipt, text


def main():
    started = now()
    spec = importlib.util.spec_from_file_location('video_review_existing_reporting', REPORTING)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    client = module.load_client()
    receipts, documents = [], {}
    for shared_path, digest in PINS.items():
        receipt, content = fetch(client, shared_path, digest)
        receipts.append(receipt)
        documents[shared_path] = content
    manifest = json.loads(documents[PACKAGE + '/MANIFEST.json'])
    check(manifest['noteId'] == NOTE.rsplit('/', 1)[1][:-5], 'manifest_identity_mismatch')
    check(manifest['readmeSHA256'] == PINS[PACKAGE + '/README.md'], 'readme_pin_mismatch')
    check(manifest['mode'] == 'passive-source-handoff'
          and manifest['receiverRestartAuthorized'] is False
          and manifest['hardwareVerified'] is False, 'manifest_scope_changed')
    entries = manifest['files']
    check(len(entries) == 60 and sum(item['bytes'] for item in entries) == 679156,
          'manifest_inventory_mismatch')
    targets, shared_paths = set(), set()
    for entry in entries:
        target = str(relative_path(entry['targetPath']))
        shared = str(relative_path(entry['sharedPath']))
        check(target not in targets and shared not in shared_paths, 'duplicate_manifest_path')
        targets.add(target)
        shared_paths.add(shared)
        check(shared.startswith(PACKAGE + '/files/'), 'shared_path_outside_package')
        check(entry['role'] in {'intel-new-package', 'mac-reference'}, 'unknown_file_role')
        expected_prefix = 'intel-runtime/media-bridge/' if entry['role'] == 'intel-new-package' else 'klemen-dashboard/'
        check(target.startswith(expected_prefix), 'target_role_mismatch')
        check(type(entry['bytes']) is int and 0 <= entry['bytes'] <= 2_000_000,
              'manifest_bytes_invalid')
    for index, entry in enumerate(entries, 1):
        receipt, _ = fetch(client, entry['sharedPath'], entry['sha256'],
                           entry['bytes'], entry['targetPath'])
        receipt['role'] = entry['role']
        receipts.append(receipt)
        if index % 5 == 0 or index == len(entries):
            print(json.dumps({'verifiedPayloadFiles': index, 'total': len(entries),
                              'latestTargetPath': entry['targetPath']}), flush=True)
    result = {
        'status': 'all_package_files_received_and_hash_verified',
        'startedAt': started, 'completedAt': now(),
        'agent': '/root/adoption_receiver_review', 'designatedReporter': '/root',
        'requestId': manifest['noteId'],
        'sessionId': 'd0dc73a7-df82-48e6-a8c1-8a4c23c144e6',
        'manifestPath': PACKAGE + '/MANIFEST.json', 'manifestSHA256': PINS[PACKAGE + '/MANIFEST.json'],
        'payloadFiles': len(entries), 'payloadBytes': sum(item['bytes'] for item in entries),
        'roles': {role: sum(item['role'] == role for item in entries)
                  for role in ('intel-new-package', 'mac-reference')},
        'allReadPages': sum(item['pageCount'] for item in receipts),
        'reviewOnly': True, 'activeSourceFilesChanged': [], 'servicesStarted': False,
        'hardwareAccessed': False, 'providerCalls': 0, 'coordinationEventsCreated': 0,
        'files': receipts,
    }
    save_json(REVIEW / 'package-verification.json', result)
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        failure = {'status': 'failed_closed', 'observedAt': now(), 'errorType': type(error).__name__,
                   'errorCode': str(error)[:240], 'reviewOnly': True}
        save_json(REVIEW / ('fetch-failure-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json'), failure)
        raise SystemExit(json.dumps(failure)) from None
