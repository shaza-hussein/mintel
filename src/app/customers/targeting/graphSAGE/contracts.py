import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class GraphBuildResult:
    graph_dir: Path
    metrics: Dict


@dataclass
class GraphSAGETrainingResult:
    artifact_dir: Path
    metrics: Dict
    best_model_path: Optional[Path] = None