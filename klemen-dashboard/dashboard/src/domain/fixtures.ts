import type {
  Attempt,
  ComponentStatusRecord,
  Confirmation,
  Correction,
  Cycle,
  DecisionRecord,
  Frame,
  GoalState,
  Inspection,
  JointTelemetry,
  ModelRunMetadata,
  NemotronObservation,
  Quality,
  ReferenceLabel,
  Session,
  SimulationPresetId,
  SkillExecution,
  StationEventEnvelope,
  StationSnapshot,
  VoiceUtterance,
} from "./prototypeTypes.ts";
import { computeSessionMetrics } from "./stationLogic.ts";

export const SIMULATION_SCENE_URL = "/assets/aistudio/inspection-scene_9217b058.svg";

export const DEFAULT_MODEL_RUNS: ModelRunMetadata[] = [
  {
    id: "mr-anomalib-01",
    provider: "Intel OpenVINO / Anomalib",
    modelId: "anomalib-patchcore-duplo-01",
    version: "2.7.0-synth-fit",
    device: "Target CPU/GPU/NPU pending",
    precision: "FP16 (export verified, target exec pending)",
    endpointVerified: false,
    returnedIdentity: null,
  },
  {
    id: "mr-nemotron-01",
    provider: "NVIDIA NIM",
    modelId: "nvidia/nemotron-3.5-super-vl-120b-a12b",
    version: "3.5-super-vl-120b-a12b",
    device: "Cloud API",
    precision: "BF16",
    endpointVerified: false,
    returnedIdentity: null,
  },
  {
    id: "mr-gemini-01",
    provider: "Google Decisions API",
    modelId: "gemini-decision-1",
    version: "v1beta/decisions",
    device: "Cloud API",
    precision: null,
    endpointVerified: false,
    returnedIdentity: null,
  },
  {
    id: "mr-scribe-01",
    provider: "ElevenLabs Realtime",
    modelId: "scribe_v3_live",
    version: "v3_live",
    device: "Cloud WebSocket",
    precision: null,
    endpointVerified: false,
    returnedIdentity: null,
  },
  {
    id: "mr-policy-01",
    provider: "Physical AI Studio",
    modelId: "studio-vla-duplo-sort (pending)",
    version: "0.3.0",
    device: "Intel Core Ultra Series 3 (planned)",
    precision: null,
    endpointVerified: false,
    returnedIdentity: null,
  },
];

export const DEFAULT_COMPONENTS: ComponentStatusRecord[] = [
  {
    id: "comp-so101",
    name: "SO-101 / local runtime",
    roleDescription: "Calibration · workspace · controller acknowledgment",
    deploymentLocation: "local_station",
    configuredIdentity: "SO-101 6-DOF Manipulator",
    capabilityStatus: "proposed",
    connectionState: "unverified",
    statusBadgeText: "Hardware unverified",
    calibrationOrNote: "Calibration and physical stop confirmation not yet verified on station",
    latestError: null,
  },
  {
    id: "comp-studio-vla",
    name: "Physical AI Studio / VLA",
    roleDescription: "Learned manipulation · exact policy ID pending",
    deploymentLocation: "local_station",
    configuredIdentity: "Studio 0.3.0 · Policy ID pending demonstration run",
    capabilityStatus: "proposed",
    connectionState: "unverified",
    statusBadgeText: "Policy pending",
    calibrationOrNote: "Software profile checked; trained skill conditioning interface unverified",
    latestError: null,
  },
  {
    id: "comp-anomalib",
    name: "Anomalib / OpenVINO",
    roleDescription: "Defect measurement · Intel device assignment pending",
    deploymentLocation: "local_station",
    configuredIdentity: "Anomalib 2.7.0 · OpenVINO IR export",
    capabilityStatus: "implemented",
    connectionState: "unverified",
    statusBadgeText: "Intel test pending",
    calibrationOrNote: "Synthetic 64×64 fit & export passed; Intel target execution unverified",
    latestError: "Mac synthetic OpenVINO smoke run reported internal error; awaiting Intel station test",
  },
  {
    id: "comp-nemotron",
    name: "NVIDIA Nemotron 3.5 Super VL",
    roleDescription: "Frame-linked visual observations",
    deploymentLocation: "cloud_api",
    configuredIdentity: "nvidia/nemotron-3.5-super-vl-120b-a12b",
    capabilityStatus: "implemented",
    connectionState: "unverified",
    statusBadgeText: "API unverified",
    calibrationOrNote: "Published model ID verified; account endpoint & image inference unverified",
    latestError: null,
  },
  {
    id: "comp-gemini",
    name: "Gemini Decision 1",
    roleDescription: "Selects from the currently permitted tasks",
    deploymentLocation: "cloud_api",
    configuredIdentity: "gemini-decision-1 (Decisions API)",
    capabilityStatus: "implemented",
    connectionState: "unverified",
    statusBadgeText: "API unverified",
    calibrationOrNote: "Two-step typed choice contract (goal selection → permitted task selection)",
    latestError: null,
  },
  {
    id: "comp-scribe",
    name: "ElevenLabs Scribe v3 Live",
    roleDescription: "Finalized operator utterances",
    deploymentLocation: "cloud_api",
    configuredIdentity: "scribe_v3_live",
    capabilityStatus: "implemented",
    connectionState: "unverified",
    statusBadgeText: "API unverified",
    calibrationOrNote: "Single-use token flow & utterance ID deduplication implemented",
    latestError: null,
  },
];

