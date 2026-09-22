import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.errors import IllegalTransitionError
from app.core.state_machine import FlowStatus
from app.db.base import Base
from app.db.models.connection import Connection
from app.db.models.flow import Flow
from app.services.flow_service import move_flow


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def flow(db):
    conn = Connection(
        name="test-pg",
        type="postgres",
        encrypted_secret=b"irrelevant-for-this-test",
        created_by="shubhanshu@tnqtech.com",
    )
    db.add(conn)
    db.flush()

    f = Flow(
        name="test flow",
        nl_request="join orders and customers",
        source_connection_id=conn.id,
        status=FlowStatus.DRAFT.value,
        created_by="shubhanshu@tnqtech.com",
    )
    db.add(f)
    db.flush()
    return f


def test_move_flow_updates_status_and_writes_audit_log(db, flow):
    move_flow(db, flow, FlowStatus.PLAN_PENDING_APPROVAL, actor="shubhanshu@tnqtech.com")

    assert flow.status == FlowStatus.PLAN_PENDING_APPROVAL.value

    from app.db.models.audit_log import AuditLog

    logs = db.query(AuditLog).filter_by(flow_id=flow.id).all()
    assert len(logs) == 1
    assert logs[0].event_type == "transitioned_to_plan_pending_approval"
    assert logs[0].actor == "shubhanshu@tnqtech.com"


def test_move_flow_rejects_illegal_transition(db, flow):
    with pytest.raises(IllegalTransitionError):
        move_flow(db, flow, FlowStatus.RUNNING, actor="shubhanshu@tnqtech.com")

    # status must be unchanged and no audit row written on rejection
    assert flow.status == FlowStatus.DRAFT.value
    from app.db.models.audit_log import AuditLog

    assert db.query(AuditLog).filter_by(flow_id=flow.id).count() == 0
