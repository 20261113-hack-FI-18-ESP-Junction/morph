import type {
  Attempt,
  CanonicalPhase,
  Confirmation,
  Correction,
  Cycle,
  DecisionRecord,
  Destination,
  Frame,
  GoalState,
  ID,
  Inspection,
  ISOTime,
  NemotronObservation,
  Outcome,
  PauseState,
  PermittedTaskId,
  Quality,
  ReferenceLabel,
  Session,
  SimulationPresetId,
  SkillExecution,
  SoftwareStopRecord,
  SourceMode,
  StationEventEnvelope,
  StationSnapshot,
  SupportedGoalId,
  ViewMode,
  VoiceUtterance,
} from "./prototypeTypes.ts";
import {
  buildDisconnectedLiveSnapshot,
  buildSimulationSnapshot,
  DEFAULT_COMPONENTS,
  DEFAULT_JOINTS,
  DEFAULT_MODEL_RUNS,
  SIMULATION_SCENE_URL,
} from "./fixtures.ts";
import {
  appendCommittedSegment,
  applyOrderedEvent,
  applyPartialTranscript,
  commitQueuedGoalAtBoundary,
  computeSessionMetrics,
  enrichUtteranceTimestamps,
  evaluateCycleOutcome,
  type EventLogState,
  finalizeUtteranceOnce,
  validateTaskDispatch,
} from "./stationLogic.ts";

const CANONICAL_PHASES: CanonicalPhase[] = [
  "observe",
  "pick",
  "verify_grasp",
  "present",
  "inspect",
  "choose_task",
  "place",
  "verify_outcome",
];

export class StationStore {
  private viewMode: ViewMode = "live"; // Default hardware view to disconnected/empty until connected
  private presetId: SimulationPresetId = "demo_01_full";
  private liveStationConnected = false;

  // Authoritative persisted collections (simulation and live isolated by session.sourceMode)
  private sessions: Map<ID, Session> = new Map();
  private activeSessionIdByMode: { live: ID | null; simulation: ID | null; replay: ID | null } = {
    live: null,
    simulation: null,
    replay: null,
  };

  private cycles: Map<ID, Cycle> = new Map();
  private attempts: Map<ID, Attempt> = new Map();
  private inspections: Map<ID, Inspection> = new Map();
  private frames: Map<ID, Frame> = new Map();
  private confirmations: Map<ID, Confirmation> = new Map();
  private referenceLabels: Map<ID, ReferenceLabel> = new Map();
  private corrections: Map<ID, Correction> = new Map();
  private nemotronObservations: Map<ID, NemotronObservation> = new Map();
  private decisions: Map<ID, DecisionRecord> = new Map();
  private skillExecutions: Map<ID, SkillExecution> = new Map();
  private utterances: Map<ID, VoiceUtterance> = new Map();

  private stateVersion = 24;
  private goalState: GoalState = {
    activeGoal: "standard_sorting",
    activeGoalLabel: "Standard sorting",
    goalVersion: 1,
    queuedGoal: "extra_view_next_reject",
    queuedGoalLabel: "Additional view",
    queuedBoundary: "Next boundary",
    updatedAt: "2026-11-14T13:42:07.120Z",
  };

  private pauseState: PauseState = {
    requested: false,
    acknowledged: false,
    requestedAt: null,
    acknowledgedAt: null,
  };

  private stopRecord: SoftwareStopRecord | null = null;
  private activeFaultBanner: string | null = null;

  private eventLog: EventLogState = {
    appliedEventIds: new Set(),
    entityRevisions: new Map(),
    lastSequence: 0,
    events: [],
    resyncRequired: false,
    detectedGapRange: null,
  };

  constructor(initialViewMode: ViewMode = "live") {
    this.seedSimulationPreset("demo_01_full");
    this.viewMode = initialViewMode;
  }

  public seedSimulationPreset(presetId: SimulationPresetId): StationSnapshot {
    this.presetId = presetId;
    const snap = buildSimulationSnapshot(presetId, "simulation");

    if (snap.activeSession) {
      this.sessions.set(snap.activeSession.id, snap.activeSession);
      this.activeSessionIdByMode.simulation = snap.activeSession.id;
      if (!this.activeSessionIdByMode.replay) {
        this.activeSessionIdByMode.replay = snap.activeSession.id;
      }
    }

    // Clear previous cycles belonging to this specific preset session before re-seeding
    const targetSessionId = snap.activeSession?.id;
    if (targetSessionId) {
      for (const [id, c] of this.cycles) {
        if (c.sessionId === targetSessionId) {
          this.cycles.delete(id);
        }
      }
    }

    for (const c of snap.cycles) this.cycles.set(c.id, c);
    for (const a of snap.attempts) this.attempts.set(a.id, a);
    for (const i of snap.inspections) this.inspections.set(i.id, i);
    for (const f of snap.frames) this.frames.set(f.id, f);
    for (const cf of snap.confirmations) this.confirmations.set(cf.id, cf);
    for (const rl of snap.referenceLabels) this.referenceLabels.set(rl.id, rl);
    for (const cor of snap.corrections) this.corrections.set(cor.id, cor);
    for (const nem of snap.nemotronObservations) this.nemotronObservations.set(nem.id, nem);
    for (const dec of snap.decisions) this.decisions.set(dec.id, dec);
    for (const ex of snap.skillExecutions) this.skillExecutions.set(ex.id, ex);
    for (const utt of snap.utterances) this.utterances.set(utt.id, utt);

    this.stateVersion = snap.stateVersion;
    this.goalState = snap.goalState;
    this.pauseState = snap.pauseState;
    this.stopRecord = null;
    this.activeFaultBanner = snap.activeFaultBanner;

    this.eventLog = {
      appliedEventIds: new Set(snap.recentEvents.map((e) => e.eventId)),
      entityRevisions: new Map(snap.recentEvents.map((e) => [e.entityId, e.entityRevision])),
      lastSequence: snap.lastEventSequence,
      events: [...snap.recentEvents],
      resyncRequired: false,
      detectedGapRange: null,
    };

    return this.getSnapshot();
  }

