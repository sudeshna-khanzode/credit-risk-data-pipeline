"""
app/etl/loader.py
==================
LOAD step — persists the clean DataFrame to a SQLite database on disk
(app.core.config.settings.DB_PATH) and also returns it so the API can
keep an in-memory copy for low-latency reads without re-running the
pipeline or re-hitting the database on every request.

SQLite was chosen over an in-memory-only store so that:
  - the data genuinely survives a container restart (mounted as a
    volume in docker-compose.yml)
  - the file is inspectable with any SQL client for debugging/demo
    purposes (`sqlite3 data/credit_risk.db`)

In a larger production system this step would instead write to:
  - PostgreSQL / Redshift (via SQLAlchemy) for concurrent multi-writer access
  - S3 (Parquet via boto3) for a data-lake landing zone
  - Redis (cached JSON) for a hot read cache in front of the database
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

TABLE_NAME = "credit_risk_records"


def _persist_to_sqlite(df: pd.DataFrame) -> None:
    """Write the dataframe to the configured SQLite file, replacing any prior table."""
    db_path = Path(settings.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        # `record_id` is already a column (added in transform()), so write
        # without the pandas index — using index_label="record_id" here would
        # collide with that existing column and raise "duplicate column name".
        df.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)
        conn.commit()

    size_kb = db_path.stat().st_size / 1024
    logger.info(f"       SQLite file     : {db_path} ({size_kb:.0f} KB)")


def load(df: pd.DataFrame) -> pd.DataFrame:
    """
    Persist the final dataframe to SQLite, validate it, and return it for
    the in-memory cache used by the API layer.
    Logs key statistics that would normally also go to a monitoring dashboard.
    """
    n = len(df)
    default_rate = df["default_flag"].mean() * 100 if "default_flag" in df.columns else 0.0
    null_pct     = df.isnull().mean().mean() * 100

    try:
        _persist_to_sqlite(df)
    except Exception as exc:  # pragma: no cover - defensive; demo should still run
        logger.error(f"  ⚠ Failed to persist to SQLite: {exc}")

    logger.info("  [L1] Load statistics:")
    logger.info(f"       Total records   : {n:,}")
    logger.info(f"       Columns         : {len(df.columns)}")
    logger.info(f"       Default rate    : {default_rate:.1f}%")
    logger.info(f"       Null percentage : {null_pct:.2f}%")
    logger.info(f"       Memory usage    : {df.memory_usage(deep=True).sum() / 1024:.0f} KB")

    if null_pct > 5:
        logger.warning(f"  ⚠ Null percentage ({null_pct:.1f}%) exceeds 5% threshold.")

    return df
