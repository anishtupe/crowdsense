"""Pipeline + vision wiring, on a temporary SQLite DB (never the dev DB)."""
import base64
import io
import json

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

PIL_Image = pytest.importorskip("PIL.Image")

from app import database
from app.config import settings
from app.media import process_report_media
from app.models import Incident, Report, User
from app.pipeline import process_new_report
from app.services import vision_service as vs
from app.utils import safe_from_shape
from tests.test_vision_model import _fake_model


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'pipeline.db'}",
                           connect_args={"check_same_thread": False})
    # Same stub spatial functions the app registers on its own engine.
    event.listen(engine, "connect", database._register_sqlite_spatial_funcs)
    database.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def vision_off(monkeypatch):
    monkeypatch.setattr(settings, "VISION_ENABLED", False)


@pytest.fixture
def text_unclassified(monkeypatch):
    """Pin the text label: with real embeddings installed, even vague text
    can get a disaster type, which would make these tests depend on the
    NLP backend."""
    from app.services import nlp_service

    monkeypatch.setattr(nlp_service, "classify_disaster_type", lambda text: "unclassified")


def _photo_uri(color=(200, 40, 40), size=(320, 240)) -> str:
    """A stored (already sanitised) photo, as POST /reports would store it."""
    import numpy as np

    y, x = np.mgrid[0:size[1], 0:size[0]]
    pixels = np.stack([(x * 0.6) % 256, (y * 0.9) % 256, np.full_like(x, color[2])], -1)
    img = PIL_Image.fromarray(pixels.astype("uint8"))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return process_report_media("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode())


def _add_report(db, text, media_url=None, lat=19.0760, lon=72.8777):
    report = Report(text=text, media_url=media_url, source="citizen",
                    location=safe_from_shape(lon, lat))
    db.add(report)
    db.commit()
    return report


def test_report_without_photo_has_no_image_fields(db, vision_off):
    report = _add_report(db, "Flooding near the station")
    process_new_report(db, report.id)
    db.refresh(report)

    assert report.image_model is None and report.image_phash is None
    incident = db.get(Incident, report.incident_id)
    assert json.loads(incident.fusion_explanation)["n_reports"] == 1


def test_photo_with_vision_off_is_neutral_fallback(db, vision_off, text_unclassified):
    report = _add_report(db, "Something happened near the market", media_url=_photo_uri())
    process_new_report(db, report.id)
    db.refresh(report)

    assert report.image_model == vs.FALLBACK_MODEL
    assert report.image_scores is None and report.image_label is None
    assert report.image_conflict is None and report.image_text_consistency is None
    assert report.image_phash is not None and len(report.image_phash) == 16
    # The old stub turned this into "unclassified_media"; now text stays as is.
    assert report.disaster_type == "unclassified"


def test_mocked_model_fills_unclassified_text_and_stores_evidence(db, monkeypatch, text_unclassified):
    monkeypatch.setattr(settings, "VISION_ENABLED", True)
    monkeypatch.setattr(vs, "_model", _fake_model("fire"))

    report = _add_report(db, "Something happened near the market", media_url=_photo_uri())
    process_new_report(db, report.id)
    db.refresh(report)

    assert report.image_model == settings.VISION_MODEL
    assert report.image_label == "fire"
    assert report.disaster_type == "fire"  # text was unclassified
    assert sum(json.loads(report.image_scores).values()) == pytest.approx(1.0)
    assert len(report.image_embedding.split(",")) == 512
    assert report.image_conflict is None  # nothing to compare: text unclassified


def test_same_photo_twice_is_flagged_as_duplicate(db, vision_off):
    photo = _photo_uri()
    first = _add_report(db, "Fire at the warehouse", media_url=photo)
    process_new_report(db, first.id)
    second = _add_report(db, "Huge blaze at warehouse", media_url=photo, lat=19.0761)
    process_new_report(db, second.id)
    db.refresh(second)

    assert second.image_duplicate_of == first.id


def test_vision_crash_does_not_lose_the_report(db, vision_off, monkeypatch, caplog):
    def boom(*args, **kwargs):
        raise RuntimeError("model exploded")

    monkeypatch.setattr(vs, "analyze_image", boom)
    report = _add_report(db, "Flooding near the station", media_url=_photo_uri())
    process_new_report(db, report.id)
    db.refresh(report)

    assert report.incident_id is not None
    assert report.disaster_type == "flood"
    assert "vision analysis failed" in caplog.text


def test_vision_in_fusion_off_gives_original_explanation(db, vision_off, monkeypatch):
    monkeypatch.setattr(settings, "VISION_IN_FUSION", False)
    report = _add_report(db, "Flooding near the station", media_url=_photo_uri())
    process_new_report(db, report.id)
    db.refresh(report)
    explanation = json.loads(db.get(Incident, report.incident_id).fusion_explanation)
    assert set(explanation) == {"n_reports", "mean_source_reliability", "has_contradiction"}


def test_vision_terms_reach_the_incident_explanation(db, monkeypatch):
    monkeypatch.setattr(settings, "VISION_ENABLED", True)
    monkeypatch.setattr(vs, "_model", _fake_model("no_incident"))
    report = _add_report(db, "Flooding near the station", media_url=_photo_uri())
    process_new_report(db, report.id)
    db.refresh(report)

    assert report.image_conflict is True  # text says flood, photo shows nothing
    incident = db.get(Incident, report.incident_id)
    explanation = json.loads(incident.fusion_explanation)
    assert explanation["cross_modal_conflict"] is True
    assert explanation["n_vision_scored"] == 1
    assert explanation["vision_support"] < 0
    assert incident.has_contradiction is True


def test_links_are_not_analysed(db, vision_off):
    report = _add_report(db, "Fire downtown", media_url="https://example.com/fire.jpg")
    process_new_report(db, report.id)
    db.refresh(report)
    assert report.image_model is None and report.image_phash is None


# ---- POST /reports media handling (temp DB, pipeline not run) -------------

@pytest.fixture
def client(db, monkeypatch):
    from fastapi.testclient import TestClient

    from app.auth import get_current_user
    from app.main import app
    from app.routers import reports as reports_router

    user = User(email="citizen@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    app.dependency_overrides[database.get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(reports_router, "process_new_report", lambda session, rid: None)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_post_report_reencodes_photo(client):
    buf = io.BytesIO()
    PIL_Image.new("RGB", (50, 40), (10, 200, 10)).save(buf, format="PNG")
    payload = {"text": "Flood", "latitude": 19.07, "longitude": 72.87,
               "media_url": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()}
    response = client.post("/reports", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["media_url"].startswith("data:image/jpeg;base64,")


def test_post_report_rejects_video(client):
    payload = {"text": "Flood", "latitude": 19.07, "longitude": 72.87,
               "media_url": "data:video/mp4;base64,AAAA"}
    response = client.post("/reports", json=payload)
    assert response.status_code == 415
    assert "Video" in response.json()["detail"]
