"""Print cosine similarities for a small multilingual embedding check."""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from app.services.nlp_service import embed

SENTENCES = [
    "Heavy flooding has submerged several streets and homes after overnight rain.",
    "Rising floodwaters have inundated roads and residential areas in the city.",
    "रात भर की बारिश के बाद भारी बाढ़ ने कई सड़कों और घरों को डुबो दिया है।",
    "A large fire is spreading through the warehouse and nearby buildings.",
    "A strong earthquake shook the region, damaging buildings and roads.",
    "The cricket match was postponed because of a scheduling conflict.",
]

LABELS = [
    "en_flood_1",
    "en_flood_2",
    "hi_flood_1",
    "en_fire",
    "en_earthquake",
    "unrelated",
]


def cosine_matrix(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    normalized = vectors / norms
    return normalized @ normalized.T


def main() -> None:
    vectors = np.array([embed(s) for s in SENTENCES], dtype=np.float64)
    sims = cosine_matrix(vectors)

    header = " ".join(f"{label:>14}" for label in LABELS)
    print(f"{'':>14} {header}")
    for i, label in enumerate(LABELS):
        row = " ".join(f"{sims[i, j]:14.4f}" for j in range(len(LABELS)))
        print(f"{label:>14} {row}")

    print("\nSentences:")
    for label, sentence in zip(LABELS, SENTENCES):
        print(f"  {label}: {sentence}")


if __name__ == "__main__":
    main()
