import type {
  Attempt,
  Correction,
  Cycle,
  DecisionRecord,
  Destination,
  Frame,
  GoalState,
  ID,
  Inspection,
  ISOTime,
  MetricRatio,
  Outcome,
  PermittedTaskId,
  Quality,
  ReferenceLabel,
  Session,
  SessionMetrics,
  SkillExecution,
  SourceMode,
  StationEventEnvelope,
  SupportedGoalId,
  VoiceUtterance,
} from "./prototypeTypes.ts";

export function computePercentile(values: number[], percentile: number): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  if (percentile === 50) {
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0
      ? Number(sorted[mid].toFixed(2))
      : Number(((sorted[mid - 1] + sorted[mid]) / 2).toFixed(2));
  }
  const idx = Math.ceil((percentile / 100) * sorted.length) - 1;
  return Number(sorted[Math.max(0, Math.min(sorted.length - 1, idx))].toFixed(2));
}

export function makeRatio(
  numerator: number,
  denominator: number,
  definition: string,
  sourceMode: SourceMode | "disconnected",
  sessionId: ID | null,
  excludedInProgressCount = 0
): MetricRatio {
  return {
    numerator,
    denominator,
    value: denominator > 0 ? Number(((100 * numerator) / denominator).toFixed(1)) : null,
    definition,
    sourceMode,
    sessionId,
    excludedInProgressCount,
  };
}

/**
 * Evaluates a cycle's overall task outcome from its physical attempts, decision inspection,
 * observed destination, confirmation, and independent reference label.
 * Rule: Correct placement in a wrongly selected bin (e.g. C-004 defective brick predicted good
 * and placed in good_bin) is physical attempt success, but overall cycle outcome is 'failed'.
 * Controller completion without confirmation stays 'unverified'.
 */
export function evaluateCycleOutcome(params: {
  isInProgress: boolean;
  isAborted: boolean;
  hasConfirmation: boolean;
  attempts: Attempt[];
  decisionClassification: Quality | "review_required" | null;
  referenceQuality: Quality | null;
  commandedDestination: Destination | null;
  observedDestination: Destination | "other" | null;
}): Outcome {
  if (params.isInProgress) return "in_progress";
  if (params.isAborted) return "aborted";

  const finishedAttempts = params.attempts.filter((a) => a.outcome !== "in_progress");
  if (finishedAttempts.length === 0) return "unverified";

  const lastAttempt = finishedAttempts[finishedAttempts.length - 1];
  if (lastAttempt.outcome === "aborted") return "aborted";
  if (lastAttempt.outcome === "unverified" || !params.hasConfirmation || !params.observedDestination) {
    return "unverified";
  }
  if (lastAttempt.outcome === "failed") {
    return "failed";
  }

  // Physical placement succeeded and was confirmed. Check whether destination matches commanded & reference truth.
  if (params.observedDestination === "other") {
    return "failed";
  }
  if (params.commandedDestination && params.observedDestination !== params.commandedDestination) {
    return "failed";
  }

  // If independent reference quality exists, verify that classification & destination match reference quality
  if (params.referenceQuality) {
    const expectedBin: Destination = params.referenceQuality === "good" ? "good_bin" : "defective_bin";
    if (params.observedDestination !== expectedBin) {
      return "failed";
    }
    if (params.decisionClassification && params.decisionClassification !== params.referenceQuality) {
      return "failed";
    }
  } else if (params.decisionClassification === "review_required" || !params.decisionClassification) {
    return "unverified";
  }

  return "correct";
}

/**
 * Computes all operational and reference-labeled detection metrics strictly from persisted records.
 */
