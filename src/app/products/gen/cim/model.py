import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))

from src.app.products.gen.cim.config import ModelParams
from src.app.products.gen.cim.contracts import ExistingCols, GeneratedCols
from src.app.products.gen.cim.validator import Validator
from src.app.products.gen.cim.features import (
      extract_existing_features, extract_generated_features,
      compute_portfolio_maxima, normalize_features
)

import math
import pandas as pd
import warnings

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


class CannibalizationModel:

    def __init__(self, existing_df: pd.DataFrame, params: ModelParams = None):
            Validator.validate_existing(existing_df)
            self.existing   = existing_df.copy().reset_index(drop=True)
            self.params     = params or ModelParams()
            self._maxima    = compute_portfolio_maxima(existing=self.existing,
                                                       params=self.params)
            logger.info("CannibalizationModel init.")

    def _weighted_cosine(self, vec_a: dict, vec_b: dict) -> float:
        w    = self.params.feature_weights
        keys = list(w.keys())
        dot   = sum(w[k] * vec_a.get(k,0) * vec_b.get(k,0) for k in keys)
        norm_a = math.sqrt(sum((w[k] * vec_a.get(k,0))**2 for k in keys))
        norm_b = math.sqrt(sum((w[k] * vec_b.get(k,0))**2 for k in keys))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _utility(self, popularity: float, price: float) -> float:
        """Logit-style value: (popularity / price) ^ elasticity."""
        if price <= 0:
            return 0.0
        return (max(popularity, 1e-9) / price) ** self.params.price_elasticity

    def _cannibalization_rate(
        self,
        similarity: float,
        new_utility: float,
        existing_utility: float,
    ) -> float:
        """
        Fraction of existing bundle revenue stolen.

        Formula
        -------
        If similarity < threshold  →  0
        Else:
            advantage = max(0, (new_utility - existing_utility) / existing_utility)
            rate = sensitivity × similarity × min(advantage × 0.5, cap)
        Result clamped to [0, cannib_cap].
        """
        if similarity < self.params.similarity_threshold:
            return 0.0
        if existing_utility <= 0:
            adv = 1.0
        else:
            adv = max(0.0, (new_utility - existing_utility) / existing_utility)
        raw = self.params.cannib_sensitivity * similarity * min(adv * 0.5, self.params.cannib_cap)
        return min(raw, self.params.cannib_cap)

    @staticmethod
    def _risk_tier(rate: float) -> str:
        if rate > 0.10: return "high"
        if rate > 0.05: return "medium"
        if rate > 0.00: return "low"
        return "none"


    def evaluate_one(
        self,
        new_bundle_row: pd.Series,
        expected_new_market_pct: float = None,
    ) -> tuple[pd.DataFrame, dict]:
        """
        - Evaluate one generated bundle against the full existing portfolio.
        """
        new_pct  = expected_new_market_pct or self.params.expected_new_market_pct
        new_fv   = extract_generated_features(new_bundle_row)
        new_pop  = float(new_bundle_row[GeneratedCols.POPULARITY])
        new_price= float(new_bundle_row[GeneratedCols.PRICE])
        new_util = self._utility(new_pop, new_price)
        new_type = str(new_bundle_row.get(GeneratedCols.BUNDLE_TYPE, ""))

        vec_new = normalize_features(params=self.params, maxima=self._maxima,fv=new_fv,new_bundle_fv= new_fv)

        rows = []
        for _, ex_row in self.existing.iterrows():
            ex_fv   = extract_existing_features(ex_row)
            vec_ex  = normalize_features(params=self.params, maxima=self._maxima,fv=ex_fv, new_bundle_fv=new_fv)
            sim     = self._weighted_cosine(vec_new, vec_ex)

            # Apply bundle_type gate: BUNDLE_DATA vs BUNDLE_VOICE are weaker substitutes
            ex_type = str(ex_row.get(ExistingCols.BUNDLE_TYPE, ""))
            if new_type and ex_type and new_type != ex_type:
                sim *= 0.4   # cross-type substitution is weaker

            ex_pop  = float(ex_row[ExistingCols.POPULARITY])
            ex_price= float(ex_row[ExistingCols.PRICE])
            ex_util = self._utility(ex_pop, ex_price)
            c_rate  = self._cannibalization_rate(sim, new_util, ex_util)

            ex_rev  = float(ex_row[ExistingCols.AVG_REVENUE])
            ex_subs = float(ex_row[ExistingCols.AVG_SUBS])

            rows.append({
                "existing_bundle_id":     ex_row[ExistingCols.ID],
                "existing_bundle_name":   ex_row.get(ExistingCols.NAME, ""),
                "existing_bundle_type":   ex_type,
                "existing_price":         ex_price,
                "existing_volume_gb":     round(ex_row[ExistingCols.VOLUME_MB] / 1000, 2),
                "existing_minutes":       ex_row[ExistingCols.MINUTES],
                "existing_sms":           ex_row[ExistingCols.SMS],
                "existing_avg_rev_weekly": ex_rev,
                "existing_avg_subs_weekly": ex_subs,
                "similarity":             round(sim, 4),
                "cannib_rate":            round(c_rate, 6),
                "cannib_rate_pct":        round(c_rate * 100, 3),
                "delta_revenue_weekly":   round(-ex_rev  * c_rate, 2),
                "delta_revenue_monthly":  round(-ex_rev  * c_rate * 4.33, 2),
                "delta_subs_weekly":      round(-ex_subs * c_rate, 4),
                "risk_tier":              self._risk_tier(c_rate),
            })

        impact_df = pd.DataFrame(rows).sort_values("delta_revenue_weekly")

        # Portfolio aggregates 
        total_existing_subs = float(self.existing[ExistingCols.AVG_SUBS].sum())
        total_existing_rev  = float(self.existing[ExistingCols.AVG_REVENUE].sum())

        new_subs_weekly    = total_existing_subs * (new_pct / 100) * (1 + self.params.growth_rate)
        incr_rev_weekly    = new_subs_weekly * new_price
        total_cannib_rev   = float(impact_df["delta_revenue_weekly"].sum())
        total_cannib_subs  = float(impact_df["delta_subs_weekly"].sum())
        net_rev_weekly     = incr_rev_weekly + total_cannib_rev
        net_subs_weekly    = new_subs_weekly + total_cannib_subs

        cannib_pct = abs(total_cannib_rev) / total_existing_rev * 100 if total_existing_rev > 0 else 0
        most_hit   = impact_df.iloc[0]

        kpis = {
            "new_bundle_id":                new_bundle_row.get(GeneratedCols.ID, ""),
            "new_bundle_type":              new_type,
            "new_price":                    new_price,
            "new_volume_mb":                new_fv["volume_mb"],
            "new_volume_min":               new_fv["minutes"],
            "new_volume_sms":               new_fv["sms"],
            "new_validity_days":            new_fv["validity_days"],
            "new_validity_bucket":          new_bundle_row.get(GeneratedCols.VALIDITY_BUCKET, ""),
            "predicted_popularity":         round(new_pop, 4),
            "popularity_category":          new_bundle_row.get(GeneratedCols.POP_CATEGORY, ""),
            "incremental_revenue_weekly":   round(incr_rev_weekly, 2),
            "incremental_subs_weekly":      round(new_subs_weekly, 2),
            "total_cannib_revenue_weekly":  round(total_cannib_rev, 2),
            "total_cannib_subs_weekly":     round(total_cannib_subs, 4),
            "net_revenue_weekly":           round(net_rev_weekly, 2),
            "net_revenue_monthly":          round(net_rev_weekly * 4.33, 2),
            "net_subs_weekly":              round(net_subs_weekly, 4),
            "cannib_pct_of_portfolio":      round(cannib_pct, 3),
            "most_cannibalized_bundle_id":  most_hit["existing_bundle_id"],
            "most_cannibalized_bundle_name":most_hit["existing_bundle_name"],
            "most_cannibalized_delta_rev":  most_hit["delta_revenue_weekly"],
            "high_risk_count":    int((impact_df["risk_tier"] == "high").sum()),
            "medium_risk_count":  int((impact_df["risk_tier"] == "medium").sum()),
            "safe_bundle_count":  int((impact_df["risk_tier"] == "none").sum()),
        }

        return impact_df, kpis

    def evaluate_portfolio(
        self,
        generated_df: pd.DataFrame,
        expected_new_market_pct: float = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        - Evaluate all generated bundles against the existing portfolio.
        """
        Validator.validate_generated(generated_df)

        all_impact_rows = []
        all_kpis        = []

        for idx, row in generated_df.iterrows():
            try:
                impact_df, kpis = self.evaluate_one(row, expected_new_market_pct)
                impact_df.insert(0, "_new_bundle_idx", idx)
                for k, v in kpis.items():
                    impact_df[k] = v
                all_impact_rows.append(impact_df)
                all_kpis.append(kpis)
            except Exception as e:
                warnings.warn(f"Skipped row {idx}: {e}")

        if not all_impact_rows:
            raise RuntimeError("No bundles could be evaluated. Check your column names.")

        results_df = pd.concat(all_impact_rows, ignore_index=True)
        summary_df = pd.DataFrame(all_kpis).sort_values(
            "net_revenue_weekly", ascending=False
        ).reset_index(drop=True)

        return results_df, summary_df

    def top_n(
        self,
        generated_df: pd.DataFrame,
        n: int = 20,
        sort_by: str = "net_revenue_weekly",
    ) -> pd.DataFrame:
        """
        Convenience: evaluate all generated bundles and return top N by sort_by.

        Parameters
        ----------
        n : int
            Number of top bundles to return.
        sort_by : str
            Column in summary_df to rank by. Options include:
            'net_revenue_weekly', 'incremental_revenue_weekly',
            'cannib_pct_of_portfolio' (ascending for least harmful).

        Returns
        -------
        pd.DataFrame — summary table of top N bundles.
        """
        _, summary_df = self.evaluate_portfolio(generated_df)
        ascending = sort_by == "cannib_pct_of_portfolio"
        return summary_df.sort_values(sort_by, ascending=ascending).head(n)

    def cannibalization_matrix(self, generated_df: pd.DataFrame) -> pd.DataFrame:
        """
        Returns a matrix of shape (len(generated_df), len(existing_df))
        where cell [i, j] = cannibalization rate of generated bundle i on existing bundle j.
        Useful for heatmap visualization.
        """
        Validator.validate_generated(generated_df)
        rows = []
        for idx, row in generated_df.iterrows():
            impact_df, _ = self.evaluate_one(row)
            r = {"new_bundle_idx": idx}
            for _, ex in impact_df.iterrows():
                r[ex["existing_bundle_id"]] = round(ex["cannib_rate_pct"], 3)
            rows.append(r)
        return pd.DataFrame(rows).set_index("new_bundle_idx")

    def update_params(self, **kwargs) -> None:
        """
        Update parameters in-place and recompute maxima.

        >>> model.update_params(cannib_sensitivity=0.7, price_elasticity=2.0)
        """
        for k, v in kwargs.items():
            if not hasattr(self.params, k):
                raise ValueError(f"Unknown parameter: {k!r}")
            setattr(self.params, k, v)
        self._maxima =  compute_portfolio_maxima(existing=self.existing,
                                                       params=self.params)

    
        