export const DEFAULT_JOINTS: JointTelemetry[] = [
  "Base",
  "Shoulder",
  "Elbow",
  "Wrist flex",
  "Wrist roll",
  "Gripper",
].map((name) => ({
  jointName: name,
  isPlaceholderName: true,
  measured: { value: null, unit: "deg", measuredAt: null, state: "unavailable" },
  commanded: { value: null, unit: "deg", measuredAt: null, state: "unavailable" },
  deviation: { value: null, unit: "deg", measuredAt: null, state: "unavailable" },
}));

export const SIMULATION_PRESET_DESCRIPTIONS: {
  id: SimulationPresetId;
  label: string;
  shortTag: string;
  description: string;
}[] = [
  {
    id: "demo_01_full",
    label: "Demo 01 — Canonical 12-Cycle Session",
    shortTag: "DEMO 01",
    description: "12 cycles, 11 finished, 8 confirmed correct (72.7%), 14 attempts (9/13 = 69.2%), C-007 recovery, C-004 defect escape, C-012 in progress.",
  },
  {
    id: "failed_grasp_recovery",
    label: "Failed Grasp → Recovered Success (1 Cycle, 2 Attempts)",
    shortTag: "RECOVERY 1×2",
    description: "Single cycle with 1 failed grasp followed by 1 confirmed retry: 1/1 cycle correctness (100%), 1/2 attempt success (50%), 1 retry, 0 first-attempt.",
  },
  {
    id: "two_failed_attempts_recovery",
    label: "Two Failed Attempts → Recovery (1 Cycle, 3 Attempts)",
    shortTag: "RECOVERY 1×3",
    description: "Two failed physical grasps followed by verified recovery on attempt 3: 1 cycle, 3 attempts (1/3 = 33.3%), 2 retries, 1 recovered cycle.",
  },
  {
    id: "extra_inspection_no_retry",
    label: "Extra Inspection Without Physical Retry",
    shortTag: "EXTRA VIEW",
    description: "Gemini selects reinspect_other_view before placing: 2 linked inspections, 1 physical attempt, 0 retries.",
  },
  {
    id: "wrong_bin_defect_escape",
    label: "Wrong-Bin / Defect Escape (C-004 Case)",
    shortTag: "DEFECT ESCAPE",
    description: "Defective reference brick predicted good and physically placed in good_bin: physical attempt successful (1/1), overall task failed (0/1).",
  },
  {
    id: "provider_timeout_hold",
    label: "Provider Timeout → Safe Local Hold",
    shortTag: "TIMEOUT HOLD",
    description: "Cloud model request exceeds deadline; local validator rejects late output and holds brick safely rather than routing to good_bin.",
  },
  {
    id: "stale_evidence_rejected",
    label: "Stale Evidence & Goal Version Change Rejected",
    shortTag: "STALE REJECT",
    description: "Task selection computed against goal v1 rejected after operator voice goal commits v2 at boundary; requires fresh snapshot.",
  },
  {
    id: "queued_voice_goal",
    label: "Queued Voice Goal + Utterance Deduplication",
    shortTag: "VOICE QUEUE",
    description: "ElevenLabs partial, committed, and timestamp-enriched segments deduplicated into one queued goal awaiting next boundary.",
  },
  {
    id: "unverified_connection_loss",
    label: "Connection Loss → Unverified Outcome",
    shortTag: "CONN LOSS",
    description: "Camera/controller stream drops mid-place: last frame marked Stale, physical outcome remains Unverified (never fabricated as success/fail).",
  },
  {
    id: "audited_correction",
    label: "Audited Manual Correction & Late Confirmation",
    shortTag: "AUDIT TRAIL",
    description: "Demonstrates late operator confirmation and audited reference-label correction with preserved author, reason, and prior value.",
  },
  {
    id: "normal_success",
    label: "Normal First-Attempt Success",
    shortTag: "FIRST-ATTEMPT",
    description: "Clean single-attempt confirmed cycle with full timing breakdown.",
  },
  {
    id: "empty_session",
    label: "Empty Session — No Eligible Denominators",
    shortTag: "EMPTY",
    description: "Bookkeeping session started with 0 cycles: all percentages render 'No data yet' without movement.",
  },
];

