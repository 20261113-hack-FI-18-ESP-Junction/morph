#!/usr/bin/env python3.12
"""Explicit last-resort unclean termination recovery; preparation never executes it.

Requires the root operator's explicit --recover-reviewed-main-with-sigkill invocation.
Only the pinned Station with exact failed SIGTERM and SIGINT receipts can receive one SIGKILL through its Linux pidfd.
SIGKILL performs no graceful cleanup. There is no automatic rollback, database restore, seed or provider call.
The worker, watcher, dashboard, Studio and isolated analyst service are preserved.
"""
from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
REVIEW = Path(__file__).resolve().parent
TRANSITION_LOCK = REVIEW.parent / 'station-transition.lock'
ROOT = Path('/home/intel/Documents/Junction')
PROJECT = ROOT / 'morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/HachingJunction'
V2 = REVIEW.parent / 'transition-v2-20261115T062955Z'
FAILED_ACTIVATION = V2 / 'station-activation-20261115T063626791124Z/activation-result.json'
V3 = REVIEW.parent / 'transition-v3-20261115T064221Z'
FAILED_RECOVERY = V3 / 'station-recovery-20261115T065637391817Z/recovery-result.json'
PINNED_FILES = {
    REVIEW / 'station_transition_support.py': '8787c662f65587c52ee1fcc668ccc74b7b5bfb26f01d0b788edca7e5e80f9005',
    REVIEW / 'station-source-baseline.json': '2539160b6d175b29c08d02c912e5cc9615747bd3be96bec7b8f408b9f1456b15',
    V2 / 'station-preflight-result.json': '8bf315699146ff0af2cf9f368cb2c1da2733f516f143c6871088601e5767d6d2',
    ROOT / 'reviews/intel-adoption-20261115T051202Z-b71f04ec/station-worker-launch.json': '7a5d14a38edac739627b9ea37522d95545893dd4f86e5e8732f12b0ccdc3cc77',
    PROJECT / 'station/morph_station/__main__.py': 'a01ca16760d38fa1fa1b1bb9f7e67b33eea6290ec799c8149b54551aaa5a7298',
    FAILED_RECOVERY: '81c52d35518014a4df46e71249257ec2874fbcd13969edcd4abc9208e1c97fd1',
    FAILED_ACTIVATION: 'b932305ad9f79bcec2f562e3bbb6b524321e6fa812d2e58a150140814f2d7eb1',
    REVIEW.parent / 'shutdown-fix-20261115T064128Z/result.json': 'cdd483244f61f665fd0b0d0a95ae0f701ddbd7757507ceffda6bca4a27e7c855',
    PROJECT / 'station/morph_station/__init__.py': '84252541a785fd57f879d4878d54bd8af19b803849d1ad438b60ed1738235399',
}
TRANSITION_STATE = {'phase': 'precheck', 'signalSent': False, 'replacementStarted': False}


class TransitionPrecheckError(RuntimeError):
    """A fixed reason for rejection before importing reviewed support code."""


def safe_error_code(error):
    support = sys.modules.get('station_transition_support')
    is_reviewed_error = isinstance(error, TransitionPrecheckError) or (
        support is not None and isinstance(error, support.Blocked))
    code = str(error) if is_reviewed_error else type(error).__name__
    return code if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,119}', code) else 'unexpected_error_detail_redacted'


