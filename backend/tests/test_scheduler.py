from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.errors import DomainError
from app.core.state_machine import FlowStatus
from app.db.base import Base
from app.db.models.flow import Flow
from app.db.models.flow_schedule import FlowSchedule
from app.db.models.plan_version import PlanVersion
from app.db.models.run import Run
from app.schemas.schedule import ScheduleCreateRequest, ScheduleUpdateRequest
from app.services.schedule_service import (
    calculate_next_run,
    create_or_update_schedule,
    get_schedule,
    update_schedule,
    delete_schedule,
)
from app.services.scheduler_worker import process_due_schedules


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_cron_and_next_run_calculation():
    # 5 AM IST every day -> 23:30 UTC previous day
    start_utc = datetime(2026, 9, 21, 0, 0, 0, tzinfo=timezone.utc)
    next_run = calculate_next_run("0 5 * * *", "Asia/Kolkata", start_utc)
    assert next_run is not None
    # 5 AM Asia/Kolkata is 23:30 UTC previous day
    assert next_run.hour == 23
    assert next_run.minute == 30


def test_cannot_schedule_unapproved_flow(memory_db):
    flow = Flow(
        id="flow_draft",
        name="Draft Flow",
        nl_request="Filter orders",
        source_connection_id="conn_1",
        status=FlowStatus.DRAFT.value,
        created_by="tester",
    )
    memory_db.add(flow)
    memory_db.commit()

    req = ScheduleCreateRequest(cron_expression="0 5 * * *", timezone="Asia/Kolkata")
    with pytest.raises(DomainError, match="must be approved before scheduling"):
        create_or_update_schedule(memory_db, flow, req, "tester")


def test_schedule_approved_flow(memory_db):
    plan_ver = PlanVersion(
        id="plan_v1",
        flow_id="flow_appr",
        version_number=1,
        source="llm_generated",
        plan_json='{"sources": [], "steps": [], "output_alias": "out"}',
        schema_snapshot_json="{}",
    )
    flow = Flow(
        id="flow_appr",
        name="Approved Flow",
        nl_request="Filter orders",
        source_connection_id="conn_1",
        status=FlowStatus.APPROVED.value,
        active_plan_version_id=plan_ver.id,
        created_by="tester",
    )
    memory_db.add_all([plan_ver, flow])
    memory_db.commit()

    req = ScheduleCreateRequest(cron_expression="0 5 * * *", timezone="Asia/Kolkata")
    schedule = create_or_update_schedule(memory_db, flow, req, "tester")
    memory_db.commit()

    assert schedule.flow_id == "flow_appr"
    assert schedule.plan_version_id == "plan_v1"
    assert schedule.enabled is True
    assert schedule.next_run_at is not None

    # Retrieve
    fetched = get_schedule(memory_db, "flow_appr")
    assert fetched is not None
    assert fetched.cron_expression == "0 5 * * *"

    # Disable schedule
    updated = update_schedule(memory_db, flow, ScheduleUpdateRequest(enabled=False))
    memory_db.commit()
    assert updated.enabled is False
    assert updated.next_run_at is None

    # Re-enable schedule
    updated2 = update_schedule(memory_db, flow, ScheduleUpdateRequest(enabled=True))
    memory_db.commit()
    assert updated2.enabled is True
    assert updated2.next_run_at is not None

    # Delete schedule
    delete_schedule(memory_db, flow.id)
    memory_db.commit()
    assert get_schedule(memory_db, flow.id) is None
