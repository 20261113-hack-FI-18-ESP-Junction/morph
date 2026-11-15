"""Offline integrity checks and evidence reports for complete station exports.

No database, network, provider or device is opened. Canonical record validation
and metric calculation are reused with an in-memory read adapter. Input exports
remain untouched; reports never reproduce model prompts, outputs or audit prose.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import html
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, get_args

from pydantic import AwareDatetime, ValidationError

from .models import MODELS, CorrectionRequest
from .store import CORRECTABLE, MUTABLE, StationStore, StoreError, without_revision

TOOL_VERSION = "1"
MAX_INPUT_BYTES = 32 * 1024 * 1024
KINDS = set(MODELS) | {"correction"}
ROOT_KEYS = {"schemaVersion", "exportedAt", "session", "records", "events", "revisions", "metrics"}
EVENT_KEYS = {"sequence", "eventId", "type", "recordType", "entityId", "entityRevision",
              "sessionId", "cycleId", "sourceMode", "occurredAt", "receivedAt", "payload"}
REVISION_KEYS = {"recordType", "entityId", "revision", "eventId", "record"}
REFERENCE_FIELDS = {"cycleId": "cycle", "inspectionId": "inspection",
                    "referenceLabelId": "reference_label", "confirmationId": "confirmation",
                    "retryOfAttemptId": "attempt", "evidenceId": "evidence",
                    "modelRunId": "model_run", "additionalInspectionOfId": "inspection",
                    "mapEvidenceId": "evidence", "frameIds": "frame", "evidenceIds": "evidence",
                    "attemptId": "attempt", "decisionId": "decision"}


class AuditInputError(ValueError):
    """Malformed, unsupported or unavailable input, without echoing its values."""


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AuditInputError("Duplicate JSON object key.")
        result[key] = value
    return result


def _constant(_value):
    raise AuditInputError("Non-finite JSON number.")


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise AuditInputError("Non-finite JSON number.")
    return result


def load_export(path: str | Path) -> dict:
    try:
        with Path(path).open("rb") as stream:
            data = stream.read(MAX_INPUT_BYTES + 1)
        if len(data) > MAX_INPUT_BYTES:
            raise AuditInputError("Export exceeds the 32 MiB input limit.")
        return json.loads(data.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_float=_finite_float)
    except AuditInputError:
        raise
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise AuditInputError("Cannot read a valid UTF-8 JSON export.") from exc


def _positive(value):
    return type(value) is int and value > 0


def _kind(value):
    return isinstance(value, str) and value in KINDS


def _file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _id(value, limit=140):
    return isinstance(value, str) and len(value) <= limit and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", value))


def _time(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except ValueError:
        return False


def _same(a, b):
    """JSON semantic equality, accepting 1/1.0 but never True/1."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def _has_datetime(annotation):
    return annotation in (datetime, AwareDatetime) or any(_has_datetime(arg) for arg in get_args(annotation))


def _strict_record(model, raw):
    # The shared Time BeforeValidator uses Python validation, where strict mode
    # rejects JSON timestamp strings. Parse only declared timestamp fields before
    # strict validation; other scalar types must retain their JSON types.
    values = dict(raw)
    for name, field in model.model_fields.items():
        if name in values and values[name] is not None and _has_datetime(field.annotation):
            if not _time(values[name]):
                raise ValueError("Invalid timezone-qualified timestamp")
            values[name] = datetime.fromisoformat(values[name].replace("Z", "+00:00"))
    return model.model_validate(values, strict=True).model_dump(mode="json")


class _MemoryRecords(StationStore):
    """Only inherited pure validation/calculation methods may be called here."""

    def __init__(self, records):
        self.records = records

    def _get(self, _db, kind, ident):
        try:
            return self.records[kind][ident]
        except KeyError as exc:
            raise StoreError(409, "Referenced record is missing") from exc

    def _list(self, _db, kind, session_id=None, cycle_id=None):
        return [r for r in self.records.get(kind, {}).values()
                if (session_id is None or (r["id"] if kind == "session" else r["sessionId"]) == session_id)
                and (cycle_id is None or r.get("cycleId", r["id"] if kind == "cycle" else None) == cycle_id)]


