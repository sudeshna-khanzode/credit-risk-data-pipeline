# Credit Risk Data Pipeline

An ETL pipeline and REST API built around the UCI Credit Card Default dataset — from raw data ingestion to a queryable API.

## Overview

I wanted to build a complete, end-to-end data pipeline: something that starts with a real dataset and ends with a usable API, not just a notebook that stops at a chart. This project takes raw credit card customer data, runs it through cleaning and feature engineering, persists the result, and serves it through a REST API with filtering, pagination, and basic analytics.

It's deliberately scoped as a single, focused project rather than trying to cover every tool at once — SQL warehousing, dashboards, and cloud deployment are things I'm building out as separate projects.

## Architecture

```
UCI Credit Card Dataset
        │
        ▼
     Extract
        │
        ▼
Clean + Transform
        │
        ▼
Feature Engineering
        │
        ▼
      SQLite
        │
        ▼
     FastAPI
```

Extraction pulls the dataset from HuggingFace; if that fails, the pipeline falls back to generated synthetic data with the same schema so the app doesn't just crash on a network hiccup. Everything downstream — cleaning, feature engineering, persistence, and the API — behaves identically either way.

## Dataset

The [UCI Credit Card Default dataset](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients) (accessed via a HuggingFace mirror) contains 30,000 records of Taiwanese credit card customers from 2005: credit limits, demographics, six months of billing and payment history, and whether each customer defaulted the following month. It's a standard, well-understood dataset for this kind of exercise — clean enough to focus on pipeline design rather than data archaeology.

## Features

- ETL pipeline with 7 named transformation steps
- Schema validation after transformation
- Engineered risk features (see below)
- SQLite persistence
- REST API with 4 endpoints
- Pagination and filtering on the records endpoint
- 26 tests covering the ETL logic and the API
- Dockerised, with a non-root user and a healthcheck
- CI workflow that runs the tests and builds the image on every push

## Engineered Features

The raw dataset gives you six months of bill and payment amounts per customer. The interesting part of this project was turning that into signals that actually mean something:

- **`credit_utilisation`** — average bill amount ÷ credit limit. How much of their credit line a customer is actually using.
- **`avg_payment_ratio`** — average payment ÷ bill amount each month. A rough measure of repayment discipline.
- **`payment_gap`** — total billed minus total paid over six months. Net exposure.
- **`repayment_trend`** — whether a customer's payments trended up or down over the period.
- **`max_late_payments`** — worst delinquency status recorded across the six months.
- **`risk_tier`** — a simple rule-based bucket (Low / Medium / High) combining utilisation and late-payment history.

None of this is a trained model — it's feature engineering meant to turn raw transaction history into something a downstream model or analyst could actually use.

## Tech Stack

Python · Pandas · FastAPI · Pydantic · SQLite · Pytest · Docker

## Running Locally

```bash
git clone https://github.com/sudeshna-khanzode/credit-risk-data-pipeline.git
cd credit-risk-data-pipeline
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Then open `http://localhost:8000/docs` for the interactive API docs.

Or with Docker:

```bash
docker compose up --build
```

Run the tests:

```bash
pytest tests/ -v
```

## API

| Endpoint | What it does |
|---|---|
| `GET /api/v1/health` | Basic health check, including record count loaded |
| `GET /api/v1/summary` | Dataset-level stats — default rate, column info |
| `GET /api/v1/records` | Paginated, filterable list of records (e.g. `?risk_tier=High`) |
| `GET /api/v1/records/{id}` | A single record by ID |
| `GET /api/v1/insights` | Aggregated breakdowns by risk tier, education, and age group |

Full request/response schemas are in the Swagger docs at `/docs` once running.

## Engineering Decisions

**Pandas.** The dataset is small enough (30K rows) that Pandas is simple and fast to iterate with. I didn't need distributed processing for this scale, and reaching for Spark here would have added complexity without solving a real problem.

**SQLite.** I wanted actual persistence — not just an in-memory dataframe that disappears on restart — without standing up a database server for what's ultimately a single-writer demo. It's mounted as a Docker volume so the data survives a container restart. For multiple concurrent writers or a real production deployment, I'd move this to Postgres.

**FastAPI.** Pydantic validation and automatic OpenAPI docs meant I got a documented, typed API without writing separate documentation by hand — useful for a project I want other people to be able to pick up and understand quickly.

**What I'd change for production.** Swap SQLite for Postgres, move the ETL off "runs once at container startup" onto a real scheduler, add authentication, and add proper monitoring instead of relying on logs.

## Limitations

This is a demo pipeline, not a production system, and I'd rather be upfront about where the edges are:

- `risk_tier` is a heuristic rule (utilisation + late-payment history), not a validated credit-scoring model. It exists to demonstrate feature engineering, not to predict anything.
- SQLite handles one writer at a time — fine here, not fine for concurrent production writes.
- The ETL runs once on startup rather than on a schedule; there's no incremental or streaming ingestion.
- No authentication — every endpoint is open, which is acceptable for public, de-identified data and a portfolio demo, not for real customer data.
- No monitoring or alerting beyond application logs.

## What I Learned

- Structuring an ETL pipeline into named, testable stages makes it much easier to reason about where something went wrong than one long script.
- Tests that pass don't guarantee the app runs — I had a test suite reporting green while the app itself couldn't start, and the only way I caught it was by actually running the server end to end and checking the real output, not just trusting `pytest`.
- Keeping the API layer and the data/ETL logic separate paid off — I could change how data got persisted without touching a single API route.
