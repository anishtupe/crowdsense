import io

import numpy as np
import pytest

PIL_Image = pytest.importorskip("PIL.Image")

from app.services.duplicate_detection import phash_distance
from app.services.vision_service import compute_phash

MAX_DISTANCE = 8  # same default as VISION_PHASH_MAX_DISTANCE


def _encode(img, fmt="PNG", **kwargs) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


def _scene() -> "PIL_Image.Image":
    """Synthetic 'photo': a smooth gradient with a bright block on it."""
    y, x = np.mgrid[0:240, 0:320]
    pixels = (x * 0.5 + y * 0.3).astype(np.uint8)
    pixels[60:140, 180:280] = 250
    return PIL_Image.fromarray(pixels).convert("RGB")


def _other_scene() -> "PIL_Image.Image":
    rng = np.random.default_rng(seed=7)
    pixels = rng.integers(0, 256, size=(240, 320, 3), dtype=np.uint8)
    return PIL_Image.fromarray(pixels)


def test_hash_is_16_hex_chars_and_deterministic():
    data = _encode(_scene())
    h = compute_phash(data)
    assert h is not None and len(h) == 16
    int(h, 16)  # valid hex
    assert compute_phash(data) == h


def test_reencoded_and_resized_copy_is_near_duplicate():
    original = _scene()
    repost = original.resize((160, 120))
    a = compute_phash(_encode(original))
    b = compute_phash(_encode(repost, fmt="JPEG", quality=60))
    assert phash_distance(a, b) <= MAX_DISTANCE


def test_different_image_is_not_a_duplicate():
    a = compute_phash(_encode(_scene()))
    b = compute_phash(_encode(_other_scene()))
    assert phash_distance(a, b) > MAX_DISTANCE


def test_unreadable_or_missing_image_gives_none():
    assert compute_phash(b"definitely not an image") is None
    assert compute_phash(None) is None
    assert compute_phash(b"") is None
