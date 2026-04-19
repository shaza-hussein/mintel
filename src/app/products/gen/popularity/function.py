import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))


import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

class PopularityFunction:

    @staticmethod
    def norm(column: pd.Series, eps: float = 1e-9) -> pd.Series:
        transformed = np.log1p(column)
        return (transformed - transformed.min()) / (transformed.max() - transformed.min() + eps)

    def compute_popularity(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Computing popularity score | rows=%d", len(df))
        data = df.copy()

        data["R_norm"] = self.norm(data["total_rev"])
        data["U_norm"] = self.norm(data["unique_users"])
        data["rev_contribution_norm"] = self.norm(data["rev_contribution_pct"])

        beta, gamma, delta = 0.50, 0.25, 0.25
        data["popularity_score"] = (
            beta * data["R_norm"]
            + gamma * data["U_norm"]
            + delta * data["rev_contribution_norm"]
        )

        logger.info("Popularity score computed successfully")
        return data
    
    
    def build_popularity_target(self, data: pd.DataFrame) -> pd.DataFrame:
        popularity_frame = self.compute_popularity(data)
        data.loc[:, "popularity"] = popularity_frame["popularity_score"].values

        p40 = data["popularity"].quantile(0.40)
        p80 = data["popularity"].quantile(0.80)

        data["popularity_category"] = pd.cut(
            data["popularity"],
            bins=[-float("inf"), p40, p80, float("inf")],
            labels=["Unpopular", "Popular", "Very Popular"],
            include_lowest=True,
        )

        def __popularity_category(score: float) -> str:
            if score >= p80:
                return "Very Popular"
            if score >= p40:
                return "Popular"
            return "Unpopular"

        data["popularity_category"] = data["popularity"].apply(__popularity_category)

        logger.info(
            "Popularity target created | p40=%.6f | p80=%.6f | category_counts=%s",
            p40,
            p80,
            data["popularity_category"].value_counts().to_dict(),
        )
        return data