export function computeSessionMetrics(params: {
  session: Session | null;
  stationConnected: boolean;
  cycles: Cycle[];
  attempts: Attempt[];
  inspections: Inspection[];
  referenceLabels: ReferenceLabel[];
}): SessionMetrics {
  const { session, stationConnected, cycles, attempts, inspections, referenceLabels } = params;
  const sourceMode: SourceMode | "disconnected" = !session || !stationConnected && session.sourceMode === "live"
    ? "disconnected"
    : session.sourceMode;
  const sessionId = session?.id ?? null;

  const sessionCycles = session
    ? cycles.filter((c) => c.sessionId === session.id)
    : [];
  const cycleIdSet = new Set(sessionCycles.map((c) => c.id));

  const sessionAttempts = attempts.filter((a) => cycleIdSet.has(a.cycleId));
  const sessionInspections = inspections.filter((ins) => cycleIdSet.has(ins.cycleId));
  const sessionRefLabels = referenceLabels.filter((rl) => cycleIdSet.has(rl.cycleId));

  const inProgressCycles = sessionCycles.filter((c) => c.outcome === "in_progress");
  const finishedCycles = sessionCycles.filter((c) => c.outcome !== "in_progress");
  const correctCycles = finishedCycles.filter((c) => c.outcome === "correct");
  const failedCycles = finishedCycles.filter((c) => c.outcome === "failed");
  const abortedCycles = finishedCycles.filter((c) => c.outcome === "aborted");
  const unverifiedCycles = finishedCycles.filter((c) => c.outcome === "unverified");

  // Attempts breakdown
  const inProgressAttempts = sessionAttempts.filter((a) => a.outcome === "in_progress");
  const finishedAttempts = sessionAttempts.filter((a) => a.outcome !== "in_progress");
  const successfulAttempts = finishedAttempts.filter((a) => a.outcome === "successful");
  const failedAttempts = finishedAttempts.filter((a) => a.outcome === "failed");
  const abortedAttempts = finishedAttempts.filter((a) => a.outcome === "aborted");
  const unverifiedAttempts = finishedAttempts.filter((a) => a.outcome === "unverified");

  // Retries: physical attempts after the first attempt in each cycle (ordinal > 1 or retryOfAttemptId !== null)
  let retriesCount = 0;
  let firstAttemptSuccesses = 0;
  let recoveredCycles = 0;

  for (const cyc of sessionCycles) {
    const cycAttempts = sessionAttempts
      .filter((a) => a.cycleId === cyc.id)
      .sort((a, b) => a.ordinal - b.ordinal);

    if (cycAttempts.length > 1) {
      retriesCount += cycAttempts.length - 1;
    }

    if (cyc.outcome === "correct") {
      const hadEarlierFailure = cycAttempts.slice(0, -1).some((a) => a.outcome === "failed");
      if (cycAttempts.length === 1 && cycAttempts[0]?.outcome === "successful") {
        firstAttemptSuccesses += 1;
      } else if (hadEarlierFailure) {
        recoveredCycles += 1;
      }
    }
  }

  // Additional inspections: inspections explicitly linked to an earlier inspection
  const extraInspections = sessionInspections.filter(
    (ins) => ins.additionalInspectionOfId !== null
  ).length;

  // Streak: consecutive confirmed correct cycles in chronological order; failed, aborted, unverified break it
  let currentStreak = 0;
  let bestStreak = 0;
  for (const cyc of finishedCycles) {
    if (cyc.outcome === "correct") {
      currentStreak += 1;
      if (currentStreak > bestStreak) bestStreak = currentStreak;
    } else {
      currentStreak = 0;
    }
  }

  // Full-cycle duration statistics (includes cloud waits, retries, extra inspections)
  const durations = finishedCycles
    .map((c) => c.fullCycleDurationSec)
    .filter((d): d is number => typeof d === "number" && d > 0);
  const p50 = computePercentile(durations, 50);
  const p95 = computePercentile(durations, 95);

  // Detection metrics over independently reference-labeled examples only (1 decision inspection per cycle)
  const refByCycleId = new Map<ID, ReferenceLabel>();
  for (const rl of sessionRefLabels) {
    refByCycleId.set(rl.cycleId, rl);
  }

  let tp = 0; // defective reference, predicted defective
  let tn = 0; // good reference, predicted good
  let fn = 0; // defective reference, predicted good (DEFECT ESCAPE)
  let fp = 0; // good reference, predicted defective
  let reviewRequiredCount = 0;
  let unlabeledCount = 0;

  for (const cyc of sessionCycles) {
    const ref = refByCycleId.get(cyc.id);
    // Find the documented decision inspection for this cycle (latest inspection marked isDecisionInspection, or latest inspection)
    const cycInspections = sessionInspections.filter((i) => i.cycleId === cyc.id);
    const decisionInspection =
      cycInspections.find((i) => i.isDecisionInspection) ??
      cycInspections[cycInspections.length - 1] ??
      null;

    if (!ref || !decisionInspection) {
      unlabeledCount += 1;
      continue;
    }

    if (decisionInspection.classification === "review_required") {
      reviewRequiredCount += 1;
      continue;
    }

    if (ref.quality === "defective" && decisionInspection.classification === "defective") {
      tp += 1;
    } else if (ref.quality === "good" && decisionInspection.classification === "good") {
      tn += 1;
    } else if (ref.quality === "defective" && decisionInspection.classification === "good") {
      fn += 1;
    } else if (ref.quality === "good" && decisionInspection.classification === "defective") {
      fp += 1;
    }
  }

  const checkedComparableCount = tp + tn + fn + fp;
  const detectionCorrectCount = tp + tn;
  const actualDefectiveChecked = tp + fn;

  const baseDetectionRatio = makeRatio(
    detectionCorrectCount,
    checkedComparableCount,
    "Correct classifications among independently reference-labeled examples",
    sourceMode,
    sessionId,
    inProgressCycles.length
  );

  return {
    sessionId,
    sourceMode,
    confirmedCorrectCycles: makeRatio(
      correctCycles.length,
      finishedCycles.length,
      "Confirmed correct cycles / all finished cycles (includes failed, aborted, unverified; excludes in-progress)",
      sourceMode,
      sessionId,
      inProgressCycles.length
    ),
    physicalExecution: makeRatio(
      successfulAttempts.length,
      finishedAttempts.length,
      "Confirmed successful physical attempts / all finished physical attempts",
      sourceMode,
      sessionId,
      inProgressAttempts.length
    ),
    detectionAccuracy: {
      ...baseDetectionRatio,
      totalPopulation: sessionCycles.length,
      checkedPopulation: checkedComparableCount + reviewRequiredCount,
      reviewRequiredCount,
    },
    defectEscape: makeRatio(
      fn,
      actualDefectiveChecked,
      "Defective reference objects predicted good / all reference-defective objects checked",
      sourceMode,
      sessionId,
      0
    ),
    streak: {
      current: currentStreak,
      best: bestStreak,
      hasData: finishedCycles.length > 0,
    },
    medianFullCycleSec: {
      value: p50,
      p50,
      p95,
      sampleCount: durations.length,
      includesCloudWait: true,
    },
    cycleCounts: {
      started: sessionCycles.length,
      finished: finishedCycles.length,
      inProgress: inProgressCycles.length,
      correct: correctCycles.length,
      failed: failedCycles.length,
      aborted: abortedCycles.length,
      unverified: unverifiedCycles.length,
      firstAttemptSuccesses,
      recoveredCycles,
      extraInspections,
    },
    attemptCounts: {
      total: sessionAttempts.length,
      finished: finishedAttempts.length,
      inProgress: inProgressAttempts.length,
      successful: successfulAttempts.length,
      failed: failedAttempts.length,
      aborted: abortedAttempts.length,
      unverified: unverifiedAttempts.length,
      retries: retriesCount,
    },
    confusionMatrix: {
      tp,
      tn,
      fn,
      fp,
      unlabeledCount,
      reviewRequiredCount,
    },
  };
}