class _Audit:
    def __init__(self):
        self.issues = []
        self.error_count = 0
        self.issue_count = 0

    def issue(self, code, path, message, severity="error"):
        self.issue_count += 1
        self.error_count += severity == "error"
        if len(self.issues) < 500:
            self.issues.append({"severity": severity, "code": code, "path": path, "message": message})

    def result(self, source=None, metrics=None, live_metrics=None, counts=None, cycles=None, model_runs=None):
        return {"toolVersion": TOOL_VERSION, "status": "failed" if self.error_count else "passed",
                "issues": self.issues, "issueCount": self.issue_count,
                "issuesTruncated": self.issue_count > len(self.issues),
                "source": source, "metrics": metrics, "liveMetrics": live_metrics,
                "recordCounts": counts or {}, "cycleSummaries": cycles or [],
                "modelRuns": model_runs or [], "physicalVerification": "not_performed",
                "evidenceFilesVerified": False,
                "scope": "Consistency of saved metadata; no independent physical, model-quality or media verification."}

    def record(self, kind, record, path, current=False):
        if not isinstance(record, dict):
            self.issue("invalid_record", path, "Record must be an object.")
            return None
        if current and not _positive(record.get("revision")):
            self.issue("invalid_revision", path, "Current record needs a positive integer revision.")
            return None
        if not current and "revision" in record:
            self.issue("invalid_history_record", path, "History payload must not contain the current revision wrapper.")
            return None
        raw = without_revision(record) if current else record
        try:
            if kind == "correction":
                fields = set(CorrectionRequest.model_fields)
                extras = {"sessionId", "cycleId", "previousRevision", "newRevision", "reviewId"}
                if not (fields | (extras - {"reviewId"})).issubset(raw) or set(raw) - fields - extras:
                    raise ValueError("correction shape")
                _strict_record(CorrectionRequest, {k: raw[k] for k in fields})
                if (not _id(raw.get("sessionId")) or
                        raw.get("cycleId") is not None and not _id(raw["cycleId"]) or
                        not _positive(raw.get("previousRevision")) or
                        not _positive(raw.get("newRevision")) or
                        not _positive(raw.get("expectedRevision")) or
                        raw["expectedRevision"] != raw["previousRevision"] or
                        raw["newRevision"] != raw["previousRevision"] + 1 or
                        "reviewId" in raw and not _id(raw["reviewId"])):
                    raise ValueError("correction identifiers or versions")
                result = deepcopy(raw)
            else:
                result = _strict_record(MODELS[kind], raw)
            if current:
                result["revision"] = record["revision"]
            return result
        except (ValidationError, ValueError, KeyError, TypeError):
            self.issue("invalid_record", path, "Record violates the supported schema; no fields were silently discarded.")
            return None


