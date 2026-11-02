"""
Evidence Fusion Engine — core research component.

Combines per-report signals (source reliability, duplicate-corroboration
count, presence of contradiction, disaster-type agreement) into a single,
calibrated incident-level confidence score plus a severity estimate.

Kept intentionally simple and fully inspectable (every intermediate term
is returned, not just the final number) — this is what makes ablation
studies possible: turn any one input off and see how much the score moves.

Swap `logistic_fusion` for a trained/calibrated model once you have
labeled outcome data; the public function signature (`fuse_evidence`)
should stay the same either way.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.services.duplicate_detection import EvidenceItem, find_image_duplicates

NO_INCIDENT_LABEL = "no_incident"  # same value as vision_service.NO_INCIDENT_LABEL

# Hand-set, UNTUNED weights for the optional vision terms (w4, w5).
DEFAULT_WEIGHTS = {"w0": -1.0, "w1": 1.1, "w2": 1.8, "w3": -2.2, "w4": 0.8, "w5": -1.2}


@dataclass
class FusionResult:
    confidence: float                 # calibrated, in [0, 1]
    severity: float                   # in [0, 1]
    has_contradiction: bool
    corroborating_reports: int
    mean_source_reliability: float
    disaster_type: Optional[str]
    explanation: dict = field(default_factory=dict)
    cross_modal_conflict: bool = False  # a photo contradicts its report's text


@dataclass
class ImageEvidence:
    """Image evidence for one report in the fused group (pure data)."""
    report_id: str
    scores: Optional[Dict[str, float]] = None  # None = no vision evidence (fallback / no photo)
    conflict: Optional[bool] = None            # photo contradicts the report's own text
    phash: Optional[str] = None


@dataclass
class VisionSignals:
    """Optional vision input to `fuse_evidence`. The two flags exist so each
    vision effect can be switched off on its own in ablation runs."""
    images: List[ImageEvidence]
    use_scores: bool = True        # vision_support + cross-modal conflict terms
    use_image_dedup: bool = True   # a reposted photo is not extra corroboration
    phash_max_distance: int = 8


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def logistic_fusion(
    n_reports: int,
    mean_reliability: float,
    has_contradiction: bool,
    weights: Optional[dict] = None,
    vision_support: float = 0.0,
    cross_modal_conflict: bool = False,
) -> float:
    """A small, fully transparent logistic model — deliberately simple
    (closed-form, a few coefficients) so it's easy to write out as
    equations in a paper and easy to unit test.

    confidence = sigmoid(
        w0
        + w1 * log(1 + n_reports)          -- more corroborating reports helps
        + w2 * mean_reliability             -- more reliable sources helps
        + w3 * (1 if has_contradiction else 0)   -- contradiction hurts
        + w4 * vision_support               -- photos showing the incident help (optional)
        + w5 * (1 if cross_modal_conflict else 0) -- photo contradicts text hurts (optional)
    )
    With the vision arguments at their defaults the last two terms are 0.
    """
    w = weights or DEFAULT_WEIGHTS

    z = (
        w["w0"]
        + w["w1"] * math.log1p(n_reports)
        + w["w2"] * mean_reliability
        + w["w3"] * (1.0 if has_contradiction else 0.0)
    )
    if vision_support or cross_modal_conflict:
        z += w.get("w4", 0.0) * vision_support
        z += w.get("w5", 0.0) * (1.0 if cross_modal_conflict else 0.0)
    return _sigmoid(z)


def _count_reposted_photos(images: List[ImageEvidence], max_distance: int) -> int:
    """How many photos in the group are near-identical (perceptual hash) to
    an earlier report's photo. Each such report is not independent
    corroboration."""
    reposts = 0
    seen: List[tuple] = []
    for img in images:
        if find_image_duplicates(img.phash, seen, max_distance=max_distance):
            reposts += 1
        elif img.phash:
            seen.append((img.report_id, img.phash))
    return reposts


def _vision_support(images: List[ImageEvidence], disaster_type: Optional[str]) -> tuple:
    """Mean over reports WITH model scores of
        P(fused disaster type) - P(no incident)     (in [-1, 1]).
    If the fused type is unknown, P(any disaster type) is used instead.
    Reports without scores (fallback / no photo) are left out, so a missing
    model never counts as negative evidence. Returns (support, n_scored)."""
    values = []
    for img in images:
        if img.scores is None:
            continue
        p_none = img.scores.get(NO_INCIDENT_LABEL, 0.0)
        if disaster_type in img.scores and disaster_type != NO_INCIDENT_LABEL:
            p_support = img.scores[disaster_type]
        else:
            p_support = 1.0 - p_none
        values.append(p_support - p_none)
    return (sum(values) / len(values) if values else 0.0), len(values)


def estimate_severity(reports: List[EvidenceItem]) -> float:
    """Placeholder severity heuristic: more corroborating reports from more
    reliable sources -> higher assumed severity. Replace with your trained
    severity model; keep it returning a float in [0, 1]."""
    if not reports:
        return 0.0
    reliability_weighted_count = sum(r.source_reliability for r in reports)
    # Squash with a simple saturating function so severity doesn't grow
    # unboundedly with report count.
    return 1.0 - math.exp(-reliability_weighted_count / 3.0)


def fuse_evidence(
    reports: List[EvidenceItem],
    has_contradiction: bool,
    vision: Optional[VisionSignals] = None,
) -> FusionResult:
    """Given the set of reports assigned to one incident candidate (e.g.
    one cluster from `clustering.py`), produce the fused incident-level
    result. With `vision=None` (the default) the result is exactly the
    text/space/time-only fusion."""
    n = len(reports)
    mean_reliability = (
        sum(r.source_reliability for r in reports) / n if n > 0 else 0.0
    )

    # Majority-vote disaster type among the fused reports
    disaster_type = None
    if reports:
        type_counts: dict = {}
        for r in reports:
            if r.disaster_type:
                type_counts[r.disaster_type] = type_counts.get(r.disaster_type, 0) + 1
        if type_counts:
            disaster_type = max(type_counts, key=type_counts.get)

    explanation = {
        "n_reports": n,
        "mean_source_reliability": mean_reliability,
        "has_contradiction": has_contradiction,
    }

    n_effective = n
    vision_support = 0.0
    cross_modal_conflict = False
    if vision is not None:
        n_scored = 0
        if vision.use_image_dedup:
            n_effective = n - _count_reposted_photos(vision.images, vision.phash_max_distance)
        if vision.use_scores:
            vision_support, n_scored = _vision_support(vision.images, disaster_type)
            cross_modal_conflict = any(
                img.conflict is True for img in vision.images if img.scores is not None
            )
        explanation.update({
            "n_effective_reports": n_effective,
            "vision_support": vision_support,
            "cross_modal_conflict": cross_modal_conflict,
            "n_vision_scored": n_scored,
            "use_vision_scores": vision.use_scores,
            "use_image_dedup": vision.use_image_dedup,
            "vision_weights": {"w4": DEFAULT_WEIGHTS["w4"], "w5": DEFAULT_WEIGHTS["w5"]},
            "vision_weights_untuned": True,
        })

    confidence = logistic_fusion(
        n_reports=n_effective,
        mean_reliability=mean_reliability,
        has_contradiction=has_contradiction,
        vision_support=vision_support,
        cross_modal_conflict=cross_modal_conflict,
    )
    severity = estimate_severity(reports)

    return FusionResult(
        confidence=confidence,
        severity=severity,
        has_contradiction=has_contradiction,
        corroborating_reports=n,
        mean_source_reliability=mean_reliability,
        disaster_type=disaster_type,
        explanation=explanation,
        cross_modal_conflict=cross_modal_conflict,
    )