/**
 * Local dispatcher gate validation.
 * Checks stateVersion, goalVersion, evidence freshness, deadline, allowed tasks, retry budget, and unique executionId.
 */
export interface DispatchValidationInput {
  expectedStateVersion: number;
  currentStateVersion: number;
  expectedGoalVersion: number;
  currentGoalVersion: number;
  selectedTask: string | null;
  allowedTasks: PermittedTaskId[];
  frameCapturedAt: ISOTime | null;
  frameStale: boolean;
  maxEvidenceAgeMs: number;
  nowIso: ISOTime;
  deadlineAt: ISOTime;
  attemptCountInCycle: number;
  maxAttemptsPerCycle: number;
  executionId: ID;
  existingExecutionIds: Set<ID>;
}

export interface DispatchValidationResult {
  accepted: boolean;
  reason: string;
  resolvedTask: PermittedTaskId;
}

export function validateTaskDispatch(input: DispatchValidationInput): DispatchValidationResult {
  if (input.existingExecutionIds.has(input.executionId)) {
    return {
      accepted: false,
      reason: `Rejected duplicate executionId ${input.executionId}`,
      resolvedTask: "hold",
    };
  }

  if (input.expectedGoalVersion !== input.currentGoalVersion) {
    return {
      accepted: false,
      reason: `Rejected stale goalVersion (decision=${input.expectedGoalVersion}, current=${input.currentGoalVersion})`,
      resolvedTask: "hold",
    };
  }

  if (input.expectedStateVersion !== input.currentStateVersion) {
    return {
      accepted: false,
      reason: `Rejected stale stateVersion (decision=${input.expectedStateVersion}, current=${input.currentStateVersion})`,
      resolvedTask: "hold",
    };
  }

  const nowMs = Date.parse(input.nowIso);
  const deadlineMs = Date.parse(input.deadlineAt);
  if (Number.isFinite(nowMs) && Number.isFinite(deadlineMs) && nowMs > deadlineMs) {
    return {
      accepted: false,
      reason: "Held: decision deadline expired before local dispatch",
      resolvedTask: "hold",
    };
  }

  if (input.frameStale || !input.frameCapturedAt) {
    return {
      accepted: false,
      reason: "Held: evidence frame stale or missing capture timestamp",
      resolvedTask: "hold",
    };
  }

  const capturedMs = Date.parse(input.frameCapturedAt);
  if (Number.isFinite(nowMs) && Number.isFinite(capturedMs) && nowMs - capturedMs > input.maxEvidenceAgeMs) {
    return {
      accepted: false,
      reason: `Held: evidence age (${nowMs - capturedMs}ms) exceeds freshness threshold (${input.maxEvidenceAgeMs}ms)`,
      resolvedTask: "hold",
    };
  }

  if (
    input.selectedTask === "pick" &&
    input.attemptCountInCycle >= input.maxAttemptsPerCycle
  ) {
    return {
      accepted: false,
      reason: `Held: retry limit reached (${input.attemptCountInCycle}/${input.maxAttemptsPerCycle} attempts)`,
      resolvedTask: "hold",
    };
  }

  if (!input.selectedTask || !input.allowedTasks.includes(input.selectedTask as PermittedTaskId)) {
    return {
      accepted: false,
      reason: `Held: selected task '${input.selectedTask ?? "none"}' is not in permitted task set`,
      resolvedTask: "hold",
    };
  }

  if (input.selectedTask === "hold") {
    return {
      accepted: true,
      reason: "Hold accepted: awaiting operator review or fresh evidence",
      resolvedTask: "hold",
    };
  }

  return {
    accepted: true,
    reason: `Accepted '${input.selectedTask}' at state v${input.currentStateVersion} / goal v${input.currentGoalVersion}`,
    resolvedTask: input.selectedTask as PermittedTaskId,
  };
}

