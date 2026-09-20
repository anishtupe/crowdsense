# CrowdSense

A Contradiction-Aware Multimodal Evidence Fusion Framework for Real-Time Geospatial Incident Intelligence.

This is a runnable **starter scaffold**, not a finished product. It implements the
architecture layers discussed in the project docs (data ingestion, storage,
AI/NLP + vision stubs, the Incident Intelligence Engine / evidence fusion core,
real-time WebSocket updates, and a minimal React dashboard) so you can build
each piece out incrementally with Claude Code.

## Stack

- **Backend:** Python, FastAPI, SQLAlchemy, GeoAlchemy2 (PostGIS), JWT auth
- **Database:** PostgreSQL + PostGIS (pgvector extension enabled, ready for embeddings)
- **Cache / real-time:** Redis (pub/sub) + native WebSockets
- **AI/ML:** pluggable NLP / vision / geocode services (lightweight fallbacks included
  so the app runs out of the box; swap in real models as you go — see comments)
- **Core research component:** `app/services/duplicate_detection.py`,
  `contradiction_detection.py`, `clustering.py`, `fusion_engine.py` — kept as pure,
  independently unit-tested functions so they're easy to ablate for your experiments
- **Frontend:** React + Vite + Leaflet dashboard

## Quick start

```bash
cp .env.example .env
docker compose up -d db redis          # Postgres+PostGIS and Redis only

cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs for the interactive API docs.

In a second terminal, for the dashboard:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Project layout

```
backend/
  app/
    main.py            FastAPI app, CORS, startup
    config.py           Settings (env vars)
    database.py          SQLAlchemy engine/session
    models.py             ORM models (User, Report, Incident, IncidentEvidence)
    schemas.py             Pydantic request/response models
    auth.py                  JWT + password hashing + role-based dependency
    pipeline.py                Orchestrates: new report -> NLP -> geocode ->
                                dedup -> cluster -> contradiction -> fusion ->
                                incident update -> WebSocket broadcast
    routers/
      auth.py                 /auth/register, /auth/login
      reports.py               POST /reports, GET /reports
      incidents.py              GET /incidents, GET /incidents/{id}
      verification.py            POST /incidents/{id}/verify  (human-in-the-loop)
      ws.py                       WebSocket /ws/incidents
    services/
      nlp_service.py             text classification + embeddings
      vision_service.py           image classification (stub)
      geocode_service.py           place-name -> lat/lon (stub)
      duplicate_detection.py       core research: text+space+time similarity
      contradiction_detection.py    core research: conflicting-report flagging
      clustering.py                  core research: spatiotemporal clustering
      fusion_engine.py                 core research: calibrated confidence score
  tests/                                pytest unit tests for the core services
  init.sql                                enables postgis + pgvector extensions

frontend/
  src/
    App.jsx                 dashboard shell
    components/MapView.jsx    Leaflet map of incidents
    components/IncidentList.jsx  sidebar list with confidence/severity
    api.js                       fetch + WebSocket client

infra/
  Dockerfile.backend, Dockerfile.frontend, nginx.conf

.github/workflows/ci.yml     runs backend tests on push
```

## Where to take this next (see the step-by-step guide)

1. Swap `nlp_service.py` / `vision_service.py` fallbacks for real models
   (sentence-transformers, an ONNX vision model).
2. Wire `pipeline.py` into the `/reports` endpoint as a background task
   (or move it to an ARQ worker once you add Redis-backed queuing).
3. Replace the naive clustering placeholder with true ST-DBSCAN.
4. Build the evaluation harness described in your project report
   (baselines 1-4 vs. proposed, with Precision/Recall/F1/Brier/ECE).
5. Add the citizen-facing report submission UI.

## Tests

```bash
cd backend
pytest -q
```

The fusion engine and duplicate-detection tests run with no external
dependencies (no DB, no network) so they're a good place to start when you
extend the core research logic.
