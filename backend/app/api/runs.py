from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.run import Run
from app.schemas.run import RunRead
from app.services.run_service import to_run_read

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=list[RunRead])
def list_runs(flow_id: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Run).order_by(Run.started_at.desc())
    if flow_id:
        query = query.filter_by(flow_id=flow_id)
    return [to_run_read(r) for r in query.all()]


@router.get("/{run_id}", response_model=RunRead)
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return to_run_read(run)
