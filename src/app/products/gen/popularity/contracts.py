import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))


from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd


@dataclass
class TrainTestData:
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series


@dataclass
class EvaluationResult:
    metrics: Dict[str, Optional[float]]
    predictions: Optional[pd.DataFrame] = None


@dataclass
class TrainingResult:
    metrics: Dict[str, Optional[float]]
    predictions: pd.DataFrame
    df_model: pd.DataFrame
    feature_engineering_cols: List[str]
    model_feature_cols: List[str]
    split: TrainTestData
