import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))


from dataclasses import dataclass
from typing import Dict, List

import pandas as pd


@dataclass
class SegmentTrainingInfo:
    bundle_type: str
    row_count: int
    strategy: str
    batch_size: int | None = None


@dataclass
class CTGANTrainingResult:
    segment_summary: List[SegmentTrainingInfo]
    modeled_columns: List[str]
    training_frame_shape: tuple[int, int]


@dataclass
class CTGANGenerationResult:
    synthetic_data: pd.DataFrame
    generated_counts: Dict[str, int]
