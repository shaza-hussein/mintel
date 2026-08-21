import torch
import logging
from tqdm import tqdm

logger = logging.getLogger("eSASRec.Trainer")

class ModelTrainer:
    def __init__(self, model, train_loader, optimizer, criterion, device, item_num, save_path, patience=3):
        self.model = model
        self.train_loader = train_loader
        self.optimizer = optimizer
        self.criterion = criterion
        self.device = device
        self.item_num = item_num
        self.save_path = save_path
        self.patience = patience

    def train(self, num_epochs):
        logger.info(f"Starting training for {num_epochs} epochs. Device: {self.device.type.upper()}")
        best_val_loss = float('inf')
        patience_counter = 0

        for epoch in range(1, num_epochs + 1):
            avg_train_loss = self._train_epoch(epoch)
            avg_val_loss = self._validate_epoch(epoch)

            logger.info(f"Epoch {epoch:02d} | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f}")

            if avg_val_loss < best_val_loss:
                best_val_loss = avg_val_loss
                patience_counter = 0
                torch.save(self.model.state_dict(), self.save_path)
                logger.info("Validation loss improved. Model weights saved.")
            else:
                patience_counter += 1
                logger.info(f"No improvement in validation loss. Patience: {patience_counter}/{self.patience}")

                if patience_counter >= self.patience:
                    logger.warning("Early stopping triggered due to lack of improvement.")
                    break

        logger.info(f"Training protocol completed. Best model saved at: {self.save_path}")

    def _train_epoch(self, epoch):
        self.model.train()
        total_loss = 0.0
        train_bar = tqdm(self.train_loader, desc=f"Epoch {epoch} [Train]", leave=False)

        for batch in train_bar:
            input_seq = batch['input_seq'].to(self.device)
            target_seq = batch['train_target'].to(self.device)

            self.optimizer.zero_grad()
            logits = self.model(input_seq)

            logits_flat = logits.view(-1, self.item_num + 1)
            target_flat = target_seq.view(-1)

            loss = self.criterion(logits_flat, target_flat)
            loss.backward()

            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=5.0)
            self.optimizer.step()
            
            total_loss += loss.item()
            train_bar.set_postfix({'Loss': f"{loss.item():.4f}"})

        return total_loss / len(self.train_loader)

    def _validate_epoch(self, epoch):
        self.model.eval()
        total_loss = 0.0
        val_bar = tqdm(self.train_loader, desc=f"Epoch {epoch} [Val]", leave=False)

        with torch.no_grad():
            for batch in val_bar:
                input_seq = batch['input_seq'].to(self.device)
                val_target = batch['val_target'].to(self.device)

                logits = self.model(input_seq)
                last_step_logits = logits[:, -1, :]

                loss = self.criterion(last_step_logits, val_target)
                total_loss += loss.item()

        return total_loss / len(self.train_loader)