import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

import ast
import csv
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.app.customers.targeting.graphSAGE.config import ArtifactConfig
from src.api.models.graphsage.recommendations import (
    GraphSAGEMsisdnRecommendationsResponse,
    GraphSAGERecommendationsResponse,
)


router = APIRouter(prefix="/graphsage", tags=["GraphSAGE Recommendations"])


def get_recommendations_path() -> Path:
    artifact_config = ArtifactConfig()
    return artifact_config.REC_OUT / "graphsage_all_recommendations.csv"


def parse_optional_int(value):
    if value is None or value == "" or value == "None":
        return None
    return int(float(value))


def parse_optional_float(value):
    if value is None or value == "" or value == "None" or value == "nan":
        return None
    return float(value)


def parse_matched_features(value):
    if not value or value in {"None", "nan"}:
        return []

    if isinstance(value, list):
        return value

    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except Exception:
        pass

    return []


def normalize_recommendation_row(row: dict) -> dict:
    return {
        "rank": int(row["rank"]),
        "msisdn": str(row["msisdn"]),
        "user_idx": parse_optional_int(row.get("user_idx")),
        "bundle_idx": int(row["bundle_idx"]),
        "bundle_id": str(row["bundle_id"]),
        "bundle_name": str(row.get("bundle_name", "")),
        "bundle_type": str(row.get("bundle_type", "")),
        "price": parse_optional_float(row.get("price")),
        "score": float(row["score"]),
        "recommendation_type": str(row.get("recommendation_type", "")),
        "matched_features": parse_matched_features(row.get("matched_features")),
        "cohort_size": parse_optional_int(row.get("cohort_size")),
    }


@router.get("/recommendations", response_model=GraphSAGERecommendationsResponse)
def get_recommendations_page(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=5000),
):
    path = get_recommendations_path()

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Recommendations file not found: {path}",
        )

    recommendations = []

    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row_index, row in enumerate(reader):
            if row_index < offset:
                continue

            recommendations.append(normalize_recommendation_row(row))

            if len(recommendations) >= limit:
                break

    return {
        "total_returned": len(recommendations),
        "offset": offset,
        "limit": limit,
        "recommendations": recommendations,
    }


@router.get("/recommendations/{msisdn}", response_model=GraphSAGEMsisdnRecommendationsResponse)
def get_recommendations_by_msisdn(
    msisdn: str,
    top_k: Optional[int] = Query(None, ge=1, le=100),
):
    path = get_recommendations_path()

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Recommendations file not found: {path}",
        )

    recommendations = []

    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if str(row.get("msisdn")) != str(msisdn):
                continue

            recommendations.append(normalize_recommendation_row(row))

            if top_k is not None and len(recommendations) >= top_k:
                break

    if not recommendations:
        raise HTTPException(
            status_code=404,
            detail=f"No recommendations found for MSISDN: {msisdn}",
        )

    return {
        "msisdn": msisdn,
        "total_returned": len(recommendations),
        "recommendations": recommendations,
    }