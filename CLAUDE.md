# CrowdSense: project context

> This file lives in the **repo root** as `CLAUDE.md`. Claude Code loads it automatically at the start of every session.
> Repo audit done 2026-10-16 against commit `91e2981` (see section 16). Facts below were checked on the team's Windows machine on that date; re-check anything that may have changed since.

## 1. What this project is

**CrowdSense** is a final-year B.E. Computer Engineering major project (VPPCOE&VA, University of Mumbai, academic year 2026-27).
Full title: *CrowdSense: A Contradiction-Aware Multimodal Evidence Fusion Framework for Real-Time Geospatial Incident Intelligence.*
(An earlier working title, "GroundTruth", is retired. Always say CrowdSense.)

It turns noisy, heterogeneous public observations (citizen reports with text, photos, GPS and time, plus public news/RSS/open-data items) into **structured, geolocated incidents** with a **calibrated confidence score**, and shows them on a live map. It is a decision-support tool, not an autonomous emergency system: every AI-detected incident stays labelled "AI Detected - Requires Verification" until a human verifier confirms or rejects it.

It is a general incident platform, not limited to one disaster type.

### The research angle (be honest about it)
- Crisis-informatics papers mostly classify single posts, or fuse text and image *within one post*. Few treat the **incident** as the unit, and few combine duplicate detection, contradiction detection and source reliability in one pipeline.
- Our contribution is **integration plus evaluation**, not new algorithms: contradiction-aware, reliability-weighted fusion at incident level, producing one calibrated confidence per incident.
- Do not overclaim novelty. Our literature search was representative, not exhaustive.
- The research question to test: does contradiction-aware, duplicate-aware fusion improve calibrated incident-level confidence and reduce false-incident inflation compared with simpler baselines?

## 2. Hard rules for you (the agent)

1. **Truthfulness over polish.** Never invent results, metrics, citations, dataset statistics or test outcomes. If you didn't run it, say "not run". The project is unfinished; the report must describe it as it really is.
2. **Verify before claiming done.** Run the tests and start the app before saying something works. Paste real command output when reporting.
3. **Small steps.** One focused change at a time. Don't refactor unrelated code. Summarise what changed, what you tested, and what is still a TODO.
4. **Keep the research modules pure.** `duplicate_detection.py`, `contradiction_detection.py`, `clustering.py`, `fusion_engine.py` must stay free of DB/network dependencies and keep their public function signatures. They are the units we ablate and unit-test.
5. **Every AI feature needs a fallback.** Real models (sentence-transformers, NLI) load lazily; if the package or model is unavailable, fall back to the lightweight version so the app still runs. Free hosting has about 512 MB RAM.
6. **Schema changes need a migration.** There is no Alembic yet and `create_all` never alters existing tables. If you add a column, also provide an idempotent migration that works on **both SQLite/SpatiaLite and Postgres**. Don't use `ADD COLUMN IF NOT EXISTS` on SQLite.
7. **No secrets in git.** `.env` is ignored; document new variables in `.env.example`.
8. **Scraping rules.** Use RSS and open APIs only. Never scrape X, Instagram or Facebook or any login-walled site. Respect robots.txt, rate limits and a descriptive User-Agent. Store headline + snippet + URL only, never full article text or personal data.
9. **Environment.** The team develops on **Windows with PowerShell** (not bash). Give PowerShell commands. The repo may live inside OneDrive, which can cause file-lock and sync problems; if you see odd file errors, mention it.
10. **Commits are made by a teammate.** After each logical change, give a conventional-commit message (`feat:`, `fix:`, `docs:`, `test:`) and a short summary he can paste. Don't assume you can push.
11. Don't add heavy dependencies without asking. Prefer what is already in `requirements.txt` / `package.json`.

