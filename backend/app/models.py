import enum
import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Float, Enum, Text, Boolean
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Role(str, enum.Enum):
    citizen = "citizen"
    verifier = "verifier"
    analyst = "analyst"
    admin = "admin"


class VerificationStatus(str, enum.Enum):
    ai_detected = "AI Detected - Requires Verification"
    verified = "Verified"
    rejected = "Rejected"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(Role), default=Role.citizen, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    reports = relationship("Report", back_populates="reporter")


class Report(Base):
    """A single raw observation submitted by a citizen or pulled from a
    public source (news/RSS/social). This is the unit of evidence that
    feeds the Incident Intelligence Engine."""

    __tablename__ = "reports"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    reporter_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    text = Column(Text, nullable=True)
    media_url = Column(String, nullable=True)
    source = Column(String, default="citizen")  # citizen | social | news | historical

    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    reported_at = Column(DateTime, default=datetime.utcnow)

    # Populated by the AI pipeline (see app/pipeline.py)
    disaster_type = Column(String, nullable=True)
    sentiment = Column(String, nullable=True)
    embedding = Column(String, nullable=True)  # JSON-encoded vector; swap for
    # a native pgvector Vector(...) column once pgvector's SQLAlchemy type
    # is wired in — kept as text here to avoid a hard dependency for the
    # starter scaffold.

    source_reliability = Column(Float, default=0.5)  # 0-1, tune per source

    incident_id = Column(UUID(as_uuid=False), ForeignKey("incidents.id"), nullable=True)

    reporter = relationship("User", back_populates="reports")
    incident = relationship("Incident", back_populates="reports")


class Incident(Base):
    """A fused, incident-level representation produced by the Evidence
    Fusion Engine from one or more corroborating (or conflicting) reports."""

    __tablename__ = "incidents"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    disaster_type = Column(String, nullable=True)
    centroid = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)

    confidence = Column(Float, default=0.0)       # calibrated, 0-1
    severity = Column(Float, default=0.0)          # 0-1 (or bucket downstream)
    has_contradiction = Column(Boolean, default=False)

    status = Column(Enum(VerificationStatus), default=VerificationStatus.ai_detected)
    verified_by_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    reports = relationship("Report", back_populates="incident")
