/** Persisted-record transport with explicit audited review submission. Successful HTTP access does not verify hardware or providers. */
import type {
  CameraResponse, CycleDetail, CycleFilters, CyclePage, CycleReviewRequest, CycleReviewResult, EventOptions, Metrics, MetricsOptions,
  RecordType, Session, SessionExport, Snapshot, StationClientOptions, StationEvent, DashboardRead, DashboardReadOptions,
} from "./types.ts";

export class StationHttpError extends Error {
  readonly status: number;
  constructor(status: number) {
    super(`Station request failed (HTTP ${status}).`);
    this.name = "StationHttpError";
    this.status = status;
  }
}
export class StationProtocolError extends Error {
  constructor(message = "The station returned an invalid response.") {
    super(message); this.name = "StationProtocolError";
  }
}
export class StationTimeoutError extends Error {
  constructor() { super("The station request timed out."); this.name = "StationTimeoutError"; }
}
/** Reconnect after obtaining a fresh snapshot; this does not imply an incompatible API. */
export class StationStreamError extends Error {
  constructor(message = "The station event stream needs to reconnect.") { super(message); this.name = "StationStreamError"; }
}
export class StationAccessError extends Error {
  constructor() { super("A valid station access token is required."); this.name = "StationAccessError"; }
}

const REQUEST_TIMEOUT_MS = 40_000;
const EVENT_IDLE_TIMEOUT_MS = 45_000;
const JSON_LIMIT = 16 * 1024 * 1024;
const EXPORT_LIMIT = 64 * 1024 * 1024;
const EVIDENCE_LIMIT = 5 * 1024 * 1024;
const EVENT_LIMIT = 2 * 1024 * 1024;
const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_.:-]*$/;
const RECORD_TYPES: RecordType[] = ["session", "cycle", "attempt", "frame", "inspection", "model_run",
  "utterance", "decision", "execution", "reference_label", "confirmation", "evidence", "correction"];
