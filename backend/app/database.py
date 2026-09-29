import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from shapely.geometry import Point
from geoalchemy2.shape import from_shape
import geoalchemy2.admin.dialects.sqlite

# Prevent GeoAlchemy2 from attempting Spatialite-specific DDL calls when running on plain SQLite
geoalchemy2.admin.dialects.sqlite.after_create = lambda *args, **kwargs: None

from app.config import settings

logger = logging.getLogger("crowdsense.database")

def _init_engine():
    db_url = settings.DATABASE_URL
    try:
        eng = create_engine(db_url, pool_pre_ping=True)
        with eng.connect() as conn:
            pass
        logger.info("Connected to primary database (PostgreSQL/PostGIS).")
        return eng
    except Exception as e:
        logger.warning(
            f"Could not connect to PostgreSQL database ({db_url}): {e}. "
            "Falling back to local SQLite database (crowdsense.db)."
        )
        fallback_url = "sqlite:///./crowdsense.db"
        return create_engine(
            fallback_url,
            connect_args={"check_same_thread": False},
        )

engine = _init_engine()

def _geom_from_ewkt_sqlite(val):
    if not val:
        return None
    if isinstance(val, (bytes, memoryview)):
        return bytes(val)
    if isinstance(val, str):
        if "POINT(" in val:
            try:
                coords = val.split("POINT(")[1].replace(")", "").split()
                p = Point(float(coords[0]), float(coords[1]))
                return from_shape(p, srid=4326).data.hex()
            except Exception:
                pass
        return val
    if hasattr(val, "data"):
        return val.data.hex() if hasattr(val.data, "hex") else bytes(val.data).hex()
    return val

# Register dummy spatial functions on SQLite connections to handle GeoAlchemy2 queries seamlessly
@event.listens_for(engine, "connect")
def _register_sqlite_spatial_funcs(dbapi_connection, connection_record):
    if hasattr(dbapi_connection, "create_function"):
        dbapi_connection.create_function("AsEWKB", 1, lambda val: val)
        dbapi_connection.create_function("AsText", 1, lambda val: str(val) if val else None)
        dbapi_connection.create_function("ST_AsText", 1, lambda val: str(val) if val else None)
        dbapi_connection.create_function("GeomFromEWKT", 1, _geom_from_ewkt_sqlite)
        dbapi_connection.create_function("GeomFromText", 1, _geom_from_ewkt_sqlite)
        dbapi_connection.create_function("GeomFromWKB", 1, lambda val: val)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