def audit_export(document: Any) -> dict:
    audit = _Audit()
    try:
        json.dumps(document, allow_nan=False)
    except (ValueError, TypeError, RecursionError):
        audit.issue("invalid_json_value", "$", "Input must contain finite JSON values without cycles.")
        return audit.result()
    if not isinstance(document, dict) or set(document) != ROOT_KEYS:
        audit.issue("invalid_export_shape", "$", "Expected all seven complete export sections, with no unknown top-level fields.")
        return audit.result()
    if type(document["schemaVersion"]) is not int or document["schemaVersion"] != 1:
        audit.issue("unsupported_schema", "schemaVersion", "Only station export schema version 1 is supported.")
    if not _time(document["exportedAt"]):
        audit.issue("invalid_time", "exportedAt", "Export time must have an explicit timezone.")
    if (not isinstance(document["records"], dict) or set(document["records"]) != KINDS - {"session"} or
            not all(isinstance(v, list) for v in document["records"].values()) or
            not isinstance(document["events"], list) or not isinstance(document["revisions"], list) or
            not isinstance(document["metrics"], dict)):
        audit.issue("invalid_export_shape", "$", "Expected complete typed record groups, event/revision arrays and metrics object.")
        return audit.result()
    records = {kind: {} for kind in sorted(KINDS)}
    originals = {}
    entries = [("session", document["session"], "session")]
    entries += [(kind, r, f"records.{kind}[{i}]") for kind, rows in document["records"].items() for i, r in enumerate(rows)]
    for kind, record, path in entries:
        valid = audit.record(kind, record, path, current=True)
        if valid is None:
            continue
        key = kind, valid["id"]
        if key in originals:
            audit.issue("duplicate_record", path, "A current typed record identity occurs more than once.")
        records[kind][valid["id"]] = valid
        originals[key] = record
    if audit.error_count:
        return audit.result()
    session = next(iter(records["session"].values()))
    sid = session["id"]
    source = {"sessionId": sid, "sourceMode": session["sourceMode"], "configId": session["configId"],
              "robotId": session["robotId"], "sessionRevision": session["revision"]}
    memory = _MemoryRecords(records)
    for kind, rows in records.items():
        for record in rows.values():
            path = f"{kind}:{record['id']}"
            if kind != "session" and record["sessionId"] != sid:
                audit.issue("cross_session", path, "Record belongs to another session.")
            if kind != "correction":
                try:
                    memory._validate(None, kind, record, old=record)
                except StoreError:
                    audit.issue("invalid_relationship", path, "Typed references or outcome preconditions fail canonical validation.")
    for cycle in records["cycle"].values():
        attempts = sorted(memory._list(None, "attempt", sid, cycle["id"]), key=lambda a: a["ordinal"])
        if [a["ordinal"] for a in attempts] != list(range(1, len(attempts) + 1)):
            audit.issue("attempt_sequence", f"cycle:{cycle['id']}", "Attempt ordinals must be unique and consecutive from one.")
    # Additional inspections may not form self-links or longer loops.
    for inspection in records["inspection"].values():
        seen, current = set(), inspection
        while current:
            if current["id"] in seen:
                audit.issue("inspection_cycle", f"inspection:{inspection['id']}", "Additional-inspection references contain a cycle.")
                break
            seen.add(current["id"])
            current = records["inspection"].get(current["additionalInspectionOfId"])

    histories = {}
    for index, row in enumerate(document["revisions"]):
        path = f"revisions[{index}]"
        if (not isinstance(row, dict) or set(row) != REVISION_KEYS or not _kind(row.get("recordType")) or
                not _id(row.get("entityId")) or not _id(row.get("eventId")) or not _positive(row.get("revision"))):
            audit.issue("invalid_history", path, "Invalid revision envelope.")
            continue
        kind, ident, revision = row["recordType"], row["entityId"], row["revision"]
        valid = audit.record(kind, row["record"], path + ".record")
        if valid is None:
            continue
        if valid["id"] != ident or (ident if kind == "session" else valid["sessionId"]) != sid:
            audit.issue("history_identity", path, "History payload identity or session differs from its envelope.")
        # Check historical links against the supplied complete record population.
        # This does not reconstruct the referenced values as of this event.
        scoped = {**valid, "cycleId": ident} if kind == "cycle" else valid
        for field, reference_kind in REFERENCE_FIELDS.items():
            value = valid.get(field)
            references = value if isinstance(value, list) else [value]
            for reference in references:
                if reference is None:
                    continue
                try:
                    memory._ref(None, reference_kind, reference, scoped,
                                object_match="objectId" in valid and reference_kind in
                                ("cycle", "frame", "inspection", "reference_label"))
                except StoreError:
                    audit.issue("invalid_history_reference", path + ".record." + field,
                                "Historical reference is missing or belongs to another session, cycle or object.")
        key = kind, ident, revision
        if key in histories:
            audit.issue("duplicate_revision", path, "A typed record revision occurs more than once.")
        histories[key] = row
    events, event_versions, sequences = {}, {}, set()
    last_sequence = 0
    for index, event in enumerate(document["events"]):
        path = f"events[{index}]"
        if (not isinstance(event, dict) or set(event) != EVENT_KEYS or not _kind(event.get("recordType")) or
                not _positive(event.get("sequence")) or not _positive(event.get("entityRevision")) or
                not _id(event.get("eventId")) or not _id(event.get("entityId")) or
                not isinstance(event.get("type"), str) or
                not isinstance(event.get("payload"), dict)):
            audit.issue("invalid_event", path, "Invalid event envelope.")
            continue
        kind, ident, revision = event["recordType"], event["entityId"], event["entityRevision"]
        version = kind, ident, revision
        if event["eventId"] in events or event["sequence"] in sequences or version in event_versions:
            audit.issue("duplicate_event", path, "Event ID, sequence or typed record revision is repeated.")
        if event["sequence"] <= last_sequence:
            audit.issue("event_order", path, "Event sequence must strictly increase; gaps are allowed.")
        last_sequence = event["sequence"]
        sequences.add(last_sequence)
        events[event["eventId"]] = event
        event_versions[version] = event
        if event["sessionId"] != sid or event["sourceMode"] != session["sourceMode"]:
            audit.issue("event_source", path, "Event session/source does not match the export.")
        for field in ("occurredAt", "receivedAt"):
            if not _time(event[field]):
                audit.issue("invalid_time", path + "." + field, "Timestamp must have an explicit timezone.")
        allowed = {f"{kind}.created"} if revision == 1 else {f"{kind}.updated", f"{kind}.corrected"}
        if event["type"] not in allowed:
            audit.issue("event_operation", path, "Event operation does not match its record revision.")
        expected_cycle = ident if kind == "cycle" else event["payload"].get("cycleId")
        if event["cycleId"] != expected_cycle:
            audit.issue("event_cycle", path, "Event cycle differs from its payload.")
        history = histories.get(version)
        if not history or history["eventId"] != event["eventId"] or not _same(history["record"], event["payload"]):
            audit.issue("event_history_mismatch", path, "Event has no exact matching revision payload.")
    for key, row in histories.items():
        if key not in event_versions or event_versions[key]["eventId"] != row["eventId"]:
            audit.issue("missing_history_event", "revisions", "Revision has no matching event.")
        if key[:2] not in originals:
            audit.issue("orphan_history", "revisions", "History has no current typed record.")
    for key, record in originals.items():
        versions = sorted(k[2] for k in histories if k[:2] == key)
        if len(versions) != record["revision"] or versions != list(range(1, len(versions) + 1)):
            audit.issue("revision_sequence", f"{key[0]}:{key[1]}", "History must contain every revision from one through current.")
        latest = histories.get((*key, record["revision"]))
        if not latest or not _same(latest["record"], without_revision(record)):
            audit.issue("current_history_mismatch", f"{key[0]}:{key[1]}", "Current record differs from its final revision.")
        prior_sequence = 0
        for revision in versions:
            event = event_versions.get((*key, revision))
            if event:
                if event["sequence"] <= prior_sequence:
                    audit.issue("revision_event_order", f"{key[0]}:{key[1]}", "Record revisions are out of event order.")
                prior_sequence = event["sequence"]
                previous = histories.get((*key, revision - 1))
                current = histories.get((*key, revision))
                if previous and current and event["type"].endswith(".updated"):
                    old, new = previous["record"], current["record"]
                    changed = {k for k in set(old) | set(new) if not _same(old.get(k), new.get(k))}
                    # Evidence acceptance requires attributed changes after any
                    # finished result, including late unverified confirmations.
                    # The older ingestion API also permits ordinary unverified
                    # updates; these are flagged for explicit audit reconciliation.
                    terminal = (key[0] in ("cycle", "attempt") and old.get("outcome") != "in_progress" or
                                key[0] == "utterance" and old.get("status") != "partial" or
                                key[0] == "model_run" and old.get("completedAt") is not None or
                                key[0] == "execution" and old.get("status") in ("finished", "failed"))
                    if not changed or not changed.issubset(MUTABLE.get(key[0], set())) or terminal:
                        audit.issue("invalid_update_transition", f"{key[0]}:{key[1]}",
                                    "Ordinary update changes immutable fields or a terminal record requiring an audit.")

    coverage = defaultdict(set)
    for correction in records["correction"].values():
        path = f"correction:{correction['id']}"
        target = correction["entityType"], correction["entityId"]
        prev_key, new_key = (*target, correction["previousRevision"]), (*target, correction["newRevision"])
        previous, new = histories.get(prev_key), histories.get(new_key)
        event = event_versions.get(new_key)
        correction_event = event_versions.get(("correction", correction["id"], correction["revision"]))
        field = correction["field"]
        valid = (target in originals and previous is not None and new is not None and event is not None and
                 event["type"] == f"{target[0]}.corrected" and
                 field in CORRECTABLE.get(target[0], set()) and field in previous["record"] and field in new["record"] and
                 _same(previous["record"][field], correction["previousValue"]) and
                 _same(new["record"][field], correction["newValue"]) and
                 not _same(correction["previousValue"], correction["newValue"]) and
                 correction["cycleId"] == event["cycleId"] and
                 correction_event is not None and correction_event["eventId"] == correction["eventId"] and
                 correction_event["sequence"] > event["sequence"])
        if not valid:
            audit.issue("invalid_correction", path, "Correction does not establish the exact attributed target transition.")
        if field in coverage[new_key]:
            audit.issue("duplicate_correction_field", path, "A corrected field is attributed more than once for one transition.")
        coverage[new_key].add(field)
    for key, event in event_versions.items():
        if not event["type"].endswith(".corrected"):
            continue
        previous, new = histories.get((*key[:2], key[2] - 1)), histories.get(key)
        if previous and new:
            changed = {k for k in set(previous["record"]) | set(new["record"])
                       if k not in previous["record"] or k not in new["record"] or
                       not _same(previous["record"].get(k), new["record"].get(k))}
            if not changed or changed != coverage[key]:
                audit.issue("incomplete_correction_audit", "revisions", "Every changed field of a corrected transition needs exact audit coverage.")
    counts = {kind: len(rows) for kind, rows in records.items()}
    counts.update(events=len(document["events"]), revisions=len(document["revisions"]))
    if audit.error_count:
        return audit.result(source=source, counts=counts)
    metrics = memory._metrics(None, sid, include_simulation=True)
    live_metrics = memory._metrics(None, sid, include_simulation=False)
    if not _same(metrics, document["metrics"]):
        audit.issue("metric_mismatch", "metrics", "Exported metrics differ from canonical calculation; use no result until reconciled.")
        return audit.result(source=source, counts=counts)
    audit.issue("evidence_metadata_only", "records.evidence", "Evidence hashes are declarations; original media bytes were not supplied or verified.", "warning")
    audit.issue("physical_not_verified", "session.sourceMode", "Saved outcome consistency is not independent proof of physical truth.", "warning")
    cycles = [{k: c[k] for k in ("id", "objectId", "outcome", "startedAt", "endedAt", "referenceLabelId",
                                   "inspectionId", "confirmationId", "commandedDestination", "observedDestination")}
              for c in records["cycle"].values()]
    model_runs = [{k: r[k] for k in ("id", "provider", "modelId", "device", "precision", "latencyMs", "requestedAt", "completedAt")}
                  for r in records["model_run"].values()]
    return audit.result(source, metrics, live_metrics, counts, cycles, model_runs)