interface RawDemoSpec {
  id: string;
  objId: string;
  startedAt: string;
  endedAt: string | null;
  outcome: Cycle["outcome"];
  attempts: Attempt["outcome"][];
  ref: Quality | null;
  prediction: Quality | null;
  score: number;
  commandedDestination: Cycle["commandedDestination"];
  observedDestination: Cycle["observedDestination"];
  duration: number | null;
  extraInspections: number;
  activePhase: Cycle["activePhase"];
  faultedPhase: Cycle["faultedPhase"];
}

const DEMO_01_SPECS: RawDemoSpec[] = [
  {
    id: "C-001",
    objId: "D-001",
    startedAt: "2026-11-14T13:36:10.000Z",
    endedAt: "2026-11-14T13:36:20.800Z",
    outcome: "correct",
    attempts: ["successful"],
    ref: "good",
    prediction: "good",
    score: 0.21,
    commandedDestination: "good_bin",
    observedDestination: "good_bin",
    duration: 10.8,
    extraInspections: 0,
    activePhase: "verify_outcome",
    faultedPhase: null,
  },
  {
    id: "C-002",
    objId: "D-002",
    startedAt: "2026-11-14T13:36:40.000Z",
    endedAt: "2026-11-14T13:36:51.200Z",
    outcome: "correct",
    attempts: ["successful"],
    ref: "defective",
    prediction: "defective",
    score: 0.84,
    commandedDestination: "defective_bin",
    observedDestination: "defective_bin",
    duration: 11.2,
    extraInspections: 0,
    activePhase: "verify_outcome",
    faultedPhase: null,
  },
  {
    id: "C-003",
    objId: "D-003",
    startedAt: "2026-11-14T13:37:10.000Z",
    endedAt: "2026-11-14T13:37:27.400Z",
    outcome: "correct",
    attempts: ["failed", "successful"],
    ref: "good",
    prediction: "good",
    score: 0.34,
    commandedDestination: "good_bin",
    observedDestination: "good_bin",
    duration: 17.4,
    extraInspections: 1,
    activePhase: "verify_outcome",
    faultedPhase: null,
  },
  {
    id: "C-004",
    objId: "D-004",
    startedAt: "2026-11-14T13:38:00.000Z",
    endedAt: "2026-11-14T13:38:10.700Z",
    outcome: "failed",
    attempts: ["successful"],
    ref: "defective",
    prediction: "good",
    score: 0.58,
    commandedDestination: "good_bin",
    observedDestination: "good_bin",
    duration: 10.7,
    extraInspections: 0,
    activePhase: "verify_outcome",
    faultedPhase: "inspect",
  },
  {
    id: "C-005",
    objId: "D-005",
    startedAt: "2026-11-14T13:38:30.000Z",
    endedAt: "2026-11-14T13:38:40.900Z",
    outcome: "correct",
    attempts: ["successful"],
    ref: "good",
    prediction: "good",
    score: 0.19,
    commandedDestination: "good_bin",
    observedDestination: "good_bin",
    duration: 10.9,
    extraInspections: 0,
    activePhase: "verify_outcome",
    faultedPhase: null,
  },
  {
    id: "C-006",
    objId: "D-006",
    startedAt: "2026-11-14T13:39:10.000Z",
    endedAt: "2026-11-14T13:39:14.100Z",
    outcome: "aborted",
    attempts: ["aborted"],
    ref: null,
    prediction: null,
    score: 0.0,
    commandedDestination: null,
    observedDestination: null,
    duration: 4.1,
    extraInspections: 0,
    activePhase: "pick",
    faultedPhase: "pick",
  },
  {
    id: "C-007",
    objId: "D-007",
    startedAt: "2026-11-14T13:40:10.000Z",
    endedAt: "2026-11-14T13:40:26.800Z",
    outcome: "correct",
    attempts: ["failed", "successful"],
    ref: "defective",
    prediction: "defective",
    score: 0.78,
    commandedDestination: "defective_bin",
    observedDestination: "defective_bin",
    duration: 16.8,
    extraInspections: 1,
    activePhase: "verify_outcome",
    faultedPhase: null,
  },
  {
    id: "C-008",
    objId: "D-008",
    startedAt: "2026-11-14T13:40:50.000Z",
    endedAt: "2026-11-14T13:41:02.400Z",
    outcome: "unverified",
    attempts: ["unverified"],
    ref: null,
    prediction: "defective",
    score: 0.74,
    commandedDestination: "defective_bin",
    observedDestination: null,
    duration: 12.4,
    extraInspections: 0,
    activePhase: "verify_outcome",
    faultedPhase: "verify_outcome",
  },
  {
    id: "C-009",
    objId: "D-009",
    startedAt: "2026-11-14T13:41:12.000Z",
    endedAt: "2026-11-14T13:41:23.300Z",
    outcome: "correct",
    attempts: ["successful"],
    ref: "good",
    prediction: "good",
    score: 0.24,
    commandedDestination: "good_bin",
    observedDestination: "good_bin",
    duration: 11.3,
    extraInspections: 0,
    activePhase: "verify_outcome",
    faultedPhase: null,
  },
  {
    id: "C-010",
    objId: "D-010",
    startedAt: "2026-11-14T13:41:28.000Z",
    endedAt: "2026-11-14T13:41:39.700Z",
    outcome: "correct",
    attempts: ["successful"],
    ref: "defective",
    prediction: "defective",
    score: 0.81,
    commandedDestination: "defective_bin",
    observedDestination: "defective_bin",
    duration: 11.7,
    extraInspections: 0,
    activePhase: "verify_outcome",
    faultedPhase: null,
  },
  {
    id: "C-011",
    objId: "D-011",
    startedAt: "2026-11-14T13:41:41.000Z",
    endedAt: "2026-11-14T13:41:52.000Z",
    outcome: "correct",
    attempts: ["successful"],
    ref: "good",
    prediction: "good",
    score: 0.22,
    commandedDestination: "good_bin",
    observedDestination: "good_bin",
    duration: 11.0,
    extraInspections: 0,
    activePhase: "verify_outcome",
    faultedPhase: null,
  },
  {
    id: "C-012",
    objId: "D-012",
    startedAt: "2026-11-14T13:42:02.000Z",
    endedAt: null,
    outcome: "in_progress",
    attempts: ["in_progress"],
    ref: null,
    prediction: "defective",
    score: 0.78,
    commandedDestination: null,
    observedDestination: null,
    duration: null,
    extraInspections: 1,
    activePhase: "choose_task",
    faultedPhase: null,
  },
];