  public setViewMode(mode: ViewMode, sessionId?: ID): StationSnapshot {
    this.viewMode = mode;
    if (mode === "replay") {
      const fallbackId =
        sessionId ??
        this.activeSessionIdByMode.replay ??
        this.activeSessionIdByMode.simulation ??
        Array.from(this.sessions.keys())[0] ??
        null;
      this.activeSessionIdByMode.replay = fallbackId;
    } else if (mode === "simulation" && sessionId && this.sessions.has(sessionId)) {
      this.activeSessionIdByMode.simulation = sessionId;
    } else if (mode === "live" && sessionId && this.sessions.has(sessionId)) {
      const s = this.sessions.get(sessionId);
      if (s?.sourceMode === "live") {
        this.activeSessionIdByMode.live = sessionId;
      }
    }
    return this.getSnapshot();
  }

  public selectSession(sessionId: ID): StationSnapshot {
    const sess = this.sessions.get(sessionId);
    if (!sess) return this.getSnapshot();
    if (this.viewMode === "replay") {
      this.activeSessionIdByMode.replay = sessionId;
    } else if (sess.sourceMode === "simulation") {
      this.viewMode = "simulation";
      this.activeSessionIdByMode.simulation = sessionId;
    } else {
      this.viewMode = "live";
      this.activeSessionIdByMode.live = sessionId;
    }
    return this.getSnapshot();
  }

  private assertWritable(actionName: string): void {
    if (this.viewMode === "replay") {
      throw new Error(
        `Replay mode is strictly read-only. Cannot execute '${actionName}' during replay.`
      );
    }
  }

  private emitEvent(
    type: StationEventEnvelope["type"],
    summary: string,
    statusTone: StationEventEnvelope["statusTone"],
    entityId: ID,
    entityRevision: number,
    cycleId: ID | null,
    attemptId: ID | null,
    payload: Record<string, unknown> = {}
  ): StationEventEnvelope {
    const now = new Date().toISOString();
    const activeSession = this.getActiveSession();
    const seq = this.eventLog.lastSequence + 1;
    const envelope: StationEventEnvelope = {
      schemaVersion: 1,
      eventId: `evt-${seq}-${Date.now()}`,
      sequence: seq,
      type,
      occurredAt: now,
      receivedAt: now,
      sourceMode: activeSession?.sourceMode ?? "simulation",
      sessionId: activeSession?.id ?? "no-session",
      cycleId,
      attemptId,
      entityId,
      entityRevision,
      summary,
      statusTone,
      payload,
    };
    const res = applyOrderedEvent(this.eventLog, envelope);
    this.eventLog = res.state;
    return envelope;
  }

  public applyExternalEvent(envelope: StationEventEnvelope): {
    applied: boolean;
    reason: "applied" | "duplicate_event" | "stale_revision" | "sequence_gap";
    snapshot: StationSnapshot;
  } {
    const res = applyOrderedEvent(this.eventLog, envelope);
    this.eventLog = res.state;
    return {
      applied: res.applied,
      reason: res.reason,
      snapshot: this.getSnapshot(),
    };
  }

  private getActiveSession(): Session | null {
    if (this.viewMode === "live") {
      if (!this.liveStationConnected) return null;
      const id = this.activeSessionIdByMode.live;
      return id ? this.sessions.get(id) ?? null : null;
    }
    if (this.viewMode === "replay") {
      const id =
        this.activeSessionIdByMode.replay ?? this.activeSessionIdByMode.simulation;
      return id ? this.sessions.get(id) ?? null : null;
    }
    const id = this.activeSessionIdByMode.simulation;
    return id ? this.sessions.get(id) ?? null : null;
  }

  /**
   * Start session is bookkeeping only. It creates a new session and resets displayed session totals
   * without erasing historical sessions or triggering robot movement.
   */
  public startSession(name: string, sourceMode: SourceMode = "simulation"): StationSnapshot {
    this.assertWritable("start_session");
    if (sourceMode === "live" && !this.liveStationConnected) {
      throw new Error("Cannot start a live hardware session while the station is disconnected.");
    }
    const now = new Date().toISOString();
    const id = `${sourceMode === "simulation" ? "SIM" : "LIVE"}-${Date.now().toString().slice(-5)}`;
    const newSession: Session = {
      id,
      name: name.trim() || `Session ${this.sessions.size + 1}`,
      sourceMode,
      startedAt: now,
      endedAt: null,
      configId: "cfg-duplo-01",
      robotId: sourceMode === "simulation" ? "SO-101-SIM" : null,
      displayTimezone: "Europe/Helsinki (UTC+02:00)",
      modelRuns: DEFAULT_MODEL_RUNS,
    };
    this.sessions.set(id, newSession);
    if (sourceMode === "simulation") {
      this.viewMode = "simulation";
      this.activeSessionIdByMode.simulation = id;
    } else {
      this.viewMode = "live";
      this.activeSessionIdByMode.live = id;
    }
    this.stateVersion += 1;
    this.stopRecord = null;
    this.pauseState = {
      requested: false,
      acknowledged: false,
      requestedAt: null,
      acknowledgedAt: null,
    };
    return this.getSnapshot();
  }

  /**
   * Ending a session ends session bookkeeping while preserving any open cycle's real status.
   * Never converts an open cycle to 'correct' or silently aborts it.
   */
  public endSession(sessionId: ID): StationSnapshot {
    this.assertWritable("end_session");
    const sess = this.sessions.get(sessionId);
    if (!sess) throw new Error(`Session ${sessionId} not found`);
    const now = new Date().toISOString();
    this.sessions.set(sessionId, {
      ...sess,
      endedAt: now,
    });
    this.stateVersion += 1;
    return this.getSnapshot();
  }

