"""Coherent bounded evidence assembled without changing canonical station records."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

from .analysis_models import CONTEXT_VERSION, Selection
from .store import ALL_KINDS, StationStore, StoreError, canonical, fingerprint, now

MAX_CONTEXT_BYTES = 40 * 1024
MAX_FACTS = 200
CONFIG_FIELDS = ("protocolVersion", "population", "cameraPreprocessing", "detectorThreshold",
                 "policy", "recovery", "robotWorkspaceCalibration", "hardwareDevicePrecision", "timingBoundaries")
DETAIL_KINDS = {"cycle": "cycle", "attempts": "attempt", "frames": "frame", "inspections": "inspection",
                "modelRuns": "model_run", "utterances": "utterance", "decisions": "decision",
                "executions": "execution", "referenceLabels": "reference_label", "confirmations": "confirmation",
                "corrections": "correction", "evidence": "evidence"}


def opaque(prefix, value):
    return prefix + hashlib.sha256(canonical(value).encode()).hexdigest()[:16]


def reference(kind, record, field="", revision=None):
    ref = {"recordType": kind, "entityId": record["id"], "revision": revision or record["revision"],
           "sessionId": record.get("sessionId", record["id"]), "fieldPath": field}
    if record.get("cycleId") or kind == "cycle":
        ref["cycleId"] = record.get("cycleId", record["id"])
    return ref


def cycle_citation_requirements(context):
    """Select bounded current-record witnesses, never historical outcome substitutes."""
    requirements = {"requiredFactIds": [], "metricFactIds": {}}
    if context["kind"] != "cycle_explanation":
        return requirements
    current = {}
    for fact in context["facts"]:
        ref = fact["sourceRefs"][0]
        key = (ref["recordType"], ref["entityId"])
        if key not in current or ref["revision"] > current[key]["sourceRefs"][0]["revision"]:
            current[key] = fact
    cycles = [fact for (kind, _), fact in current.items() if kind == "cycle"]
    attempts = sorted((fact for (kind, _), fact in current.items() if kind == "attempt"),
                      key=lambda fact: (fact["value"].get("ordinal", 0), fact["sourceRefs"][0]["entityId"]))
    first_and_last = attempts[:1] + attempts[-1:]
    failed = [fact for fact in attempts[:-1] if fact["value"].get("outcome") == "failed"]
    recovered = context["evidenceFlags"]["hasRecoveredCycle"]
    required = set()
    for metric in context["metrics"]:
        witnesses = []
        if metric["key"] == "firstAttemptSuccesses":
            witnesses = cycles + first_and_last
        elif metric["key"] == "recoveredCycles" and metric["value"] > 0:
            witnesses = cycles + failed[:1] + attempts[-1:]
        elif metric["key"] == "retries" and metric["value"] > 0:
            witnesses = first_and_last
        if witnesses:
            requirements["metricFactIds"][metric["metricId"]] = sorted({fact["factId"] for fact in witnesses})
            if recovered:
                required.update(requirements["metricFactIds"][metric["metricId"]])
    late_ids = set(context["evidenceFlags"]["lateConfirmationRecordIds"])
    late = [fact for (kind, entity_id), fact in current.items() if kind == "confirmation" and entity_id in late_ids]
    if late:
        required.update(fact["factId"] for fact in late[:1] + cycles + attempts[-1:])
    corrections = [fact for (kind, _), fact in current.items() if kind == "correction"]
    if corrections:
        # One actual outcome correction is a bounded audit witness; the full audit remains captured.
        correction = next((fact for fact in corrections if fact["value"].get("field") == "outcome"), corrections[0])
        required.add(correction["factId"])
    requirements["requiredFactIds"] = sorted(required)
    return requirements


def stratified_cycles(cycles, recovered_ids=frozenset()):
    groups = defaultdict(deque)
    for record in sorted(cycles, key=lambda r: (r["startedAt"], r["id"])):
        category = "recovered" if record["id"] in recovered_ids else record["outcome"]
        groups[(record["sessionId"], category)].append(record)
    result = []
    while any(groups.values()):
        for outcome in sorted(groups):
            if groups[outcome]:
                result.append(groups[outcome].popleft())
    return result


class ContextBuilder:
    def __init__(self, store: StationStore, directory: Path):
        self.store = store
        self.directory = directory

    def _spec(self, selection, sessions):
        if selection.kind != "session_comparison":
            return None
        path = self.directory / "comparison-specs.json"
        specifications = {}
        if path.is_file():
            try:
                specifications = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                raise StoreError(503, "The server comparison specifications cannot be read")
        if not isinstance(specifications, dict):
            raise StoreError(503, "The server comparison specifications must be a mapping")
        spec = specifications.get(selection.comparisonSpecId or "")
        if selection.comparisonSpecId and spec is None:
            raise StoreError(422, "Unknown server comparison specification")
        reasons, mismatches = [], []
        if not spec:
            reasons.append("No reviewed comparison specification is available for these sessions.")
        else:
            if not isinstance(spec, dict) or not isinstance(spec.get("sessions", {}), dict):
                raise StoreError(503, "The selected server comparison specification has an invalid shape")
            compared = spec.get("comparedVariable")
            if compared not in CONFIG_FIELDS:
                reasons.append("The specification does not declare a supported compared variable.")
            metadata = spec.get("sessions", {})
            left, right = (metadata.get(sid, {}) for sid in selection.sessionIds)
            if not isinstance(left, dict) or not isinstance(right, dict):
                raise StoreError(503, "Reviewed session comparison metadata must be a mapping")
            for session in sessions:
                item = metadata.get(session["id"], {})
                if item.get("configId") != session.get("configId"):
                    reasons.append("Reviewed configuration metadata does not match a selected session.")
            for field in CONFIG_FIELDS:
                if any(not isinstance(item.get(field), str) or not item[field].strip() for item in (left, right)):
                    reasons.append("Missing or invalid reviewed comparison metadata: " + field + ".")
                elif field != compared and left[field] != right[field]:
                    mismatches.append(field)
        state = "incompatible" if mismatches else "unknown" if reasons else "compatible"
        if mismatches:
            reasons.append("Non-comparable configuration fields differ: " + ", ".join(mismatches) + ".")
        return {"state": state, "comparisonSpecId": selection.comparisonSpecId, "reasons": reasons,
                "comparedVariable": spec.get("comparedVariable") if spec else None,
                "specificationDigest": fingerprint(spec) if spec else None,
                "interpretationPolicy": "Descriptive evidence only; no causal or winner claims."}

    def build(self, selection: Selection):
        # Every source read below belongs to this one SQLite read transaction.
        with self.store._connection() as db:
            sessions = [self.store._get(db, "session", sid) for sid in selection.sessionIds]
            if any(session["sourceMode"] != selection.sourceMode for session in sessions):
                raise StoreError(422, "Selected sessions do not share the requested source mode")
            watermark = db.execute("SELECT COALESCE(MAX(sequence),0) FROM events").fetchone()[0]
            compatibility = self._spec(selection, sessions)
            details, populations, metrics = [], {}, {}
            if selection.kind == "cycle_explanation":
                detail = self.store._cycle_detail(db, selection.cycleId)
                if detail["cycle"]["sessionId"] != selection.sessionIds[0]:
                    raise StoreError(422, "The selected cycle does not belong to the selected session")
                self._expand_related(db, detail)
                details = [detail]
                populations[selection.sessionIds[0]] = [detail["cycle"]]
                metrics[selection.sessionIds[0]] = self.store._metrics(
                    db, selection.sessionIds[0], True, cycle_ids={selection.cycleId})
                metrics[selection.sessionIds[0]]["_attemptRecords"] = detail["attempts"]
                digest_records = details
            else:
                digest_records = {}
                for sid in selection.sessionIds:
                    populations[sid] = self.store._list(db, "cycle", sid)
                    metrics[sid] = self.store._metrics(db, sid, True)
                    metrics[sid]["_attemptRecords"] = self.store._list(db, "attempt", sid)
                    # All eligible records contribute to the digest and arithmetic, before sampling.
                    digest_records[sid] = {kind: self.store._list(db, kind, sid)
                                           for kind in sorted(ALL_KINDS) if kind != "session"}
                recovered_ids = set()
                for sid, cycles in populations.items():
                    grouped_attempts = defaultdict(list)
                    for attempt in metrics[sid]["_attemptRecords"]:
                        grouped_attempts[attempt["cycleId"]].append(attempt)
                    for cycle in cycles:
                        ordered = sorted(grouped_attempts[cycle["id"]], key=lambda attempt: attempt["ordinal"])
                        if cycle["outcome"] == "correct" and any(attempt["outcome"] == "failed" for attempt in ordered[:-1]):
                            recovered_ids.add(cycle["id"])
                candidates = stratified_cycles([c for rows in populations.values() for c in rows], recovered_ids)[:50]
                details = [self.store._cycle_detail(db, cycle["id"]) for cycle in candidates]
            digest = fingerprint({"contextVersion": CONTEXT_VERSION, "selection": selection.model_dump(),
                                  "sessions": sessions, "records": digest_records, "compatibility": compatibility})
            all_cycles = [cycle for cycles in populations.values() for cycle in cycles]
            cycle_map = {cycle["id"]: cycle for cycle in all_cycles}
            corrections = [record for sid in selection.sessionIds for record in self.store._list(db, "correction", sid)
                           if selection.cycleId is None or record.get("cycleId") == selection.cycleId]
            confirmations = [record for sid in selection.sessionIds for record in self.store._list(db, "confirmation", sid)
                             if selection.cycleId is None or record.get("cycleId") == selection.cycleId]
            late_confirmations = [record for record in confirmations if cycle_map.get(record["cycleId"], {}).get("endedAt")
                                  and datetime.fromisoformat(record["confirmedAt"]) > datetime.fromisoformat(cycle_map[record["cycleId"]]["endedAt"])]
            evidence_flags = {
                "hasCorrections": bool(corrections),
                "hasLateConfirmation": bool(late_confirmations),
                "hasRecoveredCycle": any(data["recoveredCycles"] > 0 for data in metrics.values()),
                "hasRetainedFailedAttempt": any(record["outcome"] == "failed" for data in metrics.values() for record in data["_attemptRecords"]),
                "hasHistoricalRevisions": any(cycle["revision"] > 1 for cycle in all_cycles),
                "correctionRecordIds": [record["id"] for record in corrections],
                "lateConfirmationRecordIds": [record["id"] for record in late_confirmations],
                "definitions": {"hasCorrections": "Actual correction records exist; ordinary lifecycle revisions do not establish a correction.",
                                "hasLateConfirmation": "A saved confirmation time is later than the corresponding persisted cycle end.",
                                "hasRecoveredCycle": "The canonical recovered-cycle count is positive: a correct cycle retains a preceding failed attempt.",
                                "hasRetainedFailedAttempt": "At least one current attempt record has failed outcome.",
                                "hasHistoricalRevisions": "A selected cycle has earlier lifecycle revisions; this alone implies neither correction nor late confirmation."},
            }
            context = self._assemble(selection, sessions, details, populations, metrics, compatibility, digest, watermark, evidence_flags)
            while selection.kind == "session_comparison" and details and (
                    len(context["facts"]) > MAX_FACTS or len(canonical(context).encode()) > MAX_CONTEXT_BYTES):
                details.pop()
                context = self._assemble(selection, sessions, details, populations, metrics, compatibility, digest, watermark, evidence_flags)
            if len(context["facts"]) > MAX_FACTS or len(canonical(context).encode()) > MAX_CONTEXT_BYTES:
                raise StoreError(413, "too_large: required evidence exceeds the bounded analysis context")
            return context

    def _expand_related(self, db, detail):
        """Follow supplied record IDs, including session-scoped model evidence, never URLs."""
        session_id = detail["cycle"]["sessionId"]

        def include(kind, collection, identifiers):
            existing = {record["id"] for record in detail[collection]}
            for identifier in sorted(set(identifiers) - existing):
                record = self.store._get(db, kind, identifier)
                if record["sessionId"] != session_id:
                    raise StoreError(409, "Referenced evidence belongs to a different session")
                detail[collection].append(record)

        include("decision", "decisions", [record["decisionId"] for record in detail["executions"] if record.get("decisionId")])
        include("model_run", "modelRuns", [record["modelRunId"] for record in detail["inspections"] + detail["decisions"]])
        include("frame", "frames", [identifier for record in detail["inspections"] + detail["decisions"] + detail["modelRuns"]
                                      for identifier in record.get("frameIds", [])])
        include("evidence", "evidence", [record["evidenceId"] for record in detail["frames"]])

    def _assemble(self, selection, sessions, details, populations, metrics, compatibility, digest, watermark, evidence_flags):
        facts, metric_rows, gaps, targets, excerpts, revisions = [], [], [], [], [], []

        def add_fact(kind, record, fields, text, revision=None):
            value = {key: record.get(key) for key in fields}
            refs = [reference(kind, record, key, revision) for key in fields]
            fact = {"factId": "f" + str(len(facts) + 1).zfill(3), "text": text, "value": value, "sourceRefs": refs}
            facts.append(fact)
            return fact

        for session in sessions:
            add_fact("session", session, ["sourceMode", "configId"], "Recorded session source and configuration identifier.")
            revisions.append(reference("session", session))
        for detail in details:
            cycle = detail["cycle"]
            if selection.kind == "session_comparison":
                add_fact("cycle", cycle, ["outcome", "startedAt", "endedAt"], "Recorded exemplar cycle outcome and timing.")
                revisions.append(reference("cycle", cycle))
                continue
            for collection, kind in DETAIL_KINDS.items():
                records = [cycle] if collection == "cycle" else detail[collection]
                for record in records:
                    # Labels and observation fields remain exact; free-form provider or user prose is isolated below.
                    fields = {
                        "cycle": ["outcome", "startedAt", "endedAt", "commandedDestination", "observedDestination", "referenceLabelId", "inspectionId", "confirmationId"],
                        "attempt": ["ordinal", "outcome", "retryOfAttemptId", "confirmationId", "startedAt", "endedAt"],
                        "inspection": ["classification", "score", "threshold", "frameIds", "modelRunId", "additionalInspectionOfId", "requestedAt", "completedAt"],
                        "reference_label": ["quality", "authorId", "method", "evidenceIds", "createdAt"],
                        "confirmation": ["source", "physicalSuccess", "observedDestination", "attemptId", "confirmedAt", "evidenceIds", "authorId"],
                        "correction": ["entityType", "entityId", "field", "previousValue", "newValue", "createdAt", "authorId"],
                        "model_run": ["provider", "modelId", "frameIds", "requestedAt", "completedAt", "latencyMs", "device", "precision"],
                        "frame": ["cameraId", "capturedAt", "receivedAt", "width", "height", "evidenceId"],
                        "decision": ["kind", "frameIds", "modelRunId", "offeredChoices", "selectedChoice", "stateVersion", "goalVersion", "requestedAt", "completedAt", "accepted"],
                        "execution": ["attemptId", "taskId", "policyId", "decisionId", "requestedAt", "acknowledgedAt", "finishedAt", "status"],
                        "evidence": ["mediaType", "sha256", "size", "capturedAt"],
                        "utterance": ["source", "provider", "modelId", "startedAt", "completedAt", "status", "language"],
                    }[kind]
                    fields = [key for key in fields if key in record]
                    add_fact(kind, record, fields, "Recorded " + kind.replace("_", " ") + " evidence.")
                    revisions.append(reference(kind, record))
                    if kind in {"model_run", "utterance", "attempt", "correction", "decision", "execution"}:
                        for key in ("output", "error", "text", "retryReason", "reason", "rejectionReason"):
                            if record.get(key):
                                # Deliberately not a fact or an instruction. Never send images or follow embedded links.
                                from .analysis_provider import sanitize
                                excerpt = sanitize(str(record[key]))[:500]
                                excerpts.append({"untrusted": True, "sourceRef": reference(kind, record, key), "text": excerpt})
            for revision in detail["revisions"]:
                current = next((r for r in revisions if r["recordType"] == revision["recordType"]
                                and r["entityId"] == revision["entityId"]), None)
                if current and revision["revision"] != current["revision"]:
                    record = dict(revision["record"], revision=revision["revision"])
                    fields = [key for key in ("outcome", "confirmationId", "endedAt") if key in record]
                    if fields:
                        add_fact(revision["recordType"], record, fields,
                                 "Historical revision retained for lifecycle record history.", revision["revision"])
                        revisions.append(reference(revision["recordType"], record))
            targets.append({"id": "r" + str(len(targets) + 1).zfill(3), "label": "Open the saved cycle trace",
                            "sourceRefs": [reference("cycle", cycle)]})
            if not cycle.get("referenceLabelId"):
                gaps.append({"key": "missing_reference_label", "text": "The selected cycle has no linked independent reference label."})
            if not detail["confirmations"]:
                gaps.append({"key": "missing_confirmation", "text": "No physical confirmation is recorded for the selected cycle."})
        for session in sessions:
            sid = session["id"]
            data = metrics[sid]
            cycles = populations[sid]
            finished_ids = [r["id"] for r in cycles if r["outcome"] != "in_progress"]
            unfinished_ids = [r["id"] for r in cycles if r["outcome"] == "in_progress"]
            ratio_fields = [("endToEnd", "Correct finished cycles"), ("physicalExecution", "Successful finished attempts")]
            for key, label in ratio_fields:
                item = data[key]
                eligible_rows = data["_attemptRecords"] if key == "physicalExecution" else cycles
                metric_rows.append({"metricId": opaque("m_", [sid, key]), "key": key, "label": label, "sessionId": sid,
                                    "value": item["value"], "numerator": item["numerator"], "denominator": item["denominator"],
                                    "definition": item["definition"], "filters": data["filters"],
                                    "includedIds": [r["id"] for r in eligible_rows if r["outcome"] != "in_progress"],
                                    "excludedIds": [r["id"] for r in eligible_rows if r["outcome"] == "in_progress"]})
            for key, label in [("firstAttemptSuccesses", "First-attempt successes"), ("recoveredCycles", "Recovered cycles"),
                               ("retries", "Retries"), ("additionalInspections", "Additional inspections")]:
                metric_rows.append({"metricId": opaque("m_", [sid, key]), "key": key, "label": label, "sessionId": sid,
                                    "value": data[key], "definition": label + " from the canonical metric calculator.",
                                    "includedIds": [r["id"] for r in cycles], "excludedIds": []})
            detection = data["detection"]
            metric_rows.append({"metricId": opaque("m_", [sid, "detection"]), "key": "detection", "label": "Detection coverage",
                                "sessionId": sid, "value": detection, "definition": "Independent reference-labeled decision inspections only.",
                                "includedIds": [r["id"] for r in cycles if r.get("referenceLabelId") and r.get("inspectionId")],
                                "excludedIds": [r["id"] for r in cycles if not (r.get("referenceLabelId") and r.get("inspectionId"))]})
            timing = data["timings"]["fullCycle"]
            metric_rows.append({"metricId": opaque("m_", [sid, "fullCycle"]), "key": "fullCycle", "label": "Full cycle timing",
                                "sessionId": sid, "value": timing, "definition": timing["method"],
                                "includedIds": [record["id"] for record in cycles if record.get("endedAt")],
                                "excludedIds": [record["id"] for record in cycles if not record.get("endedAt")]})
            if detection["checked"] < detection["totalPopulation"]:
                gaps.append({"key": "reference_coverage_" + str(selection.sessionIds.index(sid) + 1), "text": "Detection coverage does not include every cycle in the selected session."})
        gaps.append({"key": "causal_evidence_unavailable", "text": "Recorded outcomes and provider observations do not establish physical causes."})
        if compatibility and compatibility["state"] != "compatible":
            gaps.append({"key": "comparison_compatibility", "text": "Comparison compatibility is " + compatibility["state"] + "; show descriptive tables without improvement or winner claims."})
        all_cycles = [c for rows in populations.values() for c in rows]
        shown = [d["cycle"]["id"] for d in details]
        deltas = []
        if compatibility and compatibility["state"] == "compatible":
            baseline, adaptive = metrics[selection.baselineSessionId], metrics[selection.adaptiveSessionId]
            for key in ("endToEnd", "physicalExecution"):
                left, right = baseline[key]["value"], adaptive[key]["value"]
                deltas.append({"key": key, "percentagePoints": None if left is None or right is None else (right - left) * 100,
                               "definition": "Adaptive ratio minus baseline ratio; descriptive, not a causal effect."})
        # IDs are opaque within this immutable context. SourceRefs and the digest carry durable identity.
        for ordinal, metric in enumerate(metric_rows, 1):
            metric["metricId"] = "m" + str(ordinal).zfill(3)
            metric["unit"] = ("ratio" if metric["key"] in {"endToEnd", "physicalExecution"} else
                              "duration_samples_ms" if metric["key"] == "fullCycle" else
                              "structured_detection_counts_and_ratios" if metric["key"] == "detection" else "count")
        context = {"contextVersion": CONTEXT_VERSION, "kind": selection.kind, "sourceMode": selection.sourceMode,
                "sessionIds": selection.sessionIds, "cycleId": selection.cycleId, "asOf": now(),
                "sourceEventWatermark": watermark, "contentDigest": digest, "facts": facts, "metrics": metric_rows,
                "knownGaps": list({gap["key"]: gap for gap in gaps}.values()), "reviewTargets": targets[:3],
                "untrustedExcerpts": excerpts, "recordRevisions": revisions,
                "evidenceFlags": evidence_flags,
                "sampling": {"method": "Deterministic session and outcome-stratified exemplars, including recovery, after full-population arithmetic",
                             "shownCycleIds": shown, "totalCycles": len(all_cycles),
                             "omittedCycleIds": sorted(c["id"] for c in all_cycles if c["id"] not in shown)},
                "compatibility": compatibility, "descriptiveDeltas": deltas,
                "comparisonRoles": {"baselineSessionId": selection.baselineSessionId,
                                    "adaptiveSessionId": selection.adaptiveSessionId} if compatibility else None}
        context["citationRequirements"] = cycle_citation_requirements(context)
        return context
