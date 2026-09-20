from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Incident, VerificationStatus, User, Role
from app.schemas import VerifyRequest, IncidentOut
from app.auth import require_roles
from app.routers.incidents import _incident_to_out

router = APIRouter(prefix="/incidents", tags=["verification"])


@router.post("/{incident_id}/verify", response_model=IncidentOut)
def verify_incident(
    incident_id: str,
    payload: VerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.verifier, Role.analyst, Role.admin)),
):
    """Human-in-the-loop verification gate. AI-detected incidents stay
    labeled 'AI Detected - Requires Verification' until a verifier,
    analyst, or admin confirms or rejects them here."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = (
        VerificationStatus.verified if payload.approve else VerificationStatus.rejected
    )
    incident.verified_by_id = current_user.id
    db.commit()
    db.refresh(incident)

    return _incident_to_out(incident, db)
