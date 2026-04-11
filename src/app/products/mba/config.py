import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class SparkConfig:
    app_name: str = "MINTEL_WEEKLY_MBA"
    master: Optional[str] = "local[*]"
    driver_memory: str = "16g"
    driver_extra_java_options: str = "-Djava.security.manager=allow"
    executor_extra_java_options: str = "-Djava.security.manager=allow"


@dataclass(frozen=True)
class MBADataConfig:
    source_table: str = "MinTel.weekly_purchases"
    required_columns: Tuple[str, ...] = (
        "msisdn",
        "WEEKNUMBER",
        "bundle_name",
    )
    excluded_bundle_pattern: str = r"(?i)free|bonus|DIY|SDP|VAS"


@dataclass(frozen=True)
class MBAModelConfig:
    items_col: str = "bundle_list"
    min_support: float = 0.001
    min_confidence: float = 0.5
    transaction_id_separator: str = "_"


@dataclass(frozen=True)
class ArtifactConfig:
    artifact_dir: Path = PROJECT_ROOT / "_models" / "mba"
    spark_model_dirname: str = "fp_growth_model"
    association_rules_filename: str = "association_rules.csv"
    frequent_itemsets_filename: str = "frequent_itemsets.csv"
    metrics_filename: str = "metrics.json"

    @property
    def spark_model_path(self) -> Path:
        return self.artifact_dir / self.spark_model_dirname

    @property
    def association_rules_csv_path(self) -> Path:
        return self.artifact_dir / self.association_rules_filename

    @property
    def frequent_itemsets_csv_path(self) -> Path:
        return self.artifact_dir / self.frequent_itemsets_filename

    @property
    def metrics_path(self) -> Path:
        return self.artifact_dir / self.metrics_filename
