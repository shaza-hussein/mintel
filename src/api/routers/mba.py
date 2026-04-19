import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from fastapi import APIRouter, HTTPException

from src.app.products.mba.analytics import MarketBasketAnalyzer
from src.api.models.mba import (
    HybridBundlesRequest,
    HybridBundlesResponse,
    SankeyRequest,
    SankeyResponse,
)

router = APIRouter(prefix="/mba", tags=["Market Basket Analysis"])


@router.post("/hybrid-bundles", response_model=HybridBundlesResponse)
def get_hybrid_bundles(req: HybridBundlesRequest):
    try:
        mba = MarketBasketAnalyzer()

        result = mba.hybrid_bundles(
            top_k=req.top_k,
            allowed_sizes=req.allowed_sizes,
            min_freq=req.min_freq,
            min_support_pct=req.min_support_pct,
            suppress_subsets=req.suppress_subsets,
            offer_type=req.offer_type,
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/item-relationship-sankey", response_model=SankeyResponse)
def get_item_relationship_sankey(req: SankeyRequest):
    try:
        mba = MarketBasketAnalyzer()

        result = mba.item_relationship_sankey(
            antecedent_col=req.antecedent_col,
            consequent_col=req.consequent_col,
            support_col=req.support_col,
            confidence_col=req.confidence_col,
            lift_col=req.lift_col,
            top_n_edges=req.top_n_edges,
            split_rule_weight_across_pairs=req.split_rule_weight_across_pairs,
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
