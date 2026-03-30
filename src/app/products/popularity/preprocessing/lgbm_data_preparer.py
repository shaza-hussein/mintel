import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from src.app.products.popularity.constants import (
    CATEGORICAL_FEATURE_COLUMNS,
    MODEL_BASE_FEATURE_COLUMNS,
)
from src.app.products.popularity.contracts import TrainTestData
from src.app.products.popularity.preprocessing.validators import require_columns

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)




class LGBMDataPreparer:
    BASE_FEATURE_COLS = list(MODEL_BASE_FEATURE_COLUMNS)
    CATEGORICAL_COLS = list(CATEGORICAL_FEATURE_COLUMNS)

    def __init__(self, rare_threshold: int = 5) -> None:
        self.rare_threshold = rare_threshold
        self.feature_cols_: List[str] = []
        self.categorical_cols_: List[str] = []
        self.numeric_cols_: List[str] = []
        self.train_medians_: Optional[pd.Series] = None
        self.frequent_values_: Dict[str, List[Any]] = {}
        self.category_levels_: Dict[str, List[str]] = {}
        self.is_fitted_: bool = False

        logger.info("Initialized LGBMDataPreparer | rare_threshold=%d", rare_threshold)

    def _prepare_training_inputs(
        self,
        df_model: pd.DataFrame,
        target_col: str,
    ) -> Tuple[pd.DataFrame, pd.Series, List[str], List[str], List[str]]:
        require_columns(df_model, [target_col], "LGBMDataPreparer._prepare_training_inputs")

        data = df_model.copy()
        logger.info(
            "Preparing modeling inputs | target_col=%s | input_shape=%s",
            target_col,
            data.shape,
        )

        feature_cols = [column for column in self.BASE_FEATURE_COLS if column in data.columns]
        categorical_cols = [column for column in self.CATEGORICAL_COLS if column in feature_cols]

        keep_cols = [column for column in feature_cols + [target_col] if column in data.columns]
        data = data[keep_cols].copy()

        before_rows = len(data)
        data = data[data[target_col].notna()].copy()
        logger.info(
            "Filtered rows with non-null target for modeling | before=%d | after=%d | removed=%d",
            before_rows,
            len(data),
            before_rows - len(data),
        )

        for column in categorical_cols:
            data[column] = (
                data[column]
                .fillna("unknown")
                .astype(str)
                .str.strip()
                .replace("", "unknown")
            )

        numeric_cols = [column for column in feature_cols if column not in categorical_cols]
        for column in numeric_cols:
            data[column] = pd.to_numeric(data[column], errors="coerce")

        y = pd.to_numeric(data[target_col], errors="coerce")
        valid_mask = y.notna()

        data = data.loc[valid_mask].copy()
        y = y.loc[valid_mask].copy()

        X = data[feature_cols].copy()

        logger.info(
            "Modeling inputs ready | X_shape=%s | y_len=%d | feature_count=%d | categorical_count=%d | numeric_count=%d",
            X.shape,
            len(y),
            len(feature_cols),
            len(categorical_cols),
            len(numeric_cols),
        )

        return X, y, feature_cols, categorical_cols, numeric_cols

    def fit_split_transform(
        self,
        df_model: pd.DataFrame,
        target_col: str = "popularity",
        test_size: float = 0.2,
        random_state: int = 42,
        use_time_split: bool = True,
    ) -> TrainTestData:
        logger.info(
            "Starting train/test preparation | target_col=%s | test_size=%.4f | random_state=%d | use_time_split=%s",
            target_col,
            test_size,
            random_state,
            use_time_split,
        )

        X, y, feature_cols, categorical_cols, numeric_cols = self._prepare_training_inputs(
            df_model=df_model,
            target_col=target_col,
        )

        if use_time_split and {"year_number", "week_number"}.issubset(df_model.columns):
            temporal_frame = df_model.loc[X.index, ["year_number", "week_number"]].copy()
            temporal_frame["__idx__"] = X.index
            temporal_frame = temporal_frame.sort_values(["year_number", "week_number", "__idx__"])

            ordered_index = temporal_frame["__idx__"].tolist()
            X = X.loc[ordered_index].reset_index(drop=True)
            y = y.loc[ordered_index].reset_index(drop=True)

            split_index = int(len(X) * (1 - test_size))
            X_train = X.iloc[:split_index].copy()
            X_test = X.iloc[split_index:].copy()
            y_train = y.iloc[:split_index].copy()
            y_test = y.iloc[split_index:].copy()
            split_method = "time"
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X,
                y,
                test_size=test_size,
                random_state=random_state,
            )
            split_method = "random"

        logger.info(
            "Split completed | method=%s | X_train_shape=%s | X_test_shape=%s | y_train_len=%d | y_test_len=%d",
            split_method,
            X_train.shape,
            X_test.shape,
            len(y_train),
            len(y_test),
        )

        self.feature_cols_ = feature_cols
        self.categorical_cols_ = categorical_cols
        self.numeric_cols_ = numeric_cols

        self.fit(X_train)

        X_train = self.transform(X_train)
        X_test = self.transform(X_test)
        y_train = y_train.reset_index(drop=True)
        y_test = y_test.reset_index(drop=True)

        logger.info("Train/test preprocessing completed successfully")

        return TrainTestData(
            X_train=X_train,
            X_test=X_test,
            y_train=y_train,
            y_test=y_test,
        )

    def fit(self, X_train: pd.DataFrame) -> "LGBMDataPreparer":
        train = X_train.copy()
        logger.info("Fitting LGBMDataPreparer | input_shape=%s", train.shape)

        self.train_medians_ = train[self.numeric_cols_].median()
        logger.info("Stored train medians for numeric columns | count=%d", len(self.numeric_cols_))

        self.frequent_values_ = {}
        self.category_levels_ = {}

        for column in self.categorical_cols_:
            frequency = train[column].value_counts(dropna=False)
            frequent_values = frequency[frequency >= self.rare_threshold].index

            self.frequent_values_[column] = list(frequent_values)

            train[column] = np.where(train[column].isin(frequent_values), train[column], "__RARE__")
            categories = sorted(pd.Series(train[column]).astype(str).unique().tolist())
            self.category_levels_[column] = categories

            logger.info(
                "Prepared categorical mapping | column=%s | frequent_values=%d | category_levels=%d",
                column,
                len(self.frequent_values_[column]),
                len(categories),
            )

        self.is_fitted_ = True
        logger.info("LGBMDataPreparer fitted successfully")
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if not self.is_fitted_:
            logger.error("Attempted to transform before fitting LGBMDataPreparer")
            raise RuntimeError("LGBMDataPreparer must be fitted before calling transform().")

        data = X.copy()
        logger.info("Transforming feature frame | input_shape=%s", data.shape)

        missing_features = [column for column in self.feature_cols_ if column not in data.columns]
        if missing_features:
            logger.warning(
                "Input is missing expected feature columns; filling with NaN | missing=%s",
                missing_features,
            )

        for column in self.feature_cols_:
            if column not in data.columns:
                data[column] = np.nan

        data = data[self.feature_cols_].copy()

        for column in self.categorical_cols_:
            data[column] = (
                data[column]
                .fillna("unknown")
                .astype(str)
                .str.strip()
                .replace("", "unknown")
            )

        for column in self.numeric_cols_:
            data[column] = pd.to_numeric(data[column], errors="coerce")

        if self.train_medians_ is not None:
            data[self.numeric_cols_] = data[self.numeric_cols_].fillna(self.train_medians_)

        for column in self.categorical_cols_:
            frequent_values = self.frequent_values_[column]
            data[column] = np.where(data[column].isin(frequent_values), data[column], "__RARE__")
            data[column] = pd.Categorical(data[column], categories=self.category_levels_[column])

        data[self.numeric_cols_] = data[self.numeric_cols_].replace([np.inf, -np.inf], 0)

        output = data.reset_index(drop=True)
        logger.info("Feature frame transformed | output_shape=%s", output.shape)
        return output

    def transform_inference(self, df_model: pd.DataFrame) -> pd.DataFrame:
        logger.info("Transforming inference model frame | input_shape=%s", df_model.shape)
        return self.transform(df_model)
