import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from typing import List, Optional
from pydantic import BaseModel, Field


class ColdStartFeatureOptionsResponse(BaseModel):
    service_class_category: List[str]
    canal: List[str]
    payment_mode: List[str]
    department_city: List[str]
    brand_name: List[str]
    device_capability: List[str]
    bundle_type: List[str]
    min_price: Optional[float] = None
    max_price: Optional[float] = None


class ColdStartRecommendationRequest(BaseModel):
    msisdn: str = "cold_start_user"
    top_k: int = Field(default=10, ge=1, le=100)

    service_class_category: Optional[str] = None
    canal: Optional[str] = None
    payment_mode: Optional[str] = None
    department_city: Optional[str] = None
    brand_name: Optional[str] = None
    device_capability: Optional[str] = None

    bundle_type: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None

    min_cohort_users: int = Field(default=100, ge=1)


class ColdStartRecommendation(BaseModel):
    rank: int
    msisdn: str
    user_idx: Optional[int] = None
    bundle_idx: int
    bundle_id: str
    bundle_name: str
    bundle_type: str
    price: Optional[float] = None
    score: float
    recommendation_type: str
    matched_features: List[str] = []
    cohort_size: int = 0


class ColdStartRecommendationResponse(BaseModel):
    msisdn: str
    total_returned: int
    recommendations: List[ColdStartRecommendation]