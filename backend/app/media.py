"""
Validation and sanitising of report media.

Citizen photos arrive as base64 data URIs inside the POST /reports JSON
body. Before a report is stored, every image is:
  - size-checked (MEDIA_MAX_BYTES, decoded),
  - type-checked from its decoded content, not the declared MIME type,
  - decoded with a pixel cap (decompression-bomb guard),
  - rotated per its EXIF orientation, resized to MEDIA_MAX_SIDE, and
    re-encoded as JPEG WITHOUT EXIF/ICC metadata (EXIF can hold GPS
    position, time and device details, i.e. personal data).

EXIF is not read for any other purpose. http(s) URLs are stored as given
and never downloaded; they get no vision analysis. Video is rejected.
"""
from __future__ import annotations

import base64
import binascii
import io
import re
from typing import Optional

from app.config import settings

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_PIXELS = 40_000_000
JPEG_QUALITY = 85

_DATA_URI = re.compile(r"^data:(?P<mime>[\w.+-]+/[\w.+-]+)(?:;[\w=.+-]+)*;base64,", re.I)


class MediaError(ValueError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def is_data_uri(value: Optional[str]) -> bool:
    return bool(value) and value[:5].lower() == "data:"


def _decode_data_uri(uri: str) -> tuple[str, bytes]:
    match = _DATA_URI.match(uri)
    if not match:
        raise MediaError(422, "Media must be a base64 data URI or an http(s) URL.")
    mime = match.group("mime").lower()
    if mime.startswith("video/"):
        raise MediaError(415, "Video uploads are not supported yet. Please upload a photo.")
    if mime not in ALLOWED_MIME_TYPES:
        raise MediaError(415, "Only JPEG, PNG or WebP photos are accepted.")

    payload = uri[match.end():]
    # Reject before decoding: base64 is 4/3 the size of the bytes it holds.
    if len(payload) > settings.MEDIA_MAX_BYTES * 4 // 3 + 4:
        raise MediaError(413, _too_large_message())
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        raise MediaError(422, "Media data is not valid base64.")
    if len(raw) > settings.MEDIA_MAX_BYTES:
        raise MediaError(413, _too_large_message())
    return mime, raw


def _too_large_message() -> str:
    return f"Photo is too large (max {settings.MEDIA_MAX_BYTES // 1_000_000} MB)."


def sanitize_image(raw: bytes) -> bytes:
    """Decode, check, strip metadata and re-encode as JPEG. Raises MediaError."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        raise MediaError(503, "Photo processing is unavailable on this server (Pillow missing).")

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(io.BytesIO(raw)) as probe:  # lazy: header only, no pixels yet
            fmt = probe.format
            width, height = probe.size
            if width * height > MAX_PIXELS:  # Pillow only warns up to 2x its limit
                raise MediaError(413, "Photo has too many pixels.")
            probe.verify()  # structural check; the image must be reopened after this
        if fmt not in ALLOWED_FORMATS:
            raise MediaError(415, "Only JPEG, PNG or WebP photos are accepted.")
        with Image.open(io.BytesIO(raw)) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.getchannel("A"))
                img = background
            else:
                img = img.convert("RGB")
            img.thumbnail((settings.MEDIA_MAX_SIDE, settings.MEDIA_MAX_SIDE),
                          Image.Resampling.LANCZOS)
            out = io.BytesIO()
            # No exif= / icc_profile= arguments, so no metadata is written.
            img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            return out.getvalue()
    except MediaError:
        raise
    except Image.DecompressionBombError:
        raise MediaError(413, "Photo has too many pixels.")
    except (OSError, ValueError, SyntaxError):
        # Pillow signals unreadable/corrupt files with these types.
        raise MediaError(415, "File is not a readable JPEG, PNG or WebP photo.")


def process_report_media(media_url: Optional[str]) -> Optional[str]:
    """Return the media_url value to store, or raise MediaError (with an
    HTTP status) for anything that must be rejected."""
    if not media_url:
        return None
    if is_data_uri(media_url):
        _, raw = _decode_data_uri(media_url)
        clean = sanitize_image(raw)
        return "data:image/jpeg;base64," + base64.b64encode(clean).decode("ascii")
    if media_url.lower().startswith(("http://", "https://")):
        return media_url  # stored as a link only; never fetched
    raise MediaError(422, "Media must be a base64 data URI or an http(s) URL.")


def stored_image_bytes(media_url: Optional[str]) -> Optional[bytes]:
    """Image bytes of an already-sanitised stored data URI, for the vision
    pipeline. None for URLs (never fetched) or anything undecodable."""
    if not is_data_uri(media_url):
        return None
    try:
        return _decode_data_uri(media_url)[1]
    except MediaError:
        return None
