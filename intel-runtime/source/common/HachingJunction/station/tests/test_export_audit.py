"""Independent offline export checks against saved acceptance evidence.

Fixtures are read from the canonical workspace or an explicit portable root.
Original fixtures are never rewritten. These
tests establish software record integrity only, not physical execution.
"""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

import pytest

from morph_station import export_audit as audit_module
from morph_station.export_audit import (
    AuditInputError,
    audit_export,
    compare_replay,
    load_export,
)
from morph_station.models import RecordWrite
from morph_station.store import StationStore


WORKSPACE = Path(__file__).resolve().parents[2]
STATION = WORKSPACE / "station"
FIXTURE_ROOT = Path(os.environ.get("MORPH_AUDIT_FIXTURE_ROOT", str(WORKSPACE))).resolve()
M16 = FIXTURE_ROOT / "context/verification/m16-closure-1cf186e8-ce90-4cbb-a953-6611e0bdcb98"
RECOVERED = M16 / "recovered-session-export.json"
REPLAY = M16 / "browser-replay-export.json"
SAMPLE = FIXTURE_ROOT / "station/verification/sample-export.json"


def saved(path=RECOVERED):
    return json.loads(path.read_text(encoding="utf-8"))


def assert_failed(report):
    assert report["status"] == "failed", report
    assert report["issues"], report
    for issue in report["issues"]:
        assert {"severity", "code", "path", "message"} <= issue.keys()
        assert isinstance(issue["message"], str) and issue["message"]


def replace_latest(document, kind, record_id, **changes):
    """Keep current/event/revision copies coherent for domain-negative tests."""
    current = next(r for r in document["records"][kind] if r["id"] == record_id)
    current.update(changes)
    revision = next(
        r for r in document["revisions"]
        if r["recordType"] == kind and r["entityId"] == record_id
        and r["revision"] == current["revision"]
    )
    revision["record"].update(deepcopy(changes))
    event = next(e for e in document["events"] if e["eventId"] == revision["eventId"])
    event["payload"].update(deepcopy(changes))


@pytest.mark.parametrize("path", [RECOVERED, REPLAY, SAMPLE])
def test_saved_acceptance_exports_pass_without_physical_or_media_claims(path):
    document = saved(path)
    before = deepcopy(document)
    result = audit_export(document)
    assert result["status"] == "passed", result
    assert result["metrics"] == document["metrics"]
    assert {key: result["source"][key] for key in ("sessionId", "sourceMode", "configId")} == {
        "sessionId": document["session"]["id"],
        "sourceMode": "simulation",
        "configId": document["session"]["configId"],
    }
    assert result["physicalVerification"] == "not_performed"
    assert result["evidenceFilesVerified"] is False
    assert result["recordCounts"]["cycle"] == len(document["records"]["cycle"])
    assert result["liveMetrics"]["endToEnd"]["denominator"] == 0
    assert result["liveMetrics"]["endToEnd"]["value"] is None
    assert result["liveMetrics"]["filters"]["includedSessionIds"] == []
    assert document == before


def test_recovery_and_late_confirmation_keep_distinct_denominators():
    document = saved()
    result = audit_export(document)
    assert result["status"] == "passed", result
    metrics = result["metrics"]
    assert (metrics["endToEnd"]["numerator"], metrics["endToEnd"]["denominator"]) == (1, 1)
    assert (metrics["physicalExecution"]["numerator"], metrics["physicalExecution"]["denominator"]) == (1, 2)
    assert metrics["attempts"]["failed"] == 1
    assert metrics["retries"] == metrics["recoveredCycles"] == 1
    assert metrics["firstAttemptSuccesses"] == 0
    assert metrics["timings"]["fullCycle"]["valuesMs"] == [10000]
    assert len(document["records"]["correction"]) == 5


def test_global_sequence_gaps_and_grouped_m16_audits_are_valid():
    document = saved()
    sequences = [event["sequence"] for event in document["events"]]
    assert any(right != left + 1 for left, right in zip(sequences, sequences[1:]))
    transitions = [
        (c["entityType"], c["entityId"], c["previousRevision"], c["newRevision"])
        for c in document["records"]["correction"]
    ]
    assert len(set(transitions)) < len(transitions)
    assert audit_export(document)["status"] == "passed"


