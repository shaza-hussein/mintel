import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

from src.app.customers.targeting.graphSAGE.config import ArtifactConfig
from src.api.models.graphsage.coldstart import (
    ColdStartFeatureOptionsResponse,
    ColdStartRecommendationRequest,
    ColdStartRecommendationResponse,
)


router = APIRouter(
    prefix="/graphsage/cold-start",
    tags=["GraphSAGE Cold Start"],
)


USER_FEATURE_COLS = [
    "service_class_category",
    "canal",
    "payment_mode",
    "department_city",
    "brand_name",
    "device_capability",
]

BUNDLE_COLS = [
    "bundle_idx",
    "bundle_id",
    "bundle_name",
    "bundle_type",
    "price",
    "distinct_users",
    "total_subscriptions",
    "total_revenue",
]

TRAIN_EDGE_COLS = [
    "user_idx",
    "bundle_idx",
    "raw_events",
    "active_days",
    "total_subscriptions",
    "total_revenue",
]


def get_graph_dir() -> Path:
    return ArtifactConfig().graph_dir


def clean_options(series: pd.Series) -> List[str]:
    values = (
        series
        .dropna()
        .astype(str)
        .str.strip()
    )
    values = values[values != ""]
    values = values[values.str.lower() != "nan"]
    return sorted(values.unique().tolist())


def minmax(series: pd.Series) -> pd.Series:
    series = pd.to_numeric(series, errors="coerce").fillna(0.0)
    min_value = float(series.min())
    max_value = float(series.max())

    if max_value == min_value:
        return pd.Series(np.ones(len(series)), index=series.index)

    return (series - min_value) / (max_value - min_value)


@lru_cache(maxsize=1)
def load_user_nodes_df() -> pd.DataFrame:
    path = get_graph_dir() / "user_nodes_train.parquet"

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"User nodes file not found: {path}")

    columns = ["user_idx"] + USER_FEATURE_COLS
    return pd.read_parquet(path, columns=columns)


@lru_cache(maxsize=1)
def load_bundle_nodes_df() -> pd.DataFrame:
    path = get_graph_dir() / "bundle_nodes_train.parquet"

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Bundle nodes file not found: {path}")

    return pd.read_parquet(path, columns=BUNDLE_COLS)


@lru_cache(maxsize=1)
def load_train_edges_df() -> pd.DataFrame:
    path = get_graph_dir() / "train_edges.parquet"

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Train edges file not found: {path}")

    return pd.read_parquet(path, columns=TRAIN_EDGE_COLS)


@router.get("/features", response_model=ColdStartFeatureOptionsResponse)
def get_cold_start_feature_options():
    user_nodes_df = load_user_nodes_df()
    bundle_nodes_df = load_bundle_nodes_df()

    prices = pd.to_numeric(bundle_nodes_df["price"], errors="coerce")

    return {
        "service_class_category": clean_options(user_nodes_df["service_class_category"]),
        "canal": clean_options(user_nodes_df["canal"]),
        "payment_mode": clean_options(user_nodes_df["payment_mode"]),
        "department_city": clean_options(user_nodes_df["department_city"]),
        "brand_name": clean_options(user_nodes_df["brand_name"]),
        "device_capability": clean_options(user_nodes_df["device_capability"]),
        "bundle_type": clean_options(bundle_nodes_df["bundle_type"]),
        "min_price": float(prices.min()) if prices.notna().any() else None,
        "max_price": float(prices.max()) if prices.notna().any() else None,
    }


def find_cold_start_cohort(
    user_nodes_df: pd.DataFrame,
    profile: dict,
    min_cohort_users: int,
) -> tuple[pd.DataFrame, List[str]]:
    if not profile:
        return pd.DataFrame(), []

    feature_priority = [
        "service_class_category",
        "payment_mode",
        "device_capability",
        "brand_name",
        "department_city",
        "canal",
    ]

    active_features = [
        feature
        for feature in feature_priority
        if feature in profile and feature in user_nodes_df.columns
    ]

    while active_features:
        cohort = user_nodes_df.copy()

        for feature in active_features:
            cohort = cohort[
                cohort[feature].fillna("UNK").astype(str) == str(profile[feature])
            ]

        if len(cohort) >= min_cohort_users:
            return cohort, active_features.copy()

        active_features = active_features[:-1]

    return pd.DataFrame(), []


