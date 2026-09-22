import json

import pandas as pd
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core import security
from app.core.errors import DomainError, PublishError
from app.core.state_machine import FlowStatus
from app.db.base import Base
from app.db.models.connection import Connection
from app.db.models.flow import Flow
from app.db.models.plan_version import PlanVersion
from app.db.models.run import Run
from app.services import run_service
from tests.test_plan_schema import VALID_PLAN
from tests.test_validators import LIVE_TABLES


class FakeConnector:
    def __init__(self, live_tables=LIVE_TABLES, num_chunks=1, rows_per_chunk=1, explain_fails=False):
        self.live_tables = live_tables
        self.num_chunks = num_chunks
        self.rows_per_chunk = rows_per_chunk
        self.explain_fails = explain_fails

    def introspect_schema(self):
        return self.live_tables

    def explain(self, sql, params=None):
        if self.explain_fails:
            raise RuntimeError("simulated EXPLAIN failure")

    def run_readonly(self, sql, params=None, chunksize=50_000):
        # A real generator - proves write_hyper_file consumes it lazily,
        # chunk by chunk, rather than requiring a materialized list.
        for i in range(self.num_chunks):
            yield pd.DataFrame(
                {
                    "region": [f"Region-{i}"] * self.rows_per_chunk,
                    "total_revenue": [float(i)] * self.rows_per_chunk,
                }
            )


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    monkeypatch.setattr(security.settings, "encryption_key", Fernet.generate_key().decode())


@pytest.fixture(autouse=True)
def hyper_output_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(run_service.settings, "hyper_output_dir", str(tmp_path / "hyper_output"))


@pytest.fixture()
def flow_ready_to_execute(db):
    source_conn = Connection(
        name="prod-pg", type="postgres", encrypted_secret=security.encrypt("pw"),
        created_by="shubhanshu@tnqtech.com",
    )
    tableau_conn = Connection(
        name="tableau-cloud", type="tableau_server", host="https://x.tableau.com",
        username="token-name", tableau_site_id="my-site", tableau_project_id="project-1",
        encrypted_secret=security.encrypt("pat-value"), created_by="shubhanshu@tnqtech.com",
    )
    db.add_all([source_conn, tableau_conn])
    db.flush()

    f = Flow(
        name="orders-revenue", nl_request="join orders and customers",
        source_connection_id=source_conn.id, tableau_connection_id=tableau_conn.id,
        target_datasource_name="orders-revenue", status=FlowStatus.DRAFT.value,
        created_by="shubhanshu@tnqtech.com",
    )
    db.add(f)
    db.flush()

    version = PlanVersion(
        flow_id=f.id, version_number=1, source="llm_generated",
        plan_json=json.dumps(VALID_PLAN), schema_snapshot_json="{}",
    )
    db.add(version)
    db.flush()

    f.active_plan_version_id = version.id
    f.status = FlowStatus.APPROVED.value
    db.flush()
    return f


def _patch_source_connector(monkeypatch, connector):
    monkeypatch.setattr(run_service, "build_connector", lambda *a, **k: connector)


def _patch_tableau_success(monkeypatch, luid="luid-123"):
    monkeypatch.setattr(run_service, "TableauClient", lambda *a, **k: object())
    monkeypatch.setattr(run_service, "publish_or_overwrite", lambda *a, **k: luid)


def test_execute_flow_succeeds_writes_hyper_and_publishes(db, flow_ready_to_execute, monkeypatch):
    _patch_source_connector(monkeypatch, FakeConnector(num_chunks=2, rows_per_chunk=3))
    _patch_tableau_success(monkeypatch)

    run = run_service.execute_flow(db, flow_ready_to_execute, actor="shubhanshu@tnqtech.com")

    assert run.status == "succeeded"
    assert run.publish_status == "succeeded"
    assert run.hyper_file_path is not None
    import os
    assert os.path.exists(run.hyper_file_path)
    assert flow_ready_to_execute.status == FlowStatus.PUBLISHED.value