def test_sample_includes_unknown_outcomes_and_additional_inspection():
    result = audit_export(saved(SAMPLE))
    assert result["status"] == "passed", result
    metrics = result["metrics"]
    assert metrics["cycles"]["total"] == 5
    assert metrics["cycles"]["finished"] == 4
    assert metrics["cycles"]["inProgress"] == 1
    assert metrics["endToEnd"]["value"] == 0.5
    assert metrics["physicalExecution"]["value"] == 0.6
    assert metrics["additionalInspections"] == 1
    assert metrics["firstAttemptSuccesses"] == metrics["recoveredCycles"] == 1
    assert (metrics["detection"]["correct"], metrics["detection"]["checked"],
            metrics["detection"]["totalPopulation"]) == (3, 4, 5)


def test_failed_aborted_and_unverified_remain_finished_and_no_data_is_null(tmp_path):
    store = StationStore(tmp_path / "isolated.sqlite3")
    serial = 0

    def put(kind, record, expected=None):
        nonlocal serial
        serial += 1
        return store.upsert(RecordWrite(
            eventId=f"audit-event-{serial}", recordType=kind,
            record=record, expectedRevision=expected,
        ))["record"]

    put("session", {
        "id": "audit-session", "name": "Offline audit fixture", "sourceMode": "simulation",
        "startedAt": "2026-11-14T12:00:00Z", "configId": "audit-config",
    })
    for outcome in ("failed", "aborted", "unverified", "in_progress"):
        cycle_id = f"audit-{outcome}"
        cycle = put("cycle", {
            "id": cycle_id, "sessionId": "audit-session", "objectId": cycle_id,
            "startedAt": "2026-11-14T12:00:00Z",
        })
        if outcome == "in_progress":
            continue
        attempt = put("attempt", {
            "id": f"{cycle_id}-attempt", "sessionId": "audit-session", "cycleId": cycle_id,
            "ordinal": 1, "startedAt": "2026-11-14T12:00:00Z",
        })
        attempt.pop("revision")
        put("attempt", {**attempt, "outcome": outcome, "endedAt": "2026-11-14T12:00:10Z"}, 1)
        cycle.pop("revision")
        put("cycle", {**cycle, "outcome": outcome, "endedAt": "2026-11-14T12:00:10Z"}, 1)
    result = audit_export(store.export_session("audit-session"))
    assert result["status"] == "passed", result
    metrics = result["metrics"]
    assert metrics["cycles"]["finished"] == metrics["attempts"]["finished"] == 3
    assert metrics["cycles"]["inProgress"] == 1
    for name in ("failed", "aborted", "unverified"):
        assert metrics["cycles"][name] == metrics["attempts"][name] == 1
    assert metrics["endToEnd"]["denominator"] == metrics["physicalExecution"]["denominator"] == 3
    assert metrics["endToEnd"]["value"] == 0
    assert metrics["detection"]["rate"]["denominator"] == 0
    assert metrics["detection"]["rate"]["value"] is None


@pytest.mark.parametrize("location", ["event", "sequence", "current", "revision"])
def test_duplicate_ledger_identities_fail(location):
    document = saved()
    if location == "event":
        document["events"].append(deepcopy(document["events"][0]))
    elif location == "sequence":
        document["events"][1]["sequence"] = document["events"][0]["sequence"]
    elif location == "current":
        document["records"]["attempt"].append(deepcopy(document["records"]["attempt"][0]))
    else:
        document["revisions"].append(deepcopy(document["revisions"][0]))
    assert_failed(audit_export(document))


@pytest.mark.parametrize("mutation", ["schema", "missing_events", "records_type", "bad_timestamp"])
def test_unknown_schema_and_malformed_export_fail_without_crashing(mutation):
    document = saved()
    if mutation == "schema":
        document["schemaVersion"] = 999
    elif mutation == "missing_events":
        del document["events"]
    elif mutation == "records_type":
        document["records"] = []
    else:
        document["session"]["startedAt"] = "2026-11-14T12:00:00"
    assert_failed(audit_export(document))


