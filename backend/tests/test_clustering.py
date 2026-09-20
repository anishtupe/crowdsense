from datetime import datetime, timedelta

from app.services.duplicate_detection import EvidenceItem
from app.services.clustering import cluster_reports


def make_item(id_, lat, lon, minutes_offset):
    return EvidenceItem(
        id=id_,
        embedding=[],
        latitude=lat,
        longitude=lon,
        reported_at=datetime(2025, 1, 1, 12, 0, 0) + timedelta(minutes=minutes_offset),
    )


def test_nearby_reports_cluster_together():
    items = [
        make_item("a", 28.6139, 77.2090, 0),
        make_item("b", 28.6140, 77.2091, 5),
        make_item("c", 28.6141, 77.2089, 10),
    ]
    labels = cluster_reports(items, eps_meters=750, eps_minutes=180, min_samples=2)
    assert labels[0] == labels[1] == labels[2]
    assert labels[0] != -1


def test_far_apart_reports_do_not_cluster():
    items = [
        make_item("a", 28.6139, 77.2090, 0),
        make_item("b", 40.7128, -74.0060, 0),  # New York — very far from Delhi
    ]
    labels = cluster_reports(items, eps_meters=750, eps_minutes=180, min_samples=2)
    assert labels[0] != labels[1] or labels[0] == -1


def test_single_report_is_noise():
    items = [make_item("solo", 0.0, 0.0, 0)]
    labels = cluster_reports(items)
    assert labels == [-1]


def test_empty_list_returns_empty():
    assert cluster_reports([]) == []