/**
 * Voice utterance segment handling & deduplication.
 * - Partial transcripts are display-only and never issue a goal or command.
 * - Committed segments accumulate in order.
 * - Finalization happens once per utteranceId; duplicate finalization calls return the existing utterance without issuing another command.
 * - Timestamp enrichment updates the transcript metadata and never issues another command.
 */
export function applyPartialTranscript(
  utterance: VoiceUtterance,
  partialText: string
): { utterance: VoiceUtterance; commandIssued: boolean } {
  if (utterance.finalizedText !== null) {
    return { utterance, commandIssued: false };
  }
  return {
    utterance: {
      ...utterance,
      partialTranscript: partialText,
      state: "listening",
    },
    commandIssued: false,
  };
}

export function appendCommittedSegment(
  utterance: VoiceUtterance,
  segmentText: string
): { utterance: VoiceUtterance; commandIssued: boolean } {
  if (utterance.finalizedText !== null) {
    return { utterance, commandIssued: false };
  }
  const trimmed = segmentText.trim();
  if (!trimmed) return { utterance, commandIssued: false };
  return {
    utterance: {
      ...utterance,
      committedSegments: [...utterance.committedSegments, trimmed],
      partialTranscript: "",
    },
    commandIssued: false,
  };
}

export function finalizeUtteranceOnce(params: {
  existingUtterances: Map<ID, VoiceUtterance>;
  utterance: VoiceUtterance;
  finalizedAt: ISOTime;
  selectedGoal: SupportedGoalId;
  goalProbabilities: Record<string, number>;
  queueForNextBoundary: boolean;
  currentGoalState: GoalState;
}): {
  utterance: VoiceUtterance;
  goalState: GoalState;
  deduplicated: boolean;
  commandIssued: boolean;
} {
  const existing = params.existingUtterances.get(params.utterance.id);
  if (existing && existing.finalizedText !== null) {
    // Already finalized: deduplicate by utterance ID!
    return {
      utterance: existing,
      goalState: params.currentGoalState,
      deduplicated: true,
      commandIssued: false,
    };
  }

  const fullText =
    params.utterance.committedSegments.length > 0
      ? params.utterance.committedSegments.join(" ")
      : params.utterance.partialTranscript.trim();

  if (!fullText) {
    const rejected: VoiceUtterance = {
      ...params.utterance,
      state: "rejected",
      finalizedAt: params.finalizedAt,
    };
    params.existingUtterances.set(rejected.id, rejected);
    return {
      utterance: rejected,
      goalState: params.currentGoalState,
      deduplicated: false,
      commandIssued: false,
    };
  }

  const isUnsupported = params.selectedGoal === "unsupported_request";
  const nextState = isUnsupported
    ? "rejected"
    : params.queueForNextBoundary
    ? "queued"
    : "active";

  const finalized: VoiceUtterance = {
    ...params.utterance,
    partialTranscript: "",
    finalizedText: fullText,
    finalizedAt: params.finalizedAt,
    selectedGoal: params.selectedGoal,
    goalProbabilities: params.goalProbabilities,
    effectiveBoundary: isUnsupported
      ? "Rejected (unsupported goal)"
      : params.queueForNextBoundary
      ? "Next cycle / inspection boundary"
      : `Committed immediately (goal v${params.currentGoalState.goalVersion + 1})`,
    state: nextState,
  };

  params.existingUtterances.set(finalized.id, finalized);

  let nextGoalState = { ...params.currentGoalState };
  if (!isUnsupported) {
    const labelMap: Record<SupportedGoalId, string> = {
      standard_sorting: "Standard sorting",
      extra_view_next_reject: "Additional view before next reject",
      pause_after_cycle: "Pause after cycle",
      resume: "Resume sorting",
      unsupported_request: "Unsupported request",
    };
    if (params.queueForNextBoundary) {
      nextGoalState = {
        ...params.currentGoalState,
        queuedGoal: params.selectedGoal,
        queuedGoalLabel: labelMap[params.selectedGoal],
        queuedBoundary: "Next inspection / cycle boundary",
        updatedAt: params.finalizedAt,
      };
    } else {
      nextGoalState = {
        activeGoal: params.selectedGoal,
        activeGoalLabel: labelMap[params.selectedGoal],
        goalVersion: params.currentGoalState.goalVersion + 1,
        queuedGoal: null,
        queuedGoalLabel: null,
        queuedBoundary: null,
        updatedAt: params.finalizedAt,
      };
    }
  }

  return {
    utterance: finalized,
    goalState: nextGoalState,
    deduplicated: false,
    commandIssued: !isUnsupported,
  };
}