def save_outer_failure(error):
    """Retain a new private failure receipt without exception values or credentials."""
    report = {'status': 'blocked', 'code': safe_error_code(error),
              'observedAt': datetime.now(timezone.utc).isoformat(),
              'mainActivationCompleted': False, **TRANSITION_STATE}
    path = REVIEW / ('activation-precheck-failure-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())
    return {**report, 'report': str(path)}


def check_pinned_files():
    for path, expected in PINNED_FILES.items():
        if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise TransitionPrecheckError('reviewed_transition_source_or_evidence_changed')


def check_prior_shutdown_receipts(terminated, interrupted):
    """Reject any history except the pinned old process's two failed shutdown attempts."""
    for receipt, expected_signal, expected_error in (
            (terminated, 'SIGTERM', 'graceful_shutdown_timeout_no_force_kill'),
            (interrupted, 'SIGINT', 'second_signal_exit_timeout_no_force_kill')):
        try:
            valid = (receipt['status'] == 'failed' and receipt['errorCode'] == expected_error
                     and receipt['requestId'] == 'd5315791-6749-4b01-97b5-1b9357306487'
                     and receipt['sessionId'] == 'd0dc73a7-df82-48e6-a8c1-8a4c23c144e6'
                     and len(receipt['signals']) == 1
                     and receipt['signals'][0]['signal'] == expected_signal
                     and receipt['signals'][0]['pid'] == 188282
                     and receipt['signals'][0]['startTicks'] == 10907663
                     and receipt['oldService']['pid'] == 188282
                     and receipt['oldService']['startTicks'] == 10907663
                     and receipt.get('replacementReturnCode') is None
                     and 'newService' not in receipt and not receipt['requests'])
        except (KeyError, TypeError, IndexError):
            valid = False
        if not valid:
            raise TransitionPrecheckError('two_exact_failed_shutdown_receipts_required')


def wait_for_exit(pidfd, timeout):
    """Wait only; timeout never escalates the signal."""
    events = select.poll()
    events.register(pidfd, select.POLLIN)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if events.poll(100):
            return True
    return False


def main():
    if sys.argv[1:] != ['--recover-reviewed-main-with-sigkill']:
        print(json.dumps({'status': 'blocked', 'code': 'explicit_root_activation_invocation_required'}))
        return 2
    check_pinned_files()
    from station_transition_support import (
        DATABASE, EVIDENCE, PYTHON, SERVICE_PID, SERVICE_TICKS, TOKEN, Blocked,
        analyst_snapshot, backup_file_manifest, verify_file_backup, draining_service_guard, owned_draining_connections,
        consistent_backup, direct_get, evidence_manifest, ledger_summary,
        main_port_listening, owns_main_socket, preserved_guard, private_directory,
        private_json, process_identity, require, same_canonical, service_guard, sha, source_guard, timestamp,
    )
    os.umask(0o077)
    require(Path(sys.executable).resolve() == PYTHON.resolve(), 'existing_station_interpreter_required')
    require(hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'), 'linux_pidfd_support_required')
    preflight = json.loads((V2 / 'station-preflight-result.json').read_text())
    failed = json.loads(FAILED_ACTIVATION.read_text())
    interrupted = json.loads(FAILED_RECOVERY.read_text())
    check_prior_shutdown_receipts(failed, interrupted)
    require(preflight['status'] == 'passed', 'passed_copy_preflight_required')
    require(sha(Path(preflight['backup']['path'])) == preflight['backup']['sha256'], 'retained_preflight_backup_changed')
    lock_descriptor = os.open(TRANSITION_LOCK, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_descriptor, 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Blocked('another_station_transition_is_active') from None
        identity, environment, preserved = draining_service_guard()
        TRANSITION_STATE['phase'] = 'guarded_backup'
        run = private_directory(REVIEW / ('station-recovery-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')))
        report = {'requestId': 'd5315791-6749-4b01-97b5-1b9357306487',
                  'sessionId': 'd0dc73a7-df82-48e6-a8c1-8a4c23c144e6',
                  'preparedBy': '/root/adoption_receiver_review', 'executionAuthority': 'Root operator invocation',
                  'startedAt': timestamp(), 'oldService': identity,
                  'preservedProcessesBefore': preserved, 'signals': [], 'requests': [],
                  'priorFailedActivation': str(FAILED_ACTIVATION), 'priorFailedRecovery': str(FAILED_RECOVERY),
                  'uncleanTerminationRisk': 'SIGKILL immediately terminates the old API without graceful cleanup. Active requests and uncommitted work may be lost; in-progress filesystem writes may be incomplete. Private backups preserve the observed pre-kill state; final committed data is checked without restoring or claiming unfinished work succeeded.',
                  'environmentPersisted': False, 'credentialValueOrHashPersisted': False,
                  'providerFlagsChanged': False, 'seedOrRestorePerformed': False,
                  'runDirectory': str(run)}
        child = None
        try:
            analyst_before = analyst_snapshot()
            private_json(run / 'analyst-before-stop.json', analyst_before)
            analyst_backup = backup_file_manifest(analyst_before, run / 'analyst-private-backup')
            private_json(run / 'analyst-backup-manifest.json', analyst_backup)
            canonical_before = ledger_summary(DATABASE)
            evidence_before = evidence_manifest()
            private_json(run / 'canonical-before-stop.json', canonical_before)
            private_json(run / 'evidence-before-stop.json', evidence_before)
            evidence_backup = backup_file_manifest(evidence_before, run / 'evidence-private-backup')
            private_json(run / 'evidence-backup-manifest.json', evidence_backup)
            report.update(analystBackup=analyst_backup, evidenceBackup=evidence_backup)
            before_backup = consistent_backup(DATABASE, run / 'before-stop-immutable.sqlite3')
            require(same_canonical(ledger_summary(Path(before_backup['path']), immutable=True), canonical_before),
                    'canonical_records_changed_before_backup_completed')
            report['beforeStopBackup'] = before_backup
            current_identity, current_environment, current_preserved = draining_service_guard()
            require(current_identity == identity and current_environment == environment,
                    'station_identity_or_environment_changed_before_transition')
            require(current_preserved == preserved, 'preserved_process_changed_before_transition')
            require(analyst_snapshot() == analyst_before, 'analyst_storage_changed_before_signal')
            require(ledger_summary(DATABASE) == canonical_before and evidence_manifest() == evidence_before, 'canonical_or_evidence_changed_before_signal')
            verify_file_backup(analyst_backup)
            verify_file_backup(evidence_backup)
            check_pinned_files()
            pidfd = os.pidfd_open(SERVICE_PID, 0)
            try:
                # Recheck after acquiring a stable process reference. PID reuse
                # cannot cause this signal to reach another process.
                process_identity(SERVICE_PID, SERVICE_TICKS)
                require(not main_port_listening(), 'listener_returned_before_recovery_signal')
                connections = owned_draining_connections(SERVICE_PID)
                private_json(run / 'ready-to-signal.json', {
                    'observedAt': timestamp(), 'pid': SERVICE_PID, 'startTicks': SERVICE_TICKS,
                    'signal': 'SIGKILL', 'timeoutSeconds': 10, 'forceKillAllowed': True,
                    'uncleanTermination': True, 'priorSigintReceipt': str(FAILED_RECOVERY),
                    'priorSigtermReceipt': str(FAILED_ACTIVATION), 'ownedConnections': connections,
                    'backup': before_backup, 'lastEventSequence': canonical_before['lastEventSequence']})
                signal.pidfd_send_signal(pidfd, signal.SIGKILL, None, 0)
                TRANSITION_STATE.update(phase='unclean_kill_exit_wait', signalSent=True)
                report['signals'].append({'pid': SERVICE_PID, 'startTicks': SERVICE_TICKS,
                                          'signal': 'SIGKILL', 'sentAt': timestamp()})
                require(wait_for_exit(pidfd, 10), 'sigkill_exit_timeout_no_further_signal')
            finally:
                os.close(pidfd)
            require(not main_port_listening(), 'port_8000_still_in_use_no_replacement_started')
            # A request accepted before the earlier SIGTERM may have committed
            # before this explicit unclean termination. Preserve that final state; never restore an
            # earlier backup or misattribute it to replacement startup.
            canonical_final = ledger_summary(DATABASE)
            evidence_final = evidence_manifest()
            private_json(run / 'canonical-final-before-start.json', canonical_final)
            private_json(run / 'evidence-final-before-start.json', evidence_final)
            final_backup = consistent_backup(DATABASE, run / 'final-before-start-immutable.sqlite3')
            require(same_canonical(ledger_summary(Path(final_backup['path']), immutable=True), canonical_final),
                    'canonical_records_changed_during_final_backup')
            report.update(finalBeforeStartBackup=final_backup,
                          canonicalChangedDuringUncleanTermination=canonical_final != canonical_before,
                          evidenceChangedDuringUncleanTermination=evidence_final != evidence_before,
                          finalBeforeStartEventSequence=canonical_final['lastEventSequence'])
            require(preserved_guard() == preserved, 'preserved_process_changed_during_shutdown')
            check_pinned_files()
            source_guard()
            require(analyst_snapshot() == analyst_before, 'analyst_storage_changed_during_shutdown')
            require(not main_port_listening(), 'port_8000_rebound_before_replacement')
            log_path = run / 'station-private.log'
            log_descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            # Preserve every actual old argument, the exact working directory
            # and environment values in memory. No provider/credential flag is
            # added, removed, replaced or recorded in the report.
            with os.fdopen(log_descriptor, 'wb', buffering=0) as output:
                child = subprocess.Popen(identity['argv'], cwd=identity['cwd'], env=environment,
                                         stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                         close_fds=True, start_new_session=True)
            TRANSITION_STATE.update(phase='replacement_checks', replacementStarted=True)
            new_identity = process_identity(child.pid)
            report.update(newService=new_identity, privateLogPath=str(log_path),
                          environmentPreservedInMemory=True, originalArgumentsPreserved=True)
            private_json(run / 'replacement-started.json', {
                'observedAt': timestamp(), 'newService': new_identity, 'privateLogPath': str(log_path),
                'originalArgumentsPreserved': True, 'originalEnvironmentPreserved': True})
            token = TOKEN.read_text().strip()
            ready = False
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                require(child.poll() is None, 'replacement_exited_during_startup')
                if owns_main_socket(child.pid):
                    try:
                        health = direct_get('/health', token)
                        ready = health['status'] == 200 and health.get('health', {}).get('dashboardRead', {}).get('path') == '/api/v1/dashboard'
                    except (OSError, ValueError):
                        ready = False
                    if ready:
                        report['requests'].append(health)
                        break
                time.sleep(0.1)
            require(ready, 'replacement_readiness_timeout')
            for path in ('/openapi.json', '/api/v1/schema', '/api/v1/dashboard?sourceMode=live',
                         '/api/v1/dashboard?sourceMode=simulation', '/api/v1/analysis/reports'):
                response = direct_get(path, token)
                report['requests'].append(response)
                require(response['status'] == 200, 'replacement_required_get_failed')
                if path == '/openapi.json':
                    require(response['dashboardPresent'] and response['analystPresent'], 'replacement_routes_missing')
                if path.startswith('/api/v1/dashboard'):
                    require(response['lastEventSequence'] == canonical_final['lastEventSequence'], 'replacement_event_cursor_changed')
            observed_identity, observed_environment, observed_preserved = service_guard(child.pid, new_identity['startTicks'])
            require(observed_environment == environment, 'replacement_environment_mismatch')
            require(observed_preserved == preserved, 'preserved_process_changed_after_startup')
            analyst_after = analyst_snapshot(expected_owner=child.pid)
            private_json(run / 'analyst-after-start.json', analyst_after)
            require(analyst_after['reportCount'] == analyst_before['reportCount'], 'analyst_reports_changed_after_startup')
            require([entry for entry in analyst_after['files'] if entry['relativePath'] != 'worker.lock'] == [entry for entry in analyst_before['files'] if entry['relativePath'] != 'worker.lock'], 'analyst_saved_evidence_changed_after_startup')
            canonical_after = ledger_summary(DATABASE)
            evidence_after = evidence_manifest()
            private_json(run / 'canonical-after-start.json', canonical_after)
            private_json(run / 'evidence-after-start.json', evidence_after)
            require(canonical_after == canonical_final, 'canonical_records_or_schema_changed_after_startup')
            require(evidence_after == evidence_final, 'evidence_files_changed_after_startup')
            require(sha(Path(before_backup['path'])) == before_backup['sha256'], 'before_stop_backup_changed')
            require(sha(Path(final_backup['path'])) == final_backup['sha256'], 'final_backup_changed')
            verify_file_backup(analyst_backup)
            verify_file_backup(evidence_backup)
            report.update(status='passed', completedAt=timestamp(), newService=observed_identity,
                          preservedProcessesAfter=observed_preserved, canonicalRecordsUnchangedAfterStartup=True,
                          evidenceUnchangedAfterStartup=True, providerRequestsIssuedByTransition=0, physicalVerification=False,
                          sharedMcpRoundtripVerified=False,
                          nextAction='Root must verify the actual new dashboard and saved image read through the existing Intel worker and shared Mac MCP.')
        except Exception as error:
            report.update(status='failed', completedAt=timestamp(),
                          errorCode=str(error) if isinstance(error, Blocked) else type(error).__name__,
                          replacementReturnCode=child.poll() if child is not None else None,
                          recoveryPolicy='No additional signal, database restore or automatic rollback. Preserve all processes, backups and failure evidence for root review.')
            private_json(run / 'recovery-result.json', report)
            print(json.dumps({'status': 'failed', 'code': report['errorCode'],
                              'report': str(run / 'recovery-result.json'),
                              'replacementPid': child.pid if child is not None else None}))
            return 1
        private_json(run / 'recovery-result.json', report)
        TRANSITION_STATE['phase'] = 'completed'
        print(json.dumps({'status': report['status'], 'report': str(run / 'recovery-result.json'),
                          'reportSha256': sha(run / 'recovery-result.json'),
                          'newService': report['newService'], 'lastEventSequence': canonical_after['lastEventSequence'],
                          'canonicalAndEvidencePreserved': True, 'sharedMcpRoundtripVerified': False}, indent=2))
        return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        try:
            failure = save_outer_failure(error)
        except Exception:
            failure = {'status': 'blocked', 'code': safe_error_code(error),
                       'failureReceiptSaved': False, 'mainActivationCompleted': False, **TRANSITION_STATE}
        print(json.dumps(failure))
        raise SystemExit(2) from None
