"""Explicit pandas dtype -> Hyper SqlType mapping, validated BEFORE any
write happens - the enforcement point for the build plan's 'Hyper type
mismatches' edge case. Fails with a clear list of offending columns instead
of letting the Hyper API raise an opaque low-level error mid-write.
"""
from __future__ import annotations

import decimal

import pandas as pd
from tableauhyperapi import SqlType

from app.core.errors import HyperTypeMismatchError


def _sql_type_for_series(series: pd.Series) -> SqlType | None:
    """Returns the Hyper SqlType for this column, or None if the dtype (or,
    for object columns, its actual contents) isn't something we support."""
    dtype = series.dtype

    if pd.api.types.is_bool_dtype(dtype):
        return SqlType.bool()
    if pd.api.types.is_integer_dtype(dtype):
        return SqlType.big_int()
    if pd.api.types.is_float_dtype(dtype):
        return SqlType.double()
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return SqlType.timestamp()
    if isinstance(dtype, pd.CategoricalDtype):
        return SqlType.text()

    if pd.api.types.is_object_dtype(dtype):
        non_null = series.dropna()
        if non_null.empty:
            return SqlType.text()  # all-null column - default to text
        value_types = {type(v) for v in non_null}
        if value_types <= {str}:
            return SqlType.text()
        if value_types <= {decimal.Decimal}:
            return SqlType.numeric(18, 4)
        return None  # mixed or otherwise-unsupported object column

    if pd.api.types.is_string_dtype(dtype):
        # pandas' dedicated string extension dtype (pandas >= 3.0's default
        # for string columns, or an explicit pd.StringDtype) - unlike
        # `object`, this dtype guarantees homogeneous string content, so no
        # content inspection is needed here.
        return SqlType.text()

    return None  # e.g. timedelta64, complex - unsupported


def validate_dtypes(df: pd.DataFrame) -> dict[str, SqlType]:
    """Returns column -> SqlType for every column, or raises
    HyperTypeMismatchError naming every column whose dtype/contents this
    mapping doesn't know how to handle safely."""
    mapping: dict[str, SqlType] = {}
    offending: dict[str, str] = {}

    for col in df.columns:
        sql_type = _sql_type_for_series(df[col])
        if sql_type is None:
            offending[col] = str(df[col].dtype)
        else:
            mapping[col] = sql_type

    if offending:
        raise HyperTypeMismatchError(offending)

    return mapping