type ObjectValue = Record<string, unknown>;
type Check = (value: unknown, path: string) => void;
function invalid(path: string): never {
  // Paths are local schema names, never untrusted response values or credentials.
  throw new StationProtocolError(`Invalid station response at ${path}.`);
}
function object(value: unknown, path: string): ObjectValue {
  if (value === null || typeof value !== "object" || Array.isArray(value)) invalid(path);
  return value as ObjectValue;
}
const string: Check = (v, p) => { if (typeof v !== "string") invalid(p); };
const text: Check = (v, p) => { string(v, p); if ((v as string).length === 0) invalid(p); };
const bool: Check = (v, p) => { if (typeof v !== "boolean") invalid(p); };
const finite: Check = (v, p) => { if (typeof v !== "number" || !Number.isFinite(v)) invalid(p); };
const count: Check = (v, p) => { if (!Number.isSafeInteger(v) || (v as number) < 0) invalid(p); };
const positive: Check = (v, p) => { count(v, p); if (v === 0) invalid(p); };
const nonnegative: Check = (v, p) => { finite(v, p); if ((v as number) < 0) invalid(p); };
const id: Check = (v, p) => {
  if (typeof v !== "string" || v.length > 120 || !ID_PATTERN.test(v)) invalid(p);
};
const eventId: Check = (v, p) => {
  // A correction's server-generated target event appends ':target' to the request ID.
  if (typeof v !== "string" || v.length > 140 || !ID_PATTERN.test(v)) invalid(p);
};
const time: Check = (v, p) => {
  if (typeof v !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(v)
      || !Number.isFinite(Date.parse(v))) invalid(p);
};
const nil: Check = (v, p) => { if (v !== null) invalid(p); };
function nullable(check: Check): Check { return (v, p) => { if (v !== null) check(v, p); }; }
function oneOf(...values: readonly unknown[]): Check { return (v, p) => { if (!values.includes(v)) invalid(p); }; }
function array(check: Check): Check {
  return (v, p) => { if (!Array.isArray(v)) invalid(p); v.forEach((item, i) => check(item, `${p}[${i}]`)); };
}
function shape(fields: Record<string, Check>): Check {
  return (v, p) => { const row = object(v, p); for (const [key, check] of Object.entries(fields)) check(row[key], `${p}.${key}`); };
}
const emptyArray: Check = (v, p) => { if (!Array.isArray(v) || v.length !== 0) invalid(p); };
const mode = oneOf("live", "simulation");
const destination = nullable(oneOf("good_bin", "defective_bin", "other"));
function jsonValue(value: unknown, path: string, depth = 0): void {
  if (depth > 100) invalid(path);
  if (value === null || typeof value === "string" || typeof value === "boolean") return;
  if (typeof value === "number") return finite(value, path);
  if (Array.isArray(value)) { value.forEach(v => jsonValue(v, path, depth + 1)); return; }
  const row = object(value, path);
  Object.values(row).forEach(v => jsonValue(v, path, depth + 1));
}
const jsonObject: Check = (v, p) => { object(v, p); jsonValue(v, p); };
const scoped = { sessionId: id, cycleId: id };
const sessionScoped = { sessionId: id, cycleId: nullable(id) };
const recordFields: Record<RecordType, Record<string, Check>> = {
  session: { name: text, sourceMode: mode, startedAt: time, endedAt: nullable(time), configId: id,
    robotId: nullable(id), modelRuns: array(jsonObject) },
  cycle: { sessionId: id, objectId: id, startedAt: time, endedAt: nullable(time),
    outcome: oneOf("in_progress", "correct", "failed", "aborted", "unverified"), commandedDestination: destination,
    observedDestination: destination, referenceLabelId: nullable(id), inspectionId: nullable(id), confirmationId: nullable(id) },
  attempt: { ...scoped, ordinal: positive, startedAt: time, endedAt: nullable(time),
    outcome: oneOf("in_progress", "successful", "failed", "aborted", "unverified"), retryOfAttemptId: nullable(id),
    retryReason: nullable(text), errorCode: nullable(text), confirmationId: nullable(id) },
  frame: { ...scoped, objectId: id, cameraId: id, capturedAt: time, receivedAt: time,
    width: positive, height: positive, evidenceId: id },
  evidence: { ...scoped, mediaType: oneOf("image/png", "image/jpeg", "application/json", "text/plain"),
    sha256: (v, p) => { if (typeof v !== "string" || !/^[a-f0-9]{64}$/.test(v)) invalid(p); },
    size: (v, p) => { positive(v, p); if ((v as number) > EVIDENCE_LIMIT) invalid(p); }, capturedAt: time },
  model_run: { ...sessionScoped, provider: text, modelId: text, requestedAt: time, completedAt: nullable(time),
    frameIds: array(id), input: jsonObject, output: nullable(jsonObject), error: nullable(string),
    latencyMs: nullable(nonnegative), device: nullable(string), precision: nullable(string) },
  inspection: { ...scoped, objectId: id, frameIds: array(id), modelRunId: id, score: finite, threshold: finite,
    classification: oneOf("good", "defective", "review_required"), mapEvidenceId: nullable(id),
    additionalInspectionOfId: nullable(id), requestedAt: time, completedAt: time },
  reference_label: { ...scoped, objectId: id, quality: oneOf("good", "defective"), authorId: id, method: text,
    evidenceIds: array(id), createdAt: time },
  confirmation: { ...scoped, source: oneOf("camera", "sensor", "operator"), evidenceIds: array(id),
    authorId: nullable(id), attemptId: nullable(id), confirmedAt: time, physicalSuccess: bool, observedDestination: destination },
  utterance: { ...sessionScoped, text, source: oneOf("voice", "typed"), provider: nullable(string), modelId: nullable(string),
    startedAt: time, completedAt: time, status: oneOf("partial", "finalized", "rejected"), language: nullable(string) },
  decision: { ...sessionScoped, kind: oneOf("goal", "task"), modelRunId: id, offeredChoices: array(id), selectedChoice: id,
    stateVersion: count, goalVersion: count, frameIds: array(id), requestedAt: time, completedAt: time,
    accepted: nullable(bool), rejectionReason: nullable(string) },
  execution: { ...scoped, attemptId: id, taskId: id, policyId: text, decisionId: nullable(id),
    status: oneOf("requested", "acknowledged", "finished", "failed", "unverified"), requestedAt: time,
    acknowledgedAt: nullable(time), finishedAt: nullable(time), error: nullable(string) },
  correction: { ...sessionScoped, eventId, entityType: oneOf("session", "cycle", "attempt", "reference_label"), entityId: id,
    expectedRevision: positive, field: text, previousValue: jsonValue, newValue: jsonValue, authorId: id,
    reason: text, createdAt: time, previousRevision: positive, newRevision: positive },
};
function record(kind: RecordType, versioned = true): Check {
  const fields = { id, ...recordFields[kind], ...(versioned ? { revision: positive } : {}) };
  return (v, p) => {
    shape(fields)(v, p);
    const row = v as ObjectValue;
    if ((kind === "cycle" || kind === "attempt") && ((row.outcome === "in_progress") !== (row.endedAt === null))) invalid(p);
    if (kind === "inspection" && (row.frameIds as unknown[]).length === 0) invalid(`${p}.frameIds`);
  };
}
const filters: Check = shape({ sessionId: nullable(id), includeSimulation: bool, includedSessionIds: array(id) });
const ratio: Check = (v, p) => {
  shape({ numerator: count, denominator: count, value: nullable(nonnegative), definition: text, filters })(v, p);
  const r = v as { numerator: number; denominator: number; value: number | null };
  if (r.numerator > r.denominator || (r.denominator === 0 ? r.value !== null :
    r.value === null || Math.abs(r.value - r.numerator / r.denominator) > 1e-12)) invalid(p);
};
function outcomeCounts(success: "correct" | "successful"): Check {
  return (v, p) => {
    shape({ [success]: count, failed: count, aborted: count, unverified: count,
      in_progress: count, total: count, finished: count, inProgress: count })(v, p);
    const r = v as Record<string, number>;
    if (r.finished !== r[success]! + r.failed! + r.aborted! + r.unverified! ||
      r.inProgress !== r.in_progress || r.total !== r.finished! + r.inProgress!) invalid(p);
  };
}
const metrics: Check = (v, p) => {
  shape({ filters, cycles: outcomeCounts("correct"), attempts: outcomeCounts("successful"),
    endToEnd: ratio, physicalExecution: ratio, firstAttemptSuccesses: count, recoveredCycles: count,
    retries: count, additionalInspections: count, currentStreak: count, longestStreak: count,
    detection: shape({ correct: count, checked: count, totalPopulation: count, unresolved: count,
      confusionMatrix: shape({ truePositive: count, trueNegative: count, falsePositive: count, falseNegative: count }),
      rate: ratio, defectEscape: ratio }),
    timings: shape({ fullCycle: shape({ sampleCount: count, valuesMs: array(nonnegative), method: text }) }),
  })(v, p);
  const m = v as Metrics;
  const d = m.detection, c = d.confusionMatrix;
  const sameFilters = (f: Metrics["filters"]) => f.sessionId === m.filters.sessionId &&
    f.includeSimulation === m.filters.includeSimulation && f.includedSessionIds.length === m.filters.includedSessionIds.length &&
    f.includedSessionIds.every((id, i) => id === m.filters.includedSessionIds[i]);
  if (m.endToEnd.numerator !== m.cycles.correct || m.endToEnd.denominator !== m.cycles.finished ||
      m.physicalExecution.numerator !== m.attempts.successful || m.physicalExecution.denominator !== m.attempts.finished ||
      d.checked > d.totalPopulation || d.totalPopulation !== m.cycles.total || d.correct !== c.truePositive + c.trueNegative ||
      d.checked !== c.truePositive + c.trueNegative + c.falsePositive + c.falseNegative + d.unresolved ||
      d.rate.numerator !== d.correct || d.rate.denominator !== d.checked || d.defectEscape.numerator !== c.falseNegative ||
      d.defectEscape.denominator > d.checked || m.currentStreak > m.longestStreak || m.longestStreak > m.cycles.correct ||
      m.firstAttemptSuccesses + m.recoveredCycles > m.cycles.correct ||
      m.timings.fullCycle.sampleCount !== m.timings.fullCycle.valuesMs.length ||
      m.timings.fullCycle.sampleCount !== m.cycles.finished ||
      ![m.endToEnd, m.physicalExecution, d.rate, d.defectEscape].every(r => sameFilters(r.filters))) invalid(p);
};
const snapshot: Check = (v, p) => {
  const capability = shape({ status: oneOf("unavailable"), verified: oneOf(false) });
  shape({ schemaVersion: oneOf(1), generatedAt: time, lastEventSequence: count, session: nullable(record("session")),
    cycle: nullable(record("cycle")), activeCycleIds: array(id), sourceMode: nullable(mode), stateVersion: count,
    goalVersion: nil, goal: nil, availableActions: emptyArray,
    capabilities: shape({ robot: capability, cameras: capability, anomalib: capability, nemotron: capability,
      gemini: capability, elevenlabs: capability }), metrics })(v, p);
  const s = v as Snapshot;
  if (s.sourceMode !== (s.session?.sourceMode ?? null) || s.metrics.filters.sessionId !== (s.session?.id ?? null) ||
      s.stateVersion !== s.lastEventSequence || (!s.session && (s.cycle !== null || s.activeCycleIds.length > 0)) ||
      (s.cycle && s.cycle.sessionId !== s.session?.id) ||
      (s.cycle?.outcome === "in_progress" && !s.activeCycleIds.includes(s.cycle.id))) invalid(p);
};
const stationEvent: Check = (v, p) => {
  shape({ sequence: positive, eventId, recordType: oneOf(...RECORD_TYPES), entityId: id, entityRevision: positive,
    sessionId: id, cycleId: nullable(id), sourceMode: mode, occurredAt: time, receivedAt: time, type: text })(v, p);
  const e = v as StationEvent;
  if (!["created", "updated", "corrected"].some(op => e.type === `${e.recordType}.${op}`)) invalid(`${p}.type`);
  record(e.recordType, false)(e.payload, `${p}.payload`);
  const payload = e.payload as unknown as ObjectValue;
  if (payload.id !== e.entityId || (e.recordType === "session" ? payload.id : payload.sessionId) !== e.sessionId ||
    (e.recordType === "cycle" ? payload.id : payload.cycleId ?? null) !== e.cycleId ||
    (e.recordType === "session" && payload.sourceMode !== e.sourceMode)) invalid(p);
};
const revision: Check = (v, p) => {
  shape({ recordType: oneOf(...RECORD_TYPES), entityId: id, revision: positive, eventId })(v, p);
  const row = v as { recordType: RecordType; record: ObjectValue; entityId: string };
  record(row.recordType, false)(row.record, `${p}.record`);
  if (row.record.id !== row.entityId) invalid(p);
};
const detailKinds = { attempts: "attempt", frames: "frame", inspections: "inspection", modelRuns: "model_run",
  utterances: "utterance", decisions: "decision", executions: "execution", referenceLabels: "reference_label",
  confirmations: "confirmation", corrections: "correction", evidence: "evidence" } as const;
