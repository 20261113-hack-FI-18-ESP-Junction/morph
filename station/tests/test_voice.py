"""Offline speech boundary regressions. No provider, microphone or robot access."""
from concurrent.futures import ThreadPoolExecutor
import io
import json
import urllib.error

import pytest

from morph_station.voice import SCRIBE_MODEL, VoiceError, VoiceJournal, issue_scribe_token, scribe_connection_options

T0 = "2026-11-14T20:00:00Z"
T1 = "2026-11-14T20:00:01Z"
T2 = "2026-11-14T20:00:02Z"
T3 = "2026-11-14T20:00:03Z"
T4 = "2026-11-14T20:00:04Z"
T5 = "2026-11-14T20:00:05Z"


@pytest.fixture
def journal(tmp_path):
    return VoiceJournal(tmp_path / "voice.sqlite3")


def start(journal, uid="u1"):
    journal.start(uid, "session1", T0)
    return journal.receive(uid, uid + ":session", {"message_type": "session_started",
        "session_id": "provider-" + uid, "config": {"model_id": SCRIBE_MODEL,
        "audio_format": "pcm_16000", "sample_rate": 16000, "commit_strategy": "manual"}}, T1)


def committed(journal, uid="u1", index=0, text="Pause after this cycle", event_id=None, at=T3):
    return journal.receive(uid, event_id or uid + ":commit:" + str(index),
        {"message_type": "committed_transcript", "text": text}, at, segment_index=index)


def finalized(journal, uid="u1"):
    start(journal, uid)
    journal.release(uid, T2)
    committed(journal, uid)
    return journal.finalize(uid, 1, uid + ":commit:0", T4)


def test_single_utterance_finalizes_only_after_explicit_release_and_commit(journal):
    start(journal)
    for n in range(3):
        result = journal.receive("u1", f"partial:{n}", {"message_type": "partial_transcript", "text": "Pause"}, T1)
        assert result["status"] == "capturing" and result["goalRequestId"] is None
    committed(journal, at=T1)
    with pytest.raises(VoiceError, match="released"):
        journal.finalize("u1", 1, "u1:commit:0", T2)
    journal.release("u1", T2)
    with pytest.raises(VoiceError, match="after release"):
        journal.finalize("u1", 1, "u1:commit:0", T3)
    assert journal.get("u1")["readyForGoalSelection"] is False


def test_finalization_retries_and_late_enrichment_preserve_one_goal_and_original_text(journal):
    first = finalized(journal)
    assert first["newlyFinalized"] is True
    again = journal.finalize("u1", 1, "u1:commit:0", T5)
    assert again["newlyFinalized"] is False and again["goalRequestId"] == first["goalRequestId"]
    enriched = journal.receive("u1", "u1:timestamps", {"message_type": "committed_transcript_with_timestamps",
        "text": "Pause after this cycle", "language_code": "en", "words": [{"text": "Pause", "start": 0, "end": .2}]},
        T5, segment_index=0)
    assert enriched["text"] == first["text"]
    assert enriched["eventDisposition"] == "enrichment_only"
    assert enriched["goalRequestId"] == first["goalRequestId"]
    assert len(enriched["segments"][0]["enrichments"]) == 1
    assert journal.receive("u1", "u1:timestamps", {"message_type": "committed_transcript_with_timestamps",
        "text": "Pause after this cycle", "language_code": "en", "words": [{"text": "Pause", "start": 0, "end": .2}]},
        "2026-11-14T20:00:06Z", segment_index=0)["duplicate"] is True
    assert journal.get("u1")["eventCount"] == 3


def test_segment_gaps_cannot_finalize_and_same_text_in_distinct_segments_is_preserved(journal):
    start(journal)
    committed(journal, index=0, text="one", at=T1)
    journal.release("u1", T2)
    committed(journal, index=2, text="one", at=T3)
    with pytest.raises(VoiceError, match="contiguous"):
        journal.finalize("u1", 3, "u1:commit:2", T4)
    committed(journal, index=1, text="one", at=T3)
    result = journal.finalize("u1", 3, "u1:commit:2", T4)
    assert result["text"] == "one one one"
    assert [s["index"] for s in result["segments"]] == [0, 1, 2]


def test_conflicting_event_and_segment_identities_do_not_replace_original(journal):
    start(journal)
    committed(journal)
    with pytest.raises(VoiceError, match="different content"):
        committed(journal, text="resume")
    result = committed(journal, text="resume", event_id="new-id")
    assert result["status"] == "rejected"
    assert result["rejectionReason"] == "conflicting_committed_segment"
    assert result["text"] == "Pause after this cycle"


def test_concurrent_finalize_and_restart_keep_one_stable_goal_identity(journal):
    start(journal); journal.release("u1", T2); committed(journal)
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: journal.finalize("u1", 1, "u1:commit:0", T4), range(8)))
    assert sum(item["newlyFinalized"] for item in results) == 1
    assert len({item["goalRequestId"] for item in results}) == 1
    reopened = VoiceJournal(journal.path)
    assert reopened.get("u1")["status"] == "finalized"
    assert reopened.recover_incomplete(T5) == []
    assert reopened.finalize("u1", 1, "u1:commit:0", T5)["duplicate"] is True


def test_timeout_and_restart_never_finalize_retained_speech(journal):
    start(journal); committed(journal, at=T1); journal.release("u1", T2)
    expired = journal.expire("2026-11-14T20:00:13Z")
    assert expired[0]["status"] == "rejected"
    assert expired[0]["rejectionReason"] == "finalization_timeout"
    assert expired[0]["text"] == "Pause after this cycle"
    assert expired[0]["goalRequestId"] is None
    start(journal, "u2")
    reopened = VoiceJournal(journal.path)
    recovered = reopened.recover_incomplete(T5)
    assert [item["id"] for item in recovered] == ["u2"]
    assert recovered[0]["rejectionReason"] == "capture_interrupted"


