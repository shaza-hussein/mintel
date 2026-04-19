import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../..")))

import logging
from pathlib import Path
from typing import Dict, Optional

import joblib
import numpy as np
import pandas as pd
from ctgan import CTGAN

from src.app.products.gen.genai.synthesis.config import CTGANBundleConfig
from src.app.products.gen.genai.synthesis.constraints import (
    enforce_business_constraints,
    final_cleanup_and_reprice,
)
from src.app.products.gen.genai.synthesis.contracts import (
    CTGANGenerationResult,
    CTGANTrainingResult,
    SegmentTrainingInfo,
)

logger = logging.getLogger(__name__)


class BundleCTGANSynthesizer:
    def __init__(self, config: Optional[CTGANBundleConfig] = None) -> None:
        self.config = config or CTGANBundleConfig()
        self.ctgan_models_: Dict[str, CTGAN] = {}
        self.fallback_segments_: Dict[str, pd.DataFrame] = {}
        self.training_reference_: Optional[pd.DataFrame] = None
        self.segment_summary_: list[SegmentTrainingInfo] = []
        self.is_fitted_: bool = False

    def fit(self, df_model: pd.DataFrame) -> CTGANTrainingResult:
        training_frame = self._prepare_training_frame(df_model)
        self.training_reference_ = training_frame.copy()

        self.ctgan_models_.clear()
        self.fallback_segments_.clear()
        self.segment_summary_.clear()

        segments = {
            bundle_type: group.reset_index(drop=True)
            for bundle_type, group in training_frame.groupby("bundle_type")
        }

        logger.info("Segments found:")
        for bundle_type, segment_df in segments.items():
            logger.info("  %s: %d rows", bundle_type, len(segment_df))

        for bundle_type, segment_df in segments.items():
            row_count = len(segment_df)

            logger.info("%s", "─" * 50)
            logger.info("Processing: %s (%d rows)", bundle_type, row_count)

            if row_count < self.config.min_rows_for_ctgan:
                logger.warning(
                    "Too few rows for CTGAN (%d < %d). Using bootstrap resampling.",
                    row_count,
                    self.config.min_rows_for_ctgan,
                )
                self.fallback_segments_[bundle_type] = segment_df
                self.segment_summary_.append(
                    SegmentTrainingInfo(
                        bundle_type=bundle_type,
                        row_count=row_count,
                        strategy="bootstrap",
                    )
                )
                continue

            encoded_df = self._encode_sparse_flags(segment_df)
            fit_df = encoded_df.drop(columns=["bundle_type"])

            batch_size = self._resolve_batch_size(len(fit_df))
            logger.info("batch_size set to %d", batch_size)

            model = CTGAN(
                epochs=self.config.epochs,
                batch_size=batch_size,
                generator_dim=self.config.generator_dim,
                discriminator_dim=self.config.discriminator_dim,
                verbose=True,
            )
            model.fit(fit_df, list(self.config.discrete_columns))
            self.ctgan_models_[bundle_type] = model

            self.segment_summary_.append(
                SegmentTrainingInfo(
                    bundle_type=bundle_type,
                    row_count=row_count,
                    strategy="ctgan",
                    batch_size=batch_size,
                )
            )
            logger.info("Finished training: %s", bundle_type)

        self.is_fitted_ = True

        return CTGANTrainingResult(
            segment_summary=self.segment_summary_.copy(),
            modeled_columns=list(self.config.model_columns),
            training_frame_shape=training_frame.shape,
        )

    def generate(
        self,
        samples_per_type: Optional[int] = None,
        apply_constraints: bool = True,
        apply_final_cleanup: bool = True,
    ) -> CTGANGenerationResult:
        self._ensure_fitted()

        n_samples = samples_per_type or self.config.default_samples_per_type
        all_frames: list[pd.DataFrame] = []
        generated_counts: Dict[str, int] = {}

        for bundle_type in self.ctgan_models_:
            raw_sample = self._sample_ctgan(bundle_type, n_samples)
            clean_sample = (
                enforce_business_constraints(raw_sample, self.config)
                if apply_constraints
                else raw_sample
            )
            all_frames.append(clean_sample)
            generated_counts[bundle_type] = len(clean_sample)
            logger.info(
                "[CTGAN] %s: %d/%d valid",
                bundle_type,
                len(clean_sample),
                n_samples,
            )

        for bundle_type in self.fallback_segments_:
            raw_sample = self._sample_bootstrap(bundle_type, n_samples)
            clean_sample = (
                enforce_business_constraints(raw_sample, self.config)
                if apply_constraints
                else raw_sample
            )
            all_frames.append(clean_sample)
            generated_counts[bundle_type] = len(clean_sample)
            logger.info(
                "[Bootstrap] %s: %d/%d valid",
                bundle_type,
                len(clean_sample),
                n_samples,
            )

        if not all_frames:
            raise RuntimeError("No segment models are available for generation.")

        synthetic_data = pd.concat(all_frames, ignore_index=True)
        synthetic_data = synthetic_data.loc[:, list(self.config.model_columns)]

        if apply_final_cleanup:
            synthetic_data = final_cleanup_and_reprice(
                df=synthetic_data,
                real_data=self.training_reference_,
                config=self.config,
            )

        logger.info("Generated %d synthetic bundles", len(synthetic_data))

        return CTGANGenerationResult(
            synthetic_data=synthetic_data.reset_index(drop=True),
            generated_counts=generated_counts,
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: Path) -> "BundleCTGANSynthesizer":
        loaded = joblib.load(path)
        if not isinstance(loaded, cls):
            raise TypeError("Loaded artifact is not a BundleCTGANSynthesizer.")
        return loaded

    def _prepare_training_frame(self, df_model: pd.DataFrame) -> pd.DataFrame:
        missing_columns = [
            column for column in self.config.model_columns
            if column not in df_model.columns
        ]
        if missing_columns:
            raise ValueError(f"Missing required CTGAN columns: {missing_columns}")

        data = df_model.loc[:, list(self.config.model_columns)].copy()

        data["bundle_type"] = data["bundle_type"].where(data["bundle_type"].notna(), None)
        data = data.dropna(subset=["bundle_type"]).copy()
        data["bundle_type"] = data["bundle_type"].astype(str).str.strip()
        data = data[
            data["bundle_type"].ne("")
            & data["bundle_type"].str.lower().ne("nan")
        ].reset_index(drop=True)

        data["usage_type"] = data["usage_type"].fillna("unknown").astype(str).str.strip()
        data["service_class_category"] = (
            data["service_class_category"].fillna("unknown").astype(str).str.strip()
        )

        numeric_cols = ["price", "volume_mb", "volume_min", "volume_sms", "validity_hours"]
        for column in numeric_cols:
            data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0)

        return data.reset_index(drop=True)

    def _encode_sparse_flags(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        for column in self.config.sparse_columns:
            data[f"has_{column}"] = (data[column] > 0).astype(int)
            data[column] = data[column].clip(lower=0)
        return data

    def _decode_sparse_flags(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        for column in self.config.sparse_columns:
            flag_column = f"has_{column}"
            if flag_column in data.columns:
                data[column] = data[column].abs() * data[flag_column]
                data = data.drop(columns=[flag_column])
        return data

    def _resolve_batch_size(self, row_count: int) -> int:
        raw_batch_size = min(self.config.max_batch_size, row_count)
        batch_size = (raw_batch_size // self.config.pac) * self.config.pac
        return max(batch_size, self.config.pac)

    def _sample_ctgan(self, bundle_type: str, n: int) -> pd.DataFrame:
        raw = self.ctgan_models_[bundle_type].sample(n)
        raw["bundle_type"] = bundle_type
        return self._decode_sparse_flags(raw)

    def _sample_bootstrap(self, bundle_type: str, n: int) -> pd.DataFrame:
        rng = np.random.default_rng(self.config.random_seed)
        source_df = self.fallback_segments_[bundle_type]

        sampled = source_df.sample(
            n=n,
            replace=True,
            random_state=self.config.random_seed,
        ).reset_index(drop=True)

        for column in ["price", "volume_mb", "volume_min", "volume_sms", "validity_hours"]:
            std = sampled[column].std()
            if pd.notna(std) and std > 0:
                noise = rng.normal(
                    0,
                    std * self.config.bootstrap_noise_pct,
                    size=len(sampled),
                )
                sampled[column] = (sampled[column] + noise).clip(lower=0)

        return sampled

    def _ensure_fitted(self) -> None:
        if not self.is_fitted_:
            raise RuntimeError("BundleCTGANSynthesizer must be fitted before generation.")