export function enrichUtteranceTimestamps(
  existingUtterances: Map<ID, VoiceUtterance>,
  utteranceId: ID,
  timestamps: { word: string; startMs: number; endMs: number }[]
): { utterance: VoiceUtterance | null; commandIssued: boolean } {
  const existing = existingUtterances.get(utteranceId);
  if (!existing) return { utterance: null, commandIssued: false };
  const updated: VoiceUtterance = {
    ...existing,
    timestampsEnriched: true,
    enrichmentTimestamps: timestamps,
  };
  existingUtterances.set(utteranceId, updated);
  return { utterance: updated, commandIssued: false };
}

/**
 * Commits a queued goal at a valid phase/cycle boundary, incrementing goalVersion.
 */
export function commitQueuedGoalAtBoundary(
  goalState: GoalState,
  nowIso: ISOTime
): { goalState: GoalState; committed: boolean } {
  if (!goalState.queuedGoal) {
    return { goalState, committed: false };
  }
  return {
    goalState: {
      activeGoal: goalState.queuedGoal,
      activeGoalLabel: goalState.queuedGoalLabel ?? goalState.queuedGoal,
      goalVersion: goalState.goalVersion + 1,
      queuedGoal: null,
      queuedGoalLabel: null,
      queuedBoundary: null,
      updatedAt: nowIso,
    },
    committed: true,
  };
}

