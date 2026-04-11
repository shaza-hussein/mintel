import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

import ast
import json
from pathlib import Path
from typing import Optional, Sequence

import pandas as pd

from src.app.products.mba.config import ArtifactConfig

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


def recommend_bundle_candidates_from_itemsets(
    frequent_itemsets_path: Optional[Path] = None,
    metrics_path: Optional[Path] = None,
    top_k: int = 10,
    allowed_sizes: Sequence[int] = (2, 3),
    min_freq: int = 1000,
    min_support_pct: float = 0.001,
    size_weight: float = 0.20,
    suppress_subsets: bool = True,
    subset_score_ratio: float = 0.85,
) -> pd.DataFrame:
    """
    Generate candidate new bundles from frequent itemsets.

    This is for bundle creation / ideation, not personalized recommendation.

    Args:
        frequent_itemsets_path: Path to frequent_itemsets.csv
        metrics_path: Path to metrics.json to compute support percentage
        top_k: Number of candidate bundles to return
        allowed_sizes: Only keep combos with these sizes, usually (2, 3)
        min_freq: Minimum absolute frequency threshold
        min_support_pct: Minimum support threshold relative to total transactions
        size_weight: Extra score bonus per additional item
        suppress_subsets: If True, suppress smaller subsets when a larger set is strong enough
        subset_score_ratio: Subset is removed if superset score >= subset_score * this ratio

    Returns:
        DataFrame with candidate bundles ranked for product creation.
    """
    artifact_config = ArtifactConfig()
    resolved_itemsets_path = frequent_itemsets_path or artifact_config.frequent_itemsets_csv_path
    resolved_metrics_path = metrics_path or artifact_config.metrics_path

    logger.info(
        "Generating bundle candidates from frequent itemsets | path=%s | top_k=%d",
        resolved_itemsets_path,
        top_k,
    )

    itemsets_df = pd.read_csv(resolved_itemsets_path)
    itemsets_df["items"] = itemsets_df["items"].apply(_parse_list_column)
    itemsets_df["item_count"] = itemsets_df["items"].apply(len)

    transaction_count = _load_transaction_count(resolved_metrics_path)
    itemsets_df["support_pct"] = itemsets_df["freq"] / transaction_count

    candidate_df = itemsets_df[
        itemsets_df["item_count"].isin(allowed_sizes)
    ].copy()

    candidate_df = candidate_df[
        (candidate_df["freq"] >= min_freq)
        & (candidate_df["support_pct"] >= min_support_pct)
    ].copy()

    if candidate_df.empty:
        return pd.DataFrame(
            columns=[
                "bundle_components",
                "item_count",
                "freq",
                "support_pct",
                "score",
            ]
        )

    candidate_df["bundle_components"] = candidate_df["items"].apply(
        lambda items: " + ".join(items)
    )

    candidate_df["score"] = candidate_df.apply(
        lambda row: row["support_pct"] * (1 + size_weight * (row["item_count"] - 1)),
        axis=1,
    )

    candidate_df = candidate_df.sort_values(
        by=["score", "freq", "item_count"],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    if suppress_subsets:
        candidate_df = _suppress_redundant_subsets(
            candidate_df=candidate_df,
            subset_score_ratio=subset_score_ratio,
        )

    result_df = candidate_df.loc[
        :,
        [
            "bundle_components",
            "item_count",
            "freq",
            "support_pct",
            "score",
        ],
    ].head(top_k).reset_index(drop=True)

    return result_df


def _suppress_redundant_subsets(
    candidate_df: pd.DataFrame,
    subset_score_ratio: float,
) -> pd.DataFrame:
    kept_rows: list[dict] = []

    for _, row in candidate_df.iterrows():
        current_items = set(row["items"])
        current_score = float(row["score"])
        should_skip = False

        for kept in kept_rows:
            kept_items = set(kept["items"])
            kept_score = float(kept["score"])

            # Skip smaller combos when a larger selected combo already covers them
            # and the larger combo is competitive enough.
            if current_items.issubset(kept_items) and kept_score >= current_score * subset_score_ratio:
                should_skip = True
                break

        if not should_skip:
            kept_rows.append(row.to_dict())

    return pd.DataFrame(kept_rows)


def _load_transaction_count(metrics_path: Path) -> int:
    with metrics_path.open("r", encoding="utf-8") as file:
        metrics = json.load(file)

    transaction_count = int(metrics["transaction_count"])
    if transaction_count <= 0:
        raise ValueError("transaction_count must be positive in metrics.json")

    return transaction_count

def _parse_list_column(value: str) -> list[str]:
    if pd.isna(value):
        return []

    parsed = ast.literal_eval(value)
    return [
        str(item).replace("'", "").strip()
        for item in parsed
        if str(item).strip()
    ]

