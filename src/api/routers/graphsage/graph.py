import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from fastapi import APIRouter, HTTPException, Query

from src.app.customers.targeting.graphSAGE.config import ArtifactConfig
from src.api.models.graphsage.graph import (
    GraphDataResponse,
    GraphEdge,
    GraphNode,
    GraphNodeSearchResponse,
    GraphSAGEGraphStatsResponse,
)


router = APIRouter(prefix="/graph", tags=["GraphSAGE Visualization"])


USER_NODE_COLS = [
    "user_idx",
    "msisdn",
    "raw_events",
    "active_days",
    "distinct_bundles",
    "total_subscriptions",
    "total_revenue",
    "avg_price",
    "max_price",
    "subs_data",
    "subs_voice",
    "subs_sms",
    "service_class_category",
    "canal",
    "payment_mode",
    "department_city",
    "brand_name",
    "device_capability",
]

BUNDLE_NODE_COLS = [
    "bundle_idx",
    "bundle_id",
    "bundle_name",
    "bundle_type",
    "price",
    "configured_volume_mb",
    "configured_volume_min",
    "configured_volume_sms",
    "validity_hours",
    "raw_events",
    "distinct_users",
    "total_subscriptions",
    "total_revenue",
]

EDGE_COLS = [
    "user_idx",
    "bundle_idx",
    "msisdn",
    "bundle_id",
    "raw_events",
    "active_days",
    "total_subscriptions",
    "total_revenue",
    "price",
    "first_tbl_dt",
    "last_tbl_dt",
]


def get_graph_dir() -> Path:
    return ArtifactConfig().graph_dir


def get_path(filename: str) -> Path:
    path = get_graph_dir() / filename

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Graph file not found: {path}")

    return path


def parquet_sql_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def get_parquet_row_count(path: Path) -> int:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Graph file not found: {path}")

    return pq.ParquetFile(path).metadata.num_rows


def clean_value(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, float) and np.isnan(value):
        return None

    if pd.isna(value):
        return None

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        return float(value)

    return value


def row_features(row: pd.Series, exclude: set[str]) -> Dict[str, Any]:
    return {
        col: clean_value(row[col])
        for col in row.index
        if col not in exclude
    }


def make_user_node(row: pd.Series) -> GraphNode:
    msisdn = str(row["msisdn"])
    return GraphNode(
        id=f"user:{int(row['user_idx'])}",
        node_type="user",
        label=msisdn,
        features=row_features(row, exclude=set()),
    )


def make_bundle_node(row: pd.Series) -> GraphNode:
    bundle_name = str(row.get("bundle_name") or row.get("bundle_id") or row["bundle_idx"])
    return GraphNode(
        id=f"bundle:{int(row['bundle_idx'])}",
        node_type="bundle",
        label=bundle_name,
        features=row_features(row, exclude=set()),
    )


def make_edge(row: pd.Series, idx: int) -> GraphEdge:
    user_idx = int(row["user_idx"])
    bundle_idx = int(row["bundle_idx"])

    return GraphEdge(
        id=f"edge:{user_idx}:{bundle_idx}:{idx}",
        source=f"user:{user_idx}",
        target=f"bundle:{bundle_idx}",
        edge_type="subscribed_to",
        features=row_features(row, exclude={"user_idx", "bundle_idx"}),
    )


def build_graph_response(
    users_df: pd.DataFrame,
    bundles_df: pd.DataFrame,
    edges_df: pd.DataFrame,
    requested_edge_limit: int,
) -> GraphDataResponse:
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []

    if not users_df.empty:
        users_df = users_df.drop_duplicates("user_idx")
        nodes.extend(make_user_node(row) for _, row in users_df.iterrows())

    if not bundles_df.empty:
        bundles_df = bundles_df.drop_duplicates("bundle_idx")
        nodes.extend(make_bundle_node(row) for _, row in bundles_df.iterrows())

    if not edges_df.empty:
        edges.extend(make_edge(row, idx) for idx, (_, row) in enumerate(edges_df.iterrows()))

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "truncated": len(edges) >= requested_edge_limit,
    }


def query_df(sql: str, params: Optional[list[Any]] = None) -> pd.DataFrame:
    con = duckdb.connect(database=":memory:")

    try:
        return con.execute(sql, params or []).fetchdf()
    finally:
        con.close()


def sql_in_clause(values: list[Any]) -> str:
    if not values:
        return "(NULL)"

    cleaned = []

    for value in values:
        if isinstance(value, str):
            cleaned.append("'" + value.replace("'", "''") + "'")
        else:
            cleaned.append(str(int(value)))

    return "(" + ", ".join(cleaned) + ")"


