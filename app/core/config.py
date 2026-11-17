"""
app/core/config.py
==================
Centralised settings — override any value via environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_TITLE: str = "Credit Risk Data Pipeline"
    APP_DESCRIPTION: str = (
        "A FastAPI service that extracts the UCI Credit Card Default dataset "
        "from Hugging Face, runs a multi-step ETL transformation pipeline, "
        "and exposes clean, enriched data through a versioned REST API."
    )
    APP_VERSION: str = "1.0.0"

    # Data source
    HF_DATASET_URL: str = (
        "https://huggingface.co/datasets/scikit-learn/credit-card-clients"
        "/resolve/main/UCI_Credit_Card.csv"
    )
    HF_DATASET_NAME: str = "scikit-learn/credit-card-clients"

    # ETL tunables
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE:     int = 500

    # Persistence — SQLite file the LOAD step writes to. Mounted as a volume
    # in docker-compose.yml so it survives container restarts.
    DB_PATH: str = "data/credit_risk.db"

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