  /**
   * Urgent idempotent software stop.
   * Does not depend on optimistic stateVersion checks. Immediately records stop request.
   */
  public requestSoftwareStop(): SoftwareStopRecord {
    this.assertWritable("software_stop");
    const activeSession = this.getActiveSession();
    if (!activeSession) {
      throw new Error("No active session or connected controller to receive software stop.");
    }
    if (this.stopRecord && this.stopRecord.sessionId === activeSession.id) {
      // Idempotent: return existing stop request record with stable timestamp & ID
      return this.stopRecord;
    }
    const activeCycle = this.getActiveCycleForSession(activeSession.id);
    const now = new Date().toISOString();
    const record: SoftwareStopRecord = {
      requestId: `${activeSession.sourceMode === "simulation" ? "demo" : "live"}-stop-${Date.now()}`,
      sessionId: activeSession.id,
      cycleId: activeCycle?.id ?? null,
      mode: activeSession.sourceMode,
      command: "software_stop",
      status: "requested",
      requestSentText:
        activeSession.sourceMode === "simulation" ? "Recorded in demo" : "Sent to station API",
      controllerAcknowledged: false,
      controllerStateText: "Awaiting response",
      physicalHaltVerified: false,
      physicalHaltText: "Unverified",
      requestedAt: now,
      acknowledgedAt: null,
    };
    this.stopRecord = record;
    this.emitEvent(
      "stop.requested",
      "Software stop requested",
      "bad",
      record.requestId,
      1,
      activeCycle?.id ?? null,
      null,
      { requestId: record.requestId }
    );
    return record;
  }

  public simulateControllerStopAck(): SoftwareStopRecord | null {
    this.assertWritable("acknowledge_stop");
    if (!this.stopRecord) return null;
    const now = new Date().toISOString();
    this.stopRecord = {
      ...this.stopRecord,
      status: "acknowledged",
      controllerAcknowledged: true,
      controllerStateText: "Acknowledged by controller (trajectory halted in software)",
      // Physical stop remains Unverified unless independent physical sensor/camera verification occurs
      physicalHaltVerified: false,
      physicalHaltText: "Unverified",
      acknowledgedAt: now,
    };
    this.emitEvent(
      "stop.acknowledged",
      "Controller acknowledged software stop",
      "warn",
      this.stopRecord.requestId,
      2,
      this.stopRecord.cycleId,
      null,
      { controllerAcknowledged: true, physicalHaltVerified: false }
    );
    return this.stopRecord;
  }

  public requestPauseAfterCycle(): StationSnapshot {
    this.assertWritable("pause_after_cycle");
    const activeSession = this.getActiveSession();
    if (!activeSession) throw new Error("No active session");
    const now = new Date().toISOString();
    this.pauseState = {
      requested: true,
      acknowledged: true,
      requestedAt: now,
      acknowledgedAt: now,
    };
    this.stateVersion += 1;
    this.emitEvent(
      "pause.requested",
      "Pause after cycle requested & acknowledged",
      "warn",
      activeSession.id,
      this.stateVersion,
      null,
      null,
      { pauseAfterCycle: true }
    );
    return this.getSnapshot();
  }

  public resumeOperations(): StationSnapshot {
    this.assertWritable("resume");
    const activeSession = this.getActiveSession();
    if (!activeSession) throw new Error("No active session");
    this.pauseState = {
      requested: false,
      acknowledged: false,
      requestedAt: null,
      acknowledgedAt: null,
    };
    this.stopRecord = null;
    this.stateVersion += 1;
    return this.getSnapshot();
  }

