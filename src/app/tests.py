import pandas as pd
# TODO-1-: Testing Training and Inference of Popularity Model.
# Training
from products.popularity.train import train_popularity_model
print("\033[92mStarted Training Popularity Model\033[0m")
#data = pd.read_csv(r"..\..\..\datasets\weekly_base_bundles_info_202501_202510.csv")
#print(data.shape)
#result = train_popularity_model(data=data)
print("\033[92mFinished Training Popularity Model\033[0m") 

# Inference
from products.popularity.inference import run_popularity_inference
from products.popularity.config import ArtifactConfig
# data = None #? this will come from generated bundles
#predictions = run_popularity_inference(
#    pipeline_path=ArtifactConfig().pipeline_path,
#    data=data
#)
#print(predictions)

# TODO-2-: Training And Testing GANs 
from products.genai.synthesis.train import train_bundle_ctgan
from products.popularity.pipeline import BundlePopularityPipeline
from products.popularity.constants import MODEL_BASE_FEATURE_COLUMNS


print("\033[92mStarted Training CTGAN Model\033[0m")
#synthesizer, resultGAN = train_bundle_ctgan(data=result.df_model.copy())
#print(resultGAN)
print("\033[92mFinished Training CTGAN Model\033[0m")
print("\033[92mGenerate Data using CTGAN Model\033[0m")
#generation_result = synthesizer.generate(
#    samples_per_type=500,
#    apply_constraints=True,
#    apply_final_cleanup=True,
#)

#ynthetic_data_clean = generation_result.synthetic_data
#print(synthetic_data_clean)
import numpy as np
import pandas as pd
from products.genai.synthesis.generate import generate_synthetic_bundles

# gen_res = generate_synthetic_bundles()

def prepare_products_for_inference2(
    products_df,
    model,
    model_features=None,
    year=2025,
    week=1
):
    import numpy as np
    import pandas as pd

    df = products_df.copy()

    # 1. BASIC CLEANING
    df.columns = [c.strip() for c in df.columns]

    df["usage_type"] = df["usage_type"].fillna("unknown")
    df["service_class_category"] = df["service_class_category"].fillna("unknown")
    df["bundle_type"] = df["bundle_type"].fillna("unknown")

    # 2. PRICE
    def clean_price(val):
        if pd.isna(val):
            return None
        val = str(val).replace("F", "").replace(",", "")
        try:
            return float(val)
        except Exception:
            return None

    df["price"] = df["price"].apply(clean_price).fillna(0.0)

    # 3. VALIDITY
    df["validity_days"] = df["validity_hours"] / 24.0

    # 4. TIME FEATURES
    df["week_number"] = week
    df["year_number"] = year
    df["week_sin"] = np.sin(2 * np.pi * week / 52)
    df["week_cos"] = np.cos(2 * np.pi * week / 52)

    def week_to_season(w):
        if w <= 13:
            return "winter"
        elif w <= 26:
            return "spring"
        elif w <= 39:
            return "summer"
        else:
            return "autumn"

    df["season"] = week_to_season(week)

    # 5. STRUCTURAL FLAGS
    df["has_data"] = (df["volume_mb"] > 0).astype(int)
    df["has_voice"] = (df["volume_min"] > 0).astype(int)
    df["has_sms"] = (df["volume_sms"] > 0).astype(int)

    df["is_data_only"] = ((df["has_data"] == 1) & (df["has_voice"] == 0)).astype(int)
    df["is_voice_only"] = ((df["has_voice"] == 1) & (df["has_data"] == 0)).astype(int)
    df["is_sms_only"] = ((df["has_sms"] == 1) & (df["has_data"] == 0)).astype(int)
    df["is_combo_bundle"] = ((df[["has_data", "has_voice", "has_sms"]].sum(axis=1)) >= 2).astype(int)
    df["is_unlimited_bundle"] = 0

    # if missing in synthetic data
    if "name_has_social" not in df.columns:
        df["name_has_social"] = 0
    if "name_has_roaming" not in df.columns:
        df["name_has_roaming"] = 0

    # 6. LOG FEATURES
    df["log_price"] = np.log1p(df["price"].clip(lower=0))
    df["log_mb"] = np.log1p(df["volume_mb"].clip(lower=0))
    df["log_min"] = np.log1p(df["volume_min"].clip(lower=0))
    df["log_sms"] = np.log1p(df["volume_sms"].clip(lower=0))
    df["log_validity_hours"] = np.log1p(df["validity_hours"].clip(lower=0))

    # 7. VALIDITY BUCKET
    df["validity_bucket"] = np.select(
        [
            df["validity_days"] <= 1,
            df["validity_days"] <= 7,
            df["validity_days"] <= 30,
            df["validity_days"] > 30
        ],
        ["daily", "weekly", "monthly", "long_term"],
        default="unknown"
    )

    # 8. FEATURE ALIGNMENT
    X = df.copy()

    # Best source is the loaded pipeline itself
    if model_features is None:
        model_features = getattr(model, "feature_cols_", None) or model.data_preparer.feature_cols_

    model_features = list(model_features)   # important: convert tuple -> list

    for col in model_features:
        if col not in X.columns:
            X[col] = 0

    X = X.reindex(columns=model_features).copy()

    # 9. CLEAN TYPES
    num_cols = X.select_dtypes(include=[np.number]).columns
    cat_cols = X.select_dtypes(include=["object", "category"]).columns

    X[num_cols] = X[num_cols].replace([np.inf, -np.inf], 0).fillna(0)

    for c in cat_cols:
        X[c] = X[c].fillna("unknown").astype(str).replace("", "unknown")

    # 10. PREDICT
    pred_df = model.predict_from_model_frame(X)
    df["predicted_popularity"] = pred_df["predicted_popularity"].to_numpy()

    return df
"""

pop = BundlePopularityPipeline()
Pmodel = pop.load(path=ArtifactConfig().pipeline_path)

products_scored = prepare_products_for_inference2(
    products_df=gen_res.synthetic_data,
    model=Pmodel,
    model_features=Pmodel.feature_cols_,
    year=2025,
    week=1,
)

p40 = products_scored['predicted_popularity'].quantile(0.40)
p80 = products_scored['predicted_popularity'].quantile(0.80)
products_scored['popularity_category'] = pd.cut(
    products_scored['predicted_popularity'],
    bins=[-float('inf'), p40, p80, float('inf')],
    labels=["Unpopular", "Popular", "Very Popular"],
    include_lowest=True
)

def popularity_category(score):
    if score >= p80:
        return "Very Popular"     # top 20%
    elif score >= p40:
        return "Popular"          # middle 40%
    else:
        return "Unpopular"        # bottom 40%

products_scored['popularity_category'] = products_scored['predicted_popularity'].apply(popularity_category)
print(products_scored['popularity_category'].value_counts())



top_generated_bundles = products_scored[
    products_scored["popularity_category"] == "Very Popular"
].reset_index(drop=True)

unique_top_bundles = (
    top_generated_bundles
    .drop_duplicates()
    .reset_index(drop=True)
)

print(unique_top_bundles.shape)
unique_top_bundles.to_csv("top_generated_bundles.csv", index=False)

"""



