import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))

from typing import Dict, Optional
import pandas as pd

from src.app.products.genai.synthesis.config import CTGANBundleConfig
from src.app.products.pricing.config import PRICING_CONFIG
from src.app.products.pricing.db import DynamicPricingEngine

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


class BundlePricingService:
    def __init__(self, config: Optional[CTGANBundleConfig] = None) -> None:
        self.config = config or CTGANBundleConfig()
        self.engine = DynamicPricingEngine(PRICING_CONFIG)

    def calculate_price_for_row(self, row: pd.Series) -> float:
        bundle_type = str(row.get("bundle_type", "")).strip()
        active_services = self.config.bundle_service_map.get(
            bundle_type,
            (self.config.default_fallback_service,),
        )

        validity_days = max(1, int(float(row.get("validity_hours", 24.0)) / 24))

        target_volumes: Dict[str, float] = {}
        if "data" in active_services and float(row.get("volume_mb", 0.0)) > 0:
            target_volumes["data"] = float(row["volume_mb"])
        if "voice" in active_services and float(row.get("volume_min", 0.0)) > 0:
            target_volumes["voice"] = float(row["volume_min"])
        if "sms" in active_services and float(row.get("volume_sms", 0.0)) > 0:
            target_volumes["sms"] = float(row["volume_sms"])

        if not target_volumes:
            return 5.0

        result = self.engine.calculate_price_from_volume(
            target_volumes=target_volumes,
            validity_days=validity_days,
            offer_type=self.config.default_offer_type,
        )

        if "error" in result:
            logger.warning(
                "Pricing engine returned error for bundle_type=%s | error=%s",
                bundle_type,
                result["error"],
            )
            return 5.0

        return float(result["calculated_price"])

    def reprice_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        data["price"] = data.apply(self.calculate_price_for_row, axis=1)
        data["price"] = data["price"].clip(lower=5)
        return data
