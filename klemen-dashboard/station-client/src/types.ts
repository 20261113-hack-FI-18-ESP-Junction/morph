/** M06 persisted wire records. These describe software data, not verified hardware capabilities. */
export type ID = string;
export type ISOTime = string;
export type SourceMode = "live" | "simulation";
export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };
export type Destination = "good_bin" | "defective_bin" | "other";
export type CycleOutcome = "in_progress" | "correct" | "failed" | "aborted" | "unverified";
export type AttemptOutcome = "in_progress" | "successful" | "failed" | "aborted" | "unverified";
export interface Versioned { id: ID; revision: number }
export interface SessionScoped extends Versioned { sessionId: ID; cycleId: ID | null }
export interface CycleScoped extends SessionScoped { cycleId: ID }

export interface Session extends Versioned {
  name: string; sourceMode: SourceMode; startedAt: ISOTime; endedAt: ISOTime | null;
  configId: ID; robotId: ID | null; modelRuns: JsonObject[];
}
export interface Cycle extends Versioned {
  sessionId: ID; objectId: ID; startedAt: ISOTime; endedAt: ISOTime | null;
  outcome: CycleOutcome; commandedDestination: Destination | null; observedDestination: Destination | null;
  referenceLabelId: ID | null; inspectionId: ID | null; confirmationId: ID | null;
}
export interface Attempt extends CycleScoped {
  ordinal: number; startedAt: ISOTime; endedAt: ISOTime | null; outcome: AttemptOutcome;
  retryOfAttemptId: ID | null; retryReason: string | null; errorCode: string | null; confirmationId: ID | null;
}
export type EvidenceMediaType = "image/png" | "image/jpeg" | "application/json" | "text/plain";
export interface Evidence extends CycleScoped {
  mediaType: EvidenceMediaType; sha256: string; size: number; capturedAt: ISOTime;
}
export interface Frame extends CycleScoped {
  objectId: ID; cameraId: ID; capturedAt: ISOTime; receivedAt: ISOTime;
  width: number; height: number; evidenceId: ID;
}
export interface ModelRun extends SessionScoped {
  provider: string; modelId: string; requestedAt: ISOTime; completedAt: ISOTime | null;
  frameIds: ID[]; input: JsonObject; output: JsonObject | null; error: string | null;
  latencyMs: number | null; device: string | null; precision: string | null;
}
export interface Inspection extends CycleScoped {
  objectId: ID; frameIds: ID[]; modelRunId: ID; score: number; threshold: number;
  classification: "good" | "defective" | "review_required";
  mapEvidenceId: ID | null; additionalInspectionOfId: ID | null;
  requestedAt: ISOTime; completedAt: ISOTime;
}
export interface ReferenceLabel extends CycleScoped {
  objectId: ID; quality: "good" | "defective"; authorId: ID; method: string; evidenceIds: ID[]; createdAt: ISOTime;
}
export interface Confirmation extends CycleScoped {
  source: "camera" | "sensor" | "operator"; evidenceIds: ID[]; authorId: ID | null;
  attemptId: ID | null; confirmedAt: ISOTime; physicalSuccess: boolean; observedDestination: Destination | null;
}
export interface Utterance extends SessionScoped {
  text: string; source: "voice" | "typed"; provider: string | null; modelId: string | null;
  startedAt: ISOTime; completedAt: ISOTime; status: "partial" | "finalized" | "rejected"; language: string | null;
}
export interface Decision extends SessionScoped {
  kind: "goal" | "task"; modelRunId: ID; offeredChoices: ID[]; selectedChoice: ID;
  stateVersion: number; goalVersion: number; frameIds: ID[]; requestedAt: ISOTime; completedAt: ISOTime;
  accepted: boolean | null; rejectionReason: string | null;
}
export interface Execution extends CycleScoped {
  attemptId: ID; taskId: ID; policyId: string; decisionId: ID | null;
  status: "requested" | "acknowledged" | "finished" | "failed" | "unverified";
  requestedAt: ISOTime; acknowledgedAt: ISOTime | null; finishedAt: ISOTime | null; error: string | null;
}
export interface Correction extends SessionScoped {
  eventId: ID; entityType: "session" | "cycle" | "attempt" | "reference_label"; entityId: ID;
  expectedRevision: number; field: string; previousValue: JsonValue; newValue: JsonValue;
  authorId: ID; reason: string; createdAt: ISOTime; previousRevision: number; newRevision: number;
}
export interface RecordMap {
  session: Session; cycle: Cycle; attempt: Attempt; frame: Frame; inspection: Inspection;
  model_run: ModelRun; utterance: Utterance; decision: Decision; execution: Execution;
  reference_label: ReferenceLabel; confirmation: Confirmation; evidence: Evidence; correction: Correction;
}
export type RecordType = keyof RecordMap;
export type RecordPayloadMap = { [K in RecordType]: Omit<RecordMap[K], "revision"> };
/** Global sequence, not a per-session sequence. Payloads do not include the read record's revision. */
export type StationEvent = { [K in RecordType]: {
  sequence: number; eventId: string; type: `${K}.${"created" | "updated" | "corrected"}`;
  recordType: K; entityId: ID; entityRevision: number; sessionId: ID; cycleId: ID | null;
  sourceMode: SourceMode; occurredAt: ISOTime; receivedAt: ISOTime; payload: RecordPayloadMap[K];
} }[RecordType];
export type Revision = { [K in RecordType]: {
  recordType: K; entityId: ID; revision: number; eventId: string; record: RecordPayloadMap[K];
} }[RecordType];
export interface MetricsFilters {
  sessionId: ID | null; includeSimulation: boolean; includedSessionIds: ID[];
}
/** value is a fraction in [0,1], or null when the denominator is zero. */
export interface Ratio {
  numerator: number; denominator: number; value: number | null; definition: string; filters: MetricsFilters;
}
export interface OutcomeCounts {
  failed: number; aborted: number; unverified: number; in_progress: number;
  total: number; finished: number; inProgress: number;
}
export interface Metrics {
  filters: MetricsFilters;
  cycles: OutcomeCounts & { correct: number };
  attempts: OutcomeCounts & { successful: number };
  endToEnd: Ratio; physicalExecution: Ratio;
  firstAttemptSuccesses: number; recoveredCycles: number; retries: number; additionalInspections: number;
  currentStreak: number; longestStreak: number;
  detection: {
    correct: number; checked: number; totalPopulation: number; unresolved: number;
    confusionMatrix: { truePositive: number; trueNegative: number; falsePositive: number; falseNegative: number };
    rate: Ratio; defectEscape: Ratio;
  };
  timings: { fullCycle: { sampleCount: number; valuesMs: number[]; method: string } };
}
export interface UnavailableCapability { status: "unavailable"; verified: false }
export interface StationCapabilities {
  robot: UnavailableCapability; cameras: UnavailableCapability; anomalib: UnavailableCapability;
  nemotron: UnavailableCapability; gemini: UnavailableCapability; elevenlabs: UnavailableCapability;
}
/** stateVersion is the persisted global event sequence in M06, not a robot state version. */
export interface Snapshot {
  schemaVersion: 1; generatedAt: ISOTime; lastEventSequence: number;
  session: Session | null; cycle: Cycle | null; activeCycleIds: ID[]; sourceMode: SourceMode | null;
  stateVersion: number; goalVersion: null; goal: null; availableActions: [];
  capabilities: StationCapabilities; metrics: Metrics;
}
export interface CycleDetail {
  cycle: Cycle; attempts: Attempt[]; frames: Frame[]; inspections: Inspection[]; modelRuns: ModelRun[];
  utterances: Utterance[]; decisions: Decision[]; executions: Execution[]; referenceLabels: ReferenceLabel[];
  confirmations: Confirmation[]; corrections: Correction[]; evidence: Evidence[];
  events: StationEvent[]; revisions: Revision[];
}
export interface CycleFilters {
  sessionId?: ID; objectId?: ID; outcome?: CycleOutcome; sourceMode?: SourceMode; includeSimulation?: boolean;
  hasRetry?: boolean; errorCode?: string; modelId?: string; referenceStatus?: "labeled" | "unlabeled";
  startedAfter?: ISOTime; startedBefore?: ISOTime; offset?: number; limit?: number;
}
export interface CyclePage { items: Cycle[]; total: number; offset: number; limit: number }
export interface CameraResponse { status: "unavailable"; cameras: []; reason: string }
export interface SessionExport {
  schemaVersion: 1; exportedAt: ISOTime; session: Session;
  records: { [K in Exclude<RecordType, "session">]: RecordMap[K][] };
  events: StationEvent[]; revisions: Revision[]; metrics: Metrics;
}
export interface MetricsOptions { sessionId?: ID; includeSimulation?: boolean }
export interface EventOptions {
  after: number; signal?: AbortSignal; once?: boolean; limit?: number;
  /** Called after authenticated HTTP 200 and event-stream headers, including when the stream is quiet. */
  onOpen?: () => void;
}
interface StationClientBaseOptions {
  /** HTTP(S) origin only; no credentials, path prefix, query or fragment. */
  baseUrl: string;
  fetch?: typeof fetch;
}
export type StationClientOptions = StationClientBaseOptions & (
  | {
    authMode?: "direct";
    /** Supplied by the host application. The client does not persist or log tokens. */
    getToken: () => string | Promise<string>;
  }
  | {
    /** Browser-only, same-origin local server supplies the upstream station credential. */
    authMode: "same-origin-proxy";
    getToken?: never;
  }
);

/** An explicit human review of existing records; never a robot command. */
export interface CycleReviewRequest {
  id: ID; eventId: ID; expectedRevision: number; authorId: ID; reason: string; createdAt: ISOTime;
  label?: { id: ID; quality: "good" | "defective"; method: string; evidenceIds: ID[]; expectedRevision?: number };
  confirmation?: { id: ID; source: "operator"; confirmedAt: ISOTime; physicalSuccess: boolean;
    observedDestination: Destination | null; evidenceIds: ID[]; attemptId?: ID;
    expectedAttemptRevision?: number; attemptOutcome?: Exclude<AttemptOutcome, "in_progress"> };
  changes?: { outcome?: Exclude<CycleOutcome, "in_progress">; observedDestination?: Destination | null };
}
export interface CycleReviewResult { cycle: CycleDetail; duplicate: boolean }
