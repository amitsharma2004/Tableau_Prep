"""Connector interface every source database must implement.

`check_read_only()` is the enforcement point for the "destructive queries"
edge case (build plan §Edge-Case Enforcement): services/connection_service.py
calls it once at connection-creation time and rejects the connection if it
returns False, so a writable DB user can never be saved in the first place.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_identifier(name: str, dialect: str = "ansi") -> str:
    """Guard against SQL injection via table/schema names that ultimately
    trace back to an LLM-generated plan (see transform/plan_to_sql.py in a
    later milestone). Only allows standard identifier characters."""
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Unsafe or invalid identifier: {name!r}")
    if dialect == "mysql":
        return f"`{name}`"
    return f'"{name}"'


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool


@dataclass
class TableInfo:
    name: str
    schema: str
    columns: list[ColumnInfo]


class DBConnector(ABC):
    @abstractmethod
    def test_connection(self) -> None:
        """Raise if the connection cannot be opened."""

    @abstractmethod
    def check_read_only(self) -> bool:
        """True only if the configured user holds no write/DDL privileges
        anywhere it can see."""

    @abstractmethod
    def introspect_schema(self) -> list[TableInfo]:
        """Table/column metadata only - never row data."""

    @abstractmethod
    def sample_rows(self, table: str, schema: str | None, limit: int) -> list[dict]:
        """Small sample used only as LLM context (see llm/planner.py) or a UI preview."""

    @abstractmethod
    def explain(self, sql: str, params: dict | None = None) -> None:
        """Run EXPLAIN on `sql` without executing it - validates before real use."""

    @abstractmethod
    def run_readonly(self, sql: str, params: dict | None = None, chunksize: int = 50_000) -> Iterator[pd.DataFrame]:
        """Execute already-validated read-only `sql`, yielding chunks (never
        materializes the full result at once - see build plan 'large tables')."""

    @abstractmethod
    def count_rows(self, sql: str, params: dict | None = None) -> int:
        """COUNT(*) of `sql` without fetching any rows - used for join
        blow-up detection (rows_before vs rows_after)."""


class SQLAlchemyConnectorMixin:
    """Shared introspection/read implementation for any SQLAlchemy dialect.
    Subclasses set `_engine` (dialect-specific connection args) and
    `_system_schemas` (schemas to hide from introspection)."""

    _engine: Engine
    _system_schemas: set[str] = set()

    def test_connection(self) -> None:
        with self._engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    def introspect_schema(self) -> list[TableInfo]:
        inspector = inspect(self._engine)
        tables: list[TableInfo] = []
        for schema in inspector.get_schema_names():
            if schema in self._system_schemas:
                continue
            for table_name in inspector.get_table_names(schema=schema):
                columns = [
                    ColumnInfo(
                        name=col["name"],
                        data_type=str(col["type"]),
                        nullable=bool(col["nullable"]),
                    )
                    for col in inspector.get_columns(table_name, schema=schema)
                ]
                tables.append(TableInfo(name=table_name, schema=schema, columns=columns))
        return tables

    def sample_rows(self, table: str, schema: str | None, limit: int) -> list[dict]:
        qualified = (
            f"{quote_identifier(schema)}.{quote_identifier(table)}"
            if schema
            else quote_identifier(table)
        )
        with self._engine.connect() as conn:
            result = conn.execute(text(f"SELECT * FROM {qualified} LIMIT :limit"), {"limit": limit})
            return [dict(row._mapping) for row in result]

    def explain(self, sql: str, params: dict | None = None) -> None:
        with self._engine.connect() as conn:
            conn.execute(text(f"EXPLAIN {sql}"), params or {})

    def run_readonly(self, sql: str, params: dict | None = None, chunksize: int = 50_000) -> Iterator[pd.DataFrame]:
        with self._engine.connect() as conn:
            yield from pd.read_sql(text(sql), conn, params=params or {}, chunksize=chunksize)

    def count_rows(self, sql: str, params: dict | None = None) -> int:
        with self._engine.connect() as conn:
            return conn.execute(text(f"SELECT COUNT(*) FROM ({sql}) AS __count_subquery"), params or {}).scalar()
