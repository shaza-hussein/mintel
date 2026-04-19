import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../..")))


from typing import List
import pandas as pd
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

def require_columns(df: pd.DataFrame, required: List[str], context: str) -> None:
    missing = [column for column in required if column not in df.columns]
    if missing:
        logger.error("%s is missing required columns: %s", context, missing)
        raise ValueError(f"{context} is missing required columns: {missing}")
