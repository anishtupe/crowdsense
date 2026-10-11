"""
NLP service: disaster-type classification, sentiment, and text embeddings.

This ships with a lightweight, dependency-free fallback so the app runs
immediately. Swap in real models when you're ready:

    pip install sentence-transformers torch
    (uncomment the SentenceTransformer block below)

Keep the function signatures the same so the rest of the pipeline
(duplicate_detection, fusion_engine, tests) doesn't need to change.
"""
from __future__ import annotations

import hashlib
import re
from typing import List

import numpy as np

_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_model = None
_st_unavailable = False

_DISASTER_KEYWORDS = {
    "flood": ["flood", "flooding", "inundat", "waterlog"],
    "fire": ["fire", "wildfire", "blaze", "burning"],
    "earthquake": ["earthquake", "tremor", "seismic", "quake"],
    "storm": ["storm", "cyclone", "hurricane", "typhoon", "tornado"],
    "landslide": ["landslide", "mudslide", "rockfall"],
    "accident": ["accident", "crash", "collision", "derail"],
}

_NEGATIVE_WORDS = ["dead", "died", "collapse", "trapped", "injured", "damage", "destroyed"]
_POSITIVE_WORDS = ["safe", "rescued", "recovered", "resolved", "clear"]


def classify_disaster_type(text: str) -> str:
    """Zero-shot label matching via embeddings, with keyword fallback."""
    if not text:
        return "unknown"

    def _keyword_fallback() -> str:
        lowered = text.lower()
        for label, keywords in _DISASTER_KEYWORDS.items():
            if any(k in lowered for k in keywords):
                return label
        return "unclassified"

    if _get_model() is None:
        return _keyword_fallback()

    label_descriptions = {
        "flood": "A flood or inundation with waterlogged streets and homes.",
        "fire": "A fire, wildfire, or blaze burning buildings or land.",
        "earthquake": "An earthquake, tremor, or seismic shaking that damages structures.",
        "storm": "A storm, cyclone, hurricane, typhoon, or tornado.",
        "landslide": "A landslide, mudslide, or rockfall on a slope.",
        "accident": "An accident, crash, collision, or derailment.",
    }

    query = np.asarray(embed(text), dtype=np.float64)
    qn = np.linalg.norm(query)
    if qn == 0:
        return _keyword_fallback()
    query = query / qn

    best_label = "unclassified"
    best_sim = -1.0
    for label, description in label_descriptions.items():
        vec = np.asarray(embed(description), dtype=np.float64)
        vn = np.linalg.norm(vec)
        if vn == 0:
            continue
        sim = float(np.dot(query, vec / vn))
        if sim > best_sim:
            best_sim = sim
            best_label = label

    if best_sim < 0.3:
        return "unclassified"
    return best_label


def analyze_sentiment(text: str) -> str:
    if not text:
        return "neutral"
    lowered = text.lower()
    neg = sum(1 for w in _NEGATIVE_WORDS if w in lowered)
    pos = sum(1 for w in _POSITIVE_WORDS if w in lowered)
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


def _get_model():
    """Load SentenceTransformer on first use; None if the package is missing."""
    global _model, _st_unavailable
    if _st_unavailable:
        return None
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(_MODEL_NAME)
        except ImportError:
            _st_unavailable = True
            return None
    return _model


def _hash_embed(text: str, dims: int = 64) -> List[float]:
    """Deterministic hash-based pseudo-embedding fallback."""
    if not text:
        return [0.0] * dims

    vec = np.zeros(dims, dtype=np.float64)
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    for tok in tokens:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        idx = h % dims
        sign = 1.0 if (h // dims) % 2 == 0 else -1.0
        vec[idx] += sign

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def embed(text: str, dims: int = 64) -> List[float]:
    """Sentence embedding; falls back to hash embedding if ST isn't installed."""
    model = _get_model()
    if model is None:
        return _hash_embed(text, dims)
    if not text:
        return model.encode("", normalize_embeddings=True).tolist()
    return model.encode(text, normalize_embeddings=True).tolist()
