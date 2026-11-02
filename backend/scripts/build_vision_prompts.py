"""Precompute CLIP text embeddings for the zero-shot image labels.

Writes app/services/vision_prompts.npz, which vision_service loads at
runtime so the server needs no tokenizer or text model.

Needs (build time only, not in requirements.txt):
    pip install tokenizers==0.20.0
    python scripts/fetch_vision_model.py --with-text
    python scripts/build_vision_prompts.py

Each "group" is one softmax slot whose embedding is the normalised mean of
its prompts. Disaster labels have one group each. "no_incident" is a mixed
class, so it has several groups and its probability is the sum of theirs.
The prompts are hand-written and untuned; their effect on accuracy has not
been evaluated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.nlp_service import DISASTER_LABELS  # noqa: E402
from app.services.vision_service import _model_dir  # noqa: E402

MODEL_DIR = _model_dir()
OUT = BACKEND / "app" / "services" / "vision_prompts.npz"
NO_INCIDENT = "no_incident"

# (label, prompts) — one entry per softmax group.
GROUPS = [
    ("flood", ["a photo of a flood", "a photo of a flooded street",
               "a photo of houses under flood water", "a photo of people wading through flood water"]),
    ("fire", ["a photo of a fire", "a photo of a building on fire",
              "a photo of a wildfire", "a photo of thick smoke and flames"]),
    ("earthquake", ["a photo of earthquake damage", "a photo of a collapsed building",
                    "a photo of rubble after an earthquake", "a photo of cracked roads and damaged buildings"]),
    ("storm", ["a photo of a storm", "a photo of a cyclone",
               "a photo of fallen trees after a storm", "a photo of storm damage to roofs"]),
    ("landslide", ["a photo of a landslide", "a photo of a mudslide covering a road",
                   "a photo of rocks and mud fallen on a hillside road"]),
    ("accident", ["a photo of a road accident", "a photo of a car crash",
                  "a photo of a damaged vehicle after a collision", "a photo of a train derailment"]),
    (NO_INCIDENT, ["a photo of a normal street", "a photo of everyday city life"]),
    (NO_INCIDENT, ["a selfie", "a photo of people smiling"]),
    (NO_INCIDENT, ["a screenshot of a phone screen", "a screenshot of a website or map"]),
    (NO_INCIDENT, ["a photo of a document", "a photo of text"]),
    (NO_INCIDENT, ["a photo of a calm landscape", "a photo of a clear sky"]),
    (NO_INCIDENT, ["a photo of food", "a photo of objects on a table"]),
]


def main() -> None:
    import onnxruntime as ort
    from tokenizers import Tokenizer

    labels = {label for label, _ in GROUPS}
    assert labels == set(DISASTER_LABELS) | {NO_INCIDENT}, "labels must match nlp_service"

    tokenizer = Tokenizer.from_file(str(MODEL_DIR / "tokenizer.json"))
    session = ort.InferenceSession(str(MODEL_DIR / "text_model.onnx"),
                                   providers=["CPUExecutionProvider"])

    def embed(text: str) -> np.ndarray:
        ids = np.array([tokenizer.encode(text).ids], dtype=np.int64)
        vec = session.run(["text_embeds"], {"input_ids": ids})[0][0]
        return vec / np.linalg.norm(vec)

    group_embeds = []
    for _, prompts in GROUPS:
        mean = np.mean([embed(p) for p in prompts], axis=0)
        group_embeds.append(mean / np.linalg.norm(mean))

    np.savez(
        OUT,
        group_embeddings=np.asarray(group_embeds, dtype=np.float32),
        group_labels=np.array([label for label, _ in GROUPS]),
        prompts_json=np.array(json.dumps(GROUPS)),
        source=np.array("Xenova/clip-vit-base-patch32@d15189d7 text_model.onnx (fp32)"),
    )
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(GROUPS)} groups)")


if __name__ == "__main__":
    main()
