import pytest

from app.config import settings
from app.services import nlp_service
from app.services.vision_service import (
    FALLBACK_MODEL,
    IMAGE_LABELS,
    NO_INCIDENT_LABEL,
    analyze_image,
    build_result,
    image_type_override,
    is_cross_modal_conflict,
    text_image_consistency,
)


def _scores(**probs):
    """Score dict over all image labels; unspecified labels share the rest."""
    rest = [l for l in IMAGE_LABELS if l not in probs]
    remaining = (1.0 - sum(probs.values())) / len(rest) if rest else 0.0
    return {l: probs.get(l, remaining) for l in IMAGE_LABELS}


def test_image_labels_match_text_labels_plus_no_incident():
    assert IMAGE_LABELS == nlp_service.DISASTER_LABELS + (NO_INCIDENT_LABEL,)
    # Whatever the text classifier returns is either a shared label or a
    # "nothing to compare" value.
    for keywords in nlp_service._DISASTER_KEYWORDS.values():
        label = nlp_service.classify_disaster_type(f"There is a {keywords[0]} here")
        assert label in nlp_service.DISASTER_LABELS + ("unclassified",)


@pytest.mark.parametrize("enabled", [False, True])
def test_fallback_is_neutral(monkeypatch, enabled):
    monkeypatch.setattr(settings, "VISION_ENABLED", enabled)
    result = analyze_image(b"not-really-an-image", text_label="flood")
    assert result.model == FALLBACK_MODEL
    assert result.has_evidence is False
    assert result.scores is None and result.label is None and result.embedding is None
    assert result.text_consistency is None
    assert result.cross_modal_conflict is None
    assert image_type_override("unclassified", result) is None


def test_fallback_when_no_image():
    result = analyze_image(None)
    assert result.model == FALLBACK_MODEL
    assert result.note == "no image"


def test_consistency_is_probability_of_text_label():
    scores = _scores(flood=0.7, fire=0.1)
    assert text_image_consistency(scores, "flood") == pytest.approx(0.7)
    assert text_image_consistency(scores, "unclassified") is None
    assert text_image_consistency(scores, None) is None
    assert text_image_consistency(None, "flood") is None


def test_conflict_when_image_confidently_shows_something_else():
    scores = _scores(no_incident=0.8, flood=0.05)
    assert is_cross_modal_conflict(scores, "flood", low=0.15, high=0.5) is True


def test_no_conflict_when_image_supports_text_or_is_uncertain():
    supports = _scores(flood=0.6)
    assert is_cross_modal_conflict(supports, "flood", low=0.15, high=0.5) is False
    uncertain = _scores(flood=0.1, fire=0.3)  # low support, but nothing confident
    assert is_cross_modal_conflict(uncertain, "flood", low=0.15, high=0.5) is False
    assert is_cross_modal_conflict(supports, "unclassified") is None


def test_build_result_picks_top_label():
    result = build_result("test-model", _scores(fire=0.9), [0.1, 0.2], "flood")
    assert result.label == "fire"
    assert result.has_evidence is True
    assert result.text_consistency == pytest.approx(_scores(fire=0.9)["flood"])


def test_image_only_fills_in_unclassified_text():
    fire = build_result("m", _scores(fire=0.7), None, "unclassified")
    assert image_type_override("unclassified", fire, min_confidence=0.5) == "fire"
    assert image_type_override("unknown", fire, min_confidence=0.5) == "fire"
    # Never overrides a real text label.
    assert image_type_override("flood", fire, min_confidence=0.5) is None
    # Not confident enough.
    weak = build_result("m", _scores(fire=0.4), None, "unclassified")
    assert image_type_override("unclassified", weak, min_confidence=0.5) is None
    # "No incident" never becomes a disaster type.
    nothing = build_result("m", _scores(no_incident=0.9), None, "unclassified")
    assert image_type_override("unclassified", nothing, min_confidence=0.5) is None
