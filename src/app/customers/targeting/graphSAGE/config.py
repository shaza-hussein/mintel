import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[5]

EDGE_TYPE = ("user", "subscribed_to", "bundle")
REV_EDGE_TYPE = ("bundle", "rev_subscribed_by", "user")


USER_NUM_COLS = [
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
]

USER_CAT_COLS = [
    "service_class_category",
    "canal",
    "payment_mode",
    "department_city",
    "brand_name",
    "device_capability",
]

BUNDLE_NUM_COLS = [
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

BUNDLE_CAT_COLS = ["bundle_type"]


@dataclass(frozen=True)
class GraphBuildConfig:
    input_parquet_dir: Path = Path(
        r"C:\Users\Alber\Desktop\uni\GraduationProject\datasets\graphsage_data"
    )
    graph_dir: Path = PROJECT_ROOT / "_models" / "graphsage" / "graph"
    parquet_glob: str = "*.parquet"
    train_end_dt: int = 20251010
    val_end_dt: int = 20251020
    duckdb_threads: int = 4

    @property
    def db_path(self) -> Path:
        return self.graph_dir / "graph_build.duckdb"

    @property
    def duckdb_temp_dir(self) -> Path:
        return self.graph_dir / "duckdb_tmp"


@dataclass(frozen=True)
class ArtifactConfig:
    artifact_dir: Path = PROJECT_ROOT / "_models" / "graphsage"
    graph_dir: Path = PROJECT_ROOT / "_models" / "graphsage" / "graph"
    REC_OUT: Path = PROJECT_ROOT / "_models" / "graphsage" / "recommendations"

    @property
    def best_model_path(self) -> Path:
        return self.artifact_dir / "best_graphsage_model.pt"

    @property
    def artifacts_path(self) -> Path:
        return self.artifact_dir / "graphsage_artifacts.pt"

    @property
    def metadata_path(self) -> Path:
        return self.artifact_dir / "graphsage_metadata.json"

    @property
    def cat_metadata_path(self) -> Path:
        return self.artifact_dir / "cat_features_metadata.json"

    @property
    def training_history_path(self) -> Path:
        return self.artifact_dir / "training_history.csv"

    @property
    def training_metrics_path(self) -> Path:
        return self.artifact_dir / "training_metrics.json"


@dataclass(frozen=True)
class GraphSAGEModelConfig:
    hidden_dim: int = 64
    cat_emb_dim: int = 16
    num_layers: int = 2
    dropout: float = 0.25
    train_batch_size: int = 2048
    eval_batch_size: int = 4096
    neg_sampling_ratio_train: float = 2.0
    neg_sampling_ratio_eval: float = 20.0
    epochs: int = 5
    lr: float = 2e-3
    weight_decay: float = 1e-4
    max_eval_edges: Optional[int] = 200_000
    topk_user_limit: int = 1000
    score_chunk_users: int = 250
    seed: int = 42

    @property
    def num_neighbors(self) -> dict:
        return {
            EDGE_TYPE: [15, 10],
            REV_EDGE_TYPE: [15, 10],
        }