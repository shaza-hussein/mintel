import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class GraphSAGEGraphStatsResponse(BaseModel):
    msisdn_nodes: int
    bundle_nodes: int
    train_edges: int
    val_edges: int
    test_edges: int
    total_edges: int
    avg_degree: float


class GraphNode(BaseModel):
    id: str
    node_type: str
    label: str
    features: Dict[str, Any]


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    edge_type: str
    features: Dict[str, Any]


class GraphDataResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    node_count: int
    edge_count: int
    truncated: bool


class GraphNodeSearchItem(BaseModel):
    id: str
    node_type: str
    label: str
    features: Dict[str, Any]


class GraphNodeSearchResponse(BaseModel):
    total_returned: int
    results: List[GraphNodeSearchItem]