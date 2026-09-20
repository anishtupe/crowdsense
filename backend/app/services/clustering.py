"""
Geospatial-temporal clustering — core research component.

Groups individual reports into incident candidates using a DBSCAN variant
over a combined space+time distance metric (a simplified stand-in for
ST-DBSCAN — swap in a dedicated ST-DBSCAN implementation if your
evaluation needs the full algorithm).

Pure function, no DB dependency: pass in a list of EvidenceItem and get
back cluster labels (-1 = noise / not part of any cluster, same as
scikit-learn's DBSCAN convention).
"""
from __future__ import annotations

from typing import List

import numpy as np
from sklearn.cluster import DBSCAN

from app.services.duplicate_detection import EvidenceItem, haversine_distance_m


def _combined_distance(a: EvidenceItem, b: EvidenceItem, minutes_to_meters: float) -> float:
    """Combine spatial distance (meters) and temporal distance (minutes,
    rescaled to meters via `minutes_to_meters`) into one scalar so plain
    DBSCAN can be used. `minutes_to_meters` should be set so that your
    `eps` value in meters roughly matches your intended time window —
    see `cluster_reports` for how eps and this scale factor relate.
    """
    spatial = haversine_distance_m(a.latitude, a.longitude, b.latitude, b.longitude)
    minutes_apart = abs((a.reported_at - b.reported_at).total_seconds()) / 60.0
    temporal_as_meters = minutes_apart * minutes_to_meters
    return float(np.hypot(spatial, temporal_as_meters))


def cluster_reports(
    items: List[EvidenceItem],
    eps_meters: float = 750.0,
    eps_minutes: float = 180.0,
    min_samples: int = 2,
) -> List[int]:
    """Returns a list of cluster labels, one per item, in the same order
    as `items`. -1 means the report didn't join any cluster.
    """
    n = len(items)
    if n == 0:
        return []
    if n == 1:
        return [-1]  # a single report never forms a cluster on its own

    # Scale factor so that `eps_minutes` of time separation contributes
    # about as much to the combined distance as `eps_meters` of space —
    # i.e. eps_minutes minutes ~= eps_meters meters in the combined metric.
    minutes_to_meters = eps_meters / max(eps_minutes, 1e-6)

    dist_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d = _combined_distance(items[i], items[j], minutes_to_meters)
            dist_matrix[i, j] = d
            dist_matrix[j, i] = d

    model = DBSCAN(eps=eps_meters, min_samples=min_samples, metric="precomputed")
    labels = model.fit_predict(dist_matrix)
    return labels.tolist()
