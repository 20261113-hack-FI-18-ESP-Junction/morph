"""Read installed metadata and public source; never import LeRobot or open hardware."""
from __future__ import annotations

from datetime import datetime, timezone
from email.parser import Parser
import hashlib
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
PROJECT = Path('/home/intel/project-morph/morph-robot/morph-robot-lerobot')
STUDIO = Path('/home/intel/project-morph/morph-ai/morph-physical-ai-studio')
ENVIRONMENTS = [PROJECT / '.venv', STUDIO / 'application/backend/.venv']
SOURCES = [
    'scripts/lerobot_teleoperate.py', 'configs/parser.py', 'utils/import_utils.py',
    'robots/so_follower/config_so_follower.py', 'robots/so_follower/so_follower.py',
    'teleoperators/so_leader/config_so_leader.py', 'teleoperators/so_leader/so_leader.py',
    'robots/robot.py', 'teleoperators/teleoperator.py', 'motors/motors_bus.py',
]


def file_identity(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def main():
    records = []
    for environment in ENVIRONMENTS:
        site = next(environment.glob('lib/python*/site-packages'))
        distributions = []
        plugins = []
        for path in site.glob('*.dist-info/METADATA'):
            metadata = Parser().parsestr(path.read_text())
            name = metadata.get('Name', '')
            if name.startswith(('lerobot_robot_', 'lerobot_camera_', 'lerobot_teleoperator_',
                                'lerobot_policy_', 'lerobot_env_', 'lerobot_strategy_')):
                plugins.append(name)
            if name.lower() in {'lerobot', 'torch', 'draccus', 'physicalai', 'physicalai-studio'}:
                item = {'name': name, 'version': metadata.get('Version'), **file_identity(path)}
                if name.lower() == 'lerobot':
                    entrypoints = path.parent / 'entry_points.txt'
                    item['entryPointFile'] = file_identity(entrypoints)
                    item['teleoperateEntryPoint'] = next(line for line in entrypoints.read_text().splitlines()
                                                        if line.startswith('lerobot-teleoperate = '))
                distributions.append(item)
        argv = [str(environment / 'bin/python'), '-I', '-B', '-S', '-c',
                'import json,sys;print(json.dumps({"version":sys.version.split()[0],"executable":sys.executable}))']
        response = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        assert response.returncode == 0
        record = {'environment': str(environment), 'sitePackages': str(site),
                  'python': json.loads(response.stdout), 'versionCheckArgv': argv,
                  'versionCheckExit': response.returncode, 'packages': distributions,
                  'thirdPartyPluginDiscoveryMatches': plugins,
                  'entryPointExecutable': file_identity(environment / 'bin/lerobot-teleoperate'),
                  'activationFile': file_identity(environment / 'bin/activate'),
                  'environmentConfiguration': file_identity(environment / 'pyvenv.cfg')}
        if environment == ENVIRONMENTS[0]:
            record['reviewedSources'] = [file_identity(site / 'lerobot' / path) for path in SOURCES]
        records.append(record)
    configs = []
    allowed = {'type', 'port', 'id', 'calibration_dir', 'use_degrees', 'max_relative_target',
               'disable_torque_on_disconnect', 'cameras'}
    for name in ['follower-lerobot-config.json', 'leader-lerobot-config.json']:
        path = PROJECT / '.runtime' / name
        config = json.loads(path.read_text())
        configs.append({**file_identity(path), 'selectedPublicFields': {key: value for key, value in config.items() if key in allowed}})
    result = {'observedAt': datetime.now(timezone.utc).isoformat(), 'agent': '/root/dashboard',
              'classification': 'installed_metadata_and_static_source_audit', 'environments': records,
              'existingPublicConfigurations': configs, 'hardwareAccessPerformed': False,
              'installedEnvironmentModified': False, 'authenticationOrPrivateConfigurationRead': False}
    path = OUT / 'installed-environments.json'
    with path.open('x') as handle:
        handle.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'evidence': str(path), 'environments': len(records), 'sourceFiles': len(SOURCES),
                      'versions': [{item['name']: item['version'] for item in record['packages']} for record in records]}, indent=2))


if __name__ == '__main__':
    main()
