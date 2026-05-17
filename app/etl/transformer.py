"""
app/etl/transformer.py
=======================
TRANSFORM step — cleans, enriches, and engineers features from raw data.

Transformations applied (in order):
  1.  Column normalisation          — snake_case, rename ambiguous cols
  2.  Type casting                  — ints / floats as appropriate
  3.  Null imputation               — median for numeric, mode for categorical
  4.  Outlier capping               — IQR-based for LIMIT_BAL
  5.  Label encoding                — sex, education, marriage → readable strings
  6.  Derived features              — utilisation_rate, avg_payment_ratio,
                                      total_bill, total_paid, payment_gap,
                                      repayment_trend, risk_tier
  7.  Validation                    — post-transform schema check
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from app.core.exceptions import ETLError
from app.core.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Lookup maps
# ─────────────────────────────────────────────────────────────────────────────
SEX_MAP       = {1: "Male",   2: "Female"}
EDUCATION_MAP = {1: "Graduate School", 2: "University", 3: "High School", 4: "Other"}
MARRIAGE_MAP  = {1: "Married", 2: "Single", 3: "Other"}

PAY_STATUS_COLS  = ["pay_0", "pay_2", "pay_3", "pay_4", "pay_5", "pay_6"]
BILL_AMT_COLS    = ["bill_amt1", "bill_amt2", "bill_amt3",
                    "bill_amt4", "bill_amt5", "bill_amt6"]
PAY_AMT_COLS     = ["pay_amt1", "pay_amt2", "pay_amt3",
                    "pay_amt4", "pay_amt5", "pay_amt6"]


# ─────────────────────────────────────────────────────────────────────────────
# Step helpers
# ─────────────────────────────────────────────────────────────────────────────
def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase + snake_case column names; rename target."""
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_").replace(".", "_")
                  for c in df.columns]
    # Target column rename
    if "default_payment_next_month" in df.columns:
        df.rename(columns={"default_payment_next_month": "default_flag"}, inplace=True)
    elif "default.payment.next.month" in df.columns:
        df.rename(columns={"default.payment.next.month": "default_flag"}, inplace=True)
    return df


def _cast_types(df: pd.DataFrame) -> pd.DataFrame:
    int_cols   = ["sex", "education", "marriage", "age", "default_flag"] + PAY_STATUS_COLS
    float_cols = ["limit_bal"] + BILL_AMT_COLS + PAY_AMT_COLS
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _impute_nulls(df: pd.DataFrame) -> pd.DataFrame:
    num_cols = df.select_dtypes(include="number").columns
    cat_cols = df.select_dtypes(include="object").columns
    for col in num_cols:
        if df[col].isna().any():
            df[col] = df[col].fillna(df[col].median())
    for col in cat_cols:
        if df[col].isna().any():
            df[col] = df[col].fillna(df[col].mode().iloc[0])
    return df


def _cap_outliers_iqr(df: pd.DataFrame, col: str, multiplier: float = 3.0) -> pd.DataFrame:
    q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
    iqr     = q3 - q1
    lower, upper = q1 - multiplier * iqr, q3 + multiplier * iqr
    original_outliers = ((df[col] < lower) | (df[col] > upper)).sum()
    df[col] = df[col].clip(lower=lower, upper=upper)
    if original_outliers > 0:
        logger.debug(f"  Capped {original_outliers} outliers in '{col}'")
    return df


def _encode_labels(df: pd.DataFrame) -> pd.DataFrame:
    if "sex" in df.columns:
        df["sex_label"]       = df["sex"].map(SEX_MAP).fillna("Unknown")
    if "education" in df.columns:
        df["education_label"] = df["education"].map(EDUCATION_MAP).fillna("Other")
    if "marriage" in df.columns:
        df["marriage_label"]  = df["marriage"].map(MARRIAGE_MAP).fillna("Other")
    return df


