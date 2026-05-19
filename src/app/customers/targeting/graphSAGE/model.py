import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import HeteroConv, SAGEConv

from src.app.customers.targeting.graphSAGE.config import EDGE_TYPE, REV_EDGE_TYPE


class TabEncoder(nn.Module):

    def __init__(self, num_dim, cat_cardinalities, hidden_dim, cat_emb_dim=16):
        super().__init__()
        self.embs = nn.ModuleList()

        for cardinality in cat_cardinalities:
            emb_dim = min(cat_emb_dim, max(4, int(math.sqrt(cardinality))))
            self.embs.append(nn.Embedding(cardinality, emb_dim))

        emb_total_dim = sum(emb.embedding_dim for emb in self.embs)
        self.net = nn.Sequential(
            nn.Linear(num_dim + emb_total_dim, hidden_dim),
            nn.ReLU(),
            nn.LayerNorm(hidden_dim),
            nn.Dropout(0.10),
        )

    def forward(self, x_num, x_cat):
        parts = [x_num.float()]
        for j, emb in enumerate(self.embs):
            parts.append(emb(x_cat[:, j].long()))
        return self.net(torch.cat(parts, dim=-1))


class HeteroGraphSAGE(nn.Module):
    def __init__(
        self,
        user_num_dim,
        user_cat_cardinalities,
        bundle_num_dim,
        bundle_cat_cardinalities,
        hidden_dim=64,
        cat_emb_dim=16,
        num_layers=2,
        dropout=0.25,
    ):
        super().__init__()
        self.user_encoder = TabEncoder(
            user_num_dim,
            user_cat_cardinalities,
            hidden_dim,
            cat_emb_dim,
        )
        self.bundle_encoder = TabEncoder(
            bundle_num_dim,
            bundle_cat_cardinalities,
            hidden_dim,
            cat_emb_dim,
        )

        self.convs = nn.ModuleList()
        self.user_norms = nn.ModuleList()
        self.bundle_norms = nn.ModuleList()

        for _ in range(num_layers):
            self.convs.append(
                HeteroConv(
                    {
                        EDGE_TYPE: SAGEConv((hidden_dim, hidden_dim), hidden_dim),
                        REV_EDGE_TYPE: SAGEConv((hidden_dim, hidden_dim), hidden_dim),
                    },
                    aggr="sum",
                )
            )
            self.user_norms.append(nn.LayerNorm(hidden_dim))
            self.bundle_norms.append(nn.LayerNorm(hidden_dim))

        self.dropout = dropout

    def forward(self, batch):
        x_dict = {
            "user": self.user_encoder(batch["user"].x_num, batch["user"].x_cat),
            "bundle": self.bundle_encoder(batch["bundle"].x_num, batch["bundle"].x_cat),
        }

        for i, conv in enumerate(self.convs):
            x_dict = conv(x_dict, batch.edge_index_dict)
            x_dict["user"] = self.user_norms[i](x_dict["user"])
            x_dict["bundle"] = self.bundle_norms[i](x_dict["bundle"])
            x_dict = {
                node_type: F.dropout(
                    F.relu(x),
                    p=self.dropout,
                    training=self.training,
                )
                for node_type, x in x_dict.items()
            }

        return x_dict

    def score(self, z_dict, edge_label_index):
        src_user, dst_bundle = edge_label_index
        z_user = z_dict["user"][src_user]
        z_bundle = z_dict["bundle"][dst_bundle]
        return (z_user * z_bundle).sum(dim=-1)