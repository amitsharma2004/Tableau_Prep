"""Streams DataFrame chunks (e.g. from transform/executor.py's
execute_plan()) into a single .hyper file via the official Hyper API - never
materializes the full result set in memory (see build plan 'large tables').
Column types are decided once from the first non-empty chunk; every later
chunk is checked to still match, not silently coerced - see build plan
'Hyper type mismatches'.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pandas as pd
from tableauhyperapi import (
    Connection,
    CreateMode,
    HyperProcess,
    Inserter,
    SchemaName,
    TableDefinition,
    TableName,
    Telemetry,
)

from app.core.errors import HyperTypeMismatchError
from app.hyper.dtype_mapping import validate_dtypes

DEFAULT_SCHEMA_NAME = "Extract"
DEFAULT_TABLE_NAME = "Extract"


def _clean_for_insert(chunk: pd.DataFrame) -> pd.DataFrame:
    """NaN/NaT -> None, which is what the Hyper API expects for NULL."""
    return chunk.astype(object).where(pd.notnull(chunk), None)


def write_hyper_file(
    chunks: Iterator[pd.DataFrame],
    output_path: str | Path,
    table_name: str = DEFAULT_TABLE_NAME,
    schema_name: str = DEFAULT_SCHEMA_NAME,
) -> Path:
    output_path = Path(output_path)
    table_def: TableDefinition | None = None
    column_types: dict[str, object] | None = None
    rows_written = 0

    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        with Connection(
            endpoint=hyper.endpoint,
            database=str(output_path),
            create_mode=CreateMode.CREATE_AND_REPLACE,
        ) as connection:
            for chunk in chunks:
                if chunk.empty:
                    continue

                if table_def is None:
                    column_types = validate_dtypes(chunk)
                    table_def = TableDefinition(
                        table_name=TableName(schema_name, table_name),
                        columns=[
                            TableDefinition.Column(name=col, type=sql_type)
                            for col, sql_type in column_types.items()
                        ],
                    )
                    connection.catalog.create_schema(SchemaName(schema_name))
                    connection.catalog.create_table(table_def)
                else:
                    chunk_types = validate_dtypes(chunk)
                    mismatched = {
                        col: f"{column_types[col]} -> {chunk_types[col]}"
                        for col in column_types
                        if str(column_types[col]) != str(chunk_types[col])
                    }
                    if mismatched:
                        raise HyperTypeMismatchError(mismatched)

                clean_chunk = _clean_for_insert(chunk)
                with Inserter(connection, table_def) as inserter:
                    inserter.add_rows(rows=clean_chunk.itertuples(index=False, name=None))
                    inserter.execute()
                rows_written += len(chunk)

            if table_def is None:
                raise ValueError(
                    "Cannot write a .hyper file: the query returned no rows/columns to infer a schema from"
                )

    return output_path
