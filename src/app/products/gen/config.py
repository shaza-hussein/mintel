import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[5]

_ALLOWED_OFFER_TYPES = {
    "atl",
    "diy_mode",
    "promotion_mode",
    "btl_normal",
    "btl_moderate",
    "btl_aggressive",
}

_OFFER_TYPE_ALIASES = {
    "btl": "btl_normal",
    "promo": "promotion_mode",
    "promotion": "promotion_mode",
    "diy": "diy_mode",
}


@dataclass(frozen=True)
class DataConfig:
    dataset_folder: Path = PROJECT_ROOT / "datasets"
    weekly_bundles_filename: str = "weekly_base_bundles_info_202501_202510.csv"

    @property
    def weekly_bundles_data_path(self) -> Path:
        return self.dataset_folder / self.weekly_bundles_filename


@dataclass(frozen=True)
class BundleGenerationConfig:
    offer_type: str = "atl"
    samples_per_type: int = 500
    top_n_per_bundle_type: int = 2

    # Keep only these popularity buckets after scoring
    popularity_categories: Tuple[str, ...] = ("Very Popular",)

    # Optional filter, e.g. ("BUNDLE_DATA", "BUNDLE_VOICE")
    allowed_bundle_types: Tuple[str, ...] = ()

    # Controls other generated bundle parameters too
    validity_options: Tuple[float, ...] = (24.0, 48.0, 72.0, 168.0, 360.0, 720.0)
    max_volume_mb: float = 25_000
    max_volume_min: int = 200
    max_volume_sms: int = 100

    def normalized_offer_type(self) -> str:
        raw_value = str(self.offer_type or "atl").strip().lower()
        normalized = _OFFER_TYPE_ALIASES.get(raw_value, raw_value)

        if normalized not in _ALLOWED_OFFER_TYPES:
            raise ValueError(
                f"Unsupported offer_type='{self.offer_type}'. "
                f"Allowed values: {sorted(_ALLOWED_OFFER_TYPES)}"
            )

        return normalized

    def normalized_bundle_types(self) -> Tuple[str, ...]:
        normalized = []
        for bundle_type in self.allowed_bundle_types:
            if bundle_type is None:
                continue

            value = str(bundle_type).strip()
            if value:
                normalized.append(value.upper())

        return tuple(normalized)
