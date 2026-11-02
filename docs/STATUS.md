# CrowdSense: repository status audit

Tags: [VERIFIED] = ran it or read the code; [NOT RUN] = not executed (reason given); [UNKNOWN] = could not determine.
Paths are relative to the repo root. Line numbers refer to the working copy on the audit date.

## 1. Snapshot

- Audit date: 2026-10-24, Windows 11, PowerShell. [VERIFIED]
- Branch: `main`. Latest commit: `91e2981ff4a2701e973973f9d3c17c3a7c785194` "Merge pull request #8 from anishtupe/feature/auth-and-demo". [VERIFIED]
- Uncommitted work on top of it: 20 modified tracked files (+653/-51 lines) and 13 untracked files. The entire vision feature (`backend/app/media.py`, `backend/app/migrations.py`, `vision_prompts.npz`, 3 scripts, 7 test files), the pipeline logging and the map-dots fix exist **only in the working copy**, not in any commit. [VERIFIED]

Recent history (`git log --oneline -20`, trimmed): [VERIFIED]
```
91e2981 Merge pull request #8 ...        45e1864 added refrance images in readme.md
6c4d82d some changes in readme           6aed56f Merge pull request #7 ...
2aed036 feat(frontend): redesign dashboard and stabilize map markers
0dd59ef feat(ai): add multilingual embeddings, NLI contradiction detection, and zero-shot classification
ad4d2f8 changed map api from leaflet to maplibr
26951c7 Added authenticated admin and AI insights dashboards
615b70f Added JWT login and protect report submission
8bd8618 made changes in the citizen reporting on the server side
e2a886b chore(backend): update local sqlite dev database with demo records
cb69e38 fix(backend): update numpy and psycopg2-binary for Python 3.13 compatibility
(+ merge commits and early readme commits)
```

Summary: CrowdSense is a working prototype of the plumbing (auth, report submission, a synchronous AI pipeline, incident API, MapLibre dashboard) with all four research modules implemented as pure functions and unit-tested. Tests pass with no failures. But the "intelligence" runs almost entirely on fallbacks: 64-dim hash embeddings, keyword classification and a severity-word contradiction heuristic, because torch/sentence-transformers/transformers are not installed. Only the CLIP vision model actually loads. Fusion weights are hand-set; nothing is learned or calibrated. There is no ingestion of public sources, no comparability gate, no source-reliability model, no evaluation harness, no Alembic, and Postgres has never been exercised. The dev data is 19 citizen reports and 17 incidents in SQLite. Much of the recent work is uncommitted.

## 2. What works [VERIFIED]

- `pytest -q`: **84 passed, 4 skipped, 0 failed** in `%USERPROFILE%\.venvs\crowdsense312` (Python 3.12.0).
- uvicorn starts; `/health` returns `{"status":"ok"}`; `/docs` returns 200; `/incidents` returns 17 incidents; `/reports` returns 19 reports.
- Auth gates: `POST /reports` and `POST /incidents/{id}/verify` return 401 without a token; unknown incident returns 404.
- `WS /ws/incidents` accepts a connection (server log: `"WebSocket /ws/incidents" [accepted]`), but no message arrives (see section 3).
- Text/space/time duplicate detection does merge identical texts: 2 incidents hold 2 reports each, both pairs with the identical text "Severe wildfire burning near forest perimeter".
- CLIP ViT-B/32 int8 ONNX loads (`vision_service._get_model()` returns `_ClipModel`); one dev report has vision fields filled (`image_model=clip-vit-b32-int8`, `image_label=flood`).
- Idempotent column migration (`backend/app/migrations.py`) runs at startup without error on the dev DB.
- `npm run build` succeeds (`✓ built in 6.63s`); only a chunk-size warning (JS bundle 1,264 kB, 352 kB gzip).
- Map marker code uses `[longitude, latitude]` order (`frontend/src/components/MapView.jsx:53`); the `addImage` crash is fixed in the working copy (`MapView.jsx:169-172`, uses `getImageData`).

