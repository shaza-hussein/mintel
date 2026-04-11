import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class MBATrainingResult:
    metrics: Dict[str, int | float | str | None]
    artifact_dir: Optional[Path] = None
