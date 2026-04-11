import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

import logging
from pathlib import Path
from typing import Optional

from pyspark.sql import DataFrame as SparkDataFrame
from pyspark.sql import SparkSession

from src.app.products.mba.config import (
    ArtifactConfig,
    MBADataConfig,
    MBAModelConfig,
    SparkConfig,
)
from src.app.products.mba.contracts import MBATrainingResult
from src.app.products.mba.pipeline import WeeklyMBAPipeline

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


def build_spark_session(config: Optional[SparkConfig] = None) -> SparkSession:
    resolved_config = config or SparkConfig()

    builder = (
        SparkSession.builder
        .appName(resolved_config.app_name)
        .config(
            "spark.driver.extraJavaOptions",
            resolved_config.driver_extra_java_options,
        )
        .config(
            "spark.executor.extraJavaOptions",
            resolved_config.executor_extra_java_options,
        )
        .config("spark.driver.memory", resolved_config.driver_memory)
    )

    if resolved_config.master:
        builder = builder.master(resolved_config.master)

    spark = builder.getOrCreate()
    logger.info("SparkSession ready | app_name=%s", resolved_config.app_name)
    return spark


def train_mba_model(
    spark: Optional[SparkSession] = None,
    data: Optional[SparkDataFrame] = None,
    table_name: Optional[str] = None,
    artifact_dir: Optional[Path] = None,
    spark_config: Optional[SparkConfig] = None,
    data_config: Optional[MBADataConfig] = None,
    model_config: Optional[MBAModelConfig] = None,
) -> MBATrainingResult:
    resolved_data_config = data_config or MBADataConfig()
    resolved_model_config = model_config or MBAModelConfig()
    resolved_spark = spark or build_spark_session(spark_config)
    resolved_table_name = table_name or resolved_data_config.source_table
    resolved_artifact_config = ArtifactConfig(
        artifact_dir=artifact_dir or ArtifactConfig().artifact_dir
    )

    logger.info(
        "Starting MBA training | source_table=%s | artifact_dir=%s",
        resolved_table_name,
        resolved_artifact_config.artifact_dir,
    )

    if data is not None:
        training_df = data
        logger.info("Using in-memory Spark dataframe for MBA training")
    else:
        training_df = resolved_spark.table(resolved_table_name)
        logger.info("Loaded training data from Spark table | table=%s", resolved_table_name)

    pipeline = WeeklyMBAPipeline(
        data_config=resolved_data_config,
        model_config=resolved_model_config,
    )
    training_result = pipeline.fit(training_df)
    pipeline.save_artifacts(resolved_artifact_config)

    training_result.artifact_dir = resolved_artifact_config.artifact_dir
    logger.info("MBA training finished successfully | metrics=%s", training_result.metrics)

    return training_result
