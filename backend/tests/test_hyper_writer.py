import pandas as pd
import pytest
from tableauhyperapi import Connection, CreateMode, HyperProcess, Telemetry

from app.core.errors import HyperTypeMismatchError
from app.hyper.writer import write_hyper_file


def _read_back(path):
    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        with Connection(endpoint=hyper.endpoint, database=str(path)) as connection:
            rows = connection.execute_list_query('SELECT * FROM "Extract"."Extract" ORDER BY "id"')
    return rows


def test_write_hyper_file_streams_multiple_chunks_into_one_table(tmp_path):
    out = tmp_path / "test.hyper"
    chunk1 = pd.DataFrame({"id": [1, 2], "region": ["North", "South"], "amount": [100.0, None]})
    chunk2 = pd.DataFrame({"id": [3], "region": [None], "amount": [50.5]})

    write_hyper_file(iter([chunk1, chunk2]), out)

    assert out.exists()
    rows = _read_back(out)
    assert len(rows) == 3
    assert rows[0] == [1, "North", 100.0]
    assert rows[1][2] is None  # NaN -> NULL round-tripped correctly
    assert rows[2] == [3, None, 50.5]


def test_write_hyper_file_rejects_dtype_change_between_chunks(tmp_path):
    out = tmp_path / "test.hyper"
    chunk1 = pd.DataFrame({"id": [1], "amount": [100.0]})  # amount: float
    chunk2 = pd.DataFrame({"id": [2], "amount": ["not-a-number"]})  # amount: str - a real dtype drift

    with pytest.raises(HyperTypeMismatchError):
        write_hyper_file(iter([chunk1, chunk2]), out)


def test_write_hyper_file_rejects_unsupported_column_type(tmp_path):
    out = tmp_path / "test.hyper"
    bad_chunk = pd.DataFrame({"duration": pd.to_timedelta(["1 days", "2 days"])})

    with pytest.raises(HyperTypeMismatchError) as exc_info:
        write_hyper_file(iter([bad_chunk]), out)

    assert "duration" in exc_info.value.offending_columns


def test_write_hyper_file_raises_on_no_data(tmp_path):
    out = tmp_path / "test.hyper"

    with pytest.raises(ValueError):
        write_hyper_file(iter([]), out)


def test_write_hyper_file_skips_empty_chunks_but_uses_first_nonempty_for_schema(tmp_path):
    out = tmp_path / "test.hyper"
    empty_chunk = pd.DataFrame({"id": pd.Series([], dtype="int64"), "amount": pd.Series([], dtype="float64")})
    real_chunk = pd.DataFrame({"id": [1], "amount": [42.0]})

    write_hyper_file(iter([empty_chunk, real_chunk]), out)

    rows = _read_back(out)
    assert rows == [[1, 42.0]]
