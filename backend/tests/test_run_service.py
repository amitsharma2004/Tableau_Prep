import json

import pandas as pd
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core import security
from app.core.errors import DomainError
from app.core.state_machine import FlowStatus
from app.db.base import Base
from app.db.models.audit_log import AuditLog
from app.db.models.connection import Connection
from app.db.models.flow import Flow
from app.db.models.plan_version import PlanVersion
from app.db.models.run import Run
from app.llm.plan_schema import PlanDraft
from app.services import plan_service, run_service
from tests.test_plan_schema import VALID_PLAN
from tests.test_validators import LIVE_TABLES


class FakeConnector:
    def __init__(self, live_tables=LIVE_TABLES, rows_before=100, rows_after=80, explain_fails=False):
        self.live_tables = live_tables
        self.rows_before = rows_before
        self.rows_after = rows_after
        self.explain_fails = explain_fails
        self._count_call = 0

    def introspect_schema(self):
        return self.live_tables

    def explain(self, sql, params=None):
        if self.explain_fails:
            raise RuntimeError("simulated EXPLAIN failure")

    def count_rows(self, sql, params=None):
        self._count_call += 1
        # first call = rows_before (source table), second = rows_after (compiled plan)
        return self.rows_before if self._count_call == 1 else self.rows_after

    def run_readonly(self, sql, params=None, chunksize=50_000):
        yield pd.DataFrame([{"region": "North", "total_revenue": 150.0}])

    def sample_rows(self, table, schema, limit):
        return [{"id": 1, "region": "North"}]


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    monkeypatch.setattr(security.settings, "encryption_key", Fernet.generate_key().decode())


@pytest.fixture()
def flow_with_approved_plan(db):
    conn = Connection(
        name="prod-pg", type="postgres", encrypted_secret=security.encrypt("pw"),
        created_by="shubhanshu@tnqtech.com",
    )
    db.add(conn)
    db.flush()

    f = Flow(
        name="orders-revenue", nl_request="join orders and customers",
        source_connection_id=conn.id, status=FlowStatus.DRAFT.value,
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
    f.status = FlowStatus.PLAN_APPROVED.value
    db.flush()
    return f


def _patch_connector(monkeypatch, connector):
    monkeypatch.setattr(run_service, "build_connector", lambda *a, **k: connector)


def test_run_preview_succeeds_and_moves_to_preview_pending_approval(db, flow_with_approved_plan, monkeypatch):
    connector = FakeConnector(rows_before=100, rows_after=80)
    _patch_connector(monkeypatch, connector)

    run = run_service.run_preview(db, flow_with_approved_plan, actor="shubhanshu@tnqtech.com")

    assert run.status == "succeeded"
    assert run.rows_before == 100
    assert run.rows_after == 80
    assert run.row_count_anomaly is False
    assert run.generated_sql.startswith("WITH ")
    assert flow_with_approved_plan.status == FlowStatus.PREVIEW_PENDING_APPROVAL.value


def test_run_preview_flags_join_blowup_anomaly(db, flow_with_approved_plan, monkeypatch):
    # settings.join_anomaly_ratio defaults to 1.5x; 100 -> 400 is a 4x blow-up
    connector = FakeConnector(rows_before=100, rows_after=400)
    _patch_connector(monkeypatch, connector)

    run = run_service.run_preview(db, flow_with_approved_plan, actor="shubhanshu@tnqtech.com")

    assert run.status == "succeeded"
    assert run.row_count_anomaly is True
    assert flow_with_approved_plan.status == FlowStatus.PREVIEW_PENDING_APPROVAL.value


def test_run_preview_failure_still_transitions_flow_and_records_error(db, flow_with_approved_plan, monkeypatch):
    # A raw driver-level failure (not a DomainError) must still be caught,
    # recorded on the run, and the flow must still move to
    # preview_pending_approval - never left stuck at "running".
    connector = FakeConnector(explain_fails=True)
    _patch_connector(monkeypatch, connector)

    run = run_service.run_preview(db, flow_with_approved_plan, actor="shubhanshu@tnqtech.com")

    assert run.status == "failed"
    assert "simulated EXPLAIN failure" in run.error_message
    assert run.finished_at is not None
    assert flow_with_approved_plan.status == FlowStatus.PREVIEW_PENDING_APPROVAL.value


def test_run_preview_rejected_when_flow_not_plan_approved(db, flow_with_approved_plan, monkeypatch):
    flow_with_approved_plan.status = FlowStatus.DRAFT.value
    _patch_connector(monkeypatch, FakeConnector())

    with pytest.raises(DomainError):
        run_service.run_preview(db, flow_with_approved_plan, actor="shubhanshu@tnqtech.com")


def test_approve_preview_succeeds_and_unlocks_execute(db, flow_with_approved_plan, monkeypatch):
    _patch_connector(monkeypatch, FakeConnector(rows_before=100, rows_after=80))
    run_service.run_preview(db, flow_with_approved_plan, actor="shubhanshu@tnqtech.com")

    approved_run = run_service.approve_preview(db, flow_with_approved_plan, actor="shubhanshu@tnqtech.com")

    assert approved_run.row_count_anomaly is False
    assert flow_with_approved_plan.status == FlowStatus.APPROVED.value


def test_approve_preview_blocked_when_latest_run_failed(db, flow_with_approved_plan, monkeypatch):
    _patch_connector(monkeypatch, FakeConnector(explain_fails=True))
    run_service.run_preview(db, flow_with_approved_plan, actor="shubhanshu@tnqtech.com")

    with pytest.raises(DomainError):
        run_service.approve_preview(db, flow_with_approved_plan, actor="shubhanshu@tnqtech.com")

    assert flow_with_approved_plan.status == FlowStatus.PREVIEW_PENDING_APPROVAL.value


def test_approve_preview_blocked_on_anomaly_unless_acknowledged(db, flow_with_approved_plan, monkeypatch):
    _patch_connector(monkeypatch, FakeConnector(rows_before=100, rows_after=400))
    run_service.run_preview(db, flow_with_approved_plan, actor="shubhanshu@tnqtech.com")

    with pytest.raises(DomainError):
        run_service.approve_preview(db, flow_with_approved_plan, actor="shubhanshu@tnqtech.com")
    assert flow_with_approved_plan.status == FlowStatus.PREVIEW_PENDING_APPROVAL.value

    approved_run = run_service.approve_preview(
        db, flow_with_approved_plan, actor="shubhanshu@tnqtech.com", acknowledge_anomaly=True
    )
    assert approved_run.row_count_anomaly is True
    assert flow_with_approved_plan.status == FlowStatus.APPROVED.value


def test_editing_plan_from_preview_pending_approval_rejects_the_preview(db, flow_with_approved_plan, monkeypatch):
    _patch_connector(monkeypatch, FakeConnector())
    run_service.run_preview(db, flow_with_approved_plan, actor="shubhanshu@tnqtech.com")
    assert flow_with_approved_plan.status == FlowStatus.PREVIEW_PENDING_APPROVAL.value

    edited = PlanDraft.model_validate(VALID_PLAN)
    plan_service.edit_plan(db, flow_with_approved_plan, edited, actor="shubhanshu@tnqtech.com")

    assert flow_with_approved_plan.status == FlowStatus.PLAN_PENDING_APPROVAL.value


def test_approve_preview_rejected_without_any_preview_run(db, flow_with_approved_plan):
    flow_with_approved_plan.status = FlowStatus.PREVIEW_PENDING_APPROVAL.value
    with pytest.raises(DomainError):
        run_service.approve_preview(db, flow_with_approved_plan, actor="shubhanshu@tnqtech.com")
