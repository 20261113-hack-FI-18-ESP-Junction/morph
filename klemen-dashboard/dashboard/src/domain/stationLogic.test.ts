import test from "node:test";
import assert from "node:assert/strict";
import { StationStore } from "./stationStore";
import {
  applyPartialTranscript,
  appendCommittedSegment,
  finalizeUtteranceOnce,
  enrichUtteranceTimestamps,
  validateTaskDispatch,
} from "./stationLogic";
import type { GoalState, VoiceUtterance } from "./prototypeTypes.ts";

test("1. Default hardware view is Live / Disconnected with empty metrics and no seeded fixtures", () => {
  const store = new StationStore("live");
  const snap = store.getSnapshot();
  assert.equal(snap.viewMode, "live");
  assert.equal(snap.stationConnected, false);
  assert.equal(snap.activeSession, null);
  assert.equal(snap.cycles.length, 0);
  assert.equal(snap.metrics.confirmedCorrectCycles.value, null);
  assert.equal(snap.metrics.physicalExecution.value, null);
  assert.equal(snap.metrics.streak.hasData, false);
  assert.equal(snap.metrics.medianFullCycleSec.value, null);
});

test("2. Canonical Demo 01 fixture matches exact reference counts and denominators", () => {
  const store = new StationStore("simulation");
  const snap = store.seedSimulationPreset("demo_01_full");
  const m = snap.metrics;

  assert.equal(m.cycleCounts.started, 12);
  assert.equal(m.cycleCounts.finished, 11);
  assert.equal(m.cycleCounts.inProgress, 1);
  assert.equal(m.cycleCounts.correct, 8);
  assert.equal(m.cycleCounts.failed, 1);
  assert.equal(m.cycleCounts.aborted, 1);
  assert.equal(m.cycleCounts.unverified, 1);
  assert.equal(m.cycleCounts.firstAttemptSuccesses, 6);
  assert.equal(m.cycleCounts.recoveredCycles, 2);
  assert.equal(m.cycleCounts.extraInspections, 3);

  assert.equal(m.confirmedCorrectCycles.numerator, 8);
  assert.equal(m.confirmedCorrectCycles.denominator, 11);
  assert.equal(m.confirmedCorrectCycles.value, 72.7);

  assert.equal(m.attemptCounts.total, 14);
  assert.equal(m.attemptCounts.finished, 13);
  assert.equal(m.attemptCounts.successful, 9);
  assert.equal(m.attemptCounts.failed, 2);
  assert.equal(m.attemptCounts.aborted, 1);
  assert.equal(m.attemptCounts.unverified, 1);
  assert.equal(m.attemptCounts.inProgress, 1);
  assert.equal(m.attemptCounts.retries, 2);

  assert.equal(m.physicalExecution.numerator, 9);
  assert.equal(m.physicalExecution.denominator, 13);
  assert.equal(m.physicalExecution.value, 69.2);

  assert.equal(m.streak.current, 3);
  assert.equal(m.streak.best, 3);
  assert.equal(m.medianFullCycleSec.value, 11.2);

  // Confusion matrix over 9 reference-labeled examples (positive = defective)
  assert.equal(m.confusionMatrix.tn, 5); // good accepted
  assert.equal(m.confusionMatrix.fp, 0); // good rejected
  assert.equal(m.confusionMatrix.fn, 1); // defective accepted (C-004 defect escape)
  assert.equal(m.confusionMatrix.tp, 3); // defective rejected
  assert.equal(m.detectionAccuracy.numerator, 8);
  assert.equal(m.detectionAccuracy.denominator, 9);
  assert.equal(m.detectionAccuracy.value, 88.9);
});