def compare_replay(left: Any, right: Any) -> dict:
    a, b = audit_export(left), audit_export(right)
    equivalent = (a["status"] == b["status"] == "passed" and
                  _same({k: v for k, v in left.items() if k != "exportedAt"},
                        {k: v for k, v in right.items() if k != "exportedAt"}))
    issues = [] if equivalent else [{"severity": "error", "code": "replay_mismatch", "path": "$",
                                    "message": "Both exports must pass audit and match excluding only exportedAt."}]
    return {"toolVersion": TOOL_VERSION, "status": "passed" if equivalent else "failed", "equivalent": equivalent,
            "issues": issues, "left": a, "right": b, "ignoredFields": ["exportedAt"],
            "scope": "Equivalence of paired saved snapshots; this does not run or observe browser replay.",
            "physicalVerification": "not_performed", "evidenceFilesVerified": False}


def _cell(value):
    if value is None:
        return "Unavailable"
    # Encode punctuation that could introduce Markdown links/HTML/code from input.
    text = html.escape(str(value), quote=True).replace("\n", " ").replace("\r", " ")
    for character in "|`[]*_":
        text = text.replace(character, f"&#{ord(character)};")
    return text


def _rate(value):
    n, d = value["numerator"], value["denominator"]
    return f"{n} / {d} ({value['value'] * 100:.1f}%)" if d else "No data yet (0 eligible records)"


