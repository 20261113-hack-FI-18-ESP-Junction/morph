"""Prepare-only transition guard tests; process creation and signals are forbidden."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import Mock, patch

import pytest

SCRIPT = Path(__file__).with_name('recover_reviewed_station.py')
spec = importlib.util.spec_from_file_location('reviewed_activation_preparation', SCRIPT)
activation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activation)


@pytest.mark.parametrize('arguments', [[], ['--help'], ['--activate'], ['--recover-reviewed-main-with-sigkill', '--force']])
def test_explicit_activation_gate_precedes_all_host_operations(arguments):
    with patch.object(sys, 'argv', [str(SCRIPT), *arguments]), \
         patch.object(activation, 'check_pinned_files') as pin_check, \
         patch.object(activation.subprocess, 'Popen') as spawn, \
         patch.object(activation.signal, 'pidfd_send_signal') as send_signal:
        assert activation.main() == 2
        pin_check.assert_not_called()
        spawn.assert_not_called()
        send_signal.assert_not_called()


def test_changed_reviewed_source_blocks_before_host_transition(tmp_path):
    source = tmp_path / 'reviewed.py'
    source.write_bytes(b'reviewed bytes')
    pins = {source: hashlib.sha256(source.read_bytes()).hexdigest()}
    with patch.object(activation, 'PINNED_FILES', pins):
        activation.check_pinned_files()
        source.write_bytes(b'changed bytes')
        with patch.object(sys, 'argv', [str(SCRIPT), '--recover-reviewed-main-with-sigkill']), \
             patch.object(activation.subprocess, 'Popen') as spawn, \
             patch.object(activation.signal, 'pidfd_send_signal') as send_signal:
            with pytest.raises(RuntimeError, match='reviewed_transition_source_or_evidence_changed'):
                activation.main()
            spawn.assert_not_called()
            send_signal.assert_not_called()


def test_graceful_timeout_only_waits_and_never_escalates():
    poller = Mock()
    poller.poll.return_value = []
    with patch.object(activation.select, 'poll', return_value=poller), \
         patch.object(activation.time, 'monotonic', side_effect=[0, 0, 0.01, 0.1]), \
         patch.object(activation.subprocess, 'Popen') as spawn, \
         patch.object(activation.signal, 'pidfd_send_signal') as send_signal:
        assert activation.wait_for_exit(7, 0.05) is False
        poller.register.assert_called_once_with(7, activation.select.POLLIN)
        assert poller.poll.call_count == 2
        spawn.assert_not_called()
        send_signal.assert_not_called()


def test_completed_process_wait_returns_without_another_signal():
    poller = Mock()
    poller.poll.return_value = [(7, activation.select.POLLIN)]
    with patch.object(activation.select, 'poll', return_value=poller), \
         patch.object(activation.time, 'monotonic', side_effect=[0, 0]), \
         patch.object(activation.signal, 'pidfd_send_signal') as send_signal:
        assert activation.wait_for_exit(7, 20) is True
        send_signal.assert_not_called()


def test_known_blocker_is_saved_with_explicit_code_and_no_process_operation(tmp_path):
    with patch.object(activation, 'REVIEW', tmp_path), \
         patch.object(activation.subprocess, 'Popen') as spawn, \
         patch.object(activation.signal, 'pidfd_send_signal') as send_signal:
        result = activation.save_outer_failure(activation.TransitionPrecheckError('reviewed_transition_source_or_evidence_changed'))
        saved = json.loads(Path(result['report']).read_text())
        assert saved['code'] == 'reviewed_transition_source_or_evidence_changed'
        assert saved['phase'] == 'precheck'
        assert saved['signalSent'] is False
        assert saved['replacementStarted'] is False
        assert Path(result['report']).stat().st_mode & 0o777 == 0o600
        spawn.assert_not_called()
        send_signal.assert_not_called()


def test_unrecognized_exception_values_are_not_saved(tmp_path):
    with patch.object(activation, 'REVIEW', tmp_path):
        result = activation.save_outer_failure(ValueError('Do not persist exception detail'))
    assert result['code'] == 'ValueError'
    assert 'Do not persist' not in Path(result['report']).read_text()


def test_original_and_version_two_activation_share_the_singleton_lock():
    assert activation.TRANSITION_LOCK == SCRIPT.parent.parent / 'station-transition.lock'


def test_current_source_drift_blocks_before_process_discovery(tmp_path):
    support_spec = importlib.util.spec_from_file_location('transition_guard_test', SCRIPT.with_name('station_transition_support.py'))
    support = importlib.util.module_from_spec(support_spec)
    support_spec.loader.exec_module(support)
    project = tmp_path / 'project'
    source = project / 'station/morph_station'
    source.mkdir(parents=True)
    for name in ('api.py', 'store.py', 'analysis_provider.py'):
        (source / name).write_text('reviewed\n')
    expected = hashlib.sha256(b'reviewed\n').hexdigest()
    (tmp_path / 'station-source-baseline.json').write_text(json.dumps({'preservedFiles': [
        {'path': 'station/morph_station/analysis_provider.py', 'sha256': expected}]}))
    (source / 'analysis_provider.py').write_text('new and unreviewed\n')
    with patch.object(support, 'PROJECT', project), patch.object(support, 'REVIEW', tmp_path), \
         patch.object(support, 'API_HASH', expected), patch.object(support, 'STORE_HASH', expected), \
         patch.object(support, 'process_identity') as process:
        with pytest.raises(support.Blocked, match='preserved_station_source_changed'):
            support.service_guard()
        process.assert_not_called()


def load_support():
    spec = importlib.util.spec_from_file_location('recovery_support_test', SCRIPT.with_name('station_transition_support.py'))
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    return support


def test_missing_analyst_storage_is_inspected_without_creating_it(tmp_path):
    support = load_support()
    directory = tmp_path / 'analysis'
    with patch.object(support, 'DATABASE', tmp_path / 'station.sqlite3'):
        result = support.analyst_snapshot()
    assert result['exists'] is False
    assert not directory.exists()


def test_pending_analyst_report_blocks_without_mutating_report(tmp_path):
    support = load_support()
    directory = tmp_path / 'analysis/reports'
    directory.mkdir(parents=True)
    path = directory / '00000000-0000-0000-0000-000000000001.json'
    content = json.dumps({'reportId': path.stem, 'status': 'queued'})
    path.write_text(content)
    with patch.object(support, 'DATABASE', tmp_path / 'station.sqlite3'):
        with pytest.raises(support.Blocked, match='analyst_unfinished_reports_require_review'):
            support.analyst_snapshot()
    assert path.read_text() == content
    assert not (tmp_path / 'analysis/worker.lock').exists()


def test_existing_analyst_owner_blocks_and_expected_new_owner_is_required(tmp_path):
    support = load_support()
    directory = tmp_path / 'analysis'
    directory.mkdir()
    worker_lock = directory / 'worker.lock'
    worker_lock.write_bytes(b'')
    info = worker_lock.stat()
    entry = f"1: FLOCK ADVISORY WRITE 123 {support.os.major(info.st_dev):x}:{support.os.minor(info.st_dev):x}:{info.st_ino} 0 EOF\n"
    original_read_text = Path.read_text
    def read_text(path, *args, **kwargs):
        return entry if str(path) == '/proc/locks' else original_read_text(path, *args, **kwargs)
    with patch.object(support, 'DATABASE', tmp_path / 'station.sqlite3'), patch.object(Path, 'read_text', read_text):
        with pytest.raises(support.Blocked, match='analyst_worker_lock_already_owned'):
            support.analyst_snapshot()
        assert support.analyst_snapshot(expected_owner=123)['lockOwners'] == [123]
        with pytest.raises(support.Blocked, match='replacement_analyst_worker_not_owned'):
            support.analyst_snapshot(expected_owner=124)
    assert worker_lock.read_bytes() == b''


def test_analyst_symlink_is_rejected_without_following_it(tmp_path):
    support = load_support()
    target = tmp_path / 'untouched'
    target.mkdir()
    (tmp_path / 'analysis').symlink_to(target, target_is_directory=True)
    with patch.object(support, 'DATABASE', tmp_path / 'station.sqlite3'):
        with pytest.raises(support.Blocked, match='analyst_directory_type_or_owner_changed'):
            support.analyst_snapshot()
    assert not list(target.iterdir())


def test_known_failure_after_signal_retains_state_without_another_signal(tmp_path):
    with patch.object(activation, 'REVIEW', tmp_path), \
         patch.object(activation, 'TRANSITION_STATE', {'phase': 'second_signal_exit_wait', 'signalSent': True, 'replacementStarted': False}), \
         patch.object(activation.signal, 'pidfd_send_signal') as send_signal, \
         patch.object(activation.subprocess, 'Popen') as spawn:
        result = activation.save_outer_failure(activation.TransitionPrecheckError('second_signal_exit_timeout_no_force_kill'))
    assert result['signalSent'] is True and result['replacementStarted'] is False
    send_signal.assert_not_called()
    spawn.assert_not_called()


def prior_receipts():
    return (json.loads(activation.FAILED_ACTIVATION.read_text()), json.loads(activation.FAILED_RECOVERY.read_text()))


def test_exact_two_failed_receipts_are_accepted_without_operations():
    terminated, interrupted = prior_receipts()
    with patch.object(activation.signal, 'pidfd_send_signal') as signal_call, patch.object(activation.subprocess, 'Popen') as spawn:
        activation.check_prior_shutdown_receipts(terminated, interrupted)
    signal_call.assert_not_called()
    spawn.assert_not_called()


@pytest.mark.parametrize('change', ['missing_second', 'wrong_error', 'wrong_pid', 'wrong_ticks', 'extra_signal', 'replacement', 'wrong_session'])
def test_any_changed_shutdown_history_blocks_before_host_operations(change):
    terminated, interrupted = prior_receipts()
    if change == 'missing_second':
        interrupted = {}
    elif change == 'wrong_error':
        interrupted['errorCode'] = 'graceful_shutdown_timeout_no_force_kill'
    elif change == 'wrong_pid':
        interrupted['signals'][0]['pid'] += 1
    elif change == 'wrong_ticks':
        interrupted['oldService']['startTicks'] += 1
    elif change == 'extra_signal':
        interrupted['signals'].append(dict(interrupted['signals'][0]))
    elif change == 'replacement':
        interrupted['newService'] = {'pid': 123}
    else:
        interrupted['sessionId'] = 'another-session'
    with patch.object(activation.signal, 'pidfd_send_signal') as signal_call, patch.object(activation.subprocess, 'Popen') as spawn:
        with pytest.raises(activation.TransitionPrecheckError, match='two_exact_failed_shutdown_receipts_required'):
            activation.check_prior_shutdown_receipts(terminated, interrupted)
    signal_call.assert_not_called()
    spawn.assert_not_called()


def test_private_file_backup_preserves_original_and_detects_later_copy_change(tmp_path):
    support = load_support()
    source = tmp_path / 'source'
    source.mkdir()
    original = source / 'saved.bin'
    original.write_bytes(b'actual saved bytes')
    manifest = {'directory': str(source), 'files': [{'relativePath': original.name, 'bytes': original.stat().st_size, 'sha256': hashlib.sha256(original.read_bytes()).hexdigest()}]}
    backup = support.backup_file_manifest(manifest, tmp_path / 'copy')
    support.verify_file_backup(backup)
    assert original.read_bytes() == b'actual saved bytes'
    copied = tmp_path / 'copy/saved.bin'
    assert copied.stat().st_mode & 0o777 == 0o600
    copied.write_bytes(b'changed')
    with pytest.raises(support.Blocked, match='retained_file_backup_changed'):
        support.verify_file_backup(backup)
    assert original.read_bytes() == b'actual saved bytes'


def test_changed_original_blocks_file_backup_without_rewriting_original(tmp_path):
    support = load_support()
    source = tmp_path / 'source'
    source.mkdir()
    original = source / 'saved.bin'
    original.write_bytes(b'changed')
    manifest = {'path': str(source), 'files': [{'relativePath': original.name, 'bytes': 7, 'sha256': hashlib.sha256(b'earlier').hexdigest()}]}
    with pytest.raises(support.Blocked, match='backup_source_content_changed'):
        support.backup_file_manifest(manifest, tmp_path / 'copy')
    assert original.read_bytes() == b'changed'


def test_backup_rejects_path_traversal_without_reading_external_file(tmp_path):
    support = load_support()
    source = tmp_path / 'source'
    source.mkdir()
    manifest = {'path': str(source), 'files': [{'relativePath': '../private', 'bytes': 0, 'sha256': hashlib.sha256(b'').hexdigest()}]}
    with pytest.raises(support.Blocked, match='backup_relative_path_invalid'):
        support.backup_file_manifest(manifest, tmp_path / 'copy')
    assert not (tmp_path / 'private').exists()
