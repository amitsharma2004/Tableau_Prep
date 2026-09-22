from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.llm.plan_schema import PlanDraft


class PlanVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    flow_id: str
    version_number: int
    source: str  # 'llm_generated' | 'human_edited'
    parent_version_id: str | None = None
    change_summary: str | None = None
    plan: PlanDraft
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime


class PlanEditRequest(BaseModel):
    plan: PlanDraft
    change_summary: str | None = None
    base_version_id: str | None = None  # for optimistic concurrency protection


class PlanRestoreRequest(BaseModel):
    version_id: str


class PlanGenerateRequest(BaseModel):
    prompt: str | None = None