@pytest.mark.parametrize("kind", ["auth_error", "quota_exceeded", "invalid_request", "commit_throttled", "error"])
def test_provider_errors_fail_closed(journal, kind):
    start(journal)
    result = journal.receive("u1", "error-event", {"message_type": kind, "error": "offline fixture"}, T2)
    assert result["status"] == "rejected" and result["goalRequestId"] is None
    assert result["rejectionReason"] == "provider_" + kind


@pytest.mark.parametrize("config,reason", [({"model_id": "scribe_v2_realtime"}, "provider_model_mismatch"),
    ({"model_id": SCRIBE_MODEL, "commit_strategy": "vad"}, "commit_strategy_mismatch")])
def test_wrong_provider_model_or_commit_mode_cannot_be_treated_as_selected_service(journal, config, reason):
    journal.start("u1", "session1", T0)
    result = journal.receive("u1", "session-event", {"message_type": "session_started", "session_id": "provider", "config": config}, T1)
    assert result["rejectionReason"] == reason


def test_provider_session_change_and_unbound_transcript_fail_closed(journal):
    journal.start("u1", "session1", T0)
    assert committed(journal)["rejectionReason"] == "transcript_before_session"
    start(journal, "u2")
    result = journal.receive("u2", "different-session", {"message_type": "session_started", "session_id": "another", "config": {"model_id": SCRIBE_MODEL}}, T2)
    assert result["rejectionReason"] == "provider_session_changed"


def test_unresolved_partial_and_enrichment_event_are_not_final_commit(journal):
    start(journal); journal.release("u1", T2); committed(journal)
    journal.receive("u1", "enrichment", {"message_type": "committed_transcript_with_timestamps", "text": "Pause after this cycle"}, T4, 0)
    with pytest.raises(VoiceError, match="committed segment event"):
        journal.finalize("u1", 1, "enrichment", T5)
    journal.receive("u1", "partial-late", {"message_type": "partial_transcript", "text": "actually"}, T4)
    with pytest.raises(VoiceError, match="Uncommitted"):
        journal.finalize("u1", 1, "u1:commit:0", T5)


def test_empty_commit_and_conflicting_metadata_never_invent_transcript(journal):
    start(journal); journal.release("u1", T2)
    committed(journal, text="")
    assert journal.finalize("u1", 1, "u1:commit:0", T4)["rejectionReason"] == "empty_utterance"
    first = finalized(journal, "u2")
    changed = journal.receive("u2", "edited", {"message_type": "edited_transcript", "text": "different", "edited_text": "resume"}, T5, 0)
    assert changed["eventDisposition"] == "unmatched_enrichment"
    assert changed["text"] == first["text"] and changed["goalRequestId"] == first["goalRequestId"]


def test_idempotence_and_validation_boundaries(journal):
    first = start(journal)
    assert journal.start("u1", "session1", T0)["duplicate"] is True
    with pytest.raises(VoiceError, match="metadata"):
        journal.start("u1", "session2", T0)
    with pytest.raises(VoiceError, match="timezone"):
        journal.release("u1", "2026-11-14T20:00:02")
    with pytest.raises(VoiceError, match="credentials"):
        journal.receive("u1", "secret", {"message_type": "partial_transcript", "token": "synthetic"}, T2)
    with pytest.raises(VoiceError, match="index disagree"):
        journal.receive("u1", "mismatch", {"message_type": "committed_transcript", "segment_index": 2}, T2, 1)
    result = journal.release("u1", "2026-11-14T20:00:21Z")
    assert result["rejectionReason"] == "capture_timeout"
    assert result["goalRequestId"] is None


class Response(io.BytesIO):
    status = 200


class FakeOpener:
    def __init__(self, value=None, error=None):
        self.value, self.error, self.calls = value or {"token": "synthetic-single-use"}, error, []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if self.error:
            raise self.error
        return Response(json.dumps(self.value).encode())


def test_token_helper_uses_server_header_exact_endpoint_and_does_not_return_long_lived_key():
    transport = FakeOpener()
    result = issue_scribe_token("synthetic-long-lived-secret", opener=transport)
    request, timeout = transport.calls[0]
    assert request.full_url == "https://api.elevenlabs.io/v1/single-use-token/realtime_scribe"
    assert request.method == "POST" and request.get_header("Xi-api-key") == "synthetic-long-lived-secret"
    assert result["token"] == "synthetic-single-use" and result["modelId"] == SCRIBE_MODEL
    assert "synthetic-long-lived-secret" not in json.dumps(result)
    assert scribe_connection_options()["params"]["commit_strategy"] == "manual"
    assert "token" not in scribe_connection_options()["params"]


def test_token_errors_never_echo_provider_body_or_transport_secret():
    secret = "synthetic-long-lived-secret"
    errors = [urllib.error.HTTPError("https://provider/", 401, secret, {}, io.BytesIO(secret.encode())),
              urllib.error.URLError(secret), TimeoutError(secret)]
    for error in errors:
        with pytest.raises(VoiceError) as caught:
            issue_scribe_token(secret, opener=FakeOpener(error=error))
        assert secret not in str(caught.value)
    transport = FakeOpener()
    with pytest.raises(VoiceError, match="not configured"):
        issue_scribe_token("", opener=transport)
    with pytest.raises(VoiceError, match="configuration is invalid") as caught:
        issue_scribe_token(secret + "\n", opener=transport)
    assert secret not in str(caught.value)
    assert transport.calls == []
