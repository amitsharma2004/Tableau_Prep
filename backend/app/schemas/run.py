from datetime import datetime

from pydantic import BaseModel


class RunRead(BaseModel):
    id: str
    flow_id: str
    plan_version_id: str
    run_type: str
    status: str
    generated_sql: str | None
    generated_code_lang: str | None
    rows_before: int | None
    rows_after: int | None
    row_count_anomaly: bool
    sample_before: list[dict] | None
    sample_after: list[dict] | None
    hyper_file_path: str | None
    publish_status: str | None
    publish_error: str | None
    error_message: str | None
    trigger_type: str = "manual"
    scheduled_for: datetime | None = None
    started_at: datetime
    finished_at: datetime | None
    triggered_by: str


class ApprovePreviewRequest(BaseModel):
    acknowledge_anomaly: bool = False
