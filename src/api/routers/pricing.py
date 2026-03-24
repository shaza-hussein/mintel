import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))


from fastapi import APIRouter, HTTPException
from src.app.products.pricing.config import PRICING_CONFIG  
from src.app.products.pricing.db import DynamicPricingEngine
from  src.api.models.pricing import (
    BundleRequest,
    BundleResponse,
    PriceLookupRequest,
    PriceLookupResponse,
    ConfigResponse
)

router = APIRouter(prefix="/pricing", tags=["Dynamic Pricing"])


@router.post("/bundle", response_model=BundleResponse)
def calculate_bundle(req: BundleRequest):
    try:
        engine = DynamicPricingEngine(req.config)

        result = engine.calculate_bundle(
            service_allocations=req.service_allocations,
            validity_days=req.validity_days,
            offer_type=req.offer_type
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/price-lookup", response_model=PriceLookupResponse)
def calculate_price(req: PriceLookupRequest):
    try:
        engine = DynamicPricingEngine(req.config)

        result = engine.calculate_price_from_volume(
            target_volumes=req.target_volumes,
            validity_days=req.validity_days,
            offer_type=req.offer_type
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


@router.get("/config", response_model=ConfigResponse)
def get_pricing_config():
    try:
        return {"config": PRICING_CONFIG}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))