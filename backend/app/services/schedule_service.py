from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from croniter import croniter
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.core.state_machine import FlowStatus
from app.db.base import utcnow
from app.db.models.flow import Flow
from app.db.models.flow_schedule import FlowSchedule
from app.db.models.plan_version import PlanVersion
from app.schemas.schedule import ScheduleCreateRequest, ScheduleUpdateRequest


def calculate_next_run(cron_expr: str, tz_name: str, start_time: datetime | None = None) -> datetime:
    """Calculates the next run time given a cron expression and timezone.
    Always returns UTC datetime."""
    tz = ZoneInfo(tz_name)
    if start_time is None:
        start_time = utcnow()
    
    # Convert start_time to the target timezone
    local_start = start_time.astimezone(tz)
    iter = croniter(cron_expr, local_start)
    next_local = iter.get_next(datetime)
    # Ensure timezone is set and convert back to UTC
    if next_local.tzinfo is None:
        next_local = next_local.replace(tzinfo=tz)
    return next_local.astimezone(ZoneInfo("UTC"))


def get_schedule(db: Session, flow_id: str) -> FlowSchedule | None:
    return db.query(FlowSchedule).filter_by(flow_id=flow_id).first()


def create_or_update_schedule(
    db: Session,
    flow: Flow,
    req: ScheduleCreateRequest,
    actor: str,
) -> FlowSchedule:
    """Only an APPROVED or PUBLISHED flow can be scheduled."""
    current_status = FlowStatus(flow.status)
    if current_status not in (FlowStatus.APPROVED, FlowStatus.PUBLISHED):
        raise DomainError(
            f"Cannot schedule flow in status '{flow.status}'. The flow must be approved before scheduling."
        )

    if not flow.active_plan_version_id:
        raise DomainError("Flow has no active approved plan version to schedule.")

    # Validate active plan exists
    plan_ver = db.get(PlanVersion, flow.active_plan_version_id)
    if plan_ver is None:
        raise DomainError("Flow active plan version does not exist.")

    next_run = calculate_next_run(req.cron_expression, req.timezone) if req.enabled else None

    schedule = get_schedule(db, flow.id)
    if schedule is None:
        schedule = FlowSchedule(
            flow_id=flow.id,
            plan_version_id=flow.active_plan_version_id,
            enabled=req.enabled,
            cron_expression=req.cron_expression,
            timezone=req.timezone,
            next_run_at=next_run,
            created_by=actor,
        )
        db.add(schedule)
    else:
        schedule.plan_version_id = flow.active_plan_version_id
        schedule.enabled = req.enabled
        schedule.cron_expression = req.cron_expression
        schedule.timezone = req.timezone
        schedule.next_run_at = next_run

    db.flush()
    return schedule


def update_schedule(
    db: Session,
    flow: Flow,
    req: ScheduleUpdateRequest,
) -> FlowSchedule:
    schedule = get_schedule(db, flow.id)
    if schedule is None:
        raise DomainError(f"No schedule found for flow {flow.id}")

    if req.cron_expression is not None:
        schedule.cron_expression = req.cron_expression
    if req.timezone is not None:
        schedule.timezone = req.timezone
    if req.enabled is not None:
        schedule.enabled = req.enabled

    # Always lock to current active plan version on update
    if flow.active_plan_version_id:
        schedule.plan_version_id = flow.active_plan_version_id

    if schedule.enabled:
        schedule.next_run_at = calculate_next_run(schedule.cron_expression, schedule.timezone)
    else:
        schedule.next_run_at = None

    db.flush()
    return schedule


def delete_schedule(db: Session, flow_id: str) -> None:
    schedule = get_schedule(db, flow_id)
    if schedule:
        db.delete(schedule)
        db.flush()