const cycleDetail: Check = (v, p) => {
  shape({ cycle: record("cycle"), events: array(stationEvent), revisions: array(revision) })(v, p);
  const row = object(v, p);
  const cycle = row.cycle as CycleDetail["cycle"];
  for (const [key, kind] of Object.entries(detailKinds)) {
    array(record(kind))(row[key], `${p}.${key}`);
    for (const entity of row[key] as ObjectValue[]) {
      if (entity.sessionId !== cycle.sessionId || entity.cycleId !== cycle.id) invalid(`${p}.${key}`);
    }
  }
  for (const event of row.events as StationEvent[]) {
    if (event.sessionId !== cycle.sessionId || event.cycleId !== cycle.id) invalid(`${p}.events`);
  }
};
const cyclePage: Check = (v, p) => {
  shape({ items: array(record("cycle")), total: count, offset: count, limit: positive })(v, p);
  const page = v as CyclePage;
  if (page.limit > 1000 || page.items.length > page.limit || page.items.length > Math.max(0, page.total - page.offset)) invalid(p);
};
const cameras = shape({ status: oneOf("unavailable"), cameras: emptyArray, reason: text });
const dashboardRead: Check = (v, p) => {
  shape({ schemaVersion: oneOf(1), dashboardVersion: oneOf(1), generatedAt: time,
    lastEventSequence: count, sourceMode: mode, selectedSessionId: nullable(id),
    sessions: shape({ items: array(record('session')), total: count, limit: positive, hasMore: bool }),
    snapshot, metrics, recentCycles: cyclePage, cameras,
    currentDetail: nullable(cycleDetail), detail: nullable(cycleDetail) })(v, p);
  const data = v as DashboardRead;
  const sameCycle = (a: CycleDetail['cycle'], b: CycleDetail['cycle']) =>
    ['id', 'revision', ...Object.keys(recordFields.cycle)].every(key =>
      JSON.stringify((a as unknown as ObjectValue)[key]) === JSON.stringify((b as unknown as ObjectValue)[key]));
  bool(data.recentCycles.hasMore, `${p}.recentCycles.hasMore`);
  const selected = data.selectedSessionId;
  if (data.sessions.limit > 50 || data.sessions.items.length > data.sessions.limit ||
      data.sessions.items.length > data.sessions.total ||
      data.sessions.hasMore !== (data.sessions.total > data.sessions.items.length) ||
      new Set(data.sessions.items.map(s => s.id)).size !== data.sessions.items.length ||
      data.sessions.items.some(s => s.sourceMode !== data.sourceMode) ||
      data.snapshot.generatedAt !== data.generatedAt || data.snapshot.lastEventSequence !== data.lastEventSequence ||
      (data.snapshot.session?.id ?? null) !== selected ||
      (data.snapshot.session && data.snapshot.sourceMode !== data.sourceMode) ||
      data.metrics.filters.sessionId !== selected ||
      data.metrics.filters.includeSimulation !== (data.sourceMode === 'simulation') ||
      data.metrics.filters.includedSessionIds.some(s => s !== selected) ||
      JSON.stringify(data.metrics) !== JSON.stringify(data.snapshot.metrics) ||
      data.recentCycles.offset !== 0 || data.recentCycles.limit > 100 ||
      data.recentCycles.hasMore !== (data.recentCycles.total > data.recentCycles.items.length) ||
      data.recentCycles.items.some(c => c.sessionId !== selected) ||
      (data.currentDetail?.cycle.id ?? null) !== (data.snapshot.cycle?.id ?? null) ||
      (data.currentDetail && data.snapshot.cycle && !sameCycle(data.currentDetail.cycle, data.snapshot.cycle)) ||
      [data.currentDetail, data.detail].some(d => d && (d.cycle.sessionId !== selected ||
        d.events.some(event => event.sequence > data.lastEventSequence) ||
        data.recentCycles.items.some(c => c.id === d.cycle.id && !sameCycle(c, d.cycle))))) invalid(p);
};
const sessionExport: Check = (v, p) => {
  shape({ schemaVersion: oneOf(1), exportedAt: time, session: record("session"), events: array(stationEvent),
    revisions: array(revision), metrics })(v, p);
  const data = v as SessionExport;
  object(data.records, `${p}.records`);
  for (const kind of RECORD_TYPES) {
    if (kind === "session") continue;
    array(record(kind))(data.records[kind], `${p}.records.${kind}`);
    if (data.records[kind].some(row => row.sessionId !== data.session.id)) invalid(`${p}.records.${kind}`);
  }
  if (data.events.some(e => e.sessionId !== data.session.id) || data.metrics.filters.sessionId !== data.session.id) invalid(p);
};

