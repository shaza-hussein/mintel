import torch
from torch.utils.data import Dataset

class TelecomSequenceDataset(Dataset):
    def __init__(self, dataframe, max_len=100):
        self.df = dataframe
        self.max_len = max_len

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]

        user_id = int(row['user_id'])
        train_seq = list(row['train_sequence'])
        test_seq = list(row['test_sequence'])

        test_target = test_seq[0] if len(test_seq) > 0 else 0
        val_target = train_seq[-1]
        actual_train_seq = train_seq[:-1]

        train_input_seq = actual_train_seq[:-1]
        train_target_seq = actual_train_seq[1:]

        if len(train_input_seq) > self.max_len:
            train_input_seq = train_input_seq[-self.max_len:]
            train_target_seq = train_target_seq[-self.max_len:]

        pad_length = self.max_len - len(train_input_seq)
        if pad_length > 0:
            train_input_seq = ([0] * pad_length) + train_input_seq
            train_target_seq = ([0] * pad_length) + train_target_seq

        return {
            'user_id': torch.tensor(user_id, dtype=torch.long),
            'input_seq': torch.tensor(train_input_seq, dtype=torch.long),
            'train_target': torch.tensor(train_target_seq, dtype=torch.long),
            'val_target': torch.tensor(val_target, dtype=torch.long),
            'test_target': torch.tensor(test_target, dtype=torch.long)
        }