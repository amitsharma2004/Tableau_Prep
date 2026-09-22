"""What Claude is allowed to see when generating a plan: table/column
metadata and a small row sample. Deliberately no field on either DTO can
hold a credential - `generate_plan()`'s signature only accepts these types,
so passing a Connection/secret in is a type error, not just a convention."""
from __future__ import annotations

from dataclasses import dataclass

from app.connectors.base import TableInfo


@dataclass
class SchemaContext:
    tables: list[TableInfo]


@dataclass
class SampleContext:
    # table_name -> sample rows (each row a plain dict of column -> value)
    samples: dict[str, list[dict]]
