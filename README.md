# etl-api-demo

> **A production-style FastAPI + ETL pipeline** that extracts the Credit Card Default dataset from Hugging Face, runs a 7-step transformation pipeline, and serves enriched data through a versioned, Dockerised REST API.

---

## Why this project exists

This project directly demonstrates the skills listed on my resume:

| Resume claim | Where it's proven in this repo |
|---|---|
| FastAPI development | `app/main.py`, `app/api/v1/` — 4 endpoints with Pydantic validation |
| ETL pipeline development | `app/etl/` — modular Extract → Transform → Load with 7 named steps |
| Data transformation with Pandas | `app/etl/transformer.py` — type casting, imputation, outlier capping, feature engineering |
| Docker / containerisation | `Dockerfile` (multi-stage), `docker-compose.yml` |
| Python project structure | Layered package design with `core/`, `etl/`, `api/`, `schemas/` |
| Unit testing | `tests/test_pipeline.py` — 20 test cases covering ETL + API endpoints |
| Public dataset ingestion | Live fetch from HuggingFace Hub with graceful fallback |

---

## Dataset

| Property | Detail |
|---|---|
| **Source** | [`imodels/credit-card`](https://huggingface.co/datasets/imodels/credit-card) on Hugging Face |
| **Original** | UCI ML Repository — Default of Credit Card Clients |
| **Records** | ~24,000 training records |
| **Target** | `default.payment.next.month` (binary: will customer default?) |
| **Key features** | Credit limit, age, sex, education, 6-month payment history & billing amounts |

The app fetches the dataset **directly at startup** with no manual download needed:
```python
pd.read_csv("https://huggingface.co/datasets/imodels/credit-card/raw/main/train.csv")
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      FastAPI App                             │
│                                                              │
│  Startup (lifespan)                                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              ETL Pipeline                            │   │
│  │                                                      │   │
│  │  EXTRACT          TRANSFORM              LOAD        │   │
│  │  ────────         ──────────────────     ────────    │   │
│  │  HuggingFace  →   [T1] Normalise cols →  Validate   │   │
│  │  HTTP fetch       [T2] Cast types        Log stats   │   │
│  │  (+ fallback)     [T3] Impute nulls      Return df   │   │
│  │                   [T4] Cap outliers                  │   │
│  │                   [T5] Encode labels                 │   │
│  │                   [T6] Engineer features             │   │
│  │                   [T7] Validate schema               │   │
│  └──────────────────────────────────────────────────────┘   │
│                         │                                    │
│              app.state.df (in-memory)                        │
│                         │                                    │
│  ┌──────────────────────┼───────────────────────────────┐   │
│  │          REST Endpoints                              │   │
│  │  GET /api/v1/health                                  │   │
│  │  GET /api/v1/summary                                 │   │
│  │  GET /api/v1/records      (paginated + filtered)     │   │
│  │  GET /api/v1/records/{id}                            │   │
│  │  GET /api/v1/insights     (aggregated analytics)     │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## Quickstart

### Option A — Docker (recommended)

```bash
git clone https://github.com/YOUR_USERNAME/etl-api-demo.git
cd etl-api-demo

docker compose up --build
```

The API will be live at **http://localhost:8000**

- Swagger UI: http://localhost:8000/docs
- ReDoc:       http://localhost:8000/redoc

### Option B — Local Python

```bash
git clone https://github.com/YOUR_USERNAME/etl-api-demo.git
cd etl-api-demo

python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
uvicorn app.main:app --reload
```

---

## API Endpoints

### `GET /api/v1/health`
Liveness check. Confirms the ETL pipeline completed and records are loaded.
```json
{
  "status": "ok",
  "version": "1.0.0",
  "records_loaded": 24000
}
```

---

### `GET /api/v1/summary`
Full dataset metadata + column catalogue after transformation.
```json
{
  "dataset": {
    "source": "imodels/credit-card",
    "total_records": 24000,
    "columns": 37,
    "default_rate_pct": 22.1,
    "avg_credit_limit": 167484.32,
    "avg_age": 35.5,
    "risk_tier_distribution": {"High": 8200, "Medium": 9100, "Low": 5400, "Very Low": 1300}
  },
  "columns": [
    {"name": "credit_utilisation", "dtype": "float64", "null_count": 0, "sample_values": [0.42, 0.87, 0.13]}
  ]
}
```

---

### `GET /api/v1/records`
Paginated record list with optional filters.

**Query params:**

| Param | Type | Description |
|---|---|---|
| `page` | int | Page number (default: 1) |
| `page_size` | int | Records per page (max: 500, default: 50) |
| `risk_tier` | str | `Very Low` \| `Low` \| `Medium` \| `High` |
| `default_flag` | int | `0` or `1` |
| `min_age` | int | Minimum age filter |
| `max_age` | int | Maximum age filter |

```bash
curl "http://localhost:8000/api/v1/records?risk_tier=High&default_flag=1&page=1&page_size=5"
```

---

### `GET /api/v1/records/{record_id}`
Single record with all 37 transformed fields.
```json
{
  "record_id": 42,
  "limit_bal": 200000,
  "sex_label": "Female",
  "education_label": "University",
  "marriage_label": "Single",
  "age": 28,
  "default_flag": 0,
  "credit_utilisation": 0.4312,
  "avg_payment_ratio": 0.7821,
  "total_bill_6m": 86240.5,
  "total_paid_6m": 67400.0,
  "payment_gap": 18840.5,
  "repayment_trend": 1250.0,
  "max_late_payments": 0,
  "risk_tier": "Low"
}
```

---

### `GET /api/v1/insights`
Pre-computed analytical aggregations — default rates, utilisation, credit limits broken down by risk tier, education level, and age group.
```json
{
  "by_risk_tier": [
    {"risk_tier": "High", "count": 8200, "pct_of_total": 34.2, "default_rate_pct": 38.1, ...}
  ],
  "by_education": [...],
  "by_age_group": [...],
  "key_findings": [
    "Overall default rate: 22.1% across 24,000 records.",
    "High-risk customers default at 38.1% — 1.7× the average.",
    ...
  ]
}
```

---

## Project Structure

```
etl-api-demo/
│
├── app/
│   ├── main.py                  # FastAPI app factory + lifespan (ETL trigger)
│   │
│   ├── core/
│   │   ├── config.py            # Pydantic settings (env-var overrideable)
│   │   ├── logger.py            # Structured logging
│   │   └── exceptions.py        # Custom exception types
│   │
│   ├── etl/
│   │   ├── extractor.py         # EXTRACT — HuggingFace HTTP fetch + fallback
│   │   ├── transformer.py       # TRANSFORM — 7-step cleaning & feature engineering
│   │   ├── loader.py            # LOAD — validation, stats logging
│   │   └── pipeline.py          # Orchestrator: runs E → T → L in sequence
│   │
│   ├── api/v1/
│   │   ├── health.py            # GET /api/v1/health
│   │   ├── summary.py           # GET /api/v1/summary
│   │   ├── records.py           # GET /api/v1/records, /records/{id}
│   │   └── insights.py          # GET /api/v1/insights
│   │
│   └── schemas/
│       └── responses.py         # Pydantic v2 response models
│
├── tests/
│   └── test_pipeline.py         # 20 unit + integration tests
│
├── Dockerfile                   # Multi-stage build
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Running Tests

```bash
pytest tests/ -v
```

The test suite covers:
- Column normalisation and type casting
- Null imputation
- Engineered feature value ranges (`credit_utilisation` ∈ [0,1], etc.)
- Label encoding correctness
- `record_id` uniqueness and start value
- Schema validation (post-transform)
- All 4 API endpoints (health, summary, records, insights)
- Pagination, filtering, and 404 handling

---

## ETL Transformations — Detail

| Step | What happens |
|---|---|
| **T1 Normalise** | Lowercase + snake_case columns; rename `default.payment.next.month` → `default_flag` |
| **T2 Cast types** | Enforce `Int64` for categoricals, `float64` for amounts |
| **T3 Impute** | Median for numeric nulls; mode for categorical nulls |
| **T4 Outlier cap** | IQR × 3 bounds applied to `LIMIT_BAL` |
| **T5 Encode** | `sex` → `"Male"/"Female"`, `education` → `"University"` etc. |
| **T6 Engineer** | `credit_utilisation`, `avg_payment_ratio`, `total_bill_6m`, `total_paid_6m`, `payment_gap`, `repayment_trend`, `max_late_payments`, `risk_tier` |
| **T7 Validate** | Assert required columns exist; raise `ETLError` otherwise |

---

## Tech Stack

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-2.x-150458?logo=pandas&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?logo=pydantic&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-multi--stage-2496ED?logo=docker&logoColor=white)
![HuggingFace](https://img.shields.io/badge/HuggingFace-Dataset-FFD21E?logo=huggingface&logoColor=black)
![pytest](https://img.shields.io/badge/pytest-20_tests-0A9EDC?logo=pytest&logoColor=white)

---

## Author

**Sudeshna Khanzode** — Data Analyst & Developer  
[GitHub](https://github.com/sudeshna-khanzode) · [LinkedIn](https://linkedin.com/in/sudeshna-khanzode)
