"""
tests/test_pipeline.py
=======================
Unit + integration tests for the ETL pipeline and API endpoints.
Run with:  pytest tests/ -v
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch
from contextlib import asynccontextmanager

# httpx is required by fastapi.testclient.TestClient. If it's missing, fail
# loudly and visibly via pytest's own skip-reporting rather than swallowing
# the ImportError — a hidden `except ImportError: pass` here previously
# caused all 15 API tests to vanish without a trace whenever an unrelated
# import (e.g. a moved module) broke. Don't reintroduce that pattern.
pytest.importorskip("httpx", reason="httpx is required for FastAPI TestClient")

from fastapi.testclient import TestClient

from app.etl.transformer import transform, _normalise_columns, _engineer_features
from app.etl.loader import load
from app.etl import extractor
from app.main import create_app


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def raw_sample() -> pd.DataFrame:
    """Minimal raw DataFrame mimicking the HuggingFace dataset schema.

    Module-scoped (not function-scoped) because it's deterministic (fixed
    RNG seed, no external I/O) and the module-scoped `client` fixture below
    depends on it — pytest raises a ScopeMismatch error if a module-scoped
    fixture tries to depend on a function-scoped one.
    """
    n = 50
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "ID":          range(1, n + 1),
        "LIMIT_BAL":   rng.choice([20000, 50000, 100000, 200000], size=n),
        "SEX":         rng.choice([1, 2], size=n),
        "EDUCATION":   rng.choice([1, 2, 3, 4], size=n),
        "MARRIAGE":    rng.choice([1, 2, 3], size=n),
        "AGE":         rng.integers(22, 70, size=n),
        "PAY_0":       rng.choice([-1, 0, 1, 2], size=n),
        "PAY_2":       rng.choice([-1, 0, 1, 2], size=n),
        "PAY_3":       rng.choice([-1, 0, 1], size=n),
        "PAY_4":       rng.choice([-1, 0, 1], size=n),
        "PAY_5":       rng.choice([-1, 0, 1], size=n),
        "PAY_6":       rng.choice([-1, 0, 1], size=n),
        **{f"BILL_AMT{i}": rng.integers(0, 300000, size=n) for i in range(1, 7)},
        **{f"PAY_AMT{i}":  rng.integers(0,  50000, size=n) for i in range(1, 7)},
        "default.payment.next.month": rng.choice([0, 1], size=n, p=[0.78, 0.22]),
    })


@pytest.fixture
def transformed_df(raw_sample) -> pd.DataFrame:
    return transform(raw_sample)


# ─────────────────────────────────────────────────────────────────────────────
# Transformer tests
# ─────────────────────────────────────────────────────────────────────────────
class TestTransformer:

    def test_column_normalisation(self, raw_sample):
        df = _normalise_columns(raw_sample)
        assert "default_flag" in df.columns, "Target column should be renamed"
        assert all(c == c.lower() for c in df.columns), "All cols should be lowercase"

    def test_transform_returns_dataframe(self, raw_sample):
        df = transform(raw_sample)
        assert isinstance(df, pd.DataFrame)

    def test_transform_row_count_preserved(self, raw_sample, transformed_df):
        assert len(transformed_df) == len(raw_sample)

    def test_engineered_features_present(self, transformed_df):
        required = [
            "credit_utilisation", "avg_payment_ratio", "total_bill_6m",
            "total_paid_6m", "payment_gap", "repayment_trend",
            "max_late_payments", "risk_tier",
        ]
        for col in required:
            assert col in transformed_df.columns, f"Missing engineered feature: {col}"

    def test_credit_utilisation_range(self, transformed_df):
        util = transformed_df["credit_utilisation"].dropna()
        assert (util >= 0).all() and (util <= 1).all(), \
            "Credit utilisation must be in [0, 1]"

    def test_avg_payment_ratio_range(self, transformed_df):
        ratio = transformed_df["avg_payment_ratio"].dropna()
        assert (ratio >= 0).all() and (ratio <= 1).all()

    def test_risk_tier_values(self, transformed_df):
        valid_tiers = {"Very Low", "Low", "Medium", "High"}
        actual = set(transformed_df["risk_tier"].unique())
        assert actual.issubset(valid_tiers), f"Unexpected risk tiers: {actual - valid_tiers}"

    def test_label_encoding(self, transformed_df):
        assert "sex_label" in transformed_df.columns
        assert "education_label" in transformed_df.columns
        valid_sex = {"Male", "Female", "Unknown"}
        assert set(transformed_df["sex_label"].unique()).issubset(valid_sex)

    def test_no_nulls_in_key_cols(self, transformed_df):
        key_cols = ["limit_bal", "age", "default_flag", "credit_utilisation", "risk_tier"]
        for col in key_cols:
            nulls = transformed_df[col].isna().sum()
            assert nulls == 0, f"Unexpected nulls in '{col}': {nulls}"

    def test_record_id_unique(self, transformed_df):
        assert transformed_df["record_id"].nunique() == len(transformed_df)

    def test_record_id_starts_at_1(self, transformed_df):
        assert transformed_df["record_id"].min() == 1


# ─────────────────────────────────────────────────────────────────────────────
# Extractor tests
# ─────────────────────────────────────────────────────────────────────────────
class TestExtractor:

    def test_schema_ok_uses_remote_data(self, raw_sample):
        with patch.object(extractor, "_fetch_remote", return_value=raw_sample):
            df = extractor.extract()
        assert len(df) == len(raw_sample), "Valid remote data should be used as-is"

    def test_schema_mismatch_falls_back(self, raw_sample):
        # Simulate a mirror that one-hot encodes SEX (SEX -> "sex:2")
        bad = raw_sample.drop(columns=["SEX"]).assign(**{"sex:2": 1})
        with patch.object(extractor, "_fetch_remote", return_value=bad):
            df = extractor.extract()
        assert "SEX" in df.columns, "Schema mismatch should trigger the synthetic fallback"
        assert len(df) != len(bad)


# ─────────────────────────────────────────────────────────────────────────────
# Loader tests
# ─────────────────────────────────────────────────────────────────────────────
class TestLoader:

    def test_load_returns_dataframe(self, transformed_df):
        result = load(transformed_df)
        assert isinstance(result, pd.DataFrame)

    def test_load_preserves_rows(self, transformed_df):
        result = load(transformed_df)
        assert len(result) == len(transformed_df)


# ─────────────────────────────────────────────────────────────────────────────
# API endpoint tests (using FastAPI TestClient)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def client(raw_sample):
    """TestClient with pre-loaded synthetic data — no network call."""
    transformed = transform(raw_sample)
    _app = create_app()

    # Override lifespan: inject data directly
    @asynccontextmanager
    async def _mock_lifespan(app):
        app.state.df = transformed
        yield

    _app.router.lifespan_context = _mock_lifespan
    with TestClient(_app) as test_client:
        yield test_client


class TestHealthEndpoint:
    def test_health_200(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200

    def test_health_has_status(self, client):
        body = client.get("/api/v1/health").json()
        assert body["status"] == "ok"

    def test_health_records_loaded(self, client):
        body = client.get("/api/v1/health").json()
        assert body["records_loaded"] > 0


class TestSummaryEndpoint:
    def test_summary_200(self, client):
        assert client.get("/api/v1/summary").status_code == 200

    def test_summary_has_dataset_meta(self, client):
        body = client.get("/api/v1/summary").json()
        assert "dataset" in body
        assert "columns" in body

    def test_summary_default_rate_in_range(self, client):
        meta = client.get("/api/v1/summary").json()["dataset"]
        assert 0 <= meta["default_rate_pct"] <= 100


class TestRecordsEndpoint:
    def test_records_200(self, client):
        assert client.get("/api/v1/records").status_code == 200

    def test_records_pagination(self, client):
        body = client.get("/api/v1/records?page=1&page_size=10").json()
        assert len(body["results"]) <= 10
        assert "total_records" in body
        assert "total_pages" in body

    def test_records_filter_risk(self, client):
        body = client.get("/api/v1/records?risk_tier=High").json()
        for rec in body["results"]:
            assert rec["risk_tier"] == "High"

    def test_single_record(self, client):
        r = client.get("/api/v1/records/1")
        assert r.status_code == 200
        assert r.json()["record_id"] == 1

    def test_record_not_found(self, client):
        assert client.get("/api/v1/records/99999").status_code == 404


class TestInsightsEndpoint:
    def test_insights_200(self, client):
        assert client.get("/api/v1/insights").status_code == 200

    def test_insights_structure(self, client):
        body = client.get("/api/v1/insights").json()
        assert "by_risk_tier" in body
        assert "by_education" in body
        assert "by_age_group" in body
        assert "key_findings" in body
        assert len(body["key_findings"]) > 0