def render_markdown(report: dict) -> str:
    if "equivalent" in report:
        return ("# Paired export equivalence\n\nStatus: **" + report["status"] + "**.\n\n" + report["scope"] +
                " Only top-level `exportedAt` is ignored.\n\n" +
                "\n".join(f"- {_cell(i['message'])}" for i in report["issues"]) +
                "\n\n## Left snapshot\n\n" + render_markdown(report["left"]).replace("# Export integrity report", "### Export integrity report", 1) +
                "\n## Right snapshot\n\n" + render_markdown(report["right"]).replace("# Export integrity report", "### Export integrity report", 1))
    lines = ["# Export integrity report", "", f"Status: **{report['status']}**.", "", report["scope"], "",
             "No database import, provider call or robot operation occurred. Original media bytes were not verified.", ""]
    source = report.get("source")
    if source:
        lines += [f"Session: {_cell(source['sessionId'])}. Source mode: **{source['sourceMode']}**. Configuration: {_cell(source['configId'])}.", ""]
        if source["sourceMode"] == "simulation":
            lines += ["These are simulation records. Default live reliability aggregates contain no eligible records.", ""]
    lines += ["## Findings", "", "| Severity | Code | Location | Finding |", "| --- | --- | --- | --- |"]
    lines += ["| " + " | ".join(_cell(i[k]) for k in ("severity", "code", "path", "message")) + " |" for i in report["issues"]]
    m = report.get("metrics")
    if not m:
        lines += ["", "Metrics are withheld because the export did not pass integrity checks."]
        return "\n".join(lines) + "\n"
    lines += ["", "## Recorded metrics", "", "| Metric | Result |", "| --- | --- |",
              f"| End-to-end correct cycles / all finished cycles | {_rate(m['endToEnd'])} |",
              f"| Successful attempts / all finished attempts | {_rate(m['physicalExecution'])} |",
              f"| Detection correctness | {m['detection']['correct']} correct / {m['detection']['checked']} checked; {m['detection']['totalPopulation']} cycles total |"]
    for key in ("firstAttemptSuccesses", "recoveredCycles", "retries", "additionalInspections", "currentStreak", "longestStreak"):
        lines.append(f"| {key} | {m[key]} |")
    lines += ["", "| Outcome | Cycles | Attempts |", "| --- | --- | --- |"]
    for cycle_key, attempt_key in (("correct", "successful"), ("failed", "failed"), ("aborted", "aborted"), ("unverified", "unverified"), ("in_progress", "in_progress")):
        lines.append(f"| {cycle_key} / {attempt_key} | {m['cycles'][cycle_key]} | {m['attempts'][attempt_key]} |")
    timing = m["timings"]["fullCycle"]
    lines += ["", "## Recorded full-cycle times", "", timing["method"] + ".",
              f"Samples: {timing['sampleCount']}. Milliseconds: " + (", ".join(str(v) for v in timing["valuesMs"]) or "No data yet") + ".",
              "These values use persisted event times, including waiting/retries within that interval. They are not newly measured motion or benchmark results.",
              "", "## Record trace", "", "| Cycle | Object | Outcome | Reference | Inspection | Confirmation |", "| --- | --- | --- | --- | --- | --- |"]
    for c in report["cycleSummaries"]:
        lines.append("| " + " | ".join(_cell(c[k]) for k in ("id", "objectId", "outcome", "referenceLabelId", "inspectionId", "confirmationId")) + " |")
    lines += ["", "## Recorded model provenance", "", "| Run | Provider | Model | Device | Precision | Latency ms |", "| --- | --- | --- | --- | --- | --- |"]
    for r in report["modelRuns"]:
        lines.append("| " + " | ".join(_cell(r[k]) for k in ("id", "provider", "modelId", "device", "precision", "latencyMs")) + " |")
    lines += ["", "No cross-session performance conclusion is made. Comparable inputs/configurations and actual measured hardware runs are required."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit", help="Check one complete saved export")
    audit.add_argument("input", type=Path)
    replay = sub.add_parser("replay", help="Check equivalence of two saved exports")
    replay.add_argument("left", type=Path)
    replay.add_argument("right", type=Path)
    for child in (audit, replay):
        child.add_argument("--output-dir", required=True, type=Path, help="New directory; existing paths are refused")
    args = parser.parse_args(argv)
    paths = [args.input] if args.command == "audit" else [args.left, args.right]
    try:
        if args.output_dir.exists():
            raise AuditInputError("Output directory already exists; choose a new path.")
        if any(p.stat().st_size > MAX_INPUT_BYTES for p in paths):
            raise AuditInputError("Export exceeds the 32 MiB input limit.")
        before = [_file_hash(p) for p in paths]
        documents = [load_export(p) for p in paths]
        report = audit_export(documents[0]) if args.command == "audit" else compare_replay(*documents)
        after = [_file_hash(p) for p in paths]
        if before != after:
            raise AuditInputError("An input changed during the audit; no report was saved.")
        report["provenance"] = {"checkedAt": datetime.now(timezone.utc).isoformat(),
                                "inputs": [{"path": str(p.resolve()), "sha256": h} for p, h in zip(paths, before)],
                                "inputHashesUnchanged": True,
                                "implementation": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                                   for p in (Path(__file__), Path(__file__).with_name("models.py"), Path(__file__).with_name("store.py"))}}
        args.output_dir.mkdir(parents=True, exist_ok=False)
        (args.output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        markdown = render_markdown(report)
        markdown += "\n## Input provenance\n\n" + "\n".join(f"- `{h}` — {_cell(p.name)}" for p, h in zip(paths, before)) + "\n\nInput hashes were unchanged through this audit. Full paths and implementation hashes are in `report.json`.\n"
        (args.output_dir / "report.md").write_text(markdown)
        print(json.dumps({"status": report["status"], "reportDirectory": str(args.output_dir.resolve()), "inputsUnchanged": True}))
        return 0 if report["status"] == "passed" else 1
    except (AuditInputError, OSError) as exc:
        message = str(exc) if isinstance(exc, AuditInputError) else "Input/output filesystem operation failed."
        print(json.dumps({"status": "error", "message": message}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
