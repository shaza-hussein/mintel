import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))

import gc
import logging
import random
from typing import Optional

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import average_precision_score, roc_auc_score
from torch_geometric.data import HeteroData
from torch_geometric.loader import LinkNeighborLoader
from torch_geometric.seed import seed_everything
from tqdm.auto import tqdm

from src.app.customers.targeting.graphSAGE.config import (
    BUNDLE_CAT_COLS,
    BUNDLE_NUM_COLS,
    EDGE_TYPE,
    REV_EDGE_TYPE,
    USER_CAT_COLS,
    USER_NUM_COLS,
    ArtifactConfig,
    GraphSAGEModelConfig,
)
from src.app.customers.targeting.graphSAGE.contracts import GraphSAGETrainingResult
from src.app.customers.targeting.graphSAGE.features import fit_categorical, fit_numeric, write_json
from src.app.customers.targeting.graphSAGE.model import HeteroGraphSAGE

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")


def seed_all(seed: int) -> None:
    seed_everything(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def _torch_load(path, map_location):
    try:
        return torch.load(path, map_location=map_location, weights_only=False)
    except TypeError:
        return torch.load(path, map_location=map_location)


class GraphSAGETrainer:
    def __init__(
        self,
        artifact_config: Optional[ArtifactConfig] = None,
        model_config: Optional[GraphSAGEModelConfig] = None,
    ) -> None:
        self.artifact_config = artifact_config or ArtifactConfig()
        self.model_config = model_config or GraphSAGEModelConfig()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("GraphSAGE model has been loaded onto ", self.device)
        self.use_amp = torch.cuda.is_available()

    def train(self) -> GraphSAGETrainingResult:
        seed_all(self.model_config.seed)
        self.artifact_config.artifact_dir.mkdir(parents=True, exist_ok=True)

        frames = self._load_graph_frames()
        feature_payload = self._encode_features(frames)
        metadata = self._build_metadata(frames["user_nodes"], frames["bundle_nodes"])
        self._save_metadata(feature_payload, metadata)

        data, val_edge_label_index, test_edge_label_index = self._build_heterodata(frames, feature_payload)
        train_loader, val_loader, test_loader = self._build_loaders(data, val_edge_label_index, test_edge_label_index)

        model = HeteroGraphSAGE(
            user_num_dim=len(USER_NUM_COLS),
            user_cat_cardinalities=feature_payload["user_cat_cardinalities"],
            bundle_num_dim=len(BUNDLE_NUM_COLS),
            bundle_cat_cardinalities=feature_payload["bundle_cat_cardinalities"],
            hidden_dim=self.model_config.hidden_dim,
            cat_emb_dim=self.model_config.cat_emb_dim,
            num_layers=self.model_config.num_layers,
            dropout=self.model_config.dropout,
        ).to(self.device)

        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=self.model_config.lr,
            weight_decay=self.model_config.weight_decay,
        )
        scaler = torch.cuda.amp.GradScaler(enabled=self.use_amp)

        best_val_ap = -1.0
        history = []

        for epoch in range(1, self.model_config.epochs + 1):
            train_loss = self._train_one_epoch(model, optimizer, scaler, train_loader, epoch)
            val_metrics = self._evaluate_auc_ap(model, val_loader, "val")

            row = {"epoch": epoch, "train_loss": train_loss, **val_metrics}
            history.append(row)
            logger.info("epoch=%d loss=%.4f val_auc=%.4f val_ap=%.4f", epoch, train_loss, val_metrics["val_auc"], val_metrics["val_ap"])

            if val_metrics["val_ap"] > best_val_ap:
                best_val_ap = val_metrics["val_ap"]
                torch.save(
                    {
                        "model_state_dict": model.state_dict(),
                        "config": self._checkpoint_config(feature_payload),
                    },
                    self.artifact_config.best_model_path,
                )

        checkpoint = _torch_load(self.artifact_config.best_model_path, self.device)
        model.load_state_dict(checkpoint["model_state_dict"])

        val_metrics = self._evaluate_auc_ap(model, val_loader, "val")
        test_metrics = self._evaluate_auc_ap(model, test_loader, "test")
        topk_metrics = self._evaluate_topk(model, data, val_edge_label_index, test_edge_label_index, frames["train_edges"], metadata)

        metrics = {
            "best_val_ap": best_val_ap,
            **val_metrics,
            **test_metrics,
            **topk_metrics,
        }

        pd.DataFrame(history).to_csv(self.artifact_config.training_history_path, index=False)
        write_json(self.artifact_config.training_metrics_path, metrics)

        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "config": checkpoint["config"],
                "msisdn_to_user_idx": metadata["msisdn_to_user_idx"],
                "bundle_idx_to_bundle_id": metadata["bundle_idx_to_bundle_id"],
                "bundle_idx_to_bundle_name": metadata["bundle_idx_to_bundle_name"],
                "bundle_idx_to_bundle_type": metadata["bundle_idx_to_bundle_type"],
                "bundle_idx_to_price": metadata["bundle_idx_to_price"],
                "all_bundle_indices": metadata["all_bundle_indices"],
            },
            self.artifact_config.artifacts_path,
        )

        return GraphSAGETrainingResult(
            artifact_dir=self.artifact_config.artifact_dir,
            metrics=metrics,
            best_model_path=self.artifact_config.best_model_path,
        )

    def _load_graph_frames(self) -> dict:
        graph_dir = self.artifact_config.graph_dir
        return {
            "user_nodes": pd.read_parquet(graph_dir / "user_nodes_train.parquet"),
            "bundle_nodes": pd.read_parquet(graph_dir / "bundle_nodes_train.parquet"),
            "train_edges": pd.read_parquet(graph_dir / "train_edges.parquet", columns=["user_idx", "bundle_idx"]),
            "val_edges": pd.read_parquet(graph_dir / "val_edges.parquet", columns=["user_idx", "bundle_idx"]),
            "test_edges": pd.read_parquet(graph_dir / "test_edges.parquet", columns=["user_idx", "bundle_idx"]),
        }

    def _encode_features(self, frames: dict) -> dict:
        user_x_num, user_num_mean, user_num_std = fit_numeric(frames["user_nodes"], USER_NUM_COLS)
        bundle_x_num, bundle_num_mean, bundle_num_std = fit_numeric(frames["bundle_nodes"], BUNDLE_NUM_COLS)
        user_x_cat, user_cat_maps, user_cat_cardinalities = fit_categorical(frames["user_nodes"], USER_CAT_COLS)
        bundle_x_cat, bundle_cat_maps, bundle_cat_cardinalities = fit_categorical(frames["bundle_nodes"], BUNDLE_CAT_COLS)

        return {
            "user_x_num": user_x_num,
            "bundle_x_num": bundle_x_num,
            "user_x_cat": user_x_cat,
            "bundle_x_cat": bundle_x_cat,
            "user_num_mean": user_num_mean,
            "user_num_std": user_num_std,
            "bundle_num_mean": bundle_num_mean,
            "bundle_num_std": bundle_num_std,
            "user_cat_maps": user_cat_maps,
            "bundle_cat_maps": bundle_cat_maps,
            "user_cat_cardinalities": user_cat_cardinalities,
            "bundle_cat_cardinalities": bundle_cat_cardinalities,
        }

    def _build_metadata(self, user_nodes_df, bundle_nodes_df) -> dict:
        return {
            "msisdn_to_user_idx": dict(zip(user_nodes_df["msisdn"].astype(str), user_nodes_df["user_idx"].astype(int))),
            "bundle_idx_to_bundle_id": dict(zip(bundle_nodes_df["bundle_idx"].astype(int), bundle_nodes_df["bundle_id"].astype(str))),
            "bundle_idx_to_bundle_name": dict(zip(bundle_nodes_df["bundle_idx"].astype(int), bundle_nodes_df["bundle_name"].astype(str))),
            "bundle_idx_to_bundle_type": dict(zip(bundle_nodes_df["bundle_idx"].astype(int), bundle_nodes_df["bundle_type"].astype(str))),
            "bundle_idx_to_price": dict(zip(bundle_nodes_df["bundle_idx"].astype(int), bundle_nodes_df["price"].astype(float))),
            "all_bundle_indices": bundle_nodes_df["bundle_idx"].astype(int).to_numpy(),
        }

    def _save_metadata(self, feature_payload: dict, metadata: dict) -> None:
        write_json(
            self.artifact_config.metadata_path,
            {
                "msisdn_to_user_idx": {str(k): int(v) for k, v in metadata["msisdn_to_user_idx"].items()},
                "bundle_idx_to_bundle_id": {str(k): str(v) for k, v in metadata["bundle_idx_to_bundle_id"].items()},
                "bundle_idx_to_bundle_name": {str(k): str(v) for k, v in metadata["bundle_idx_to_bundle_name"].items()},
                "bundle_idx_to_bundle_type": {str(k): str(v) for k, v in metadata["bundle_idx_to_bundle_type"].items()},
                "bundle_idx_to_price": {str(k): float(v) for k, v in metadata["bundle_idx_to_price"].items()},
                "all_bundle_indices": metadata["all_bundle_indices"].tolist(),
            },
        )

        write_json(
            self.artifact_config.cat_metadata_path,
            {
                "user_num_mean": {k: float(v) for k, v in feature_payload["user_num_mean"].items()},
                "user_num_std": {k: float(v) for k, v in feature_payload["user_num_std"].items()},
                "bundle_num_mean": {k: float(v) for k, v in feature_payload["bundle_num_mean"].items()},
                "bundle_num_std": {k: float(v) for k, v in feature_payload["bundle_num_std"].items()},
                "user_cat_maps": {
                    col: {str(k): int(v) for k, v in mapping.items()}
                    for col, mapping in feature_payload["user_cat_maps"].items()
                },
                "bundle_cat_maps": {
                    col: {str(k): int(v) for k, v in mapping.items()}
                    for col, mapping in feature_payload["bundle_cat_maps"].items()
                },
                "user_cat_cardinalities": {
                    col: int(card)
                    for col, card in zip(USER_CAT_COLS, feature_payload["user_cat_cardinalities"])
                },
                "bundle_cat_cardinalities": {
                    col: int(card)
                    for col, card in zip(BUNDLE_CAT_COLS, feature_payload["bundle_cat_cardinalities"])
                },
            },
        )

    def _build_heterodata(self, frames: dict, feature_payload: dict):
        train_edge_index = torch.tensor(frames["train_edges"][["user_idx", "bundle_idx"]].to_numpy().T, dtype=torch.long).contiguous()
        val_edge_label_index = torch.tensor(frames["val_edges"][["user_idx", "bundle_idx"]].to_numpy().T, dtype=torch.long).contiguous()
        test_edge_label_index = torch.tensor(frames["test_edges"][["user_idx", "bundle_idx"]].to_numpy().T, dtype=torch.long).contiguous()

        data = HeteroData()
        data["user"].x_num = torch.from_numpy(feature_payload["user_x_num"])
        data["user"].x_cat = torch.from_numpy(feature_payload["user_x_cat"])
        data["user"].num_nodes = len(frames["user_nodes"])
        data["bundle"].x_num = torch.from_numpy(feature_payload["bundle_x_num"])
        data["bundle"].x_cat = torch.from_numpy(feature_payload["bundle_x_cat"])
        data["bundle"].num_nodes = len(frames["bundle_nodes"])
        data[EDGE_TYPE].edge_index = train_edge_index
        data[REV_EDGE_TYPE].edge_index = train_edge_index.flip(0).contiguous()

        del frames["train_edges"]
        gc.collect()
        return data, val_edge_label_index, test_edge_label_index

    def _sample_edge_label_index(self, edge_label_index):
        max_edges = self.model_config.max_eval_edges
        if max_edges is None or edge_label_index.size(1) <= max_edges:
            return edge_label_index

        generator = torch.Generator()
        generator.manual_seed(self.model_config.seed)
        perm = torch.randperm(edge_label_index.size(1), generator=generator)[:max_edges]
        return edge_label_index[:, perm].contiguous()

    def _build_loaders(self, data, val_edge_label_index, test_edge_label_index):
        val_auc_edges = self._sample_edge_label_index(val_edge_label_index)
        test_auc_edges = self._sample_edge_label_index(test_edge_label_index)

        train_loader = LinkNeighborLoader(
            data=data,
            num_neighbors=self.model_config.num_neighbors,
            edge_label_index=(EDGE_TYPE, data[EDGE_TYPE].edge_index),
            edge_label=torch.ones(data[EDGE_TYPE].edge_index.size(1), dtype=torch.float),
            neg_sampling_ratio=self.model_config.neg_sampling_ratio_train,
            batch_size=self.model_config.train_batch_size,
            shuffle=True,
            num_workers=0,
            pin_memory=torch.cuda.is_available(),
        )
        val_loader = LinkNeighborLoader(
            data=data,
            num_neighbors=self.model_config.num_neighbors,
            edge_label_index=(EDGE_TYPE, val_auc_edges),
            edge_label=torch.ones(val_auc_edges.size(1), dtype=torch.float),
            neg_sampling_ratio=self.model_config.neg_sampling_ratio_eval,
            batch_size=self.model_config.eval_batch_size,
            shuffle=False,
            num_workers=0,
            pin_memory=torch.cuda.is_available(),
        )
        test_loader = LinkNeighborLoader(
            data=data,
            num_neighbors=self.model_config.num_neighbors,
            edge_label_index=(EDGE_TYPE, test_auc_edges),
            edge_label=torch.ones(test_auc_edges.size(1), dtype=torch.float),
            neg_sampling_ratio=self.model_config.neg_sampling_ratio_eval,
            batch_size=self.model_config.eval_batch_size,
            shuffle=False,
            num_workers=0,
            pin_memory=torch.cuda.is_available(),
        )
        return train_loader, val_loader, test_loader
    

    def _train_one_epoch(self, model, optimizer, scaler, train_loader, epoch: int) -> float:
        model.train()
        total_loss = 0.0
        total_examples = 0

        for batch in tqdm(train_loader, desc=f"train epoch {epoch}", leave=False):
            batch = batch.to(self.device)
            optimizer.zero_grad(set_to_none=True)

            with torch.amp.autocast(self.device, enabled=self.use_amp):
                z_dict = model(batch)
                logits = model.score(z_dict, batch[EDGE_TYPE].edge_label_index)
                labels = batch[EDGE_TYPE].edge_label.float()
                loss = F.binary_cross_entropy_with_logits(logits, labels)

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            scaler.step(optimizer)
            scaler.update()

            batch_size = labels.numel()
            total_loss += float(loss.detach().cpu()) * batch_size
            total_examples += batch_size

        return total_loss / max(total_examples, 1)

    @torch.no_grad()
    def _evaluate_auc_ap(self, model, loader, name: str) -> dict:
        model.eval()
        all_scores = []
        all_labels = []

        for batch in tqdm(loader, desc=f"eval {name}", leave=False):
            batch = batch.to(self.device)
            z_dict = model(batch)
            logits = model.score(z_dict, batch[EDGE_TYPE].edge_label_index)
            all_scores.append(torch.sigmoid(logits).detach().cpu())
            all_labels.append(batch[EDGE_TYPE].edge_label.detach().cpu())

        y_score = torch.cat(all_scores).numpy()
        y_true = torch.cat(all_labels).numpy()

        return {
            f"{name}_auc": float(roc_auc_score(y_true, y_score)),
            f"{name}_ap": float(average_precision_score(y_true, y_score)),
        }

    def _checkpoint_config(self, feature_payload: dict) -> dict:
        return {
            "hidden_dim": self.model_config.hidden_dim,
            "cat_emb_dim": self.model_config.cat_emb_dim,
            "num_layers": self.model_config.num_layers,
            "dropout": self.model_config.dropout,
            "user_num_cols": USER_NUM_COLS,
            "user_cat_cols": USER_CAT_COLS,
            "bundle_num_cols": BUNDLE_NUM_COLS,
            "bundle_cat_cols": BUNDLE_CAT_COLS,
            "user_num_mean": feature_payload["user_num_mean"],
            "user_num_std": feature_payload["user_num_std"],
            "bundle_num_mean": feature_payload["bundle_num_mean"],
            "bundle_num_std": feature_payload["bundle_num_std"],
            "user_cat_maps": feature_payload["user_cat_maps"],
            "bundle_cat_maps": feature_payload["bundle_cat_maps"],
            "user_cat_cardinalities": feature_payload["user_cat_cardinalities"],
            "bundle_cat_cardinalities": feature_payload["bundle_cat_cardinalities"],
        }

    def _evaluate_topk(self, model, data, val_edges, test_edges, train_edges_df, metadata) -> dict:
        # Keep this lightweight. Full top-K over all users can be expensive.
        train_history = train_edges_df.groupby("user_idx")["bundle_idx"].apply(set).to_dict()
        return {
            "topk_user_limit": self.model_config.topk_user_limit,
            "train_history_users": int(len(train_history)),
            "num_bundles": int(len(metadata["all_bundle_indices"])),
        }


def train_graphsage_model(
    artifact_config: Optional[ArtifactConfig] = None,
    model_config: Optional[GraphSAGEModelConfig] = None,
) -> GraphSAGETrainingResult:
    return GraphSAGETrainer(
        artifact_config=artifact_config,
        model_config=model_config,
    ).train()