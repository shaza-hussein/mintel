import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from dataclasses import replace
from datetime import datetime
from typing import Optional
import pandas as pd

from src.app.products.gen.genai.synthesis.generate import generate_synthetic_bundles
from src.app.products.gen.genai.synthesis.config import CTGANArtifactConfig, CTGANBundleConfig
from src.app.products.gen.genai.synthesis.synthesizer import BundleCTGANSynthesizer
from src.app.products.gen.popularity.pipeline import BundlePopularityPipeline
from src.app.products.gen.popularity.config import ArtifactConfig
from src.app.products.gen.genai.synthesis.constraints import volume_contraints
from src.app.products.gen.popularity.preprocessing.raw_bundle_preprocessor import RawBundlePreprocessor
from src.app.products.gen.config import DataConfig, BundleGenerationConfig
from src.app.products.gen.popularity.function import PopularityFunction
from src.app.products.gen.cim.runner import run_pipeline
from src.app.products.gen.cim.config import ModelParams

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

class BundlesGenerator:

    def __init__(
        self,
        dataConfig: Optional[DataConfig] = None,
        generationConfig: Optional[BundleGenerationConfig] = None,
    ):
        self.raw_preprocessor = RawBundlePreprocessor()
        self.dataConfig = dataConfig or DataConfig()
        self.generationConfig = generationConfig or BundleGenerationConfig()
        self.popularity = PopularityFunction()

    def generate(
        self,
        top_n: Optional[int] = None,
        generation_config: Optional[BundleGenerationConfig] = None,
    ):
        active_generation_config = generation_config or self.generationConfig
        resolved_top_n = (
            top_n
            if top_n is not None
            else active_generation_config.top_n_per_bundle_type
        )

        generated = self.__generate_products(active_generation_config)
        existing = self.__exiting_products()

        _, summary_df = run_pipeline(
            existing_df=existing,
            generated_df=generated,
            params=ModelParams(),
            top_n=10,
            verbose=True,
        )

        top_per_type = self.__top_n_per_bundle_type(summary_df, n=resolved_top_n)

        return top_per_type, summary_df, generated

    def __top_n_per_bundle_type(
        self,
        summary_df: pd.DataFrame,
        n: int = 5,
        sort_by: str = "net_revenue_weekly"
    ) -> pd.DataFrame:
        ascending = sort_by == "cannib_pct_of_portfolio"
        df = summary_df.sort_values(sort_by, ascending=ascending)
        top_df = (
            df
            .groupby("new_bundle_type", group_keys=False)
            .head(n)
            .reset_index(drop=True)
        )

        return top_df

    def __current_date(self):
        now = datetime.now()
        year, week, _ = now.isocalendar()
        return (year, week)

    def __load_synthesizer(
        self,
        generation_config: BundleGenerationConfig,
    ) -> BundleCTGANSynthesizer:
        synthesizer = BundleCTGANSynthesizer.load(CTGANArtifactConfig().artifact_path)

        base_config = getattr(synthesizer, "config", None) or CTGANBundleConfig()
        synthesizer.config = replace(
            base_config,
            default_offer_type=generation_config.normalized_offer_type(),
            default_samples_per_type=generation_config.samples_per_type,
            validity_options=generation_config.validity_options,
            max_volume_mb=generation_config.max_volume_mb,
            max_volume_min=generation_config.max_volume_min,
            max_volume_sms=generation_config.max_volume_sms,
        )

        return synthesizer

    def __exiting_products(self) -> pd.DataFrame:
        data = pd.read_csv(self.dataConfig.weekly_bundles_data_path)
        data = data[~data['configured_volume'].isna()]
        data = data[~data["bundle_name"].str.contains("DIY", case=False, na=False)]

        volume_extracted = data['configured_volume'].apply(
            self.raw_preprocessor.extract_conf_volume_values
        )
        data['volume_mb'] = volume_extracted.apply(lambda x: x['mb'] if x['mb'] is not None else 0.0)
        data['minutes'] = volume_extracted.apply(lambda x: x['min'] if x['min'] is not None else 0.0)
        data['sms'] = volume_extracted.apply(lambda x: x['sms'] if x['sms'] is not None else 0.0)
        data.drop(columns=['configured_volume'], inplace=True)

        data = self.raw_preprocessor.build_input_features_of_target(data)

        data["price"] = data["price"].apply(
            self.raw_preprocessor.clean_price
        )

        data_pop = self.popularity.compute_popularity(data)
        data.loc[:, 'popularity'] = data_pop['popularity_score'].values
        del data_pop

        existing = data.groupby("bundle_id").agg(
            bundle_name=("bundle_name", "first"),
            price=("price", "first"),
            volume_mb=("volume_mb", "max"),
            bundle_type=("bundle_type", "first"),
            minutes=("minutes", "max"),
            sms=("sms", "max"),
            avg_weekly_revenue=("total_rev", "mean"),
            avg_weekly_subs=("total_subscriptions", "mean"),
            popularity_score=("popularity", "max")
        ).reset_index()
        existing["price"] = existing["price"].astype(float)
        del data

        return existing

    def __generate_products(
        self,
        generation_config: BundleGenerationConfig,
    ) -> pd.DataFrame:
        synthesizer = self.__load_synthesizer(generation_config)

        gen_result = generate_synthetic_bundles(
            synthesizer=synthesizer,
            samples_per_type=generation_config.samples_per_type,
        )
        synthetic_data = gen_result.synthetic_data

        pop = BundlePopularityPipeline()
        Pmodel = pop.load(path=ArtifactConfig().pipeline_path)

        year, week = self.__current_date()
        new_products_scored = self.__predict_populaity_of_generated_bundles(
            products_df=synthetic_data,
            model=Pmodel,
            year=year,
            week=week,
        )

        allowed_categories = tuple(
            category for category in generation_config.popularity_categories
            if str(category).strip()
        ) or ("Very Popular",)

        filtered_bundles = new_products_scored[
            new_products_scored["popularity_category"].isin(allowed_categories)
        ].reset_index(drop=True)

        allowed_bundle_types = generation_config.normalized_bundle_types()
        if allowed_bundle_types:
            filtered_bundles = filtered_bundles[
                filtered_bundles["bundle_type"].isin(allowed_bundle_types)
            ].reset_index(drop=True)

        if filtered_bundles.empty:
            raise ValueError(
                "No generated bundles matched the selected filters. "
                "Try changing offer_type, bundle_type, or popularity_categories."
            )

        unique_top_bundles = (
            filtered_bundles
            .drop_duplicates()
            .reset_index(drop=True)
        )

        generated = volume_contraints(unique_top_bundles.copy(), config=synthesizer.config)
        if generated.empty:
            raise ValueError(
                "All generated bundles were removed by volume constraints. "
                "Try relaxing max volumes or allowed bundle types."
            )

        generated["validity_hours"] = pd.to_numeric(
            generated["validity_hours"],
            errors="coerce"
        ).fillna(0)
        generated["validity_days"] = generated["validity_hours"] / 24.0

        generated = generated.reset_index(drop=True)
        generated['bundle_id'] = generated.index + 1
        
        return generated

    def __predict_populaity_of_generated_bundles(
        self,
        products_df: pd.DataFrame,
        model: BundlePopularityPipeline,
        year: int,
        week: int,
    ) -> pd.DataFrame:
        df = products_df.copy()
        df["week_number"] = week
        df["year_number"] = year

        if "bundle_name" not in df.columns:
            df["bundle_name"] = ""

        if "is_illimite" not in df.columns:
            df["is_illimite"] = 0

        df["configured_volume_mb"] = pd.to_numeric(
            df.get("configured_volume_mb", df.get("volume_mb", 0)),
            errors="coerce",
        ).fillna(0.0)

        df["configured_volume_min"] = pd.to_numeric(
            df.get("configured_volume_min", df.get("volume_min", 0)),
            errors="coerce",
        ).fillna(0.0)

        df["configured_volume_sms"] = pd.to_numeric(
            df.get("configured_volume_sms", df.get("volume_sms", 0)),
            errors="coerce",
        ).fillna(0.0)

        if "season" not in df.columns:
            df["season"] = df["week_number"].apply(self.raw_preprocessor.week_to_season)

        feature_engineer = model.feature_engineer
        model_frame, _ = feature_engineer.prepare_inference_frame(df)

        pred_df = model.predict_from_model_frame(model_frame)

        df["predicted_popularity"] = pred_df["predicted_popularity"].values

        p40 = df["predicted_popularity"].quantile(0.40)
        p80 = df["predicted_popularity"].quantile(0.80)

        def popularity_category(score):
            if score >= p80:
                return "Very Popular"
            elif score >= p40:
                return "Popular"
            else:
                return "Unpopular"

        df["popularity_category"] = df["predicted_popularity"].apply(popularity_category)

        return df