  /**
   * Starts a new cycle intentionally in the active simulation session.
   */
  public startCycle(): StationSnapshot {
    this.assertWritable("start_cycle");
    const activeSession = this.getActiveSession();
    if (!activeSession) throw new Error("Start or select a session first.");
    if (activeSession.endedAt) {
      throw new Error("Cannot start a cycle in an ended session.");
    }
    if (this.stopRecord) {
      throw new Error("Software stop is active. Resume operations intentionally before starting a cycle.");
    }
    if (this.pauseState.requested) {
      throw new Error("Station is paused after cycle. Resume before starting a new cycle.");
    }

    // If a queued goal exists, commit it at this cycle start boundary!
    const now = new Date().toISOString();
    if (this.goalState.queuedGoal) {
      const committed = commitQueuedGoalAtBoundary(this.goalState, now);
      this.goalState = committed.goalState;
      this.emitEvent(
        "goal.activated",
        `Goal v${this.goalState.goalVersion} active (${this.goalState.activeGoalLabel})`,
        "good",
        activeSession.id,
        this.goalState.goalVersion,
        null,
        null,
        { goalVersion: this.goalState.goalVersion }
      );
    }

    const sessionCycles = Array.from(this.cycles.values()).filter(
      (c) => c.sessionId === activeSession.id
    );
    // Mark any previously in_progress cycle as finished before starting a new one if needed
    for (const c of sessionCycles) {
      if (c.outcome === "in_progress") {
        throw new Error(`Cycle ${c.id} is already in progress. Complete or advance it first.`);
      }
    }

    const nextIdx = sessionCycles.length + 1;
    const padNum = String(nextIdx).padStart(3, "0");
    const cycleId = `C-${padNum}`;
    const objectId = `D-${padNum}`;
    const frameId = `F-${padNum}-01`;
    const insId = `INS-${padNum}-01`;
    const attId = `A-${padNum}-01`;
    const execId = `EX-${padNum}-01`;
    const nemId = `NEM-${padNum}`;
    const decId = `DEC-${padNum}`;

    const isDefective = nextIdx % 2 === 0;
    const score = isDefective ? 0.79 : 0.23;
    const pred: Quality = isDefective ? "defective" : "good";
    const dest: Destination = isDefective ? "defective_bin" : "good_bin";

    this.frames.set(frameId, {
      id: frameId,
      sessionId: activeSession.id,
      cycleId,
      objectId,
      cameraId: "overhead",
      capturedAt: now,
      receivedAt: now,
      width: 1280,
      height: 720,
      imageUrl: SIMULATION_SCENE_URL,
      sha256: `sha256-sim-${frameId.toLowerCase()}`,
      stale: false,
      fps: null,
      overlayBox: { x: 49, y: 57, w: 10, h: 19 },
    });

    this.inspections.set(insId, {
      id: insId,
      cycleId,
      objectId,
      frameIds: [frameId],
      modelRunId: "mr-anomalib-01",
      score,
      threshold: 0.65,
      scoreRange: [0, 1],
      classification: pred,
      mapEvidenceId: `MAP-${padNum}-01`,
      additionalInspectionOfId: null,
      isDecisionInspection: true,
      requestedAt: now,
      completedAt: now,
    });

    this.skillExecutions.set(execId, {
      id: execId,
      cycleId,
      attemptId: attId,
      taskId: "present_for_inspection",
      policyId: "studio-vla-duplo-sort (pending)",
      policyVersion: "0.3.0-sim",
      commandSentAt: now,
      acknowledgedAt: now,
      finishedAt: null,
      motionStartedAt: now,
      motionEndedAt: null,
      controllerStatus: "running",
      physicalOutcome: "pending",
    });

    this.attempts.set(attId, {
      id: attId,
      cycleId,
      ordinal: 1,
      executionIds: [execId],
      startedAt: now,
      endedAt: null,
      outcome: "in_progress",
      retryOfAttemptId: null,
      retryReason: null,
      errorCode: null,
      confirmationId: null,
    });

    this.nemotronObservations.set(nemId, {
      id: nemId,
      cycleId,
      frameIds: [frameId],
      modelId: "nvidia/nemotron-3.5-super-vl-120b-a12b",
      requestedAt: now,
      completedAt: now,
      status: "completed",
      observations: [
        isDefective
          ? "Object visible. Surface anomaly detected along lateral brick face."
          : "Object visible. Uniform top studs and clean lateral surfaces.",
      ],
      hypotheses: [
        isDefective
          ? "Hypothesis: Structural surface crack on front wall."
          : "Hypothesis: Nominal Duplo 2×2 geometry.",
      ],
      uncertainty: null,
      rawArtifact: JSON.stringify({ frameId, simulated: true }),
      parseError: null,
    });

    const chosenTask: PermittedTaskId =
      isDefective && this.goalState.activeGoal === "extra_view_next_reject"
        ? "reinspect_other_view"
        : isDefective
        ? "place_defective"
        : "place_good";

    this.decisions.set(decId, {
      id: decId,
      sessionId: activeSession.id,
      cycleId,
      attemptId: attId,
      kind: "task_selection",
      modelId: "gemini-decision-1",
      stateVersion: this.stateVersion + 1,
      goalVersion: this.goalState.goalVersion,
      frameIds: [frameId],
      offeredChoices: [
        "pick",
        "present_for_inspection",
        "reinspect_other_view",
        "place_good",
        "place_defective",
        "hold",
      ],
      selectedChoice: chosenTask,
      probabilities: {
        [chosenTask]: 0.91,
        hold: 0.06,
        reinspect_other_view: chosenTask === "reinspect_other_view" ? 0.91 : 0.03,
      },
      requestedAt: now,
      completedAt: now,
      deadlineAt: new Date(Date.now() + 5000).toISOString(),
      validatorAccepted: true,
      validatorReason: `Accepted '${chosenTask}' at state v${this.stateVersion + 1} / goal v${this.goalState.goalVersion}`,
    });

    const newCycle: Cycle = {
      id: cycleId,
      sessionId: activeSession.id,
      objectId,
      revision: 1,
      startedAt: now,
      endedAt: null,
      outcome: "in_progress",
      activePhase: "choose_task",
      faultedPhase: null,
      phaseElapsedSec: 0.4,
      attemptIds: [attId],
      inspectionIds: [insId],
      decisionIds: [decId],
      nemotronIds: [nemId],
      plannedDestination: dest,
      commandedDestination: null,
      observedDestination: null,
      referenceLabelId: null,
      confirmationId: null,
      fullCycleDurationSec: null,
      timingBreakdown: {
        anomalibMs: 138,
        nemotronMs: 340,
        geminiMs: 245,
        motionMs: null,
        verificationMs: null,
        cloudWaitIncluded: true,
      },
    };

    this.cycles.set(cycleId, newCycle);
    this.stateVersion += 1;

    this.emitEvent(
      "cycle.started",
      `${cycleId} started (${objectId})`,
      "neutral",
      cycleId,
      1,
      cycleId,
      attId,
      { objectId }
    );

    return this.getSnapshot();
  }

