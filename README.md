# 🌍 CrowdSense

> **Contradiction-Aware Multimodal Evidence Fusion Platform for Real-Time Geospatial Incident Intelligence**

CrowdSense is a final-year Computer Science project that aggregates crowd-sourced incident reports, fuses multimodal evidence (text + image), detects duplicate/contradictory signals, clusters geospatial events, and presents a live map dashboard — all powered by a FastAPI backend with a React/Leaflet frontend.

---

## 📋 Table of Contents

- [Features](#-features)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [Prerequisites](#-prerequisites)
- [Quick Start (Dev Mode)](#-quick-start-dev-mode)
- [Running the Tests](#-running-the-tests)
- [API Reference](#-api-reference)
- [Project Structure](#-project-structure)
- [Demonstrating to Your Teacher](#-demonstrating-to-your-teacher)

---

## ✅ Features

| # | Feature | Status |
|---|---------|--------|
| 1 | **Citizen Report Submission** — text, GPS coordinates, photo/video upload | ✅ Ready |
| 2 | **Duplicate Detection** — cosine-similarity + geo-distance deduplication | ✅ Ready |
| 3 | **Contradiction Detection** — flags conflicting location/type claims | ✅ Ready |
| 4 | **Geospatial Clustering** — DBSCAN-based incident grouping | ✅ Ready |
| 5 | **Evidence Fusion Engine** — confidence, severity & disaster-type voting | ✅ Ready |
| 6 | **Live Map Dashboard** — Leaflet map with colour-coded severity markers | ✅ Ready |
| 7 | **Real-Time WebSocket Updates** — dashboard refreshes automatically | ✅ Ready |
| 8 | **JWT Authentication** — citizen / verifier / analyst / admin roles | ✅ Ready |
| 9 | **Human Verification Gate** — verifier role can approve/reject incidents | ✅ Ready |
| 10 | **SQLite Fallback** — works without PostgreSQL for demo/dev | ✅ Ready |
| 11 | **24 Unit + Integration Tests** — all green | ✅ Passing |

---

## 🏗 System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  React Frontend (Vite)                    │
│  • Live Incident Map (Leaflet)                            │
│  • Citizen Report Form (text + GPS + media upload)        │
│  • Real-Time WebSocket listener                           │
└────────────────────────┬─────────────────────────────────┘
                         │  HTTP /api  +  WS /ws
                         ▼
┌──────────────────────────────────────────────────────────┐
│                  FastAPI Backend                          │
│  /auth    – register / login / JWT tokens                 │
│  /reports – submit & list raw citizen reports             │
│  /incidents – fused, clustered incident objects           │
│  /incidents/{id}/verify – human verification gate         │
│  /ws/incidents – WebSocket broadcast                      │
└────────────────────────┬─────────────────────────────────┘
                         │ SQLAlchemy ORM
                         ▼
┌──────────────────────────────────────────────────────────┐
│          AI Pipeline  (backend/app/pipeline.py)           │
│  1. NLP Service   – text classification (stub→real model) │
│  2. Vision Service – image classification (stub→real)     │
│  3. Duplicate Detection – TF-IDF cosine + geo-distance    │
│  4. Contradiction Detection – location/type conflict      │
│  5. DBSCAN Clustering – spatial+temporal grouping         │
│  6. Fusion Engine – Bayesian evidence aggregation         │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
              SQLite (dev) / PostgreSQL+PostGIS (prod)
```

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, Vite 5, Leaflet / react-leaflet |
| Backend | FastAPI 0.115, Uvicorn |
| ORM | SQLAlchemy 2, GeoAlchemy2 |
| Database | SQLite (dev) / PostgreSQL 15 + PostGIS (prod) |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| AI/ML | scikit-learn (DBSCAN, TF-IDF), NumPy |
| Testing | pytest, HTTPX (async test client) |
| Realtime | WebSockets (built-in FastAPI) |

---

## 📦 Prerequisites

- **Python 3.10+** (tested with 3.12)
- **Node.js 18+** and **npm 9+**
- *(Optional for prod)* PostgreSQL 15 with PostGIS extension

Check your versions:
```bash
python --version
node --version
npm --version
```

---

## 🚀 Quick Start (Dev Mode)

### 1 — Clone & enter the project

```bash
git clone <your-repo-url>
cd crowdsense
```

### 2 — Backend Setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Start the backend:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: **http://localhost:8000**
- Interactive docs (Swagger): **http://localhost:8000/docs**

> **No PostgreSQL?** No problem. The backend automatically falls back to a local SQLite file (`crowdsense.db`) — zero extra setup for demos.

---

### 3 — Frontend Setup

Open a **new terminal**:

```bash
cd frontend
npm install
npm run dev
```

App: **http://localhost:5173**

> Vite proxies `/api/*` → `http://localhost:8000` automatically — no CORS configuration needed.

---

## 🧪 Running the Tests

```bash
cd backend

# Windows
.venv\Scripts\python -m pytest -q

# macOS / Linux
source .venv/bin/activate && pytest -q
```

Expected output:
```
........................                        [100%]
26 passed
```

Tests cover:
- **Duplicate detection** — text similarity + geo-distance thresholds
- **Contradiction detection** — location/type conflict flagging
- **DBSCAN Clustering** — spatial grouping correctness
- **Fusion Engine** — confidence/severity/disaster-type aggregation
- **API Endpoints** — report submission, incident listing, verification gate

---

## 📡 API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/auth/register` | None | Register new user |
| `POST` | `/auth/login` | None | Login, receive JWT |
| `GET` | `/auth/me` | Bearer token | Return the signed-in user and role |
| `POST` | `/reports` | Signed in | Submit citizen report |
| `GET` | `/reports` | None | List all reports |
| `GET` | `/incidents` | None | List all fused incidents |
| `POST` | `/incidents/{id}/verify` | Verifier+ | Approve/reject incident |
| `GET` | `/health` | None | Health check |
| `WS` | `/ws/incidents` | None | Real-time incident stream |

Full interactive docs: **http://localhost:8000/docs**

---

## 📁 Project Structure

```
crowdsense/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry-point
│   │   ├── config.py            # Pydantic settings (env vars)
│   │   ├── database.py          # Engine + SQLite fallback
│   │   ├── models.py            # ORM models (Report, Incident, User)
│   │   ├── schemas.py           # Pydantic I/O schemas
│   │   ├── auth.py              # JWT helpers, role guards
│   │   ├── pipeline.py          # AI pipeline orchestrator
│   │   ├── utils.py             # Shared helpers
│   │   ├── routers/
│   │   │   ├── auth.py          # /auth endpoints
│   │   │   ├── reports.py       # /reports endpoints
│   │   │   ├── incidents.py     # /incidents endpoints
│   │   │   ├── verification.py  # /incidents/{id}/verify
│   │   │   └── ws.py            # WebSocket router
│   │   ├── services/
│   │   │   ├── nlp_service.py         # Text classifier (stub)
│   │   │   ├── vision_service.py      # Image classifier (stub)
│   │   │   ├── duplicate_detection.py # TF-IDF + geo dedup
│   │   │   ├── contradiction_detection.py
│   │   │   ├── clustering.py          # DBSCAN clustering
│   │   │   └── fusion_engine.py       # Evidence fusion
│   │   └── ws/
│   │       └── manager.py       # WebSocket connection manager
│   ├── tests/                   # 24 unit + integration tests
│   ├── requirements.txt
│   └── crowdsense.db            # Auto-created SQLite (dev only)
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Root component + hash routing
│   │   ├── api.js               # Fetch + WebSocket helpers
│   │   ├── styles.css           # Design system
│   │   └── components/
│   │       ├── MapView.jsx      # Leaflet map, severity markers
│   │       ├── IncidentList.jsx # Sidebar incident cards
│   │       └── ReportForm.jsx   # Citizen report submission form
│   ├── index.html
│   ├── vite.config.js           # Dev proxy → backend:8000
│   └── package.json
│
├── docker-compose.yml           # PostgreSQL + PostGIS for prod
├── .env.example                 # Env variable template
└── README.md
```

---

## 🎯 Demonstrating to Your Teacher

### Step 1 — Start both servers (two terminals)

**Terminal 1 — Backend** (activate the Python environment you installed dependencies into):
```powershell
cd backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

If the environment is outside the project folder, run its Python executable directly instead:
```powershell
& "$env:LOCALAPPDATA\CrowdSense\venv312\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Frontend** (from the project root):
```powershell
cd frontend
npm install
npm run dev
```

### Step 2 — Open the app

| URL | What it shows |
|-----|---------------|
| http://localhost:5173 | Live React dashboard |
| http://localhost:8000/docs | Full Swagger API explorer |

### Step 3 — Demo flow (5 minutes)

1. **Register and sign in** — Click *Sign in* → *Create an account*, use an email/password, then submit the form. New accounts receive the citizen role. The dashboard is publicly viewable; report submission requires a signed-in account.

2. **Submit a report** — Click *"📢 Submit Citizen Report"*, enter a description (e.g. "Heavy flooding near Main Street"), click *"📍 Use My Location"* or type coordinates, then submit. A confirmation card with the Report ID appears.

3. **Live map update** — Switch to *"🗺️ Live Incidents Map"*. A colour-coded circle appears for the new incident (red = high severity, orange = medium, green = low). Click the circle to see its details.

4. **Human verification (optional)** — To demonstrate verifier controls locally, first create an account in the app, then promote that account from the backend folder:
   ```powershell
   .\.venv\Scripts\python.exe -c "from app.database import SessionLocal; from app.models import User, Role; db=SessionLocal(); user=db.query(User).filter(User.email == 'your-email@example.com').one(); user.role=Role.verifier; db.commit(); db.close()"
   ```
   Replace the email with the account you registered. Sign out and back in; verifier accounts see Approve/Reject actions for incidents awaiting verification. If using a virtual environment outside the project, substitute its Python executable path.

5. **API Swagger tour** — Open http://localhost:8000/docs and walk through `POST /auth/register`, `POST /auth/login`, `GET /incidents`, and `POST /incidents/{id}/verify`. Use the *Authorize* button to test protected routes.

6. **Run tests live** — In the backend terminal:
   ```bash
   .venv\Scripts\python -m pytest -v
   ```
   The tests cover the API and evidence processing pipeline.

7. **Explain the pipeline** — Submit two nearly-identical reports at the same coordinates; the fusion engine can merge them into one incident with higher confidence. Submit conflicting reports (different disaster types); the `⚠ Conflicting` badge appears in the sidebar.

---

## 🗺️ Road-Map / Future Work

- [ ] Replace stub NLP with `sentence-transformers` fine-tuned model
- [ ] Replace stub Vision with CLIP/ResNet image classifier
- [ ] Add Alembic database migrations
- [ ] Deploy via Docker Compose (PostGIS already wired in `docker-compose.yml`)
- [ ] Analyst role dashboard with contradiction drill-down view
- [ ] Source credibility / reporter reliability scoring

---

## 📄 License

MI
by mohit n anish