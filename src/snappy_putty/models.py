from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


RiskLevel = Literal["low", "med", "high"]


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="ignore")

    step: int
    action: str
    why: str


class SuggestedCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cmd: str
    explain: str
    risk: RiskLevel


class Snippet(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    language: str
    content: str


class AgentOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    goal: str
    assumptions: list[str]
    question: str | None
    plan: list[PlanStep]
    commands: list[SuggestedCommand]
    warnings: list[str]
    snippets: list[Snippet] = Field(default_factory=list)