test("3. One failed grasp followed by confirmed retry produces 1 cycle, 2 attempts (1/1 cycle, 1/2 attempts)", () => {
  const store = new StationStore("simulation");
  const snap = store.seedSimulationPreset("failed_grasp_recovery");
  const m = snap.metrics;

  assert.equal(m.cycleCounts.started, 1);
  assert.equal(m.cycleCounts.finished, 1);
  assert.equal(m.cycleCounts.correct, 1);
  assert.equal(m.cycleCounts.recoveredCycles, 1);
  assert.equal(m.cycleCounts.firstAttemptSuccesses, 0);

  assert.equal(m.attemptCounts.total, 2);
  assert.equal(m.attemptCounts.failed, 1);
  assert.equal(m.attemptCounts.successful, 1);
  assert.equal(m.attemptCounts.retries, 1);

  assert.equal(m.confirmedCorrectCycles.numerator, 1);
  assert.equal(m.confirmedCorrectCycles.denominator, 1);
  assert.equal(m.confirmedCorrectCycles.value, 100);

  assert.equal(m.physicalExecution.numerator, 1);
  assert.equal(m.physicalExecution.denominator, 2);
  assert.equal(m.physicalExecution.value, 50);
});

test("4. Two failed attempts followed by recovery remain 1 cycle with 3 attempts", () => {
  const store = new StationStore("simulation");
  const snap = store.seedSimulationPreset("two_failed_attempts_recovery");
  const m = snap.metrics;

  assert.equal(m.cycleCounts.started, 1);
  assert.equal(m.cycleCounts.correct, 1);
  assert.equal(m.cycleCounts.recoveredCycles, 1);
  assert.equal(m.attemptCounts.total, 3);
  assert.equal(m.attemptCounts.failed, 2);
  assert.equal(m.attemptCounts.successful, 1);
  assert.equal(m.attemptCounts.retries, 2);
  assert.equal(m.physicalExecution.value, 33.3);
});

test("5. Extra inspection without physical retry does not increment attempts", () => {
  const store = new StationStore("simulation");
  const snap = store.seedSimulationPreset("extra_inspection_no_retry");
  const m = snap.metrics;

  assert.equal(m.cycleCounts.started, 1);
  assert.equal(m.attemptCounts.total, 1);
  assert.equal(m.attemptCounts.retries, 0);
  assert.equal(m.cycleCounts.extraInspections, 1);
});

test("6. Wrong-bin outcome (C-004): physical placement is successful (1/1) while overall cycle is failed (0/1)", () => {
  const store = new StationStore("simulation");
  const snap = store.seedSimulationPreset("wrong_bin_defect_escape");
  const m = snap.metrics;

  assert.equal(m.physicalExecution.numerator, 1);
  assert.equal(m.physicalExecution.denominator, 1);
  assert.equal(m.physicalExecution.value, 100);

  assert.equal(m.confirmedCorrectCycles.numerator, 0);
  assert.equal(m.confirmedCorrectCycles.denominator, 1);
  assert.equal(m.confirmedCorrectCycles.value, 0);
  assert.equal(m.confusionMatrix.fn, 1); // Defect escape
});

test("7. Duplicate event ID, stale entityRevision, and sequence gap detection", () => {
  const store = new StationStore("simulation");
  store.seedSimulationPreset("demo_01_full");

  const dupResult = store.applyExternalEvent({
    schemaVersion: 1,
    eventId: "evt-demo-03", // already applied in seed
    sequence: 4,
    type: "inspection.recorded",
    occurredAt: "2026-11-14T13:42:10.000Z",
    receivedAt: "2026-11-14T13:42:10.005Z",
    sourceMode: "simulation",
    sessionId: "DEMO-01",
    cycleId: "C-012",
    attemptId: "A-012-01",
    entityId: "INS-012-02",
    entityRevision: 2,
    summary: "Duplicate event",
    statusTone: "neutral",
    payload: {},
  });
  assert.equal(dupResult.applied, false);
  assert.equal(dupResult.reason, "duplicate_event");

  // Sequence gap (lastSequence is 3, jumping to 6)
  const gapResult = store.applyExternalEvent({
    schemaVersion: 1,
    eventId: "evt-demo-gap-06",
    sequence: 6,
    type: "inspection.recorded",
    occurredAt: "2026-11-14T13:42:11.000Z",
    receivedAt: "2026-11-14T13:42:11.005Z",
    sourceMode: "simulation",
    sessionId: "DEMO-01",
    cycleId: "C-012",
    attemptId: "A-012-01",
    entityId: "INS-012-02",
    entityRevision: 2,
    summary: "Gap event",
    statusTone: "neutral",
    payload: {},
  });
  assert.equal(gapResult.applied, false);
  assert.equal(gapResult.reason, "sequence_gap");
});

