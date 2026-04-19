import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))

import logging
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
from src.app.products.gen.popularity.pipeline import BundlePopularityPipeline

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


def run_popularity_inference(
    pipeline_path: Path,
    data: Optional[pd.DataFrame] = None,
    input_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    input_kind: Literal["raw", "model_frame"] = "raw",
) -> pd.DataFrame:
    """
    Run bundle popularity inference from a saved pipeline.

    Args:
        pipeline_path: Path to the persisted pipeline artifact.
        data: Optional in-memory input dataframe.
        input_path: Optional path to input CSV.
        output_path: Optional CSV output path for predictions.
        input_kind: 'raw' for original schema, 'model_frame' for engineered features.

    Returns:
        DataFrame containing predictions.
    """
    logger.info(
        "Starting popularity inference | pipeline_path=%s | input_path=%s | input_kind=%s",
        pipeline_path,
        input_path,
        input_kind,
    )

    pipeline = BundlePopularityPipeline.load(pipeline_path)

    if data is not None:
        input_df = data.copy()
        logger.info("Using in-memory inference input | shape=%s", input_df.shape)
    else:
        if input_path is None:
            raise ValueError("Either 'data' or 'input_path' must be provided.")
        input_df = pd.read_csv(input_path)
        logger.info("Inference input loaded from file | shape=%s", input_df.shape)

    if input_kind == "raw":
        predictions_df = pipeline.predict_from_raw(input_df)
    else:
        predictions_df = pipeline.predict_from_model_frame(input_df)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        predictions_df.to_csv(output_path, index=False)
        logger.info("Saved inference output | path=%s", output_path)

    logger.info("Inference finished successfully | output_shape=%s", predictions_df.shape)
    return predictions_df
