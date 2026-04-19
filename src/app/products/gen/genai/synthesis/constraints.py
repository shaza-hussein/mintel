import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../..")))
import pandas as pd
from src.app.products.gen.genai.synthesis.config import CTGANBundleConfig
from src.app.products.gen.genai.synthesis.pricing_service import BundlePricingService

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


def enforce_business_constraints(
    df: pd.DataFrame,
    config: CTGANBundleConfig=CTGANBundleConfig(),
) -> pd.DataFrame:
    data = df.copy()

    data["price"] = data["price"].clip(lower=1)
    data["volume_mb"] = data["volume_mb"].clip(lower=0)
    data["volume_min"] = data["volume_min"].clip(lower=0)
    data["volume_sms"] = data["volume_sms"].clip(lower=0)
    data["validity_hours"] = data["validity_hours"].clip(lower=1)

    data["validity_hours"] = data["validity_hours"].apply(
        lambda value: min(config.validity_options, key=lambda option: abs(option - value))
    )

    data_mask = data["bundle_type"].str.contains("DATA", case=False, na=False)
    median_mb = data.loc[data_mask, "volume_mb"].replace(0, pd.NA).median()
    median_mb = float(median_mb) if pd.notna(median_mb) else 100.0
    data.loc[data_mask & (data["volume_mb"] < 10), "volume_mb"] = median_mb

    voice_mask = data["bundle_type"].isin(config.voice_bundle_types)
    median_min = data.loc[voice_mask, "volume_min"].replace(0, pd.NA).median()
    median_min = float(median_min) if pd.notna(median_min) else 10.0
    data.loc[voice_mask & (data["volume_min"] < 1), "volume_min"] = median_min

    valid_mask = (
        data[["volume_mb", "volume_min", "volume_sms"]].sum(axis=1) > 0
    )
    data = data.loc[valid_mask].reset_index(drop=True)
    
    # volume mb, min, and sms contraints.
    data = volume_contraints(data, config)
    return data


def final_cleanup_and_reprice(
    df: pd.DataFrame,
    real_data: pd.DataFrame,
    config: CTGANBundleConfig,
) -> pd.DataFrame:
    data = df.copy()

    data_mask = data["bundle_type"].str.contains("DATA", case=False, na=False)
    voice_mask = data["bundle_type"].isin(config.voice_bundle_types)
    sms_mask = data["bundle_type"].str.contains("SMS", case=False, na=False)

    data.loc[data_mask, "volume_min"] = 0.0
    data.loc[data_mask, "volume_sms"] = 0.0
    data.loc[voice_mask, "volume_mb"] = 0.0
    data.loc[sms_mask, "volume_mb"] = 0.0
    data.loc[sms_mask, "volume_min"] = 0.0

    for column in ["volume_mb", "volume_min", "volume_sms"]:
        cap_value = real_data[column].quantile(0.999)
        data[column] = data[column].clip(upper=cap_value)

    data["volume_min"] = data["volume_min"].round(1)
    data["volume_sms"] = data["volume_sms"].round(0).astype(int)
    data["volume_mb"] = data["volume_mb"].round(2)

    pricing_service = BundlePricingService(config=config)
    data = pricing_service.reprice_dataframe(data)

    return data.reset_index(drop=True)


def volume_contraints(df: pd.DataFrame, config: CTGANBundleConfig=CTGANBundleConfig()) -> pd.DataFrame:
    df = df.copy()
    # Ensure no NaNs break logic
    df["volume_mb"]  = df["volume_mb"].fillna(0)
    df["volume_min"] = df["volume_min"].fillna(0)
    df["volume_sms"] = df["volume_sms"].fillna(0)
    # Build conditions
    cond_data = (
        (df["bundle_type"] == "BUNDLE_DATA") &
        (df["volume_mb"] <= config.max_volume_mb)
    )
    cond_voice = (
        (df["bundle_type"] == "BUNDLE_VOICE") &
        (df["volume_min"] <= config.max_volume_min)
    )
    cond_sms = (
        (df["bundle_type"] == "BUNDLE_SMS") &
        (df["volume_sms"] <= config.max_volume_sms)
    )
    # Combine all valid conditions
    filtered_df = df[cond_data | cond_voice | cond_sms]

    return filtered_df.reset_index(drop=True)