## 3. What's broken

| Symptom | Cause | Where | Tag |
|---|---|---|---|
| Dashboard never gets live pushes; it polls every 10 s | `_run_and_broadcast` gets `incident_id` and discards it; `manager.broadcast` is never called anywhere | `backend/app/routers/reports.py:56-67`; poll at `frontend/src/App.jsx:145` | [VERIFIED] |
| Near-identical reports usually stay separate incidents (dev DB: 15 of 17 incidents have 1 report; 6 flood incidents) | Clustering runs only over the new report plus its text-duplicates, so with no duplicate the report is always a singleton (label -1). Hash embeddings rarely reach 0.50 cosine for paraphrases | `backend/app/pipeline.py:154-168` | [VERIFIED] code; root-cause share not measured |
| Clustering adds nothing beyond dedup | Duplicates are already ≤500 m and ≤120 min, so their combined distance is ≤ sqrt(500² + (120·750/180)²) ≈ 707 m < eps 750 m: DBSCAN always groups them | `pipeline.py:154`, `clustering.py:54-64` | [VERIFIED] by arithmetic from code |
| Incident score ignores reports already in the incident | Upsert reuses the first existing incident but recomputes confidence from `fused_group` only; other reports of that incident are not included, and two existing incidents are never merged | `pipeline.py:193-225` | [VERIFIED] code, not exercised |
| Incident centroid is the latest report's point, not a centroid | Explicit simplification | `pipeline.py:221` | [VERIFIED] |
| Mixed embedding dimensions in the dev DB (16 x 64-dim, 3 x 384-dim) | Some earlier environment ran real MiniLM against this DB; `cosine_similarity` returns 0.0 for unequal lengths, so these can never match | DB; `duplicate_detection.py:41` | [VERIFIED] |
| Pipeline would crash if sentence-transformers is installed but the model can't download (offline) | `_get_model()` catches only `ImportError` | `backend/app/services/nlp_service.py:108-114` | [VERIFIED] code; [NOT RUN] |
| DB-selection log line is invisible and wrong | Engine is built at import time, before `logging.basicConfig` in `main.py:13`, so the INFO line is dropped; it also says "PostgreSQL/PostGIS" even for a SQLite URL; the fallback WARNING prints the full `DATABASE_URL` including password | `backend/app/database.py:15-35` | [VERIFIED] code; startup log showed no DB line |
| SQLite path depends on the working directory | `sqlite:///./crowdsense.db` is relative; starting uvicorn from the repo root would create a new empty DB there | `database.py:31`, `.env` | [VERIFIED] code; [NOT RUN] |
| `docker compose up` cannot start the backend as written | `env_file: .env` expects a root `.env`, which does not exist (only `backend/.env`); inside the container `localhost:5432` is not the db service, so it would silently fall back to SQLite | `docker-compose.yml:27` | [VERIFIED] file check; [NOT RUN] docker |
| Frontend Docker build fails | `COPY ../infra/nginx.conf` is outside build context `./frontend` | `infra/Dockerfile.frontend:10` | [VERIFIED] code; [NOT RUN] |
| Backend image would include the committed venv and dev DB | No `.dockerignore`; `COPY . .` | `infra/Dockerfile.backend:12` | [VERIFIED] |
| Tests modify the committed dev DB | `test_api_endpoints.py` uses the app's real engine | `backend/tests/test_api_endpoints.py:6-11` | [VERIFIED] (DB was backed up and restored for this audit; SHA-256 identical before/after) |

## 4. Placeholders and fallbacks currently in use

