from datetime import datetime, timedelta

from app.services.duplicate_detection import (
    EvidenceItem,
    find_duplicates,
    haversine_distance_m,
    cosine_similarity,
    find_image_duplicates,
    phash_distance,
)


def make_item(id_, lat, lon, minutes_offset, embedding, reliability=0.7):
    return EvidenceItem(
        id=id_,
        embedding=embedding,
        latitude=lat,
        longitude=lon,
        reported_at=datetime(2025, 1, 1, 12, 0, 0) + timedelta(minutes=minutes_offset),
        source_reliability=reliability,
    )


def test_haversine_zero_distance():
    assert haversine_distance_m(28.6, 77.2, 28.6, 77.2) == 0.0


def test_haversine_known_distance_approx():
    # Roughly 111 km per degree of latitude near the equator/mid-latitudes
    d = haversine_distance_m(0.0, 0.0, 1.0, 0.0)
    assert 110_000 < d < 112_000


def test_cosine_similarity_identical_vectors():
    v = [1.0, 2.0, 3.0]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-9


def test_cosine_similarity_orthogonal_vectors():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_find_duplicates_flags_close_matching_report():
    new_item = make_item("new", 28.6139, 77.2090, 0, [1.0, 0.0, 0.0])
    close_dup = make_item("dup", 28.6140, 77.2091, 5, [1.0, 0.0, 0.0])  # ~15m, 5 min, identical text vec
    far_report = make_item("far", 29.0, 78.0, 5, [1.0, 0.0, 0.0])       # far away
    different_text = make_item("diff", 28.6139, 77.2090, 5, [0.0, 1.0, 0.0])  # same place/time, diff text

    results = find_duplicates(new_item, [close_dup, far_report, different_text])
    by_id = {r.candidate_id: r for r in results}

    assert by_id["dup"].is_duplicate is True
    assert by_id["far"].is_duplicate is False
    assert by_id["diff"].is_duplicate is False


def test_find_duplicates_respects_time_window():
    new_item = make_item("new", 28.6139, 77.2090, 0, [1.0, 0.0, 0.0])
    too_late = make_item("late", 28.6139, 77.2090, 500, [1.0, 0.0, 0.0])  # same place/text, 500 min later

    results = find_duplicates(new_item, [too_late], time_window_minutes=120)
    assert results[0].is_duplicate is False


def test_phash_distance_counts_differing_bits():
    assert phash_distance("0" * 16, "0" * 16) == 0
    assert phash_distance("0" * 16, "f" * 16) == 64
    assert phash_distance("0" * 15 + "1", "0" * 16) == 1


def test_find_image_duplicates_threshold_order_and_missing_hashes():
    new = "0" * 16
    candidates = [
        ("far", "f" * 16),            # 64 bits apart
        ("close", "0" * 15 + "3"),    # 2 bits apart
        ("exact", "0" * 16),          # 0 bits apart
        ("no_image", None),
        ("other_size", "0" * 8),
    ]
    matches = find_image_duplicates(new, candidates, max_distance=8)
    assert [m.candidate_id for m in matches] == ["exact", "close"]
    assert [m.distance for m in matches] == [0, 2]
    assert find_image_duplicates(None, candidates) == []
