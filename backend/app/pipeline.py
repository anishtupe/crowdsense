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

import json
import logging
from datetime import datetime, timedelta
from typing import List

from geoalchemy2.shape import to_shape
from app.utils import safe_to_shape
from sqlalchemy.orm import Session

from app.media import stored_image_bytes
from app.models import Report, Incident, VerificationStatus
from app.services import nlp_service, vision_service
from app.services.duplicate_detection import (
    EvidenceItem, find_duplicates, find_image_duplicates,
)
from app.services.clustering import cluster_reports
from app.services.contradiction_detection import any_contradictions
from app.services.fusion_engine import ImageEvidence, VisionSignals, fuse_evidence
from app.config import settings

logger = logging.getLogger("crowdsense.pipeline")


def _report_to_evidence_item(report: Report) -> EvidenceItem:
    point = safe_to_shape(report.location)
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


def _analyze_media(report: Report) -> None:
    """Fill the report's image_* fields from its uploaded photo. Only photos
    uploaded with the report (stored data URIs) are analysed; links are
    never downloaded."""
    image_bytes = stored_image_bytes(report.media_url)
    if image_bytes is None:
        if report.media_url:
            logger.info("Report %s: media is a link, not analysed", report.id)
        return

    text_label = report.disaster_type
    result = vision_service.analyze_image(image_bytes, text_label=text_label)
    report.image_model = result.model
    report.image_label = result.label
    report.image_scores = json.dumps(result.scores) if result.scores else None
    report.image_embedding = (
        ",".join(str(x) for x in result.embedding) if result.embedding else None
    )
    report.image_text_consistency = result.text_consistency
    report.image_conflict = result.cross_modal_conflict
    report.image_phash = vision_service.compute_phash(image_bytes)

    override = vision_service.image_type_override(text_label, result)
    if override:
        report.disaster_type = override
    logger.info(
        "Report %s vision: model=%s label=%s consistency=%s conflict=%s type %s -> %s%s",
        report.id, result.model, result.label, result.text_consistency,
        result.cross_modal_conflict, text_label, report.disaster_type,
        f" ({result.note})" if result.note else "",
    )


def process_new_report(db: Session, report_id: str) -> None:
    report = db.query(Report).filter(Report.id == report_id).first()
    if report is None:
        logger.warning("Report %s not found; nothing to process", report_id)
        return

    # 1. NLP
    report.disaster_type = nlp_service.classify_disaster_type(report.text)
    report.sentiment = nlp_service.analyze_sentiment(report.text)
    embedding = nlp_service.embed(report.text or "")
    report.embedding = ",".join(str(x) for x in embedding)
    logger.info("Report %s NLP: type=%s sentiment=%s embedding_dim=%d",
                report.id, report.disaster_type, report.sentiment, len(embedding))

    # 2. Vision (uploaded photo only). A vision failure must not lose the
    #    report: log it and continue without image evidence.
    try:
        _analyze_media(report)
    except Exception:
        logger.exception("Report %s: vision analysis failed; continuing without it", report.id)

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

    # Same photo reposted? (perceptual hash, same candidate window)
    image_dups = find_image_duplicates(
        report.image_phash,
        [(r.id, r.image_phash) for r in candidates_q],
        max_distance=settings.VISION_PHASH_MAX_DISTANCE,
    )
    if image_dups:
        report.image_duplicate_of = image_dups[0].candidate_id
        logger.info("Report %s: photo near-duplicate of report %s (%d bits apart)",
                    report.id, image_dups[0].candidate_id, image_dups[0].distance)

    dup_results = find_duplicates(
        new_item,
        candidates,
        text_similarity_threshold=settings.DEDUP_TEXT_SIMILARITY_THRESHOLD,
        distance_threshold_m=settings.DEDUP_DISTANCE_METERS,
        time_window_minutes=settings.DEDUP_TIME_WINDOW_MINUTES,
    )
    duplicate_ids = {r.candidate_id for r in dup_results if r.is_duplicate}
    logger.info("Report %s: %d candidates in window, %d text/space/time duplicates",
                report.id, len(candidates), len(duplicate_ids))

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

    # 6. Evidence fusion (vision terms only when VISION_IN_FUSION; off =
    #    exactly the text/space/time fusion, for the "remove vision" ablation)
    vision = None
    if settings.VISION_IN_FUSION:
        rows = {r.id: r for r in candidates_q}
        rows[report.id] = report
        vision = VisionSignals(
            images=[
                ImageEvidence(
                    report_id=i.id,
                    scores=json.loads(rows[i.id].image_scores) if rows[i.id].image_scores else None,
                    conflict=rows[i.id].image_conflict,
                    phash=rows[i.id].image_phash,
                )
                for i in fused_group
            ],
            phash_max_distance=settings.VISION_PHASH_MAX_DISTANCE,
        )
    result = fuse_evidence(fused_group, has_contradiction=contradiction, vision=vision)

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
    # Flag for verifiers: text-text OR photo-vs-text contradiction. The
    # explanation keeps the two apart.
    incident.has_contradiction = result.has_contradiction or result.cross_modal_conflict
    incident.fusion_explanation = json.dumps(result.explanation)
    incident.updated_at = datetime.utcnow()

    # Point the centroid at the new report's location for simplicity;
    # replace with a true centroid-of-cluster calculation if needed.
    incident.centroid = report.location

    db.query(Report).filter(Report.id.in_(fused_report_ids)).update(
        {Report.incident_id: incident.id}, synchronize_session=False
    )

    db.commit()
    logger.info("Report %s -> incident %s (%d reports, confidence=%.3f, contradiction=%s)",
                report.id, incident.id, len(fused_group), result.confidence,
                incident.has_contradiction)

    # 8. Broadcast — call this from the async route/background task that
    #    invokes process_new_report, since this function itself is sync.
    return incident.id
