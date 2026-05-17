"""
app/etl/loader.py
==================
LOAD step — in this demo, "loading" means persisting the clean DataFrame
to an in-memory store so the API can serve it without re-running the pipeline
on every request.

In a production system this step would write to:
  - PostgreSQL / Redshift (via SQLAlchemy)
  - S3 (Parquet via boto3)
  - Redis (cached JSON)
"""

from __future__ import annotations

import pandas as pd
from app.core.logger import get_logger

logger = get_logger(__name__)


def load(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate the final dataframe and return it.
    Logs key statistics that would normally also go to a monitoring dashboard.
    """
    n = len(df)
    default_rate = df["default_flag"].mean() * 100 if "default_flag" in df.columns else 0.0
    null_pct     = df.isnull().mean().mean() * 100

    logger.info("  [L1] Load statistics:")
    logger.info(f"       Total records   : {n:,}")
    logger.info(f"       Columns         : {len(df.columns)}")
    logger.info(f"       Default rate    : {default_rate:.1f}%")
    logger.info(f"       Null percentage : {null_pct:.2f}%")
    logger.info(f"       Memory usage    : {df.memory_usage(deep=True).sum() / 1024:.0f} KB")

    if null_pct > 5:
        logger.warning(f"  ⚠ Null percentage ({null_pct:.1f}%) exceeds 5% threshold.")

    return df
