from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://crowdsense:crowdsense@localhost:5432/crowdsense"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    DEDUP_TEXT_SIMILARITY_THRESHOLD: float = 0.82
    DEDUP_DISTANCE_METERS: float = 500.0
    DEDUP_TIME_WINDOW_MINUTES: int = 120

    CLUSTER_EPS_METERS: float = 750.0
    CLUSTER_EPS_MINUTES: float = 180.0
    CLUSTER_MIN_SAMPLES: int = 2

    CORS_ORIGINS: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()
