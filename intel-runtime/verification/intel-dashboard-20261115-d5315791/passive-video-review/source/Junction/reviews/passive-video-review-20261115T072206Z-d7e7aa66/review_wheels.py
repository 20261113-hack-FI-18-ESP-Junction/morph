"""Review exact downloaded wheel metadata and file RECORD hashes; install nothing."""
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from email.parser import BytesParser
import base64
import csv
import hashlib
import io
import json
import stat
import zipfile

REVIEW = Path(__file__).resolve().parent
expected = {'websockets': '17.4', 'pillow': '13.0.0'}
results = []
for path in sorted((REVIEW / 'wheels').glob('*.whl')):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names))
        file_names = set()
        directories = []
        for info in archive.infolist():
            relative = PurePosixPath(info.filename)
            assert not relative.is_absolute() and '..' not in relative.parts
            assert not stat.S_ISLNK(info.external_attr >> 16)
            if info.is_dir():
                assert info.file_size == 0
                directories.append(info.filename)
            else:
                file_names.add(info.filename)
        metadata_names = [name for name in names if name.endswith('.dist-info/METADATA')]
        wheel_names = [name for name in names if name.endswith('.dist-info/WHEEL')]
        record_names = [name for name in names if name.endswith('.dist-info/RECORD')]
        assert len(metadata_names) == len(wheel_names) == len(record_names) == 1
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
        wheel = BytesParser().parsebytes(archive.read(wheel_names[0]))
        normalized_name = metadata['Name'].lower()
        assert expected[normalized_name] == metadata['Version']
        entries = set()
        for entry, digest, size in csv.reader(io.StringIO(archive.read(record_names[0]).decode())):
            assert entry in file_names and entry not in entries
            content = archive.read(entry)
            if digest:
                algorithm, value = digest.split('=', 1)
                assert algorithm == 'sha256'
                measured = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b'=').decode()
                assert measured == value and str(len(content)) == size
            else:
                assert entry == record_names[0] and not size
            entries.add(entry)
        assert entries == file_names
        requires = metadata.get_all('Requires-Dist', [])
        assert all('extra ==' in value for value in requires)
        hooks = [name for name in file_names if '.data/scripts/' in name
                 or name.endswith('.pth') or name.endswith('entry_points.txt')]
        if normalized_name == 'websockets':
            assert hooks == ['websockets-17.4.dist-info/entry_points.txt']
            assert archive.read(hooks[0]).decode() == '[console_scripts]\nwebsockets = websockets.cli:main\n'
        else:
            assert not hooks
        results.append({
            'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'bytes': path.stat().st_size, 'name': metadata['Name'], 'version': metadata['Version'],
            'requiresPython': metadata['Requires-Python'], 'requiresDist': requires,
            'wheelTags': wheel.get_all('Tag'), 'wheelVersion': wheel['Wheel-Version'],
            'buildBackendExecuted': False, 'recordFileHashesVerified': True,
            'memberCount': len(names), 'hashedFileCount': len(entries) - 1,
            'emptyDirectoryEntries': directories, 'entryPoints': hooks,
            'entryPointContent': {name: archive.read(name).decode() for name in hooks},
            'entryPointsExecuted': False,
        })
assert len(results) == 2
result = {
    'status': 'wheel_metadata_and_record_hashes_reviewed',
    'observedAt': datetime.now(timezone.utc).isoformat(),
    'downloadOnly': True, 'exactPinnedRequirements': expected, 'wheels': results,
    'priorReviewAttempt': {
        'outcome': 'review_script_assertion_before_installation',
        'reason': 'The first read-only check counted empty ZIP directory entries as RECORD files. '
                  'Wheel RECORD lists files; this review checks every non-directory member and separately validates empty directories.',
        'packageOrTestChanges': False,
    },
}
destination = REVIEW / 'wheel-review.json'
with destination.open('x') as handle:
    json.dump(result, handle, indent=2)
    handle.write('\n')
print(json.dumps(result, indent=2))
