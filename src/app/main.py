TRAIN: bool = False
MBA: bool =  False
CTGAN: bool = False
#----------------------------------------------------------------------------------------
# Trainer
#----------------------------------------------------------------------------------------
if TRAIN:
    import pandas as pd
    from products.pipeline.trainer import ProductModelsTrainer
    from products.mba.train import build_spark_session

    trainer = ProductModelsTrainer()

    # TODO-1-: Train ML Popularity Model
    data = pd.read_csv(r"..\..\..\datasets\weekly_base_bundles_info_202501_202510.csv")
    df_model = trainer.train_popularity(data=data)

    del data
    # TODO-2-: train CTGAN Model 
    trainer.train_synthesizer(data=df_model)

    del df_model

    # TODO-3-: Train MBA Model
    FODLER_PATH: str =  r"C:\Users\Alber\Desktop\uni\GraduationProject\datasets\weekly purchases"
    spark = build_spark_session()
    mba_df = spark.read.csv(
        [
        rf"{FODLER_PATH}\weekly-purchase-202508.csv",
        rf"{FODLER_PATH}\weekly-purchase-202509.csv",
        rf"{FODLER_PATH}\weekly-purchase-202510.csv",
        ],
        header=True,
        inferSchema=True,
    )
    trainer.train_mba(data=mba_df, spark=spark)


#----------------------------------------------------------------------------------------
# Generation new bundles
#----------------------------------------------------------------------------------------
else:
    import json
    import pandas as pd

    if CTGAN:
        from products.gen.generator import BundlesGenerator
        from products.gen.config import BundleGenerationConfig

        generator = BundlesGenerator()

        request = BundleGenerationConfig(
            offer_type="atl", 
            allowed_bundle_types=("BUNDLE_DATA", "BUNDLE_VOICE", "BUNDLE_SMS"),
            validity_options=(24.0, 72.0, 168.0, 720.0),
            max_volume_mb=25000,
            max_volume_min=300,
            max_volume_sms=150,
        )

        top_per_type, summary_df, generated = generator.generate(
            generation_config=request
        )


    if MBA:
        # TODO-3-: Bundles from MBA
        from products.mba.analytics import MarketBasketAnalyzer
        mba = MarketBasketAnalyzer()
        bundles = mba.hybrid_bundles()

        with open("mab_bundles.json", "w", encoding="utf-8") as f:
            json.dump(bundles, f, indent=4, ensure_ascii=False)

        # other insgihts from MBA Association rules result.
        sankey_bundles = mba.item_relationship_sankey()

        with open("sankey_bundles.json", "w", encoding="utf-8") as f:
            json.dump(sankey_bundles, f, indent=4, ensure_ascii=False)

        
