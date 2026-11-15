"""Explicit deterministic simulation fixtures; never run on startup or reconnect."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import EvidenceUpload, RecordWrite
from .store import StationStore

PIXEL = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j5ioAAAAASUVORK5CYII="


def seed_demo(store: StationStore, prefix: str = "demo") -> dict:
    start = datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)

    def stamp(second):
        return (start + timedelta(seconds=second)).isoformat()

    def write(kind, record, tag="create", revision=None):
        return store.upsert(RecordWrite(eventId=f"{record['id']}:{tag}", recordType=kind,
                                        record=record, expectedRevision=revision))

    sid = f"{prefix}:session"
    write("session", {"id": sid, "name": "Morph deterministic simulation",
                     "sourceMode": "simulation", "startedAt": stamp(0),
                     "configId": f"{prefix}:config"})
    cycle_ids = []
    for index, scenario in enumerate(("good", "retry", "wrong_bin", "unverified", "in_progress")):
        offset = index * 30
        cid, oid = f"{prefix}:{scenario}", f"{prefix}:object:{index}"
        cycle_ids.append(cid)
        cycle = {"id": cid, "sessionId": sid, "objectId": oid,
                 "startedAt": stamp(offset), "outcome": "in_progress"}
        write("cycle", cycle)
        if scenario == "in_progress":
            continue
        scope = {"sessionId": sid, "cycleId": cid}
        evidence_id, frame_id = cid + ":image", cid + ":frame"
        store.put_evidence(EvidenceUpload(
            id=evidence_id, eventId=evidence_id + ":upload", **scope,
            mediaType="image/png", contentBase64=PIXEL, capturedAt=stamp(offset + 1)))
        write("frame", {"id": frame_id, **scope, "objectId": oid, "cameraId": "simulated-camera",
                        "capturedAt": stamp(offset + 1), "receivedAt": stamp(offset + 1),
                        "width": 1, "height": 1, "evidenceId": evidence_id})
        predicted = "defective" if scenario == "wrong_bin" else "good"
        inspection_count = 2 if scenario == "retry" else 1
        first_inspection = None
        for n in range(inspection_count):
            model_id, inspection_id = cid + f":model:{n}", cid + f":inspection:{n}"
            write("model_run", {"id": model_id, **scope, "provider": "simulation",
                               "modelId": "fixture-only-not-an-actual-detector",
                               "frameIds": [frame_id], "input": {"fixture": scenario},
                               "output": {"classification": predicted}, "latencyMs": 100,
                               "requestedAt": stamp(offset + 2 + n), "completedAt": stamp(offset + 2.1 + n)})
            write("inspection", {"id": inspection_id, **scope, "objectId": oid,
                                 "frameIds": [frame_id], "modelRunId": model_id, "score": 0.8 if predicted == "defective" else 0.1,
                                 "threshold": 0.5, "classification": predicted,
                                 "additionalInspectionOfId": first_inspection,
                                 "requestedAt": stamp(offset + 2 + n), "completedAt": stamp(offset + 2.1 + n)})
            first_inspection = first_inspection or inspection_id
        label_id = cid + ":reference"
        write("reference_label", {"id": label_id, **scope, "objectId": oid, "quality": "good",
                                  "authorId": "simulation-operator", "method": "Independent fixture label",
                                  "createdAt": stamp(offset + 1), "evidenceIds": [evidence_id]})
        attempts = 2 if scenario == "retry" else 1
        previous_attempt = None
        confirmation_id = None
        destination = "defective_bin" if predicted == "defective" else "good_bin"
        for n in range(attempts):
            aid = cid + f":attempt:{n + 1}"
            attempt = {"id": aid, **scope, "ordinal": n + 1, "startedAt": stamp(offset + 4 + n * 5),
                       "outcome": "in_progress", "retryOfAttemptId": previous_attempt,
                       "retryReason": "Failed grasp in simulated fixture" if previous_attempt else None}
            write("attempt", attempt)
            execution = {"id": aid + ":execution", **scope, "attemptId": aid, "taskId": "fixture_skill",
                         "policyId": "simulation-only-no-robot", "status": "finished",
                         "requestedAt": stamp(offset + 4 + n * 5),
                         "acknowledgedAt": stamp(offset + 4.1 + n * 5),
                         "finishedAt": stamp(offset + 6 + n * 5)}
            write("execution", execution)
            outcome = "failed" if scenario == "retry" and n == 0 else (
                "unverified" if scenario == "unverified" else "successful")
            if outcome == "successful":
                confirmation_id = aid + ":confirmation"
                write("confirmation", {"id": confirmation_id, **scope, "source": "operator",
                                       "authorId": "simulation-operator", "attemptId": aid,
                                       "confirmedAt": stamp(offset + 7 + n * 5),
                                       "physicalSuccess": True, "observedDestination": destination,
                                       "evidenceIds": [evidence_id]})
            write("attempt", {**attempt, "endedAt": stamp(offset + 7 + n * 5), "outcome": outcome,
                              "confirmationId": confirmation_id,
                              "errorCode": "simulated_failed_grasp" if outcome == "failed" else None}, "finish", 1)
            previous_attempt = aid
        write("cycle", {**cycle, "endedAt": stamp(offset + 20),
                        "outcome": "failed" if scenario == "wrong_bin" else (
                            "unverified" if scenario == "unverified" else "correct"),
                        "commandedDestination": destination,
                        "observedDestination": destination if confirmation_id else None,
                        "referenceLabelId": label_id, "inspectionId": inspection_id,
                        "confirmationId": confirmation_id}, "finish", 1)
    return {"sessionId": sid, "cycleIds": cycle_ids, "sourceMode": "simulation",
            "metrics": store.metrics(sid, include_simulation=True),
            "snapshot": store.snapshot(sid)}