def global_cold_start_recommendations(
    msisdn: str,
    top_k: int,
    bundle_type: Optional[str],
    min_price: Optional[float],
    max_price: Optional[float],
    reason: str,
) -> pd.DataFrame:
    df = load_bundle_nodes_df().copy()

    if bundle_type is not None:
        df = df[df["bundle_type"].astype(str) == str(bundle_type)]

    if min_price is not None:
        df = df[pd.to_numeric(df["price"], errors="coerce") >= float(min_price)]

    if max_price is not None:
        df = df[pd.to_numeric(df["price"], errors="coerce") <= float(max_price)]

    if df.empty:
        return pd.DataFrame()

    for col in ["distinct_users", "total_subscriptions", "total_revenue"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["score"] = (
        0.50 * minmax(df["distinct_users"])
        + 0.30 * minmax(df["total_subscriptions"])
        + 0.20 * minmax(df["total_revenue"])
    )

    df = df.sort_values(
        ["score", "distinct_users", "total_subscriptions", "total_revenue"],
        ascending=False,
    ).head(top_k)

    rows = []

    for rank, (_, row) in enumerate(df.iterrows(), start=1):
        rows.append(
            {
                "rank": rank,
                "msisdn": str(msisdn),
                "user_idx": None,
                "bundle_idx": int(row["bundle_idx"]),
                "bundle_id": str(row["bundle_id"]),
                "bundle_name": str(row.get("bundle_name", "")),
                "bundle_type": str(row.get("bundle_type", "")),
                "price": float(row.get("price", np.nan)),
                "score": float(row["score"]),
                "recommendation_type": reason,
                "matched_features": [],
                "cohort_size": 0,
            }
        )

    return pd.DataFrame(rows)


@router.post("/recommendations", response_model=ColdStartRecommendationResponse)
def get_cold_start_recommendations(req: ColdStartRecommendationRequest):
    user_nodes_df = load_user_nodes_df()
    bundle_nodes_df = load_bundle_nodes_df()
    train_edges_df = load_train_edges_df()

    profile = {
        "service_class_category": req.service_class_category,
        "canal": req.canal,
        "payment_mode": req.payment_mode,
        "department_city": req.department_city,
        "brand_name": req.brand_name,
        "device_capability": req.device_capability,
    }

    profile = {
        key: str(value)
        for key, value in profile.items()
        if value is not None and str(value).strip()
    }

    cohort_users_df, matched_features = find_cold_start_cohort(
        user_nodes_df=user_nodes_df,
        profile=profile,
        min_cohort_users=req.min_cohort_users,
    )

    if cohort_users_df.empty:
        rec_df = global_cold_start_recommendations(
            msisdn=req.msisdn,
            top_k=req.top_k,
            bundle_type=req.bundle_type,
            min_price=req.min_price,
            max_price=req.max_price,
            reason="global_popularity_no_matching_cohort",
        )
    else:
        cohort_user_indices = set(cohort_users_df["user_idx"].astype(int).tolist())

        cohort_edges = train_edges_df[
            train_edges_df["user_idx"].astype(int).isin(cohort_user_indices)
        ].copy()

        if cohort_edges.empty:
            rec_df = global_cold_start_recommendations(
                msisdn=req.msisdn,
                top_k=req.top_k,
                bundle_type=req.bundle_type,
                min_price=req.min_price,
                max_price=req.max_price,
                reason="global_popularity_empty_cohort_edges",
            )
        else:
            for col in ["raw_events", "active_days", "total_subscriptions", "total_revenue"]:
                cohort_edges[col] = pd.to_numeric(
                    cohort_edges[col],
                    errors="coerce",
                ).fillna(0.0)

            scored = (
                cohort_edges
                .groupby("bundle_idx", as_index=False)
                .agg(
                    cohort_users=("user_idx", "nunique"),
                    cohort_raw_events=("raw_events", "sum"),
                    cohort_active_days=("active_days", "sum"),
                    cohort_subscriptions=("total_subscriptions", "sum"),
                    cohort_revenue=("total_revenue", "sum"),
                )
            )

            scored = scored.merge(
                bundle_nodes_df,
                on="bundle_idx",
                how="left",
            )

            if req.bundle_type is not None:
                scored = scored[scored["bundle_type"].astype(str) == str(req.bundle_type)]

            if req.min_price is not None:
                scored = scored[
                    pd.to_numeric(scored["price"], errors="coerce") >= float(req.min_price)
                ]

            if req.max_price is not None:
                scored = scored[
                    pd.to_numeric(scored["price"], errors="coerce") <= float(req.max_price)
                ]

            if scored.empty:
                rec_df = global_cold_start_recommendations(
                    msisdn=req.msisdn,
                    top_k=req.top_k,
                    bundle_type=req.bundle_type,
                    min_price=req.min_price,
                    max_price=req.max_price,
                    reason="global_popularity_after_filters",
                )
            else:
                for col in [
                    "cohort_users",
                    "cohort_raw_events",
                    "cohort_active_days",
                    "cohort_subscriptions",
                    "cohort_revenue",
                    "distinct_users",
                    "total_subscriptions",
                    "total_revenue",
                ]:
                    scored[col] = pd.to_numeric(scored[col], errors="coerce").fillna(0.0)

                scored["score"] = (
                    0.35 * minmax(scored["cohort_users"])
                    + 0.25 * minmax(scored["cohort_subscriptions"])
                    + 0.20 * minmax(scored["cohort_revenue"])
                    + 0.10 * minmax(scored["distinct_users"])
                    + 0.10 * minmax(scored["total_subscriptions"])
                )

                scored = scored.sort_values(
                    ["score", "cohort_users", "cohort_subscriptions", "cohort_revenue"],
                    ascending=False,
                ).head(req.top_k)

                rows = []

                for rank, (_, row) in enumerate(scored.iterrows(), start=1):
                    rows.append(
                        {
                            "rank": rank,
                            "msisdn": str(req.msisdn),
                            "user_idx": None,
                            "bundle_idx": int(row["bundle_idx"]),
                            "bundle_id": str(row["bundle_id"]),
                            "bundle_name": str(row.get("bundle_name", "")),
                            "bundle_type": str(row.get("bundle_type", "")),
                            "price": float(row.get("price", np.nan)),
                            "score": float(row["score"]),
                            "recommendation_type": "cold_start_cohort",
                            "matched_features": matched_features,
                            "cohort_size": int(len(cohort_users_df)),
                        }
                    )

                rec_df = pd.DataFrame(rows)

    recommendations = rec_df.replace({np.nan: None}).to_dict(orient="records")

    return {
        "msisdn": str(req.msisdn),
        "total_returned": len(recommendations),
        "recommendations": recommendations,
    }