/**
 * Ordered event processor with eventId deduplication, entityRevision checks, and sequence gap detection.
 */
export interface EventLogState {
  appliedEventIds: Set<ID>;
  entityRevisions: Map<ID, number>;
  lastSequence: number;
  events: StationEventEnvelope[];
  resyncRequired: boolean;
  detectedGapRange: [number, number] | null;
}

export function applyOrderedEvent(
  state: EventLogState,
  envelope: StationEventEnvelope
): {
  state: EventLogState;
  applied: boolean;
  reason: "applied" | "duplicate_event" | "stale_revision" | "sequence_gap";
} {
  if (state.appliedEventIds.has(envelope.eventId)) {
    return { state, applied: false, reason: "duplicate_event" };
  }

  if (state.lastSequence > 0 && envelope.sequence > state.lastSequence + 1) {
    return {
      state: {
        ...state,
        resyncRequired: true,
        detectedGapRange: [state.lastSequence + 1, envelope.sequence - 1],
      },
      applied: false,
      reason: "sequence_gap",
    };
  }

  const currentRev = state.entityRevisions.get(envelope.entityId) ?? 0;
  if (envelope.entityRevision < currentRev) {
    return { state, applied: false, reason: "stale_revision" };
  }

  const nextAppliedIds = new Set(state.appliedEventIds);
  nextAppliedIds.add(envelope.eventId);

  const nextRevisions = new Map(state.entityRevisions);
  nextRevisions.set(envelope.entityId, envelope.entityRevision);

  return {
    state: {
      appliedEventIds: nextAppliedIds,
      entityRevisions: nextRevisions,
      lastSequence: Math.max(state.lastSequence, envelope.sequence),
      events: [envelope, ...state.events],
      resyncRequired: false,
      detectedGapRange: null,
    },
    applied: true,
    reason: "applied",
  };
}
