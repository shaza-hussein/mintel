import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))

from src.app.products.gen.cim.contracts import ExistingCols
from src.app.products.gen.cim.config import ModelParams

import pandas as pd

def extract_existing_features(row):
    return {
        "volume_mb": float(row.get("volume_mb", 0)),
        "minutes": float(row.get("minutes", 0)),
        "sms": float(row.get("sms", 0)),
        "price": float(row.get("price", 0)),
        "validity_days": 0.0,
    }

def extract_generated_features(row):
    return {
        "volume_mb": float(row.get("volume_mb", 0)),
        "minutes": float(row.get("volume_min", 0)),
        "sms": float(row.get("volume_sms", 0)),
        "price": float(row.get("price", 0)),
        "validity_days": float(row.get("validity_days", 0)),
    }


def compute_portfolio_maxima(existing: pd.DataFrame, params: ModelParams) -> dict:
    """Max of each feature across the existing portfolio (for normalization)."""
    maxima = {}
    for key in params.feature_weights:
        if key == "volume_mb":
            maxima[key] = float(existing[ExistingCols.VOLUME_MB].max() or 1)
        elif key == "minutes":
            maxima[key] = float(existing[ExistingCols.MINUTES].max() or 1)
        elif key == "sms":
            maxima[key] = float(existing[ExistingCols.SMS].max() or 1)
        elif key == "price":
            maxima[key] = float(existing[ExistingCols.PRICE].max() or 1)
        elif key == "validity_days":
            maxima[key] = 30.0   # assume max 30-day bundle as reference
    return maxima


def normalize_features(params: ModelParams, maxima: dict,fv: dict, new_bundle_fv: dict = None) -> dict:
    """
    Normalize feature dict against portfolio maxima.
    If new_bundle_fv supplied, maxima are updated to include it
    (so new bundle never exceeds 1.0 and existing stay proportional).
    """
    maxima = dict(maxima)
    if new_bundle_fv:
        for k in maxima:
            maxima[k] = max(maxima[k], new_bundle_fv.get(k, 0.0))
    return {
        k: min(fv.get(k, 0.0) / maxima[k], 1.0) if maxima.get(k, 0) > 0 else 0.0
        for k in params.feature_weights
    }