export function buildSimulationSnapshot(
  presetId: SimulationPresetId = "demo_01_full",
  viewMode: "live" | "simulation" | "replay" = "simulation"
): StationSnapshot {
  if (viewMode === "live") {
    return buildDisconnectedLiveSnapshot();
  }

  const sessionId =
    presetId === "demo_01_full"
      ? "DEMO-01"
      : `SIM-${presetId.toUpperCase().slice(0, 12)}`;
  const sessionName =
    presetId === "demo_01_full"
      ? "Demo 01"
      : SIMULATION_PRESET_DESCRIPTIONS.find((p) => p.id === presetId)?.shortTag ?? "Sim 01";

  const session: Session = {
    id: sessionId,
    name: sessionName,
    sourceMode: "simulation",
    startedAt: "2026-11-14T13:35:00.000Z",
    endedAt: null,
    configId: "cfg-sim-duplo-01",
    robotId: "SO-101-SIM",
    displayTimezone: "Europe/Helsinki (UTC+02:00)",
    scenarioPreset: presetId,
    modelRuns: DEFAULT_MODEL_RUNS,
  };

  let specs: RawDemoSpec[] = [];
  if (presetId === "demo_01_full" || presetId === "queued_voice_goal") {
    specs = DEMO_01_SPECS;
  } else if (presetId === "empty_session") {
    specs = [];
  } else if (presetId === "normal_success") {
    specs = [DEMO_01_SPECS[0]];
  } else if (presetId === "failed_grasp_recovery") {
    specs = [DEMO_01_SPECS[6]]; // C-007: 1 failed grasp + 1 successful retry
  } else if (presetId === "two_failed_attempts_recovery") {
    specs = [
      {
        ...DEMO_01_SPECS[6],
        id: "C-007B",
        objId: "D-007B",
        attempts: ["failed", "failed", "successful"],
        duration: 21.6,
      },
    ];
  } else if (presetId === "extra_inspection_no_retry") {
    specs = [
      {
        ...DEMO_01_SPECS[1],
        id: "C-002X",
        objId: "D-002X",
        attempts: ["successful"],
        extraInspections: 1,
        duration: 14.3,
      },
    ];
  } else if (presetId === "wrong_bin_defect_escape") {
    specs = [DEMO_01_SPECS[3]]; // C-004: defective ref, predicted good, placed in good_bin
  } else if (presetId === "provider_timeout_hold") {
    specs = [
      {
        ...DEMO_01_SPECS[11],
        id: "C-012",
        objId: "D-012",
        activePhase: "choose_task",
        faultedPhase: "choose_task",
      },
    ];
  } else if (presetId === "stale_evidence_rejected") {
    specs = [DEMO_01_SPECS[6], DEMO_01_SPECS[11]];
  } else if (presetId === "unverified_connection_loss") {
    specs = [DEMO_01_SPECS[7]]; // C-008 unverified
  } else if (presetId === "audited_correction") {
    specs = [DEMO_01_SPECS[3], DEMO_01_SPECS[6]];
  }

  const cycles: Cycle[] = [];
  const attempts: Attempt[] = [];
  const inspections: Inspection[] = [];
  const frames: Frame[] = [];
  const confirmations: Confirmation[] = [];
  const referenceLabels: ReferenceLabel[] = [];
  const corrections: Correction[] = [];
  const nemotronObservations: NemotronObservation[] = [];
  const decisions: DecisionRecord[] = [];
  const skillExecutions: SkillExecution[] = [];

  for (const spec of specs) {
    const numSuffix = spec.id.replace("C-", "");
    const cycAttemptIds: string[] = [];
    const cycInspectionIds: string[] = [];
    const cycDecisionIds: string[] = [];
    const cycNemotronIds: string[] = [];

    // Primary frame
    const frame1Id = `F-${numSuffix}-01`;
    frames.push({
      id: frame1Id,
      sessionId: session.id,
      cycleId: spec.id,
      objectId: spec.objId,
      cameraId: "overhead",
      capturedAt: "2026-11-14T13:42:06.110Z",
      receivedAt: "2026-11-14T13:42:06.124Z",
      width: 1280,
      height: 720,
      imageUrl: SIMULATION_SCENE_URL,
      sha256: `sha256-sim-${frame1Id.toLowerCase()}`,
      stale: presetId === "unverified_connection_loss" || presetId === "stale_evidence_rejected",
      fps: null,
      overlayBox: { x: 49, y: 57, w: 10, h: 19 },
    });

    let activeFrameId = frame1Id;

    // Inspections
    if (spec.prediction !== null) {
      const ins1Id = `INS-${numSuffix}-01`;
      inspections.push({
        id: ins1Id,
        cycleId: spec.id,
        objectId: spec.objId,
        frameIds: [frame1Id],
        modelRunId: "mr-anomalib-01",
        score: spec.extraInspections > 0 ? Number((spec.score - 0.06).toFixed(2)) : spec.score,
        threshold: 0.65,
        scoreRange: [0, 1],
        classification: spec.prediction,
        mapEvidenceId: `MAP-${numSuffix}-01`,
        additionalInspectionOfId: null,
        isDecisionInspection: spec.extraInspections === 0,
        requestedAt: spec.startedAt,
        completedAt: spec.startedAt,
      });
      cycInspectionIds.push(ins1Id);

      for (let e = 0; e < spec.extraInspections; e++) {
        const extraIndex = e + 2;
        const extraFrameId = `F-${numSuffix}-0${extraIndex}`;
        activeFrameId = extraFrameId;
        frames.push({
          id: extraFrameId,
          sessionId: session.id,
          cycleId: spec.id,
          objectId: spec.objId,
          cameraId: "wrist",
          capturedAt: "2026-11-14T13:42:08.240Z",
          receivedAt: "2026-11-14T13:42:08.252Z",
          width: 1280,
          height: 720,
          imageUrl: SIMULATION_SCENE_URL,
          sha256: `sha256-sim-${extraFrameId.toLowerCase()}`,
          stale: presetId === "stale_evidence_rejected",
          fps: null,
          overlayBox: { x: 49, y: 57, w: 10, h: 19 },
        });

        const insExtraId = `INS-${numSuffix}-0${extraIndex}`;
        inspections.push({
          id: insExtraId,
          cycleId: spec.id,
          objectId: spec.objId,
          frameIds: [extraFrameId],
          modelRunId: "mr-anomalib-01",
          score: spec.score,
          threshold: 0.65,
          scoreRange: [0, 1],
          classification: spec.prediction,
          mapEvidenceId: `MAP-${numSuffix}-0${extraIndex}`,
          additionalInspectionOfId: ins1Id,
          isDecisionInspection: e === spec.extraInspections - 1,
          requestedAt: "2026-11-14T13:42:08.250Z",
          completedAt: "2026-11-14T13:42:08.410Z",
        });
        cycInspectionIds.push(insExtraId);
      }
    }

    // Attempts & Skill Executions
    spec.attempts.forEach((attOutcome, idx) => {
      const ordinal = idx + 1;
      const attId = `A-${numSuffix}-0${ordinal}`;
      const execId = `EX-${numSuffix}-0${ordinal}`;
      cycAttemptIds.push(attId);

      const taskForExec =
        attOutcome === "failed"
          ? "pick"
          : spec.commandedDestination === "defective_bin"
          ? "place_defective"
          : spec.commandedDestination === "good_bin"
          ? "place_good"
          : "present_for_inspection";

      skillExecutions.push({
        id: execId,
        cycleId: spec.id,
        attemptId: attId,
        taskId: taskForExec,
        policyId: "studio-vla-duplo-sort (pending)",
        policyVersion: "0.3.0-sim",
        commandSentAt: spec.startedAt,
        acknowledgedAt: attOutcome === "in_progress" ? null : spec.startedAt,
        finishedAt: attOutcome === "in_progress" ? null : spec.endedAt ?? spec.startedAt,
        motionStartedAt: attOutcome === "in_progress" ? null : spec.startedAt,
        motionEndedAt: attOutcome === "in_progress" ? null : spec.endedAt ?? spec.startedAt,
        controllerStatus:
          attOutcome === "in_progress"
            ? "sent"
            : attOutcome === "failed"
            ? "failed"
            : attOutcome === "aborted"
            ? "aborted"
            : "finished",
        physicalOutcome:
          attOutcome === "successful"
            ? "verified"
            : attOutcome === "failed"
            ? "failed"
            : attOutcome === "in_progress"
            ? "pending"
            : "unverified",
      });

      let confId: string | null = null;
      if (attOutcome === "successful") {
        confId = `CONF-${attId}`;
        confirmations.push({
          id: confId,
          source: spec.id === "C-007" ? "operator" : "camera",
          evidenceIds: [activeFrameId],
          authorId: spec.id === "C-007" ? "demo-operator" : null,
          confirmedAt: spec.endedAt ?? spec.startedAt,
          notes:
            spec.id === "C-007"
              ? "Defective bin observed; demo operator confirmation recorded."
              : "Overhead camera verified brick resting inside target bin.",
        });
      }

      attempts.push({
        id: attId,
        cycleId: spec.id,
        ordinal,
        executionIds: [execId],
        startedAt: spec.startedAt,
        endedAt: attOutcome === "in_progress" ? null : spec.endedAt,
        outcome: attOutcome,
        retryOfAttemptId: ordinal > 1 ? `A-${numSuffix}-0${ordinal - 1}` : null,
        retryReason: ordinal > 1 ? "Failed grasp: brick remained in pickup area" : null,
        errorCode: attOutcome === "failed" ? "GRASP_SLIP_DETECTED" : null,
        confirmationId: confId,
      });
    });

    // Nemotron observation
    const nemId = `NEM-${numSuffix}`;
    cycNemotronIds.push(nemId);
    const isTimeout = presetId === "provider_timeout_hold" && spec.id === "C-012";
    nemotronObservations.push({
      id: nemId,
      cycleId: spec.id,
      frameIds: [activeFrameId],
      modelId: "nvidia/nemotron-3.5-super-vl-120b-a12b",
      requestedAt: "2026-11-14T13:42:08.260Z",
      completedAt: isTimeout ? null : "2026-11-14T13:42:08.620Z",
      status: isTimeout ? "timeout" : "completed",
      observations:
        spec.id === "C-007"
          ? [
              "Object remains in pickup area after Attempt 01.",
              "Upper stud geometry clear and unobstructed for top-down grasp retry.",
            ]
          : [
              "Object visible. Surface region partially occluded.",
              "Side wall shows linear surface discontinuity near central stud.",
            ],
      hypotheses: [
        "Hypothesis (non-ground-truth): Possible mold seam or surface crack along front face.",
      ],
      uncertainty:
        spec.id === "C-012"
          ? "Lower edge shadowed under overhead illumination; wrist angle recommended."
          : null,
      rawArtifact: JSON.stringify({
        model: "nvidia/nemotron-3.5-super-vl-120b-a12b",
        frameId: activeFrameId,
        simulated: true,
      }),
      parseError: isTimeout ? "Provider deadline exceeded (timeout > 2500ms)" : null,
    });

    // Gemini Decision 1 record
    const decId = `DEC-${numSuffix}`;
    cycDecisionIds.push(decId);
    const isStaleRejected = presetId === "stale_evidence_rejected" && spec.id === "C-012";
    const selectedTask =
      isTimeout
        ? "hold"
        : spec.id === "C-012"
        ? "reinspect_other_view"
        : spec.commandedDestination === "defective_bin"
        ? "place_defective"
        : spec.commandedDestination === "good_bin"
        ? "place_good"
        : "hold";

    decisions.push({
      id: decId,
      sessionId: session.id,
      cycleId: spec.id,
      attemptId: cycAttemptIds[cycAttemptIds.length - 1] ?? null,
      kind: "task_selection",
      modelId: "gemini-decision-1",
      stateVersion: isStaleRejected ? 23 : 24,
      goalVersion: isStaleRejected ? 1 : 2,
      frameIds: [activeFrameId],
      offeredChoices: [
        "pick",
        "present_for_inspection",
        "reinspect_other_view",
        "place_good",
        "place_defective",
        "hold",
      ],
      selectedChoice: selectedTask,
      probabilities:
        selectedTask === "reinspect_other_view"
          ? {
              reinspect_other_view: 0.64,
              place_defective: 0.24,
              hold: 0.09,
              place_good: 0.03,
            }
          : {
              [selectedTask]: 0.88,
              hold: 0.08,
              reinspect_other_view: 0.04,
            },
      requestedAt: "2026-11-14T13:42:08.630Z",
      completedAt: isTimeout ? null : "2026-11-14T13:42:08.890Z",
      deadlineAt: "2026-11-14T13:42:10.000Z",
      validatorAccepted: !isStaleRejected && !isTimeout,
      validatorReason: isStaleRejected
        ? "Held: stale goalVersion (decision=v1, active=v2) and stale frame F-012-02"
        : isTimeout
        ? "Held: Gemini Decision 1 / Nemotron deadline expired; safe local hold enforced"
        : spec.id === "C-012"
        ? "Example selection · local validation pending"
        : "Validated stateVersion, goalVersion, frame freshness, and permitted task preconditions",
    });

    // Independent reference label
    let refId: string | null = null;
    if (spec.ref !== null) {
      refId = `REF-${numSuffix}`;
      referenceLabels.push({
        id: refId,
        objectId: spec.objId,
        cycleId: spec.id,
        quality: spec.ref,
        authorId: "demo-operator",
        method: "Independent visual inspection prior to fixture run",
        reason: "Pre-labeled reference brick for calibration & confusion matrix check",
        evidenceIds: [activeFrameId],
        createdAt: "2026-11-14T13:40:09.000Z",
      });
    }

    if (spec.id === "C-007" || presetId === "audited_correction") {
      corrections.push({
        id: `COR-${numSuffix}-01`,
        sessionId: session.id,
        entityType: "reference_label",
        entityId: refId ?? `REF-${numSuffix}`,
        field: "quality",
        previousValue: "unset",
        newValue: spec.ref ?? "defective",
        authorId: "Demo operator",
        reason: "Pre-labeled defect fixture. An edit must preserve author, time, prior value and reason.",
        createdAt: "2026-11-14T13:40:09.000Z",
      });
    }

    const plannedDest =
      spec.commandedDestination ??
      (spec.prediction === "defective"
        ? "defective_bin"
        : spec.prediction === "good"
        ? "good_bin"
        : null);

    const lastAttemptConfId =
      attempts
        .filter((a) => a.cycleId === spec.id)
        .map((a) => a.confirmationId)
        .filter(Boolean)
        .pop() ?? null;

    cycles.push({
      id: spec.id,
      sessionId: session.id,
      objectId: spec.objId,
      revision: spec.attempts.length > 1 ? 3 : 1,
      startedAt: spec.startedAt,
      endedAt: spec.endedAt,
      outcome: spec.outcome,
      activePhase: spec.activePhase,
      faultedPhase: spec.faultedPhase,
      phaseElapsedSec: 0.8,
      attemptIds: cycAttemptIds,
      inspectionIds: cycInspectionIds,
      decisionIds: cycDecisionIds,
      nemotronIds: cycNemotronIds,
      plannedDestination: plannedDest,
      commandedDestination: spec.commandedDestination,
      observedDestination: spec.observedDestination,
      referenceLabelId: refId,
      confirmationId: lastAttemptConfId,
      fullCycleDurationSec: spec.duration,
      timingBreakdown: {
        anomalibMs: 142,
        nemotronMs: isTimeout ? null : 360,
        geminiMs: isTimeout ? null : 260,
        motionMs: spec.duration ? Math.round(spec.duration * 1000 - 920) : null,
        verificationMs: spec.duration ? 158 : null,
        cloudWaitIncluded: true,
      },
    });
  }

  const utterances: VoiceUtterance[] = [
    {
      id: "utt-demo-01",
      sessionId: session.id,
      source: "scribe_v3_live",
      language: "en",
      partialTranscript: "",
      committedSegments: ["Take one more look", "before placing the next rejected object."],
      finalizedText: "Take one more look before placing the next rejected object.",
      timestampsEnriched: true,
      enrichmentTimestamps: [
        { word: "Take", startMs: 0, endMs: 210 },
        { word: "one", startMs: 220, endMs: 380 },
        { word: "more", startMs: 390, endMs: 610 },
        { word: "look", startMs: 620, endMs: 920 },
      ],
      selectedGoal: "extra_view_next_reject",
      goalProbabilities: {
        extra_view_next_reject: 0.94,
        standard_sorting: 0.04,
        pause_after_cycle: 0.01,
        unsupported_request: 0.01,
      },
      effectiveBoundary: "Next inspection / cycle boundary",
      state: "queued",
      createdAt: "2026-11-14T13:42:06.500Z",
      finalizedAt: "2026-11-14T13:42:07.120Z",
      transcriptionMs: 310,
      goalDecisionMs: 240,
    },
  ];

  const goalState: GoalState = {
    activeGoal: "standard_sorting",
    activeGoalLabel: "Standard sorting",
    goalVersion: presetId === "stale_evidence_rejected" ? 2 : 1,
    queuedGoal: "extra_view_next_reject",
    queuedGoalLabel: "Additional view",
    queuedBoundary: "Next boundary",
    updatedAt: "2026-11-14T13:42:07.120Z",
  };

  const recentEvents: StationEventEnvelope[] = [
    {
      schemaVersion: 1,
      eventId: "evt-demo-03",
      sequence: 3,
      type: "inspection.recorded",
      occurredAt: "2026-11-14T13:42:08.240Z",
      receivedAt: "2026-11-14T13:42:08.252Z",
      sourceMode: "simulation",
      sessionId: session.id,
      cycleId: "C-012",
      attemptId: "A-012-01",
      entityId: "INS-012-02",
      entityRevision: 1,
      summary: "Inspection recorded",
      statusTone: "good",
      payload: { score: 0.78, threshold: 0.65 },
    },
    {
      schemaVersion: 1,
      eventId: "evt-demo-02",
      sequence: 2,
      type: "goal.queued",
      occurredAt: "2026-11-14T13:42:07.120Z",
      receivedAt: "2026-11-14T13:42:07.130Z",
      sourceMode: "simulation",
      sessionId: session.id,
      cycleId: "C-012",
      attemptId: null,
      entityId: "utt-demo-01",
      entityRevision: 1,
      summary: "Goal queued",
      statusTone: "warn",
      payload: { queuedGoal: "extra_view_next_reject" },
    },
    {
      schemaVersion: 1,
      eventId: "evt-demo-01",
      sequence: 1,
      type: "outcome.confirmed",
      occurredAt: "2026-11-14T13:41:52.000Z",
      receivedAt: "2026-11-14T13:41:52.015Z",
      sourceMode: "simulation",
      sessionId: session.id,
      cycleId: "C-011",
      attemptId: "A-011-01",
      entityId: "C-011",
      entityRevision: 2,
      summary: "C-011 confirmed correct",
      statusTone: "good",
      payload: { outcome: "correct" },
    },
  ];

  const activeCycle =
    cycles.find((c) => c.outcome === "in_progress") ??
    cycles[cycles.length - 1] ??
    null;

  const metrics = computeSessionMetrics({
    session,
    stationConnected: true,
    cycles,
    attempts,
    inspections,
    referenceLabels,
  });

  let activeFaultBanner: string | null = null;
  if (presetId === "provider_timeout_hold") {
    activeFaultBanner =
      "Provider timeout on C-012: Nemotron / Gemini response exceeded deadline. Local validator enforced safe hold (brick never routed to good_bin on uncertainty).";
  } else if (presetId === "stale_evidence_rejected") {
    activeFaultBanner =
      "Stale decision rejected on C-012: Task choice used goalVersion v1 after v2 committed, with stale frame F-012-02.";
  } else if (presetId === "unverified_connection_loss") {
    activeFaultBanner =
      "Camera / controller stream interrupted on C-008: Last frame marked Stale; physical outcome preserved as Unverified.";
  } else if (presetId === "wrong_bin_defect_escape") {
    activeFaultBanner =
      "Defect escape detected on C-004: Reference-defective brick was predicted good (score 0.58 < 0.65) and placed in good_bin. Physical attempt succeeded, overall cycle outcome failed.";
  }

  return {
    viewMode,
    stationConnected: true,
    activeSession: session,
    sessions: [session],
    stateVersion: 24,
    goalState,
    pauseState: {
      requested: false,
      acknowledged: false,
      requestedAt: null,
      acknowledgedAt: null,
    },
    stopRecord: null,
    activeCycle,
    cycles,
    attempts,
    inspections,
    frames,
    confirmations,
    referenceLabels,
    corrections,
    nemotronObservations,
    decisions,
    skillExecutions,
    utterances,
    recentEvents,
    lastEventSequence: 3,
    components: DEFAULT_COMPONENTS,
    joints: DEFAULT_JOINTS,
    hardwareSummary: {
      cpuLoad: { value: null, unit: "%", measuredAt: null, state: "unavailable" },
      memory: { value: null, unit: "GB", measuredAt: null, state: "unavailable" },
      controlRate: { value: null, unit: "Hz", measuredAt: null, state: "unavailable" },
    },
    metrics,
    activeFaultBanner,
  };
}

