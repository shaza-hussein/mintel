import torch
import torch.nn as nn
import math

class SwigluFeedForward(nn.Module):
    def __init__(self, n_factors: int, n_factors_ff: int, dropout_rate: float, bias: bool = True):
        super().__init__()
        self.ff_linear_1 = nn.Linear(n_factors, n_factors_ff, bias=bias)
        self.ff_dropout_1 = nn.Dropout(dropout_rate)
        self.ff_activation = nn.SiLU() 
        self.ff_linear_2 = nn.Linear(n_factors_ff, n_factors, bias=bias)
        self.ff_linear_3 = nn.Linear(n_factors, n_factors_ff, bias=bias)

    def forward(self, seqs: torch.Tensor) -> torch.Tensor:
        output = self.ff_activation(self.ff_linear_1(seqs)) * self.ff_linear_3(seqs)
        fin = self.ff_linear_2(self.ff_dropout_1(output))
        return fin


class LiGRLayer(nn.Module):
    def __init__(self, n_factors: int, n_heads: int, dropout_rate: float, ff_factors_multiplier: int = 4):
        super().__init__()
        self.multi_head_attn = nn.MultiheadAttention(n_factors, n_heads, dropout_rate, batch_first=True)
        self.layer_norm_1 = nn.LayerNorm(n_factors)
        self.layer_norm_2 = nn.LayerNorm(n_factors)
        self.feed_forward = SwigluFeedForward(n_factors, n_factors * ff_factors_multiplier, dropout_rate)
        self.dropout_1 = nn.Dropout(dropout_rate)
        self.dropout_2 = nn.Dropout(dropout_rate)
        self.gating_linear_1 = nn.Linear(n_factors, n_factors)
        self.gating_linear_2 = nn.Linear(n_factors, n_factors)

    def forward(self, seqs: torch.Tensor, attn_mask: torch.Tensor, key_padding_mask: torch.Tensor) -> torch.Tensor:
        mha_input = self.layer_norm_1(seqs)
        mha_output, _ = self.multi_head_attn(
            mha_input, mha_input, mha_input,
            attn_mask=attn_mask,
            key_padding_mask=key_padding_mask,
            need_weights=False,
        )
        gated_skip_1 = torch.sigmoid(self.gating_linear_1(seqs))
        seqs = seqs + torch.mul(gated_skip_1, self.dropout_1(mha_output))

        ff_input = self.layer_norm_2(seqs)
        ff_output = self.feed_forward(ff_input)
        gated_skip_2 = torch.sigmoid(self.gating_linear_2(seqs))
        seqs = seqs + torch.mul(gated_skip_2, self.dropout_2(ff_output))
        return seqs


class Official_eSASRec(nn.Module):
    def __init__(self, item_num, max_len=100, hidden_size=64, num_blocks=2, num_heads=2, dropout_rate=0.2):
        super(Official_eSASRec, self).__init__()
        self.hidden_size = hidden_size
        self.item_emb = nn.Embedding(item_num + 1, hidden_size, padding_idx=0)
        self.pos_emb = nn.Embedding(max_len, hidden_size)
        self.emb_dropout = nn.Dropout(dropout_rate)
        self.transformer_blocks = nn.ModuleList([
            LiGRLayer(hidden_size, num_heads, dropout_rate, ff_factors_multiplier=4) 
            for _ in range(num_blocks)
        ])
        self.layer_norm = nn.LayerNorm(hidden_size)
        self.prediction_head = nn.Linear(hidden_size, item_num + 1)

    def generate_square_subsequent_mask(self, sz: int) -> torch.Tensor:
        mask = (torch.triu(torch.ones(sz, sz)) == 1).transpose(0, 1)
        mask = mask.float().masked_fill(mask == 0, float('-inf')).masked_fill(mask == 1, float(0.0))
        return mask

    def forward(self, log_seqs: torch.Tensor) -> torch.Tensor:
        device = log_seqs.device
        seq_len = log_seqs.size(1)
        padding_mask = (log_seqs == 0)
        causal_mask = self.generate_square_subsequent_mask(seq_len).to(device)
        
        seq_emb = self.item_emb(log_seqs) * math.sqrt(self.hidden_size)
        positions = torch.arange(seq_len, dtype=torch.long, device=device).unsqueeze(0)
        seq_emb += self.pos_emb(positions)
        seqs = self.emb_dropout(seq_emb)
        
        for block in self.transformer_blocks:
            seqs = block(seqs, attn_mask=causal_mask, key_padding_mask=padding_mask)
            
        seqs = self.layer_norm(seqs)
        logits = self.prediction_head(seqs)
        return logits