## 3. Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, GeoAlchemy2, Shapely |
| Auth | JWT (python-jose) + passlib/bcrypt; roles `citizen`, `verifier`, `analyst`, `admin` |
| Database (local dev) | **Plain SQLite** (`backend/crowdsense.db`), **not** SpatiaLite. `database.py` disables GeoAlchemy's SpatiaLite DDL and registers stub SQL functions (`AsEWKB`, `GeomFromEWKT`, ...) so points are stored as WKB hex; there are no spatial indexes or spatial SQL. The default `DATABASE_URL` is Postgres; if that connection fails the app **silently falls back** to SQLite. |
| Database (target) | PostgreSQL + PostGIS (pgvector optional/planned) |
| Real time | FastAPI WebSocket `/ws/incidents` with an in-memory connection manager (Redis pub/sub planned, not required) |
| NLP | Code for `paraphrase-multilingual-MiniLM-L12-v2` (384-dim, `nlp_service.py`) and `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` (`contradiction_detection.py`) exists with lazy loading and fallbacks (commit `0dd59ef`). **But torch, sentence-transformers and transformers are not installed in the team venv**, so every run so far used the fallbacks: 64-dim hash embeddings, keyword type classifier, severity-word contradiction heuristic. "Zero-shot" type classification = cosine between the text embedding and six label descriptions (same embedder), not an NLI zero-shot model. |
| Vision | CLIP ViT-B/32 vision tower, **int8 ONNX** (`Xenova/clip-vit-base-patch32` @ `d15189d7`, 89 MB, sha256-checked) run with **onnxruntime + Pillow, no torch**. Zero-shot over the text labels + `no_incident` using precomputed prompt embeddings (`app/services/vision_prompts.npz`). Off unless `VISION_ENABLED=true` and the model is downloaded (`scripts/fetch_vision_model.py`); otherwise a neutral fallback. Accuracy **not evaluated**. |
| Clustering | scikit-learn DBSCAN on a precomputed space+time distance matrix |
| Ingestion | **Not in this repo.** No fetchers, `sources.yaml`, scheduler, `/ingest` endpoints or `migrate_ingest.py` exist at `91e2981`. The Copilot session's work was never merged here (it may exist in another clone). |
| Frontend | React + Vite + **MapLibre GL** (migrated from Leaflet), redesign in progress |
| Tests | pytest (team venv is Python 3.12.0; CI workflow uses Python 3.11) |
| Infra (written, mostly untested) | Dockerfiles, docker-compose, nginx.conf, GitHub Actions CI |

## 4. Architecture (data flow)

```
Citizen app / public sources (RSS, GDELT, Reddit API)
        -> FastAPI ingestion (validate, normalise)
        -> Report row stored (text, media_url, GPS point, timestamp, source, reliability)
        -> NLP: disaster type, sentiment, embedding   (+ vision if media)
        -> Duplicate detection against recent nearby reports
        -> Spatiotemporal clustering (DBSCAN, combined metric)
        -> Contradiction check inside each cluster
        -> Evidence fusion -> incident confidence + severity
        -> Incident upsert  (status = "AI Detected - Requires Verification")
        -> Human verification (/incidents/{id}/verify)  -> Verified / Rejected
        -> WebSocket push -> dashboard map
```

Orchestrator: `backend/app/pipeline.py::process_new_report(db, report_id)`. `POST /reports` runs it as a FastAPI `BackgroundTask`.
Candidate window: reports from the previous 6 hours. A report that falls in no cluster (label -1) becomes a single-report incident, never a dropped one.

## 5. Repo layout (from `git ls-files` at `91e2981`)

The git repo root is the inner `crowdsense/` folder (OneDrive path `Desktop\major project\crowdsense\crowdsense`).

