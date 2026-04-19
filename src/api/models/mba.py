import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from typing import Any, Dict, List, Tuple
from pydantic import BaseModel


class HybridBundlesRequest(BaseModel):
    top_k: int = 10
    allowed_sizes: Tuple[int, int] = (2, 3)
    min_freq: int = 5000
    min_support_pct: float = 0.001
    suppress_subsets: bool = True
    offer_type: str = "atl"


class HybridBundleItem(BaseModel):
    name: str
    components: Dict[str, float]
    validity_days: int
    calculated_price: float
    individual_prices: Dict[str, float]
    score: float
    justification: str


class HybridBundlesResponse(BaseModel):
    bundles: List[HybridBundleItem]


class SankeyRequest(BaseModel):
    antecedent_col: str = "antecedent"
    consequent_col: str = "consequent"
    support_col: str = "support"
    confidence_col: str = "confidence"
    lift_col: str = "lift"
    top_n_edges: int = 30
    split_rule_weight_across_pairs: bool = True


class SankeyNode(BaseModel):
    name: str


class SankeyLink(BaseModel):
    source: int
    target: int
    value: float
    source_name: str
    target_name: str
    avg_confidence: float
    avg_lift: float
    edge_count: int
    strength_score: float


class SankeyNodeData(BaseModel):
    label: List[str]


class SankeyLinkData(BaseModel):
    source: List[int]
    target: List[int]
    value: List[float]
    customdata: List[List[Any]]


class SankeyData(BaseModel):
    node: SankeyNodeData
    link: SankeyLinkData


class SankeyEdgeTableItem(BaseModel):
    source: str
    target: str
    value: float
    avg_confidence: float
    avg_lift: float
    edge_count: int
    strength_score: float


class SankeyResponse(BaseModel):
    nodes: List[SankeyNode]
    links: List[SankeyLink]
    sankey_data: SankeyData
    edge_table: List[SankeyEdgeTableItem]
