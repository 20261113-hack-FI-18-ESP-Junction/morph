/** Retained prototype contract. The connected UI uses src/types/morph.ts and the canonical M06 projection. */
export type ID = string;
export type ISOTime = string; // ISO 8601 UTC, e.g. 2026-11-14T13:30:00.000Z
export type SourceMode = "live" | "simulation";
export type ViewMode = "live" | "simulation" | "replay";
export type Outcome = "in_progress" | "correct" | "failed" | "aborted" | "unverified";
export type AttemptOutcome = "in_progress" | "successful" | "failed" | "aborted" | "unverified";
export type Quality = "good" | "defective";
export type Destination = "good_bin" | "defective_bin";
export type CapabilityStatus = "proposed" | "implemented" | "verified";

export type CanonicalPhase =
  | "observe"
  | "pick"
  | "verify_grasp"
  | "present"
  | "inspect"
  | "choose_task"
  | "place"
  | "verify_outcome";

export type SupportedGoalId =
  | "standard_sorting"
  | "extra_view_next_reject"
  | "pause_after_cycle"
  | "resume"
  | "unsupported_request";

export type PermittedTaskId =
  | "pick"
  | "present_for_inspection"
  | "reinspect_other_view"
  | "place_good"
  | "place_defective"
  | "hold";

export type VoiceUiState =
  | "ready"
  | "listening"
  | "finalizing"
  | "selecting_goal"
  | "queued"
  | "active"
  | "rejected"
  | "unavailable";

export interface ModelRunMetadata {
  id: ID;
  provider: string;
  modelId: string;
  version: string | null;
  device: string | null;
  precision: string | null;
  endpointVerified: boolean;
  returnedIdentity: string | null;
}

export interface Session {
  id: ID;
  name: string;
  sourceMode: SourceMode;
  startedAt: ISOTime;
  endedAt: ISOTime | null;
  configId: ID;
  robotId: ID | null;
  displayTimezone: string;
  scenarioPreset?: SimulationPresetId;
  modelRuns: ModelRunMetadata[];
}

export interface Frame {
  id: ID;
  sessionId: ID;
  cycleId: ID;
  objectId: ID;
  cameraId: "overhead" | "wrist";
  capturedAt: ISOTime;
  receivedAt: ISOTime;
  width: number;
  height: number;
  imageUrl: string;
  sha256: string;
  stale: boolean;
  fps: number | null;
  overlayBox?: { x: number; y: number; w: number; h: number };
}

export interface Confirmation {
  id: ID;
  source: "camera" | "sensor" | "operator";
  evidenceIds: ID[];
  authorId: ID | null;
  confirmedAt: ISOTime;
  notes?: string;
}

export interface NemotronObservation {
  id: ID;
  cycleId: ID;
  frameIds: ID[];
  modelId: string;
  requestedAt: ISOTime;
  completedAt: ISOTime | null;
  status: "completed" | "waiting" | "timeout" | "rejected" | "unavailable";
  observations: string[];
  hypotheses: string[];
  uncertainty: string | null;
  rawArtifact: string;
  parseError: string | null;
}

export interface DecisionRecord {
  id: ID;
  sessionId: ID;
  cycleId: ID;
  attemptId: ID | null;
  kind: "goal_selection" | "task_selection";
  modelId: "gemini-decision-1";
  stateVersion: number;
  goalVersion: number;
  frameIds: ID[];
  offeredChoices: string[];
  selectedChoice: string | null;
  probabilities: Record<string, number>;
  requestedAt: ISOTime;
  completedAt: ISOTime | null;
  deadlineAt: ISOTime;
  validatorAccepted: boolean;
  validatorReason: string;
}

export interface SkillExecution {
  id: ID;
  cycleId: ID;
  attemptId: ID;
  taskId: PermittedTaskId;
  policyId: string;
  policyVersion: string;
  commandSentAt: ISOTime;
  acknowledgedAt: ISOTime | null;
  finishedAt: ISOTime | null;
  motionStartedAt: ISOTime | null;
  motionEndedAt: ISOTime | null;
  controllerStatus: "sent" | "acknowledged" | "running" | "finished" | "failed" | "aborted" | "unverified";
  physicalOutcome: "verified" | "failed" | "unverified" | "pending";
}

