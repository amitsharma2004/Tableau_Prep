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
from app.llm.plan_schema import PlanDraft
from app.services import plan_service
from tests.test_plan_schema import VALID_PLAN


class FakeConnector:
    def introspect_schema(self):
        return []

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
def flow(db):
    conn = Connection(
        name="prod-pg",
        type="postgres",
        encrypted_secret=security.encrypt("pw"),
        created_by="shubhanshu@tnqtech.com",
    )
    db.add(conn)
    db.flush()

    f = Flow(
        name="orders-revenue",
        nl_request="join orders and customers, total revenue by region",
        source_connection_id=conn.id,
        status=FlowStatus.DRAFT.value,
        created_by="shubhanshu@tnqtech.com",
    )
    db.add(f)
    db.flush()
    return f


@pytest.fixture(autouse=True)
def fake_connector(monkeypatch):
    monkeypatch.setattr(plan_service, "build_connector", lambda *a, **k: FakeConnector())


@pytest.fixture()
def fake_llm_plan(monkeypatch):
    monkeypatch.setattr(plan_service, "generate_plan", lambda *a, **k: PlanDraft.model_validate(VALID_PLAN))


def test_generate_plan_for_flow_creates_version_and_transitions_flow(db, flow, fake_llm_plan):
    version = plan_service.generate_plan_for_flow(db, flow, actor="shubhanshu@tnqtech.com")

    assert version.version_number == 1
    assert version.source == "llm_generated"
    assert flow.status == FlowStatus.PLAN_PENDING_APPROVAL.value
    assert flow.active_plan_version_id == version.id

    logs = db.query(AuditLog).filter_by(flow_id=flow.id).all()
    assert any(l.event_type == "transitioned_to_plan_pending_approval" for l in logs)


def test_regenerating_plan_creates_a_new_version_number(db, flow, fake_llm_plan):
    v1 = plan_service.generate_plan_for_flow(db, flow, actor="shubhanshu@tnqtech.com")
    v2 = plan_service.generate_plan_for_flow(db, flow, actor="shubhanshu@tnqtech.com")

    assert v1.version_number == 1
    assert v2.version_number == 2
    assert flow.active_plan_version_id == v2.id
    assert db.query(PlanVersion).filter_by(flow_id=flow.id).count() == 2


def test_generate_plan_rejected_when_flow_already_approved(db, flow, fake_llm_plan):
    from app.services.flow_service import move_flow

    move_flow(db, flow, FlowStatus.PLAN_PENDING_APPROVAL, actor="a@b.com")
    move_flow(db, flow, FlowStatus.PLAN_APPROVED, actor="a@b.com")

    with pytest.raises(DomainError):
        plan_service.generate_plan_for_flow(db, flow, actor="shubhanshu@tnqtech.com")


def test_to_plan_version_read_deserializes_plan_json(db, flow, fake_llm_plan):
    version = plan_service.generate_plan_for_flow(db, flow, actor="shubhanshu@tnqtech.com")

    dto = plan_service.to_plan_version_read(version)

    assert dto.plan.output_alias == "result"
    assert dto.version_number == 1


EDITED_PLAN = {
    "summary": "Same as before but only for the North region.",
    "sources": VALID_PLAN["sources"],
    "steps": VALID_PLAN["steps"],
    "output_alias": "result",
}


def test_edit_plan_creates_human_edited_version_and_stays_pending(db, flow, fake_llm_plan):
    v1 = plan_service.generate_plan_for_flow(db, flow, actor="shubhanshu@tnqtech.com")

    edited_draft = PlanDraft.model_validate(EDITED_PLAN)
    v2 = plan_service.edit_plan(db, flow, edited_draft, actor="shubhanshu@tnqtech.com")

    assert v2.version_number == 2
    assert v2.source == "human_edited"
    assert v2.schema_snapshot_json == v1.schema_snapshot_json  # carried forward, not re-fetched
    assert flow.status == FlowStatus.PLAN_PENDING_APPROVAL.value
    assert flow.active_plan_version_id == v2.id


def test_edit_plan_rejected_outside_pending_approval(db, flow):
    edited_draft = PlanDraft.model_validate(EDITED_PLAN)
    with pytest.raises(DomainError):
        plan_service.edit_plan(db, flow, edited_draft, actor="shubhanshu@tnqtech.com")  # flow is still DRAFT


def test_approve_plan_stamps_approver_and_transitions_flow(db, flow, fake_llm_plan):
    version = plan_service.generate_plan_for_flow(db, flow, actor="shubhanshu@tnqtech.com")
    assert version.approved_by is None

    approved = plan_service.approve_plan(db, flow, actor="shubhanshu@tnqtech.com")

    assert approved.id == version.id
    assert approved.approved_by == "shubhanshu@tnqtech.com"
    assert approved.approved_at is not None
    assert flow.status == FlowStatus.PLAN_APPROVED.value


def test_approve_plan_rejected_without_a_pending_plan(db, flow):
    with pytest.raises(DomainError):
        plan_service.approve_plan(db, flow, actor="shubhanshu@tnqtech.com")  # flow is still DRAFT, no plan yet


def test_cannot_approve_plan_twice(db, flow, fake_llm_plan):
    plan_service.generate_plan_for_flow(db, flow, actor="shubhanshu@tnqtech.com")
    plan_service.approve_plan(db, flow, actor="shubhanshu@tnqtech.com")

    with pytest.raises(DomainError):
        plan_service.approve_plan(db, flow, actor="shubhanshu@tnqtech.com")  # already plan_approved, not pending
