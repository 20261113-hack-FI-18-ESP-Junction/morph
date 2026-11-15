"""Versioned input and output contracts for the read-only evidence analyst."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import ID

MODEL = "gemma-4-26b-a4b-it"
CONTRACT_VERSION = "gemma-brief-v1"
PROMPT_VERSION = "gemma-evidence-v11"
CONTEXT_VERSION = "morph-evidence-v7"


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Selection(ClosedModel):
    kind: Literal["cycle_explanation", "session_comparison"]
    sessionIds: list[ID] = Field(min_length=1, max_length=2)
    cycleId: ID | None = None
    sourceMode: Literal["simulation", "live"]
    comparisonSpecId: ID | None = None
    baselineSessionId: ID | None = None
    adaptiveSessionId: ID | None = None

    @model_validator(mode="after")
    def scope(self):
        if self.kind == "cycle_explanation":
            if len(self.sessionIds) != 1 or self.cycleId is None:
                raise ValueError("Cycle analysis requires one session and a cycle")
            if any((self.comparisonSpecId, self.baselineSessionId, self.adaptiveSessionId)):
                raise ValueError("Cycle analysis does not accept comparison fields")
        else:
            if len(set(self.sessionIds)) != 2 or self.cycleId is not None:
                raise ValueError("Comparison requires two distinct sessions and no cycle")
            if self.baselineSessionId is None or self.adaptiveSessionId is None:
                raise ValueError("Comparison requires explicit baseline and adaptive session roles")
            if {self.baselineSessionId, self.adaptiveSessionId} != set(self.sessionIds):
                raise ValueError("Comparison roles must identify the two selected sessions")
        return self


class AnalysisRequest(Selection):
    requestId: ID
    question: str = Field(default="Explain the recorded evidence and its limitations.", min_length=1, max_length=500)
    expectedSelectionDigest: str = Field(pattern=r"^[0-9a-f]{64}$")

    def selection(self) -> Selection:
        return Selection.model_validate({key: getattr(self, key) for key in Selection.model_fields})


class Interpretation(ClosedModel):
    text: str = Field(min_length=1, max_length=350)
    factIds: list[str] = Field(min_length=1, max_length=8)
    metricIds: list[str] = Field(default_factory=list, max_length=4)


class Hypothesis(ClosedModel):
    text: str = Field(min_length=1, max_length=250)
    factIds: list[str] = Field(min_length=1, max_length=8)
    gapKeys: list[str] = Field(min_length=1, max_length=8)


class EvidenceBriefResponse(ClosedModel):
    contractVersion: Literal["gemma-brief-v1"]
    answerState: Literal["supported", "insufficient_evidence"]
    headline: str = Field(min_length=1, max_length=120)
    interpretations: list[Interpretation] = Field(max_length=4)
    hypotheses: list[Hypothesis] = Field(default_factory=list, max_length=2)
    evidenceGapKeys: list[str] = Field(default_factory=list, max_length=20)
    suggestedReviewTargetIds: list[str] = Field(default_factory=list, max_length=3)