export interface Cycle {
  id: ID;
  sessionId: ID;
  objectId: ID;
  revision: number;
  startedAt: ISOTime;
  endedAt: ISOTime | null;
  outcome: Outcome;
  activePhase: CanonicalPhase;
  faultedPhase: CanonicalPhase | null;
  phaseElapsedSec: number;
  attemptIds: ID[];
  inspectionIds: ID[];
  decisionIds: ID[];
  nemotronIds: ID[];
  plannedDestination: Destination | null;
  commandedDestination: Destination | null;
  observedDestination: Destination | "other" | null;
  referenceLabelId: ID | null;
  confirmationId: ID | null;
  fullCycleDurationSec: number | null;
  timingBreakdown: {
    anomalibMs: number | null;
    nemotronMs: number | null;
    geminiMs: number | null;
    motionMs: number | null;
    verificationMs: number | null;
    cloudWaitIncluded: boolean;
  };
}

export interface Attempt {
  id: ID;
  cycleId: ID;
  ordinal: number;
  executionIds: ID[];
  startedAt: ISOTime;
  endedAt: ISOTime | null;
  outcome: AttemptOutcome;
  retryOfAttemptId: ID | null;
  retryReason: string | null;
  errorCode: string | null;
  confirmationId: ID | null;
}

export interface Inspection {
  id: ID;
  cycleId: ID;
  objectId: ID;
  frameIds: ID[];
  modelRunId: ID;
  score: number;
  threshold: number;
  scoreRange: [number, number];
  classification: Quality | "review_required";
  mapEvidenceId: ID | null;
  additionalInspectionOfId: ID | null;
  isDecisionInspection: boolean;
  requestedAt: ISOTime;
  completedAt: ISOTime;
}

export interface ReferenceLabel {
  id: ID;
  objectId: ID;
  cycleId: ID;
  quality: Quality;
  authorId: ID;
  method: string;
  reason: string;
  evidenceIds: ID[];
  createdAt: ISOTime;
}

export interface Correction {
  id: ID;
  sessionId: ID;
  entityType: "cycle" | "reference_label" | "attempt";
  entityId: ID;
  field: string;
  previousValue: unknown;
  newValue: unknown;
  authorId: ID;
  reason: string;
  createdAt: ISOTime;
}

export interface VoiceUtterance {
  id: ID;
  sessionId: ID;
  source: "scribe_v3_live" | "typed";
  language: string;
  partialTranscript: string;
  committedSegments: string[];
  finalizedText: string | null;
  timestampsEnriched: boolean;
  enrichmentTimestamps: { word: string; startMs: number; endMs: number }[];
  selectedGoal: SupportedGoalId | null;
  goalProbabilities: Record<string, number>;
  effectiveBoundary: string;
  state: VoiceUiState;
  createdAt: ISOTime;
  finalizedAt: ISOTime | null;
  transcriptionMs: number | null;
  goalDecisionMs: number | null;
}

export interface GoalState {
  activeGoal: SupportedGoalId;
  activeGoalLabel: string;
  goalVersion: number;
  queuedGoal: SupportedGoalId | null;
  queuedGoalLabel: string | null;
  queuedBoundary: string | null;
  updatedAt: ISOTime;
}

export interface TelemetryValue {
  value: number | null;
  unit: string;
  measuredAt: ISOTime | null;
  state: "available" | "stale" | "unavailable" | "error";
}

export interface JointTelemetry {
  jointName: string;
  isPlaceholderName: boolean;
  measured: TelemetryValue;
  commanded: TelemetryValue;
  deviation: TelemetryValue;
}

export interface ComponentStatusRecord {
  id: string;
  name: string;
  roleDescription: string;
  deploymentLocation: "local_station" | "cloud_api";
  configuredIdentity: string;
  capabilityStatus: CapabilityStatus;
  connectionState: "disconnected" | "unverified" | "ready" | "active" | "error";
  statusBadgeText: string;
  calibrationOrNote: string;
  latestError: string | null;
}

export interface SoftwareStopRecord {
  requestId: ID;
  sessionId: ID | null;
  cycleId: ID | null;
  mode: SourceMode;
  command: "software_stop";
  status: "requested" | "acknowledged" | "rejected" | "unavailable";
  requestSentText: string;
  controllerAcknowledged: boolean;
  controllerStateText: string;
  physicalHaltVerified: boolean;
  physicalHaltText: "Verified" | "Unverified";
  requestedAt: ISOTime;
  acknowledgedAt: ISOTime | null;
}

