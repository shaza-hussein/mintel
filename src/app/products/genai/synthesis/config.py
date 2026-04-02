import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[5]


@dataclass(frozen=True)
class CTGANBundleConfig:
    model_columns: Tuple[str, ...] = (
        "bundle_type",
        "usage_type",
        "service_class_category",
        "price",
        "volume_mb",
        "volume_min",
        "volume_sms",
        "validity_hours",
    )
    sparse_columns: Tuple[str, ...] = (
        "volume_mb",
        "volume_min",
        "volume_sms",
    )
    validity_options: Tuple[float, ...] = (24.0, 48.0, 72.0, 168.0, 360.0, 720.0)
    voice_bundle_types: Tuple[str, ...] = (
        "BUNDLE_VOICE",
        "INT_BUNDLE_VOICE",
        "OFFNET_BUNDLE_VOICE",
        "BUNDLE_VOICEDATA",
        "ONNET_BUNDLE_VOICE",
    )

    bundle_service_map: Mapping[str, Tuple[str, ...]] = field(
        default_factory=lambda: {
            "BUNDLE_DATA": ("data",),
            "BUNDLE_VOICE": ("voice",),
            "BUNDLE_SMS": ("sms",),
            "INT_BUNDLE_VOICE": ("voice",),
            "OFFNET_BUNDLE_VOICE": ("voice",),
            "BUNDLE_VOICEDATA": ("voice", "data"),
            "FLEXI_BUNDLE": ("voice", "data"),
        }
    )
    default_offer_type: str = "atl"
    default_fallback_service: str = "data"

    min_rows_for_ctgan: int = 100
    pac: int = 10
    epochs: int = 300
    max_batch_size: int = 500
    generator_dim: Tuple[int, int] = (256, 256)
    discriminator_dim: Tuple[int, int] = (256, 256)
    bootstrap_noise_pct: float = 0.05
    default_samples_per_type: int = 500
    random_seed: int = 42

    @property
    def discrete_columns(self) -> Tuple[str, ...]:
        return (
            "usage_type",
            "service_class_category",
            "has_volume_mb",
            "has_volume_min",
            "has_volume_sms",
        )


@dataclass(frozen=True)
class CTGANArtifactConfig:
    artifact_dir: Path = PROJECT_ROOT / "_models" / "bundle_synthesis"
    artifact_filename: str = "bundle_ctgan_synthesizer.joblib"

    @property
    def artifact_path(self) -> Path:
        return self.artifact_dir / self.artifact_filename
