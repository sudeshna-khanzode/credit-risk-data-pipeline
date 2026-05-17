"""
app/api/v1/insights.py
=======================
GET /api/v1/insights  — pre-computed analytical aggregations over the ETL output.

Demonstrates that the API can do more than serve raw rows:
  - Risk tier breakdown (default rate, utilisation, limit)
  - Education level breakdown
  - Age group breakdown
  - Auto-generated key findings
"""

from fastapi import APIRouter, Request
import pandas as pd

from app.schemas.responses import (
    InsightsResponse, RiskBreakdown, EducationBreakdown, AgeGroupBreakdown,
)

router = APIRouter()

RISK_ORDER = ["Very Low", "Low", "Medium", "High"]

AGE_BINS   = [0, 25, 35, 45, 55, 200]
AGE_LABELS = ["<25", "25–34", "35–44", "45–54", "55+"]


@router.get("/insights", response_model=InsightsResponse, summary="Analytical insights")
def get_insights(request: Request) -> InsightsResponse:
    """
    Returns three analytical breakdowns computed in real-time from the
    ETL-transformed dataset, plus auto-generated key findings.

    - **by_risk_tier**: default rate, avg credit limit, avg utilisation per tier
    - **by_education**: default rate and avg credit limit by education level
    - **by_age_group**: default rate and avg utilisation by age band
    - **key_findings**: 4 human-readable bullet-point insights
    """
    df    = request.app.state.df.copy()
    total = len(df)

    # ── By risk tier ─────────────────────────────────────────────
    risk_rows = []
    for tier in RISK_ORDER:
        sub = df[df["risk_tier"] == tier]
        if sub.empty:
            continue
        risk_rows.append(RiskBreakdown(
            risk_tier=tier,
            count=len(sub),
            pct_of_total=round(len(sub) / total * 100, 1),
            default_rate_pct=round(float(sub["default_flag"].mean()) * 100, 1),
            avg_credit_limit=round(float(sub["limit_bal"].mean()), 0),
            avg_utilisation=round(float(sub["credit_utilisation"].mean()), 3),
        ))

    # ── By education ─────────────────────────────────────────────
    edu_order = ["Graduate School", "University", "High School", "Other"]
    edu_rows  = []
    for edu in edu_order:
        sub = df[df["education_label"] == edu]
        if sub.empty:
            continue
        edu_rows.append(EducationBreakdown(
            education_label=edu,
            count=len(sub),
            default_rate_pct=round(float(sub["default_flag"].mean()) * 100, 1),
            avg_credit_limit=round(float(sub["limit_bal"].mean()), 0),
        ))

    # ── By age group ─────────────────────────────────────────────
    df["age_group"] = pd.cut(df["age"].astype(int), bins=AGE_BINS,
                             labels=AGE_LABELS, right=False)
    age_rows = []
    for grp in AGE_LABELS:
        sub = df[df["age_group"] == grp]
        if sub.empty:
            continue
        age_rows.append(AgeGroupBreakdown(
            age_group=grp,
            count=len(sub),
            default_rate_pct=round(float(sub["default_flag"].mean()) * 100, 1),
            avg_utilisation=round(float(sub["credit_utilisation"].mean()), 3),
        ))

    # ── Key findings (auto-generated) ────────────────────────────
    findings: list[str] = []

    overall_default = df["default_flag"].mean() * 100
    findings.append(
        f"Overall default rate: {overall_default:.1f}% across {total:,} records."
    )

    high_risk_default = df[df["risk_tier"] == "High"]["default_flag"].mean() * 100 \
        if (df["risk_tier"] == "High").any() else 0
    findings.append(
        f"High-risk customers default at {high_risk_default:.1f}% — "
        f"{high_risk_default / max(overall_default, 0.01):.1f}× the average."
    )

    best_edu = max(edu_rows, key=lambda r: r.avg_credit_limit, default=None)
    if best_edu:
        findings.append(
            f"{best_edu.education_label} holders have the highest avg credit limit "
            f"(NT${best_edu.avg_credit_limit:,.0f})."
        )

    young_def = next((r.default_rate_pct for r in age_rows if r.age_group == "<25"), None)
    mid_def   = next((r.default_rate_pct for r in age_rows if r.age_group == "35–44"), None)
    if young_def and mid_def:
        findings.append(
            f"Customers under 25 default at {young_def:.1f}% vs "
            f"{mid_def:.1f}% for the 35–44 cohort."
        )

    return InsightsResponse(
        by_risk_tier=risk_rows,
        by_education=edu_rows,
        by_age_group=age_rows,
        key_findings=findings,
    )
