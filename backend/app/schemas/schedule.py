from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from croniter import croniter


class ScheduleCreateRequest(BaseModel):
    cron_expression: str
    timezone: str = "UTC"
    enabled: bool = True

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        v = v.strip()
        if not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: {v!r}")
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        v = v.strip()
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError:
            raise ValueError(f"Invalid timezone: {v!r}")
        return v


class ScheduleUpdateRequest(BaseModel):
    cron_expression: str | None = None
    timezone: str | None = None
    enabled: bool | None = None

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not croniter.is_valid(v):
                raise ValueError(f"Invalid cron expression: {v!r}")
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            try:
                ZoneInfo(v)
            except ZoneInfoNotFoundError:
                raise ValueError(f"Invalid timezone: {v!r}")
        return v


class ScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    flow_id: str
    plan_version_id: str
    enabled: bool
    cron_expression: str
    timezone: str
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_run_status: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime
