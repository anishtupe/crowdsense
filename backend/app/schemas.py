import json
from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, EmailStr, field_validator


def _parse_json(value):
    """JSON text columns come out of the DB as strings."""
    if value is None or isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


# ---- Auth -------------------------------------------------------------

class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    role: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Reports ------------------------------------------------------------

class ReportCreate(BaseModel):
    text: Optional[str] = None
    media_url: Optional[str] = None
    latitude: float
    longitude: float
    source: str = "citizen"


class ReportOut(BaseModel):
    id: str
    text: Optional[str]
    media_url: Optional[str]
    source: str
    disaster_type: Optional[str]
    sentiment: Optional[str]
    reported_at: datetime
    incident_id: Optional[str]

    # Image evidence; image_model == "fallback" means no vision evidence.
    image_model: Optional[str] = None
    image_label: Optional[str] = None
    image_scores: Optional[Dict[str, float]] = None
    image_text_consistency: Optional[float] = None
    image_conflict: Optional[bool] = None
    image_phash: Optional[str] = None
    image_duplicate_of: Optional[str] = None

    _scores_from_json = field_validator("image_scores", mode="before")(_parse_json)

    class Config:
        from_attributes = True


# ---- Incidents ------------------------------------------------------------

class IncidentOut(BaseModel):
    id: str
    disaster_type: Optional[str]
    confidence: float
    severity: float
    has_contradiction: bool
    status: str
    created_at: datetime
    updated_at: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    report_count: int = 0
    fusion_explanation: Optional[dict] = None  # every term of the fusion score

    _explanation_from_json = field_validator("fusion_explanation", mode="before")(_parse_json)

    class Config:
        from_attributes = True


class VerifyRequest(BaseModel):
    approve: bool
    note: Optional[str] = None
