import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))

import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.app.products.popularity.constants import (
    CATEGORICAL_FEATURE_COLUMNS,
    FEATURE_ENGINEERING_REQUIRED_COLUMNS,
)
from src.app.products.popularity.preprocessing.validators import require_columns
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


class BundleFeatureEngineer:
    @staticmethod
    def parse_bundle_name(name: str) -> Dict[str, Any]:
        normalized = str(name).lower().strip().replace(",", ".")

        output = {
            "parsed_volume_mb": np.nan,
            "parsed_volume_min": np.nan,
            "parsed_volume_sms": np.nan,
            "parsed_validity_hours": np.nan,
            "parsed_speed_mbps": np.nan,
            "name_has_data": 0,
            "name_has_voice": 0,
            "name_has_sms": 0,
            "name_has_unlimited": 0,
            "name_has_speed": 0,
            "name_has_social": 0,
            "name_has_roaming": 0,
        }

        if re.search(r"\b(illimite|illimitÃ©|unlimited|illimix)\b", normalized):
            output["name_has_unlimited"] = 1

        if re.search(r"\b(whatsapp|tiktok|facebook|youtube|instagram|social)\b", normalized):
            output["name_has_social"] = 1

        if re.search(r"\b(roaming|hadj|voyage|travel)\b", normalized):
            output["name_has_roaming"] = 1

        match = re.search(r"(\d+(?:\.\d+)?)\s*(mbps|kbps)\b", normalized)
        if match:
            value = float(match.group(1))
            unit = match.group(2)
            output["parsed_speed_mbps"] = value if unit == "mbps" else value / 1000.0
            output["name_has_speed"] = 1

        data_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(go|gb|giga|g|mb|mo)\b", normalized)
        if data_matches:
            mb_values = []
            for value, unit in data_matches:
                numeric_value = float(value)
                normalized_unit = unit.lower()

                if normalized_unit in {"go", "gb", "giga", "g"}:
                    mb_values.append(numeric_value * 1024.0)
                elif normalized_unit in {"mb", "mo"}:
                    mb_values.append(numeric_value)

            if mb_values:
                output["parsed_volume_mb"] = max(mb_values)
                output["name_has_data"] = 1

        match = re.search(r"(\d+(?:\.\d+)?)\s*(min|mins|minute|minutes)\b", normalized)
        if match:
            output["parsed_volume_min"] = float(match.group(1))
            output["name_has_voice"] = 1

        match = re.search(r"(\d+(?:\.\d+)?)\s*(sms)\b", normalized)
        if match:
            output["parsed_volume_sms"] = float(match.group(1))
            output["name_has_sms"] = 1

        match = re.search(r"(\d+(?:\.\d+)?)\s*(jour|jours|day|days|j)\b", normalized)
        if match:
            output["parsed_validity_hours"] = float(match.group(1)) * 24.0

        match = re.search(r"(\d+(?:\.\d+)?)\s*(mois|month|months)\b", normalized)
        if match:
            output["parsed_validity_hours"] = float(match.group(1)) * 30.0 * 24.0

        if pd.isna(output["parsed_validity_hours"]):
            match = re.search(r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours)\b", normalized)
            if match:
                output["parsed_validity_hours"] = float(match.group(1))

        return output

    @staticmethod
    def choose_value(configured: Any, parsed: Any) -> Tuple[float, str]:
        if pd.notna(configured) and configured > 0:
            return float(configured), "configured"
        if pd.notna(parsed) and parsed > 0:
            return float(parsed), "parsed_name"
        return 0.0, "zero_or_unknown"

    def prepare_training_frame(
        self,
        df: pd.DataFrame,
        target_col: str = "popularity",
    ) -> Tuple[pd.DataFrame, List[str]]:
        logger.info(
            "Preparing training frame | target_col=%s | input_shape=%s",
            target_col,
            df.shape,
        )
        return self._prepare_core_frame(df=df, target_col=target_col)

    def prepare_inference_frame(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        logger.info("Preparing inference frame | input_shape=%s", df.shape)
        return self._prepare_core_frame(df=df, target_col=None)

    def _prepare_core_frame(
        self,
        df: pd.DataFrame,
        target_col: Optional[str],
    ) -> Tuple[pd.DataFrame, List[str]]:
        required_columns = list(FEATURE_ENGINEERING_REQUIRED_COLUMNS)
        if target_col is not None:
            required_columns.append(target_col)

        require_columns(df, required_columns, "BundleFeatureEngineer._prepare_core_frame")

        data = df.copy()
        logger.info(
            "Starting feature engineering | target_col=%s | input_shape=%s",
            target_col,
            data.shape,
        )

        data.columns = [column.strip() for column in data.columns]
        data["bundle_name"] = data["bundle_name"].fillna("").astype(str)

        numeric_columns = [
            "week_number",
            "year_number",
            "price",
            "configured_volume_mb",
            "configured_volume_min",
            "configured_volume_sms",
            "validity_hours",
            "is_illimite",
        ]
        for column in numeric_columns:
            if column in data.columns:
                data[column] = pd.to_numeric(data[column], errors="coerce")
        logger.info("Numeric columns coerced where available")

        if target_col is not None:
            before_rows = len(data)
            data = data[data[target_col].notna()].copy()
            logger.info(
                "Filtered rows with non-null target | target=%s | before=%d | after=%d | removed=%d",
                target_col,
                before_rows,
                len(data),
                before_rows - len(data),
            )

        parsed_bundle_name = data["bundle_name"].apply(self.parse_bundle_name).apply(pd.Series)
        data = pd.concat([data, parsed_bundle_name], axis=1)
        logger.info("Parsed bundle_name signals and fallback structured values")

        mb_values = data.apply(
            lambda row: self.choose_value(row.get("configured_volume_mb", np.nan), row["parsed_volume_mb"]),
            axis=1,
        )
        min_values = data.apply(
            lambda row: self.choose_value(row.get("configured_volume_min", np.nan), row["parsed_volume_min"]),
            axis=1,
        )
        sms_values = data.apply(
            lambda row: self.choose_value(row.get("configured_volume_sms", np.nan), row["parsed_volume_sms"]),
            axis=1,
        )
        validity_values = data.apply(
            lambda row: self.choose_value(row.get("validity_hours", np.nan), row["parsed_validity_hours"]),
            axis=1,
        )

        data["volume_mb"] = [value[0] for value in mb_values]
        data["volume_min"] = [value[0] for value in min_values]
        data["volume_sms"] = [value[0] for value in sms_values]
        data["validity_hours"] = [value[0] for value in validity_values]

        data["mb_value_source"] = [value[1] for value in mb_values]
        data["min_value_source"] = [value[1] for value in min_values]
        data["sms_value_source"] = [value[1] for value in sms_values]
        data["validity_value_source"] = [value[1] for value in validity_values]
        logger.info("Structured values resolved using configured-first fallback logic")

        data["is_unlimited_bundle"] = (
            (data["is_illimite"].fillna(0).astype(int) == 1)
            | (data["name_has_unlimited"] == 1)
        ).astype(int)

        data["is_speed_based_bundle"] = (data["name_has_speed"] == 1).astype(int)
        data["speed_mbps"] = data["parsed_speed_mbps"].fillna(0)

        data["has_data"] = (data["volume_mb"] > 0).astype(int)
        data["has_voice"] = (data["volume_min"] > 0).astype(int)
        data["has_sms"] = (data["volume_sms"] > 0).astype(int)

        data["is_data_only"] = (
            (data["has_data"] == 1)
            & (data["has_voice"] == 0)
            & (data["has_sms"] == 0)
        ).astype(int)
        data["is_voice_only"] = (
            (data["has_data"] == 0)
            & (data["has_voice"] == 1)
            & (data["has_sms"] == 0)
        ).astype(int)
        data["is_sms_only"] = (
            (data["has_data"] == 0)
            & (data["has_voice"] == 0)
            & (data["has_sms"] == 1)
        ).astype(int)
        data["is_combo_bundle"] = (
            data[["has_data", "has_voice", "has_sms"]].sum(axis=1) >= 2
        ).astype(int)

        data["validity_days"] = data["validity_hours"] / 24.0
        data["validity_days"] = data["validity_days"].replace([np.inf, -np.inf], np.nan).fillna(0)

        data["log_price"] = np.log1p(data["price"].clip(lower=0))
        data["log_mb"] = np.log1p(data["volume_mb"].clip(lower=0))
        data["log_min"] = np.log1p(data["volume_min"].clip(lower=0))
        data["log_sms"] = np.log1p(data["volume_sms"].clip(lower=0))
        data["log_validity_hours"] = np.log1p(data["validity_hours"].clip(lower=0))

        data["validity_bucket"] = np.select(
            [
                data["validity_days"] <= 1,
                (data["validity_days"] > 1) & (data["validity_days"] <= 7),
                (data["validity_days"] > 7) & (data["validity_days"] <= 30),
                data["validity_days"] > 30,
            ],
            [
                "daily",
                "weekly",
                "monthly",
                "long_term",
            ],
            default="unknown",
        )

        week = data["week_number"].fillna(0)
        data["week_sin"] = np.sin(2 * np.pi * week / 52.0)
        data["week_cos"] = np.cos(2 * np.pi * week / 52.0)

        data["bundle_value_proxy"] = (
            0.5 * data["log_mb"]
            + 0.3 * data["log_min"]
            + 0.2 * data["log_sms"]
        )

        for column in CATEGORICAL_FEATURE_COLUMNS:
            if column in data.columns:
                data[column] = data[column].fillna("unknown").astype(str).str.strip()
        logger.info("Categorical columns normalized")

        feature_columns = [
            "week_number",
            "year_number",
            "week_sin",
            "week_cos",
            "season",
            "bundle_type",
            "usage_type",
            "service_class_category",
            "price",
            "log_price",
            "volume_mb",
            "volume_min",
            "volume_sms",
            "log_mb",
            "log_min",
            "log_sms",
            "validity_hours",
            "validity_days",
            "log_validity_hours",
            "validity_bucket",
            "has_data",
            "has_voice",
            "has_sms",
            "is_data_only",
            "is_voice_only",
            "is_sms_only",
            "is_combo_bundle",
            "is_unlimited_bundle",
            "is_speed_based_bundle",
            "speed_mbps",
            "name_has_social",
            "name_has_roaming",
        ]
        feature_columns = [column for column in feature_columns if column in data.columns]

        keep_columns = feature_columns.copy()
        if target_col is not None and target_col in data.columns:
            keep_columns.append(target_col)
        keep_columns.extend(["bundle_id", "bundle_name"])
        keep_columns = [column for column in keep_columns if column in data.columns]

        model_frame = data[keep_columns].copy()

        numeric_frame_columns = model_frame.select_dtypes(include=[np.number]).columns
        model_frame[numeric_frame_columns] = model_frame[numeric_frame_columns].replace(
            [np.inf, -np.inf],
            np.nan,
        )
        model_frame[numeric_frame_columns] = model_frame[numeric_frame_columns].fillna(0)

        logger.info(
            "Feature engineering completed | output_shape=%s | feature_count=%d",
            model_frame.shape,
            len(feature_columns),
        )
        logger.info("Selected feature columns | columns=%s", feature_columns)

        return model_frame, feature_columns
