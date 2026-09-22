from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FlowCreate(BaseModel):
    name: str
    nl_request: str
    source_connection_id: str
    tableau_connection_id: str | None = None
    target_datasource_name: str | None = None


class FlowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    nl_request: str
    source_connection_id: str
    tableau_connection_id: str | None
    target_datasource_name: str | None
    status: str
    current_version_id: str | None = None
    approved_version_id: str | None = None
    active_plan_version_id: str | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime
