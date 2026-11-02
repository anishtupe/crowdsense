"""Vision model path. All tests except the last run without the real model."""
import io
from pathlib import Path

import numpy as np
import pytest

PIL_Image = pytest.importorskip("PIL.Image")

from app.config import settings
from app.services import vision_service as vs

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def vision_on(monkeypatch):
    """Enable vision and reset the lazily-loaded model state."""
    monkeypatch.setattr(settings, "VISION_ENABLED", True)
    monkeypatch.setattr(vs, "_model", None)
    monkeypatch.setattr(vs, "_model_unavailable", False)


def _png(size=(320, 240)) -> bytes:
    buf = io.BytesIO()
    PIL_Image.new("RGB", size, (120, 60, 30)).save(buf, format="PNG")
    return buf.getvalue()


class _FakeSession:
    """Stands in for onnxruntime: always returns the same image embedding."""

    def __init__(self, embedding):
        self.embedding = np.asarray(embedding, dtype=np.float32)
        self.last_input = None

    def run(self, output_names, feeds):
        self.last_input = feeds["pixel_values"]
        return [self.embedding[np.newaxis, :]]


def _fake_model(winning_label: str) -> vs._ClipModel:
    """One group per label with orthogonal embeddings; the image embedding
    points at `winning_label`'s group."""
    labels = list(vs.IMAGE_LABELS)
    groups = np.eye(len(labels), 512, dtype=np.float32)
    image = groups[labels.index(winning_label)]
    return vs._ClipModel(session=_FakeSession(image), group_embeddings=groups, group_labels=labels)


def test_preprocess_shape_and_dtype():
    pixels = vs._preprocess(_png((320, 240)))
    assert pixels.shape == (1, 3, 224, 224)
    assert pixels.dtype == np.float32


def test_analyze_image_with_mocked_model(monkeypatch, vision_on):
    monkeypatch.setattr(vs, "_model", _fake_model("fire"))
    result = vs.analyze_image(_png(), text_label="flood")

    assert result.model == settings.VISION_MODEL
    assert result.has_evidence is True
    assert result.label == "fire"
    assert set(result.scores) == set(vs.IMAGE_LABELS)
    assert sum(result.scores.values()) == pytest.approx(1.0)
    assert len(result.embedding) == 512
    assert np.linalg.norm(result.embedding) == pytest.approx(1.0, abs=1e-4)
    # Text says flood, image confidently says fire -> cross-modal conflict.
    assert result.text_consistency < settings.VISION_CONFLICT_LOW
    assert result.cross_modal_conflict is True


def test_no_incident_groups_are_summed(monkeypatch, vision_on):
    model = _fake_model("no_incident")
    # Split "no_incident" into two identical groups: their mass must add up.
    model.group_embeddings = np.vstack([model.group_embeddings, model.group_embeddings[-1]])
    model.group_labels = model.group_labels + ["no_incident"]
    monkeypatch.setattr(vs, "_model", model)

    result = vs.analyze_image(_png())
    assert result.label == "no_incident"
    assert sum(result.scores.values()) == pytest.approx(1.0)


def test_missing_model_file_falls_back(monkeypatch, vision_on, tmp_path):
    monkeypatch.setattr(settings, "VISION_MODEL_DIR", str(tmp_path))  # empty dir
    result = vs.analyze_image(_png(), text_label="flood")
    assert result.model == vs.FALLBACK_MODEL
    assert result.note == "model unavailable"
    assert result.has_evidence is False


def test_unreadable_image_falls_back(monkeypatch, vision_on):
    monkeypatch.setattr(vs, "_model", _fake_model("fire"))
    result = vs.analyze_image(b"not an image")
    assert result.model == vs.FALLBACK_MODEL
    assert result.note == "image unreadable"


def test_real_model_runs_on_a_real_image(monkeypatch, vision_on):
    """Optional: needs onnxruntime and the downloaded model. Checks only the
    shape of the output, NOT whether the label is right (not evaluated)."""
    pytest.importorskip("onnxruntime")
    if not (vs._model_dir() / vs._MODEL_FILE).exists():
        pytest.skip("vision model not downloaded (scripts/fetch_vision_model.py)")

    image = (REPO_ROOT / "docs" / "images" / "map_dashboard.png").read_bytes()
    result = vs.analyze_image(image, text_label="flood")

    assert result.model == settings.VISION_MODEL
    assert set(result.scores) == set(vs.IMAGE_LABELS)
    assert sum(result.scores.values()) == pytest.approx(1.0, abs=1e-5)
    assert all(0.0 <= p <= 1.0 for p in result.scores.values())
    assert len(result.embedding) == 512
    assert result.label in vs.IMAGE_LABELS
