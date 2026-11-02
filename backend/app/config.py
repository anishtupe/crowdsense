from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://crowdsense:crowdsense@localhost:5432/crowdsense"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    DEDUP_TEXT_SIMILARITY_THRESHOLD: float = 0.50
    DEDUP_DISTANCE_METERS: float = 500.0
    DEDUP_TIME_WINDOW_MINUTES: int = 120

    CLUSTER_EPS_METERS: float = 750.0
    CLUSTER_EPS_MINUTES: float = 180.0
    CLUSTER_MIN_SAMPLES: int = 2

    # Vision (image evidence). Off by default: tests and the slim deploy use
    # the fallback, which contributes no vision evidence. Thresholds are
    # hand-set and untuned.
    VISION_ENABLED: bool = False
    VISION_MODEL: str = "clip-vit-b32-int8"            # id recorded with each result
    VISION_MODEL_DIR: str = "models/clip-vit-b32"      # relative to backend/
    VISION_MIN_LABEL_CONFIDENCE: float = 0.5
    VISION_CONFLICT_LOW: float = 0.15
    VISION_CONFLICT_HIGH: float = 0.5
    VISION_PHASH_MAX_DISTANCE: int = 8   # of 64 bits
    VISION_IN_FUSION: bool = True        # false = "remove vision" ablation

    # Uploaded photos (base64 data URIs in POST /reports)
    MEDIA_MAX_BYTES: int = 5_000_000     # decoded size
    MEDIA_MAX_SIDE: int = 1600           # px, longest side after re-encoding

    CORS_ORIGINS: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()
