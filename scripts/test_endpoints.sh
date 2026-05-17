#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# scripts/test_endpoints.sh
# Quick smoke test for all API endpoints.
# Usage: bash scripts/test_endpoints.sh [BASE_URL]
# ─────────────────────────────────────────────────────────────────

BASE_URL="${1:-http://localhost:8000}"
PASS=0; FAIL=0

check() {
    local desc="$1"
    local url="$2"
    local expected_status="${3:-200}"
    local result
    result=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    if [ "$result" -eq "$expected_status" ]; then
        echo "  ✅  $desc ($result)"
        ((PASS++))
    else
        echo "  ❌  $desc — expected $expected_status, got $result"
        ((FAIL++))
    fi
}

echo ""
echo "ETL API Demo — Endpoint Smoke Tests"
echo "Base URL: $BASE_URL"
echo "────────────────────────────────────"

check "Health check"                   "$BASE_URL/api/v1/health"
check "Summary"                        "$BASE_URL/api/v1/summary"
check "Records (default)"              "$BASE_URL/api/v1/records"
check "Records (page 2)"               "$BASE_URL/api/v1/records?page=2&page_size=10"
check "Records (filter High risk)"     "$BASE_URL/api/v1/records?risk_tier=High"
check "Records (filter defaulted)"     "$BASE_URL/api/v1/records?default_flag=1"
check "Records (age range)"            "$BASE_URL/api/v1/records?min_age=25&max_age=35"
check "Single record"                  "$BASE_URL/api/v1/records/1"
check "Record not found (404)"         "$BASE_URL/api/v1/records/99999" 404
check "Insights"                       "$BASE_URL/api/v1/insights"
check "Swagger UI"                     "$BASE_URL/docs"
check "OpenAPI JSON"                   "$BASE_URL/openapi.json"

echo "────────────────────────────────────"
echo "Results: $PASS passed, $FAIL failed"
echo ""