All [VERIFIED] by running the check in section 10 and reading code.
- Text embedding: 64-dim MD5 hash bag-of-tokens (`nlp_service.py:118-134`).
- Disaster type: keyword match over 6 types (`nlp_service.py:47-52`). Example: "Water is rising on the street near the station" returns `unclassified`.
- Sentiment: word counts (`nlp_service.py:89-99`).
- Contradiction: severity-word heuristic (`contradiction_detection.py:30-31, 89-92`). No attribute, time or space check.
- Fusion: hand-set logistic weights (`fusion_engine.py:27`).
- Severity: `1 - exp(-sum(reliability)/3)` (`fusion_engine.py:134-143`).
- Source reliability: constant 0.5 for every report (column default, `models.py:69`; all 19 dev reports are `citizen`, 0.5).
- Geocoding: both functions return `None`; module is not imported anywhere (`backend/app/services/geocode_service.py:15-22`).
- Centroid: latest report's location (`pipeline.py:221`).
- Vision: real model when `VISION_ENABLED=true` and files present (both true on this machine); otherwise `fallback` result with no evidence.

## 5. Test results

`pytest -q -rs` in `%USERPROFILE%\.venvs\crowdsense312` [VERIFIED]:
```
SKIPPED [1] tests\test_nlp_service.py:5: could not import 'sentence_transformers': No module named 'sentence_transformers'
... (same for lines 14, 23, 30)
84 passed, 4 skipped, 63 warnings in 22.60s
```
`pytest -q` in committed `backend\.venv312` [VERIFIED]: `51 passed, 8 skipped, 22 warnings in 21.29s` (Pillow-dependent files skip).
Failures: none. Warnings are deprecations (`datetime.utcnow`, FastAPI `on_event`, Pydantic class `Config`).

Tests per file (88 collected): api_endpoints 5, clustering 4, contradiction_detection 4, duplicate_detection 8, fusion_engine 7, fusion_vision 10, image_hash 4, media 13, migrations 4, nlp_service 4, pipeline_vision 10, vision_model 6, vision_service 9. [VERIFIED]