@lru_cache(maxsize=1)
def load_graph_stats() -> dict:
    graph_dir = get_graph_dir()

    msisdn_nodes = get_parquet_row_count(graph_dir / "user_nodes_train.parquet")
    bundle_nodes = get_parquet_row_count(graph_dir / "bundle_nodes_train.parquet")

    train_edges = get_parquet_row_count(graph_dir / "train_edges.parquet")
    val_edges = get_parquet_row_count(graph_dir / "val_edges.parquet")
    test_edges = get_parquet_row_count(graph_dir / "test_edges.parquet")

    total_edges = train_edges + val_edges + test_edges
    total_nodes = msisdn_nodes + bundle_nodes
    avg_degree = (2 * total_edges / total_nodes) if total_nodes else 0.0

    return {
        "msisdn_nodes": msisdn_nodes,
        "bundle_nodes": bundle_nodes,
        "train_edges": train_edges,
        "val_edges": val_edges,
        "test_edges": test_edges,
        "total_edges": total_edges,
        "avg_degree": round(avg_degree, 4),
    }


@router.get("/stats", response_model=GraphSAGEGraphStatsResponse)
def get_graph_stats():
    return load_graph_stats()


@router.get("/sample", response_model=GraphDataResponse)
def get_graph_sample(
    max_edges: int = Query(300, ge=1, le=2000),
    max_users: int = Query(150, ge=1, le=1000),
    max_bundles: int = Query(100, ge=1, le=1000),
):
    user_path = parquet_sql_path(get_path("user_nodes_train.parquet"))
    bundle_path = parquet_sql_path(get_path("bundle_nodes_train.parquet"))
    edge_path = parquet_sql_path(get_path("train_edges.parquet"))

    edge_cols = ", ".join(EDGE_COLS)

    edges_df = query_df(
        f"""
        SELECT {edge_cols}
        FROM read_parquet(?)
        ORDER BY total_subscriptions DESC NULLS LAST,
                 total_revenue DESC NULLS LAST,
                 raw_events DESC NULLS LAST
        LIMIT ?
        """,
        [edge_path, max_edges],
    )

    if edges_df.empty:
        return build_graph_response(
            users_df=pd.DataFrame(),
            bundles_df=pd.DataFrame(),
            edges_df=pd.DataFrame(),
            requested_edge_limit=max_edges,
        )

    user_ids = edges_df["user_idx"].dropna().astype(int).drop_duplicates().head(max_users).tolist()
    bundle_ids = edges_df["bundle_idx"].dropna().astype(int).drop_duplicates().head(max_bundles).tolist()

    edges_df = edges_df[
        edges_df["user_idx"].astype(int).isin(user_ids)
        & edges_df["bundle_idx"].astype(int).isin(bundle_ids)
    ].head(max_edges)

    users_df = query_df(
        f"""
        SELECT {", ".join(USER_NODE_COLS)}
        FROM read_parquet(?)
        WHERE user_idx IN {sql_in_clause(user_ids)}
        """,
        [user_path],
    )

    bundles_df = query_df(
        f"""
        SELECT {", ".join(BUNDLE_NODE_COLS)}
        FROM read_parquet(?)
        WHERE bundle_idx IN {sql_in_clause(bundle_ids)}
        """,
        [bundle_path],
    )

    return build_graph_response(
        users_df=users_df,
        bundles_df=bundles_df,
        edges_df=edges_df,
        requested_edge_limit=max_edges,
    )


@router.get("/neighborhood/msisdn/{msisdn}", response_model=GraphDataResponse)
def get_msisdn_neighborhood(
    msisdn: str,
    max_edges: int = Query(100, ge=1, le=1000),
):
    user_path = parquet_sql_path(get_path("user_nodes_train.parquet"))
    bundle_path = parquet_sql_path(get_path("bundle_nodes_train.parquet"))
    edge_path = parquet_sql_path(get_path("train_edges.parquet"))

    user_df = query_df(
        f"""
        SELECT {", ".join(USER_NODE_COLS)}
        FROM read_parquet(?)
        WHERE CAST(msisdn AS VARCHAR) = ?
        LIMIT 1
        """,
        [user_path, str(msisdn)],
    )

    if user_df.empty:
        raise HTTPException(status_code=404, detail=f"MSISDN not found: {msisdn}")

    user_idx = int(user_df.iloc[0]["user_idx"])

    edges_df = query_df(
        f"""
        SELECT {", ".join(EDGE_COLS)}
        FROM read_parquet(?)
        WHERE user_idx = ?
        ORDER BY total_subscriptions DESC NULLS LAST,
                 total_revenue DESC NULLS LAST,
                 raw_events DESC NULLS LAST
        LIMIT ?
        """,
        [edge_path, user_idx, max_edges],
    )

    bundle_ids = (
        edges_df["bundle_idx"].dropna().astype(int).drop_duplicates().tolist()
        if not edges_df.empty
        else []
    )

    bundles_df = pd.DataFrame()

    if bundle_ids:
        bundles_df = query_df(
            f"""
            SELECT {", ".join(BUNDLE_NODE_COLS)}
            FROM read_parquet(?)
            WHERE bundle_idx IN {sql_in_clause(bundle_ids)}
            """,
            [bundle_path],
        )

    return build_graph_response(
        users_df=user_df,
        bundles_df=bundles_df,
        edges_df=edges_df,
        requested_edge_limit=max_edges,
    )


