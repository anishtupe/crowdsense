import base64
import io

import pytest

PIL_Image = pytest.importorskip("PIL.Image")

from app import media
from app.config import settings
from app.media import MediaError, process_report_media, stored_image_bytes

GPS_IFD = 0x8825
ORIENTATION = 0x0112
MAKE = 0x010F


def _data_uri(raw: bytes, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def _image_bytes(fmt="JPEG", size=(64, 48), mode="RGB", exif=None) -> bytes:
    buf = io.BytesIO()
    color = (200, 30, 30, 128) if mode == "RGBA" else (200, 30, 30)
    img = PIL_Image.new(mode, size, color)
    kwargs = {"exif": exif} if exif is not None else {}
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


def _decode_stored(uri: str) -> "PIL_Image.Image":
    assert uri.startswith("data:image/jpeg;base64,")
    return PIL_Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1])))


def _exif_with_gps_and_rotation():
    from PIL.TiffImagePlugin import IFDRational

    exif = PIL_Image.Exif()
    exif[ORIENTATION] = 6          # "rotate 90 CW to display"
    exif[MAKE] = "TestPhone"
    exif[GPS_IFD] = {1: "N", 2: (IFDRational(19, 1), IFDRational(10, 1), IFDRational(30, 1))}
    return exif


def test_exif_gps_and_device_tags_are_stripped_and_rotation_applied():
    raw = _image_bytes(size=(64, 48), exif=_exif_with_gps_and_rotation())
    with PIL_Image.open(io.BytesIO(raw)) as original:  # precondition: EXIF really present
        assert original.getexif().get_ifd(GPS_IFD)
        assert original.getexif()[MAKE] == "TestPhone"

    out = _decode_stored(process_report_media(_data_uri(raw, "image/jpeg")))
    exif = out.getexif()
    assert not exif.get_ifd(GPS_IFD)
    assert MAKE not in exif and ORIENTATION not in exif
    assert "icc_profile" not in out.info
    assert out.size == (48, 64)  # orientation baked into the pixels


def test_png_with_alpha_becomes_rgb_jpeg():
    out = _decode_stored(process_report_media(_data_uri(_image_bytes("PNG", mode="RGBA"), "image/png")))
    assert out.format == "JPEG" and out.mode == "RGB"


def test_large_image_is_resized(monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_MAX_SIDE", 100)
    out = _decode_stored(process_report_media(_data_uri(_image_bytes(size=(400, 200)), "image/jpeg")))
    assert out.size == (100, 50)


def test_type_is_checked_from_content_not_declared_mime():
    gif = _image_bytes("GIF")
    with pytest.raises(MediaError) as err:
        process_report_media(_data_uri(gif, "image/png"))
    assert err.value.status_code == 415
    with pytest.raises(MediaError) as err:
        process_report_media(_data_uri(b"<html>not a photo</html>", "image/jpeg"))
    assert err.value.status_code == 415


@pytest.mark.parametrize("mime", ["video/mp4", "image/svg+xml", "image/gif", "text/html"])
def test_disallowed_mime_types_rejected(mime):
    with pytest.raises(MediaError) as err:
        process_report_media(_data_uri(b"whatever", mime))
    assert err.value.status_code == 415


def test_too_large_rejected_before_and_after_decoding(monkeypatch):
    raw = _image_bytes(size=(256, 256))
    monkeypatch.setattr(settings, "MEDIA_MAX_BYTES", len(raw) - 1)
    with pytest.raises(MediaError) as err:
        process_report_media(_data_uri(raw, "image/jpeg"))
    assert err.value.status_code == 413


def test_too_many_pixels_rejected(monkeypatch):
    monkeypatch.setattr(media, "MAX_PIXELS", 1000)
    with pytest.raises(MediaError) as err:
        process_report_media(_data_uri(_image_bytes(size=(64, 48)), "image/jpeg"))
    assert err.value.status_code == 413


def test_invalid_base64_rejected():
    with pytest.raises(MediaError) as err:
        process_report_media("data:image/jpeg;base64,@@@not-base64@@@")
    assert err.value.status_code == 422


def test_urls_are_kept_and_never_fetched_other_schemes_rejected():
    assert process_report_media("https://example.com/photo.jpg") == "https://example.com/photo.jpg"
    assert stored_image_bytes("https://example.com/photo.jpg") is None
    assert process_report_media(None) is None and process_report_media("") is None
    with pytest.raises(MediaError) as err:
        process_report_media("javascript:alert(1)")
    assert err.value.status_code == 422


def test_stored_image_bytes_round_trip():
    stored = process_report_media(_data_uri(_image_bytes(), "image/jpeg"))
    raw = stored_image_bytes(stored)
    assert raw is not None and PIL_Image.open(io.BytesIO(raw)).format == "JPEG"
