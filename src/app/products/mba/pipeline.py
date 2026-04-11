import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

import json
import logging
from pathlib import Path
from typing import Dict, Optional

from pyspark.sql import DataFrame as SparkDataFrame
from pyspark.sql.functions import (
    col,
    collect_set,
    concat_ws,
    length,
    size,
    sort_array,
    trim,
)

from src.app.products.mba.config import ArtifactConfig, MBADataConfig, MBAModelConfig
from src.app.products.mba.contracts import MBATrainingResult
from src.app.products.mba.model import BundleMBAModel

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


class WeeklyMBAPipeline:
    def __init__(
        self,
        data_config: Optional[MBADataConfig] = None,
        model_config: Optional[MBAModelConfig] = None,
    ) -> None:
        self.data_config = data_config or MBADataConfig()
        self.model_config = model_config or MBAModelConfig()
        self.model = BundleMBAModel(config=self.model_config)

        self.transactions_: Optional[SparkDataFrame] = None
        self.association_rules_: Optional[SparkDataFrame] = None
        self.frequent_itemsets_: Optional[SparkDataFrame] = None
        self.metrics_: Dict[str, int | float | str | None] = {}
        self.is_fitted_: bool = False

        logger.info(
            "Initialized WeeklyMBAPipeline | source_table=%s | excluded_pattern=%s",
            self.data_config.source_table,
            self.data_config.excluded_bundle_pattern,
        )

    def fit(self, raw_df: SparkDataFrame) -> MBATrainingResult:
        logger.info("Starting MBA pipeline training")

        self.is_fitted_ = False
        self.model = BundleMBAModel(config=self.model_config)

        selected_df = self._select_required_columns(raw_df).cache()
        source_row_count = selected_df.count()

        cleaned_df = self._clean_input(selected_df).cache()
        filtered_row_count = cleaned_df.count()

        transactions = self._build_transactions(cleaned_df).cache()
        transaction_count = transactions.count()

        if transaction_count == 0:
            logger.error("No transactions available after preprocessing")
            raise ValueError("No transactions available after preprocessing.")

        self.model.fit(transactions)

        association_rules = self.model.association_rules().cache()
        frequent_itemsets = self.model.frequent_itemsets().cache()

        association_rule_count = association_rules.count()
        frequent_itemset_count = frequent_itemsets.count()

        self.transactions_ = transactions
        self.association_rules_ = association_rules
        self.frequent_itemsets_ = frequent_itemsets
        self.metrics_ = {
            "source_row_count": source_row_count,
            "filtered_row_count": filtered_row_count,
            "transaction_count": transaction_count,
            "association_rule_count": association_rule_count,
            "frequent_itemset_count": frequent_itemset_count,
            "min_support": self.model_config.min_support,
            "min_confidence": self.model_config.min_confidence,
            "items_col": self.model_config.items_col,
        }
        self.is_fitted_ = True

        logger.info("MBA pipeline training completed | metrics=%s", self.metrics_)
        return MBATrainingResult(metrics=self.metrics_.copy())

    def save_artifacts(self, artifact_config: Optional[ArtifactConfig] = None) -> None:
        self._ensure_fitted()

        resolved_artifact_config = artifact_config or ArtifactConfig()
        resolved_artifact_config.artifact_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Saving MBA artifacts | artifact_dir=%s",
            resolved_artifact_config.artifact_dir,
        )

        self.model.save(resolved_artifact_config.spark_model_path)

        association_rules_pdf = self.association_rules_.toPandas()
        association_rules_pdf.to_csv(
            resolved_artifact_config.association_rules_csv_path,
            index=False,
        )
        logger.info(
            "Saved association rules CSV | path=%s",
            resolved_artifact_config.association_rules_csv_path,
        )

        frequent_itemsets_pdf = self.frequent_itemsets_.toPandas()
        frequent_itemsets_pdf.to_csv(
            resolved_artifact_config.frequent_itemsets_csv_path,
            index=False,
        )
        logger.info(
            "Saved frequent itemsets CSV | path=%s",
            resolved_artifact_config.frequent_itemsets_csv_path,
        )

        with resolved_artifact_config.metrics_path.open("w", encoding="utf-8") as file:
            json.dump(self.metrics_, file, indent=2)
        logger.info("Saved metrics | path=%s", resolved_artifact_config.metrics_path)

    def _select_required_columns(self, raw_df: SparkDataFrame) -> SparkDataFrame:
        missing_columns = [
            column_name
            for column_name in self.data_config.required_columns
            if column_name not in raw_df.columns
        ]
        if missing_columns:
            logger.error("Missing required columns | columns=%s", missing_columns)
            raise ValueError(
                f"Input data is missing required columns: {missing_columns}"
            )

        return raw_df.select(*self.data_config.required_columns)

    def _clean_input(self, raw_df: SparkDataFrame) -> SparkDataFrame:
        cleaned_df = (
            raw_df
            .select(
                col("msisdn").cast("string").alias("msisdn"),
                col("WEEKNUMBER").cast("string").alias("WEEKNUMBER"),
                trim(col("bundle_name")).alias("bundle_name"),
            )
            .dropna(subset=["msisdn", "WEEKNUMBER", "bundle_name"])
            .filter(length(col("bundle_name")) > 0)
            .filter(~col("bundle_name").rlike(self.data_config.excluded_bundle_pattern))
        )

        logger.info("Input cleaning completed")
        return cleaned_df

    def _build_transactions(self, cleaned_df: SparkDataFrame) -> SparkDataFrame:
        transaction_id = concat_ws(
            self.model_config.transaction_id_separator,
            col("msisdn"),
            col("WEEKNUMBER"),
        )

        transactions = (
            cleaned_df
            .withColumn("transaction_id", transaction_id)
            .groupBy("transaction_id")
            .agg(
                sort_array(
                    collect_set("bundle_name")
                ).alias(self.model_config.items_col)
            )
            .filter(size(col(self.model_config.items_col)) > 0)
        )

        logger.info("Transaction aggregation completed")
        return transactions

    def _ensure_fitted(self) -> None:
        if (
            not self.is_fitted_
            or self.transactions_ is None
            or self.association_rules_ is None
            or self.frequent_itemsets_ is None
        ):
            logger.error("Attempted to save or infer before fitting the MBA pipeline")
            raise RuntimeError("The MBA pipeline is not fitted. Train it first.")
