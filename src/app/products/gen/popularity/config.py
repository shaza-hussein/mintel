import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


@dataclass(frozen=True)
class DataConfig:
    dataset_folder: Path = Path(r"..\..\..\..\..\..\datasets")
    weekly_bundles_filename: str = "weekly_base_bundles_info_202501_202510.csv"

    @property
    def weekly_bundles_data_path(self) -> Path:
        return self.dataset_folder / self.weekly_bundles_filename


@dataclass(frozen=True)
class ModelConfig:
    target_col: str = "popularity"
    test_size: float = 0.2
    random_state: int = 42
    use_time_split: bool = False
    rare_threshold: int = 5

    n_estimators: int = 500
    learning_rate: float = 0.05
    num_leaves: int = 31
    subsample: float = 0.8
    colsample_bytree: float = 0.8

    categorical_cols: Tuple[str, ...] = (
        "season",
        "bundle_type",
        "usage_type",
        "service_class_category",
        "validity_bucket",
    )


PROJECT_ROOT = Path(__file__).resolve().parents[5]

@dataclass(frozen=True)
class ArtifactConfig:
    artifact_dir: Path = PROJECT_ROOT / "_models" / "popularity"
    pipeline_filename: str = "bundle_popularity_pipeline.joblib"
    metrics_filename: str = "metrics.json"
    predictions_filename: str = "test_predictions.csv"

    @property
    def pipeline_path(self) -> Path:
        return self.artifact_dir / self.pipeline_filename

    @property
    def metrics_path(self) -> Path:
        return self.artifact_dir / self.metrics_filename

    @property
    def predictions_path(self) -> Path:
        return self.artifact_dir / self.predictions_filename
