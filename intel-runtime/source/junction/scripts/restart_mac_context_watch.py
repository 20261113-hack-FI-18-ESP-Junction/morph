#!/usr/bin/env python3
"""Replace only the verified Mac context watcher after a reviewed source fix."""
import json
from pathlib import Path
import signal
import subprocess
import sys
import time

from watch_mac_context import ROOT, lock_held, now, process_matches, read_json


def wait_for(predicate, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False


def main():
    directory = ROOT / "mac-sync"
    script = ROOT / "scripts/watch_mac_context.py"
    pid_file = directory / "watch.pid"
    previous = process_matches(pid_file, script)
    if previous is None:
        print(json.dumps({"error": "ExistingProcessIdentityUnverified", "changed": False}))
        return 1
    if lock_held(directory) is not True:
        print(json.dumps({"error": "ExistingWatcherLockNotHeld", "changed": False}))
        return 1
    import os
    os.kill(previous, signal.SIGTERM)
    if not wait_for(lambda: lock_held(directory) is False, 10):
        print(json.dumps({"error": "ExistingWatcherDidNotReleaseLock", "previousPid": previous}))
        return 1
    with (directory / "watcher.log").open("ab") as log:
        child = subprocess.Popen(
            [sys.executable, str(script), "--config", str(directory / "config.json"),
             "--watch", "--interval", "300", "--cycle-timeout", "120"],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    ready = wait_for(lambda: process_matches(pid_file, script) == child.pid
                    and lock_held(directory) is True, 5)
    if not ready:
        if child.poll() is None:
            child.terminate()
        print(json.dumps({"error": "ReplacementWatcherNotVerified", "previousPid": previous}))
        return 1
    print(json.dumps({"observedAt": now(), "previousPid": previous, "replacementPid": child.pid,
                      "identityVerified": True, "lockHeld": True, "intervalSeconds": 300,
                      "pollCompletion": "Pending; check watcher status for its completed read."}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
