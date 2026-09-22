import json

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core import security
from app.core.errors import DomainError
from app.core.state_machine import FlowStatus
from app.db.base import Base
from app.db.models.connection import Connection
from app.db.models.flow import Flow
from app.db.models.plan_version import PlanVersion
from app.services import plan_service
from tests.test_plan_schema import VALID_PLAN


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    monkeypatch.setattr(security.settings, "encryption_key", Fernet.generate_key().decode())


def test_get_active_plan_version_returns_current_plan(db):
    conn = Connection(name="pg", type="postgres", encrypted_secret=security.encrypt("pw"), created_by="a@b.com")
    db.add(conn)
    db.flush()

    flow = Flow(
        name="f", nl_request="x", source_connection_id=conn.id,
        status=FlowStatus.PLAN_PENDING_APPROVAL.value, created_by="a@b.com",
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

    result = plan_service.get_active_plan_version(db, flow)
    assert result.id == version.id


def test_get_active_plan_version_raises_when_no_plan_yet(db):
    conn = Connection(name="pg", type="postgres", encrypted_secret=security.encrypt("pw"), created_by="a@b.com")
    db.add(conn)
    db.flush()
    flow = Flow(name="f", nl_request="x", source_connection_id=conn.id, status=FlowStatus.DRAFT.value, created_by="a@b.com")
    db.add(flow)
    db.flush()

    with pytest.raises(DomainError):
        plan_service.get_active_plan_version(db, flow)
