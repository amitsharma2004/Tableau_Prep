from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConnectionCreate(BaseModel):
    name: str
    type: str = Field(pattern="^(postgres|mysql|sqlite|tableau_server)$")
    host: str
    port: int
    database_name: str
    username: str
    secret: str  # plaintext password/PAT, write-only - encrypted before storage, never echoed back
    tableau_site_id: str | None = None
    tableau_project_id: str | None = None


class ConnectionRead(BaseModel):
    """Deliberately has no secret/encrypted_secret field - the only way to
    make leaking it via `response_model=ConnectionRead` impossible."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: str
    host: str | None
    port: int | None
    database_name: str | None
    username: str | None
    is_read_only: bool
    tableau_site_id: str | None
    tableau_project_id: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class ColumnSchema(BaseModel):
    name: str
    data_type: str
    nullable: bool


class TableSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    schema_name: str = Field(alias="schema")
    columns: list[ColumnSchema]


class ConnectionTestResult(BaseModel):
    connected: bool
    is_read_only: bool
    tables: list[TableSchema]