function abortError(): DOMException { return new DOMException("The station request was aborted.", "AbortError"); }
/** Abort races also cover custom fetch implementations and token providers that ignore signals. */
class RequestScope {
  readonly controller = new AbortController();
  private timer: ReturnType<typeof setTimeout> | undefined;
  private readonly external: AbortSignal | undefined;
  private readonly onExternal = () => this.controller.abort(abortError());
  constructor(signal?: AbortSignal) {
    this.external = signal;
    if (signal?.aborted) this.onExternal();
    else signal?.addEventListener("abort", this.onExternal, { once: true });
  }
  arm(ms: number): void { this.disarm(); this.timer = setTimeout(() => this.controller.abort(new StationTimeoutError()), ms); }
  disarm(): void { if (this.timer !== undefined) clearTimeout(this.timer); this.timer = undefined; }
  async run<T>(operation: Promise<T>): Promise<T> {
    const signal = this.controller.signal;
    if (signal.aborted) { void operation.catch(() => {}); throw signal.reason; }
    let onAbort: () => void = () => {};
    const stopped = new Promise<never>((_, reject) => {
      onAbort = () => reject(signal.reason);
      signal.addEventListener("abort", onAbort, { once: true });
    });
    try { return await Promise.race([operation, stopped]); }
    finally { signal.removeEventListener("abort", onAbort); }
  }
  close(): void {
    this.disarm(); this.external?.removeEventListener("abort", this.onExternal);
    if (!this.controller.signal.aborted) this.controller.abort(abortError());
  }
}
function dispose(reader: ReadableStreamDefaultReader<Uint8Array>): void {
  void reader.cancel().catch(() => {});
  try { reader.releaseLock(); } catch { /* A canceled pending read may still be settling. */ }
}
function mediaType(response: Response): string {
  return (response.headers.get("Content-Type") ?? "").split(";", 1)[0]!.trim().toLowerCase();
}
async function body(response: Response, limit: number, scope: RequestScope): Promise<Uint8Array> {
  const declared = response.headers.get("Content-Length");
  if (declared !== null && (!/^\d+$/.test(declared) || Number(declared) > limit)) {
    void response.body?.cancel().catch(() => {});
    throw new StationProtocolError("The station response exceeds the allowed size.");
  }
  if (!response.body) throw new StationProtocolError("The station response has no body.");
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = []; let size = 0;
  try {
    while (true) {
      const part = await scope.run(reader.read());
      if (part.done) break;
      size += part.value.byteLength;
      if (size > limit) throw new StationProtocolError("The station response exceeds the allowed size.");
      chunks.push(part.value);
    }
  } finally { dispose(reader); }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return bytes;
}
function decode(bytes: Uint8Array): string {
  try { return new TextDecoder("utf-8", { fatal: true }).decode(bytes); }
  catch { throw new StationProtocolError("The station response is not valid UTF-8."); }
}
function parseJson(value: string): unknown {
  try { return JSON.parse(value) as unknown; }
  catch { throw new StationProtocolError("The station response is not valid JSON."); }
}
function parsed<T>(value: unknown, check: Check): T { check(value, "response"); return value as T; }
function argumentId(value: string): string {
  if (typeof value !== "string" || value.length > 120 || !ID_PATTERN.test(value)) throw new TypeError("A valid station record ID is required.");
  return encodeURIComponent(value);
}
function argumentCount(value: number, min: number, max: number): void {
  if (!Number.isSafeInteger(value) || value < min || value > max) throw new TypeError("Invalid station cursor or pagination limit.");
}