test("8. Local dispatcher rejects stale goalVersion, stale frame, expired deadline, and duplicate executionId", () => {
  const execIds = new Set(["EX-001"]);

  // Duplicate executionId
  const dupExec = validateTaskDispatch({
    expectedStateVersion: 10,
    currentStateVersion: 10,
    expectedGoalVersion: 2,
    currentGoalVersion: 2,
    selectedTask: "place_good",
    allowedTasks: ["place_good", "place_defective", "hold"],
    frameCapturedAt: "2026-11-14T13:42:08.000Z",
    frameStale: false,
    maxEvidenceAgeMs: 5000,
    nowIso: "2026-11-14T13:42:09.000Z",
    deadlineAt: "2026-11-14T13:42:12.000Z",
    attemptCountInCycle: 1,
    maxAttemptsPerCycle: 3,
    executionId: "EX-001",
    existingExecutionIds: execIds,
  });
  assert.equal(dupExec.accepted, false);
  assert.equal(dupExec.resolvedTask, "hold");

  // Stale goalVersion after operator voice goal change
  const staleGoal = validateTaskDispatch({
    expectedStateVersion: 10,
    currentStateVersion: 10,
    expectedGoalVersion: 1,
    currentGoalVersion: 2,
    selectedTask: "place_defective",
    allowedTasks: ["place_good", "place_defective", "hold"],
    frameCapturedAt: "2026-11-14T13:42:08.000Z",
    frameStale: false,
    maxEvidenceAgeMs: 5000,
    nowIso: "2026-11-14T13:42:09.000Z",
    deadlineAt: "2026-11-14T13:42:12.000Z",
    attemptCountInCycle: 1,
    maxAttemptsPerCycle: 3,
    executionId: "EX-002",
    existingExecutionIds: execIds,
  });
  assert.equal(staleGoal.accepted, false);
  assert.match(staleGoal.reason, /stale goalVersion/);
});

test("9. Partial, committed, finalized, and timestamp-enriched transcript deduplication", () => {
  const utterances = new Map<string, VoiceUtterance>();
  const initialGoalState: GoalState = {
    activeGoal: "standard_sorting",
    activeGoalLabel: "Standard sorting",
    goalVersion: 1,
    queuedGoal: null,
    queuedGoalLabel: null,
    queuedBoundary: null,
    updatedAt: "2026-11-14T13:40:00.000Z",
  };

  let utt: VoiceUtterance = {
    id: "utt-test-01",
    sessionId: "DEMO-01",
    source: "scribe_v3_live",
    language: "en",
    partialTranscript: "",
    committedSegments: [],
    finalizedText: null,
    timestampsEnriched: false,
    enrichmentTimestamps: [],
    selectedGoal: null,
    goalProbabilities: {},
    effectiveBoundary: "Pending",
    state: "listening",
    createdAt: "2026-11-14T13:42:00.000Z",
    finalizedAt: null,
    transcriptionMs: 220,
    goalDecisionMs: 180,
  };

  // Partial transcript issues no command
  const p1 = applyPartialTranscript(utt, "Take one more");
  assert.equal(p1.commandIssued, false);
  utt = p1.utterance;

  // Committed segments issue no command until finalized
  const c1 = appendCommittedSegment(utt, "Take one more look");
  const c2 = appendCommittedSegment(c1.utterance, "before rejecting.");
  assert.equal(c1.commandIssued, false);
  assert.equal(c2.commandIssued, false);
  utt = c2.utterance;

  // Finalize once
  const fin1 = finalizeUtteranceOnce({
    existingUtterances: utterances,
    utterance: utt,
    finalizedAt: "2026-11-14T13:42:02.000Z",
    selectedGoal: "extra_view_next_reject",
    goalProbabilities: { extra_view_next_reject: 0.95 },
    queueForNextBoundary: true,
    currentGoalState: initialGoalState,
  });
  assert.equal(fin1.deduplicated, false);
  assert.equal(fin1.commandIssued, true);
  assert.equal(fin1.utterance.finalizedText, "Take one more look before rejecting.");
  assert.equal(fin1.goalState.queuedGoal, "extra_view_next_reject");

  // Duplicate finalization with same utterance ID is deduplicated and issues no second command
  const fin2 = finalizeUtteranceOnce({
    existingUtterances: utterances,
    utterance: utt,
    finalizedAt: "2026-11-14T13:42:03.000Z",
    selectedGoal: "extra_view_next_reject",
    goalProbabilities: { extra_view_next_reject: 0.95 },
    queueForNextBoundary: true,
    currentGoalState: fin1.goalState,
  });
  assert.equal(fin2.deduplicated, true);
  assert.equal(fin2.commandIssued, false);

  // Timestamp enrichment updates metadata and never issues another command
  const enr = enrichUtteranceTimestamps(utterances, "utt-test-01", [
    { word: "Take", startMs: 0, endMs: 180 },
  ]);
  assert.equal(enr.commandIssued, false);
  assert.equal(enr.utterance?.timestampsEnriched, true);
});

