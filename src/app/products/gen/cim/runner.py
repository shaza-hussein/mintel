import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))

from src.app.products.gen.cim.model import CannibalizationModel
from src.app.products.gen.cim.config import ModelParams

import pandas as pd

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

def run_pipeline(
    existing_df: pd.DataFrame,
    generated_df: pd.DataFrame,
    params: ModelParams = None,
    top_n: int = None,
    save_csv: str = None,
    verbose: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    One-shot entry point for the full pipeline.

    Parameters
    ----------
    existing_df : pd.DataFrame
        Your live portfolio data.
    generated_df : pd.DataFrame
        CTGAN bundles, already priced and scored. Pre-filter to top 20%
        before calling this, or pass the full set and filter summary_df afterward.
    params : ModelParams, optional
    top_n : int, optional
        If set, prints the top N bundles by net revenue.
    save_csv : str, optional
        If set, saves results_df to this path.
    verbose : bool
        Print summary statistics.

    Returns
    -------
    results_df : pd.DataFrame  (long format — per bundle pair)
    summary_df : pd.DataFrame  (wide format — per new bundle, sorted best-first)
    """
    model      = CannibalizationModel(existing_df, params=params)
    results_df, summary_df = model.evaluate_portfolio(generated_df)

    if verbose:
        best  = summary_df.iloc[0]
        worst = summary_df.iloc[-1]
        logger.info(f"\n{'='*62}")
        logger.info(f"  Portfolio evaluation: {len(generated_df)} generated bundles")
        logger.info(f"  against {len(existing_df)} existing bundles")
        logger.info(f"{'─'*62}")
        logger.info(f"  Best net revenue / week  : {best['new_bundle_id']}  "
              f"→ +{best['net_revenue_weekly']:,.0f}")
        logger.info(f"  Worst net revenue / week : {worst['new_bundle_id']}  "
              f"→ {worst['net_revenue_weekly']:,.0f}")
        logger.info(f"  Avg incremental rev/wk   : {summary_df['incremental_revenue_weekly'].mean():,.0f}")
        logger.info(f"  Avg cannib % of portfolio: {summary_df['cannib_pct_of_portfolio'].mean():.2f}%")
        if top_n:
            logger.info(f"\n  Top {top_n} by net revenue (weekly):")
            cols = ["new_bundle_id","new_bundle_type","new_price",
                    "predicted_popularity","net_revenue_weekly",
                    "cannib_pct_of_portfolio","high_risk_count"]
            logger.info(summary_df[cols].head(top_n).to_string(index=False))
        logger.info(f"{'='*62}\n")

    if save_csv:
        results_df.to_csv(save_csv, index=False)
        logger.info(f"Saved: {save_csv}")

    return results_df, summary_df
