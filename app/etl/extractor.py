"""
app/etl/extractor.py
=====================
EXTRACT step — pulls the Credit Card Default dataset from Hugging Face.

Dataset  : imodels/credit-card  (HuggingFace Hub)
Direct URL: https://huggingface.co/datasets/imodels/credit-card/raw/main/train.csv

Falls back to a bundled synthetic sample if the remote is unreachable
(e.g. running fully offline or in a restricted CI environment).
"""

from __future__ import annotations

import io
import os
import time

import pandas as pd
import requests

from app.core.config import settings
from app.core.exceptions import DataSourceError
from app.core.logger import get_logger

logger = get_logger(__name__)

# Columns we care about from the raw dataset
EXPECTED_COLS = {
    "LIMIT_BAL", "SEX", "EDUCATION", "MARRIAGE", "AGE",
    "PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6",
    "BILL_AMT1", "BILL_AMT2", "BILL_AMT3", "BILL_AMT4", "BILL_AMT5", "BILL_AMT6",
    "PAY_AMT1", "PAY_AMT2", "PAY_AMT3", "PAY_AMT4", "PAY_AMT5", "PAY_AMT6",
    "default.payment.next.month",
}


def _fetch_remote(url: str, timeout: int = 15) -> pd.DataFrame:
    logger.info(f"Fetching dataset from: {url}")
    t0 = time.perf_counter()
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    elapsed = time.perf_counter() - t0
    logger.info(f"  Downloaded {len(resp.content) / 1024:.1f} KB in {elapsed:.2f}s")
    df = pd.read_csv(io.StringIO(resp.text))
    return df


def _make_synthetic_fallback(n: int = 3_000) -> pd.DataFrame:
    """
    Generates a realistic synthetic version of the Credit Card Default dataset.
    Same schema, same value ranges — used when remote data is unavailable.
    """
    import numpy as np
    rng = np.random.default_rng(42)

    n_rows = n
    df = pd.DataFrame({
        "ID":          range(1, n_rows + 1),
        "LIMIT_BAL":   rng.choice([10_000, 20_000, 30_000, 50_000, 80_000, 100_000,
                                   150_000, 200_000, 300_000, 500_000], size=n_rows),
        "SEX":         rng.choice([1, 2], size=n_rows),
        "EDUCATION":   rng.choice([1, 2, 3, 4], size=n_rows, p=[0.35, 0.45, 0.15, 0.05]),
        "MARRIAGE":    rng.choice([1, 2, 3], size=n_rows, p=[0.45, 0.50, 0.05]),
        "AGE":         rng.integers(21, 75, size=n_rows),
        "PAY_0":       rng.choice([-2, -1, 0, 1, 2, 3], size=n_rows,
                                   p=[0.10, 0.25, 0.35, 0.15, 0.10, 0.05]),
        "PAY_2":       rng.choice([-2, -1, 0, 1, 2, 3], size=n_rows,
                                   p=[0.10, 0.25, 0.35, 0.15, 0.10, 0.05]),
        "PAY_3":       rng.choice([-2, -1, 0, 1, 2], size=n_rows),
        "PAY_4":       rng.choice([-2, -1, 0, 1, 2], size=n_rows),
        "PAY_5":       rng.choice([-2, -1, 0, 1, 2], size=n_rows),
        "PAY_6":       rng.choice([-2, -1, 0, 1, 2], size=n_rows),
    })

    for i in range(1, 7):
        df[f"BILL_AMT{i}"] = rng.integers(-5_000, 500_000, size=n_rows)
        df[f"PAY_AMT{i}"]  = rng.integers(0, 100_000, size=n_rows)

    # ~22% default rate (matches real dataset)
    df["default.payment.next.month"] = rng.choice([0, 1], size=n_rows, p=[0.78, 0.22])
    return df


def extract() -> pd.DataFrame:
    """
    Entry point for the Extract step.
    Returns a raw DataFrame — no cleaning applied yet.
    """
    try:
        df = _fetch_remote(settings.HF_DATASET_URL)
        logger.info(f"  Remote extract OK — {len(df):,} rows, {len(df.columns)} columns.")
        return df
    except Exception as exc:
        logger.warning(f"  Remote fetch failed ({exc}). Using synthetic fallback data.")
        df = _make_synthetic_fallback()
        logger.info(f"  Synthetic fallback — {len(df):,} rows.")
        return df
