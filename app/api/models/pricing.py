import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from pydantic import BaseModel
from typing import Dict, Optional, Any


class ConfigResponse(BaseModel):
    config: Dict[str, Any]


class BundleRequest(BaseModel):
    service_allocations: Dict[str, float]
    validity_days: int
    offer_type: str
    config: Dict


class BundleResponse(BaseModel):
    units: Dict[str, str]


class PriceLookupRequest(BaseModel):
    target_volumes: Dict[str, float]
    validity_days: int
    offer_type: str
    config: Dict


class PriceLookupResponse(BaseModel):
    calculated_price: float
    individual_prices: Optional[Dict[str, float]] = None