interface RawEvent { id: string; type: string; data: string }
/** Parses UTF-8 chunks after decoding; CR, LF, CRLF, comments and multiline data follow SSE framing. */
class SSEParser {
  private line = "";
  private skipLF = false;
  private data: string[] = [];
  private id: string | undefined;
  private type: string | undefined;
  private size = 0;
  private readonly encoder = new TextEncoder();
  *feed(text: string): Generator<RawEvent> {
    let start = 0;
    for (let i = 0; i < text.length; i++) {
      const char = text[i];
      if (this.skipLF) {
        this.skipLF = false;
        if (char === "\n") { start = i + 1; continue; }
      }
      if (char !== "\r" && char !== "\n") continue;
      this.line += text.slice(start, i); this.boundLine();
      const event = this.consumeLine(this.line);
      this.line = ""; this.skipLF = char === "\r"; start = i + 1;
      if (event) yield event;
    }
    this.line += text.slice(start); this.boundLine();
  }
  private boundLine(): void {
    if (this.line.length > EVENT_LIMIT || this.size + this.encoder.encode(this.line).byteLength > EVENT_LIMIT)
      throw new StationProtocolError("A station event exceeds the allowed size.");
  }
  private consumeLine(line: string): RawEvent | undefined {
    this.size += this.encoder.encode(line).byteLength + 1;
    if (this.size > EVENT_LIMIT) throw new StationProtocolError("A station event exceeds the allowed size.");
    if (line === "") {
      let event: RawEvent | undefined;
      if (this.data.length) {
        if (this.id === undefined || this.type === undefined) throw new StationProtocolError("A station event is missing its ID or type.");
        event = { id: this.id, type: this.type, data: this.data.join("\n") };
      }
      this.data = []; this.id = undefined; this.type = undefined; this.size = 0;
      return event;
    }
    if (line.startsWith(":")) return;
    const colon = line.indexOf(":");
    const field = colon < 0 ? line : line.slice(0, colon);
    let value = colon < 0 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "data") this.data.push(value);
    else if (field === "id") this.id = value;
    else if (field === "event") this.type = value;
  }
  finish(): void {
    // An unfinished event must never advance the reconnect cursor.
    if (this.line || this.data.length || this.id !== undefined || this.type !== undefined)
      throw new StationStreamError("The station event stream ended in an incomplete event.");
  }
}