def _engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create analytical features:
      - credit_utilisation  : avg(bill_amt / limit_bal) across 6 months — how
                              much of the credit line is actively used
      - avg_payment_ratio   : avg(pay_amt / bill_amt) — repayment discipline
      - total_bill_6m       : sum of all 6 billing amounts
      - total_paid_6m       : sum of all 6 payment amounts
      - payment_gap         : total_bill - total_paid (net exposure)
      - repayment_trend     : whether avg payment increased vs first 3 months
      - max_late_payments   : highest PAY_* status value (worst delinquency)
      - risk_tier           : rule-based tier using utilisation + late payment
    """
    # Guard: ensure required columns exist
    missing = [c for c in BILL_AMT_COLS + PAY_AMT_COLS if c not in df.columns]
    if missing:
        raise ETLError(f"Missing expected columns for feature engineering: {missing}")

    df = df.copy()

    # Total bill / paid
    df["total_bill_6m"]  = df[BILL_AMT_COLS].clip(lower=0).sum(axis=1)
    df["total_paid_6m"]  = df[PAY_AMT_COLS].clip(lower=0).sum(axis=1)
    df["payment_gap"]    = (df["total_bill_6m"] - df["total_paid_6m"]).round(2)

    # Credit utilisation (0–1 range, capped at 1)
    if "limit_bal" in df.columns:
        avg_bill = df[BILL_AMT_COLS].clip(lower=0).mean(axis=1)
        df["credit_utilisation"] = (avg_bill / df["limit_bal"].replace(0, np.nan)
                                    ).clip(0, 1).round(4)
    else:
        df["credit_utilisation"] = np.nan

    # Avg payment ratio (payments relative to bills each month)
    bill_arr = df[BILL_AMT_COLS].clip(lower=1).values   # avoid /0
    paid_arr = df[PAY_AMT_COLS].clip(lower=0).values
    ratios   = np.where(bill_arr > 0, paid_arr / bill_arr, 0)
    df["avg_payment_ratio"] = ratios.mean(axis=1).clip(0, 1).round(4)

    # Repayment trend: avg of last 3 months vs first 3 months
    early_pay = df[["pay_amt1", "pay_amt2", "pay_amt3"]].mean(axis=1)
    late_pay  = df[["pay_amt4", "pay_amt5", "pay_amt6"]].mean(axis=1)
    df["repayment_trend"] = (late_pay - early_pay).round(2)   # positive = improving

    # Worst delinquency
    if all(c in df.columns for c in PAY_STATUS_COLS):
        df["max_late_payments"] = df[PAY_STATUS_COLS].max(axis=1)
    else:
        df["max_late_payments"] = 0

    # Risk tier (rule-based — simple & transparent)
    conditions = [
        (df["credit_utilisation"] >= 0.9)  | (df["max_late_payments"] >= 3),
        (df["credit_utilisation"] >= 0.6)  | (df["max_late_payments"] >= 1),
        (df["credit_utilisation"] >= 0.3),
    ]
    choices = ["High", "Medium", "Low"]
    df["risk_tier"] = np.select(conditions, choices, default="Very Low")

    return df


def _validate(df: pd.DataFrame) -> pd.DataFrame:
    required = {"default_flag", "limit_bal", "age", "credit_utilisation",
                "avg_payment_ratio", "risk_tier"}
    missing = required - set(df.columns)
    if missing:
        raise ETLError(f"Post-transform validation failed — missing columns: {missing}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────
def transform(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Full transformation chain.
    Returns a clean, feature-enriched DataFrame.
    """
    logger.info("  [T1] Normalising columns …")
    df = _normalise_columns(raw)

    logger.info("  [T2] Casting types …")
    df = _cast_types(df)

    logger.info("  [T3] Imputing nulls …")
    df = _impute_nulls(df)

    logger.info("  [T4] Capping LIMIT_BAL outliers …")
    df = _cap_outliers_iqr(df, "limit_bal")

    logger.info("  [T5] Encoding labels …")
    df = _encode_labels(df)

    logger.info("  [T6] Engineering features …")
    df = _engineer_features(df)

    logger.info("  [T7] Validating schema …")
    df = _validate(df)

    # Reset index so record IDs are stable
    df = df.reset_index(drop=True)
    df.insert(0, "record_id", range(1, len(df) + 1))

    logger.info(f"  Transform complete — {len(df):,} rows, {len(df.columns)} columns.")
    return df