export interface PauseState {
  requested: boolean;
  acknowledged: boolean;
  requestedAt: ISOTime | null;
  acknowledgedAt: ISOTime | null;
}

export interface MetricRatio {
  numerator: number;
  denominator: number;
  value: number | null; // percentage 0..100 or null when denominator === 0
  definition: string;
  sourceMode: SourceMode | "disconnected";
  sessionId: ID | null;
  excludedInProgressCount: number;
}

export interface SessionMetrics {
  sessionId: ID | null;
  sourceMode: SourceMode | "disconnected";
  confirmedCorrectCycles: MetricRatio;
  physicalExecution: MetricRatio;
  detectionAccuracy: MetricRatio & {
    totalPopulation: number;
    checkedPopulation: number;
    reviewRequiredCount: number;
  };
  defectEscape: MetricRatio;
  streak: {
    current: number;
    best: number;
    hasData: boolean;
  };
  medianFullCycleSec: {
    value: number | null;
    p50: number | null;
    p95: number | null;
    sampleCount: number;
    includesCloudWait: boolean;
  };
  cycleCounts: {
    started: number;
    finished: number;
    inProgress: number;
    correct: number;
    failed: number;
    aborted: number;
    unverified: number;
    firstAttemptSuccesses: number;
    recoveredCycles: number;
    extraInspections: number;
  };
  attemptCounts: {
    total: number;
    finished: number;
    inProgress: number;
    successful: number;
    failed: number;
    aborted: number;
    unverified: number;
    retries: number;
  };
  confusionMatrix: {
    tp: number; // defective reference, predicted defective (correctly rejected)
    tn: number; // good reference, predicted good (correctly accepted)
    fn: number; // defective reference, predicted good (defect escape!)
    fp: number; // good reference, predicted defective (false rejection)
    unlabeledCount: number;
    reviewRequiredCount: number;
  };
}

export interface StationEventEnvelope {
  schemaVersion: 1;
  eventId: ID;
  sequence: number;
  type:
    | "cycle.started"
    | "inspection.recorded"
    | "nemotron.completed"
    | "decision.recorded"
    | "execution.sent"
    | "execution.acknowledged"
    | "execution.finished"
    | "outcome.confirmed"
    | "goal.queued"
    | "goal.activated"
    | "pause.requested"
    | "pause.acknowledged"
    | "stop.requested"
    | "stop.acknowledged"
    | "correction.recorded"
    | "stream.stale";
  occurredAt: ISOTime;
  receivedAt: ISOTime;
  sourceMode: SourceMode;
  sessionId: ID;
  cycleId: ID | null;
  attemptId: ID | null;
  entityId: ID;
  entityRevision: number;
  summary: string;
  statusTone: "good" | "warn" | "bad" | "neutral";
  payload: Record<string, unknown>;
}

export type SimulationPresetId =
  | "demo_01_full"
  | "normal_success"
  | "failed_grasp_recovery"
  | "two_failed_attempts_recovery"
  | "extra_inspection_no_retry"
  | "wrong_bin_defect_escape"
  | "provider_timeout_hold"
  | "stale_evidence_rejected"
  | "queued_voice_goal"
  | "unverified_connection_loss"
  | "audited_correction"
  | "empty_session";

export interface StationSnapshot {
  viewMode: ViewMode;
  stationConnected: boolean;
  activeSession: Session | null;
  sessions: Session[];
  stateVersion: number;
  goalState: GoalState;
  pauseState: PauseState;
  stopRecord: SoftwareStopRecord | null;
  activeCycle: Cycle | null;
  cycles: Cycle[];
  attempts: Attempt[];
  inspections: Inspection[];
  frames: Frame[];
  confirmations: Confirmation[];
  referenceLabels: ReferenceLabel[];
  corrections: Correction[];
  nemotronObservations: NemotronObservation[];
  decisions: DecisionRecord[];
  skillExecutions: SkillExecution[];
  utterances: VoiceUtterance[];
  recentEvents: StationEventEnvelope[];
  lastEventSequence: number;
  components: ComponentStatusRecord[];
  joints: JointTelemetry[];
  hardwareSummary: {
    cpuLoad: TelemetryValue;
    memory: TelemetryValue;
    controlRate: TelemetryValue;
  };
  metrics: SessionMetrics;
  activeFaultBanner: string | null;
}
