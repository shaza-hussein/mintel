import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))


from fastapi import APIRouter, HTTPException, Query
from src.app.products.pricing.config import PRICING_CONFIG  
from src.app.products.pricing.db import DynamicPricingEngine
from typing import Any, Dict, List, Optional
from src.app.products.pricing.visualization import PricingVisualizationData
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
    

@router.get("/visualization", response_model=Dict[str, Any])
def get_all_pricing_visualizations(
    validities: Optional[List[int]] = Query(default=None),
    n_points: int = Query(default=400, ge=2, le=2000),
):
    try:
        visualizer = PricingVisualizationData(PRICING_CONFIG)
        return visualizer.build_all_service_charts(
            validities=validities,
            n_points=n_points,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/visualization/{service}", response_model=Dict[str, Any])
def get_pricing_visualization(
    service: str,
    validities: Optional[List[int]] = Query(default=None),
    n_points: int = Query(default=400, ge=2, le=2000),
):
    try:
        visualizer = PricingVisualizationData(PRICING_CONFIG)
        return visualizer.build_service_chart(
            service=service,
            validities=validities,
            n_points=n_points,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))