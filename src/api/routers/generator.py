import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from typing import Any, Dict, List

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

from src.app.products.gen.config import BundleGenerationConfig
from src.app.products.gen.generator import BundlesGenerator
from src.app.products.gen.cim.config import ModelParams
from src.app.products.gen.cim.runner import run_pipeline
from src.api.models.generator import (
    BundleGeneratorRequest,
    BundleGeneratorResponse,
    DashboardModelParams,
    ExistingBundleItem,
    GeneratedBundleItem,
    GeneratorMeta,
)

router = APIRouter(prefix="/generator", tags=["Bundle Generator"])


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating,)):
        return float(value)

    if isinstance(value, (np.bool_,)):
        return bool(value)

    if pd.isna(value):
        return None

    return value


def _dataframe_to_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    records = df.to_dict(orient="records")
    return [
        {key: _sanitize_value(value) for key, value in row.items()}
        for row in records
    ]


def _ensure_generated_bundle_ids(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()

    if "bundle_id" not in data.columns:
        data.insert(0, "bundle_id", [f"GEN_{i + 1}" for i in range(len(data))])
        return data

    missing_mask = data["bundle_id"].isna() | (data["bundle_id"].astype(str).str.strip() == "")
    if missing_mask.any():
        generated_ids = [f"GEN_{i + 1}" for i in range(len(data))]
        data.loc[missing_mask, "bundle_id"] = [
            generated_ids[i] for i in range(len(data)) if missing_mask.iloc[i]
        ]

    return data


def _ensure_validity_bucket(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()

    if "validity_days" not in data.columns:
        data["validity_hours"] = pd.to_numeric(
            data.get("validity_hours", 0),
            errors="coerce",
        ).fillna(0.0)
        data["validity_days"] = data["validity_hours"] / 24.0

    data["validity_days"] = pd.to_numeric(
        data["validity_days"],
        errors="coerce",
    ).fillna(0.0)

    if "validity_bucket" not in data.columns:
        data["validity_bucket"] = np.select(
            [
                data["validity_days"] <= 1,
                (data["validity_days"] > 1) & (data["validity_days"] <= 7),
                (data["validity_days"] > 7) & (data["validity_days"] <= 30),
                data["validity_days"] > 30,
            ],
            [
                "daily",
                "weekly",
                "monthly",
                "long_term",
            ],
            default="unknown",
        )

    return data


def _normalize_existing_df(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()

    numeric_defaults = {
        "price": 0.0,
        "volume_mb": 0.0,
        "minutes": 0.0,
        "sms": 0.0,
        "avg_weekly_revenue": 0.0,
        "avg_weekly_subs": 0.0,
        "popularity_score": 0.0,
    }

    for col, default in numeric_defaults.items():
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce").fillna(default)

    string_defaults = {
        "bundle_id": "",
        "bundle_name": "",
        "bundle_type": "UNKNOWN",
    }

    for col, default in string_defaults.items():
        if col in data.columns:
            data[col] = data[col].fillna(default).astype(str)

    return data


def _normalize_generated_df(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()

    numeric_defaults = {
        "price": 0.0,
        "volume_mb": 0.0,
        "volume_min": 0.0,
        "volume_sms": 0.0,
        "validity_hours": 0.0,
        "validity_days": 0.0,
        "predicted_popularity": 0.0,
    }

    for col, default in numeric_defaults.items():
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce").fillna(default)

    string_defaults = {
        "bundle_id": "",
        "bundle_type": "UNKNOWN",
        "usage_type": "",
        "service_class_category": "",
        "validity_bucket": "unknown",
        "popularity_category": "Unknown",
    }

    for col, default in string_defaults.items():
        if col in data.columns:
            data[col] = data[col].fillna(default).astype(str)

    return data


def _top_n_per_bundle_type(
    summary_df: pd.DataFrame,
    n: int = 2,
    sort_by: str = "net_revenue_weekly",
) -> pd.DataFrame:
    ascending = sort_by == "cannib_pct_of_portfolio"
    ranked = summary_df.sort_values(sort_by, ascending=ascending)

    return (
        ranked
        .groupby("new_bundle_type", group_keys=False)
        .head(n)
        .reset_index(drop=True)
    )


@router.post("/bundles", response_model=BundleGeneratorResponse)
def generate_bundles(req: BundleGeneratorRequest):
    try:
        generation_config = BundleGenerationConfig(
            offer_type=req.offer_type,
            allowed_bundle_types=req.allowed_bundle_types,
            validity_options=req.validity_options,
            max_volume_mb=req.max_volume_mb,
            max_volume_min=req.max_volume_min,
            max_volume_sms=req.max_volume_sms,
            samples_per_type=req.samples_per_type,
            top_n_per_bundle_type=req.top_n,
        )

        generator = BundlesGenerator(generationConfig=generation_config)

        existing_df = generator._BundlesGenerator__exiting_products()
        generated_df = generator._BundlesGenerator__generate_products(generation_config)

        generated_df = _ensure_generated_bundle_ids(generated_df)
        generated_df = _ensure_validity_bucket(generated_df)

        existing_df = _normalize_existing_df(existing_df)
        generated_df = _normalize_generated_df(generated_df)

        results_df, summary_df = run_pipeline(
            existing_df=existing_df,
            generated_df=generated_df,
            params=ModelParams(),
            top_n=None,
            verbose=False,
        )

        top_per_type_df = _top_n_per_bundle_type(summary_df, n=req.top_n)
        params = ModelParams()

        return BundleGeneratorResponse(
            request=req,
            meta=GeneratorMeta(
                existing_count=len(existing_df),
                generated_count=len(generated_df),
                summary_count=len(summary_df),
                top_per_type_count=len(top_per_type_df),
            ),
            model_params=DashboardModelParams(
                growth_rate=params.growth_rate,
                cannib_sensitivity=params.cannib_sensitivity,
                price_elasticity=params.price_elasticity,
                similarity_threshold=params.similarity_threshold,
                cannib_cap=params.cannib_cap,
                expected_new_market_pct=params.expected_new_market_pct,
                cross_type_penalty=0.6,
                feature_weights=params.feature_weights,
            ),
            existing_bundles=[
                ExistingBundleItem(**row)
                for row in _dataframe_to_records(existing_df)
            ],
            generated_bundles=[
                GeneratedBundleItem(**row)
                for row in _dataframe_to_records(generated_df)
            ],
            summary=_dataframe_to_records(summary_df),
            top_per_type=_dataframe_to_records(top_per_type_df),
            impact_rows=_dataframe_to_records(results_df),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
