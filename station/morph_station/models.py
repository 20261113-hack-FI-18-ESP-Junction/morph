"""Validated application records; these are not vendor or robot SDK payloads."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from pydantic import (
    AfterValidator, AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field,
    model_validator,
)


def iso_input(value: Any) -> Any:
    if not isinstance(value, (str, datetime)):
        raise ValueError("Use an ISO 8601 timestamp with an explicit timezone")
    return value


Time = Annotated[AwareDatetime, BeforeValidator(iso_input),
                 AfterValidator(lambda value: value.astimezone(timezone.utc))]
ID = Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")]
Text = Annotated[str, Field(min_length=1, max_length=4000)]
Quality = Literal["good", "defective"]
Destination = Literal["good_bin", "defective_bin", "other"]
RecordType = Literal["session", "cycle", "attempt", "frame", "inspection", "model_run",
                     "utterance", "decision", "execution", "reference_label", "confirmation"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    @model_validator(mode="after")
    def chronological(self):
        for start, end in (("startedAt", "endedAt"), ("requestedAt", "completedAt"),
                           ("requestedAt", "acknowledgedAt"), ("acknowledgedAt", "finishedAt"),
                           ("requestedAt", "finishedAt"), ("startedAt", "completedAt")):
            a, b = getattr(self, start, None), getattr(self, end, None)
            if a is not None and b is not None and b < a:
                raise ValueError(f"{end} must be at or after {start}")
        return self


class Session(StrictModel):
    id: ID
    name: Text
    sourceMode: Literal["live", "simulation"]
    startedAt: Time
    endedAt: Time | None = None
    configId: ID
    robotId: ID | None = None
    modelRuns: list[dict[str, Any]] = Field(default_factory=list, max_length=50)


class SessionScoped(StrictModel):
    id: ID
    sessionId: ID
    cycleId: ID | None = None


class Scoped(SessionScoped):
    cycleId: ID


class Cycle(StrictModel):
    id: ID
    sessionId: ID
    objectId: ID
    startedAt: Time
    endedAt: Time | None = None
    outcome: Literal["in_progress", "correct", "failed", "aborted", "unverified"] = "in_progress"
    commandedDestination: Destination | None = None
    observedDestination: Destination | None = None
    referenceLabelId: ID | None = None
    inspectionId: ID | None = None
    confirmationId: ID | None = None

    @model_validator(mode="after")
    def finished(self):
        if (self.outcome == "in_progress") != (self.endedAt is None):
            raise ValueError("Only in_progress cycles have no endedAt")
        return self


class Attempt(Scoped):
    ordinal: int = Field(ge=1)
    startedAt: Time
    endedAt: Time | None = None
    outcome: Literal["in_progress", "successful", "failed", "aborted", "unverified"] = "in_progress"
    retryOfAttemptId: ID | None = None
    retryReason: Text | None = None
    errorCode: Text | None = None
    confirmationId: ID | None = None

    @model_validator(mode="after")
    def finished(self):
        if (self.outcome == "in_progress") != (self.endedAt is None):
            raise ValueError("Only in_progress attempts have no endedAt")
        if self.ordinal > 1 and (not self.retryOfAttemptId or not self.retryReason):
            raise ValueError("Retries must identify the preceding attempt and reason")
        if self.ordinal == 1 and self.retryOfAttemptId:
            raise ValueError("First attempt cannot retry another attempt")
        return self


class Evidence(Scoped):
    mediaType: Literal["image/png", "image/jpeg", "application/json", "text/plain"]
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size: int = Field(ge=1, le=5 * 1024 * 1024)
    capturedAt: Time


class Frame(Scoped):
    objectId: ID
    cameraId: ID
    capturedAt: Time
    receivedAt: Time
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    evidenceId: ID


class ModelRun(SessionScoped):
    provider: Text
    modelId: Text
    requestedAt: Time
    completedAt: Time | None = None
    frameIds: list[ID] = Field(default_factory=list)
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] | None = None
    error: str | None = None
    latencyMs: float | None = Field(default=None, ge=0)
    device: str | None = None
    precision: str | None = None


class Inspection(Scoped):
    objectId: ID
    frameIds: list[ID] = Field(min_length=1)
    modelRunId: ID
    score: float
    threshold: float
    classification: Literal["good", "defective", "review_required"]
    mapEvidenceId: ID | None = None
    additionalInspectionOfId: ID | None = None
    requestedAt: Time
    completedAt: Time


class ReferenceLabel(Scoped):
    objectId: ID
    quality: Quality
    authorId: ID
    method: Text
    evidenceIds: list[ID] = Field(default_factory=list)
    createdAt: Time


class Confirmation(Scoped):
    source: Literal["camera", "sensor", "operator"]
    evidenceIds: list[ID] = Field(default_factory=list)
    authorId: ID | None = None
    attemptId: ID | None = None
    confirmedAt: Time
    physicalSuccess: bool
    observedDestination: Destination | None = None

    @model_validator(mode="after")
    def evidence_required(self):
        if self.source == "operator" and not self.authorId:
            raise ValueError("Operator confirmation requires authorId")
        if self.source in ("camera", "sensor") and not self.evidenceIds:
            raise ValueError("Camera/sensor confirmation requires evidence")
        return self


class Utterance(SessionScoped):
    text: Text
    source: Literal["voice", "typed"]
    provider: str | None = None
    modelId: str | None = None
    startedAt: Time
    completedAt: Time
    status: Literal["partial", "finalized", "rejected"]
    language: str | None = None


class Decision(SessionScoped):
    kind: Literal["goal", "task"]
    modelRunId: ID
    offeredChoices: list[ID] = Field(min_length=1)
    selectedChoice: ID
    stateVersion: int = Field(ge=0)
    goalVersion: int = Field(ge=0)
    frameIds: list[ID] = Field(default_factory=list)
    requestedAt: Time
    completedAt: Time
    accepted: bool | None = None
    rejectionReason: str | None = None

    @model_validator(mode="after")
    def permitted_choice(self):
        if self.kind == "task" and not self.cycleId:
            raise ValueError("Task decisions require cycleId")
        if len(set(self.offeredChoices)) != len(self.offeredChoices):
            raise ValueError("Choices must be unique")
        if self.selectedChoice not in self.offeredChoices:
            raise ValueError("Selected choice was not offered")
        return self


class Execution(Scoped):
    attemptId: ID
    taskId: ID
    policyId: Text
    decisionId: ID | None = None
    status: Literal["requested", "acknowledged", "finished", "failed", "unverified"]
    requestedAt: Time
    acknowledgedAt: Time | None = None
    finishedAt: Time | None = None
    error: str | None = None

    @model_validator(mode="after")
    def lifecycle(self):
        if self.status == "acknowledged" and self.acknowledgedAt is None:
            raise ValueError("Acknowledged execution needs acknowledgedAt")
        if self.status in ("finished", "failed") and self.finishedAt is None:
            raise ValueError("Finished/failed execution needs finishedAt")
        return self


MODELS = {
    "session": Session, "cycle": Cycle, "attempt": Attempt, "frame": Frame,
    "inspection": Inspection, "model_run": ModelRun, "utterance": Utterance,
    "decision": Decision, "execution": Execution, "reference_label": ReferenceLabel,
    "confirmation": Confirmation, "evidence": Evidence,
}


class RecordWrite(StrictModel):
    eventId: ID
    recordType: RecordType
    record: dict[str, Any]
    expectedRevision: int | None = Field(default=None, ge=1)
    occurredAt: Time | None = None


class CorrectionRequest(StrictModel):
    id: ID
    eventId: ID
    entityType: Literal["session", "cycle", "attempt", "reference_label"]
    entityId: ID
    expectedRevision: int = Field(ge=1)
    field: Text
    previousValue: Any
    newValue: Any
    authorId: ID
    reason: Text
    createdAt: Time


class EvidenceUpload(StrictModel):
    id: ID
    eventId: ID
    sessionId: ID
    cycleId: ID
    mediaType: Literal["image/png", "image/jpeg", "application/json", "text/plain"]
    contentBase64: str = Field(max_length=7 * 1024 * 1024)
    capturedAt: Time