  /**
   * Advances or completes the active cycle in simulation mode:
   * - 'complete_success': places brick into planned destination and records independent confirmation
   * - 'extra_inspection': adds a wrist-camera inspection linked to the prior inspection without adding an Attempt
   * - 'failed_grasp_retry': marks current attempt failed, creates retry Attempt in the same cycle, and recovers
   */
  public advanceActiveCycle(
    mode: "complete_success" | "extra_inspection" | "failed_grasp_retry"
  ): StationSnapshot {
    this.assertWritable("advance_cycle");
    const activeSession = this.getActiveSession();
    if (!activeSession) throw new Error("No active session");
    const cycle = this.getActiveCycleForSession(activeSession.id);
    if (!cycle) throw new Error("No cycle available in active session");

    const now = new Date().toISOString();
    const numSuffix = cycle.id.replace("C-", "");

    if (mode === "extra_inspection") {
      const prevInsId = cycle.inspectionIds[cycle.inspectionIds.length - 1] ?? null;
      const prevIns = prevInsId ? this.inspections.get(prevInsId) : null;
      const nextIdx = cycle.inspectionIds.length + 1;
      const frameId = `F-${numSuffix}-0${nextIdx}`;
      const insId = `INS-${numSuffix}-0${nextIdx}`;

      this.frames.set(frameId, {
        id: frameId,
        sessionId: activeSession.id,
        cycleId: cycle.id,
        objectId: cycle.objectId,
        cameraId: "wrist",
        capturedAt: now,
        receivedAt: now,
        width: 1280,
        height: 720,
        imageUrl: SIMULATION_SCENE_URL,
        sha256: `sha256-sim-${frameId.toLowerCase()}`,
        stale: false,
        fps: null,
        overlayBox: { x: 49, y: 57, w: 10, h: 19 },
      });

      // Mark previous inspection non-decision so only 1 decision inspection counts per cycle
      if (prevIns) {
        this.inspections.set(prevIns.id, { ...prevIns, isDecisionInspection: false });
      }

      const score = prevIns ? prevIns.score : 0.78;
      const classification = prevIns ? prevIns.classification : "defective";

      this.inspections.set(insId, {
        id: insId,
        cycleId: cycle.id,
        objectId: cycle.objectId,
        frameIds: [frameId],
        modelRunId: "mr-anomalib-01",
        score,
        threshold: 0.65,
        scoreRange: [0, 1],
        classification,
        mapEvidenceId: `MAP-${numSuffix}-0${nextIdx}`,
        additionalInspectionOfId: prevInsId,
        isDecisionInspection: true,
        requestedAt: now,
        completedAt: now,
      });

      const updatedCycle: Cycle = {
        ...cycle,
        revision: cycle.revision + 1,
        activePhase: "inspect",
        inspectionIds: [...cycle.inspectionIds, insId],
      };
      this.cycles.set(cycle.id, updatedCycle);
      this.stateVersion += 1;

      this.emitEvent(
        "inspection.recorded",
        `Extra inspection ${insId} recorded (no new attempt)`,
        "good",
        insId,
        1,
        cycle.id,
        cycle.attemptIds[cycle.attemptIds.length - 1] ?? null,
        { additionalInspectionOfId: prevInsId }
      );
      return this.getSnapshot();
    }

    if (mode === "failed_grasp_retry") {
      const currentAttId = cycle.attemptIds[cycle.attemptIds.length - 1];
      const currentAtt = currentAttId ? this.attempts.get(currentAttId) : null;
      if (currentAtt) {
        this.attempts.set(currentAtt.id, {
          ...currentAtt,
          endedAt: now,
          outcome: "failed",
          errorCode: "GRASP_SLIP_DETECTED",
        });
      }

      const nextOrd = cycle.attemptIds.length + 1;
      const retryAttId = `A-${numSuffix}-0${nextOrd}`;
      const retryExecId = `EX-${numSuffix}-0${nextOrd}`;
      const confId = `CONF-${retryAttId}`;
      const refId = cycle.referenceLabelId ?? `REF-${numSuffix}`;
      const dest: Destination = cycle.plannedDestination ?? "defective_bin";
      const refQual: Quality = dest === "defective_bin" ? "defective" : "good";

      this.confirmations.set(confId, {
        id: confId,
        source: "camera",
        evidenceIds: [cycle.inspectionIds[cycle.inspectionIds.length - 1] ?? `F-${numSuffix}-01`],
        authorId: null,
        confirmedAt: now,
        notes: `Verified placement in ${dest} on retry attempt ${nextOrd}.`,
      });

      if (!cycle.referenceLabelId) {
        this.referenceLabels.set(refId, {
          id: refId,
          objectId: cycle.objectId,
          cycleId: cycle.id,
          quality: refQual,
          authorId: "demo-operator",
          method: "Post-cycle fixture verification",
          reason: "Verified reference quality for recovery cycle",
          evidenceIds: [],
          createdAt: now,
        });
      }

      this.skillExecutions.set(retryExecId, {
        id: retryExecId,
        cycleId: cycle.id,
        attemptId: retryAttId,
        taskId: dest === "defective_bin" ? "place_defective" : "place_good",
        policyId: "studio-vla-duplo-sort (pending)",
        policyVersion: "0.3.0-sim",
        commandSentAt: now,
        acknowledgedAt: now,
        finishedAt: now,
        motionStartedAt: now,
        motionEndedAt: now,
        controllerStatus: "finished",
        physicalOutcome: "verified",
      });

      this.attempts.set(retryAttId, {
        id: retryAttId,
        cycleId: cycle.id,
        ordinal: nextOrd,
        executionIds: [retryExecId],
        startedAt: now,
        endedAt: now,
        outcome: "successful",
        retryOfAttemptId: currentAttId ?? null,
        retryReason: "Failed grasp: object remained in pickup area",
        errorCode: null,
        confirmationId: confId,
      });

      const updatedCycle: Cycle = {
        ...cycle,
        revision: cycle.revision + 1,
        endedAt: now,
        outcome: "correct",
        activePhase: "verify_outcome",
        attemptIds: [...cycle.attemptIds, retryAttId],
        commandedDestination: dest,
        observedDestination: dest,
        referenceLabelId: refId,
        confirmationId: confId,
        fullCycleDurationSec: 16.8,
      };
      this.cycles.set(cycle.id, updatedCycle);
      this.stateVersion += 1;

      this.emitEvent(
        "outcome.confirmed",
        `${cycle.id} recovered on attempt ${nextOrd}`,
        "good",
        cycle.id,
        updatedCycle.revision,
        cycle.id,
        retryAttId,
        { attempts: nextOrd, outcome: "correct" }
      );
      return this.getSnapshot();
    }

    // Default: complete_success
    const currentAttId = cycle.attemptIds[cycle.attemptIds.length - 1];
    const currentAtt = currentAttId ? this.attempts.get(currentAttId) : null;
    const confId = `CONF-${currentAttId ?? cycle.id}`;
    const dest: Destination = cycle.plannedDestination ?? "defective_bin";
    const refId = cycle.referenceLabelId ?? `REF-${numSuffix}`;
    const refQual: Quality = dest === "defective_bin" ? "defective" : "good";

    this.confirmations.set(confId, {
      id: confId,
      source: "camera",
      evidenceIds: [cycle.inspectionIds[cycle.inspectionIds.length - 1] ?? `F-${numSuffix}-01`],
      authorId: null,
      confirmedAt: now,
      notes: `Overhead camera confirmed placement in ${dest}.`,
    });

    if (!cycle.referenceLabelId) {
      this.referenceLabels.set(refId, {
        id: refId,
        objectId: cycle.objectId,
        cycleId: cycle.id,
        quality: refQual,
        authorId: "demo-operator",
        method: "Independent fixture verification",
        reason: "Reference quality confirmed",
        evidenceIds: [],
        createdAt: now,
      });
    }

    if (currentAtt) {
      this.attempts.set(currentAtt.id, {
        ...currentAtt,
        endedAt: now,
        outcome: "successful",
        confirmationId: confId,
      });
      for (const exId of currentAtt.executionIds) {
        const ex = this.skillExecutions.get(exId);
        if (ex) {
          this.skillExecutions.set(exId, {
            ...ex,
            taskId: dest === "defective_bin" ? "place_defective" : "place_good",
            finishedAt: now,
            motionEndedAt: now,
            controllerStatus: "finished",
            physicalOutcome: "verified",
          });
        }
      }
    }

    // If a queued goal was waiting for cycle end boundary, commit it now!
    if (this.goalState.queuedGoal) {
      const committed = commitQueuedGoalAtBoundary(this.goalState, now);
      this.goalState = committed.goalState;
    }

    const updatedCycle: Cycle = {
      ...cycle,
      revision: cycle.revision + 1,
      endedAt: now,
      outcome: "correct",
      activePhase: "verify_outcome",
      commandedDestination: dest,
      observedDestination: dest,
      referenceLabelId: refId,
      confirmationId: confId,
      fullCycleDurationSec: cycle.fullCycleDurationSec ?? 11.4,
      timingBreakdown: {
        ...cycle.timingBreakdown,
        motionMs: 9800,
        verificationMs: 160,
      },
    };
    this.cycles.set(cycle.id, updatedCycle);
    this.stateVersion += 1;

    this.emitEvent(
      "outcome.confirmed",
      `${cycle.id} confirmed correct`,
      "good",
      cycle.id,
      updatedCycle.revision,
      cycle.id,
      currentAttId ?? null,
      { outcome: "correct" }
    );

    return this.getSnapshot();
  }

