import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

import json
import logging
from pathlib import Path
from typing import Optional
import pandas as pd

from src.app.products.popularity.config import ArtifactConfig, DataConfig, ModelConfig
from src.app.products.popularity.contracts import TrainingResult
from src.app.products.popularity.pipeline import BundlePopularityPipeline

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

def train_popularity_model(
    data: Optional[pd.DataFrame] = None,
    input_path: Optional[Path] = None,
    artifact_dir: Optional[Path] = None,
    model_config: Optional[ModelConfig] = None
) -> TrainingResult:
    """
    Train the bundle popularity model and persist artifacts.

    Args:
        input_path: CSV path for raw training data.
        artifact_dir: Directory where pipeline, metrics, and predictions will be saved.
        model_config: Optional model/training configuration override.
        configure_logger: Whether to initialize default logging.

    Returns:
        TrainingResult containing metrics, predictions, model frame, and split artifacts.
    """

    data_config = DataConfig()
    resolved_model_config = model_config or ModelConfig()
    resolved_input_path = input_path or data_config.weekly_bundles_data_path

    artifact_config = ArtifactConfig(
        artifact_dir=artifact_dir or ArtifactConfig().artifact_dir
    )

    logger.info(
        "Starting popularity training | input_path=%s | artifact_dir=%s",
        resolved_input_path,
        artifact_config.artifact_dir,
    )
    if data is not None:
        raw_df = data.copy()
    else:
        raw_df = pd.read_csv(resolved_input_path)
    logger.info("Training dataset loaded | shape=%s", raw_df.shape)

    pipeline = BundlePopularityPipeline(model_config=resolved_model_config)
    training_result = pipeline.fit(raw_df)

    artifact_config.artifact_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Artifact directory ready | path=%s", artifact_config.artifact_dir)

    pipeline.save(artifact_config.pipeline_path)

    with artifact_config.metrics_path.open("w", encoding="utf-8") as file:
        json.dump(training_result.metrics, file, indent=2)
    logger.info("Saved metrics | path=%s", artifact_config.metrics_path)

    training_result.predictions.to_csv(artifact_config.predictions_path, index=False)
    logger.info("Saved test predictions | path=%s", artifact_config.predictions_path)

    logger.info("Training finished successfully | metrics=%s", training_result.metrics)
    return training_result