def test_execute_flow_rejected_when_not_approved(db, flow_ready_to_execute, monkeypatch):
    flow_ready_to_execute.status = FlowStatus.DRAFT.value
    _patch_source_connector(monkeypatch, FakeConnector())
    _patch_tableau_success(monkeypatch)

    with pytest.raises(DomainError):
        run_service.execute_flow(db, flow_ready_to_execute, actor="shubhanshu@tnqtech.com")


def test_execute_flow_rejected_without_tableau_connection(db, flow_ready_to_execute, monkeypatch):
    flow_ready_to_execute.tableau_connection_id = None
    _patch_source_connector(monkeypatch, FakeConnector())

    with pytest.raises(DomainError):
        run_service.execute_flow(db, flow_ready_to_execute, actor="shubhanshu@tnqtech.com")

    # must never have moved past approved into running if it fails this early
    assert flow_ready_to_execute.status == FlowStatus.APPROVED.value


def test_execute_flow_marks_failed_when_query_validation_fails(db, flow_ready_to_execute, monkeypatch):
    _patch_source_connector(monkeypatch, FakeConnector(explain_fails=True))
    _patch_tableau_success(monkeypatch)

    run = run_service.execute_flow(db, flow_ready_to_execute, actor="shubhanshu@tnqtech.com")

    assert run.status == "failed"
    assert "simulated EXPLAIN failure" in run.error_message
    assert run.publish_status == "not_attempted"  # never got that far
    assert flow_ready_to_execute.status == FlowStatus.FAILED.value


def test_execute_flow_marks_failed_when_publish_fails_but_keeps_hyper_file_path(db, flow_ready_to_execute, monkeypatch):
    _patch_source_connector(monkeypatch, FakeConnector())
    monkeypatch.setattr(run_service, "TableauClient", lambda *a, **k: object())

    def failing_publish(*a, **k):
        raise PublishError("permission denied", retryable=False)

    monkeypatch.setattr(run_service, "publish_or_overwrite", failing_publish)

    run = run_service.execute_flow(db, flow_ready_to_execute, actor="shubhanshu@tnqtech.com")

    assert run.status == "failed"
    assert run.publish_status == "failed"
    assert "permission denied" in run.publish_error
    assert run.hyper_file_path is not None  # the extract itself succeeded
    import os
    assert os.path.exists(run.hyper_file_path)
    assert flow_ready_to_execute.status == FlowStatus.FAILED.value


def test_execute_flow_never_leaves_flow_stuck_in_running(db, flow_ready_to_execute, monkeypatch):
    _patch_source_connector(monkeypatch, FakeConnector(explain_fails=True))
    _patch_tableau_success(monkeypatch)

    run_service.execute_flow(db, flow_ready_to_execute, actor="shubhanshu@tnqtech.com")

    assert flow_ready_to_execute.status in (FlowStatus.PUBLISHED.value, FlowStatus.FAILED.value)
    assert flow_ready_to_execute.status != FlowStatus.RUNNING.value


def test_execute_flow_streams_many_chunks_without_requiring_a_materialized_list(db, flow_ready_to_execute, monkeypatch):
    # 200 chunks x 500 rows = 100,000 rows, produced lazily by a real
    # generator (FakeConnector.run_readonly uses `yield`, never builds a
    # list) - proves the write path handles a result too large to
    # comfortably materialize all at once, not just a single small chunk.
    _patch_source_connector(monkeypatch, FakeConnector(num_chunks=200, rows_per_chunk=500))
    _patch_tableau_success(monkeypatch)

    run = run_service.execute_flow(db, flow_ready_to_execute, actor="shubhanshu@tnqtech.com")

    assert run.status == "succeeded"

    from tableauhyperapi import Connection as HyperConnection, HyperProcess, Telemetry

    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        with HyperConnection(endpoint=hyper.endpoint, database=run.hyper_file_path) as conn:
            count = conn.execute_scalar_query('SELECT COUNT(*) FROM "Extract"."Extract"')

    assert count == 100_000
