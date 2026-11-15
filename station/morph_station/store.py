"""Transactional records and evidence for Morph. No robot control or provider calls."""
from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import MODELS, CorrectionRequest, EvidenceUpload, RecordWrite

SCHEMA_VERSION = 1
ALL_KINDS = set(MODELS) | {"correction"}
MUTABLE = {
    "session": {"name", "endedAt"},
    "cycle": {"outcome", "endedAt", "commandedDestination", "observedDestination",
              "referenceLabelId", "inspectionId", "confirmationId"},
    "attempt": {"outcome", "endedAt", "errorCode", "confirmationId"},
    "execution": {"status", "acknowledgedAt", "finishedAt", "error"},
    "model_run": {"completedAt", "output", "error", "latencyMs"},
    "utterance": {"text", "completedAt", "status"},
}
CORRECTABLE = {
    "session": {"name"},
    "cycle": {"outcome", "commandedDestination", "observedDestination",
              "referenceLabelId", "inspectionId", "confirmationId"},
    "attempt": {"outcome", "confirmationId", "errorCode"},
    "reference_label": {"quality", "method"},
}
SECRET_KEYS = {"apikey", "authorization", "password", "secret", "accesstoken",
               "refreshtoken", "privatekey"}


class StoreError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code, self.detail = status_code, detail
        super().__init__(detail)


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def reject_secrets(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            if "".join(c for c in key.lower() if c.isalnum()) in SECRET_KEYS:
                raise StoreError(422, "Credential fields must be redacted before recording")
            reject_secrets(child)
    elif isinstance(value, list):
        for child in value:
            reject_secrets(child)


def without_revision(value: dict) -> dict:
    return {k: v for k, v in value.items() if k != "revision"}


def ratio(n: int, d: int, definition: str, filters: dict) -> dict:
    return {"numerator": n, "denominator": d, "value": n / d if d else None,
            "definition": definition, "filters": filters}


class StationStore:
    def __init__(self, db_path: str | Path, evidence_dir: str | Path | None = None):
        if str(db_path) == ":memory:":
            raise ValueError("Use a file path: persistence requires a real SQLite database")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.evidence_dir = Path(evidence_dir) if evidence_dir else self.db_path.parent / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.db_path, timeout=15, isolation_level=None)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(Path(__file__).with_name("schema.sql").read_text())
            versions = [r[0] for r in db.execute("SELECT version FROM schema_migrations")]
            if any(v > SCHEMA_VERSION for v in versions):
                raise StoreError(409, "Database schema is newer than this application")
            db.execute("INSERT OR IGNORE INTO schema_migrations VALUES (?, ?)", (SCHEMA_VERSION, now()))
        finally:
            db.close()

    @contextmanager
    def _connection(self, write: bool = False):
        db = sqlite3.connect(self.db_path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=15000")
        try:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _kind(kind: str):
        if kind not in ALL_KINDS:
            raise StoreError(422, "Unknown record type")

    @staticmethod
    def _row_record(row) -> dict:
        return {**json.loads(row["payload"]), "revision": row["revision"]}

    def _get(self, db, kind: str, record_id: str) -> dict:
        self._kind(kind)
        row = db.execute("SELECT * FROM records WHERE kind=? AND id=?", (kind, record_id)).fetchone()
        if not row:
            raise StoreError(404, f"{kind} record not found: {record_id}")
        return self._row_record(row)

    def get(self, record_type: str, record_id: str) -> dict:
        with self._connection() as db:
            return self._get(db, record_type, record_id)

    def _list(self, db, kind: str, session_id=None, cycle_id=None):
        self._kind(kind)
        sql, args = "SELECT * FROM records WHERE kind=?", [kind]
        if session_id is not None:
            sql += " AND session_id=?"
            args.append(session_id)
        if cycle_id is not None:
            sql += " AND cycle_id=?"
            args.append(cycle_id)
        rows = db.execute(sql + " ORDER BY rowid", args).fetchall()
        return [self._row_record(row) for row in rows]

    def list_records(self, record_type: str, session_id=None, cycle_id=None) -> list[dict]:
        with self._connection() as db:
            return self._list(db, record_type, session_id, cycle_id)

    def _normalize(self, kind: str, record: dict) -> dict:
        self._kind(kind)
        reject_secrets(record)
        try:
            return MODELS[kind].model_validate(without_revision(record)).model_dump(mode="json")
        except ValidationError as exc:
            # Do not echo arbitrary request values or accidentally retain credentials.
            errors = [{"loc": e["loc"], "message": e["msg"]} for e in exc.errors(include_input=False)]
            raise StoreError(422, f"Invalid {kind}: {canonical(errors)}") from exc

    def _ref(self, db, kind: str, ident: str | None, record: dict, object_match=False):
        if ident is None:
            return None
        ref = self._get(db, kind, ident)
        session_id = record["id"] if isinstance(record, dict) and "sourceMode" in record else record["sessionId"]
        if ref.get("sessionId", ref.get("id") if kind == "session" else None) != session_id:
            raise StoreError(409, f"{kind} reference belongs to another session")
        if record.get("cycleId") and ref.get("cycleId", ref.get("id") if kind == "cycle" else None) != record["cycleId"]:
            raise StoreError(409, f"{kind} reference belongs to another cycle")
        if object_match and record.get("objectId") != ref.get("objectId"):
            raise StoreError(409, "Reference belongs to another object")
        return ref

    def _validate(self, db, kind: str, r: dict, old: dict | None = None, correcting=False):
        if kind == "session":
            if r["endedAt"] is not None:
                unresolved = [c["id"] for c in self._list(db, "cycle", r["id"])
                              if c["outcome"] == "in_progress"]
                if unresolved:
                    raise StoreError(409, "Session contains unresolved cycles: " + ", ".join(unresolved))
            return

        session = self._get(db, "session", r["sessionId"])
        if old is None and kind in ("cycle", "attempt", "execution", "utterance") and session["endedAt"]:
            raise StoreError(409, "Cannot start new work in an ended session")
        cycle_id = r["id"] if kind == "cycle" else r.get("cycleId")
        cycle = r if kind == "cycle" else (
            self._ref(db, "cycle", cycle_id, r, object_match="objectId" in r) if cycle_id else None)
        if kind != "cycle" and cycle and kind in ("attempt", "execution") and old is None:
            if cycle["outcome"] != "in_progress":
                raise StoreError(409, "Cannot start an attempt or execution in a finished cycle")

        scoped = {**r, "cycleId": cycle_id}
        if kind == "cycle":
            for key, refkind in (("referenceLabelId", "reference_label"),
                                 ("inspectionId", "inspection"), ("confirmationId", "confirmation")):
                self._ref(db, refkind, r[key], scoped,
                          object_match=refkind in ("reference_label", "inspection"))
            attempts = self._list(db, "attempt", r["sessionId"], r["id"])
            if r["outcome"] != "in_progress" and any(a["outcome"] == "in_progress" for a in attempts):
                raise StoreError(409, "Finish or explicitly mark unresolved attempts before ending the cycle")
            if r["outcome"] == "correct":
                self._correct_cycle(db, r, attempts)
            return

        if kind == "attempt":
            existing = [a for a in self._list(db, "attempt", r["sessionId"], r["cycleId"]) if a["id"] != r["id"]]
            if any(a["ordinal"] == r["ordinal"] for a in existing):
                raise StoreError(409, "Attempt ordinal is already used in this cycle")
            if old is None and r["ordinal"] != len(existing) + 1:
                raise StoreError(409, "Attempts must have consecutive ordinals")
            if r["retryOfAttemptId"]:
                previous = self._ref(db, "attempt", r["retryOfAttemptId"], r)
                if previous["ordinal"] != r["ordinal"] - 1 or previous["outcome"] == "in_progress":
                    raise StoreError(409, "Retry must follow the previous finished attempt")
            confirmation = self._ref(db, "confirmation", r["confirmationId"], r)
            if r["outcome"] == "successful":
                if not confirmation or not confirmation["physicalSuccess"]:
                    raise StoreError(409, "Successful physical attempt requires confirmation")
                if confirmation.get("attemptId") != r["id"]:
                    raise StoreError(409, "Attempt confirmation must identify this attempt")
            return

        if kind == "frame":
            evidence = self._ref(db, "evidence", r["evidenceId"], r)
            if not evidence["mediaType"].startswith("image/"):
                raise StoreError(409, "Frame must reference image evidence")
        elif kind == "inspection":
            for ident in r["frameIds"]:
                self._ref(db, "frame", ident, r, object_match=True)
            model = self._ref(db, "model_run", r["modelRunId"], r)
            if not set(r["frameIds"]).issubset(set(model["frameIds"])):
                raise StoreError(409, "Inspection frames must belong to the recorded model input")
            if r["additionalInspectionOfId"]:
                self._ref(db, "inspection", r["additionalInspectionOfId"], r, object_match=True)
            self._ref(db, "evidence", r["mapEvidenceId"], r)
        elif kind in ("model_run", "decision"):
            for ident in r["frameIds"]:
                self._ref(db, "frame", ident, r)
            if kind == "decision":
                self._ref(db, "model_run", r["modelRunId"], r)
        elif kind == "reference_label":
            for ident in r["evidenceIds"]:
                self._ref(db, "evidence", ident, r)
        elif kind == "confirmation":
            for ident in r["evidenceIds"]:
                self._ref(db, "evidence", ident, r)
            self._ref(db, "attempt", r["attemptId"], r)
        elif kind == "execution":
            self._ref(db, "attempt", r["attemptId"], r)
            self._ref(db, "decision", r["decisionId"], r)

    def _correct_cycle(self, db, cycle: dict, attempts=None):
        scoped = {**cycle, "cycleId": cycle["id"]}
        label = self._ref(db, "reference_label", cycle["referenceLabelId"], scoped, object_match=True)
        inspection = self._ref(db, "inspection", cycle["inspectionId"], scoped, object_match=True)
        confirmation = self._ref(db, "confirmation", cycle["confirmationId"], scoped)
        if not label or not inspection or not confirmation or not confirmation["physicalSuccess"]:
            raise StoreError(409, "Correct cycle requires independent label, decision inspection and physical confirmation")
        expected = "good_bin" if label["quality"] == "good" else "defective_bin"
        if (inspection["classification"] != label["quality"] or
            cycle["commandedDestination"] != expected or cycle["observedDestination"] != expected or
            confirmation["observedDestination"] != expected):
            raise StoreError(409, "Prediction, reference and actual destination do not establish a correct cycle")
        attempts = attempts if attempts is not None else self._list(db, "attempt", cycle["sessionId"], cycle["id"])
        if not attempts or max(attempts, key=lambda a: a["ordinal"])["outcome"] != "successful":
            raise StoreError(409, "Correct cycle requires the latest physical attempt to be confirmed successful")
        last = max(attempts, key=lambda a: a["ordinal"])
        if confirmation.get("attemptId") != last["id"]:
            raise StoreError(409, "Cycle confirmation must identify the successful final attempt")

    def _validate_finished_dependents(self, db, session_id: str, cycle_id: str | None):
        if not cycle_id:
            return
        cycle = self._get(db, "cycle", cycle_id)
        if cycle["outcome"] == "correct":
            self._correct_cycle(db, cycle)
        if cycle["outcome"] != "in_progress":
            attempts = self._list(db, "attempt", session_id, cycle_id)
            if any(a["outcome"] == "in_progress" for a in attempts):
                raise StoreError(409, "Correction would reopen an attempt in a finished cycle")

    @staticmethod
    def _event(row) -> dict:
        return {
            "sequence": row["sequence"], "eventId": row["event_id"],
            "type": f"{row['kind']}.{row['operation']}", "recordType": row["kind"],
            "entityId": row["entity_id"], "entityRevision": row["revision"],
            "sessionId": row["session_id"], "cycleId": row["cycle_id"],
            "sourceMode": row["source_mode"], "occurredAt": row["occurred_at"],
            "receivedAt": row["received_at"], "payload": json.loads(row["payload"]),
        }

    def _receipt(self, db, event_id: str, fp: str):
        row = db.execute("SELECT * FROM request_receipts WHERE event_id=?", (event_id,)).fetchone()
        if row:
            if row["fingerprint"] != fp:
                raise StoreError(409, "Event ID was already used for a different request")
            return {**json.loads(row["response"]), "duplicate": True}
        if db.execute("SELECT 1 FROM events WHERE event_id=?", (event_id,)).fetchone():
            raise StoreError(409, "Event ID is already reserved by another operation")
        return None

    @staticmethod
    def _save_receipt(db, event_id: str, fp: str, response: dict):
        db.execute("INSERT INTO request_receipts VALUES (?,?,?)", (event_id, fp, canonical(response)))

    def _persist(self, db, kind, record, revision, event_id, fp, operation, occurred_at=None):
        sid = record["id"] if kind == "session" else record["sessionId"]
        cid = record["id"] if kind == "cycle" else record.get("cycleId")
        db.execute(
            "INSERT INTO records VALUES (?,?,?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET "
            "revision=excluded.revision,payload=excluded.payload",
            (kind, record["id"], sid, cid, revision, canonical(record)),
        )
        mode = record["sourceMode"] if kind == "session" else self._get(db, "session", sid)["sourceMode"]
        db.execute(
            "INSERT INTO events(event_id,fingerprint,kind,entity_id,session_id,cycle_id,revision,"
            "occurred_at,received_at,source_mode,operation,payload) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (event_id, fp, kind, record["id"], sid, cid, revision, occurred_at or now(), now(),
             mode, operation, canonical(record)),
        )
        db.execute("INSERT INTO revisions VALUES (?,?,?,?,?)",
                   (kind, record["id"], revision, event_id, canonical(record)))
        event = self._event(db.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone())
        return {"recordType": kind, "record": {**record, "revision": revision}, "event": event, "duplicate": False}

    def upsert(self, write: RecordWrite) -> dict:
        if not isinstance(write, RecordWrite):
            write = RecordWrite.model_validate(write)
        record = self._normalize(write.recordType, write.record)
        request = {**write.model_dump(mode="json"), "record": record}
        fp = fingerprint(request)
        with self._connection(write=True) as db:
            prior = self._receipt(db, write.eventId, fp)
            if prior:
                return prior
            row = db.execute("SELECT * FROM records WHERE kind=? AND id=?",
                             (write.recordType, record["id"])).fetchone()
            old = self._row_record(row) if row else None
            if old and without_revision(old) == record:
                eventrow = db.execute("SELECT * FROM events WHERE kind=? AND entity_id=? ORDER BY sequence DESC LIMIT 1",
                                      (write.recordType, record["id"])).fetchone()
                result = {"recordType": write.recordType, "record": old,
                          "event": self._event(eventrow), "duplicate": True}
                self._save_receipt(db, write.eventId, fp, result)
                return result
            if old:
                if write.expectedRevision != old["revision"]:
                    raise StoreError(409, "Stale or missing expectedRevision")
                changed = {k for k in record if record[k] != old.get(k)}
                if not changed.issubset(MUTABLE.get(write.recordType, set())):
                    raise StoreError(409, "Immutable record fields cannot be overwritten")
                if write.recordType in ("cycle", "attempt") and old["outcome"] not in ("in_progress", "unverified"):
                    raise StoreError(409, "A finished result requires an audited correction")
                if write.recordType == "utterance" and old["status"] != "partial":
                    raise StoreError(409, "Finalized utterance cannot be emitted or changed again")
                if write.recordType == "model_run" and old["completedAt"] is not None:
                    raise StoreError(409, "Completed model output is immutable")
                if write.recordType == "execution" and old["status"] in ("finished", "failed"):
                    raise StoreError(409, "Finished execution is immutable")
            elif write.expectedRevision is not None:
                raise StoreError(409, "New record cannot specify expectedRevision")
            self._validate(db, write.recordType, record, old)
            result = self._persist(db, write.recordType, record, old["revision"] + 1 if old else 1,
                                   write.eventId, fp, "updated" if old else "created",
                                   write.occurredAt.isoformat() if write.occurredAt else None)
            if write.recordType != "session":
                self._validate_finished_dependents(db, record["sessionId"],
                                                  record["id"] if write.recordType == "cycle" else record.get("cycleId"))
            self._save_receipt(db, write.eventId, fp, result)
            return result

    def end_session(self, session_id, event_id, ended_at, expected_revision):
        record = without_revision(self.get("session", session_id))
        record["endedAt"] = ended_at
        return self.upsert(RecordWrite(eventId=event_id, recordType="session", record=record,
                                       expectedRevision=expected_revision))

    def correct(self, request: CorrectionRequest) -> dict:
        if not isinstance(request, CorrectionRequest):
            request = CorrectionRequest.model_validate(request)
        payload = request.model_dump(mode="json")
        reject_secrets(payload)
        fp = fingerprint(payload)
        with self._connection(write=True) as db:
            previous = self._receipt(db, request.eventId, fp)
            if previous:
                return previous
            if db.execute("SELECT 1 FROM records WHERE kind='correction' AND id=?", (request.id,)).fetchone():
                raise StoreError(409, "Correction ID is already used")
            current = self._get(db, request.entityType, request.entityId)
            if current["revision"] != request.expectedRevision:
                raise StoreError(409, "Stale correction revision")
            if request.field not in CORRECTABLE[request.entityType]:
                raise StoreError(422, "This field cannot be manually corrected")
            if current.get(request.field) != request.previousValue:
                raise StoreError(409, "Previous value does not match the saved record")
            if request.previousValue == request.newValue:
                raise StoreError(422, "Correction must change a value")
            changed = {**without_revision(current), request.field: request.newValue}
            changed = self._normalize(request.entityType, changed)
            self._validate(db, request.entityType, changed, current, correcting=True)
            # Target revision and correction evidence commit together; each has a distinct event ID.
            target_event = request.eventId + ":target"
            if (len(target_event) > 140
                or db.execute("SELECT 1 FROM events WHERE event_id=?", (target_event,)).fetchone()
                or db.execute("SELECT 1 FROM request_receipts WHERE event_id=?", (target_event,)).fetchone()):
                raise StoreError(409, "Correction target event ID collision")
            target = self._persist(db, request.entityType, changed, current["revision"] + 1,
                                   target_event, fp, "corrected", payload["createdAt"])
            sid = current["id"] if request.entityType == "session" else current["sessionId"]
            cid = current["id"] if request.entityType == "cycle" else current.get("cycleId")
            correction = {**payload, "sessionId": sid, "cycleId": cid,
                          "previousRevision": current["revision"], "newRevision": current["revision"] + 1}
            saved = self._persist(db, "correction", correction, 1, request.eventId, fp, "created", payload["createdAt"])
            self._validate_finished_dependents(db, sid, cid)
            result = {"correction": saved["record"], "record": target["record"],
                      "event": saved["event"], "duplicate": False}
            self._save_receipt(db, request.eventId, fp, result)
            return result

    def put_evidence(self, request: EvidenceUpload) -> dict:
        if not isinstance(request, EvidenceUpload):
            request = EvidenceUpload.model_validate(request)
        try:
            content = base64.b64decode(request.contentBase64, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise StoreError(422, "Evidence must be valid base64") from exc
        if not content or len(content) > 5 * 1024 * 1024:
            raise StoreError(413, "Evidence must contain 1 byte to 5 MiB")
        if request.mediaType == "image/png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise StoreError(422, "PNG signature does not match")
        if request.mediaType == "image/jpeg" and not content.startswith(b"\xff\xd8\xff"):
            raise StoreError(422, "JPEG signature does not match")
        if request.mediaType in ("text/plain", "application/json"):
            try:
                text = content.decode("utf-8")
                if request.mediaType == "application/json":
                    reject_secrets(json.loads(text))
            except (UnicodeError, ValueError) as exc:
                raise StoreError(422, "Evidence must be valid UTF-8/JSON") from exc
        digest = hashlib.sha256(content).hexdigest()
        record = self._normalize("evidence", {
            "id": request.id, "sessionId": request.sessionId, "cycleId": request.cycleId,
            "mediaType": request.mediaType, "sha256": digest, "size": len(content),
            "capturedAt": request.capturedAt,
        })
        fp = fingerprint(record)
        with self._connection(write=True) as db:
            prior = self._receipt(db, request.eventId, fp)
            if prior:
                return prior
            oldrow = db.execute("SELECT * FROM records WHERE kind='evidence' AND id=?", (request.id,)).fetchone()
            if oldrow:
                if without_revision(self._row_record(oldrow)) != record:
                    raise StoreError(409, "Evidence ID is immutable")
                eventrow = db.execute("SELECT * FROM events WHERE kind='evidence' AND entity_id=? ORDER BY sequence DESC LIMIT 1",
                                      (request.id,)).fetchone()
                result = {"recordType": "evidence", "record": self._row_record(oldrow),
                          "event": self._event(eventrow), "duplicate": True}
                self._save_receipt(db, request.eventId, fp, result)
                return result
            self._validate(db, "evidence", record)
            path = self.evidence_dir / digest
            try:
                with path.open("xb") as target:
                    target.write(content)
            except FileExistsError:
                if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    raise StoreError(409, "Existing evidence file failed integrity validation")
            result = self._persist(db, "evidence", record, 1, request.eventId, fp, "created",
                                   request.capturedAt.isoformat())
            self._save_receipt(db, request.eventId, fp, result)
            return result

    def evidence_file(self, evidence_id: str):
        evidence = self.get("evidence", evidence_id)
        path = self.evidence_dir / evidence["sha256"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != evidence["sha256"]:
            raise StoreError(409, "Evidence is missing or failed integrity validation")
        return path, evidence["mediaType"]

    def events(self, after: int = 0, limit: int = 100) -> list[dict]:
        if after < 0 or not 1 <= limit <= 1000:
            raise StoreError(422, "Invalid event cursor or limit")
        with self._connection() as db:
            latest = db.execute("SELECT COALESCE(MAX(sequence),0) FROM events").fetchone()[0]
            if after > latest:
                raise StoreError(409, "Event cursor is ahead of this station; reload the snapshot")
            return [self._event(row) for row in db.execute(
                "SELECT * FROM events WHERE sequence>? ORDER BY sequence LIMIT ?", (after, limit))]

    def latest_sequence(self):
        with self._connection() as db:
            return db.execute("SELECT COALESCE(MAX(sequence),0) FROM events").fetchone()[0]

    def _cycle_detail(self, db, cycle_id):
        cycle = self._get(db, "cycle", cycle_id)
        names = {"attempt": "attempts", "frame": "frames", "inspection": "inspections",
                 "model_run": "modelRuns", "utterance": "utterances", "decision": "decisions",
                 "execution": "executions", "reference_label": "referenceLabels",
                 "confirmation": "confirmations", "correction": "corrections", "evidence": "evidence"}
        detail = {"cycle": cycle}
        for kind, key in names.items():
            detail[key] = self._list(db, kind, cycle["sessionId"], cycle_id)
        detail["events"] = [self._event(row) for row in db.execute(
            "SELECT * FROM events WHERE cycle_id=? ORDER BY sequence", (cycle_id,))]
        detail["revisions"] = [
            {"recordType": row["kind"], "entityId": row["id"], "revision": row["revision"],
             "eventId": row["event_id"], "record": json.loads(row["payload"])}
            for row in db.execute("SELECT v.* FROM revisions v JOIN records r ON r.kind=v.kind AND r.id=v.id "
                                  "WHERE r.cycle_id=? ORDER BY v.rowid", (cycle_id,))]
        return detail

    def cycle_detail(self, cycle_id):
        with self._connection() as db:
            return self._cycle_detail(db, cycle_id)

    def export_session(self, session_id):
        with self._connection() as db:
            session = self._get(db, "session", session_id)
            records = {kind: self._list(db, kind, session_id) for kind in sorted(ALL_KINDS) if kind != "session"}
            revisions = [
                {"recordType": r["kind"], "entityId": r["id"], "revision": r["revision"],
                 "eventId": r["event_id"], "record": json.loads(r["payload"])}
                for r in db.execute("SELECT v.* FROM revisions v JOIN records r ON r.kind=v.kind AND r.id=v.id "
                                    "WHERE r.session_id=? ORDER BY v.rowid", (session_id,))]
            events = [self._event(r) for r in db.execute("SELECT * FROM events WHERE session_id=? ORDER BY sequence",
                                                       (session_id,))]
            return {"schemaVersion": SCHEMA_VERSION, "exportedAt": now(), "session": session,
                    "records": records, "events": events, "revisions": revisions,
                    "metrics": self._metrics(db, session_id, include_simulation=True)}

    def snapshot(self, session_id=None):
        with self._connection() as db:
            sessions = self._list(db, "session")
            selected = self._get(db, "session", session_id) if session_id else (
                max(sessions, key=lambda s: (s["startedAt"], s["id"])) if sessions else None)
            cycles = self._list(db, "cycle", selected["id"]) if selected else []
            active = [c for c in cycles if c["outcome"] == "in_progress"]
            current = max(active or cycles, key=lambda c: (c["startedAt"], c["id"])) if cycles else None
            seq = db.execute("SELECT COALESCE(MAX(sequence),0) FROM events").fetchone()[0]
            capabilities = {name: {"status": "unavailable", "verified": False}
                            for name in ("robot", "cameras", "anomalib", "nemotron", "gemini", "elevenlabs")}
            return {"schemaVersion": SCHEMA_VERSION, "generatedAt": now(), "lastEventSequence": seq,
                    "session": selected, "cycle": current, "activeCycleIds": [c["id"] for c in active],
                    "sourceMode": selected["sourceMode"] if selected else None, "stateVersion": seq,
                    "goalVersion": None, "goal": None, "availableActions": [],
                    "capabilities": capabilities,
                    "metrics": self._metrics(db, selected["id"], include_simulation=True) if selected else
                               self._metrics(db, None, include_simulation=False)}

    def metrics(self, session_id=None, include_simulation=False):
        with self._connection() as db:
            return self._metrics(db, session_id, include_simulation)

    def _metrics(self, db, session_id=None, include_simulation=False):
        if session_id:
            self._get(db, "session", session_id)
        sessions = self._list(db, "session", session_id)
        if not include_simulation:
            sessions = [s for s in sessions if s["sourceMode"] == "live"]
        eligible = {s["id"] for s in sessions}
        records = {}
        for kind in ("cycle", "attempt", "inspection", "reference_label"):
            records[kind] = [r for r in self._list(db, kind, session_id) if r["sessionId"] in eligible]
        cycles, attempts = records["cycle"], records["attempt"]
        inspections = {r["id"]: r for r in records["inspection"]}
        labels = {r["id"]: r for r in records["reference_label"]}
        filters = {"sessionId": session_id, "includeSimulation": include_simulation,
                   "includedSessionIds": sorted(eligible)}
        ccounts = {name: sum(c["outcome"] == name for c in cycles)
                   for name in ("correct", "failed", "aborted", "unverified", "in_progress")}
        acounts = {name: sum(a["outcome"] == name for a in attempts)
                   for name in ("successful", "failed", "aborted", "unverified", "in_progress")}
        cfinished = len(cycles) - ccounts["in_progress"]
        afinished = len(attempts) - acounts["in_progress"]
        first = recovered = retries = 0
        for cycle in cycles:
            ca = sorted((a for a in attempts if a["cycleId"] == cycle["id"]), key=lambda a: a["ordinal"])
            retries += max(0, len(ca) - 1)
            if cycle["outcome"] == "correct":
                if len(ca) == 1 and ca[0]["outcome"] == "successful":
                    first += 1
                elif any(a["outcome"] == "failed" for a in ca[:-1]):
                    recovered += 1
        checked = correct = unresolved = 0
        confusion = {"truePositive": 0, "trueNegative": 0, "falsePositive": 0, "falseNegative": 0}
        defective = 0
        for cycle in cycles:
            label, inspection = labels.get(cycle["referenceLabelId"]), inspections.get(cycle["inspectionId"])
            if not label or not inspection:
                continue
            checked += 1
            truth, prediction = label["quality"], inspection["classification"]
            defective += truth == "defective"
            if prediction == "review_required":
                unresolved += 1
            else:
                correct += truth == prediction
                key = ("truePositive" if prediction == truth == "defective" else
                       "trueNegative" if prediction == truth == "good" else
                       "falsePositive" if prediction == "defective" else "falseNegative")
                confusion[key] += 1
        streak = longest = 0
        for cycle in sorted((c for c in cycles if c["outcome"] != "in_progress"),
                            key=lambda c: (c["endedAt"], c["id"])):
            streak = streak + 1 if cycle["outcome"] == "correct" else 0
            longest = max(longest, streak)
        durations = [(datetime.fromisoformat(c["endedAt"]) - datetime.fromisoformat(c["startedAt"])).total_seconds() * 1000
                     for c in cycles if c["endedAt"]]
        return {
            "filters": filters,
            "cycles": {**ccounts, "total": len(cycles), "finished": cfinished, "inProgress": ccounts["in_progress"]},
            "attempts": {**acounts, "total": len(attempts), "finished": afinished, "inProgress": acounts["in_progress"]},
            "endToEnd": ratio(ccounts["correct"], cfinished, "Confirmed correct cycles / all finished cycles", filters),
            "physicalExecution": ratio(acounts["successful"], afinished, "Confirmed successful attempts / all finished attempts", filters),
            "firstAttemptSuccesses": first, "recoveredCycles": recovered, "retries": retries,
            "additionalInspections": sum(bool(i["additionalInspectionOfId"]) for i in inspections.values()),
            "currentStreak": streak, "longestStreak": longest,
            "detection": {"correct": correct, "checked": checked, "totalPopulation": len(cycles),
                          "unresolved": unresolved, "confusionMatrix": confusion,
                          "rate": ratio(correct, checked, "Correct decision inspections / reference-labeled decision inspections", filters),
                          "defectEscape": ratio(confusion["falseNegative"], defective, "Predicted good / checked defective references", filters)},
            "timings": {"fullCycle": {"sampleCount": len(durations), "valuesMs": durations,
                                      "method": "Persisted endedAt minus startedAt, including waiting and retries"}},
        }
