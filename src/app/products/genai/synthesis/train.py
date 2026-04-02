import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from src.app.products.genai.synthesis.config import (
    CTGANArtifactConfig,
    CTGANBundleConfig,
)
from src.app.products.genai.synthesis.contracts import CTGANTrainingResult
from src.app.products.genai.synthesis.synthesizer import BundleCTGANSynthesizer

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


def train_bundle_ctgan(
    data: Optional[pd.DataFrame] = None,
    input_path: Optional[Path] = None,
    artifact_path: Optional[Path] = None,
    config: Optional[CTGANBundleConfig] = None,
) -> tuple[BundleCTGANSynthesizer, CTGANTrainingResult]:
    """
    Train the CTGAN bundle synthesizer.

    Args:
        data: In-memory training dataframe.
        input_path: Optional CSV path if data is not passed.
        artifact_path: Optional save path for the trained synthesizer artifact.
        config: Optional CTGAN configuration.

    Returns:
        A tuple of:
        - trained BundleCTGANSynthesizer
        - CTGANTrainingResult
    """
    if data is None and input_path is None:
        raise ValueError("Either 'data' or 'input_path' must be provided.")

    if data is not None:
        training_df = data.copy()
        logger.info(
            "Starting CTGAN training | source=in_memory_dataframe | shape=%s",
            training_df.shape,
        )
    else:
        training_df = pd.read_csv(input_path)
        logger.info(
            "Starting CTGAN training | source=file | input_path=%s | shape=%s",
            input_path,
            training_df.shape,
        )

    resolved_config = config or CTGANBundleConfig()
    synthesizer = BundleCTGANSynthesizer(config=resolved_config)

    training_result = synthesizer.fit(training_df)

    resolved_artifact_path = artifact_path or CTGANArtifactConfig().artifact_path
    resolved_artifact_path.parent.mkdir(parents=True, exist_ok=True)
    synthesizer.save(resolved_artifact_path)

    logger.info(
        "CTGAN training finished | artifact_path=%s | segments=%d",
        resolved_artifact_path,
        len(training_result.segment_summary),
    )

    return synthesizer, training_result
