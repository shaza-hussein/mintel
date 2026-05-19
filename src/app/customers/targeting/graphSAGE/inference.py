import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))

import logging
from typing import Optional, Sequence
from pathlib import Path
import csv
import numpy as np
import pandas as pd
import torch
from torch_geometric.data import HeteroData
from torch_geometric.loader import LinkNeighborLoader
from tqdm.auto import tqdm

from src.app.customers.targeting.graphSAGE.config import (
    EDGE_TYPE,
    REV_EDGE_TYPE,
    ArtifactConfig,
    GraphSAGEModelConfig,
)
from src.app.customers.targeting.graphSAGE.features import (
    read_json,
    transform_categorical,
    transform_numeric,
)
from src.app.customers.targeting.graphSAGE.model import HeteroGraphSAGE

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def _torch_load(path, map_location):
    try:
        return torch.load(path, map_location=map_location, weights_only=False)
    except TypeError:
        return torch.load(path, map_location=map_location)


class GraphSAGERecommender:
    def __init__(
        self,
        artifact_config: Optional[ArtifactConfig] = None,
        model_config: Optional[GraphSAGEModelConfig] = None,
    ) -> None:
        self.artifact_config = artifact_config or ArtifactConfig()
        self.model_config = model_config or GraphSAGEModelConfig()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("GraphSAGE model on %s", self.device)
        self.artifacts = _torch_load(self.artifact_config.artifacts_path, self.device)
        self.config = self.artifacts["config"]
        self._load_feature_metadata()

        self.msisdn_to_user_idx = {
            str(k): int(v)
            for k, v in self.artifacts["msisdn_to_user_idx"].items()
        }
        self.bundle_idx_to_bundle_id = {
            int(k): str(v)
            for k, v in self.artifacts["bundle_idx_to_bundle_id"].items()
        }
        self.bundle_idx_to_bundle_name = {
            int(k): str(v)
            for k, v in self.artifacts["bundle_idx_to_bundle_name"].items()
        }
        self.bundle_idx_to_bundle_type = {
            int(k): str(v)
            for k, v in self.artifacts["bundle_idx_to_bundle_type"].items()
        }
        self.bundle_idx_to_price = {
            int(k): float(v)
            for k, v in self.artifacts["bundle_idx_to_price"].items()
        }
        self.all_bundle_indices = np.asarray(
            self.artifacts["all_bundle_indices"],
            dtype=np.int64,
        )

        self.user_nodes_df = pd.read_parquet(
            self.artifact_config.graph_dir / "user_nodes_train.parquet"
        )
        self.bundle_nodes_df = pd.read_parquet(
            self.artifact_config.graph_dir / "bundle_nodes_train.parquet"
        )
        self.train_edges_df = pd.read_parquet(
            self.artifact_config.graph_dir / "train_edges.parquet"
        )

        self.data = self._load_graph_for_inference()
        self.train_history = self._load_train_history()
        self.model = self._load_model()

    def _load_feature_metadata(self) -> None:
        if not self.artifact_config.cat_metadata_path.exists():
            logger.warning(
                "cat_features_metadata.json was not found | path=%s",
                self.artifact_config.cat_metadata_path,
            )
            return

        feature_metadata = read_json(self.artifact_config.cat_metadata_path)

        for key in [
            "user_num_mean",
            "user_num_std",
            "bundle_num_mean",
            "bundle_num_std",
            "user_cat_maps",
            "bundle_cat_maps",
        ]:
            if key in feature_metadata:
                self.config[key] = feature_metadata[key]

        if "user_cat_cardinalities" in feature_metadata:
            self.config["user_cat_cardinalities"] = self._cardinality_dict_to_list(
                feature_metadata["user_cat_cardinalities"],
                self.config["user_cat_cols"],
            )

        if "bundle_cat_cardinalities" in feature_metadata:
            self.config["bundle_cat_cardinalities"] = self._cardinality_dict_to_list(
                feature_metadata["bundle_cat_cardinalities"],
                self.config["bundle_cat_cols"],
            )

    def _cardinality_dict_to_list(self, cardinalities: dict, cols: list[str]) -> list[int]:
        return [int(cardinalities[col]) for col in cols]

    def _load_graph_for_inference(self):
        user_x_num = transform_numeric(
            self.user_nodes_df,
            self.config["user_num_cols"],
            self.config["user_num_mean"],
            self.config["user_num_std"],
        )
        bundle_x_num = transform_numeric(
            self.bundle_nodes_df,
            self.config["bundle_num_cols"],
            self.config["bundle_num_mean"],
            self.config["bundle_num_std"],
        )
        user_x_cat = transform_categorical(
            self.user_nodes_df,
            self.config["user_cat_cols"],
            self.config["user_cat_maps"],
        )
        bundle_x_cat = transform_categorical(
            self.bundle_nodes_df,
            self.config["bundle_cat_cols"],
            self.config["bundle_cat_maps"],
        )

        train_edge_index = torch.tensor(
            self.train_edges_df[["user_idx", "bundle_idx"]].to_numpy().T,
            dtype=torch.long,
        ).contiguous()

        data = HeteroData()
        data["user"].x_num = torch.from_numpy(user_x_num)
        data["user"].x_cat = torch.from_numpy(user_x_cat)
        data["user"].num_nodes = len(self.user_nodes_df)

        data["bundle"].x_num = torch.from_numpy(bundle_x_num)
        data["bundle"].x_cat = torch.from_numpy(bundle_x_cat)
        data["bundle"].num_nodes = len(self.bundle_nodes_df)

        data[EDGE_TYPE].edge_index = train_edge_index
        data[REV_EDGE_TYPE].edge_index = train_edge_index.flip(0).contiguous()

        return data

    def _load_train_history(self):
        return (
            self.train_edges_df
            .groupby("user_idx")["bundle_idx"]
            .apply(set)
            .to_dict()
        )

    def _load_model(self):
        model = HeteroGraphSAGE(
            user_num_dim=len(self.config["user_num_cols"]),
            user_cat_cardinalities=self.config["user_cat_cardinalities"],
            bundle_num_dim=len(self.config["bundle_num_cols"]),
            bundle_cat_cardinalities=self.config["bundle_cat_cardinalities"],
            hidden_dim=self.config["hidden_dim"],
            cat_emb_dim=self.config["cat_emb_dim"],
            num_layers=self.config["num_layers"],
            dropout=self.config["dropout"],
        ).to(self.device)

        model.load_state_dict(self.artifacts["model_state_dict"])
        model.eval()
        return model

    @torch.no_grad()
    def score_user_bundle_pairs(
        self,
        user_indices,
        bundle_indices,
        batch_size: Optional[int] = None,
    ) -> np.ndarray:
        batch_size = batch_size or self.model_config.eval_batch_size

        user_indices = np.asarray(user_indices, dtype=np.int64)
        bundle_indices = np.asarray(bundle_indices, dtype=np.int64)

        if len(user_indices) != len(bundle_indices):
            raise ValueError("user_indices and bundle_indices must have the same length")

        pair_ids = torch.arange(len(user_indices), dtype=torch.long)
        edge_label_index = torch.tensor(
            np.stack([user_indices, bundle_indices], axis=0),
            dtype=torch.long,
        ).contiguous()

        loader = LinkNeighborLoader(
            data=self.data,
            num_neighbors=self.model_config.num_neighbors,
            edge_label_index=(EDGE_TYPE, edge_label_index),
            edge_label=pair_ids,
            neg_sampling_ratio=0.0,
            batch_size=batch_size,
            shuffle=False,
            num_workers=0,
            pin_memory=torch.cuda.is_available(),
        )

        scores = np.empty(len(user_indices), dtype=np.float32)

        for batch in tqdm(loader, desc="score pairs", leave=False):
            batch = batch.to(self.device)
            z_dict = self.model(batch)
            logits = self.model.score(z_dict, batch[EDGE_TYPE].edge_label_index)
            probs = torch.sigmoid(logits).detach().cpu().numpy()
            ids = batch[EDGE_TYPE].edge_label.detach().cpu().numpy().astype(np.int64)
            scores[ids] = probs

        return scores

    def recommend_for_msisdn(
        self,
        msisdn: str,
        top_k: int = 10,
        exclude_seen: bool = False,
    ) -> pd.DataFrame:
        result = self.recommend_for_msisdns(
            msisdns=[msisdn],
            top_k=top_k,
            exclude_seen=exclude_seen,
            include_cold_start=False,
        )

        if result.empty:
            raise ValueError(
                "This MSISDN was not seen in the training graph. "
                "Use recommend_cold_start or set include_cold_start=True."
            )

        return result

    def recommend_for_msisdns(
        self,
        msisdns: Sequence[str],
        top_k: int = 10,
        exclude_seen: bool = False,
        include_cold_start: bool = True,
        cold_start_profiles: Optional[dict[str, dict]] = None,
        user_chunk_size: int = 100,
        batch_size: Optional[int] = None,
    ) -> pd.DataFrame:
        known = []
        cold = []

        for msisdn in msisdns:
            msisdn = str(msisdn)
            if msisdn in self.msisdn_to_user_idx:
                known.append(msisdn)
            else:
                cold.append(msisdn)

        rows = []

        for start in range(0, len(known), user_chunk_size):
            chunk_msisdns = known[start:start + user_chunk_size]
            user_indices = np.asarray(
                [self.msisdn_to_user_idx[msisdn] for msisdn in chunk_msisdns],
                dtype=np.int64,
            )

            candidate_bundles = self.all_bundle_indices.astype(np.int64)
            num_users = len(user_indices)
            num_bundles = len(candidate_bundles)

            pair_users = np.repeat(user_indices, num_bundles)
            pair_bundles = np.tile(candidate_bundles, num_users)

            scores = self.score_user_bundle_pairs(
                pair_users,
                pair_bundles,
                batch_size=batch_size,
            ).reshape(num_users, num_bundles)

            for row_idx, msisdn in enumerate(chunk_msisdns):
                user_idx = int(user_indices[row_idx])
                row_scores = scores[row_idx].copy()

                if exclude_seen:
                    seen = self.train_history.get(user_idx, set())
                    if seen:
                        seen_mask = np.isin(candidate_bundles, list(seen))
                        row_scores[seen_mask] = -np.inf

                top_pos = np.argsort(-row_scores)[:top_k]

                for rank, pos in enumerate(top_pos, start=1):
                    bundle_idx = int(candidate_bundles[pos])
                    rows.append(
                        self._format_recommendation_row(
                            rank=rank,
                            msisdn=msisdn,
                            user_idx=user_idx,
                            bundle_idx=bundle_idx,
                            score=float(row_scores[pos]),
                            recommendation_type="graphsage",
                            matched_features=[],
                            cohort_size=None,
                        )
                    )

        if include_cold_start:
            cold_start_profiles = cold_start_profiles or {}

            for msisdn in cold:
                profile = cold_start_profiles.get(str(msisdn), {})
                cold_df = self.recommend_cold_start(
                    msisdn=msisdn,
                    top_k=top_k,
                    **profile,
                )
                rows.extend(cold_df.to_dict(orient="records"))

        return pd.DataFrame(rows)

    def recommend_cold_start(
        self,
        msisdn: str,
        top_k: int = 10,
        service_class_category: Optional[str] = None,
        canal: Optional[str] = None,
        payment_mode: Optional[str] = None,
        department_city: Optional[str] = None,
        brand_name: Optional[str] = None,
        device_capability: Optional[str] = None,
        bundle_type: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_cohort_users: int = 100,
    ) -> pd.DataFrame:
        msisdn = str(msisdn)

        profile = {
            "service_class_category": service_class_category,
            "canal": canal,
            "payment_mode": payment_mode,
            "department_city": department_city,
            "brand_name": brand_name,
            "device_capability": device_capability,
        }
        profile = {
            key: str(value)
            for key, value in profile.items()
            if value is not None and str(value).strip()
        }

        cohort_users_df, matched_features = self._find_cold_start_cohort(
            profile=profile,
            min_cohort_users=min_cohort_users,
        )

        if cohort_users_df.empty:
            return self._global_cold_start_recommendations(
                msisdn=msisdn,
                top_k=top_k,
                bundle_type=bundle_type,
                min_price=min_price,
                max_price=max_price,
                reason="global_popularity_no_matching_cohort",
            )

        cohort_user_indices = set(cohort_users_df["user_idx"].astype(int).tolist())
        cohort_edges = self.train_edges_df[
            self.train_edges_df["user_idx"].astype(int).isin(cohort_user_indices)
        ].copy()

        if cohort_edges.empty:
            return self._global_cold_start_recommendations(
                msisdn=msisdn,
                top_k=top_k,
                bundle_type=bundle_type,
                min_price=min_price,
                max_price=max_price,
                reason="global_popularity_empty_cohort_edges",
            )

        for col in ["raw_events", "active_days", "total_subscriptions", "total_revenue"]:
            cohort_edges[col] = pd.to_numeric(cohort_edges[col], errors="coerce").fillna(0.0)

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

        bundle_cols = [
            "bundle_idx",
            "bundle_id",
            "bundle_name",
            "bundle_type",
            "price",
            "distinct_users",
            "total_subscriptions",
            "total_revenue",
        ]

        scored = scored.merge(
            self.bundle_nodes_df[bundle_cols],
            on="bundle_idx",
            how="left",
        )

        if bundle_type is not None:
            scored = scored[scored["bundle_type"].astype(str) == str(bundle_type)]

        if min_price is not None:
            scored = scored[pd.to_numeric(scored["price"], errors="coerce") >= float(min_price)]

        if max_price is not None:
            scored = scored[pd.to_numeric(scored["price"], errors="coerce") <= float(max_price)]

        if scored.empty:
            return self._global_cold_start_recommendations(
                msisdn=msisdn,
                top_k=top_k,
                bundle_type=bundle_type,
                min_price=min_price,
                max_price=max_price,
                reason="global_popularity_after_filters",
            )

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
            0.35 * self._minmax(scored["cohort_users"])
            + 0.25 * self._minmax(scored["cohort_subscriptions"])
            + 0.20 * self._minmax(scored["cohort_revenue"])
            + 0.10 * self._minmax(scored["distinct_users"])
            + 0.10 * self._minmax(scored["total_subscriptions"])
        )

        scored = scored.sort_values(
            ["score", "cohort_users", "cohort_subscriptions", "cohort_revenue"],
            ascending=False,
        ).head(top_k)

        rows = []
        for rank, (_, row) in enumerate(scored.iterrows(), start=1):
            rows.append(
                {
                    "rank": rank,
                    "msisdn": msisdn,
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

        return pd.DataFrame(rows)

    def _find_cold_start_cohort(
        self,
        profile: dict,
        min_cohort_users: int,
    ) -> tuple[pd.DataFrame, list[str]]:
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
            if feature in profile and feature in self.user_nodes_df.columns
        ]

        while active_features:
            cohort = self.user_nodes_df.copy()

            for feature in active_features:
                cohort = cohort[
                    cohort[feature].fillna("UNK").astype(str) == str(profile[feature])
                ]

            if len(cohort) >= min_cohort_users:
                return cohort, active_features.copy()

            active_features = active_features[:-1]

        return pd.DataFrame(), []

    def _global_cold_start_recommendations(
        self,
        msisdn: str,
        top_k: int,
        bundle_type: Optional[str],
        min_price: Optional[float],
        max_price: Optional[float],
        reason: str,
    ) -> pd.DataFrame:
        df = self.bundle_nodes_df.copy()

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
            0.50 * self._minmax(df["distinct_users"])
            + 0.30 * self._minmax(df["total_subscriptions"])
            + 0.20 * self._minmax(df["total_revenue"])
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

    def _minmax(self, series: pd.Series) -> pd.Series:
        series = pd.to_numeric(series, errors="coerce").fillna(0.0)
        min_value = float(series.min())
        max_value = float(series.max())

        if max_value == min_value:
            return pd.Series(np.ones(len(series)), index=series.index)

        return (series - min_value) / (max_value - min_value)

    def _format_recommendation_row(
        self,
        rank: int,
        msisdn: str,
        user_idx: int,
        bundle_idx: int,
        score: float,
        recommendation_type: str,
        matched_features: Optional[list[str]] = None,
        cohort_size: Optional[int] = None,
    ) -> dict:
        return {
            "rank": rank,
            "msisdn": msisdn,
            "user_idx": int(user_idx),
            "bundle_idx": int(bundle_idx),
            "bundle_id": self.bundle_idx_to_bundle_id[bundle_idx],
            "bundle_name": self.bundle_idx_to_bundle_name.get(bundle_idx, ""),
            "bundle_type": self.bundle_idx_to_bundle_type.get(bundle_idx, ""),
            "price": self.bundle_idx_to_price.get(bundle_idx, np.nan),
            "score": float(score),
            "recommendation_type": recommendation_type,
            "matched_features": matched_features or [],
            "cohort_size": cohort_size,
        }
    
    
    @torch.no_grad()
    def export_all_recommendations(
        self,
        out_path,
        top_k: int = 10,
        user_chunk_size: int = 8192,
        exclude_seen: bool = False,
    ) -> None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Moving full graph to %s", self.device)
        data = self.data.to(self.device)

        logger.info("Computing full-graph embeddings once")
        self.model.eval()
        z_dict = self.model(data)

        user_emb = z_dict["user"]
        bundle_indices = torch.as_tensor(
            self.all_bundle_indices,
            dtype=torch.long,
            device=self.device,
        )

        bundle_emb = z_dict["bundle"][bundle_indices]
        bundle_emb_t = bundle_emb.T.contiguous()

        idx_to_msisdn = {
            int(user_idx): str(msisdn)
            for msisdn, user_idx in self.msisdn_to_user_idx.items()
        }

        all_user_indices = np.asarray(
            sorted(idx_to_msisdn.keys()),
            dtype=np.int64,
        )

        fieldnames = [
            "rank",
            "msisdn",
            "user_idx",
            "bundle_idx",
            "bundle_id",
            "bundle_name",
            "bundle_type",
            "price",
            "score",
            "recommendation_type",
            "matched_features",
            "cohort_size",
        ]

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for start in range(0, len(all_user_indices), user_chunk_size):
                end = min(start + user_chunk_size, len(all_user_indices))
                chunk_user_indices_np = all_user_indices[start:end]

                logger.info("Scoring users %s to %s", start, end)

                chunk_user_indices = torch.as_tensor(
                    chunk_user_indices_np,
                    dtype=torch.long,
                    device=self.device,
                )

                chunk_user_emb = user_emb[chunk_user_indices]

                # Raw model logits, same as model.score(...) before sigmoid.
                logits = chunk_user_emb @ bundle_emb_t

                if exclude_seen:
                    for row_idx, user_idx in enumerate(chunk_user_indices_np):
                        seen = self.train_history.get(int(user_idx), set())
                        if seen:
                            seen_bundle_positions = np.where(
                                np.isin(self.all_bundle_indices, list(seen))
                            )[0]

                            if len(seen_bundle_positions) > 0:
                                logits[
                                    row_idx,
                                    torch.as_tensor(
                                        seen_bundle_positions,
                                        dtype=torch.long,
                                        device=self.device,
                                    ),
                                ] = -float("inf")

                # Ranking by logits is equivalent to ranking by sigmoid(logits),
                # but the saved score must be sigmoid(logit), same as notebook inference.
                top_logits, top_positions = torch.topk(
                    logits,
                    k=top_k,
                    dim=1,
                    largest=True,
                    sorted=True,
                )

                top_scores = torch.sigmoid(top_logits)

                top_scores = top_scores.detach().cpu().numpy()
                top_positions = top_positions.detach().cpu().numpy()

                for row_idx, user_idx in enumerate(chunk_user_indices_np):
                    msisdn = idx_to_msisdn[int(user_idx)]

                    for rank in range(1, top_k + 1):
                        pos = int(top_positions[row_idx, rank - 1])
                        bundle_idx = int(self.all_bundle_indices[pos])
                        score = float(top_scores[row_idx, rank - 1])

                        writer.writerow(
                            {
                                "rank": rank,
                                "msisdn": msisdn,
                                "user_idx": int(user_idx),
                                "bundle_idx": bundle_idx,
                                "bundle_id": self.bundle_idx_to_bundle_id[bundle_idx],
                                "bundle_name": self.bundle_idx_to_bundle_name.get(bundle_idx, ""),
                                "bundle_type": self.bundle_idx_to_bundle_type.get(bundle_idx, ""),
                                "price": self.bundle_idx_to_price.get(bundle_idx, np.nan),
                                "score": score,
                                "recommendation_type": "graphsage",
                                "matched_features": [],
                                "cohort_size": None,
                            }
                        )

        logger.info("Saved recommendations to %s", out_path)