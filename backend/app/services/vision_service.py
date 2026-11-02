"""
Vision service: image evidence for citizen-uploaded report photos.

Produces, per image:
  - zero-shot scores over the SAME disaster labels as the text classifier
    (nlp_service.DISASTER_LABELS) plus a "no_incident" class,
  - an image embedding,
  - a label-level text-image consistency score and a cross-modal conflict
    flag (does the photo support what the report text claims?).

Model: CLIP ViT-B/32 vision tower, int8 ONNX, run with onnxruntime (no
torch). Fetch it with `python scripts/fetch_vision_model.py`. Label text
embeddings are precomputed in vision_prompts.npz
(scripts/build_vision_prompts.py), so no text model is loaded at runtime.

When no model is available (VISION_ENABLED=false, onnxruntime/Pillow or the
model file missing) `analyze_image` returns a fallback result:
model="fallback", scores=None. Downstream code must treat that as "no
vision evidence", never as negative evidence.

All thresholds and prompts are hand-set and untuned; accuracy has not been
evaluated.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from app.config import settings
from app.services.nlp_service import DISASTER_LABELS

logger = logging.getLogger("crowdsense.vision")

NO_INCIDENT_LABEL = "no_incident"
IMAGE_LABELS = tuple(DISASTER_LABELS) + (NO_INCIDENT_LABEL,)
FALLBACK_MODEL = "fallback"

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_PROMPTS_FILE = Path(__file__).with_name("vision_prompts.npz")
_MODEL_FILE = "vision_model_quantized.onnx"
_IMAGE_SIZE = 224
_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
# Trained CLIP logit scale (exp(logit_scale), clamped to 100 in training).
_LOGIT_SCALE = 100.0

_model = None
_model_unavailable = False


@dataclass
class VisionResult:
    model: str                                  # model id, or "fallback"
    label: Optional[str] = None                 # top class; None for fallback
    scores: Optional[Dict[str, float]] = None   # class -> probability, sums to 1
    embedding: Optional[List[float]] = None
    text_consistency: Optional[float] = None    # P(image = text's label)
    cross_modal_conflict: Optional[bool] = None
    note: Optional[str] = None                  # why the fallback was used

    @property
    def has_evidence(self) -> bool:
        return self.scores is not None


def fallback_result(note: str) -> VisionResult:
    return VisionResult(model=FALLBACK_MODEL, note=note)


def text_image_consistency(
    scores: Optional[Dict[str, float]], text_label: Optional[str]
) -> Optional[float]:
    """Probability the image assigns to the text's disaster label. None when
    there is nothing to compare (no scores, or the text was unclassified)."""
    if scores is None or text_label not in DISASTER_LABELS:
        return None
    return float(scores.get(text_label, 0.0))


def is_cross_modal_conflict(
    scores: Optional[Dict[str, float]],
    text_label: Optional[str],
    low: Optional[float] = None,
    high: Optional[float] = None,
) -> Optional[bool]:
    """True when the image gives the text's label little support AND is
    confident about something else (another disaster type or no incident)."""
    consistency = text_image_consistency(scores, text_label)
    if consistency is None:
        return None
    low = settings.VISION_CONFLICT_LOW if low is None else low
    high = settings.VISION_CONFLICT_HIGH if high is None else high
    top_label = max(scores, key=scores.get)
    return consistency < low and top_label != text_label and scores[top_label] >= high


def build_result(
    model_id: str,
    scores: Dict[str, float],
    embedding: Optional[List[float]],
    text_label: Optional[str],
) -> VisionResult:
    """Turn raw model output into a VisionResult (pure; no model needed)."""
    return VisionResult(
        model=model_id,
        label=max(scores, key=scores.get),
        scores=dict(scores),
        embedding=embedding,
        text_consistency=text_image_consistency(scores, text_label),
        cross_modal_conflict=is_cross_modal_conflict(scores, text_label),
    )


def image_type_override(
    text_label: Optional[str],
    result: Optional[VisionResult],
    min_confidence: Optional[float] = None,
) -> Optional[str]:
    """Disaster type to use from the image, or None to keep the text label.
    Only fills in when the text could not be classified; the image never
    overrides a text label."""
    if result is None or not result.has_evidence:
        return None
    if text_label in DISASTER_LABELS:
        return None
    min_confidence = (
        settings.VISION_MIN_LABEL_CONFIDENCE if min_confidence is None else min_confidence
    )
    if result.label == NO_INCIDENT_LABEL or result.scores[result.label] < min_confidence:
        return None
    return result.label


def compute_phash(image_bytes: Optional[bytes], hash_size: int = 8) -> Optional[str]:
    """DCT perceptual hash (64 bits for hash_size=8) as a hex string.
    Survives re-encoding and resizing, not cropping or rotation. Returns
    None when there is no image, it can't be decoded, or Pillow is missing.
    Needs no model, so it works even when vision is disabled."""
    if not image_bytes:
        return None
    try:
        from PIL import Image
        from scipy.fft import dctn
    except ImportError:
        return None
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            side = hash_size * 4
            gray = img.convert("L").resize((side, side), Image.Resampling.LANCZOS)
    except (OSError, ValueError, Image.DecompressionBombError):
        return None

    coeffs = dctn(np.asarray(gray, dtype=np.float64), type=2, norm="ortho")
    low = coeffs[:hash_size, :hash_size].flatten()
    median = np.median(low[1:])  # exclude the DC (overall brightness) term
    value = 0
    for bit in low > median:
        value = (value << 1) | int(bit)
    return f"{value:0{hash_size * hash_size // 4}x}"


@dataclass
class _ClipModel:
    session: object                 # onnxruntime.InferenceSession
    group_embeddings: np.ndarray    # (groups, 512), L2-normalised
    group_labels: List[str]         # label of each group


def _model_dir() -> Path:
    path = Path(settings.VISION_MODEL_DIR)
    return path if path.is_absolute() else _BACKEND_DIR / path


def _get_model() -> Optional[_ClipModel]:
    """Load the ONNX session on first use; None when vision is disabled or
    anything needed is missing (logged once, then the fallback is used)."""
    global _model, _model_unavailable
    if not settings.VISION_ENABLED or _model_unavailable:
        return None
    if _model is None:
        try:
            import onnxruntime as ort
            import PIL  # noqa: F401  (needed by _preprocess)

            options = ort.SessionOptions()
            options.intra_op_num_threads = 2  # keep CPU/RAM use modest
            session = ort.InferenceSession(
                str(_model_dir() / _MODEL_FILE), options, providers=["CPUExecutionProvider"]
            )
            prompts = np.load(_PROMPTS_FILE)
            _model = _ClipModel(
                session=session,
                group_embeddings=prompts["group_embeddings"].astype(np.float32),
                group_labels=[str(l) for l in prompts["group_labels"]],
            )
        except Exception as exc:  # missing package, file, or bad model
            _model_unavailable = True
            logger.warning("Vision model unavailable, using fallback: %s", exc)
            return None
    return _model


def _preprocess(image_bytes: bytes) -> np.ndarray:
    """CLIP preprocessing: shortest edge -> 224 (bicubic), centre crop 224,
    scale to [0, 1], normalise. Returns float32 (1, 3, 224, 224)."""
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(image_bytes)) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        w, h = img.size
        scale = _IMAGE_SIZE / min(w, h)
        img = img.resize(
            (max(_IMAGE_SIZE, round(w * scale)), max(_IMAGE_SIZE, round(h * scale))),
            Image.Resampling.BICUBIC,
        )
        w, h = img.size
        left, top = (w - _IMAGE_SIZE) // 2, (h - _IMAGE_SIZE) // 2
        img = img.crop((left, top, left + _IMAGE_SIZE, top + _IMAGE_SIZE))
        pixels = np.asarray(img, dtype=np.float32) / 255.0
    pixels = (pixels - _MEAN) / _STD
    return pixels.transpose(2, 0, 1)[np.newaxis, ...]


def _label_scores(model: _ClipModel, image_embedding: np.ndarray) -> Dict[str, float]:
    """Softmax over prompt groups, then sum the groups of each label."""
    logits = _LOGIT_SCALE * (model.group_embeddings @ image_embedding)
    probs = np.exp(logits - logits.max())
    probs /= probs.sum()
    scores = {label: 0.0 for label in IMAGE_LABELS}
    for label, p in zip(model.group_labels, probs):
        scores[label] += float(p)
    return scores


def analyze_image(
    image_bytes: Optional[bytes], text_label: Optional[str] = None
) -> VisionResult:
    if not image_bytes:
        return fallback_result("no image")
    if not settings.VISION_ENABLED:
        return fallback_result("vision disabled")
    model = _get_model()
    if model is None:
        return fallback_result("model unavailable")
    try:
        pixels = _preprocess(image_bytes)
    except Exception as exc:  # Pillow raises many error types on bad input
        logger.warning("Could not decode image for vision: %s", exc)
        return fallback_result("image unreadable")

    raw = model.session.run(["image_embeds"], {"pixel_values": pixels})[0][0]
    embedding = raw / np.linalg.norm(raw)
    scores = _label_scores(model, embedding)
    return build_result(
        settings.VISION_MODEL,
        scores,
        [round(float(x), 6) for x in embedding],
        text_label,
    )
