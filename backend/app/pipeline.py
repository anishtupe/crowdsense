"""
Orchestrates the full path from a new raw report to an updated,
fused incident:

    new report
      -> NLP (classify + embed)
      -> vision (if media attached)
      -> duplicate detection against recent nearby reports
      -> (re)cluster the affected neighborhood
      -> contradiction check within the cluster
      -> evidence fusion -> confidence + severity
      -> upsert Incident row
      -> broadcast update over WebSocket

Run this as a FastAPI BackgroundTask for the starter scaffold; move it to
an ARQ (or Celery) worker once you need it off the request/response cycle
entirely (see the README's "where to take this next" section).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from geoalchemy2.shape import to_shape
from sqlalchemy.orm import Session

from app.models import Report, Incident, VerificationStatus
from app.services import nlp_service, vision_service
from app.services.duplicate_detection import EvidenceItem, find_duplicates
from app.services.clustering import cluster_reports
from app.services.contradiction_detection import any_contradictions
from app.services.fusion_engine import fuse_evidence
from app.config import settings


def _report_to_evidence_item(report: Report) -> EvidenceItem:
    point = to_shape(report.location)
    embedding = [float(x) for x in (report.embedding or "").split(",") if x] \
        if report.embedding else []
    return EvidenceItem(
        id=report.id,
        embedding=embedding,
        latitude=point.y,
        longitude=point.x,
        reported_at=report.reported_at,
        source_reliability=report.source_reliability,
        disaster_type=report.disaster_type,
        text=report.text,
    )


def process_new_report(db: Session, report_id: str) -> None:
    report = db.query(Report).filter(Report.id == report_id).first()
    if report is None:
        return

    # 1. NLP
    report.disaster_type = nlp_service.classify_disaster_type(report.text)
    report.sentiment = nlp_service.analyze_sentiment(report.text)
    embedding = nlp_service.embed(report.text or "")
    report.embedding = ",".join(str(x) for x in embedding)

    # 2. Vision (if media attached)
    if report.media_url:
        vision_label = vision_service.classify_image(report.media_url)
        if vision_label and report.disaster_type == "unclassified":
            report.disaster_type = vision_label

    db.commit()
    db.refresh(report)

    # 3. Pull recent nearby reports of the same (candidate) disaster type
    #    as duplicate/cluster candidates. This window is intentionally
    #    generous; find_duplicates / cluster_reports apply the real
    #    space+time+text thresholds.
    window_start = report.reported_at - timedelta(hours=6)
    candidates_q = (
        db.query(Report)
        .filter(Report.id != report.id)
        .filter(Report.reported_at >= window_start)
        .all()
    )
    candidates = [_report_to_evidence_item(r) for r in candidates_q if r.location is not None]
    new_item = _report_to_evidence_item(report)

    dup_results = find_duplicates(
        new_item,
        candidates,
        text_similarity_threshold=settings.DEDUP_TEXT_SIMILARITY_THRESHOLD,
        distance_threshold_m=settings.DEDUP_DISTANCE_METERS,
        time_window_minutes=settings.DEDUP_TIME_WINDOW_MINUTES,
    )
    duplicate_ids = {r.candidate_id for r in dup_results if r.is_duplicate}

    # 4. Cluster this report together with its duplicates/neighbors
    cluster_items = [new_item] + [c for c in candidates if c.id in duplicate_ids]
    labels = cluster_reports(
        cluster_items,
        eps_meters=settings.CLUSTER_EPS_METERS,
        eps_minutes=settings.CLUSTER_EPS_MINUTES,
        min_samples=settings.CLUSTER_MIN_SAMPLES,
    )

    # New report's own label is labels[0]; if it's noise (-1), treat it as
    # a fresh, single-report incident candidate instead of dropping it.
    own_label = labels[0]
    if own_label == -1:
        fused_group = [new_item]
    else:
        fused_group = [item for item, lbl in zip(cluster_items, labels) if lbl == own_label]

    # 5. Contradiction check within the fused group
    contradiction = any_contradictions([(i.id, i.text) for i in fused_group])

    # 6. Evidence fusion
    result = fuse_evidence(fused_group, has_contradiction=contradiction)

    # 7. Upsert the Incident: reuse an existing incident if any fused
    #    report already belongs to one, otherwise create a new one.
    fused_report_ids = [i.id for i in fused_group]
    existing_incident = (
        db.query(Incident)
        .join(Report, Report.incident_id == Incident.id)
        .filter(Report.id.in_(fused_report_ids))
        .first()
    )

    if existing_incident:
        incident = existing_incident
    else:
        incident = Incident(status=VerificationStatus.ai_detected)
        db.add(incident)
        db.flush()

    incident.disaster_type = result.disaster_type
    incident.confidence = result.confidence
    incident.severity = result.severity
    incident.has_contradiction = result.has_contradiction
    incident.updated_at = datetime.utcnow()

    # Point the centroid at the new report's location for simplicity;
    # replace with a true centroid-of-cluster calculation if needed.
    incident.centroid = report.location

    db.query(Report).filter(Report.id.in_(fused_report_ids)).update(
        {Report.incident_id: incident.id}, synchronize_session=False
    )

    db.commit()

    # 8. Broadcast — call this from the async route/background task that
    #    invokes process_new_report, since this function itself is sync.
    return incident.id
