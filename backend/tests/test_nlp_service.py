import pytest


def test_english_flood_classifies_as_flood():
    pytest.importorskip("sentence_transformers")
    from app.services.nlp_service import classify_disaster_type

    assert classify_disaster_type(
        "Heavy flooding has submerged several streets and homes after overnight rain."
    ) == "flood"


def test_hindi_flood_classifies_as_flood():
    pytest.importorskip("sentence_transformers")
    from app.services.nlp_service import classify_disaster_type

    assert classify_disaster_type(
        "रात भर की बारिश के बाद भारी बाढ़ ने कई सड़कों और घरों को डुबो दिया है।"
    ) == "flood"


def test_empty_text_returns_unknown():
    pytest.importorskip("sentence_transformers")
    from app.services.nlp_service import classify_disaster_type

    assert classify_disaster_type("") == "unknown"


def test_similar_sentences_score_higher_than_unrelated():
    pytest.importorskip("sentence_transformers")
    import numpy as np
    from app.services.nlp_service import embed

    def cosine(a, b) -> float:
        va = np.asarray(a, dtype=np.float64)
        vb = np.asarray(b, dtype=np.float64)
        na = np.linalg.norm(va)
        nb = np.linalg.norm(vb)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(va, vb) / (na * nb))

    flood_a = embed("Rising floodwaters have inundated roads and residential areas.")
    flood_b = embed("Heavy flooding has submerged several streets and homes.")
    unrelated = embed("The cricket match was postponed because of a scheduling conflict.")
    assert cosine(flood_a, flood_b) > cosine(flood_a, unrelated)
