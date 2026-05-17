"""
app/core/config.py
==================
Centralised settings — override any value via environment variables.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_TITLE: str = "ETL API Demo"
    APP_DESCRIPTION: str = (
        "A production-style FastAPI service that extracts the Credit Card Default "
        "dataset from Hugging Face, runs a multi-step ETL transformation pipeline, "
        "and exposes clean, enriched data through a versioned REST API."
    )
    APP_VERSION: str = "1.0.0"

    # Data source
    HF_DATASET_URL: str = (
        "https://huggingface.co/datasets/imodels/credit-card/raw/main/train.csv"
    )
    HF_DATASET_NAME: str = "imodels/credit-card"

    # ETL tunables
    CACHE_TTL_SECONDS: int = 3600          # how long cached data stays valid
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE:     int = 500

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
