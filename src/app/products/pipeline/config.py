import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class ArtifactConfig:
    artifact_dir: Path = PROJECT_ROOT / "_models"