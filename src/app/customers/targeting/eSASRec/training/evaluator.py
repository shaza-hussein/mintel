import torch
import numpy as np
import logging
from tqdm import tqdm

logger = logging.getLogger("eSASRec.Evaluator")

class ModelEvaluator:
    def __init__(self, model, test_loader, device, k=10):
        self.model = model
        self.test_loader = test_loader
        self.device = device
        self.k = k

    def evaluate(self):
        logger.info(f"Starting final evaluation protocol (HitRate@{self.k} and NDCG@{self.k})")
        self.model.eval()
        
        hits = 0
        ndcg = 0
        total_valid_users = 0

        with torch.no_grad():
            test_bar = tqdm(self.test_loader, desc="Evaluating", leave=False)

            for batch in test_bar:
                input_seq = batch['input_seq'].to(self.device)
                val_target = batch['val_target'].to(self.device).unsqueeze(1)
                test_targets = batch['test_target'].to(self.device)

                full_history = torch.cat([input_seq[:, 1:], val_target], dim=1)
                logits = self.model(full_history)
                last_step_logits = logits[:, -1, :]

                _, top_k_indices = torch.topk(last_step_logits, k=self.k, dim=-1)

                for i in range(len(test_targets)):
                    target = test_targets[i].item()
                    if target == 0:
                        continue

                    total_valid_users += 1
                    predictions = top_k_indices[i].tolist()

                    if target in predictions:
                        hits += 1
                        rank = predictions.index(target)
                        ndcg += 1.0 / np.log2(rank + 2)

        final_hitrate = (hits / total_valid_users) * 100 if total_valid_users > 0 else 0.0
        final_ndcg = (ndcg / total_valid_users) * 100 if total_valid_users > 0 else 0.0

        logger.info(f"Evaluation Completed. Valid Users: {total_valid_users}")
        logger.info(f"HitRate@{self.k}: {final_hitrate:.2f}%")
        logger.info(f"NDCG@{self.k}: {final_ndcg:.2f}%")

        return final_hitrate, final_ndcg