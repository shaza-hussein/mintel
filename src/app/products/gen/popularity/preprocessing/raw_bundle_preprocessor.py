import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../..")))

import re
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from src.app.products.gen.popularity.constants import (
    RAW_REQUIRED_COLUMNS,
    RAW_TARGET_REQUIRED_COLUMNS,
    SYSTEM_NAMES,
)
from src.app.products.gen.popularity.preprocessing.validators import require_columns
from src.app.products.gen.popularity.function import PopularityFunction
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

class RawBundlePreprocessor:
    SYSTEM_NAMES = list(SYSTEM_NAMES)

    def __init__(self):
        self.popularity = PopularityFunction()

    @staticmethod
    def extract_conf_volume_values(volume_str: Any) -> Dict[str, Optional[float]]:
        if pd.isna(volume_str) or volume_str is None:
            return {"mb": None, "min": None, "sms": None}

        original_str = str(volume_str)
        if original_str.lower() in ["unlimited", "illimitÃ©", "illimite"]:
            return {"mb": None, "min": None, "sms": None}

        volume_str = original_str.replace(",", ".")
        volume_str_upper = volume_str.upper()

        mb_value = None
        min_value = None
        sms_value = None

        gb_pattern = r"(\d+(?:\.\d+)?)\s*G(?:B)?\b"
        gb_matches = re.findall(gb_pattern, volume_str_upper)
        if gb_matches:
            mb_value = sum(float(gb) for gb in gb_matches) * 1024

        mb_pattern = r"(\d+(?:\.\d+)?)\s*MB\b"
        mb_matches = re.findall(mb_pattern, volume_str_upper)
        if mb_matches:
            total_mb = sum(float(mb) for mb in mb_matches)
            mb_value = total_mb if mb_value is None else mb_value + total_mb

        min_pattern = r"(\d+(?:\.\d+)?)\s*MINS?\b"
        min_matches = re.findall(min_pattern, volume_str_upper)
        add_pattern_min = r"(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)\s*MINS?\b"
        add_match_min = re.search(add_pattern_min, volume_str_upper)

        if add_match_min:
            min_value = float(add_match_min.group(1)) + float(add_match_min.group(2))
        elif min_matches:
            min_value = sum(float(match) for match in min_matches)

        sms_pattern = r"(\d+(?:\.\d+)?)\s*SMS\b"
        sms_matches = re.findall(sms_pattern, volume_str_upper)
        if sms_matches:
            sms_value = sum(float(sms) for sms in sms_matches)

        slash_pattern = r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)"
        slash_match = re.search(slash_pattern, volume_str)
        if slash_match and "MIN" in volume_str_upper:
            if min_value is None:
                min_value = float(slash_match.group(2))
            if mb_value is None:
                mb_value = float(slash_match.group(1))

        sec_pattern = r"(\d+(?:\.\d+)?)\s*SEC\b"
        sec_matches = re.findall(sec_pattern, volume_str_upper)
        if sec_matches:
            sec_as_min = sum(float(sec) for sec in sec_matches) / 60.0
            min_value = sec_as_min if min_value is None else min_value + sec_as_min

        return {"mb": mb_value, "min": min_value, "sms": sms_value}

    @staticmethod
    def clean_price(value: Any) -> Optional[float]:
        if pd.isna(value):
            return None

        normalized = str(value).replace("F", "").replace(",", "")
        try:
            return float(normalized)
        except Exception:
            return None

    @staticmethod
    def parse_validity_to_hours(value: Any) -> float:
        if pd.isna(value):
            return np.nan

        if isinstance(value, (int, float)):
            return float(value) * 24.0

        normalized = str(value).strip().lower()
        normalized = re.sub(r"\s+", " ", normalized)

        match = re.match(r"^(\d+(\.\d+)?)\s*(day|days|hour|hours|month|months)?", normalized)
        if not match:
            return np.nan

        numeric_value = float(match.group(1))
        unit = match.group(3) or "days"

        if "hour" in unit:
            return numeric_value
        if "day" in unit:
            return numeric_value * 24.0
        if "month" in unit:
            return numeric_value * 30.0 * 24.0
        return numeric_value * 24.0

    @staticmethod
    def extract_price(text: Any) -> Optional[float]:
        if pd.isna(text):
            return None

        match = re.search(r"@(\d+)\s*F", str(text))
        if match:
            return float(match.group(1))
        return None

    @staticmethod
    def week_to_season(iso_week: int) -> str:
        if 1 <= iso_week <= 13:
            return "winter"
        if 14 <= iso_week <= 26:
            return "spring"
        if 27 <= iso_week <= 39:
            return "summer"
        return "autumn"

    @staticmethod
    def is_illimite(bundle_name: str) -> int:
        return 1 if "illimite" in bundle_name.lower() else 0

    @staticmethod
    def build_input_features_of_target(data: pd.DataFrame) -> pd.DataFrame:
        revenue_by_week = data.groupby("week_number")["total_rev"].sum()
        data["week_total_rev"] = data["week_number"].map(revenue_by_week)
        data["rev_contribution"] = data["total_rev"] / data["week_total_rev"]
        data["rev_contribution_pct"] = data["rev_contribution"] * 100
        data = data.drop(columns=["week_total_rev"])
        logger.info("Revenue contribution features created")

        before_rows = len(data)
        data = data[~(data["total_rev"] <= 0.0)].copy()
        logger.info(
            "Removed non-positive total_rev rows | before=%d | after=%d | removed=%d",
            before_rows,
            len(data),
            before_rows - len(data),
        )

        before_rows = len(data)
        data = data[~(data["usage_type"] == "FREE")].copy()
        logger.info(
            "Removed FREE usage_type rows | before=%d | after=%d | removed=%d",
            before_rows,
            len(data),
            before_rows - len(data),
        )

        return data
    
    def transform(self, df: pd.DataFrame, build_target: bool = True) -> pd.DataFrame:
        required_columns = list(RAW_REQUIRED_COLUMNS)
        if build_target:
            required_columns.extend(RAW_TARGET_REQUIRED_COLUMNS)

        require_columns(df, required_columns, "RawBundlePreprocessor.transform")

        data = df.copy()
        logger.info(
            "Starting raw preprocessing | build_target=%s | input_shape=%s",
            build_target,
            data.shape,
        )

        data = self._filter_missing_configured_volume(data)
        data = self._extract_configured_volume_features(data)
        data = self._clean_price_column(data)
        data = self._normalize_validity(data)
        data = self._remove_diy_bundles(data)
        data = self._drop_total_duration_if_present(data)
        data = self._drop_missing_bundle_names(data)
        data = self._fill_missing_validity_values(data)
        data = self._impute_missing_prices(data)

        data["season"] = data["week_number"].apply(self.week_to_season)
        logger.info("Season assigned from week_number")

        if build_target:
            data = self.build_input_features_of_target(data)

        data["is_illimite"] = data["bundle_name"].apply(self.is_illimite)
        logger.info("Illimite flag created")

        if build_target:
            data = self._build_popularity_target(data)

        logger.info("Raw preprocessing completed | output_shape=%s", data.shape)
        return data.reset_index(drop=True)

    def _filter_missing_configured_volume(self, data: pd.DataFrame) -> pd.DataFrame:
        before_rows = len(data)
        filtered = data[~data["configured_volume"].isna()].copy()
        logger.info(
            "Filtered missing configured_volume | before=%d | after=%d | removed=%d",
            before_rows,
            len(filtered),
            before_rows - len(filtered),
        )
        return filtered

    def _extract_configured_volume_features(self, data: pd.DataFrame) -> pd.DataFrame:
        volume_extracted = data["configured_volume"].apply(self.extract_conf_volume_values)

        data["configured_volume_mb"] = volume_extracted.apply(
            lambda item: item["mb"] if item["mb"] is not None else 0.0
        )
        data["configured_volume_min"] = volume_extracted.apply(
            lambda item: item["min"] if item["min"] is not None else 0.0
        )
        data["configured_volume_sms"] = volume_extracted.apply(
            lambda item: item["sms"] if item["sms"] is not None else 0.0
        )

        data = data.drop(columns=["configured_volume"])
        logger.info("Configured volume extracted into numeric columns")
        return data

    def _clean_price_column(self, data: pd.DataFrame) -> pd.DataFrame:
        data["price"] = data["price"].apply(self.clean_price)
        logger.info("Price column cleaned")
        return data

    def _normalize_validity(self, data: pd.DataFrame) -> pd.DataFrame:
        data["clean_validity"] = np.where(
            data["validity"].str.strip().str.lower().isin(["null", ""]) | data["validity"].isna(),
            None,
            data["validity"]
            .str.strip()
            .str.lower()
            .str.replace(r"\(s\)", "", regex=True)
            .str.replace(r"\bday\b", "days", regex=True)
            .str.replace(r"\bmonth\b", "months", regex=True),
        )
        data = data.drop(columns=["validity"])
        data = data.rename(columns={"clean_validity": "validity"})
        logger.info("Validity column normalized")

        data["validity_hours"] = data["validity"].apply(self.parse_validity_to_hours)
        logger.info("Validity converted to hours")
        return data

    def _remove_diy_bundles(self, data: pd.DataFrame) -> pd.DataFrame:
        before_rows = len(data)
        filtered = data[~data["bundle_name"].str.contains("DIY", case=False, na=False)].copy()
        logger.info(
            "Removed DIY bundles | before=%d | after=%d | removed=%d",
            before_rows,
            len(filtered),
            before_rows - len(filtered),
        )
        return filtered

    def _drop_total_duration_if_present(self, data: pd.DataFrame) -> pd.DataFrame:
        if "total_duration" in data.columns:
            data = data.drop(columns=["total_duration"])
            logger.info("Dropped total_duration column")
        return data

    def _drop_missing_bundle_names(self, data: pd.DataFrame) -> pd.DataFrame:
        before_rows = len(data)
        cleaned = data.dropna(subset=["bundle_name"]).copy()
        logger.info(
            "Dropped rows with missing bundle_name | before=%d | after=%d | removed=%d",
            before_rows,
            len(cleaned),
            before_rows - len(cleaned),
        )
        return cleaned

    def _fill_missing_validity_values(self, data: pd.DataFrame) -> pd.DataFrame:
        data["validity"] = data["validity"].fillna("NO_VALIDITY")
        data["validity_hours"] = data["validity_hours"].fillna(0)
        logger.info("Filled missing validity fields")
        return data

    def _impute_missing_prices(self, data: pd.DataFrame) -> pd.DataFrame:
        missing_price_before = int(data["price"].isna().sum())

        mask_missing_price = data["price"].isna()
        data.loc[mask_missing_price, "price_extracted"] = data.loc[
            mask_missing_price, "bundle_name"
        ].apply(self.extract_price)

        extracted_from_name = int(data.loc[mask_missing_price, "price_extracted"].notna().sum())

        data["price"] = data["price"].fillna(data["price_extracted"])

        free_mask = data["bundle_name"].str.contains("@F", na=False)
        free_count = int(free_mask.sum())
        data.loc[free_mask, "price"] = 0

        staff_mask = data["bundle_name"].str.contains("STAFF", na=False, case=False)
        staff_count = int(staff_mask.sum())
        data.loc[staff_mask, "price"] = 0

        system_mask = data["bundle_name"].isin(self.SYSTEM_NAMES)
        system_count = int(system_mask.sum())
        data.loc[system_mask, "price"] = 0

        still_missing = data["price"].isna()
        filled_zero_count = int(still_missing.sum())
        data.loc[still_missing, "price"] = 0

        if "price_extracted" in data.columns:
            data = data.drop(columns=["price_extracted"])

        logger.info(
            "Price imputation completed | missing_before=%d | extracted_from_name=%d | free_marked=%d | staff_marked=%d | system_marked=%d | filled_zero=%d",
            missing_price_before,
            extracted_from_name,
            free_count,
            staff_count,
            system_count,
            filled_zero_count,
        )
        return data

    def _build_popularity_target(self, data: pd.DataFrame) -> pd.DataFrame:
       return self.popularity.build_popularity_target(data=data)