import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def fit_numeric(df: pd.DataFrame, cols: List[str]) -> Tuple[np.ndarray, Dict, Dict]:
    x = df[cols].replace([np.inf, -np.inf], np.nan).astype("float32")
    mean = x.mean(axis=0).astype("float32")
    std = x.std(axis=0).replace(0, 1).astype("float32")
    x = x.fillna(mean)
    x = ((x - mean) / std).astype("float32")
    return x.to_numpy(), mean.to_dict(), std.to_dict()


def transform_numeric(df: pd.DataFrame, cols: List[str], mean: Dict, std: Dict) -> np.ndarray:
    x = df[cols].replace([np.inf, -np.inf], np.nan).astype("float32")
    mean_s = pd.Series(mean, dtype="float32")
    std_s = pd.Series(std, dtype="float32").replace(0, 1)
    x = x.fillna(mean_s)
    x = ((x - mean_s) / std_s).astype("float32")
    return x.to_numpy()


def fit_categorical(df: pd.DataFrame, cols: List[str]):
    cat_arrays = []
    maps = {}
    cardinalities = []

    for col in cols:
        s = df[col].fillna("UNK").astype(str)
        values = pd.Index(s.unique())
        mapping = {v: i for i, v in enumerate(values)}
        unk_idx = len(mapping)

        arr = s.map(mapping).fillna(unk_idx).astype("int64").to_numpy()
        cat_arrays.append(arr)
        maps[col] = mapping
        cardinalities.append(len(mapping) + 1)

    if not cat_arrays:
        return np.zeros((len(df), 0), dtype=np.int64), maps, cardinalities

    return np.stack(cat_arrays, axis=1), maps, cardinalities


def transform_categorical(df: pd.DataFrame, cols: List[str], maps: Dict) -> np.ndarray:
    cat_arrays = []

    for col in cols:
        mapping = maps[col]
        unk_idx = len(mapping)
        s = df[col].fillna("UNK").astype(str)
        arr = s.map(mapping).fillna(unk_idx).astype("int64").to_numpy()
        cat_arrays.append(arr)

    if not cat_arrays:
        return np.zeros((len(df), 0), dtype=np.int64)

    return np.stack(cat_arrays, axis=1)


def write_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=4)


def read_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)