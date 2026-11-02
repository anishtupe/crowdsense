import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.migrations import run_migrations
from app.routers import auth, reports, incidents, verification, ws

# Show the app's own INFO logs (pipeline steps, vision, migrations) next to
# uvicorn's. Uvicorn's loggers don't propagate to root, so no duplicates.
logging.basicConfig(format="%(levelname)s:     %(name)s: %(message)s")
logging.getLogger("crowdsense").setLevel(logging.INFO)

app = FastAPI(
    title="CrowdSense API",
    description=(
        "Contradiction-Aware Multimodal Evidence Fusion Framework for "
        "Real-Time Geospatial Incident Intelligence"
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(reports.router)
app.include_router(incidents.router)
app.include_router(verification.router)
app.include_router(ws.router)


@app.on_event("startup")
def on_startup():
    # For the starter scaffold, create tables directly from the ORM
    # models. Swap this for Alembic migrations once the schema
    # stabilizes (`alembic init` / `alembic revision --autogenerate`).
    Base.metadata.create_all(bind=engine)
    # create_all never alters existing tables; add newer columns here.
    run_migrations(engine)


@app.get("/health")
def health():
    return {"status": "ok"}
