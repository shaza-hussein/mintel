import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

import logging
from pathlib import Path
from typing import Optional

from pyspark.ml.fpm import FPGrowth, FPGrowthModel
from pyspark.sql import DataFrame as SparkDataFrame

from src.app.products.mba.config import MBAModelConfig

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


class BundleMBAModel:
    def __init__(self, config: Optional[MBAModelConfig] = None) -> None:
        self.config = config or MBAModelConfig()
        self.model_: Optional[FPGrowthModel] = None
        self.is_fitted_: bool = False

        logger.info(
            "Initialized BundleMBAModel | items_col=%s | min_support=%.4f | min_confidence=%.4f",
            self.config.items_col,
            self.config.min_support,
            self.config.min_confidence,
        )

    def fit(self, transactions: SparkDataFrame) -> "BundleMBAModel":
        logger.info(
            "Fitting BundleMBAModel | items_col=%s | min_support=%.4f | min_confidence=%.4f",
            self.config.items_col,
            self.config.min_support,
            self.config.min_confidence,
        )

        estimator = FPGrowth(
            itemsCol=self.config.items_col,
            minSupport=self.config.min_support,
            minConfidence=self.config.min_confidence,
        )
        self.model_ = estimator.fit(transactions)
        self.is_fitted_ = True

        logger.info("BundleMBAModel fitted successfully")
        return self

    def association_rules(self) -> SparkDataFrame:
        self._ensure_fitted()
        return self.model_.associationRules

    def frequent_itemsets(self) -> SparkDataFrame:
        self._ensure_fitted()
        return self.model_.freqItemsets

    def transform(self, transactions: SparkDataFrame) -> SparkDataFrame:
        self._ensure_fitted()
        return self.model_.transform(transactions)

    def save(self, path: Path) -> None:
        self._ensure_fitted()
        path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Saving BundleMBAModel | path=%s", path)
        self.model_.write().overwrite().save(str(path))
        logger.info("BundleMBAModel saved successfully")

    @classmethod
    def load(
        cls,
        path: Path,
        config: Optional[MBAModelConfig] = None,
    ) -> "BundleMBAModel":
        logger.info("Loading BundleMBAModel | path=%s", path)

        model = cls(config=config)
        model.model_ = FPGrowthModel.load(str(path))
        model.is_fitted_ = True

        logger.info("BundleMBAModel loaded successfully")
        return model

    def _ensure_fitted(self) -> None:
        if not self.is_fitted_ or self.model_ is None:
            logger.error("Attempted to use BundleMBAModel before fitting")
            raise RuntimeError("The MBA model is not fitted. Train or load a fitted model first.")