```
backend/
  app/
    main.py config.py database.py models.py schemas.py auth.py pipeline.py utils.py
    routers/   auth.py reports.py incidents.py verification.py ws.py
    services/  nlp_service.py vision_service.py geocode_service.py
               duplicate_detection.py contradiction_detection.py clustering.py fusion_engine.py
    ws/manager.py
    media.py migrations.py                     (added with vision)
    services/vision_prompts.npz                (precomputed CLIP label embeddings, 31 KB)
  tests/       conftest.py test_duplicate_detection.py (8) test_fusion_engine.py (7)
               test_contradiction_detection.py (4) test_clustering.py (4)
               test_api_endpoints.py (5) test_nlp_service.py (4, skipped without sentence-transformers)
               test_vision_service.py test_image_hash.py test_vision_model.py test_media.py
               test_migrations.py test_pipeline_vision.py test_fusion_vision.py   (vision; skip without Pillow)
  scripts/check_embeddings.py   (prints a cosine-similarity matrix for sample sentences)
  scripts/fetch_vision_model.py scripts/build_vision_prompts.py
  models/                       (downloaded model files, git-ignored)
  init.sql  requirements.txt
  crowdsense.db                 (SQLite dev DB, COMMITTED; see gotchas)
  .venv312/                     (Windows virtualenv, ~6,040 files, COMMITTED; see gotchas)
frontend/src/  App.jsx main.jsx api.js styles.css
               components/ AIInsights AdminDashboard AuthForm IncidentDetails IncidentList MapView ReportForm (.jsx)
infra/         Dockerfile.backend Dockerfile.frontend nginx.conf
docs/images/   README screenshots
docker-compose.yml  .env.example  .github/workflows/ci.yml  Makefile  README.md  CLAUDE.md
```
Not present: `backend/app/ingest/`, `routers/ingest.py`, `migrate_ingest.py`, Alembic.

## 6. Data model

