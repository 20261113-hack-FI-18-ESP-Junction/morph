"""Scribe access and a durable, non-dispatching push-to-talk transcript journal.

The journal treats provider transcripts as untrusted data. A transport must bind
each received message to its capture ID and assign stable event/segment IDs.
Nothing in this module selects a goal or calls a robot adapter.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator
import urllib.error
import urllib.request

SCRIBE_MODEL = "scribe_v3_live"
SCRIBE_ENDPOINT = "wss://api.elevenlabs.io/v1/speech-to-text/realtime"
TOKEN_ENDPOINT = "https://api.elevenlabs.io/v1/single-use-token/realtime_scribe"
MAX_EVENT_BYTES = 64 * 1024
ERROR_EVENTS = frozenset({"error", "auth_error", "quota_exceeded", "transcriber_error",
    "input_error", "invalid_request", "commit_throttled", "unaccepted_terms",
    "rate_limited", "queue_overflow", "resource_exhausted", "session_time_limit_exceeded",
    "chunk_size_exceeded", "insufficient_audio_activity"})
ENRICHMENT_EVENTS = frozenset({"committed_transcript_with_timestamps", "diarized_transcript",
    "committed_transcript_entities", "redacted_transcript", "edited_transcript", "speakers_merged"})


class VoiceError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 409):
        super().__init__(message)
        self.code, self.status_code = code, status_code


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}", value):
        raise VoiceError("invalid_id", f"{field} must be a stable identifier.", 422)
    return value


def _time(value: str | datetime) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
        if not isinstance(result, datetime) or result.tzinfo is None or result.utcoffset() is None:
            raise ValueError
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError):
        raise VoiceError("invalid_time", "Use a timestamp with an explicit timezone.", 422) from None


def _iso(value: str | datetime) -> str:
    return _time(value).isoformat()


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError):
        raise VoiceError("invalid_event", "Event data must be finite JSON.", 422) from None


def _has_secret_fields(value: Any) -> bool:
    if isinstance(value, dict):
        forbidden = {"token", "api_key", "xi-api-key", "authorization", "audio_base_64"}
        return any(str(key).lower() in forbidden or _has_secret_fields(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_has_secret_fields(item) for item in value)
    return False


def scribe_connection_options(language_code: str | None = "sl") -> dict:
    """Public non-secret options. Add a single-use token only at connection time."""
    if language_code is not None and not re.fullmatch(r"[a-z]{2,3}", language_code):
        raise VoiceError("invalid_language", "Use a two- or three-letter language code.", 422)
    params = {"model_id": SCRIBE_MODEL, "audio_format": "pcm_16000", "commit_strategy": "manual",
              "include_timestamps": "true", "include_language_detection": "true"}
    if language_code:
        params["language_code"] = language_code
    return {"endpoint": SCRIBE_ENDPOINT, "params": params, "maxCaptureSeconds": 20,
            "finalizationTimeoutSeconds": 10}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise VoiceError("provider_redirect", "Scribe token endpoint redirected; credential was not forwarded.", 502)


def issue_scribe_token(api_key: str, timeout: float = 10, *, opener=None) -> dict:
    """One explicit token request; callers must authenticate and never log output.

    The response contains a credential intended only for the requesting browser.
    Errors deliberately exclude provider bodies and transport exception text.
    """
    if not isinstance(api_key, str) or not api_key.strip():
        raise VoiceError("missing_credential", "ElevenLabs credential is not configured.", 503)
    if len(api_key) > 8192 or not api_key.isascii() or any(char.isspace() or ord(char) < 32 for char in api_key):
        raise VoiceError("invalid_credential", "ElevenLabs credential configuration is invalid.", 503)
    if not 0 < timeout <= 30:
        raise VoiceError("invalid_timeout", "Token timeout must be between zero and 30 seconds.", 422)
    transport = opener or urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(TOKEN_ENDPOINT, method="POST", data=b"",
        headers={"xi-api-key": api_key, "Accept": "application/json"})
    try:
        with transport.open(request, timeout=timeout) as response:
            raw = response.read(MAX_EVENT_BYTES + 1)
            if response.status != 200 or len(raw) > MAX_EVENT_BYTES:
                raise VoiceError("invalid_token_response", "Unexpected Scribe token response.", 502)
        result = json.loads(raw)
        token = result.get("token") if isinstance(result, dict) else None
        if not isinstance(token, str) or not 1 <= len(token) <= 8192 or any(c.isspace() for c in token):
            raise VoiceError("invalid_token_response", "Scribe token response contained no usable token.", 502)
    except urllib.error.HTTPError as error:
        raise VoiceError("token_http_error", f"Scribe token request failed with HTTP {error.code}.", 502) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise VoiceError("token_transport_error", "Scribe token request failed or timed out.", 502) from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise VoiceError("invalid_token_response", "Scribe token response was not valid JSON.", 502) from None
    return {"token": token, "modelId": SCRIBE_MODEL,
            "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}


class VoiceJournal:
    """SQLite-backed complete-utterance assembly with explicit finalization.

    ``finalize`` needs a committed event identifying the final segment after
    release, plus an exact contiguous segment count from the trusted transport.
    A browser's unverified claim is not independent provider provenance. The lab
    may relay browser events, but must retain that evidence limitation.
    """
    def __init__(self, path: str | Path, *, max_capture_seconds: float = 20,
                 finalization_timeout_seconds: float = 10):
        if not 0 < max_capture_seconds <= 30 or not 0 < finalization_timeout_seconds <= 30:
            raise ValueError("Capture and finalization timeouts must be positive and at most 30 seconds.")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_capture_seconds = max_capture_seconds
        self.finalization_timeout_seconds = finalization_timeout_seconds
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS voice_captures (
                    id TEXT PRIMARY KEY, data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS voice_events (
                    id TEXT PRIMARY KEY, capture_id TEXT NOT NULL, digest TEXT NOT NULL,
                    data TEXT NOT NULL, FOREIGN KEY(capture_id) REFERENCES voice_captures(id)
                );
                CREATE INDEX IF NOT EXISTS voice_events_capture ON voice_events(capture_id);
            """)

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _load(db, identity: str) -> dict:
        row = db.execute("SELECT data FROM voice_captures WHERE id=?", (identity,)).fetchone()
        if row is None:
            raise VoiceError("not_found", "Voice capture does not exist.", 404)
        return json.loads(row["data"])

    @staticmethod
    def _save(db, record: dict) -> None:
        db.execute("UPDATE voice_captures SET data=? WHERE id=?", (_json(record), record["id"]))

    @staticmethod
    def _public(record: dict, **extra) -> dict:
        result = json.loads(_json(record))
        result["segments"] = sorted(result["segments"], key=lambda row: row["index"])
        result["text"] = " ".join(row["text"] for row in result["segments"] if row["text"])
        result["readyForGoalSelection"] = result["status"] == "finalized"
        result["goalRequestId"] = "voice-goal:" + hashlib.sha256(result["id"].encode()).hexdigest() if result["status"] == "finalized" else None
        return {**result, **extra}

    @staticmethod
    def _reject(record: dict, reason: str, when: str) -> None:
        if record["status"] not in ("finalized", "rejected"):
            record.update(status="rejected", rejectionReason=reason, completedAt=when, partialText="")

    def start(self, utterance_id: str, session_id: str, started_at: str | datetime,
              source_mode: str = "simulation", cycle_id: str | None = None) -> dict:
        _id(utterance_id, "utterance_id"); _id(session_id, "session_id")
        if cycle_id is not None:
            _id(cycle_id, "cycle_id")
        if source_mode not in ("simulation", "live"):
            raise VoiceError("invalid_source", "Voice capture source must be simulation or live.", 422)
        metadata = {"id": utterance_id, "sessionId": session_id, "cycleId": cycle_id,
                    "startedAt": _iso(started_at), "sourceMode": source_mode}
        with self._db() as db:
            existing = db.execute("SELECT data FROM voice_captures WHERE id=?", (utterance_id,)).fetchone()
            if existing:
                record = json.loads(existing["data"])
                if any(record[key] != value for key, value in metadata.items()):
                    raise VoiceError("id_conflict", "Capture ID already has different metadata.")
                return self._public(record, duplicate=True)
            record = {**metadata, "provider": "elevenlabs", "modelId": SCRIBE_MODEL,
                "providerSessionId": None, "providerConfig": None, "status": "capturing",
                "releasedAt": None, "completedAt": None, "finalizationDeadline": None,
                "rejectionReason": None, "partialText": "", "segments": [], "eventCount": 0,
                "enrichmentWarnings": [], "finalization": None,
                "captureDeadline": (_time(started_at) + timedelta(seconds=self.max_capture_seconds)).isoformat()}
            db.execute("INSERT INTO voice_captures(id,data) VALUES(?,?)", (utterance_id, _json(record)))
            return self._public(record, duplicate=False)

    def get(self, utterance_id: str) -> dict:
        with self._db() as db:
            return self._public(self._load(db, utterance_id))

    def events(self, utterance_id: str) -> list[dict]:
        with self._db() as db:
            self._load(db, utterance_id)
            return [json.loads(row["data"]) for row in db.execute(
                "SELECT data FROM voice_events WHERE capture_id=? ORDER BY rowid", (utterance_id,))]

    def receive(self, utterance_id: str, event_id: str, event: dict, received_at: str | datetime,
                segment_index: int | None = None) -> dict:
        _id(event_id, "event_id")
        when = _iso(received_at)
        if not isinstance(event, dict) or len(_json(event).encode()) > MAX_EVENT_BYTES:
            raise VoiceError("invalid_event", "Voice event must be a bounded JSON object.", 422)
        kind = event.get("message_type")
        if not isinstance(kind, str):
            raise VoiceError("invalid_event", "Voice event requires message_type.", 422)
        if segment_index is None:
            segment_index = event.get("segment_index")
        if segment_index is not None and (type(segment_index) is not int or not 0 <= segment_index < 128):
            raise VoiceError("invalid_segment", "Segment index must be an integer from 0 to 127.", 422)
        if "segment_index" in event and event["segment_index"] != segment_index:
            raise VoiceError("segment_conflict", "Envelope and provider segment index disagree.", 422)
        if _has_secret_fields(event):
            raise VoiceError("forbidden_event_field", "Do not persist credentials or audio in transcript events.", 422)
        if "text" in event and (not isinstance(event["text"], str) or len(event["text"]) > 4000):
            raise VoiceError("invalid_text", "Transcript text must contain at most 4000 characters.", 422)
        identity = {"utteranceId": utterance_id, "event": event, "segmentIndex": segment_index}
        digest = hashlib.sha256(_json(identity).encode()).hexdigest()
        with self._db() as db:
            record = self._load(db, utterance_id)
            previous = db.execute("SELECT digest FROM voice_events WHERE id=?", (event_id,)).fetchone()
            if previous:
                if previous["digest"] != digest:
                    raise VoiceError("event_conflict", "Event ID already identifies different content.")
                return self._public(record, duplicate=True)
            if record["eventCount"] >= 1000:
                raise VoiceError("event_limit", "Capture event limit reached.", 422)
            if _time(when) < _time(record["startedAt"]):
                raise VoiceError("invalid_time", "Event predates capture start.", 422)
            if record["status"] == "capturing" and _time(when) > _time(record["captureDeadline"]):
                self._reject(record, "capture_timeout", when)
            if record["status"] == "finalizing" and _time(when) > _time(record["finalizationDeadline"]):
                self._reject(record, "finalization_timeout", when)
            disposition = "ignored"
            terminal = record["status"] in ("finalized", "rejected")
            if kind == "session_started" and not terminal:
                config = event.get("config", {})
                provider_id = event.get("session_id")
                if not isinstance(config, dict) or config.get("model_id") != SCRIBE_MODEL:
                    self._reject(record, "provider_model_mismatch", when)
                elif not isinstance(provider_id, str) or not provider_id or len(provider_id) > 200:
                    self._reject(record, "missing_provider_session", when)
                elif record["providerSessionId"] not in (None, provider_id):
                    self._reject(record, "provider_session_changed", when)
                elif config.get("commit_strategy", "manual") != "manual":
                    self._reject(record, "commit_strategy_mismatch", when)
                else:
                    record["providerSessionId"] = provider_id
                    record["providerConfig"] = {key: config[key] for key in
                        ("model_id", "audio_format", "sample_rate", "commit_strategy", "language_code") if key in config}
                disposition = "session_configuration"
            elif kind in ERROR_EVENTS:
                self._reject(record, "provider_" + kind, when)
                disposition = "provider_error"
            elif kind in ("partial_transcript", "committed_transcript") and not terminal:
                if not record["providerSessionId"]:
                    self._reject(record, "transcript_before_session", when)
                elif kind == "partial_transcript":
                    record["partialText"] = event.get("text", "")
                    disposition = "display_only"
                elif segment_index is None:
                    self._reject(record, "missing_segment_identity", when)
                else:
                    text = event.get("text", "").strip()
                    segment = next((row for row in record["segments"] if row["index"] == segment_index), None)
                    if segment and segment["text"] != text:
                        self._reject(record, "conflicting_committed_segment", when)
                    elif not segment:
                        if sum(len(row["text"]) + 1 for row in record["segments"]) + len(text) > 4000:
                            self._reject(record, "utterance_too_long", when)
                        else:
                            record["segments"].append({"index": segment_index, "text": text,
                                "committedEventId": event_id, "receivedAt": when, "enrichments": []})
                            record["partialText"] = ""
                    disposition = "committed_segment"
            elif kind in ENRICHMENT_EVENTS:
                segment = next((row for row in record["segments"] if row["index"] == segment_index), None)
                if segment and ("text" not in event or event["text"].strip() == segment["text"]):
                    segment["enrichments"].append({"eventId": event_id, "receivedAt": when,
                                                  "messageType": kind, "data": event})
                    disposition = "enrichment_only"
                else:
                    record["enrichmentWarnings"].append({"eventId": event_id, "reason": "unmatched_or_conflicting_segment"})
                    disposition = "unmatched_enrichment"
            envelope = {"id": event_id, **identity, "receivedAt": when, "disposition": disposition}
            db.execute("INSERT INTO voice_events(id,capture_id,digest,data) VALUES(?,?,?,?)",
                       (event_id, utterance_id, digest, _json(envelope)))
            record["eventCount"] += 1
            self._save(db, record)
            return self._public(record, duplicate=False, eventDisposition=disposition)

    def release(self, utterance_id: str, released_at: str | datetime) -> dict:
        when = _iso(released_at)
        with self._db() as db:
            record = self._load(db, utterance_id)
            if record["releasedAt"] is not None or record["status"] in ("finalized", "rejected"):
                return self._public(record, duplicate=True)
            if _time(when) < _time(record["startedAt"]):
                raise VoiceError("invalid_time", "Release predates capture start.", 422)
            if _time(when) > _time(record["captureDeadline"]):
                self._reject(record, "capture_timeout", when)
            else:
                record.update(status="finalizing", releasedAt=when,
                    finalizationDeadline=(_time(when) + timedelta(seconds=self.finalization_timeout_seconds)).isoformat())
            self._save(db, record)
            return self._public(record, duplicate=False)

    def finalize(self, utterance_id: str, expected_segment_count: int, terminal_commit_event_id: str,
                 completed_at: str | datetime) -> dict:
        when = _iso(completed_at)
        if type(expected_segment_count) is not int or not 1 <= expected_segment_count <= 128:
            raise VoiceError("invalid_segment_count", "Expected segment count must be between 1 and 128.", 422)
        _id(terminal_commit_event_id, "terminal_commit_event_id")
        marker = {"expectedSegmentCount": expected_segment_count, "terminalCommitEventId": terminal_commit_event_id}
        with self._db() as db:
            record = self._load(db, utterance_id)
            if record["status"] == "finalized":
                if record["finalization"] != marker:
                    raise VoiceError("finalization_conflict", "Utterance was finalized with different segment evidence.")
                return self._public(record, newlyFinalized=False, duplicate=True)
            if record["status"] != "finalizing":
                raise VoiceError("not_finalizing", "Capture must be explicitly released before finalization.")
            if _time(when) < _time(record["releasedAt"]):
                raise VoiceError("invalid_time", "Finalization predates release.", 422)
            if _time(when) > _time(record["finalizationDeadline"]):
                self._reject(record, "finalization_timeout", when)
                self._save(db, record)
                return self._public(record, newlyFinalized=False)
            segments = sorted(record["segments"], key=lambda row: row["index"])
            if [row["index"] for row in segments] != list(range(expected_segment_count)):
                raise VoiceError("segments_unresolved", "All expected contiguous segments must be committed.")
            final_segment = segments[-1]
            if final_segment["committedEventId"] != terminal_commit_event_id:
                raise VoiceError("invalid_final_commit", "Finalization must reference the final committed segment event.")
            if _time(final_segment["receivedAt"]) < _time(record["releasedAt"]):
                raise VoiceError("commit_before_release", "A final commit response after release is required.")
            if _time(when) < max(_time(row["receivedAt"]) for row in segments):
                raise VoiceError("invalid_time", "Finalization predates a committed segment.", 422)
            if record["partialText"].strip():
                raise VoiceError("unresolved_partial", "Uncommitted speech remains after the final segment.")
            text = " ".join(row["text"] for row in segments if row["text"])
            if not text:
                self._reject(record, "empty_utterance", when)
            elif not record["providerSessionId"]:
                self._reject(record, "missing_provider_session", when)
            else:
                record.update(status="finalized", completedAt=when, finalization=marker)
            self._save(db, record)
            return self._public(record, newlyFinalized=record["status"] == "finalized", duplicate=False)

    def expire(self, now: str | datetime) -> list[dict]:
        return self._end_incomplete(now, interrupted=False)

    def recover_incomplete(self, now: str | datetime) -> list[dict]:
        """Explicit startup reconciliation; never resume microphone/commands."""
        return self._end_incomplete(now, interrupted=True)

    def _end_incomplete(self, now: str | datetime, *, interrupted: bool) -> list[dict]:
        when = _iso(now)
        changed = []
        with self._db() as db:
            for row in db.execute("SELECT data FROM voice_captures").fetchall():
                record = json.loads(row["data"])
                if record["status"] not in ("capturing", "finalizing"):
                    continue
                deadline = record["finalizationDeadline"] or record["captureDeadline"]
                if interrupted or _time(when) > _time(deadline):
                    if _time(when) < _time(record["startedAt"]):
                        raise VoiceError("invalid_time", "Reconciliation predates capture start.", 422)
                    self._reject(record, "capture_interrupted" if interrupted else
                        ("finalization_timeout" if record["status"] == "finalizing" else "capture_timeout"), when)
                    self._save(db, record)
                    changed.append(self._public(record))
        return changed
