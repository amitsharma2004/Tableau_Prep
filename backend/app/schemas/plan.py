from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.llm.plan_schema import PlanDraft


class PlanVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    flow_id: str
    version_number: int
    source: str  # 'llm_generated' | 'human_edited'
    plan: PlanDraft
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime


class PlanEditRequest(BaseModel):
    plan: PlanDraft


class PlanGenerateRequest(BaseModel):
    prompt: str | None = None
