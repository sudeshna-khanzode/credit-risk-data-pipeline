"""
app/schemas/responses.py
=========================
Pydantic v2 models for all API response shapes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str = Field(..., example="ok")
    version: str = Field(..., example="1.0.0")
    records_loaded: int = Field(..., description="Number of clean records in memory")


# ─────────────────────────────────────────────────────────────────────────────
# ETL Summary
# ─────────────────────────────────────────────────────────────────────────────
class DatasetMeta(BaseModel):
    source: str
    total_records: int
    columns: int
    default_rate_pct: float
    avg_credit_limit: float
    avg_age: float
    risk_tier_distribution: Dict[str, int]


class ColumnInfo(BaseModel):
    name: str
    dtype: str
    null_count: int
    sample_values: List[Any]


class SummaryResponse(BaseModel):
    dataset: DatasetMeta
    columns: List[ColumnInfo]


# ─────────────────────────────────────────────────────────────────────────────
# Records
# ─────────────────────────────────────────────────────────────────────────────
class RecordResponse(BaseModel):
    record_id: int
    limit_bal: float
    sex_label: Optional[str]
    education_label: Optional[str]
    marriage_label: Optional[str]
    age: int
    default_flag: int
    credit_utilisation: float
    avg_payment_ratio: float
    total_bill_6m: float
    total_paid_6m: float
    payment_gap: float
    repayment_trend: float
    max_late_payments: int
    risk_tier: str


class PaginatedRecordsResponse(BaseModel):
    page: int
    page_size: int
    total_records: int
    total_pages: int
    results: List[RecordResponse]


# ─────────────────────────────────────────────────────────────────────────────
# Insights
# ─────────────────────────────────────────────────────────────────────────────
class RiskBreakdown(BaseModel):
    risk_tier: str
    count: int
    pct_of_total: float
    default_rate_pct: float
    avg_credit_limit: float
    avg_utilisation: float


class EducationBreakdown(BaseModel):
    education_label: str
    count: int
    default_rate_pct: float
    avg_credit_limit: float


class AgeGroupBreakdown(BaseModel):
    age_group: str
    count: int
    default_rate_pct: float
    avg_utilisation: float


class InsightsResponse(BaseModel):
    by_risk_tier: List[RiskBreakdown]
    by_education: List[EducationBreakdown]
    by_age_group: List[AgeGroupBreakdown]
    key_findings: List[str]
