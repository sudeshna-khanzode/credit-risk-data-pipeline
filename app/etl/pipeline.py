"""
app/etl/pipeline.py
====================
Orchestrates Extract → Transform → Load in sequence.
Exposes a single .run() method called at app startup.
"""

from __future__ import annotations

import time

import pandas as pd

from app.etl.extractor  import extract
from app.etl.transformer import transform
from app.etl.loader      import load
from app.core.logger     import get_logger

logger = get_logger(__name__)


class ETLPipeline:
    """
    Three-stage pipeline: Extract → Transform → Load.

    Usage
    -----
        pipeline = ETLPipeline()
        df = pipeline.run()        # returns clean pd.DataFrame
    """

    def run(self) -> pd.DataFrame:
        logger.info("=" * 55)
        logger.info("  ETL Pipeline starting …")
        logger.info("=" * 55)
        t_start = time.perf_counter()

        # ── Extract ──────────────────────────────────────────────
        logger.info("► EXTRACT")
        raw_df = extract()

        # ── Transform ────────────────────────────────────────────
        logger.info("► TRANSFORM")
        clean_df = transform(raw_df)

        # ── Load ─────────────────────────────────────────────────
        logger.info("► LOAD")
        final_df = load(clean_df)

        elapsed = time.perf_counter() - t_start
        logger.info(f" Pipeline finished in {elapsed:.2f}s — {len(final_df):,} records ready.")
        logger.info("=" * 55)

        return final_df
