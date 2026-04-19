import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

import pandas as pd
from pyspark.sql import SparkSession
from src.app.products.pipeline.config import ArtifactConfig
from src.app.products.gen.popularity.train import train_popularity_model
from src.app.products.gen.genai.synthesis.train import train_bundle_ctgan
from src.app.products.mba.train import train_mba_model
from src.app.products.mba.train import train_mba_model


import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


class ProductModelsTrainer:

    def __init__(self):
        self.config = ArtifactConfig()


    def train_popularity(self, data: pd.DataFrame) -> pd.DataFrame:
        if data is None:
            raise ValueError(
                f"Input data is required"
            )
        logger.info("\033[92mStarted Training Popularity Model\033[0m")

        try:
            result = train_popularity_model(data=data)
        except Exception as e:
            logger.exception(e)

        logger.info("\033[95mFinished Training Popularity Model\033[0m")
        return result.df_model
        


    def train_synthesizer(self, data: pd.DataFrame):
        if data is None:
            raise ValueError(
                f"Input data is required"
            )
        logger.info("\033[92mStarted Training CTGAN Model\033[0m")
        try:
            train_bundle_ctgan(data=data)
        except Exception as e:
            logger.exception(e)

        logger.info("\033[95mFinished Training CTGAN Model\033[0m")



    def train_mba(self, spark: SparkSession,data: pd.DataFrame):
        if data is None:
            raise ValueError(
                f"Input data is required"
            )
        logger.info("\033[92mStarted Training FP-Growth (MBA) Model\033[0m")

        try: 
            train_mba_model(
                spark=spark,
                data=data,
            )
        except Exception as e:
            logger.exception(e)

        logger.info("\033[95mFinished Training FP-Growth (MBA) Model\033[0m")