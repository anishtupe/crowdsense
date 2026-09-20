from datetime import datetime

from app.services.duplicate_detection import EvidenceItem
from app.services.fusion_engine import fuse_evidence, logistic_fusion, estimate_severity


def make_item(reliability, disaster_type="flood"):
    return EvidenceItem(
        id="x",
        embedding=[],
        latitude=0.0,
        longitude=0.0,
        reported_at=datetime.utcnow(),
        source_reliability=reliability,
        disaster_type=disaster_type,
    )


def test_more_corroborating_reports_increases_confidence():
    low = logistic_fusion(n_reports=1, mean_reliability=0.5, has_contradiction=False)
    high = logistic_fusion(n_reports=5, mean_reliability=0.5, has_contradiction=False)
    assert high > low


def test_contradiction_decreases_confidence():
    without = logistic_fusion(n_reports=3, mean_reliability=0.7, has_contradiction=False)
    with_contradiction = logistic_fusion(n_reports=3, mean_reliability=0.7, has_contradiction=True)
    assert with_contradiction < without


def test_higher_reliability_increases_confidence():
    low_rel = logistic_fusion(n_reports=3, mean_reliability=0.2, has_contradiction=False)
    high_rel = logistic_fusion(n_reports=3, mean_reliability=0.9, has_contradiction=False)
    assert high_rel > low_rel


def test_confidence_stays_in_unit_interval():
    for n in [0, 1, 10, 100]:
        for rel in [0.0, 0.5, 1.0]:
            for contradiction in [True, False]:
                c = logistic_fusion(n, rel, contradiction)
                assert 0.0 <= c <= 1.0


def test_fuse_evidence_majority_disaster_type():
    reports = [make_item(0.8, "flood"), make_item(0.6, "flood"), make_item(0.5, "fire")]
    result = fuse_evidence(reports, has_contradiction=False)
    assert result.disaster_type == "flood"
    assert result.corroborating_reports == 3


def test_fuse_evidence_empty_list_does_not_crash():
    result = fuse_evidence([], has_contradiction=False)
    assert result.corroborating_reports == 0
    assert 0.0 <= result.confidence <= 1.0


def test_estimate_severity_increases_with_more_reliable_reports():
    few = estimate_severity([make_item(0.9)])
    many = estimate_severity([make_item(0.9), make_item(0.9), make_item(0.9)])
    assert many > few