- **User**: id, email, hashed_password, role. Registration always creates `citizen`; to test verification, promote a user in the DB (`UPDATE users SET role='admin' WHERE email=...`).
- **Report**: reporter_id, text, media_url, source (`citizen|social|news|historical`), `location` (Point, SRID 4326), reported_at, disaster_type, sentiment, embedding (**stored as a comma-separated string**, not a vector column; the model comment says "JSON-encoded" but the code joins with commas), source_reliability (default 0.5, never set per source in code), incident_id. **No** `source_url` / `source_name` / `content_hash` columns.
  - `media_url` is **not a URL** for citizen uploads: the frontend sends a base64 data URI inside the JSON body. Since the vision work, `app/media.py` validates it in `POST /reports` (JPEG/PNG/WebP only, checked from the bytes; ≤ `MEDIA_MAX_BYTES` 5 MB; ≤ 40 MP), applies EXIF orientation, resizes to ≤ `MEDIA_MAX_SIDE` 1600 px and **re-encodes to JPEG with all EXIF/ICC stripped**; the stored value is that clean `data:image/jpeg;base64,...`. Video → 415. EXIF is never read for any other purpose. http(s) links are stored as-is and **never fetched** (no vision). Reports stored before this change still hold their original, unsanitised data URIs.
  - **Image evidence columns** (all NULL without an uploaded photo): `image_model` (model id, or `"fallback"` = no vision evidence), `image_label`, `image_scores` (JSON {label: p}), `image_embedding` (comma-separated, 512-dim), `image_text_consistency` (P(image = the report text's label)), `image_conflict`, `image_phash` (16 hex), `image_duplicate_of` (earlier report with the same photo).
- **Incident**: disaster_type, centroid (Point), confidence, severity, has_contradiction (**text contradiction OR photo-vs-text conflict**), `fusion_explanation` (JSON, every fusion term; returned by `GET /incidents`), status (`AI Detected - Requires Verification` | `Verified` | `Rejected`), verified_by_id, timestamps.
- **Migrations:** `app/migrations.py` adds the columns above to existing tables (plain `ALTER TABLE ... ADD COLUMN` only when missing; SQLite + Postgres). It runs at startup and via `python -m app.migrations`. Tested on temp SQLite DBs and a copy of the dev DB; **not tested on Postgres**. Add every new column to `ADDED_COLUMNS` as well as `models.py`.
- **GeocodeCache**: does **not** exist.

## 7. Core algorithms (initial defaults; hand-set, NOT yet tuned or calibrated)

- **Distance:** haversine, metres.
- **Duplicate:** a pair is a duplicate only if cosine similarity of embeddings ≥ 0.82 **and** distance ≤ 500 m **and** time gap ≤ 120 min. **Actual value is 0.50**, in both `config.py` and `.env.example` (not 0.82). Neither value has been tuned; retune once real embeddings are installed.
- **Clustering:** combined distance `D = sqrt(d_space² + (λ·Δt)²)` with `λ = eps_m / eps_min`; DBSCAN `eps = 750 m`, time scale 180 min, `min_samples = 2`.
- **Contradiction:** pairwise inside a cluster. Uses multilingual NLI (both directions) when `transformers` is installed, else the heuristic that flags opposite severity language ("collapsed/trapped" vs "contained/safe"). The team venv currently runs the heuristic. Any contradicting pair sets `has_contradiction = true`.
- **Fusion:** `confidence = sigmoid(w0 + w1·ln(1+n) + w2·mean_reliability + w3·contradiction [+ w4·vision_support + w5·cross_modal_conflict])` with `w = (-1.0, 1.1, 1.8, -2.2, 0.8, -1.2)` (all hand-set; **w4, w5 untuned**, labelled so in the explanation). Every intermediate term is returned in `FusionResult.explanation` so ablations are possible.
  - Vision terms only apply when `fuse_evidence(..., vision=VisionSignals(...))` is passed; `vision=None` gives exactly the original result (tested). The pipeline passes it when `VISION_IN_FUSION=true`.
  - `vision_support` = mean over reports **with model scores** of P(fused type) − P(no_incident) (P(any disaster) if the type is unknown). Fallback/no-photo reports are left out, so a missing model is never negative evidence.
  - `cross_modal_conflict` = any scored photo with P(text's label) < 0.15 while its top class (another type or `no_incident`) is ≥ 0.5 (`VISION_CONFLICT_LOW/HIGH`, untuned).
  - With image dedup on, `n` becomes `n_effective` = reports minus reposted photos (pHash Hamming distance ≤ `VISION_PHASH_MAX_DISTANCE` = 8 of 64 bits, untuned).
  - Ablation flags: `VisionSignals.use_scores`, `VisionSignals.use_image_dedup`, and `VISION_IN_FUSION` for "remove vision" as a whole.
- **Vision (per photo):** CLIP preprocessing (shortest edge 224 bicubic, centre crop, CLIP mean/std), image embedding · prompt-group embeddings × 100 (CLIP logit scale), softmax over 12 prompt groups, summed per label (`no_incident` has 6 groups). The image label only replaces the text label when the text is `unclassified`/`unknown` and the image's top label is a disaster type with p ≥ 0.5 (`VISION_MIN_LABEL_CONFIDENCE`). Prompts are hand-written, untuned.
- **Severity (placeholder):** `1 - exp(-sum(reliability)/3)`. Disaster type: majority vote.
- **Source reliability:** per-source constant; news should rank below eyewitness citizen reports. Weights are tunable and untrained.

## 8. API surface

Confirmed from `/openapi.json` on 2026-10-16:
`POST /auth/register`, `POST /auth/login` (form fields `username`, `password`), `GET /auth/me`; `POST /reports` (**requires a bearer token**, 401 without), `GET /reports?limit=`; `GET /incidents?limit=`, `GET /incidents/{id}`; `POST /incidents/{id}/verify` (verifier/analyst/admin); `WS /ws/incidents`; `GET /health`.
- **No `/ingest/*` endpoints** and **no file-upload endpoint**. Images travel as base64 data URIs in the `media_url` field of the `POST /reports` JSON body; bad media returns 413/415/422 with a readable `detail`.
- **The WebSocket broadcast is still never called.** `routers/reports.py::_run_and_broadcast` gets the incident id from `process_new_report` and discards it; nothing calls `manager.broadcast`. The dashboard only updates by polling.
- `ReportOut` includes the `image_*` fields (not the embedding); `IncidentOut` includes `fusion_explanation`.

## 9. Status and known issues (audited 2026-10-16)

| Area | Status |
|---|---|
| Backend scaffold, auth/roles, report/incident/verify endpoints | Runs. `uvicorn` started; `/health` returns `{"status":"ok"}`, `/docs` 200, `/incidents` returned 16 incidents, `/reports` 18 reports from the committed dev DB. |
| Tests | Audit (before vision): **26 passed, 4 skipped** with `backend\.venv312`. After vision: **84 passed, 4 skipped** in a venv with Pillow + onnxruntime + the downloaded model (the 4 = `test_nlp_service.py`, no sentence-transformers); **51 passed, 8 skipped** in `.venv312`, where the Pillow-dependent test files skip. New tests use temp SQLite DBs; one optional test runs the real model and checks output shape only. |
| Real embeddings / NLI / zero-shot classification | Code merged (`0dd59ef`) but **not active**: `len(nlp_service.embed("test")) == 64`, `_get_model()` and `_get_nli_pipeline()` both return `None`. torch / sentence-transformers / transformers are listed in `requirements.txt` but not installed in `.venv312`. The MiniLM model is in the user's HF cache (`~\.cache\huggingface\hub`), so some other environment once loaded it. |
| Vision (2026-10-16) | Built: `vision_service.py`, `media.py`, migrations, pipeline wiring, fusion terms. **Measured** (Windows laptop, `%USERPROFILE%\.venvs\crowdsense312`): server working set **376–377 MB, peak 392–393 MB** with the model loaded (175 MB without); 38–64 ms per image after warm-up; model load 0.4 s. End-to-end run: a report with text "flood" + a dashboard screenshot got `image_label=no_incident` (p=0.99), `image_conflict=true`, confidence 0.209 instead of 0.660; reposting it set `image_duplicate_of`. **Accuracy not evaluated** (needs a labelled set, e.g. CrisisMMD). The 6 old dev reports labelled `"unclassified_media"` by the former stub were left as they are. Linux/Render memory not measured; 512 MB looks tight. |
| Duplicate merging | Observed, root cause not established: the dev DB has 16 incidents with `report_count = 1` each, including 3 flood incidents within ~5 m of each other, so dedup/clustering did not merge them. Likely factors to check: hash embeddings vs the 0.50 threshold, and clustering only runs over the new report plus its duplicates (`pipeline.py:97`). |
| Public-source ingestion | **Not in this repo** (see section 3). |
| MapLibre dashboard | **Invisible-dots bug fixed 2026-10-16.** Root cause (seen in headless Chrome): `MapView.jsx` passed a `<canvas>` element to `map.addImage` for the conflict-ring icon; MapLibre throws `RangeError: mismatched image size`, and since that ran before `addSource`/`addLayer`, no incident layer was ever created (and when it threw inside a React effect, the whole page went blank). Fix: pass `context.getImageData(...)`. Verified in dark and light themes: 16 incidents render as clusters (5 San Francisco, 11 Mumbai). The fork copy and the committed `HEAD` still have the bug. The light style's glyph server has no `Open Sans Bold`, so cluster counts fall back to a locally rendered font (warning only). |
| Rate limiting, audit logging | **Not implemented.** |
| Pipeline logging | Added with the vision work: `crowdsense.*` INFO logs for each pipeline step, and a full traceback if the background task fails. |
| Evaluation harness / baselines / metrics | **Not started** |
| Hosting | **Not done** (see section 11) |
| Project report (LaTeX, college format) | In progress, separate from this repo |

Known gotchas:
- **Committed virtualenv and DB.** `backend/.venv312/` (~6,040 files) and `backend/crowdsense.db` (~5 MB, contains base64 images) are tracked by git. `.gitignore` only ignores `.venv/` and `venv/`. Untracking them (`git rm -r --cached`) is a decision for the team; it is not done.
- **Tests write to the dev DB.** `test_api_endpoints.py` uses the app's real engine, so `pytest` adds users/reports to `backend/crowdsense.db` and makes git show it modified. Restore with `git restore backend/crowdsense.db`, and consider pointing tests at a temp DB.
- **Wrong Python on PATH.** Plain `python` resolves to **3.8.10** via pyenv-win. Use `.venv312\Scripts\python.exe` or `py -3.12`.
- **Local Postgres rejects the default credentials.** Something is listening on port 5432 but `crowdsense/crowdsense` fails authentication, so the backend logs a warning and falls back to SQLite. Set `DATABASE_URL=sqlite:///./crowdsense.db` in `.env` to make this explicit. (Before 2026-10-16 a direct `sqlite:` URL crashed queries with `no such function: AsEWKB`, because the probe connection was reused; fixed in `database.py`.)
- **Don't `pip install` into `.venv312`.** It is committed, so installs add hundreds of changed files to git. Use a venv outside the repo and OneDrive, e.g. `%USERPROFILE%\.venvs\crowdsense312`.
- **Model files and OneDrive.** `scripts/fetch_vision_model.py` saves to `VISION_MODEL_DIR` (default `backend/models/`, git-ignored but **inside OneDrive**: 89 MB, or ~330 MB with `--with-text`). Point `VISION_MODEL_DIR` outside OneDrive to avoid syncing it.
- **Duplicate photos don't merge incidents yet.** In the end-to-end run the reposted photo was flagged (`image_duplicate_of`), but the two reports still became separate incidents, because the text/space/time dedup didn't match them (see "Duplicate merging"). `n_effective` therefore only matters once reports cluster; it is covered by unit tests, not yet seen end-to-end.
- **`localhost` can hang** in PowerShell (`Invoke-RestMethod` tries `::1` first and uvicorn binds 127.0.0.1). Use `http://127.0.0.1:8000`.
- **Schema drift.** `create_all` never alters existing tables. Adding a model column without also adding it to `app/migrations.py` breaks existing DBs (seen before as `no such column: reports.source_url`). Alembic would still be better long-term.
- **Embedding dimension change.** `cosine_similarity` returns 0.0 when vectors differ in length. When real 384-dim embeddings are switched on, the stored 64-dim ones stop matching; re-embed existing reports or reset the dev DB.
- `infra/Dockerfile.frontend` line 10 has `COPY ../infra/nginx.conf` with build context `./frontend`; Docker rejects paths outside the context. Not yet fixed.
- First run of real models downloads them (the NLI model is about 1 GB).

## 10. Commands (PowerShell, from repo root)

```powershell
# backend
cd backend
py -3.12 -m venv $env:USERPROFILE\.venvs\crowdsense312   # NOT plain `python` (3.8 here); outside repo + OneDrive
& $env:USERPROFILE\.venvs\crowdsense312\Scripts\Activate.ps1
pip install -r requirements.txt   # note: this includes torch/transformers (~1 GB); omit those 3 lines for the fallback-only setup
uvicorn app.main:app --reload --port 8000     # API docs at http://127.0.0.1:8000/docs
pytest -q
git restore crowdsense.db                     # test_api_endpoints.py writes to the committed dev DB

# vision (optional): download the model, then set VISION_ENABLED=true in .env
python scripts/fetch_vision_model.py          # 89 MB, sha256-checked
python -m app.migrations                      # also runs automatically at startup

# frontend
cd frontend
npm install
npm run dev                      # http://localhost:5173
npm run build

# quick data check
Invoke-RestMethod http://127.0.0.1:8000/incidents | Select-Object id, latitude, longitude, status, report_count
```

Config lives in `.env` (see `.env.example`): `DATABASE_URL`, `JWT_SECRET`, `CORS_ORIGINS`, dedup/cluster thresholds, `GOOGLE_MAPS_API_KEY` (optional).

## 11. Hosting plan (free tier)

- Frontend: Vercel or Netlify (HTTPS is required for the browser geolocation feature).
- Backend: Render free web service. About 512 MB RAM, sleeps when idle, no background workers, so deploy with a **slim requirements file** (no torch/transformers) and rely on the fallbacks.
- Database: Neon (PostGIS) rather than Render's free DB, which expires.
- Frontend needs `VITE_API_URL` instead of the hard-coded `/api` proxy and `ws://localhost`.
- For a viva demo with the real AI: run the backend on the laptop and expose it with a Cloudflare Tunnel.
- Free-tier terms change; confirm on the providers' pages.

## 12. Geocoding policy

Citizen reports carry GPS, so geocoding matters mainly for news/RSS items. Default to **Nominatim** (1 request per second, descriptive User-Agent, cache results). Google Geocoding is optional behind `GOOGLE_MAPS_API_KEY`; its terms restrict caching/storing results and expect Google maps, so don't use it for experiment data.

## 13. Suggested backlog (do in this order, one at a time)

1. **Audit** the repo and update sections 5, 8 and 9 of this file (see below).
2. Get `pytest -q` green on the real machine; fix whatever is broken.
3. Fix the invisible map dots, with evidence at each step.
4. Introduce Alembic (or keep a tested migration script) so schema changes stop breaking dev databases.
5. Add logging to the pipeline; wire the WebSocket broadcast after `process_new_report`.
6. Confirm or finish real embeddings, NLI contradiction and zero-shot type classification, each with a fallback and tests; retune the dedup threshold on real similarity numbers.
7. Verify feed URLs one by one, enable one source, run an ingestion cycle, review the skip reasons.
8. Build the evaluation harness (below).
9. Prepare for deployment (slim requirements, env-based API URL, Render/Vercel/Neon config).
10. Citizen report submission UI (text, photo/video upload, "use my location").

## 14. Evaluation plan (to implement; no results exist yet)

Compare, on a labelled set of reports (synthetic scenarios the team generates, plus public datasets such as CrisisMMD where suitable):
- B1 citizen reports only; B2 + NLP; B3 + NLP + geospatial clustering; B4 + NLP + vision + GIS; **Proposed** = + public sources + duplicate detection + contradiction-aware fusion.
- Metrics: precision, recall, F1, PR-AUC, Brier score, Expected Calibration Error, clustering quality, false-incident rate (incident inflation), detection latency.
- Ablations: remove NLP, vision, GIS, duplicate detection, contradiction detection, source reliability, temporal term, public-source data, one at a time.
- Report numbers exactly as measured. If a result is weak or negative, report it as such.

## 15. Documents that exist outside the repo

- Literature survey table (14 papers), architecture diagram/flowchart and a 13-slide presentation, built in a chat session.
- **Citation corrections.** The first survey table had wrong authors for three papers. Correct entries: (1) Hanny, Schmidt, Gandhi, Granitzer, Resch, *Big Earth Data* 2025, doi 10.1080/20964471.2025.2572140; (2) El-Niss, Alzu'bi, Abuarqoub, ICFNDS '23 (ACM), doi 10.1145/3644713.3644840; (6) Mandal, Khanal, Caragea, WWW '24, doi 10.1145/3589334.3648143. Also verified: Shaik et al., IPTA 2025, doi 10.1109/IPTA66025.2025.11222034; Senarath et al., arXiv:2011.05440. Authors still to verify: the CEFN paper (*Computer Speech & Language* 92, 101784) and Fuzzy-MSF (*Information Fusion*, 2026).
- The five references on the old presentation's last slide could not be verified; do not copy them into the report.
- Development used AI coding assistants (Antigravity IDE, GitHub Copilot, Claude). Keep that disclosed per college policy.

## 16. First task (audit)

**Done 2026-10-16** against `91e2981`; results are in sections 3, 5, 6, 7, 8 and 9. Re-run it if the repo has moved on a lot.

1. Run `git log --oneline -30` and `git ls-files`; compare against sections 5 and 8.
2. Run `pytest -q` and report the real result.
3. Start the backend, then check `/health`, `/docs` and `/incidents`; report errors.
4. Check `len(nlp_service.embed("test"))` and the `DEDUP_TEXT_SIMILARITY_THRESHOLD` in `config.py`.
5. Rewrite sections 5, 8 and 9 of this file so every **VERIFY** is resolved, then show me the diff.
Do not start new features until this audit is done.
