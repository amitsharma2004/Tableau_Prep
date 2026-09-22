from __future__ import annotations

import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from app.core.state_machine import FlowStatus
from app.db.base import utcnow
from app.db.models.flow import Flow
from app.db.models.flow_schedule import FlowSchedule
from app.db.models.run import Run
from app.db.session import SessionLocal
from app.services.run_service import execute_flow
from app.services.schedule_service import calculate_next_run

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def process_due_schedules():
    """Polls for due schedules and executes them safely.
    Uses locking/idempotency checks to prevent duplicate runs."""
    db: Session = SessionLocal()
    try:
        now = utcnow()
        # Find enabled schedules where next_run_at <= now
        due_schedules = (
            db.query(FlowSchedule)
            .filter(
                FlowSchedule.enabled == True,
                FlowSchedule.next_run_at != None,
                FlowSchedule.next_run_at <= now,
            )
            .all()
        )

        for sched in due_schedules:
            flow = db.get(Flow, sched.flow_id)
            if flow is None:
                logger.warning("Flow %s for schedule %s not found, skipping.", sched.flow_id, sched.id)
                continue

            # Check flow status - must be APPROVED or PUBLISHED
            if flow.status not in (FlowStatus.APPROVED.value, FlowStatus.PUBLISHED.value):
                logger.warning(
                    "Flow %s status is %s (not approved/published). Skipping scheduled execution.",
                    flow.id, flow.status,
                )
                continue

            scheduled_for = sched.next_run_at

            # Duplicate-execution prevention: Check if a run already exists for this flow & scheduled_for
            existing_run = (
                db.query(Run)
                .filter(
                    Run.flow_id == flow.id,
                    Run.trigger_type == "scheduled",
                    Run.scheduled_for == scheduled_for,
                )
                .first()
            )
            if existing_run:
                logger.info(
                    "Scheduled run for flow %s at %s already exists (run_id=%s). Skipping duplicate.",
                    flow.id, scheduled_for, existing_run.id,
                )
                # Recalculate next run
                sched.next_run_at = calculate_next_run(sched.cron_expression, sched.timezone, now)
                db.commit()
                continue

            # Prevent running if the flow is already in RUNNING state
            running_run = (
                db.query(Run)
                .filter(
                    Run.flow_id == flow.id,
                    Run.status == "running",
                )
                .first()
            )
            if running_run:
                logger.warning(
                    "Flow %s already has an active running run %s. Skipping this trigger.",
                    flow.id, running_run.id,
                )
                sched.next_run_at = calculate_next_run(sched.cron_expression, sched.timezone, now)
                db.commit()
                continue

            # Update next_run_at and last_run_at immediately so no duplicate pickup occurs
            sched.last_run_at = now
            sched.next_run_at = calculate_next_run(sched.cron_expression, sched.timezone, now)
            db.commit()

            # Execute the flow through RunService without calling LLM
            logger.info("Triggering scheduled execution for flow %s (scheduled_for=%s)", flow.id, scheduled_for)
            try:
                run = execute_flow(
                    db,
                    flow,
                    actor=f"scheduler:{sched.created_by}",
                    trigger_type="scheduled",
                    scheduled_for=scheduled_for,
                )
                sched.last_run_status = run.status
                db.commit()
            except Exception as exc:
                logger.exception("Scheduled execution failed for flow %s: %s", flow.id, exc)
                sched.last_run_status = "failed"
                db.commit()

    except Exception as exc:
        logger.exception("Error processing due schedules: %s", exc)
        db.rollback()
    finally:
        db.close()


def start_scheduler():
    if not scheduler.running:
        # Check every 10 seconds for due schedules
        scheduler.add_job(
            process_due_schedules,
            trigger=IntervalTrigger(seconds=10),
            id="process_due_schedules",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.start()
        logger.info("Background flow scheduler started.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background flow scheduler stopped.")
