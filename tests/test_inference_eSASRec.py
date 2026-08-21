import os
import sys
import json
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app.customers.targeting.eSASRec.inference.engine import RecommendationEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("eSASRec.Tests.Inference")

def run_inference_test():
    model_path = os.path.expanduser("_models/eSASRec/best_esasrec_model.pth")
    data_path = os.path.expanduser("data/processed_data")

    try:
        logger.info("Initializing RecommendationEngine for isolated testing...")
        engine = RecommendationEngine(
            model_path=model_path, 
            processed_data_path=data_path,
            device_type="cpu"
        )
        
        sample_msisdn = list(engine.user_encoder.keys())[0]
        logger.info(f"Engine initialized successfully. Target MSISDN: {sample_msisdn}")
        
        result = engine.get_recommendations(msisdn=sample_msisdn, top_k=3)
        
        logger.info("Inference completed successfully. Output JSON:")
        print(json.dumps(result, indent=4, ensure_ascii=False))
        
    except Exception as e:
        logger.error(f"Inference test failed: {str(e)}")

if __name__ == "__main__":
    run_inference_test()