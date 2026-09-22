from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_actor, get_db
from app.core.errors import DomainError
from app.db.models.flow import Flow
from app.schemas.flow import FlowCreate, FlowRead
from app.schemas.plan import PlanEditRequest, PlanGenerateRequest, PlanRestoreRequest, PlanVersionRead
from app.schemas.run import ApprovePreviewRequest, RunRead
from app.schemas.schedule import ScheduleCreateRequest, ScheduleRead, ScheduleUpdateRequest
from app.services import flow_service, plan_service, run_service, schedule_service

router = APIRouter(prefix="/flows", tags=["flows"])


def _get_flow_or_404(db: Session, flow_id: str) -> Flow:
    flow = db.get(Flow, flow_id)
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


@router.post("", response_model=FlowRead, status_code=201)
def create_flow(
    payload: FlowCreate,
    db: Session = Depends(get_db),
    actor: str = Depends(get_current_actor),
):
    try:
        flow = flow_service.create_flow(db, payload, actor)
        db.commit()
        db.refresh(flow)
        return flow
    except DomainError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", response_model=list[FlowRead])
def list_flows(db: Session = Depends(get_db)):
    return db.query(Flow).order_by(Flow.created_at.desc()).all()


@router.get("/{flow_id}", response_model=FlowRead)
def get_flow(flow_id: str, db: Session = Depends(get_db)):
    return _get_flow_or_404(db, flow_id)


@router.post("/{flow_id}/plan", response_model=PlanVersionRead, status_code=201)
def generate_plan(
    flow_id: str,
    payload: PlanGenerateRequest = PlanGenerateRequest(),
    db: Session = Depends(get_db),
    actor: str = Depends(get_current_actor),
):
    flow = _get_flow_or_404(db, flow_id)
    try:
        version = plan_service.generate_plan_for_flow(db, flow, actor, prompt=payload.prompt)
        db.commit()
        db.refresh(version)
        return plan_service.to_plan_version_read(version)
    except DomainError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{flow_id}/plan", response_model=PlanVersionRead)
def get_active_plan(flow_id: str, db: Session = Depends(get_db)):
    flow = _get_flow_or_404(db, flow_id)
    try:
        version = plan_service.get_active_plan_version(db, flow)
        return plan_service.to_plan_version_read(version)
    except DomainError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{flow_id}/plan", response_model=PlanVersionRead)
def edit_plan(
    flow_id: str,
    payload: PlanEditRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(get_current_actor),
):
    flow = _get_flow_or_404(db, flow_id)
    try:
        version = plan_service.edit_plan(
            db,
            flow,
            payload.plan,
            actor,
            change_summary=payload.change_summary,
            base_version_id=payload.base_version_id,
        )
        db.commit()
        db.refresh(version)
        return plan_service.to_plan_version_read(version)
    except DomainError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{flow_id}/versions", response_model=list[PlanVersionRead])
def list_flow_versions(flow_id: str, db: Session = Depends(get_db)):
    flow = _get_flow_or_404(db, flow_id)
    from app.db.models.plan_version import PlanVersion
    versions = (
        db.query(PlanVersion)
        .filter_by(flow_id=flow.id)
        .order_by(PlanVersion.version_number.desc())
        .all()
    )
    return [plan_service.to_plan_version_read(v) for v in versions]


@router.post("/{flow_id}/restore-version", response_model=PlanVersionRead)
def restore_plan_version(
    flow_id: str,
    payload: PlanRestoreRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(get_current_actor),
):
    flow = _get_flow_or_404(db, flow_id)
    try:
        version = plan_service.restore_version(db, flow, payload.version_id, actor)
        db.commit()
        db.refresh(version)
        return plan_service.to_plan_version_read(version)
    except DomainError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{flow_id}/approve-plan", response_model=PlanVersionRead)
def approve_plan(
    flow_id: str,
    version_id: str | None = None,
    db: Session = Depends(get_db),
    actor: str = Depends(get_current_actor),
):
    flow = _get_flow_or_404(db, flow_id)
    try:
        version = plan_service.approve_plan(db, flow, actor, version_id=version_id)
        db.commit()
        db.refresh(version)
        return plan_service.to_plan_version_read(version)
    except DomainError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{flow_id}/preview", response_model=RunRead, status_code=201)
def preview_flow(
    flow_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(get_current_actor),
):
    flow = _get_flow_or_404(db, flow_id)
    try:
        run = run_service.run_preview(db, flow, actor)
        db.commit()
        db.refresh(run)
        return run_service.to_run_read(run)
    except DomainError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{flow_id}/preview-step")
def preview_step_endpoint(
    flow_id: str,
    alias: str,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    flow = _get_flow_or_404(db, flow_id)
    try:
        rows = run_service.preview_step(db, flow, alias, limit=limit)
        return {"alias": alias, "rows": rows}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc



@router.post("/{flow_id}/approve-preview", response_model=RunRead)
def approve_preview(
    flow_id: str,
    payload: ApprovePreviewRequest = ApprovePreviewRequest(),
    db: Session = Depends(get_db),
    actor: str = Depends(get_current_actor),
):
    flow = _get_flow_or_404(db, flow_id)
    try:
        run = run_service.approve_preview(db, flow, actor, acknowledge_anomaly=payload.acknowledge_anomaly)
        db.commit()
        db.refresh(run)
        return run_service.to_run_read(run)
    except DomainError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{flow_id}/execute", response_model=RunRead, status_code=201)
def execute_flow(
    flow_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(get_current_actor),
):
    flow = _get_flow_or_404(db, flow_id)
    try:
        run = run_service.execute_flow(db, flow, actor)
        db.commit()
        db.refresh(run)
        return run_service.to_run_read(run)
    except DomainError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{flow_id}/schedule", response_model=ScheduleRead, status_code=201)
def set_schedule(
    flow_id: str,
    payload: ScheduleCreateRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(get_current_actor),
):
    flow = _get_flow_or_404(db, flow_id)
    try:
        schedule = schedule_service.create_or_update_schedule(db, flow, payload, actor)
        db.commit()
        db.refresh(schedule)
        return schedule
    except DomainError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{flow_id}/schedule", response_model=ScheduleRead | None)
def get_schedule(flow_id: str, db: Session = Depends(get_db)):
    flow = _get_flow_or_404(db, flow_id)
    schedule = schedule_service.get_schedule(db, flow.id)
    return schedule


@router.patch("/{flow_id}/schedule", response_model=ScheduleRead)
def update_schedule(
    flow_id: str,
    payload: ScheduleUpdateRequest,
    db: Session = Depends(get_db),
):
    flow = _get_flow_or_404(db, flow_id)
    try:
        schedule = schedule_service.update_schedule(db, flow, payload)
        db.commit()
        db.refresh(schedule)
        return schedule
    except DomainError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{flow_id}/schedule", status_code=204)
def delete_schedule(flow_id: str, db: Session = Depends(get_db)):
    flow = _get_flow_or_404(db, flow_id)
    schedule_service.delete_schedule(db, flow.id)
    db.commit()
