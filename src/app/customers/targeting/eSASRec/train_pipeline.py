import os
import logging
import pandas as pd
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.utils.data import DataLoader

from model.dataset import TelecomSequenceDataset
from model.architecture import Official_eSASRec
from training.trainer import ModelTrainer
from training.evaluator import ModelEvaluator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("eSASRec.Pipeline")

# Configuration Constants
MAX_LEN = 100
BATCH_SIZE = 256
NUM_WORKERS = 2
ITEM_NUM = 708
NUM_EPOCHS = 15
PATIENCE = 3
PROCESSED_PATH = os.path.expanduser('~/processed_data')
DATA_FILE = f"{PROCESSED_PATH}/pytorch_ready_data.parquet"
MODEL_SAVE_PATH = os.path.expanduser("~/models/best_esasrec_model.pth")

def run_training_pipeline():
    logger.info("Initializing Data Pipeline...")
    valid_users_df = pd.read_parquet(DATA_FILE)
    
    telecom_dataset = TelecomSequenceDataset(valid_users_df, max_len=MAX_LEN)
    train_dataloader = DataLoader(
        telecom_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=NUM_WORKERS,
        drop_last=False
    )
    logger.info(f"Data pipeline built. Total batches per epoch: {len(train_dataloader)}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = Official_eSASRec(item_num=ITEM_NUM, max_len=MAX_LEN, hidden_size=64).to(device)
    
    criterion = nn.CrossEntropyLoss(ignore_index=0)
    optimizer = AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)

    os.makedirs(os.path.dirname(MODEL_SAVE_PATH), exist_ok=True)

    trainer = ModelTrainer(
        model=model,
        train_loader=train_dataloader,
        optimizer=optimizer,
        criterion=criterion,
        device=device,
        item_num=ITEM_NUM,
        save_path=MODEL_SAVE_PATH,
        patience=PATIENCE
    )
    
    trainer.train(num_epochs=NUM_EPOCHS)

    logger.info("Loading best model for evaluation...")
    model.load_state_dict(torch.load(MODEL_SAVE_PATH))
    
    evaluator = ModelEvaluator(
        model=model,
        test_loader=train_dataloader,
        device=device,
        k=10
    )
    evaluator.evaluate()

if __name__ == "__main__":
    run_training_pipeline()