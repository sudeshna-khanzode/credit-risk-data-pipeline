"""
app/api/v1/summary.py
======================
GET /api/v1/summary  — dataset metadata + column catalogue after ETL.
"""

from fastapi import APIRouter, Request
from app.schemas.responses import SummaryResponse, DatasetMeta, ColumnInfo
from app.core.config import settings

router = APIRouter()

SAMPLE_SIZE = 3


@router.get("/summary", response_model=SummaryResponse, summary="ETL pipeline summary")
def get_summary(request: Request) -> SummaryResponse:
    """
    Returns high-level metadata about the transformed dataset:
    - Row/column counts, source URL
    - Default payment rate (key target metric)
    - Average credit limit and age
    - Risk tier distribution
    - Column catalogue with dtype, null count, and sample values
    """
    df = request.app.state.df

    # ── Dataset-level metadata ───────────────────────────────────
    default_rate = round(float(df["default_flag"].mean()) * 100, 2) \
        if "default_flag" in df.columns else 0.0

    risk_dist = df["risk_tier"].value_counts().to_dict() \
        if "risk_tier" in df.columns else {}

    dataset_meta = DatasetMeta(
        source=settings.HF_DATASET_NAME,
        total_records=len(df),
        columns=len(df.columns),
        default_rate_pct=default_rate,
        avg_credit_limit=round(float(df["limit_bal"].mean()), 2) if "limit_bal" in df.columns else 0.0,
        avg_age=round(float(df["age"].mean()), 1) if "age" in df.columns else 0.0,
        risk_tier_distribution={str(k): int(v) for k, v in risk_dist.items()},
    )

    # ── Column catalogue ─────────────────────────────────────────
    columns = []
    for col in df.columns:
        samples = df[col].dropna().head(SAMPLE_SIZE).tolist()
        columns.append(ColumnInfo(
            name=col,
            dtype=str(df[col].dtype),
            null_count=int(df[col].isna().sum()),
            sample_values=samples,
        ))

    return SummaryResponse(dataset=dataset_meta, columns=columns)
