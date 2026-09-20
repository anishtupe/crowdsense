"""
Vision service: image/video evidence classification.

Stub implementation — returns a placeholder label so the pipeline can run
without a model download. Swap in a real model:

    pip install onnxruntime pillow
    (load an exported int8 ONNX model and run inference in classify_image)
"""
from __future__ import annotations

from typing import Optional


def classify_image(media_url: Optional[str]) -> Optional[str]:
    if not media_url:
        return None
    # TODO: replace with real inference, e.g.:
    #   session = onnxruntime.InferenceSession("model.onnx")
    #   ... preprocess image, run session, decode label ...
    return "unclassified_media"
