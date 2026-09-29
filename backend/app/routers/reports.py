from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy.orm import Session

from app.database import get_db, engine
from app.models import Report, User
from app.schemas import ReportCreate, ReportOut
from app.auth import get_current_user, get_optional_current_user
from app.pipeline import process_new_report
from app.ws.manager import manager
from app.utils import safe_from_shape

router = APIRouter(prefix="/reports", tags=["reports"])


def _report_to_out(report: Report) -> ReportOut:
    return ReportOut.model_validate(report)


@router.post("", response_model=ReportOut)
async def create_report(
    payload: ReportCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    point = safe_from_shape(payload.longitude, payload.latitude, engine)

    report = Report(
        reporter_id=current_user.id if current_user else None,
        text=payload.text,
        media_url=payload.media_url,
        source=payload.source,
        location=point,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # Run the AI pipeline in the background so the citizen gets an
    # immediate response; the dashboard picks up the fused result via
    # the WebSocket broadcast once processing finishes.
    def _run_and_broadcast(report_id: str):
        from app.database import SessionLocal
        session = SessionLocal()
        try:
            incident_id = process_new_report(session, report_id)
        finally:
            session.close()

    background_tasks.add_task(_run_and_broadcast, report.id)

    return _report_to_out(report)


@router.get("", response_model=List[ReportOut])
def list_reports(db: Session = Depends(get_db), limit: int = 50):
    reports = db.query(Report).order_by(Report.reported_at.desc()).limit(limit).all()
    return [_report_to_out(r) for r in reports]
