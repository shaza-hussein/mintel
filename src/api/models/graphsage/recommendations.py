import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from typing import List, Optional
from pydantic import BaseModel, Field


class GraphSAGERecommendation(BaseModel):
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
    matched_features: List[str] = Field(default_factory=list)
    cohort_size: Optional[int] = None


class GraphSAGERecommendationsResponse(BaseModel):
    total_returned: int
    offset: int
    limit: int
    recommendations: List[GraphSAGERecommendation]


class GraphSAGEMsisdnRecommendationsResponse(BaseModel):
    msisdn: str
    total_returned: int
    recommendations: List[GraphSAGERecommendation]