  /**
   * Submits or updates an independent ReferenceLabel or audited Correction on a cycle.
   * Requires authorId and reason; preserves previousValue, newValue, and timestamp.
   * Recomputes cycle outcome and session metrics immediately.
   */
  public submitReferenceCorrection(params: {
    cycleId: ID;
    referenceQuality: Quality;
    observedDestination?: Destination | "other";
    authorId: string;
    reason: string;
  }): StationSnapshot {
    this.assertWritable("submit_correction");
    const authorId = params.authorId.trim();
    const reason = params.reason.trim();
    if (!authorId || !reason) {
      throw new Error("Reference labels and corrections require both author and reason.");
    }

    const cycle = this.cycles.get(params.cycleId);
    if (!cycle) throw new Error(`Cycle ${params.cycleId} not found`);

    const now = new Date().toISOString();
    const existingRef = cycle.referenceLabelId
      ? this.referenceLabels.get(cycle.referenceLabelId) ?? null
      : null;

    const previousQuality = existingRef ? existingRef.quality : "unset";
    const refId = existingRef?.id ?? `REF-${cycle.id.replace("C-", "")}`;

    const newRef: ReferenceLabel = {
      id: refId,
      objectId: cycle.objectId,
      cycleId: cycle.id,
      quality: params.referenceQuality,
      authorId,
      method: "Operator audited reference entry",
      reason,
      evidenceIds: cycle.inspectionIds,
      createdAt: now,
    };
    this.referenceLabels.set(refId, newRef);

    const corId = `COR-${cycle.id}-${Date.now().toString().slice(-4)}`;
    this.corrections.set(corId, {
      id: corId,
      sessionId: cycle.sessionId,
      entityType: "reference_label",
      entityId: refId,
      field: "quality",
      previousValue: previousQuality,
      newValue: params.referenceQuality,
      authorId,
      reason,
      createdAt: now,
    });

    // If observedDestination is also provided (e.g. late confirmation of C-008), record Confirmation
    let observedDest = params.observedDestination ?? cycle.observedDestination;
    let confId = cycle.confirmationId;
    const cycAttempts = cycle.attemptIds
      .map((id) => this.attempts.get(id))
      .filter((a): a is Attempt => Boolean(a));

    if (params.observedDestination && !confId) {
      confId = `CONF-LATE-${cycle.id}`;
      this.confirmations.set(confId, {
        id: confId,
        source: "operator",
        evidenceIds: cycle.inspectionIds,
        authorId,
        confirmedAt: now,
        notes: `Late confirmation by ${authorId}: ${reason}`,
      });
      // Update last unverified attempt if present
      const lastAtt = cycAttempts[cycAttempts.length - 1];
      if (lastAtt && lastAtt.outcome === "unverified") {
        const updatedAtt: Attempt = {
          ...lastAtt,
          outcome: params.observedDestination === "other" ? "failed" : "successful",
          confirmationId: confId,
        };
        this.attempts.set(lastAtt.id, updatedAtt);
        cycAttempts[cycAttempts.length - 1] = updatedAtt;
      }
    }

    const cycInspections = cycle.inspectionIds
      .map((id) => this.inspections.get(id))
      .filter((i): i is Inspection => Boolean(i));
    const decisionIns =
      cycInspections.find((i) => i.isDecisionInspection) ??
      cycInspections[cycInspections.length - 1] ??
      null;

    const newOutcome = evaluateCycleOutcome({
      isInProgress: cycle.outcome === "in_progress",
      isAborted: cycle.outcome === "aborted",
      hasConfirmation: Boolean(confId),
      attempts: cycAttempts,
      decisionClassification: decisionIns?.classification ?? null,
      referenceQuality: params.referenceQuality,
      commandedDestination: cycle.commandedDestination,
      observedDestination: observedDest,
    });

    const updatedCycle: Cycle = {
      ...cycle,
      revision: cycle.revision + 1,
      referenceLabelId: refId,
      observedDestination: observedDest,
      confirmationId: confId,
      outcome: newOutcome,
    };
    this.cycles.set(cycle.id, updatedCycle);
    this.stateVersion += 1;

    this.emitEvent(
      "correction.recorded",
      `Audited correction on ${cycle.id} (${previousQuality} → ${params.referenceQuality})`,
      "neutral",
      cycle.id,
      updatedCycle.revision,
      cycle.id,
      null,
      { authorId, reason, newOutcome }
    );

    return this.getSnapshot();
  }

