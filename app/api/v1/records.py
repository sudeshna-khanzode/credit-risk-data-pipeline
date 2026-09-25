"""
app/api/v1/records.py
======================
GET /api/v1/records          — paginated, filterable record list
GET /api/v1/records/{id}     — single record by ID
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.config import settings
from app.schemas.responses import PaginatedRecordsResponse, RecordResponse

router = APIRouter()

SERVED_COLS = [
    "record_id", "limit_bal", "sex_label", "education_label", "marriage_label",
    "age", "default_flag", "credit_utilisation", "avg_payment_ratio",
    "total_bill_6m", "total_paid_6m", "payment_gap", "repayment_trend",
    "max_late_payments", "risk_tier",
]


def _row_to_record(row) -> RecordResponse:
    return RecordResponse(
        record_id=int(row.get("record_id", 0)),
        limit_bal=float(row.get("limit_bal", 0)),
        sex_label=str(row.get("sex_label", "")) or None,
        education_label=str(row.get("education_label", "")) or None,
        marriage_label=str(row.get("marriage_label", "")) or None,
        age=int(row.get("age", 0)),
        default_flag=int(row.get("default_flag", 0)),
        credit_utilisation=float(row.get("credit_utilisation", 0)),
        avg_payment_ratio=float(row.get("avg_payment_ratio", 0)),
        total_bill_6m=float(row.get("total_bill_6m", 0)),
        total_paid_6m=float(row.get("total_paid_6m", 0)),
        payment_gap=float(row.get("payment_gap", 0)),
        repayment_trend=float(row.get("repayment_trend", 0)),
        max_late_payments=int(row.get("max_late_payments", 0)),
        risk_tier=str(row.get("risk_tier", "Unknown")),
    )


@router.get("/records", response_model=PaginatedRecordsResponse, summary="List records")
def list_records(
    request:   Request,
    page:      int           = Query(default=1,  ge=1,  description="Page number (1-indexed)"),
    page_size: int           = Query(default=50, ge=1,  description="Records per page"),
    risk_tier: Optional[str] = Query(default=None, description="Filter by risk tier: Very Low | Low | Medium | High"),
    default_flag: Optional[int] = Query(default=None, description="Filter by default flag: 0 or 1"),
    min_age:   Optional[int] = Query(default=None, description="Minimum age"),
    max_age:   Optional[int] = Query(default=None, description="Maximum age"),
) -> PaginatedRecordsResponse:
    """
    Returns a paginated list of transformed credit-card records.

    Supports optional filters:
    - **risk_tier**: `Very Low`, `Low`, `Medium`, `High`
    - **default_flag**: `0` (no default) or `1` (defaulted)
    - **min_age** / **max_age**: age range filter
    """
    page_size = min(page_size, settings.MAX_PAGE_SIZE)

    df = request.app.state.df.copy()

    # ── Apply filters ────────────────────────────────────────────
    if risk_tier is not None:
        df = df[df["risk_tier"].str.lower() == risk_tier.lower()]
    if default_flag is not None:
        df = df[df["default_flag"] == default_flag]
    if min_age is not None:
        df = df[df["age"] >= min_age]
    if max_age is not None:
        df = df[df["age"] <= max_age]

    total   = len(df)
    n_pages = max(1, -(-total // page_size))           # ceiling division

    if page > n_pages:
        raise HTTPException(
            status_code=404,
            detail=f"Page {page} does not exist. Total pages: {n_pages}",
        )

    start = (page - 1) * page_size
    end   = start + page_size
    slice_df = df.iloc[start:end]

    results = [_row_to_record(row) for _, row in slice_df.iterrows()]

    return PaginatedRecordsResponse(
        page=page,
        page_size=page_size,
        total_records=total,
        total_pages=n_pages,
        results=results,
    )


@router.get("/records/{record_id}", response_model=RecordResponse, summary="Get record by ID")
def get_record(record_id: int, request: Request) -> RecordResponse:
    """
    Returns a single fully-transformed record by its `record_id`.
    Includes all engineered features: utilisation, payment ratio, risk tier, etc.
    """
    df  = request.app.state.df
    row = df[df["record_id"] == record_id]

    if row.empty:
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found.")

    return _row_to_record(row.iloc[0].to_dict())
