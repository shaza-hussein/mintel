import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

import ast
from typing import Dict, Any, Optional, Tuple, List
import re
import pandas as pd
from src.app.products.mba.config import ArtifactConfig
from src.app.products.mba.inference import recommend_bundle_candidates_from_itemsets
from src.app.products.gen.genai.llm.selector import Selector
from src.app.products.pricing.db import DynamicPricingEngine
from src.app.products.pricing.config import PRICING_CONFIG

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


class MarketBasketAnalyzer:


    def __init__(self, artifact_config: Optional[ArtifactConfig] = None) -> None:
        self.artifact_config = artifact_config or ArtifactConfig()
        self.selector = Selector()
        self.pricing_engine = DynamicPricingEngine(config=PRICING_CONFIG)


    def hybrid_bundles(self, 
        top_k: int=10, 
        allowed_sizes: Tuple[int, int]=(2, 3),
        min_freq: int=5000,
        min_support_pct: float=0.001,
        suppress_subsets: bool=True,
        offer_type: str = "atl"
        ) -> Dict[str, Any]:
        """
        - based on the freq sets can return the best 2 hybrid bundles
        """
        bundle_candidates = recommend_bundle_candidates_from_itemsets(
            top_k=top_k,
            allowed_sizes=allowed_sizes,
            min_freq=min_freq,
            min_support_pct=min_support_pct,
            suppress_subsets=suppress_subsets,
        )

        bundles = self.selector.selecting(str(bundle_candidates))

        final_result = self.__reprice_bundles_pricing(
            result=bundles,
            offer_type=offer_type
        )

        return final_result



    def item_relationship_sankey(
        self,
        antecedent_col: str = "antecedent",
        consequent_col: str = "consequent",
        support_col: str = "support",
        confidence_col: str = "confidence",
        lift_col: str = "lift",
        top_n_edges: int = 30,
        split_rule_weight_across_pairs: bool = True,
    ) -> Dict[str, Any]:
        """
        - Convert association rules dataframe into sankey-ready data.
        """
        rules_df = pd.read_csv(self.artifact_config.association_rules_csv_path)
        required = [antecedent_col, consequent_col, support_col, confidence_col, lift_col]
        missing = [c for c in required if c not in rules_df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        def _clean_text(x):
            return re.sub(r"\s+", " ", str(x).strip())

        def _parse_items(value):
            if pd.isna(value):
                return []
            if isinstance(value, list):
                return [_clean_text(v) for v in value if _clean_text(v)]
            if isinstance(value, (set, tuple)):
                return [_clean_text(v) for v in list(value) if _clean_text(v)]

            raw = _clean_text(value)
            if not raw:
                return []

            try:
                parsed = ast.literal_eval(raw)
                if isinstance(parsed, (list, tuple, set)):
                    return [_clean_text(v) for v in parsed if _clean_text(v)]
                return [_clean_text(parsed)]
            except Exception:
                raw = raw.strip("[]")
                parts = [p.strip().strip("'").strip('"') for p in raw.split(",")]
                return [_clean_text(p) for p in parts if _clean_text(p)]

        df = rules_df.copy()
        df["__ants__"] = df[antecedent_col].apply(_parse_items)
        df["__cons__"] = df[consequent_col].apply(_parse_items)

        df[support_col] = pd.to_numeric(df[support_col], errors="coerce")
        df[confidence_col] = pd.to_numeric(df[confidence_col], errors="coerce")
        df[lift_col] = pd.to_numeric(df[lift_col], errors="coerce")

        df = df.dropna(subset=[support_col, confidence_col, lift_col])
        df = df[(df["__ants__"].map(len) > 0) & (df["__cons__"].map(len) > 0)].copy()

        edge_rows = []
        for _, row in df.iterrows():
            ants = row["__ants__"]
            cons = row["__cons__"]

            pair_count = max(len(ants) * len(cons), 1)
            edge_support = row[support_col] / pair_count if split_rule_weight_across_pairs else row[support_col]

            for a in ants:
                for c in cons:
                    edge_rows.append(
                        {
                            "source": a,
                            "target": c,
                            "edge_support": edge_support,
                            "confidence": row[confidence_col],
                            "lift": row[lift_col],
                        }
                    )

        edge_table = pd.DataFrame(edge_rows)

        if edge_table.empty:
            return {
                "nodes": [],
                "links": [],
                "sankey_data": {"node": {"label": []}, "link": {"source": [], "target": [], "value": []}},
                "edge_table": edge_table,
            }

        edge_table = (
            edge_table.groupby(["source", "target"], as_index=False)
            .agg(
                value=("edge_support", "sum"),
                avg_confidence=("confidence", "mean"),
                avg_lift=("lift", "mean"),
                edge_count=("source", "count"),
            )
        )

        edge_table["strength_score"] = (
            0.5 * (edge_table["value"] / edge_table["value"].max())
            + 0.25 * (edge_table["avg_confidence"] / edge_table["avg_confidence"].max())
            + 0.25 * (edge_table["avg_lift"] / edge_table["avg_lift"].max())
        )

        edge_table = edge_table.sort_values(
            ["strength_score", "value", "avg_lift"],
            ascending=False
        ).head(top_n_edges).reset_index(drop=True)

        node_names = pd.unique(edge_table[["source", "target"]].values.ravel("K")).tolist()
        node_index = {name: i for i, name in enumerate(node_names)}

        nodes = [{"name": n} for n in node_names]
        links = []
        for _, row in edge_table.iterrows():
            links.append(
                {
                    "source": node_index[row["source"]],
                    "target": node_index[row["target"]],
                    "value": float(row["value"]),
                    "source_name": row["source"],
                    "target_name": row["target"],
                    "avg_confidence": float(row["avg_confidence"]),
                    "avg_lift": float(row["avg_lift"]),
                    "edge_count": int(row["edge_count"]),
                    "strength_score": float(row["strength_score"]),
                }
            )

        sankey_data = {
            "node": {
                "label": [n["name"] for n in nodes]
            },
            "link": {
                "source": [l["source"] for l in links],
                "target": [l["target"] for l in links],
                "value": [l["value"] for l in links],
                "customdata": [
                    [
                        l["source_name"],
                        l["target_name"],
                        l["avg_confidence"],
                        l["avg_lift"],
                        l["edge_count"],
                        l["strength_score"],
                    ]
                    for l in links
                ],
            },
        }

        return {
            "nodes": nodes,
            "links": links,
            "sankey_data": sankey_data,
            "edge_table": edge_table.to_dict(orient="records"),
        }
    

    def __reprice_bundles_pricing(
        self,
        result: Dict[str, Any],
        offer_type: str = "atl"
    ) -> Dict[str, Any]:
        """
        - Reprice MBA bundles using the DynamicPricingEngine.
        """

        service_map = {
            "volume_sms": "sms",
            "volume_voice_min": "voice",
            "volume_data_mb": "data"
        }

        repriced_bundles: List[Dict[str, Any]] = []

        for bundle in result.get("bundles", []):
            # Map MBA components to pricing engine services
            target_volumes = {
                service_map[k]: v
                for k, v in bundle.get("components", {}).items()
                if k in service_map
            }

            validity_days = bundle.get("validity_days", 1)

            # Calculate new price using pricing engine
            repriced = self.pricing_engine.calculate_price_from_volume(
                target_volumes,
                validity_days,
                offer_type
            )

            repriced_bundle = {
                "name": bundle.get("name", ""),
                "components": bundle.get("components", {}),
                "validity_days": validity_days,
                "calculated_price": repriced.get("calculated_price", 0),
                "individual_prices": repriced.get("individual_prices", {}),
                "score": bundle.get("score", 0),
                "justification": bundle.get("justification", "")
            }

            repriced_bundles.append(repriced_bundle)

        return {"bundles": repriced_bundles}

