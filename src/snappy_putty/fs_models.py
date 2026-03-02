from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


FsAction = Literal["mkdir", "copy", "move", "rename"]
FsRisk = Literal["low", "med"]
FsApplyStatus = Literal["applied", "skipped", "failed"]


class PlannedOp(BaseModel):
    model_config = ConfigDict(extra="ignore")

    op_id: str
    action: FsAction
    src: str | None
    dst: str | None
    notes: list[str] = Field(default_factory=list)
    risk: FsRisk


class FsPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    goal: str
    cwd: str
    ops: list[PlannedOp] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_confirmation: bool


class FsApplyItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    op_id: str
    action: FsAction
    status: FsApplyStatus
    message: str


class FsApplyResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    goal: str
    results: list[FsApplyItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
