from typing import List

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.shape import to_shape
from app.utils import safe_to_shape
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Incident, Report
from app.schemas import IncidentOut

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _incident_to_out(incident: Incident, db: Session) -> IncidentOut:
    lat = lon = None
    if incident.centroid is not None:
        point = safe_to_shape(incident.centroid)
        lat, lon = point.y, point.x

    report_count = db.query(Report).filter(Report.incident_id == incident.id).count()

    return IncidentOut(
        id=incident.id,
        disaster_type=incident.disaster_type,
        confidence=incident.confidence,
        severity=incident.severity,
        has_contradiction=incident.has_contradiction,
        status=incident.status.value if hasattr(incident.status, "value") else incident.status,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        latitude=lat,
        longitude=lon,
        report_count=report_count,
    )


@router.get("", response_model=List[IncidentOut])
def list_incidents(db: Session = Depends(get_db), limit: int = 100):
    incidents = db.query(Incident).order_by(Incident.updated_at.desc()).limit(limit).all()
    return [_incident_to_out(i, db) for i in incidents]


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _incident_to_out(incident, db)