/**
 * Default hardware view: disconnected & empty until connected.
 * Never presents seeded simulation fixtures as live hardware results!
 */
export function buildDisconnectedLiveSnapshot(): StationSnapshot {
  const emptyMetrics = computeSessionMetrics({
    session: null,
    stationConnected: false,
    cycles: [],
    attempts: [],
    inspections: [],
    referenceLabels: [],
  });

  return {
    viewMode: "live",
    stationConnected: false,
    activeSession: null,
    sessions: [],
    stateVersion: 0,
    goalState: {
      activeGoal: "standard_sorting",
      activeGoalLabel: "Standard sorting",
      goalVersion: 0,
      queuedGoal: null,
      queuedGoalLabel: null,
      queuedBoundary: null,
      updatedAt: "2026-11-14T13:35:00.000Z",
    },
    pauseState: {
      requested: false,
      acknowledged: false,
      requestedAt: null,
      acknowledgedAt: null,
    },
    stopRecord: null,
    activeCycle: null,
    cycles: [],
    attempts: [],
    inspections: [],
    frames: [],
    confirmations: [],
    referenceLabels: [],
    corrections: [],
    nemotronObservations: [],
    decisions: [],
    skillExecutions: [],
    utterances: [],
    recentEvents: [],
    lastEventSequence: 0,
    components: DEFAULT_COMPONENTS,
    joints: DEFAULT_JOINTS,
    hardwareSummary: {
      cpuLoad: { value: null, unit: "%", measuredAt: null, state: "unavailable" },
      memory: { value: null, unit: "GB", measuredAt: null, state: "unavailable" },
      controlRate: { value: null, unit: "Hz", measuredAt: null, state: "unavailable" },
    },
    metrics: emptyMetrics,
    activeFaultBanner: null,
  };
}
