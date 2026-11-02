import math
from datetime import datetime

import pytest

from app.services.duplicate_detection import EvidenceItem
from app.services.fusion_engine import (
    DEFAULT_WEIGHTS,
    ImageEvidence,
    VisionSignals,
    fuse_evidence,
    logistic_fusion,
)

LABELS = ("flood", "fire", "earthquake", "storm", "landslide", "accident", "no_incident")


def _item(id_, reliability=0.7, disaster_type="flood"):
    return EvidenceItem(id=id_, embedding=[1.0], latitude=19.0, longitude=72.8,
                        reported_at=datetime(2026, 1, 1), source_reliability=reliability,
                        disaster_type=disaster_type)


def _scores(**probs):
    rest = [l for l in LABELS if l not in probs]
    share = (1.0 - sum(probs.values())) / len(rest)
    return {l: probs.get(l, share) for l in LABELS}


def _original_confidence(n, mean_reliability, contradiction):
    """The fusion formula exactly as it was before vision existed."""
    z = -1.0 + 1.1 * math.log1p(n) + 1.8 * mean_reliability + -2.2 * (1.0 if contradiction else 0.0)
    return 1.0 / (1.0 + math.exp(-z))


REPORTS = [_item("a", 0.7), _item("b", 0.5), _item("c", 0.9)]


@pytest.mark.parametrize("contradiction", [False, True])
def test_no_vision_is_exactly_the_original_fusion(contradiction):
    result = fuse_evidence(REPORTS, has_contradiction=contradiction)
    assert result.confidence == _original_confidence(3, (0.7 + 0.5 + 0.9) / 3, contradiction)
    assert set(result.explanation) == {"n_reports", "mean_source_reliability", "has_contradiction"}
    assert result.cross_modal_conflict is False


def test_fallback_images_change_nothing():
    """model="fallback" -> scores None: no vision evidence, not negative evidence."""
    vision = VisionSignals(images=[ImageEvidence(r.id) for r in REPORTS])
    with_fallback = fuse_evidence(REPORTS, False, vision=vision)
    without = fuse_evidence(REPORTS, False)
    assert with_fallback.confidence == without.confidence
    assert with_fallback.explanation["n_vision_scored"] == 0
    assert with_fallback.explanation["vision_support"] == 0.0


def test_supporting_photos_raise_and_no_incident_photos_lower_confidence():
    base = fuse_evidence(REPORTS, False).confidence
    support = VisionSignals(images=[ImageEvidence("a", scores=_scores(flood=0.8))])
    against = VisionSignals(images=[ImageEvidence("a", scores=_scores(no_incident=0.8))])
    up = fuse_evidence(REPORTS, False, vision=support)
    down = fuse_evidence(REPORTS, False, vision=against)

    assert up.confidence > base > down.confidence
    assert up.explanation["vision_support"] == pytest.approx(0.8 - _scores(flood=0.8)["no_incident"])
    assert up.explanation["n_vision_scored"] == 1


def test_cross_modal_conflict_lowers_confidence_and_is_reported():
    images = [ImageEvidence("a", scores=_scores(fire=0.5, flood=0.5), conflict=True)]
    no_conflict = [ImageEvidence("a", scores=_scores(fire=0.5, flood=0.5), conflict=False)]
    flagged = fuse_evidence(REPORTS, False, vision=VisionSignals(images=images))
    clean = fuse_evidence(REPORTS, False, vision=VisionSignals(images=no_conflict))

    assert flagged.cross_modal_conflict is True
    assert flagged.has_contradiction is False  # text contradiction stays separate
    assert flagged.explanation["cross_modal_conflict"] is True
    assert flagged.confidence < clean.confidence


def test_conflict_from_fallback_result_is_ignored():
    images = [ImageEvidence("a", scores=None, conflict=True)]
    result = fuse_evidence(REPORTS, False, vision=VisionSignals(images=images))
    assert result.cross_modal_conflict is False


def test_reposted_photo_does_not_add_corroboration():
    same = "0f" * 8
    images = [ImageEvidence("a", phash=same), ImageEvidence("b", phash=same),
              ImageEvidence("c", phash="f0" * 8)]
    result = fuse_evidence(REPORTS, False, vision=VisionSignals(images=images))

    assert result.explanation["n_effective_reports"] == 2
    assert result.corroborating_reports == 3
    mean_rel = (0.7 + 0.5 + 0.9) / 3
    assert result.confidence == pytest.approx(logistic_fusion(2, mean_rel, False))


def test_ablation_flags_switch_each_effect_off():
    same = "0f" * 8
    images = [ImageEvidence("a", scores=_scores(flood=0.9), phash=same),
              ImageEvidence("b", scores=_scores(flood=0.9), phash=same),
              ImageEvidence("c")]
    base = fuse_evidence(REPORTS, False).confidence

    both_off = fuse_evidence(REPORTS, False, vision=VisionSignals(
        images=images, use_scores=False, use_image_dedup=False))
    assert both_off.confidence == base
    assert both_off.explanation["n_effective_reports"] == 3
    assert both_off.explanation["vision_support"] == 0.0

    dedup_only = fuse_evidence(REPORTS, False, vision=VisionSignals(images=images, use_scores=False))
    assert dedup_only.explanation["n_effective_reports"] == 2
    assert dedup_only.confidence < base


def test_explanation_labels_vision_weights_as_untuned():
    result = fuse_evidence(REPORTS, False, vision=VisionSignals(images=[ImageEvidence("a")]))
    assert result.explanation["vision_weights_untuned"] is True
    assert result.explanation["vision_weights"] == {"w4": DEFAULT_WEIGHTS["w4"], "w5": DEFAULT_WEIGHTS["w5"]}


def test_custom_weights_without_vision_keys_still_work():
    w = {"w0": 0.0, "w1": 1.0, "w2": 1.0, "w3": -1.0}
    assert 0.0 < logistic_fusion(2, 0.5, False, weights=w, vision_support=0.5) < 1.0