export class StationClient {
  private readonly origin: string;
  private readonly getToken: (() => string | Promise<string>) | undefined;
  private readonly authMode: "direct" | "same-origin-proxy";
  private readonly fetcher: typeof fetch;
  constructor(options: StationClientOptions) {
    let url: URL;
    try { url = new URL(options.baseUrl); } catch { throw new TypeError("Station baseUrl must be an HTTP(S) origin."); }
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.pathname !== "/" || url.search || url.hash)
      throw new TypeError("Station baseUrl must be an HTTP(S) origin without credentials, path, query or fragment.");
    if (options.authMode !== undefined && options.authMode !== "direct" && options.authMode !== "same-origin-proxy")
      throw new TypeError("Unsupported station authentication mode.");
    this.origin = url.origin;
    this.authMode = options.authMode ?? "direct";
    if (this.authMode === "same-origin-proxy") {
      if (options.getToken !== undefined) throw new TypeError("Proxy authentication must not receive a browser token.");
      this.assertProxyOrigin();
      this.getToken = undefined;
    } else {
      if (typeof options.getToken !== "function") throw new TypeError("Station getToken is required.");
      this.getToken = options.getToken;
    }
    this.fetcher = options.fetch ?? globalThis.fetch.bind(globalThis);
  }
  private assertProxyOrigin(): void {
    if (typeof globalThis.location === "undefined" || globalThis.location.origin !== this.origin)
      throw new TypeError("Station proxy mode requires the current browser origin.");
  }
  private url(path: string, query: Record<string, string | number | boolean | undefined> = {}): URL {
    const url = new URL(`/api/v1${path}`, this.origin);
    for (const [key, value] of Object.entries(query)) if (value !== undefined) url.searchParams.set(key, String(value));
    return url;
  }
  private async open(url: URL, accept: string, scope: RequestScope, payload?: string): Promise<Response> {
    const headers: Record<string, string> = { Accept: accept };
    if (payload !== undefined) { headers["Content-Type"] = "application/json"; headers["X-Morph-Intent"] = "record-review"; }
    if (this.authMode === "same-origin-proxy") {
      this.assertProxyOrigin();
    } else {
      let token: string;
      try { token = await scope.run(Promise.resolve().then(() => this.getToken!())); }
      catch (error) {
        if (scope.controller.signal.aborted) throw scope.controller.signal.reason;
        throw new StationAccessError();
      }
      if (typeof token !== "string" || token.length < 32 || !/^[!-~]+$/.test(token)) throw new StationAccessError();
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await scope.run(this.fetcher(url, { method: payload === undefined ? "GET" : "POST", headers, body: payload,
      credentials: "omit", redirect: "error", cache: "no-store", referrerPolicy: "no-referrer", signal: scope.controller.signal }));
    if (!response.ok) { void response.body?.cancel().catch(() => {}); throw new StationHttpError(response.status); }
    return response;
  }
  private async request<T>(url: URL, accept: string, signal: AbortSignal | undefined,
    read: (response: Response, scope: RequestScope) => Promise<T>): Promise<T> {
    const scope = new RequestScope(signal); scope.arm(REQUEST_TIMEOUT_MS);
    try { return await read(await this.open(url, accept, scope), scope); }
    finally { scope.close(); }
  }
  private json<T>(url: URL, check: Check, signal?: AbortSignal, limit = JSON_LIMIT): Promise<T> {
    return this.request(url, "application/json", signal, async (response, scope) => {
      if (mediaType(response) !== "application/json") throw new StationProtocolError("Expected a JSON station response.");
      return parsed<T>(parseJson(decode(await body(response, limit, scope))), check);
    });
  }
  /** Caller retains this exact request for an uncertain-result retry; never retries automatically. */
  async reviewCycle(cycleId: string, request: CycleReviewRequest, signal?: AbortSignal): Promise<CycleReviewResult> {
    const path = `/cycles/${argumentId(cycleId)}/review`;
    argumentId(request.id); argumentId(request.eventId); argumentId(request.authorId);
    argumentCount(request.expectedRevision, 1, Number.MAX_SAFE_INTEGER);
    time(request.createdAt, "request.createdAt");
    if (!request.reason.trim()) throw new TypeError("A review reason is required.");
    const payload = JSON.stringify(request);
    if (new TextEncoder().encode(payload).length > 64 * 1024) throw new TypeError("Review is too large.");
    const scope = new RequestScope(signal); scope.arm(REQUEST_TIMEOUT_MS);
    try {
      const response = await this.open(this.url(path), "application/json", scope, payload);
      if (mediaType(response) !== "application/json") throw new StationProtocolError("Expected a JSON review response.");
      const result = parsed<CycleReviewResult>(parseJson(decode(await body(response, JSON_LIMIT, scope))),
        shape({ cycle: cycleDetail, duplicate: bool }));
      if (result.cycle.cycle.id !== cycleId) invalid("response.cycle.cycle.id");
      return result;
    } finally { scope.close(); }
  }
  async getSnapshot(sessionId?: string, signal?: AbortSignal): Promise<Snapshot> {
    if (sessionId !== undefined) argumentId(sessionId);
    const result = await this.json<Snapshot>(this.url("/station/snapshot", { sessionId }), snapshot, signal);
    if (sessionId !== undefined && result.session?.id !== sessionId) invalid("response.session.id");
    return result;
  }
  async supportsDashboard(signal?: AbortSignal): Promise<boolean> {
    const schema = await this.json<Record<string, unknown>>(this.url('/schema'), object, signal);
    const capabilities = schema.capabilities;
    if (!capabilities || typeof capabilities !== 'object') return false;
    const advertised = (capabilities as Record<string, unknown>).dashboardRead;
    return !!advertised && typeof advertised === 'object' &&
      (advertised as Record<string, unknown>).version === 1 &&
      (advertised as Record<string, unknown>).path === '/api/v1/dashboard';
  }
  async getDashboard(options: DashboardReadOptions, signal?: AbortSignal): Promise<DashboardRead> {
    if (!['live', 'simulation'].includes(options.sourceMode)) throw new TypeError('Choose live or simulation.');
    if (options.sessionId !== undefined) argumentId(options.sessionId);
    if (options.cycleId !== undefined) argumentId(options.cycleId);
    argumentCount(options.limit ?? 20, 1, 100);
    const result = await this.json<DashboardRead>(this.url('/dashboard', { ...options, limit: options.limit ?? 20 }), dashboardRead, signal, 4 * 1024 * 1024);
    if (result.sourceMode !== options.sourceMode || result.recentCycles.limit !== (options.limit ?? 20) ||
        (options.sessionId !== undefined && result.selectedSessionId !== options.sessionId) ||
        (options.cycleId !== undefined && result.detail?.cycle.id !== options.cycleId)) invalid('response.selection');
    return result;
  }
  listSessions(signal?: AbortSignal): Promise<Session[]> {
    return this.json(this.url("/sessions"), array(record("session")), signal);
  }
  async getMetrics(options: MetricsOptions = {}, signal?: AbortSignal): Promise<Metrics> {
    const path = options.sessionId === undefined ? "/metrics" : `/sessions/${argumentId(options.sessionId)}/metrics`;
    const result = await this.json<Metrics>(this.url(path, { includeSimulation: options.includeSimulation ?? false }), metrics, signal);
    if (result.filters.sessionId !== (options.sessionId ?? null) || result.filters.includeSimulation !== (options.includeSimulation ?? false))
      invalid("response.filters");
    return result;
  }
  async listCycles(filters: CycleFilters = {}, signal?: AbortSignal): Promise<CyclePage> {
    if (filters.sessionId !== undefined) argumentId(filters.sessionId);
    if (filters.objectId !== undefined) argumentId(filters.objectId);
    argumentCount(filters.offset ?? 0, 0, Number.MAX_SAFE_INTEGER);
    argumentCount(filters.limit ?? 100, 1, 1000);
    const result = await this.json<CyclePage>(this.url("/cycles", { ...filters }), cyclePage, signal);
    if (result.offset !== (filters.offset ?? 0) || result.limit !== (filters.limit ?? 100) ||
      result.items.some(c => (filters.sessionId !== undefined && c.sessionId !== filters.sessionId) ||
        (filters.objectId !== undefined && c.objectId !== filters.objectId) || (filters.outcome !== undefined && c.outcome !== filters.outcome)))
      invalid("response.items");
    return result;
  }
  async getCycle(id: string, signal?: AbortSignal): Promise<CycleDetail> {
    const result = await this.json<CycleDetail>(this.url(`/cycles/${argumentId(id)}`), cycleDetail, signal);
    if (result.cycle.id !== id) invalid("response.cycle.id");
    return result;
  }
  getCameras(signal?: AbortSignal): Promise<CameraResponse> { return this.json(this.url("/cameras"), cameras, signal); }
  getEvidence(id: string, signal?: AbortSignal): Promise<Blob> {
    return this.request(this.url(`/evidence/${argumentId(id)}`), "image/png,image/jpeg,application/json,text/plain", signal,
      async (response, scope) => {
        const type = mediaType(response);
        if (!["image/png", "image/jpeg", "application/json", "text/plain"].includes(type))
          throw new StationProtocolError("The station evidence has an unsupported media type.");
        const bytes = await body(response, EVIDENCE_LIMIT, scope);
        if (!bytes.byteLength) throw new StationProtocolError("The station evidence is empty.");
        return new Blob([bytes as Uint8Array<ArrayBuffer>], { type });
      });
  }
  exportSession(id: string, format: "json", signal?: AbortSignal): Promise<SessionExport>;
  exportSession(id: string, format: "csv", signal?: AbortSignal): Promise<string>;
  exportSession(id: string, format: "json" | "csv", signal?: AbortSignal): Promise<SessionExport | string>;
  async exportSession(id: string, format: "json" | "csv", signal?: AbortSignal): Promise<SessionExport | string> {
    if (format !== "json" && format !== "csv") throw new TypeError("Unsupported station export format.");
    const url = this.url(`/sessions/${argumentId(id)}/export`, { format });
    if (format === "json") {
      const result = await this.json<SessionExport>(url, sessionExport, signal, EXPORT_LIMIT);
      if (result.session.id !== id) invalid("response.session.id");
      return result;
    }
    return this.request(url, "text/csv", signal, async (response, scope) => {
      if (mediaType(response) !== "text/csv") throw new StationProtocolError("Expected a CSV station response.");
      const csv = decode(await body(response, EXPORT_LIMIT, scope));
      if (!/^section,recordType,id,dataJson\r?\n/.test(csv)) throw new StationProtocolError("Invalid station CSV export header.");
      return csv;
    });
  }
  /** One connection only. The caller owns backoff, auth recovery and snapshot refresh after HTTP 409. */
  async *events(options: EventOptions): AsyncIterable<StationEvent> {
    argumentCount(options.after, 0, Number.MAX_SAFE_INTEGER);
    argumentCount(options.limit ?? 100, 1, 1000);
    const scope = new RequestScope(options.signal); scope.arm(REQUEST_TIMEOUT_MS);
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    let cursor = options.after;
    try {
      const response = await this.open(this.url("/events", { after: cursor, once: options.once ?? false, limit: options.limit }), "text/event-stream", scope);
      if (response.status !== 200 || mediaType(response) !== "text/event-stream" || !response.body)
        throw new StationProtocolError("Expected a station event stream.");
      scope.disarm(); reader = response.body.getReader();
      options.onOpen?.();
      const decoder = new TextDecoder("utf-8", { fatal: true });
      const parser = new SSEParser();
      while (true) {
        scope.arm(EVENT_IDLE_TIMEOUT_MS);
        const part = await scope.run(reader.read()); scope.disarm();
        let text: string;
        try { text = part.done ? decoder.decode() : decoder.decode(part.value, { stream: true }); }
        catch {
          if (part.done) throw new StationStreamError("The station event stream ended in an incomplete UTF-8 character.");
          throw new StationProtocolError("The station event stream is not valid UTF-8.");
        }
        for (const raw of parser.feed(text)) {
          if (!/^\d+$/.test(raw.id)) throw new StationProtocolError("Invalid station event cursor.");
          const sequence = Number(raw.id);
          const event = parsed<StationEvent>(parseJson(raw.data), stationEvent);
          if (!Number.isSafeInteger(sequence) || sequence !== event.sequence || raw.type !== event.type)
            throw new StationProtocolError("Station event cursor, order or type does not match its payload.");
          if (sequence <= cursor) continue;
          // A missing global event invalidates the read model; never silently skip it.
          if (sequence !== cursor + 1) throw new StationStreamError("The station event stream has a sequence gap.");
          cursor = sequence;
          yield event;
        }
        if (part.done) {
          parser.finish();
          if (!options.once) throw new StationStreamError("The live station event stream ended.");
          return;
        }
      }
    } finally { if (reader) dispose(reader); scope.close(); }
  }
}