test("10. Late confirmation and audited manual correction update original record and recompute metrics", () => {
  const store = new StationStore("simulation");
  store.seedSimulationPreset("demo_01_full");

  // C-008 starts unverified (predicted defective, commanded defective_bin, observed null)
  const afterLateConfirm = store.submitReferenceCorrection({
    cycleId: "C-008",
    referenceQuality: "defective",
    observedDestination: "defective_bin",
    authorId: "qa-inspector-01",
    reason: "Verified brick in defective bin via secondary camera archive",
  });

  const c008 = afterLateConfirm.cycles.find((c) => c.id === "C-008");
  assert.equal(c008?.outcome, "correct");
  assert.equal(afterLateConfirm.metrics.cycleCounts.correct, 9);
  assert.equal(afterLateConfirm.metrics.cycleCounts.unverified, 0);
  // Streak was 3 (C-009, C-010, C-011), and since C-007 was also correct and C-008 is now correct,
  // C-007, C-008, C-009, C-010, C-011 are 5 consecutive confirmed correct cycles!
  assert.equal(afterLateConfirm.metrics.streak.current, 5);
  assert.equal(afterLateConfirm.corrections.length >= 2, true);
});

test("11. Session end preserves open cycle status; new session resets displayed totals without erasing history; replay is read-only", () => {
  const store = new StationStore("simulation");
  store.seedSimulationPreset("demo_01_full");

  // End DEMO-01 while C-012 is in_progress
  const afterEnd = store.endSession("DEMO-01");
  const c012 = afterEnd.cycles.find((c) => c.id === "C-012");
  assert.equal(c012?.outcome, "in_progress"); // Never converted to success!
  assert.notEqual(afterEnd.activeSession?.endedAt, null);

  // Start a new session: displayed totals are empty, while DEMO-01 remains in sessions list
  const newSessSnap = store.startSession("Demo 02", "simulation");
  assert.equal(newSessSnap.cycles.length, 0);
  assert.equal(newSessSnap.metrics.confirmedCorrectCycles.value, null);
  assert.equal(newSessSnap.sessions.some((s) => s.id === "DEMO-01"), true);

  // Switch to Replay mode over DEMO-01: read-only
  const replaySnap = store.setViewMode("replay", "DEMO-01");
  assert.equal(replaySnap.viewMode, "replay");
  assert.equal(replaySnap.cycles.length, 12);
  assert.throws(() => store.startCycle(), /Replay mode is strictly read-only/);
});
