import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))

from src.app.products.gen.cim.contracts import ExistingCols, GeneratedCols
import pandas as pd


class Validator:

    @staticmethod
    def validate_existing(df: pd.DataFrame):
        required = [
            ExistingCols.ID, ExistingCols.PRICE, ExistingCols.VOLUME_MB,
            ExistingCols.MINUTES, ExistingCols.SMS,
            ExistingCols.AVG_REVENUE, ExistingCols.AVG_SUBS,
            ExistingCols.POPULARITY,
        ]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"existing_df is missing columns: {missing}")

    @staticmethod
    def validate_generated(df: pd.DataFrame):
        required = [
            GeneratedCols.PRICE, GeneratedCols.VOLUME_MB,
            GeneratedCols.VOLUME_MIN, GeneratedCols.VOLUME_SMS,
            GeneratedCols.VALIDITY_DAYS, GeneratedCols.POPULARITY,
        ]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"generated_df is missing columns: {missing}")