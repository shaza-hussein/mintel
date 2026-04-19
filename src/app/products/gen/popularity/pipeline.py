import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))


import logging
from pathlib import Path
from typing import List, Optional

import joblib
import pandas as pd

from src.app.products.gen.popularity.config import ModelConfig
from src.app.products.gen.popularity.contracts import TrainingResult
from src.app.products.gen.popularity.evaluation import RegressionEvaluator
from src.app.products.gen.popularity.model import PopularityRegressor
from src.app.products.gen.popularity.preprocessing.bundle_feature_engineer import BundleFeatureEngineer
from src.app.products.gen.popularity.preprocessing.lgbm_data_preparer import LGBMDataPreparer
from src.app.products.gen.popularity.preprocessing.raw_bundle_preprocessor import RawBundlePreprocessor

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


class BundlePopularityPipeline:
    def __init__(self, model_config: Optional[ModelConfig] = None) -> None:
        self.model_config = model_config or ModelConfig()
        self.raw_preprocessor = RawBundlePreprocessor()
        self.feature_engineer = BundleFeatureEngineer()
        self.data_preparer = LGBMDataPreparer(rare_threshold=self.model_config.rare_threshold)
        self.model = PopularityRegressor(config=self.model_config)
        self.feature_cols_: List[str] = []
        self.is_fitted_: bool = False

        logger.info(
            "Initialized BundlePopularityPipeline | target_col=%s | test_size=%.4f | random_state=%d | use_time_split=%s | rare_threshold=%d",
            self.model_config.target_col,
            self.model_config.test_size,
            self.model_config.random_state,
            self.model_config.use_time_split,
            self.model_config.rare_threshold,
        )

    def fit(self, raw_df: pd.DataFrame) -> TrainingResult:
        logger.info("Starting pipeline training | raw_input_shape=%s", raw_df.shape)

        self.is_fitted_ = False
        self.data_preparer = LGBMDataPreparer(rare_threshold=self.model_config.rare_threshold)
        self.model = PopularityRegressor(config=self.model_config)

        cleaned_df = self.raw_preprocessor.transform(raw_df, build_target=True)
        logger.info("Raw preprocessing finished | cleaned_shape=%s", cleaned_df.shape)

        if cleaned_df.empty:
            logger.error("No rows left after raw preprocessing")
            raise ValueError("No rows left after raw preprocessing.")

        df_model, feature_engineering_cols = self.feature_engineer.prepare_training_frame(
            cleaned_df,
            target_col=self.model_config.target_col,
        )
        logger.info(
            "Feature engineering finished | df_model_shape=%s | engineered_feature_count=%d",
            df_model.shape,
            len(feature_engineering_cols),
        )

        if df_model.empty:
            logger.error("No rows left after feature engineering")
            raise ValueError("No rows left after feature engineering.")

        split = self.data_preparer.fit_split_transform(
            df_model=df_model,
            target_col=self.model_config.target_col,
            test_size=self.model_config.test_size,
            random_state=self.model_config.random_state,
            use_time_split=self.model_config.use_time_split,
        )
        logger.info(
            "Data preparation finished | X_train_shape=%s | X_test_shape=%s",
            split.X_train.shape,
            split.X_test.shape,
        )

        categorical_feature = [
            column
            for column in self.data_preparer.categorical_cols_
            if column in split.X_train.columns
        ]
        logger.info("Resolved categorical features for LightGBM | columns=%s", categorical_feature)

        self.model.fit(
            split.X_train,
            split.y_train,
            categorical_feature=categorical_feature,
        )
        logger.info("Model fitting finished")

        evaluation = RegressionEvaluator.evaluate(
            self.model,
            split.X_test,
            split.y_test,
            return_predictions=True,
        )

        self.feature_cols_ = self.data_preparer.feature_cols_
        self.is_fitted_ = True

        logger.info("Pipeline training completed | metrics=%s", evaluation.metrics)

        return TrainingResult(
            metrics=evaluation.metrics,
            predictions=evaluation.predictions if evaluation.predictions is not None else pd.DataFrame(),
            df_model=df_model,
            feature_engineering_cols=feature_engineering_cols,
            model_feature_cols=self.data_preparer.feature_cols_,
            split=split,
        )

    def predict_from_model_frame(self, df_model: pd.DataFrame) -> pd.DataFrame:
        self._ensure_fitted()
        logger.info("Predicting from model frame | input_shape=%s", df_model.shape)

        result = df_model.copy().reset_index(drop=True)
        if result.empty:
            logger.warning("Received empty model frame for prediction")
            result["predicted_popularity"] = pd.Series(dtype=float)
            return result

        X = self.data_preparer.transform(df_model)
        predictions = self.model.predict(X)

        result["predicted_popularity"] = predictions
        logger.info("Prediction from model frame completed | output_shape=%s", result.shape)
        return result

    def predict_from_raw(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        self._ensure_fitted()
        logger.info("Predicting from raw input | raw_input_shape=%s", raw_df.shape)

        cleaned_df = self.raw_preprocessor.transform(raw_df, build_target=False)
        logger.info("Raw preprocessing for inference finished | cleaned_shape=%s", cleaned_df.shape)

        df_model, _ = self.feature_engineer.prepare_inference_frame(cleaned_df)
        logger.info("Inference feature engineering finished | df_model_shape=%s", df_model.shape)

        return self.predict_from_model_frame(df_model)

    def save(self, path: Path) -> None:
        logger.info("Saving pipeline | path=%s", path)
        joblib.dump(self, path)
        logger.info("Pipeline saved successfully")

    @classmethod
    def load(cls, path: Path) -> "BundlePopularityPipeline":
        logger.info("Loading pipeline | path=%s", path)
        pipeline = joblib.load(path)
        logger.info("Pipeline loaded successfully")
        return pipeline

    def _ensure_fitted(self) -> None:
        if not self.is_fitted_:
            logger.error("Attempted to use pipeline before fitting")
            raise RuntimeError("The pipeline is not fitted. Train or load a fitted pipeline first.")