Not run: CI on GitHub (Python 3.11, installs full `requirements.txt` incl. torch). With transformers installed, the 4 contradiction tests would call the real NLI model (they don't force the heuristic) and download ~1 GB; outcome [UNKNOWN].

## 6. API routes

From `/openapi.json` plus manual checks, server on 127.0.0.1:8000 [VERIFIED]:

| Method | Path | Auth | Works? |
|---|---|---|---|
| POST | /auth/register | none (always creates `citizen`) | not called this audit; covered by tests |
| POST | /auth/login | none (form `username`, `password`) | covered by tests |
| GET | /auth/me | bearer | covered by tests |
| POST | /reports | bearer | 401 without token confirmed; success path covered by tests |
| GET | /reports?limit= | **none** | yes, 19 rows; returns full base64 photos and report text publicly |
| GET | /incidents?limit= | none | yes, 17 rows |
| GET | /incidents/{incident_id} | none | 404 for unknown id confirmed |
| POST | /incidents/{incident_id}/verify | bearer + role verifier/analyst/admin | 401 without token confirmed |
| WS | /ws/incidents | none | connects; never sends anything |
| GET | /health | none | yes |

No `/ingest/*` routes, no file-upload route, no rate limiting, no audit log. [VERIFIED]

## 7. Data model

Source: `backend/app/models.py`, confirmed against the dev DB's `PRAGMA table_info`. [VERIFIED]

- **users** (10 rows, all `citizen`): id (UUID str), email (unique), hashed_password, role (`citizen|verifier|analyst|admin`), created_at.
- **reports** (19 rows): id, reporter_id -> users, text, media_url (base64 data URI for uploads; 8 rows have one), source (`citizen|social|news|historical`, client-supplied, default `citizen`), location (POINT 4326, stored as WKB hex on SQLite), reported_at, disaster_type, sentiment, embedding (comma-separated text), source_reliability (float, default 0.5), incident_id -> incidents, image_model, image_label, image_scores (JSON text), image_embedding (comma-separated, 512-dim), image_text_consistency, image_conflict, image_phash (16 hex), image_duplicate_of.
- **incidents** (17 rows, all `ai_detected`): id, disaster_type, centroid (POINT), confidence, severity, has_contradiction, fusion_explanation (JSON text; filled on 1 row), status, verified_by_id -> users, created_at, updated_at.
- Missing vs target: no claim/attribute table, no source table, no per-source reliability counts, no source_url/source_name/content_hash, no ground-truth label column, no geocode cache.

Database actually used: `config.py:5` defaults to Postgres; `.env.example` also says Postgres; `backend/.env` sets a `sqlite:` URL (value not printed). The running app used SQLite `backend/crowdsense.db`. Plain SQLite, not SpatiaLite: spatial functions are Python stubs (`database.py:58-66`), no spatial index or spatial SQL. [VERIFIED]
Migrations: `backend/app/migrations.py` adds 9 listed columns if missing (tested on SQLite; [NOT RUN] on Postgres). **No Alembic.** `backend/init.sql` enables `postgis` and `vector` for the compose Postgres. [VERIFIED]

## 8. Pipeline as it runs today

`backend/app/pipeline.py::process_new_report(db, report_id)`, run as a FastAPI `BackgroundTask` from `routers/reports.py:67`. [VERIFIED by code; INFO logs at each step]

1. Load report; warn and return if missing (`:94-97`). Real.
2. NLP (`:100-105`): type, sentiment, embedding. **Fallback** (keywords, word counts, 64-dim hash).
3. Vision (`:109-112`, `_analyze_media`): only for stored data-URI photos; CLIP scores, label, consistency, conflict, pHash; can override `unclassified` text type. **Real** model here; failure is logged and skipped. Commit.
4. Candidates (`:121-128`): all reports in the previous 6 h, **any type and any distance** (comment at `:117` says "same disaster type"; no such filter).
5. Photo dedup (`:132-140`): pHash Hamming ≤ 8 sets `image_duplicate_of`. Real.
6. Text/space/time dedup (`:142-151`): cosine ≥ 0.50 AND ≤ 500 m AND ≤ 120 min. Real logic, fallback embeddings.
7. Clustering (`:154-168`): DBSCAN over new report + duplicates only; noise becomes a single-report incident. Effectively redundant (section 3).
8. Contradiction (`:171`): all pairs in the group, heuristic. **No comparability gate.**
9. Fusion (`:175-191`): logistic with hand-set weights, plus vision terms when `VISION_IN_FUSION=true`; `n_effective` subtracts reposted photos. Placeholder weights.
10. Incident upsert (`:196-227`): reuse first linked incident or create one; set fields, centroid = this report's point; link reports; commit; log.
11. Broadcast: **missing.** Returns `incident.id`; the caller drops it (`reports.py:60`).

Logging: yes, `crowdsense.*` INFO lines per step; background-task exceptions logged with traceback (`reports.py:61-63`). [VERIFIED code]

## 9. Research modules

All four have no DB or network imports (`numpy`, `sklearn`, stdlib only). Exception: `contradiction_detection._get_nli_pipeline()` lazily imports `transformers`, whose first call downloads the model from Hugging Face (network). [VERIFIED]

**duplicate_detection.py** (8 tests)
- `haversine_distance_m(lat1, lon1, lat2, lon2) -> float` (`:26`)
- `cosine_similarity(a, b) -> float` (`:40`), 0.0 if lengths differ
- `find_duplicates(new_item, candidates, text_similarity_threshold=0.82, distance_threshold_m=500.0, time_window_minutes=120.0) -> List[SimilarityResult]` (`:76`)
- `phash_distance(a, b) -> int` (`:120`); `find_image_duplicates(new_hash, candidates, max_distance=8) -> List[ImageDuplicateResult]` (`:132`)
- Dataclasses `EvidenceItem`, `SimilarityResult`, `ImageDuplicateResult`.
- Live parameters from `config.py:12-14`: threshold **0.50** (function default 0.82 is unused by the pipeline), 500 m, 120 min. Untuned.

**contradiction_detection.py** (4 tests)
- `detect_contradiction(report_a_id, text_a, report_b_id, text_b) -> ContradictionResult` (`:95`)
- `any_contradictions(reports: List[(id, text)]) -> bool` (`:123`)
- NLI model `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`, both directions, any "contradiction" label wins; fallback word lists at `:30-31`. No config entries; nothing returns a score or which pair contradicted to fusion (bool only).

**clustering.py** (4 tests)
- `cluster_reports(items, eps_meters=750.0, eps_minutes=180.0, min_samples=2) -> List[int]` (`:36`)
- `D = hypot(d_space, Δt_min · eps_m/eps_min)`, DBSCAN precomputed. Live values `config.py:16-18` (750, 180, 2).

**fusion_engine.py** (7 tests + 10 in `test_fusion_vision.py`)
- `logistic_fusion(n_reports, mean_reliability, has_contradiction, weights=None, vision_support=0.0, cross_modal_conflict=False) -> float` (`:65`)
- `estimate_severity(reports) -> float` (`:134`)
- `fuse_evidence(reports, has_contradiction, vision: Optional[VisionSignals]=None) -> FusionResult` (`:146`)
- Weights `w0..w5 = -1.0, 1.1, 1.8, -2.2, 0.8, -1.2` hard-coded in `DEFAULT_WEIGHTS` (`:27`), not in config. `explanation` records inputs and vision terms but not w0..w3 or the logit.
- Vision thresholds from `config.py:26-30` (0.5, 0.15, 0.5, pHash 8). All untuned.

## 10. Models and dependencies

`python -c` check in `%USERPROFILE%\.venvs\crowdsense312` [VERIFIED]:
```
embed_dim 64
st_model None
nli None
VISION_ENABLED True DEDUP 0.5
vision_model _ClipModel
```

| Role | Intended | Actually used |
|---|---|---|
| Embedding | paraphrase-multilingual-MiniLM-L12-v2 (384-d) | 64-d hash fallback |
| Type classification | cosine to 6 label descriptions with the same embedder (not NLI zero-shot) | keyword fallback |
| Contradiction | mDeBERTa-v3 XNLI | severity-word heuristic |
| Vision | CLIP ViT-B/32 int8 ONNX via onnxruntime | **loaded** (accuracy not evaluated) |

Installed in that venv: fastapi 0.115.0, numpy 2.1.3, onnxruntime 1.19.2, pillow 10.4.0, pytest 8.3.3, scikit-learn 1.5.2; **no** torch, transformers, sentence-transformers. [VERIFIED]
`backend/requirements.txt`: fastapi, uvicorn, sqlalchemy 2.0.35, geoalchemy2, shapely, psycopg2-binary, pydantic 2.9.2, pydantic-settings, email-validator, python-jose, passlib, bcrypt 4.0.1, python-multipart, redis, numpy, scikit-learn, Pillow, onnxruntime, and **uncommented** sentence-transformers 3.1.1, torch 2.4.1, transformers 4.44.2 under an "Optional" comment; pytest, httpx. `redis` and `REDIS_URL` are unused by the code. [VERIFIED]

## 11. Frontend status

- React 18 + Vite 5 + maplibre-gl ^6.13 (`frontend/package.json`). `npm run build` passes. [VERIFIED]
- Components: `App.jsx` (426 lines), `MapView.jsx` (578), `ReportForm.jsx` (252), `IncidentList.jsx` (248), `AIInsights.jsx` (163), `AdminDashboard.jsx` (94), `AuthForm.jsx` (89), `IncidentDetails.jsx` (56). [VERIFIED]
- Coordinates: GeoJSON `[longitude, latitude]` (`MapView.jsx:53`), correct order. [VERIFIED code]
- Incidents render: not re-checked in a browser this audit [NOT RUN]; the fix that made them render (`MapView.jsx:169-172`) is uncommitted; committed HEAD still passes `canvas` (`HEAD:MapView.jsx:169`). [VERIFIED]
- API base: hard-coded `"/api"` (`frontend/src/api.js:1`), proxied by Vite to `http://localhost:8000` (`vite.config.js`). WebSocket: `ws://localhost:8000/ws/incidents` when host is `localhost`, else `wss://<host>/ws/incidents` (`api.js:96-99`). No `VITE_API_URL`. [VERIFIED]
- Report form: text, photo (FileReader -> data URI), GPS or manual lat/lon; always sends `source: "citizen"` (`ReportForm.jsx:92`). [VERIFIED]
- Live updates: App opens the socket (`App.jsx:146`) and polls every 10 s (`App.jsx:145`); only polling has effect. [VERIFIED]

## 12. Drift between CLAUDE.md and the code

1. CLAUDE.md section 5 says its layout is "from `git ls-files` at `91e2981`", but `media.py`, `migrations.py`, `vision_prompts.npz`, the vision scripts and vision tests are **untracked**; vision, logging and the map fix are uncommitted. [VERIFIED]
2. Section 9 says 16 incidents / 18 reports, all `report_count = 1`. Working DB: 17 incidents / 19 reports; 2 incidents have 2 reports (identical text). [VERIFIED]
3. Section 9 describes an end-to-end vision run (`no_incident` p=0.99, `image_conflict=true`, `image_duplicate_of` set). The dev DB has one vision-analysed report: `flood`, conflict false, no duplicate. That run's DB state is not in this file. [VERIFIED / where it ran UNKNOWN]
4. Section 3 says "every run so far used the fallbacks"; 3 dev reports carry 384-dim embeddings, so a real embedder once wrote to this DB. [VERIFIED]
5. Section 4 data flow includes public sources and "WebSocket push"; neither exists. [VERIFIED]
6. Section 5 omits `backend/scripts/try_vision.py`. [VERIFIED]
7. `pipeline.py:117` comment claims candidates are filtered by type; they aren't. `pipeline.py:13` docstring lists broadcast; not done. [VERIFIED]
8. `contradiction_detection.py:9-18` docstring says it "ships as a keyword/heuristic placeholder... swap in NLI"; NLI code is already there. `nlp_service.py:7-8` says "uncomment the SentenceTransformer block"; there is none. [VERIFIED]
9. `models.py:64` says embedding is "JSON-encoded"; code joins with commas. (Already noted in CLAUDE.md.) [VERIFIED]
10. `database.py:24` logs "Connected to primary database (PostgreSQL/PostGIS)" for any URL that connects, including SQLite. [VERIFIED]
11. `requirements.txt:20-24` labels torch/transformers "Optional (comment in...)", yet they are already uncommented. [VERIFIED]
12. CLAUDE.md section 10 tells users to put config in `.env`; `.env.example` is at repo root but the app reads `.env` from the working directory (`config.py:39`), i.e. `backend/.env` when run from `backend`; compose reads the root `.env`. [VERIFIED]

## 13. Gap analysis vs target direction

Sizes are my **estimates** (S = a day or two, M = about a week, L = several weeks for this team), not measurements.

| Target item | Exists | Partial | Missing | Size (estimate) |
|---|---|---|---|---|
| Comparability gate (same attribute + per-type time window + per-type radius before comparing claims) | Pairwise loop over a group (`any_contradictions`) | Group is already roughly bounded by dedup (500 m / 120 min, global, not per type) | Attribute/claim extraction (e.g. "road flooded" vs "road clear"), per-type window/radius config, gate function, outcome categories (contradiction vs temporal evolution vs spatial granularity), returning which pairs and why, tests, labelled pairs to evaluate | L |
| Duplicate-aware effective sample size n_eff | `n_effective` = n minus pHash reposts (`fusion_engine.py:176-182`) | Only image reposts count; only active with vision | Text/near-duplicate and same-source discounting, a principled n_eff definition (e.g. similarity-weighted), use in fusion without vision | S-M |
| Learned, calibrated fusion (Platt primary, isotonic comparison) | Logistic form; full feature `explanation` per incident | Weights are hand-set constants | Labelled incident outcomes, feature export, training script, Platt + isotonic fits, held-out split, persisted parameters, Brier/ECE/reliability plots | M (after data exists) |
| Beta-Binomial source reliability | `source_reliability` column, used in fusion | Constant 0.5; `source` is client-supplied | Source identity model, per-source α/β counts, update from verifier decisions (`/verify` doesn't feed back), prior choice, cold start, tests | M |
| Evaluation harness (baselines B1-B4 vs proposed, ablations, metrics) | Ablation flags for vision (`VisionSignals`, `VISION_IN_FUSION`) | Pure modules make offline replay possible | Labelled dataset (synthetic scenarios and/or CrisisMMD mapping), offline replay runner, baselines, metrics (P/R/F1, PR-AUC, Brier, ECE, incident inflation, latency), results tables | L |
| Real NLP models active | Code with lazy loading | Fallback works; offline-failure path doesn't (section 3) | Installed in a venv, memory measured, dedup threshold retuned, re-embed dev DB | S-M |
| Public-source ingestion | Nothing in this repo | `source` enum values exist | Fetchers, source config, scheduler, dedup by URL/hash, storage columns | M-L |
| Postgres + PostGIS | `docker-compose.yml` with `postgis/postgis:16-3.4`, `init.sql`, GeoAlchemy2 columns | Default URL targets Postgres but local creds fail and it silently falls back | Ever running against Postgres, spatial queries/indexes (pipeline does all geometry in Python), migrations tested on Postgres | M |
| Alembic | `app/migrations.py` (add-column only) | Idempotent, tested on SQLite | Alembic setup, baseline revision matching current schema, CI check | S-M |

## 14. Risks and open questions for the team

1. **Commit the working copy?** Vision, migrations, logging and the map fix are uncommitted. One disk or OneDrive problem loses them. Who commits, and as how many commits?
2. **Committed venv and DB.** `backend/.venv312` (6,045 tracked files) and `backend/crowdsense.db` (5.1 MB, contains base64 photos) are in git. Untrack them? Does the DB contain any real person's photos or locations?
3. **Public `GET /reports`.** It returns every report's text, GPS and photo without auth. Acceptable for a demo? Not for any real deployment.
4. **Which dataset gives ground truth** for calibration and the comparability gate? Synthetic only, CrisisMMD, or both? Calibration (Platt/isotonic) cannot start without incident-level labels.
5. **Attribute extraction approach** for the comparability gate: keyword rules, NLI hypotheses per attribute, or an LLM? This decides the gate's size and its fallback.
6. **Per-type windows and radii:** who chooses the values, and from what source (literature, domain judgment)?
7. **Real models vs 512 MB hosting.** Vision alone measured ~377 MB on Windows (per CLAUDE.md, not re-measured here). Adding MiniLM and mDeBERTa will not fit; is the demo laptop + tunnel plan final?
8. **CI status** [UNKNOWN]: has the GitHub Actions run ever passed? It installs torch on 3.11, and the untracked test files aren't in the repo yet.
9. **Where did the 384-dim embeddings and the CLAUDE.md vision end-to-end run come from?** A second clone or environment may hold work not in this repo (CLAUDE.md also mentions a Copilot ingestion branch).
10. **Postgres on port 5432:** what is listening locally and with which credentials? Needed before any PostGIS work.
11. Should the research modules stay boolean (`any_contradictions -> bool`)? The gate and calibrated fusion likely need per-pair scores, which changes a public signature (CLAUDE.md hard rule 4).