@router.get("/neighborhood/bundle/{bundle_id}", response_model=GraphDataResponse)
def get_bundle_neighborhood(
    bundle_id: str,
    max_edges: int = Query(100, ge=1, le=1000),
):
    user_path = parquet_sql_path(get_path("user_nodes_train.parquet"))
    bundle_path = parquet_sql_path(get_path("bundle_nodes_train.parquet"))
    edge_path = parquet_sql_path(get_path("train_edges.parquet"))

    bundle_df = query_df(
        f"""
        SELECT {", ".join(BUNDLE_NODE_COLS)}
        FROM read_parquet(?)
        WHERE CAST(bundle_id AS VARCHAR) = ?
        LIMIT 1
        """,
        [bundle_path, str(bundle_id)],
    )

    if bundle_df.empty:
        raise HTTPException(status_code=404, detail=f"Bundle not found: {bundle_id}")

    bundle_idx = int(bundle_df.iloc[0]["bundle_idx"])

    edges_df = query_df(
        f"""
        SELECT {", ".join(EDGE_COLS)}
        FROM read_parquet(?)
        WHERE bundle_idx = ?
        ORDER BY total_subscriptions DESC NULLS LAST,
                 total_revenue DESC NULLS LAST,
                 raw_events DESC NULLS LAST
        LIMIT ?
        """,
        [edge_path, bundle_idx, max_edges],
    )

    user_ids = (
        edges_df["user_idx"].dropna().astype(int).drop_duplicates().tolist()
        if not edges_df.empty
        else []
    )

    users_df = pd.DataFrame()

    if user_ids:
        users_df = query_df(
            f"""
            SELECT {", ".join(USER_NODE_COLS)}
            FROM read_parquet(?)
            WHERE user_idx IN {sql_in_clause(user_ids)}
            """,
            [user_path],
        )

    return build_graph_response(
        users_df=users_df,
        bundles_df=bundle_df,
        edges_df=edges_df,
        requested_edge_limit=max_edges,
    )


@router.get("/search", response_model=GraphNodeSearchResponse)
def search_graph_nodes(
    q: str = Query(..., min_length=1),
    node_type: str = Query("all", pattern="^(all|user|bundle)$"),
    limit: int = Query(20, ge=1, le=100),
):
    user_path = parquet_sql_path(get_path("user_nodes_train.parquet"))
    bundle_path = parquet_sql_path(get_path("bundle_nodes_train.parquet"))

    results = []
    q_like = f"%{q}%"

    if node_type in {"all", "user"}:
        users_df = query_df(
            f"""
            SELECT {", ".join(USER_NODE_COLS)}
            FROM read_parquet(?)
            WHERE CAST(msisdn AS VARCHAR) ILIKE ?
            LIMIT ?
            """,
            [user_path, q_like, limit],
        )

        for _, row in users_df.iterrows():
            results.append(make_user_node(row).model_dump())

    remaining = limit - len(results)

    if remaining > 0 and node_type in {"all", "bundle"}:
        bundles_df = query_df(
            f"""
            SELECT {", ".join(BUNDLE_NODE_COLS)}
            FROM read_parquet(?)
            WHERE CAST(bundle_id AS VARCHAR) ILIKE ?
               OR CAST(bundle_name AS VARCHAR) ILIKE ?
               OR CAST(bundle_type AS VARCHAR) ILIKE ?
            LIMIT ?
            """,
            [bundle_path, q_like, q_like, q_like, remaining],
        )

        for _, row in bundles_df.iterrows():
            results.append(make_bundle_node(row).model_dump())

    return {
        "total_returned": len(results),
        "results": results,
    }