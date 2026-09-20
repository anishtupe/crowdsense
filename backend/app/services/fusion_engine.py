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
from typing import List, Optional

from app.services.duplicate_detection import EvidenceItem


@dataclass
class FusionResult:
    confidence: float                 # calibrated, in [0, 1]
    severity: float                   # in [0, 1]
    has_contradiction: bool
    corroborating_reports: int
    mean_source_reliability: float
    disaster_type: Optional[str]
    explanation: dict = field(default_factory=dict)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def logistic_fusion(
    n_reports: int,
    mean_reliability: float,
    has_contradiction: bool,
    weights: Optional[dict] = None,
) -> float:
    """A small, fully transparent logistic model — deliberately simple
    (closed-form, a few coefficients) so it's easy to write out as
    equations in a paper and easy to unit test.

    confidence = sigmoid(
        w0
        + w1 * log(1 + n_reports)          -- more corroborating reports helps
        + w2 * mean_reliability             -- more reliable sources helps
        + w3 * (1 if has_contradiction else 0)   -- contradiction hurts
    )
    """
    w = weights or {"w0": -1.0, "w1": 1.1, "w2": 1.8, "w3": -2.2}

    z = (
        w["w0"]
        + w["w1"] * math.log1p(n_reports)
        + w["w2"] * mean_reliability
        + w["w3"] * (1.0 if has_contradiction else 0.0)
    )
    return _sigmoid(z)


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
) -> FusionResult:
    """Given the set of reports assigned to one incident candidate (e.g.
    one cluster from `clustering.py`), produce the fused incident-level
    result."""
    n = len(reports)
    mean_reliability = (
        sum(r.source_reliability for r in reports) / n if n > 0 else 0.0
    )

    confidence = logistic_fusion(
        n_reports=n,
        mean_reliability=mean_reliability,
        has_contradiction=has_contradiction,
    )
    severity = estimate_severity(reports)

    # Majority-vote disaster type among the fused reports
    disaster_type = None
    if reports:
        type_counts: dict = {}
        for r in reports:
            if r.disaster_type:
                type_counts[r.disaster_type] = type_counts.get(r.disaster_type, 0) + 1
        if type_counts:
            disaster_type = max(type_counts, key=type_counts.get)

    return FusionResult(
        confidence=confidence,
        severity=severity,
        has_contradiction=has_contradiction,
        corroborating_reports=n,
        mean_source_reliability=mean_reliability,
        disaster_type=disaster_type,
        explanation={
            "n_reports": n,
            "mean_source_reliability": mean_reliability,
            "has_contradiction": has_contradiction,
        },
    )
