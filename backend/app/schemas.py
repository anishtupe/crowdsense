from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


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

    class Config:
        from_attributes = True


class VerifyRequest(BaseModel):
    approve: bool
    note: Optional[str] = None
