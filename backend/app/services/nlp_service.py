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

# ---- Real-model hook (commented out by default) ---------------------------
# from sentence_transformers import SentenceTransformer
# _model = SentenceTransformer("all-MiniLM-L6-v2")
#
# def embed(text: str) -> List[float]:
#     return _model.encode(text, normalize_embeddings=True).tolist()

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
    """Cheap keyword classifier. Replace with a fine-tuned transformer
    classifier for real use (see module docstring)."""
    if not text:
        return "unknown"
    lowered = text.lower()
    for label, keywords in _DISASTER_KEYWORDS.items():
        if any(k in lowered for k in keywords):
            return label
    return "unclassified"


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


def embed(text: str, dims: int = 64) -> List[float]:
    """Deterministic hash-based pseudo-embedding fallback.

    NOT semantically meaningful beyond exact/near-duplicate token overlap
    (it's a bag-of-words hashing trick) — good enough to make the
    duplicate-detection pipeline runnable end-to-end without any model
    downloads. Replace with a real sentence embedding for anything you
    intend to evaluate or publish results from.
    """
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