@pytest.mark.parametrize("mutation", ["event_source", "foreign_session", "missing_frame", "object_mismatch"])
def test_source_and_reference_integrity_fail(mutation):
    document = saved(SAMPLE)
    if mutation == "event_source":
        document["events"][0]["sourceMode"] = "live"
    elif mutation == "foreign_session":
        target = document["records"]["frame"][0]
        replace_latest(document, "frame", target["id"], sessionId="another-session")
    elif mutation == "missing_frame":
        target = document["records"]["inspection"][0]
        replace_latest(document, "inspection", target["id"], frameIds=["missing-frame"])
    else:
        target = document["records"]["reference_label"][0]
        replace_latest(document, "reference_label", target["id"], objectId="different-object")
    assert_failed(audit_export(document))


@pytest.mark.parametrize("mutation", ["ordinal", "retry_target", "successful_confirmation"])
def test_attempt_chain_and_confirmation_requirements_fail(mutation):
    document = saved(SAMPLE)
    attempts = document["records"]["attempt"]
    if mutation == "ordinal":
        target = next(a for a in attempts if a["ordinal"] == 2)
        replace_latest(document, "attempt", target["id"], ordinal=3)
    elif mutation == "retry_target":
        target = next(a for a in attempts if a["ordinal"] == 2)
        replace_latest(document, "attempt", target["id"], retryOfAttemptId=target["id"])
    else:
        target = next(a for a in attempts if a["outcome"] == "successful")
        replace_latest(document, "attempt", target["id"], confirmationId=None)
    assert_failed(audit_export(document))


def test_wrong_bin_cannot_support_an_otherwise_correct_cycle():
    document = saved(SAMPLE)
    target = next(c for c in document["records"]["cycle"] if c["outcome"] == "correct")
    replace_latest(document, "cycle", target["id"], observedDestination="defective_bin")
    assert_failed(audit_export(document))


def test_omitted_grouped_audit_field_is_detected():
    document = saved()
    omitted = next(c for c in document["records"]["correction"]
                   if c["entityType"] == "cycle" and c["field"] == "observedDestination")
    document["records"]["correction"] = [c for c in document["records"]["correction"] if c["id"] != omitted["id"]]
    document["events"] = [e for e in document["events"]
                          if not (e["recordType"] == "correction" and e["entityId"] == omitted["id"])]
    document["revisions"] = [r for r in document["revisions"]
                             if not (r["recordType"] == "correction" and r["entityId"] == omitted["id"])]
    assert_failed(audit_export(document))


def test_audit_previous_value_must_match_original_revision():
    document = saved()
    target = document["records"]["correction"][0]
    replace_latest(document, "correction", target["id"], previousValue="fabricated-old-value")
    assert_failed(audit_export(document))


def test_missing_correction_scope_is_a_reported_failure():
    document = saved()
    del document["records"]["correction"][0]["cycleId"]
    assert_failed(audit_export(document))


def test_erased_audit_cannot_be_hidden_by_relabeling_finished_updates():
    document = saved()
    document["records"]["correction"] = []
    document["events"] = [e for e in document["events"] if e["recordType"] != "correction"]
    document["revisions"] = [r for r in document["revisions"] if r["recordType"] != "correction"]
    for event in document["events"]:
        if event["type"].endswith(".corrected"):
            event["type"] = event["type"].replace(".corrected", ".updated")
    # Offline evidence acceptance must retain an attributed transition after a
    # finished outcome, even where an older ingestion API allowed that update.
    assert_failed(audit_export(document))


def test_historical_immutable_object_change_is_detected():
    document = saved()
    for revision in document["revisions"]:
        if revision["recordType"] == "cycle" and revision["revision"] == 1:
            revision["record"]["objectId"] = "another-historical-object"
    for event in document["events"]:
        if event["recordType"] == "cycle" and event["entityRevision"] == 1:
            event["payload"]["objectId"] = "another-historical-object"
    assert_failed(audit_export(document))


def test_missing_reference_in_prior_revision_is_not_hidden_by_current_state():
    document = saved()
    for revision in document["revisions"]:
        if revision["recordType"] == "cycle" and revision["revision"] == 1:
            revision["record"]["inspectionId"] = "never-existed"
    for event in document["events"]:
        if event["recordType"] == "cycle" and event["entityRevision"] == 1:
            event["payload"]["inspectionId"] = "never-existed"
    assert_failed(audit_export(document))


