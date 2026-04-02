import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))

from pathlib import Path
from typing import Optional

from src.app.products.genai.synthesis.config import CTGANArtifactConfig
from src.app.products.genai.synthesis.contracts import CTGANGenerationResult
from src.app.products.genai.synthesis.synthesizer import BundleCTGANSynthesizer

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)



def generate_synthetic_bundles(
    synthesizer: Optional[BundleCTGANSynthesizer] = None,
    artifact_path: Optional[Path] = None,
    samples_per_type: int = 500,
    output_path: Optional[Path] = None,
) -> CTGANGenerationResult:
    resolved_synthesizer = synthesizer
    if resolved_synthesizer is None:
        resolved_artifact_path = artifact_path or CTGANArtifactConfig().artifact_path
        resolved_synthesizer = BundleCTGANSynthesizer.load(resolved_artifact_path)

    generation_result = resolved_synthesizer.generate(
        samples_per_type=samples_per_type,
        apply_constraints=True,
        apply_final_cleanup=True,
    )

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        generation_result.synthetic_data.to_csv(output_path, index=False)

    logger.info(
        "Synthetic bundle generation finished | rows=%d",
        len(generation_result.synthetic_data),
    )
    return generation_result