  /**
   * Voice utterance workflow: start, partial, committed segment, finalize once (deduplicated), and timestamp enrichment.
   */
  public recordVoiceUtterance(params: {
    utteranceId: ID;
    source: "scribe_v3_live" | "typed";
    text: string;
    selectedGoal: SupportedGoalId;
    goalProbabilities: Record<string, number>;
    queueForNextBoundary: boolean;
  }): {
    utterance: VoiceUtterance;
    deduplicated: boolean;
    snapshot: StationSnapshot;
  } {
    this.assertWritable("voice_utterance");
    const activeSession = this.getActiveSession();
    const sessionId = activeSession?.id ?? "DEMO-01";
    const now = new Date().toISOString();

    let baseUtt = this.utterances.get(params.utteranceId);
    if (!baseUtt) {
      baseUtt = {
        id: params.utteranceId,
        sessionId,
        source: params.source,
        language: "en",
        partialTranscript: "",
        committedSegments: [params.text.trim()],
        finalizedText: null,
        timestampsEnriched: false,
        enrichmentTimestamps: [],
        selectedGoal: null,
        goalProbabilities: {},
        effectiveBoundary: "Pending",
        state: "finalizing",
        createdAt: now,
        finalizedAt: null,
        transcriptionMs: params.source === "scribe_v3_live" ? 295 : 0,
        goalDecisionMs: 215,
      };
    }

    const res = finalizeUtteranceOnce({
      existingUtterances: this.utterances,
      utterance: baseUtt,
      finalizedAt: now,
      selectedGoal: params.selectedGoal,
      goalProbabilities: params.goalProbabilities,
      queueForNextBoundary: params.queueForNextBoundary,
      currentGoalState: this.goalState,
    });

    this.goalState = res.goalState;
    if (res.commandIssued && !res.deduplicated) {
      this.stateVersion += 1;
      this.emitEvent(
        params.queueForNextBoundary ? "goal.queued" : "goal.activated",
        params.queueForNextBoundary
          ? `Goal queued: ${params.selectedGoal}`
          : `Goal active: ${params.selectedGoal}`,
        params.queueForNextBoundary ? "warn" : "good",
        res.utterance.id,
        1,
        null,
        null,
        { selectedGoal: params.selectedGoal }
      );
    }

    return {
      utterance: res.utterance,
      deduplicated: res.deduplicated,
      snapshot: this.getSnapshot(),
    };
  }

  public enrichVoiceUtterance(
    utteranceId: ID,
    timestamps: { word: string; startMs: number; endMs: number }[]
  ): { utterance: VoiceUtterance | null; commandIssued: boolean; snapshot: StationSnapshot } {
    const res = enrichUtteranceTimestamps(this.utterances, utteranceId, timestamps);
    return {
      utterance: res.utterance,
      commandIssued: res.commandIssued,
      snapshot: this.getSnapshot(),
    };
  }

  public commitQueuedVoiceGoalNow(): StationSnapshot {
    this.assertWritable("commit_queued_goal");
    const now = new Date().toISOString();
    const res = commitQueuedGoalAtBoundary(this.goalState, now);
    this.goalState = res.goalState;
    if (res.committed) {
      this.stateVersion += 1;
      this.emitEvent(
        "goal.activated",
        `Queued goal committed (v${this.goalState.goalVersion})`,
        "good",
        this.goalState.activeGoal,
        this.goalState.goalVersion,
        null,
        null,
        { goalVersion: this.goalState.goalVersion }
      );
    }
    return this.getSnapshot();
  }

  private getActiveCycleForSession(sessionId: ID): Cycle | null {
    const sessCycles = Array.from(this.cycles.values()).filter(
      (c) => c.sessionId === sessionId
    );
    return (
      sessCycles.find((c) => c.outcome === "in_progress") ??
      sessCycles[sessCycles.length - 1] ??
      null
    );
  }