@pytest.mark.parametrize("kind,field,value", [
    ("attempt", "ordinal", True),
    ("attempt", "ordinal", "1"),
    ("inspection", "score", "0.2"),
    ("confirmation", "physicalSuccess", "true"),
])
def test_scalar_types_are_not_silently_coerced(kind, field, value):
    document = saved(SAMPLE)
    target = document["records"][kind][0]
    # Keep all copies of the original scalar coherent so equality checks do
    # not mask schema coercion of boolean/string values into numbers/booleans.
    target[field] = value
    for revision in document["revisions"]:
        if revision["recordType"] == kind and revision["entityId"] == target["id"]:
            revision["record"][field] = value
    for event in document["events"]:
        if event["recordType"] == kind and event["entityId"] == target["id"]:
            event["payload"][field] = value
    assert_failed(audit_export(document))


@pytest.mark.parametrize("section,field", [
    ("events", "recordType"),
    ("events", "type"),
    ("revisions", "recordType"),
])
def test_malformed_unhashable_envelope_values_fail_without_crashing(section, field):
    document = saved()
    document[section][0][field] = []
    assert_failed(audit_export(document))


@pytest.mark.parametrize("mutation", ["event_payload", "latest_revision", "metric"])
def test_cross_section_or_metric_disagreement_fails(mutation):
    document = saved()
    if mutation == "event_payload":
        document["events"][0]["payload"]["name"] = "Tampered event only"
    elif mutation == "latest_revision":
        document["session"]["name"] = "Tampered current only"
    else:
        document["metrics"]["endToEnd"]["denominator"] = 99
    assert_failed(audit_export(document))


def test_paired_replay_only_ignores_top_level_exported_at():
    left, right = saved(), saved(REPLAY)
    assert left["exportedAt"] != right["exportedAt"]
    result = compare_replay(left, right)
    assert result["status"] == "passed", result
    assert result["equivalent"] is True
    modified = deepcopy(right)
    modified["session"]["name"] = "Changed history"
    result = compare_replay(left, modified)
    assert_failed(result)
    assert result["equivalent"] is False


def test_even_coherent_history_changes_are_not_replay_equivalent():
    left = saved(SAMPLE)
    right = deepcopy(left)
    session_id = right["session"]["id"]
    right["session"]["name"] = "Another descriptive session name"
    for revision in right["revisions"]:
        if revision["recordType"] == "session" and revision["entityId"] == session_id:
            revision["record"]["name"] = right["session"]["name"]
    for event in right["events"]:
        if event["recordType"] == "session" and event["entityId"] == session_id:
            event["payload"]["name"] = right["session"]["name"]
    assert audit_export(right)["status"] == "passed"
    comparison = compare_replay(left, right)
    assert_failed(comparison)
    assert comparison["equivalent"] is False


@pytest.mark.parametrize("text", [
    '{"schemaVersion":1,"schemaVersion":1}',
    '{"nested":{"value":1,"value":2}}',
    '{"value":NaN}',
    '{"value":Infinity}',
    '{"value":-Infinity}',
    '{"value":1e10000}',
    '{"unfinished":',
    '{"value":' + "1" * 5000 + '}',
])
def test_strict_loader_rejects_ambiguous_or_non_json_input(tmp_path, text):
    path = tmp_path / "invalid.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(AuditInputError):
        load_export(path)


def test_input_limit_applies_to_loader_and_cli_before_report_creation(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_module, "MAX_INPUT_BYTES", 128)
    source = tmp_path / "oversized.json"
    source.write_text('{"padding":"' + "a" * 128 + '"}', encoding="utf-8")
    with pytest.raises(AuditInputError):
        load_export(source)
    output = tmp_path / "should-not-exist"
    assert audit_module.main(["audit", str(source), "--output-dir", str(output)]) == 2
    assert not output.exists()


