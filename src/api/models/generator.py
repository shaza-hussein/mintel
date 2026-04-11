import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field


class BundleGeneratorRequest(BaseModel):
    offer_type: str = "atl"
    allowed_bundle_types: Tuple[str, ...] = (
        "BUNDLE_DATA",
        "BUNDLE_VOICE",
        "BUNDLE_SMS",
    )
    validity_options: Tuple[float, ...] = (24.0, 72.0, 168.0, 720.0)
    max_volume_mb: float = 25000
    max_volume_min: int = 300
    max_volume_sms: int = 150
    samples_per_type: int = Field(default=500, gt=0)
    top_n: int = Field(default=2, gt=0)


class ExistingBundleItem(BaseModel):
    bundle_id: Union[int, str]
    bundle_name: str
    price: float
    volume_mb: float
    bundle_type: str
    minutes: float
    sms: float
    avg_weekly_revenue: float
    avg_weekly_subs: float
    popularity_score: float


class GeneratedBundleItem(BaseModel):
    bundle_id: Union[int, str]
    bundle_type: str
    usage_type: Optional[str] = None
    service_class_category: Optional[str] = None
    price: float
    volume_mb: float
    volume_min: float
    volume_sms: float
    validity_hours: float
    validity_days: float
    validity_bucket: Optional[str] = None
    predicted_popularity: Optional[float] = None
    popularity_category: Optional[str] = None


class GeneratorMeta(BaseModel):
    existing_count: int
    generated_count: int
    summary_count: int
    top_per_type_count: int


class DashboardModelParams(BaseModel):
    growth_rate: float
    cannib_sensitivity: float
    price_elasticity: float
    similarity_threshold: float
    cannib_cap: float
    expected_new_market_pct: float
    cross_type_penalty: float
    feature_weights: Dict[str, float]


class BundleGeneratorResponse(BaseModel):
    request: BundleGeneratorRequest
    meta: GeneratorMeta
    model_params: DashboardModelParams
    existing_bundles: List[ExistingBundleItem]
    generated_bundles: List[GeneratedBundleItem]
    summary: List[Dict[str, Any]]
    top_per_type: List[Dict[str, Any]]
    impact_rows: List[Dict[str, Any]]
