import pandas as pd
# TODO-1-: Testing Training and Inference of Popularity Model.
# Training
from products.popularity.train import train_popularity_model

data = pd.read_csv(r"..\..\..\datasets\weekly_base_bundles_info_202501_202510.csv")
print(data.shape)
#result = train_popularity_model(data=data)
#print(result)

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
