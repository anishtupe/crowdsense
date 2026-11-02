"""
Duplicate detection — core research component.

Given a new report, decide whether it's describing the same real-world
event as an existing report/incident, by combining:
  - text/embedding similarity  (cosine similarity of report embeddings)
  - spatial proximity          (haversine distance in meters)
  - temporal proximity         (minutes between reports)

Kept as pure functions with no DB/network dependency so they're easy to
unit-test and to ablate independently for your experiments (this is the
"duplicate detection" component in the ablation study from the project
report).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence


EARTH_RADIUS_M = 6_371_000.0


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in meters."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class EvidenceItem:
    """Minimal view of a report needed for duplicate/cluster/fusion logic.
    Build one of these from a `Report` ORM row before calling into these
    pure functions — keeps the research logic decoupled from the DB layer."""

    id: str
    embedding: Sequence[float]
    latitude: float
    longitude: float
    reported_at: datetime
    source_reliability: float = 0.5
    disaster_type: Optional[str] = None
    text: Optional[str] = None


@dataclass
class SimilarityResult:
    candidate_id: str
    text_similarity: float
    distance_m: float
    minutes_apart: float
    is_duplicate: bool


def find_duplicates(
    new_item: EvidenceItem,
    candidates: List[EvidenceItem],
    text_similarity_threshold: float = 0.82,
    distance_threshold_m: float = 500.0,
    time_window_minutes: float = 120.0,
) -> List[SimilarityResult]:
    """Return similarity results for every candidate, flagging which ones
    count as duplicates under the given thresholds.

    A candidate is a duplicate only if it passes ALL three checks
    (text, space, time) — tune the thresholds via Settings / your
    ablation experiments rather than hardcoding new values here.
    """
    results: List[SimilarityResult] = []

    for cand in candidates:
        text_sim = cosine_similarity(new_item.embedding, cand.embedding)
        dist_m = haversine_distance_m(
            new_item.latitude, new_item.longitude, cand.latitude, cand.longitude
        )
        minutes_apart = abs((new_item.reported_at - cand.reported_at).total_seconds()) / 60.0

        is_dup = (
            text_sim >= text_similarity_threshold
            and dist_m <= distance_threshold_m
            and minutes_apart <= time_window_minutes
        )

        results.append(
            SimilarityResult(
                candidate_id=cand.id,
                text_similarity=text_sim,
                distance_m=dist_m,
                minutes_apart=minutes_apart,
                is_duplicate=is_dup,
            )
        )

    return results


# ---- Near-duplicate images (same photo reposted) --------------------------

def phash_distance(a: str, b: str) -> int:
    """Hamming distance (number of differing bits) between two hex-encoded
    perceptual hashes of the same length."""
    return bin(int(a, 16) ^ int(b, 16)).count("1")


@dataclass
class ImageDuplicateResult:
    candidate_id: str
    distance: int


def find_image_duplicates(
    new_hash: Optional[str],
    candidates: List[tuple[str, Optional[str]]],
    max_distance: int = 8,
) -> List[ImageDuplicateResult]:
    """candidates: list of (report_id, image_hash). Returns the candidates
    whose hash is within `max_distance` bits of `new_hash`, closest first.
    A missing hash on either side (no image, or no Pillow) never matches."""
    if not new_hash:
        return []
    matches: List[ImageDuplicateResult] = []
    for cand_id, cand_hash in candidates:
        if not cand_hash or len(cand_hash) != len(new_hash):
            continue
        dist = phash_distance(new_hash, cand_hash)
        if dist <= max_distance:
            matches.append(ImageDuplicateResult(candidate_id=cand_id, distance=dist))
    matches.sort(key=lambda m: m.distance)
    return matches
