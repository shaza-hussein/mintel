import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))

from pathlib import Path
from typing import Optional, Sequence

import joblib
import pandas as pd
from lightgbm import LGBMRegressor

from src.app.products.gen.popularity.config import ModelConfig
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


class PopularityRegressor:
    def __init__(self, config: Optional[ModelConfig] = None) -> None:
        self.config = config or ModelConfig()
        self.estimator = LGBMRegressor(
            n_estimators=self.config.n_estimators,
            learning_rate=self.config.learning_rate,
            num_leaves=self.config.num_leaves,
            subsample=self.config.subsample,
            colsample_bytree=self.config.colsample_bytree,
            random_state=self.config.random_state,
        )
        self.categorical_feature_: list[str] = []

        logger.info(
            "Initialized PopularityRegressor | n_estimators=%d | learning_rate=%.4f | num_leaves=%d | subsample=%.4f | colsample_bytree=%.4f | random_state=%d",
            self.config.n_estimators,
            self.config.learning_rate,
            self.config.num_leaves,
            self.config.subsample,
            self.config.colsample_bytree,
            self.config.random_state,
        )

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        categorical_feature: Optional[Sequence[str]] = None,
    ) -> "PopularityRegressor":
        self.categorical_feature_ = list(categorical_feature or [])
        logger.info(
            "Fitting PopularityRegressor | X_train_shape=%s | y_train_len=%d | categorical_features=%s",
            X_train.shape,
            len(y_train),
            self.categorical_feature_,
        )

        self.estimator.fit(
            X_train,
            y_train,
            categorical_feature=self.categorical_feature_,
        )

        logger.info("PopularityRegressor fitted successfully")
        return self

    def predict(self, X: pd.DataFrame):
        logger.info("Running prediction | input_shape=%s", X.shape)
        predictions = self.estimator.predict(X)
        logger.info("Prediction completed | output_len=%d", len(predictions))
        return predictions

    def save(self, path: Path) -> None:
        logger.info("Saving PopularityRegressor | path=%s", path)
        joblib.dump(self, path)
        logger.info("PopularityRegressor saved successfully")

    @classmethod
    def load(cls, path: Path) -> "PopularityRegressor":
        logger.info("Loading PopularityRegressor | path=%s", path)
        model = joblib.load(path)
        logger.info("PopularityRegressor loaded successfully")
        return model
