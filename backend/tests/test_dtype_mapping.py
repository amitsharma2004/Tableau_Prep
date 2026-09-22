import decimal

import pandas as pd
import pytest
from tableauhyperapi import SqlType

from app.core.errors import HyperTypeMismatchError
from app.hyper.dtype_mapping import validate_dtypes


def test_validate_dtypes_maps_common_pandas_types():
    df = pd.DataFrame(
        {
            "id": pd.Series([1, 2, 3], dtype="int64"),
            "amount": pd.Series([1.5, 2.5, None], dtype="float64"),
            "is_active": pd.Series([True, False, True], dtype="bool"),
            "name": pd.Series(["a", "b", None], dtype="object"),
            "created_at": pd.to_datetime(["2026-01-01", "2026-01-02", None]),
        }
    )

    mapping = validate_dtypes(df)

    assert str(mapping["id"]) == str(SqlType.big_int())
    assert str(mapping["amount"]) == str(SqlType.double())
    assert str(mapping["is_active"]) == str(SqlType.bool())
    assert str(mapping["name"]) == str(SqlType.text())
    assert str(mapping["created_at"]) == str(SqlType.timestamp())


def test_validate_dtypes_maps_decimal_object_column():
    df = pd.DataFrame({"price": pd.Series([decimal.Decimal("1.50"), decimal.Decimal("2.00")], dtype="object")})

    mapping = validate_dtypes(df)

    assert str(mapping["price"]) == str(SqlType.numeric(18, 4))


def test_validate_dtypes_all_null_column_defaults_to_text():
    df = pd.DataFrame({"maybe": pd.Series([None, None, None], dtype="object")})

    mapping = validate_dtypes(df)

    assert str(mapping["maybe"]) == str(SqlType.text())


def test_validate_dtypes_rejects_mixed_type_object_column():
    df = pd.DataFrame({"bad": pd.Series(["a", 1, 2.5], dtype="object")})

    with pytest.raises(HyperTypeMismatchError) as exc_info:
        validate_dtypes(df)

    assert "bad" in exc_info.value.offending_columns


def test_validate_dtypes_rejects_timedelta_column():
    df = pd.DataFrame({"duration": pd.to_timedelta(["1 days", "2 days"])})

    with pytest.raises(HyperTypeMismatchError) as exc_info:
        validate_dtypes(df)

    assert "duration" in exc_info.value.offending_columns


def test_validate_dtypes_reports_all_offending_columns_at_once():
    df = pd.DataFrame(
        {
            "good": pd.Series([1, 2], dtype="int64"),
            "bad1": pd.to_timedelta(["1 days", "2 days"]),
            "bad2": pd.Series(["x", 1], dtype="object"),
        }
    )

    with pytest.raises(HyperTypeMismatchError) as exc_info:
        validate_dtypes(df)

    assert set(exc_info.value.offending_columns.keys()) == {"bad1", "bad2"}