def test_audit_does_not_construct_a_database(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("An offline audit must not initialize StationStore")

    monkeypatch.setattr(StationStore, "__init__", forbidden)
    assert audit_export(saved())["status"] == "passed"


def test_report_omits_untrusted_prompts_outputs_and_audit_prose():
    document = saved()
    model = document["records"]["model_run"][0]
    prompt_marker = "PRIVATE_PROMPT_CONTENT_MUST_NOT_LEAVE_SOURCE"
    output_marker = "UNTRUSTED_MODEL_OUTPUT_MUST_NOT_LEAVE_SOURCE"
    reason_marker = "AUDIT_REASON_CONTENT_MUST_NOT_LEAVE_SOURCE"
    model["input"] = {"instruction": prompt_marker}
    for revision in document["revisions"]:
        if revision["recordType"] == "model_run" and revision["entityId"] == model["id"]:
            revision["record"]["input"] = deepcopy(model["input"])
    for event in document["events"]:
        if event["recordType"] == "model_run" and event["entityId"] == model["id"]:
            event["payload"]["input"] = deepcopy(model["input"])
    replace_latest(document, "model_run", model["id"], output={"text": output_marker})
    correction = document["records"]["correction"][0]
    replace_latest(document, "correction", correction["id"], reason=reason_marker)
    report = audit_export(document)
    assert report["status"] == "passed", report
    rendered = json.dumps(report) + audit_module.render_markdown(report)
    assert all(marker not in rendered for marker in (prompt_marker, output_marker, reason_marker))


def test_markdown_provenance_is_plain_text_and_cannot_inject_markup():
    document = saved(SAMPLE)
    target = document["records"]["model_run"][0]
    hostile = '\n# Forged result\n[External](https://example.invalid/collect) | <script>alert(1)</script> `code`'
    target["provider"] = hostile
    for revision in document["revisions"]:
        if revision["recordType"] == "model_run" and revision["entityId"] == target["id"]:
            revision["record"]["provider"] = hostile
    for event in document["events"]:
        if event["recordType"] == "model_run" and event["entityId"] == target["id"]:
            event["payload"]["provider"] = hostile
    report = audit_export(document)
    assert report["status"] == "passed", report
    markdown = audit_module.render_markdown(report)
    assert "\n# Forged result" not in markdown
    assert "[External](" not in markdown
    assert "<script>" not in markdown
    assert "`code`" not in markdown


def run_cli(*arguments):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(STATION)
    return subprocess.run(
        [sys.executable, "-m", "morph_station.export_audit", *map(str, arguments)],
        cwd=WORKSPACE, env=env, capture_output=True, text=True, timeout=30,
        check=False,
    )


@pytest.mark.parametrize("mode", ["audit", "replay"])
def test_cli_writes_new_reports_and_preserves_exact_input_bytes(tmp_path, mode):
    paths = [RECOVERED] if mode == "audit" else [RECOVERED, REPLAY]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    output = tmp_path / f"{mode}-report"
    result = run_cli(mode, *paths, "--output-dir", output)
    assert result.returncode == 0, (result.stdout, result.stderr)
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    markdown = (output / "report.md").read_text(encoding="utf-8")
    assert markdown.strip()
    assert "simulation" in markdown.lower()
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths} == before


def test_cli_invalid_content_has_failure_report_and_exit_one(tmp_path):
    document = saved()
    document["schemaVersion"] = 999
    source = tmp_path / "unsupported.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    output = tmp_path / "failed-audit"
    result = run_cli("audit", source, "--output-dir", output)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert_failed(json.loads((output / "report.json").read_text(encoding="utf-8")))
    assert (output / "report.md").is_file()


def test_cli_existing_output_is_not_overwritten(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "report.json"
    sentinel.write_text("existing owner data", encoding="utf-8")
    result = run_cli("audit", RECOVERED, "--output-dir", output)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert sentinel.read_text(encoding="utf-8") == "existing owner data"
    assert sorted(p.name for p in output.iterdir()) == ["report.json"]


def test_cli_input_parse_error_exits_two(tmp_path):
    source = tmp_path / "ambiguous.json"
    source.write_text('{"duplicate":1,"duplicate":2}', encoding="utf-8")
    result = run_cli("audit", source, "--output-dir", tmp_path / "unused-report")
    assert result.returncode == 2, (result.stdout, result.stderr)