  public getSnapshot(): StationSnapshot {
    if (this.viewMode === "live" && !this.liveStationConnected) {
      const disconnected = buildDisconnectedLiveSnapshot();
      // Include available simulation sessions in sessions list so user can switch or replay
      return {
        ...disconnected,
        sessions: Array.from(this.sessions.values()),
      };
    }

    const activeSession = this.getActiveSession();
    const sessionCycles = activeSession
      ? Array.from(this.cycles.values()).filter((c) => c.sessionId === activeSession.id)
      : [];
    const cycleIdSet = new Set(sessionCycles.map((c) => c.id));

    const sessionAttempts = Array.from(this.attempts.values()).filter((a) =>
      cycleIdSet.has(a.cycleId)
    );
    const sessionInspections = Array.from(this.inspections.values()).filter((i) =>
      cycleIdSet.has(i.cycleId)
    );
    const sessionFrames = Array.from(this.frames.values()).filter((f) =>
      cycleIdSet.has(f.cycleId)
    );
    const sessionConfirmations = Array.from(this.confirmations.values());
    const sessionRefLabels = Array.from(this.referenceLabels.values()).filter((r) =>
      cycleIdSet.has(r.cycleId)
    );
    const sessionCorrections = activeSession
      ? Array.from(this.corrections.values()).filter((c) => c.sessionId === activeSession.id)
      : [];
    const sessionNemotron = Array.from(this.nemotronObservations.values()).filter((n) =>
      cycleIdSet.has(n.cycleId)
    );
    const sessionDecisions = Array.from(this.decisions.values()).filter((d) =>
      cycleIdSet.has(d.cycleId)
    );
    const sessionExecutions = Array.from(this.skillExecutions.values()).filter((e) =>
      cycleIdSet.has(e.cycleId)
    );
    const sessionUtterances = activeSession
      ? Array.from(this.utterances.values()).filter((u) => u.sessionId === activeSession.id)
      : [];

    const activeCycle = activeSession
      ? this.getActiveCycleForSession(activeSession.id)
      : null;

    const metrics = computeSessionMetrics({
      session: activeSession,
      stationConnected: this.viewMode !== "live" || this.liveStationConnected,
      cycles: sessionCycles,
      attempts: sessionAttempts,
      inspections: sessionInspections,
      referenceLabels: sessionRefLabels,
    });

    return {
      viewMode: this.viewMode,
      stationConnected: this.viewMode !== "live" || this.liveStationConnected,
      activeSession,
      sessions: Array.from(this.sessions.values()),
      stateVersion: this.stateVersion,
      goalState: this.goalState,
      pauseState: this.pauseState,
      stopRecord: this.stopRecord,
      activeCycle,
      cycles: sessionCycles,
      attempts: sessionAttempts,
      inspections: sessionInspections,
      frames: sessionFrames,
      confirmations: sessionConfirmations,
      referenceLabels: sessionRefLabels,
      corrections: sessionCorrections,
      nemotronObservations: sessionNemotron,
      decisions: sessionDecisions,
      skillExecutions: sessionExecutions,
      utterances: sessionUtterances,
      recentEvents: this.eventLog.events.slice(0, 12),
      lastEventSequence: this.eventLog.lastSequence,
      components: DEFAULT_COMPONENTS,
      joints: DEFAULT_JOINTS,
      hardwareSummary: {
        cpuLoad: { value: null, unit: "%", measuredAt: null, state: "unavailable" },
        memory: { value: null, unit: "GB", measuredAt: null, state: "unavailable" },
        controlRate: { value: null, unit: "Hz", measuredAt: null, state: "unavailable" },
      },
      metrics,
      activeFaultBanner: this.activeFaultBanner,
    };
  }

  public exportSessionCsv(sessionId?: ID): string {
    const snap = this.getSnapshot();
    const targetSession =
      (sessionId ? this.sessions.get(sessionId) : snap.activeSession) ?? snap.activeSession;
    if (!targetSession) {
      return "schema_version,source_mode,session_id,cycle_id,object_id,revision,outcome,attempt_count,extra_inspections,reference_quality,predicted_quality,anomaly_score,threshold,commanded_destination,observed_destination,full_cycle_s\n";
    }
    const cycs = Array.from(this.cycles.values()).filter(
      (c) => c.sessionId === targetSession.id
    );
    const header =
      "schema_version,source_mode,session_id,cycle_id,object_id,revision,outcome,attempt_count,extra_inspections,reference_quality,predicted_quality,anomaly_score,threshold,commanded_destination,observed_destination,full_cycle_s";
    const rows = cycs.map((c) => {
      const cycInspections = c.inspectionIds
        .map((id) => this.inspections.get(id))
        .filter((i): i is Inspection => Boolean(i));
      const decIns =
        cycInspections.find((i) => i.isDecisionInspection) ??
        cycInspections[cycInspections.length - 1] ??
        null;
      const extraCount = cycInspections.filter(
        (i) => i.additionalInspectionOfId !== null
      ).length;
      const ref = c.referenceLabelId
        ? this.referenceLabels.get(c.referenceLabelId) ?? null
        : null;
      return [
        "1",
        targetSession.sourceMode,
        targetSession.id,
        c.id,
        c.objectId,
        c.revision,
        c.outcome,
        c.attemptIds.length,
        extraCount,
        ref?.quality ?? "",
        decIns?.classification ?? "",
        decIns?.score ?? "",
        decIns?.threshold ?? "",
        c.commandedDestination ?? "",
        c.observedDestination ?? "",
        c.fullCycleDurationSec ?? "",
      ].join(",");
    });
    return [header, ...rows].join("\n");
  }

  public exportSessionJson(sessionId?: ID): string {
    const snap = this.getSnapshot();
    const targetSession =
      (sessionId ? this.sessions.get(sessionId) : snap.activeSession) ?? snap.activeSession;
    const payload = {
      schemaVersion: 1,
      exportedAt: new Date().toISOString(),
      sourceMode: targetSession?.sourceMode ?? "simulation",
      fixture: targetSession?.sourceMode === "simulation",
      session: targetSession,
      metrics: snap.metrics,
      cycles: snap.cycles,
      attempts: snap.attempts,
      inspections: snap.inspections,
      frames: snap.frames,
      nemotronObservations: snap.nemotronObservations,
      decisions: snap.decisions,
      skillExecutions: snap.skillExecutions,
      confirmations: snap.confirmations,
      referenceLabels: snap.referenceLabels,
      corrections: snap.corrections,
      utterances: snap.utterances,
      recentEvents: snap.recentEvents,
    };
    return JSON.stringify(payload, null, 2);
  }
}
