"""Proves the state machine's failed -> plan_pending_approval and
failed -> preview_pending_approval transitions (declared in
core/state_machine.py since milestone 1) are actually reachable - a flow
whose execute run failed must not be a permanent dead end.
"""
import json

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core import security
from app.core.state_machine import FlowStatus
from app.db.base import Base
from app.db.models.connection import Connection
from app.db.models.flow import Flow
from app.db.models.plan_version import PlanVersion
from app.llm.plan_schema import PlanDraft
from app.services import plan_service, run_service
from tests.test_plan_schema import VALID_PLAN
from tests.test_validators import LIVE_TABLES


class FakeConnector:
    def introspect_schema(self):
        return LIVE_TABLES

    def explain(self, sql, params=None):
        pass

    def count_rows(self, sql, params=None):
        return 10

    def run_readonly(self, sql, params=None, chunksize=50_000):
        import pandas as pd
        yield pd.DataFrame([{"region": "North", "total_revenue": 100.0}])

    def sample_rows(self, table, schema, limit):
        return []


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
def failed_flow(db):
    conn = Connection(name="pg", type="postgres", encrypted_secret=security.encrypt("pw"), created_by="a@b.com")
    db.add(conn)
    db.flush()

    flow = Flow(
        name="f", nl_request="x", source_connection_id=conn.id,
        status=FlowStatus.FAILED.value, created_by="a@b.com",
    )
    db.add(flow)
    db.flush()

    version = PlanVersion(
        flow_id=flow.id, version_number=1, source="llm_generated",
        plan_json=json.dumps(VALID_PLAN), schema_snapshot_json="{}",
    )
    db.add(version)
    db.flush()
    flow.active_plan_version_id = version.id
    db.flush()
    return flow


def test_generate_plan_recovers_a_failed_flow(db, failed_flow, monkeypatch):
    monkeypatch.setattr(plan_service, "build_connector", lambda *a, **k: FakeConnector())
    monkeypatch.setattr(plan_service, "generate_plan", lambda *a, **k: PlanDraft.model_validate(VALID_PLAN))

    plan_service.generate_plan_for_flow(db, failed_flow, actor="a@b.com")

    assert failed_flow.status == FlowStatus.PLAN_PENDING_APPROVAL.value


def test_edit_plan_recovers_a_failed_flow(db, failed_flow):
    edited = PlanDraft.model_validate(VALID_PLAN)
    plan_service.edit_plan(db, failed_flow, edited, actor="a@b.com")

    assert failed_flow.status == FlowStatus.PLAN_PENDING_APPROVAL.value


def test_run_preview_recovers_a_failed_flow_without_editing_the_plan(db, failed_flow, monkeypatch):
    monkeypatch.setattr(run_service, "build_connector", lambda *a, **k: FakeConnector())

    run = run_service.run_preview(db, failed_flow, actor="a@b.com")

    assert run.status == "succeeded"
    assert failed_flow.status == FlowStatus.PREVIEW_PENDING_APPROVAL.value
