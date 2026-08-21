import os
import logging
import torch
import pandas as pd
import json


from src.app.customers.targeting.eSASRec.model.architecture import Official_eSASRec

logger = logging.getLogger("eSASRec.InferenceEngine")

class RecommendationEngine:
    def __init__(self, model_path, processed_data_path, device_type="cpu"):
        self.device = torch.device(device_type)
        self.model_path = model_path
        self.processed_data_path = processed_data_path
        self.max_len = 100
        
        self.model = None
        self.user_encoder = {}
        self.item_decoder = {}
        self.history_df = None
        
        self._initialize_engine()

    def _initialize_engine(self):
        logger.info("Initializing Inference Engine...")
        
        # 1. Load Data & Build O(1) Dictionaries
        logger.info("Loading mapping dictionaries and user history...")
        user_mapping_df = pd.read_parquet(f"{self.processed_data_path}/user_mapping.parquet")
        item_mapping_df = pd.read_parquet(f"{self.processed_data_path}/item_mapping.parquet")
        item_catalog_df = pd.read_parquet(f"{self.processed_data_path}/item_catalog.parquet")
        
        # history_df acts as the in-memory database for fast sequence retrieval
        self.history_df = pd.read_parquet(f"{self.processed_data_path}/pytorch_ready_data.parquet")
        
        self.user_encoder = user_mapping_df.set_index('msisdn')['user_id'].to_dict()
        
        full_item_info = pd.merge(item_mapping_df, item_catalog_df, on='bundle_id', how='left')
        full_item_info = full_item_info.drop_duplicates(subset=['item_id'], keep='first')
        
        self.item_decoder = full_item_info.set_index('item_id')[
            ['bundle_id', 'bundle_name', 'price', 'bundle_type']
        ].to_dict('index')
        
        # 2. Load Model Architecture & Weights
        logger.info("Loading eSASRec model weights...")
        item_num = len(self.item_decoder)
        self.model = Official_eSASRec(item_num=item_num, max_len=self.max_len, hidden_size=64).to(self.device)
        
        if os.path.exists(self.model_path):
            self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
            self.model.eval()
            logger.info("Model loaded successfully and set to evaluation mode.")
        else:
            logger.error(f"Model weights not found at {self.model_path}")
            raise FileNotFoundError(f"Model weights not found at {self.model_path}")

    def get_recommendations(self, msisdn, top_k=5):
        """
        Receives a real MSISDN, retrieves history, runs inference, 
        and returns a JSON-ready dictionary with actual bundle details.
        """
        encoded_user_id = self.user_encoder.get(msisdn)
        
        if encoded_user_id is None:
            return {"status": "error", "message": f"Customer ({msisdn}) not found in the system."}
        
        user_data = self.history_df[self.history_df['user_id'] == encoded_user_id]
        if user_data.empty:
            return {"status": "error", "message": "Insufficient historical data for this customer."}
        
        train_seq = list(user_data['train_sequence'].values[0])
        original_history_length = len(train_seq)
        
        if len(train_seq) > self.max_len:
            train_seq = train_seq[-self.max_len:]
        
        pad_length = self.max_len - len(train_seq)
        if pad_length > 0:
            train_seq = ([0] * pad_length) + train_seq
            
        input_tensor = torch.tensor([train_seq], dtype=torch.long).to(self.device)
        
        with torch.no_grad():
            logits = self.model(input_tensor)
            last_step_logits = logits[:, -1, :] 
            last_step_logits[0, 0] = float('-inf') # Ignore padding index
            
            probabilities = torch.softmax(last_step_logits, dim=-1)
            top_probs, top_indices = torch.topk(probabilities, k=top_k, dim=-1)
        
        recommendations = []
        for idx, prob in zip(top_indices[0].tolist(), top_probs[0].tolist()):
            bundle_info = self.item_decoder.get(idx, {})
            bundle_id_val = bundle_info.get('bundle_id', 'Unknown')
            
            recommendations.append({
                "rank": int(len(recommendations) + 1),
                "bundle_id": str(bundle_id_val) if pd.notna(bundle_id_val) else "Unknown", 
                "bundle_name": str(bundle_info.get('bundle_name', 'Unknown Bundle')),
                "bundle_type": str(bundle_info.get('bundle_type', 'N/A')),
                "price": float(bundle_info.get('price', 0.0)),
                "confidence_score": f"{round(prob * 100, 1)}%"
            })
            
        return {
            "status": "success",
            "customer": {
                "msisdn": int(msisdn),
                "historical_purchases_count": original_history_length
            },
            "recommendations": recommendations
        }



    def get_batch_recommendations(self, msisdn_list, top_k=5):
        """
        Receives a list of MSISDNs and returns their recommendations in a single batch operation.
        """
        valid_encoded_ids = []
        valid_msisdns = []
        
        
        for msisdn in msisdn_list:
            encoded_id = self.user_encoder.get(msisdn)
            if encoded_id is not None:
                valid_encoded_ids.append(encoded_id)
                valid_msisdns.append(msisdn)
                
        if not valid_encoded_ids:
            return {"status": "error", "message": "None of the provided customers were found."}

       
        user_data = self.history_df[self.history_df['user_id'].isin(valid_encoded_ids)]
        user_seq_dict = user_data.set_index('user_id')['train_sequence'].to_dict()
        
        batch_seqs = []
        hist_counts = []
        
        
        for encoded_id in valid_encoded_ids:
            seq = list(user_seq_dict.get(encoded_id, []))
            hist_counts.append(len(seq))
            
            if len(seq) > self.max_len:
                seq = seq[-self.max_len:]
            pad_length = self.max_len - len(seq)
            if pad_length > 0:
                seq = ([0] * pad_length) + seq
                
            batch_seqs.append(seq)
            
        
        batch_tensor = torch.tensor(batch_seqs, dtype=torch.long).to(self.device)
        
        with torch.no_grad():
            logits = self.model(batch_tensor)
            last_step_logits = logits[:, -1, :] 
            last_step_logits[:, 0] = float('-inf') 
            
            probabilities = torch.softmax(last_step_logits, dim=-1)
            top_probs, top_indices = torch.topk(probabilities, k=top_k, dim=-1)
            
        
        batch_results = []
        for i, msisdn in enumerate(valid_msisdns):
            recommendations = []
            for rank, (idx, prob) in enumerate(zip(top_indices[i].tolist(), top_probs[i].tolist())):
                bundle_info = self.item_decoder.get(idx, {})
                bundle_id_val = bundle_info.get('bundle_id', 'Unknown')
                
                recommendations.append({
                    "rank": rank + 1,
                    "bundle_id": str(bundle_id_val) if pd.notna(bundle_id_val) else "Unknown", 
                    "bundle_name": str(bundle_info.get('bundle_name', 'Unknown Bundle')),
                    "bundle_type": str(bundle_info.get('bundle_type', 'N/A')),
                    "price": float(bundle_info.get('price', 0.0)),
                    "confidence_score": f"{round(prob * 100, 1)}%"
                })
                
            batch_results.append({
                "msisdn": int(msisdn),
                "historical_purchases_count": hist_counts[i],
                "recommendations": recommendations
            })
            
        return {
            "status": "success",
            "total_processed": len(batch_results),
            "data": batch_results
        }