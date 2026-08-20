import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import warnings
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from scipy import linalg, stats

from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import plotly.express as px
import plotly.graph_objects as go

# Optional: quality report from SDMetrics if installed
try:
    from sdmetrics.reports.single_table import QualityReport
    HAS_SDMETRICS = True
except Exception:
    HAS_SDMETRICS = False

# Make your project imports work when this script is run from repo root
PROJECT_ROOT = Path.cwd()
sys.path.append(str(PROJECT_ROOT))

from src.app.products.gen.genai.synthesis.config import CTGANArtifactConfig, CTGANBundleConfig
from src.app.products.gen.genai.synthesis.synthesizer import BundleCTGANSynthesizer


warnings.filterwarnings("ignore")


# ----------------------------
# Config
# ----------------------------
ARTIFACT_PATH = CTGANArtifactConfig().artifact_path
REAL_DATA_CSV: Optional[Path] = None
OUTPUT_DIR = PROJECT_ROOT / "_reports" / "ctgan_eval"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLES_PER_TYPE = 500
RANDOM_STATE = 42

# White report theme
PLOTLY_TEMPLATE = "plotly_white"
PAPER_BG = "white"
PLOT_BG = "white"


# ----------------------------
# Helpers
# ----------------------------
def ensure_dataframe_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = np.nan
    return out[columns]


def split_column_types(df: pd.DataFrame) -> Tuple[List[str], List[str]]:
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = [c for c in df.columns if c not in numeric_cols]
    return numeric_cols, categorical_cols


def normalize_for_compare(real_df: pd.DataFrame, synth_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    columns = sorted(set(real_df.columns).intersection(set(synth_df.columns)))
    real_df = ensure_dataframe_columns(real_df, columns).copy()
    synth_df = ensure_dataframe_columns(synth_df, columns).copy()

    for col in columns:
        if pd.api.types.is_numeric_dtype(real_df[col]) or pd.api.types.is_numeric_dtype(synth_df[col]):
            real_df[col] = pd.to_numeric(real_df[col], errors="coerce")
            synth_df[col] = pd.to_numeric(synth_df[col], errors="coerce")
        else:
            real_df[col] = real_df[col].astype("string")
            synth_df[col] = synth_df[col].astype("string")

    return real_df, synth_df


def js_divergence_from_freq(real_s: pd.Series, synth_s: pd.Series) -> float:
    real_freq = real_s.fillna("__nan__").astype(str).value_counts(normalize=True)
    synth_freq = synth_s.fillna("__nan__").astype(str).value_counts(normalize=True)
    cats = sorted(set(real_freq.index).union(set(synth_freq.index)))

    p = np.array([real_freq.get(c, 0.0) for c in cats], dtype=float)
    q = np.array([synth_freq.get(c, 0.0) for c in cats], dtype=float)

    eps = 1e-12
    p = np.clip(p, eps, 1.0)
    q = np.clip(q, eps, 1.0)
    p = p / p.sum()
    q = q / q.sum()
    m = 0.5 * (p + q)

    kl_pm = np.sum(p * np.log(p / m))
    kl_qm = np.sum(q * np.log(q / m))
    return float(0.5 * (kl_pm + kl_qm))


def total_variation_distance(real_s: pd.Series, synth_s: pd.Series) -> float:
    real_freq = real_s.fillna("__nan__").astype(str).value_counts(normalize=True)
    synth_freq = synth_s.fillna("__nan__").astype(str).value_counts(normalize=True)
    cats = sorted(set(real_freq.index).union(set(synth_freq.index)))
    p = np.array([real_freq.get(c, 0.0) for c in cats], dtype=float)
    q = np.array([synth_freq.get(c, 0.0) for c in cats], dtype=float)
    return float(0.5 * np.abs(p - q).sum())


def correlation_similarity(real_df: pd.DataFrame, synth_df: pd.DataFrame, numeric_cols: List[str]) -> float:
    if len(numeric_cols) < 2:
        return np.nan
    r1 = real_df[numeric_cols].corr(method="spearman").fillna(0).values
    r2 = synth_df[numeric_cols].corr(method="spearman").fillna(0).values
    diff = np.abs(r1 - r2)
    return float(1.0 - diff.mean())


def build_preprocessor(real_df: pd.DataFrame, synth_df: pd.DataFrame):
    union_df = pd.concat([real_df, synth_df], ignore_index=True)
    num_cols, cat_cols = split_column_types(union_df)

    num_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    cat_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    pre = ColumnTransformer([
        ("num", num_pipe, num_cols),
        ("cat", cat_pipe, cat_cols),
    ])

    return pre, num_cols, cat_cols


def tabular_embedding(real_df: pd.DataFrame, synth_df: pd.DataFrame, n_components: int = 32):
    pre, _, _ = build_preprocessor(real_df, synth_df)
    X_all = pre.fit_transform(pd.concat([real_df, synth_df], ignore_index=True))
    n_components = min(n_components, X_all.shape[1], max(2, min(len(real_df), len(synth_df)) - 1))
    pca = PCA(n_components=n_components, random_state=RANDOM_STATE)
    Z_all = pca.fit_transform(X_all)

    Z_real = Z_all[: len(real_df)]
    Z_synth = Z_all[len(real_df):]
    return Z_real, Z_synth, pca


def frechet_distance(mu1, sigma1, mu2, sigma2, eps=1e-6) -> float:
    mu1 = np.atleast_1d(mu1)
    mu2 = np.atleast_1d(mu2)
    sigma1 = np.atleast_2d(sigma1)
    sigma2 = np.atleast_2d(sigma2)

    diff = mu1 - mu2

    covmean, _ = linalg.sqrtm(sigma1 @ sigma2, disp=False)
    if not np.isfinite(covmean).all():
        offset = np.eye(sigma1.shape[0]) * eps
        covmean = linalg.sqrtm((sigma1 + offset) @ (sigma2 + offset))

    if np.iscomplexobj(covmean):
        covmean = covmean.real

    return float(diff @ diff + np.trace(sigma1 + sigma2 - 2 * covmean))


def compute_tabular_fid(real_df: pd.DataFrame, synth_df: pd.DataFrame) -> float:
    Z_real, Z_synth, _ = tabular_embedding(real_df, synth_df, n_components=32)
    mu1 = Z_real.mean(axis=0)
    mu2 = Z_synth.mean(axis=0)
    sigma1 = np.cov(Z_real, rowvar=False)
    sigma2 = np.cov(Z_synth, rowvar=False)
    return frechet_distance(mu1, sigma1, mu2, sigma2)


def detection_auc(real_df: pd.DataFrame, synth_df: pd.DataFrame) -> float:
    real_df = real_df.copy()
    synth_df = synth_df.copy()
    real_df["_label"] = 1
    synth_df["_label"] = 0
    df = pd.concat([real_df, synth_df], ignore_index=True)

    X = df.drop(columns=["_label"])
    y = df["_label"].values

    pre, _, _ = build_preprocessor(real_df.drop(columns=["_label"]), synth_df.drop(columns=["_label"]))
    X_enc = pre.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(
        X_enc, y, test_size=0.25, random_state=RANDOM_STATE, stratify=y
    )

    clf = LogisticRegression(max_iter=2000, random_state=RANDOM_STATE)
    clf.fit(X_train, y_train)
    proba = clf.predict_proba(X_test)[:, 1]
    return float(roc_auc_score(y_test, proba))


def nearest_neighbor_privacy_ratio(real_df: pd.DataFrame, synth_df: pd.DataFrame) -> float:
    Z_real, Z_synth, _ = tabular_embedding(real_df, synth_df, n_components=16)

    nn_real = NearestNeighbors(n_neighbors=2).fit(Z_real)
    d_real, _ = nn_real.kneighbors(Z_real)
    real_ref = d_real[:, 1].mean()

    nn_cross = NearestNeighbors(n_neighbors=1).fit(Z_real)
    d_cross, _ = nn_cross.kneighbors(Z_synth)
    synth_to_real = d_cross[:, 0].mean()

    if real_ref == 0:
        return np.nan
    return float(synth_to_real / real_ref)


def evaluate_numeric_columns(real_df: pd.DataFrame, synth_df: pd.DataFrame, numeric_cols: List[str]) -> pd.DataFrame:
    rows = []
    for col in numeric_cols:
        r = pd.to_numeric(real_df[col], errors="coerce").dropna()
        s = pd.to_numeric(synth_df[col], errors="coerce").dropna()

        if len(r) == 0 or len(s) == 0:
            rows.append({
                "column": col,
                "real_mean": np.nan,
                "synth_mean": np.nan,
                "real_std": np.nan,
                "synth_std": np.nan,
                "mean_diff_pct": np.nan,
                "ks_stat": np.nan,
                "ks_pvalue": np.nan,
                "wasserstein": np.nan,
            })
            continue

        mean_diff_pct = abs(s.mean() - r.mean()) / (abs(r.mean()) + 1e-9) * 100.0
        ks_stat, ks_p = stats.ks_2samp(r, s)
        wass = stats.wasserstein_distance(r, s)

        rows.append({
            "column": col,
            "real_mean": float(r.mean()),
            "synth_mean": float(s.mean()),
            "real_std": float(r.std(ddof=1)),
            "synth_std": float(s.std(ddof=1)),
            "mean_diff_pct": float(mean_diff_pct),
            "ks_stat": float(ks_stat),
            "ks_pvalue": float(ks_p),
            "wasserstein": float(wass),
        })

    return pd.DataFrame(rows).sort_values("ks_stat", ascending=False).reset_index(drop=True)


def evaluate_categorical_columns(real_df: pd.DataFrame, synth_df: pd.DataFrame, categorical_cols: List[str]) -> pd.DataFrame:
    rows = []
    for col in categorical_cols:
        r = real_df[col]
        s = synth_df[col]
        real_unique = set(r.fillna("__nan__").astype(str).unique())
        synth_unique = set(s.fillna("__nan__").astype(str).unique())
        overlap = len(real_unique.intersection(synth_unique))
        coverage = overlap / max(len(real_unique), 1)

        rows.append({
            "column": col,
            "real_unique": len(real_unique),
            "synth_unique": len(synth_unique),
            "category_coverage": float(coverage),
            "js_divergence": js_divergence_from_freq(r, s),
            "tv_distance": total_variation_distance(r, s),
        })

    return pd.DataFrame(rows).sort_values("js_divergence", ascending=False).reset_index(drop=True)


def missingness_comparison(real_df: pd.DataFrame, synth_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in real_df.columns:
        rows.append({
            "column": col,
            "real_missing_pct": float(real_df[col].isna().mean() * 100.0),
            "synth_missing_pct": float(synth_df[col].isna().mean() * 100.0),
            "abs_gap_pct": float(abs(real_df[col].isna().mean() - synth_df[col].isna().mean()) * 100.0),
        })
    return pd.DataFrame(rows).sort_values("abs_gap_pct", ascending=False).reset_index(drop=True)


def dataset_summary(real_df: pd.DataFrame, synth_df: pd.DataFrame) -> Dict[str, float]:
    num_cols, cat_cols = split_column_types(real_df)
    return {
        "real_rows": int(len(real_df)),
        "synthetic_rows": int(len(synth_df)),
        "columns": int(real_df.shape[1]),
        "numeric_columns": int(len(num_cols)),
        "categorical_columns": int(len(cat_cols)),
        "correlation_similarity": correlation_similarity(real_df, synth_df, num_cols),
        "detection_auc": detection_auc(real_df, synth_df),
        "privacy_nn_ratio": nearest_neighbor_privacy_ratio(real_df, synth_df),
        "tabular_fid": compute_tabular_fid(real_df, synth_df),
    }


def quality_report_if_available(real_df: pd.DataFrame, synth_df: pd.DataFrame) -> Tuple[Optional[float], Optional[pd.DataFrame]]:
    if not HAS_SDMETRICS:
        return None, None

    metadata = {
        "columns": {}
    }

    for col in real_df.columns:
        if pd.api.types.is_numeric_dtype(real_df[col]):
            metadata["columns"][col] = {"sdtype": "numerical"}
        else:
            metadata["columns"][col] = {"sdtype": "categorical"}

    report = QualityReport()
    report.generate(real_data=real_df, synthetic_data=synth_df, metadata=metadata)
    overall_score = float(report.get_score())
    props = report.get_properties()
    return overall_score, props


# ----------------------------
# Charts
# ----------------------------
def chart_numeric_distributions(real_df: pd.DataFrame, synth_df: pd.DataFrame, numeric_cols: List[str]) -> List[go.Figure]:
    figs = []
    for col in numeric_cols[:6]:
        dfp = pd.DataFrame({
            "value": pd.concat([real_df[col], synth_df[col]], ignore_index=True),
            "dataset": ["Real"] * len(real_df) + ["Synthetic"] * len(synth_df)
        }).dropna()

        fig = px.histogram(
            dfp,
            x="value",
            color="dataset",
            barmode="overlay",
            nbins=40,
            opacity=0.6,
            title=f"Distribution: {col}",
            template=PLOTLY_TEMPLATE,
            color_discrete_map={"Real": "#1f77b4", "Synthetic": "#d62728"},
        )
        fig.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG)
        figs.append(fig)
    return figs


def chart_categorical_distributions(real_df: pd.DataFrame, synth_df: pd.DataFrame, categorical_cols: List[str]) -> List[go.Figure]:
    figs = []
    for col in categorical_cols[:4]:
        r = real_df[col].fillna("__nan__").astype(str).value_counts(normalize=True).rename("Real")
        s = synth_df[col].fillna("__nan__").astype(str).value_counts(normalize=True).rename("Synthetic")
        comp = pd.concat([r, s], axis=1).fillna(0).reset_index().rename(columns={"index": col})
        comp = comp.sort_values("Real", ascending=False).head(15)
        comp_m = comp.melt(id_vars=[col], var_name="dataset", value_name="share")

        fig = px.bar(
            comp_m,
            x=col,
            y="share",
            color="dataset",
            barmode="group",
            title=f"Category Share: {col}",
            template=PLOTLY_TEMPLATE,
            color_discrete_map={"Real": "#1f77b4", "Synthetic": "#d62728"},
        )
        fig.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, xaxis_tickangle=-35)
        figs.append(fig)
    return figs


def chart_correlation_heatmaps(real_df: pd.DataFrame, synth_df: pd.DataFrame, numeric_cols: List[str]) -> List[go.Figure]:
    figs = []
    if len(numeric_cols) < 2:
        return figs

    real_corr = real_df[numeric_cols].corr(method="spearman")
    synth_corr = synth_df[numeric_cols].corr(method="spearman")

    for title, corr in [("Real Correlations", real_corr), ("Synthetic Correlations", synth_corr)]:
        fig = go.Figure(
            data=go.Heatmap(
                z=corr.values,
                x=corr.columns,
                y=corr.index,
                colorscale="RdBu",
                zmin=-1,
                zmax=1,
                colorbar=dict(title="rho"),
            )
        )
        fig.update_layout(title=title, template=PLOTLY_TEMPLATE, paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG)
        figs.append(fig)

    return figs


def chart_pca_scatter(real_df: pd.DataFrame, synth_df: pd.DataFrame) -> go.Figure:
    Z_real, Z_synth, _ = tabular_embedding(real_df, synth_df, n_components=2)
    plot_df = pd.DataFrame({
        "PC1": np.concatenate([Z_real[:, 0], Z_synth[:, 0]]),
        "PC2": np.concatenate([Z_real[:, 1], Z_synth[:, 1]]),
        "dataset": ["Real"] * len(Z_real) + ["Synthetic"] * len(Z_synth),
    })

    max_points = 2000
    if len(plot_df) > max_points:
        plot_df = plot_df.sample(max_points, random_state=RANDOM_STATE)

    fig = px.scatter(
        plot_df,
        x="PC1",
        y="PC2",
        color="dataset",
        opacity=0.65,
        title="PCA Embedding: Real vs Synthetic",
        template=PLOTLY_TEMPLATE,
        color_discrete_map={"Real": "#1f77b4", "Synthetic": "#d62728"},
    )
    fig.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG)
    return fig


# ----------------------------
# HTML
# ----------------------------
def df_to_html_table(df: pd.DataFrame, round_digits: int = 4, max_rows: int = 50) -> str:
    show = df.head(max_rows).copy()
    for col in show.columns:
        if pd.api.types.is_numeric_dtype(show[col]):
            show[col] = show[col].round(round_digits)

    return show.to_html(index=False, border=0, classes="dataframe compact")


def metric_cards_html(summary: Dict[str, float], sdmetrics_score: Optional[float]) -> str:
    items = [
        ("Real rows", summary["real_rows"]),
        ("Synthetic rows", summary["synthetic_rows"]),
        ("Columns", summary["columns"]),
        ("Detection AUC", summary["detection_auc"]),
        ("Privacy NN ratio", summary["privacy_nn_ratio"]),
        ("Correlation similarity", summary["correlation_similarity"]),
        ("Tabular FID", summary["tabular_fid"]),
    ]
    if sdmetrics_score is not None:
        items.append(("SDMetrics quality", sdmetrics_score))

    cards = []
    for k, v in items:
        if isinstance(v, float):
            txt = f"{v:.4f}" if np.isfinite(v) else "nan"
        else:
            txt = str(v)
        cards.append(f"""
        <div class="card">
            <div class="card-title">{k}</div>
            <div class="card-value">{txt}</div>
        </div>
        """)

    return "\n".join(cards)


def fig_to_html(fig: go.Figure, include_plotlyjs: bool = False) -> str:
    return fig.to_html(full_html=False, include_plotlyjs="cdn" if include_plotlyjs else False)


def save_report(
    report_path: Path,
    summary: Dict[str, float],
    numeric_eval: pd.DataFrame,
    categorical_eval: pd.DataFrame,
    missing_eval: pd.DataFrame,
    figures: List[go.Figure],
    sdmetrics_score: Optional[float],
    sdmetrics_props: Optional[pd.DataFrame],
    generation_counts: Dict[str, int],
):
    chart_blocks = []
    for i, fig in enumerate(figures):
        chart_blocks.append(fig_to_html(fig, include_plotlyjs=(i == 0)))

    sdmetrics_html = "<p>SDMetrics not installed, skipped.</p>"
    if sdmetrics_props is not None:
        sdmetrics_html = df_to_html_table(sdmetrics_props)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <title>CTGAN Evaluation Report</title>
        <style>
            body {{
                font-family: Arial, Helvetica, sans-serif;
                background: white;
                color: #111;
                margin: 0;
                padding: 24px;
            }}
            h1, h2, h3 {{
                margin: 0 0 12px 0;
            }}
            .muted {{
                color: #555;
                margin-bottom: 24px;
            }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 12px;
                margin-bottom: 28px;
            }}
            .card {{
                background: #fff;
                border: 1px solid #ddd;
                border-radius: 12px;
                padding: 14px 16px;
                box-shadow: 0 1px 4px rgba(0,0,0,0.05);
            }}
            .card-title {{
                font-size: 13px;
                color: #666;
                margin-bottom: 8px;
            }}
            .card-value {{
                font-size: 28px;
                font-weight: 700;
            }}
            .section {{
                margin-top: 28px;
                margin-bottom: 28px;
            }}
            .dataframe {{
                width: 100%;
                border-collapse: collapse;
                background: #fff;
            }}
            .dataframe th, .dataframe td {{
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
                font-size: 13px;
            }}
            .dataframe th {{
                background: #f7f7f7;
            }}
            .note {{
                padding: 12px 14px;
                background: #fafafa;
                border-left: 4px solid #999;
                margin: 12px 0 20px;
            }}
            .chart {{
                margin-bottom: 26px;
                background: #fff;
                border: 1px solid #e6e6e6;
                border-radius: 12px;
                padding: 8px;
            }}
            pre {{
                background: #f7f7f7;
                border: 1px solid #ddd;
                padding: 12px;
                overflow-x: auto;
            }}
        </style>
    </head>
    <body>
        <h1>CTGAN Evaluation Report</h1>
        <div class="muted">Generated at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>

        <div class="note">
            <strong>Metric note:</strong> classic FID is designed for images. This report uses a
            <strong>tabular FID-style Fréchet distance</strong> computed on a standardized PCA embedding
            of mixed numerical and categorical features.
        </div>

        <div class="section">
            <h2>Headline Metrics</h2>
            <div class="grid">
                {metric_cards_html(summary, sdmetrics_score)}
            </div>
        </div>

        <div class="section">
            <h2>Generation Counts</h2>
            <pre>{json.dumps(generation_counts, indent=2)}</pre>
        </div>

        <div class="section">
            <h2>Charts</h2>
            {''.join(f'<div class="chart">{block}</div>' for block in chart_blocks)}
        </div>

        <div class="section">
            <h2>Numeric Column Evaluation</h2>
            {df_to_html_table(numeric_eval)}
        </div>

        <div class="section">
            <h2>Categorical Column Evaluation</h2>
            {df_to_html_table(categorical_eval)}
        </div>

        <div class="section">
            <h2>Missingness Comparison</h2>
            {df_to_html_table(missing_eval)}
        </div>

        <div class="section">
            <h2>SDMetrics Quality Report</h2>
            {sdmetrics_html}
        </div>
    </body>
    </html>
    """

    report_path.write_text(html, encoding="utf-8")


# ----------------------------
# Main
# ----------------------------
def main():
    synthesizer = BundleCTGANSynthesizer.load(ARTIFACT_PATH)

    if getattr(synthesizer, "training_reference_", None) is not None:
        real_df = synthesizer.training_reference_.copy()
    elif REAL_DATA_CSV is not None:
        real_df = pd.read_csv(REAL_DATA_CSV)
    else:
        raise ValueError(
            "No real data found. Either keep training_reference_ in the saved artifact or set REAL_DATA_CSV."
        )

    generation_result = synthesizer.generate(
        samples_per_type=SAMPLES_PER_TYPE,
        apply_constraints=True,
        apply_final_cleanup=True,
    )
    synth_df = generation_result.synthetic_data.copy()

    real_df, synth_df = normalize_for_compare(real_df, synth_df)
    numeric_cols, categorical_cols = split_column_types(real_df)

    summary = dataset_summary(real_df, synth_df)
    numeric_eval = evaluate_numeric_columns(real_df, synth_df, numeric_cols)
    categorical_eval = evaluate_categorical_columns(real_df, synth_df, categorical_cols)
    missing_eval = missingness_comparison(real_df, synth_df)

    sdmetrics_score, sdmetrics_props = quality_report_if_available(real_df, synth_df)

    figures: List[go.Figure] = []
    figures.extend(chart_numeric_distributions(real_df, synth_df, numeric_cols))
    figures.extend(chart_categorical_distributions(real_df, synth_df, categorical_cols))
    figures.extend(chart_correlation_heatmaps(real_df, synth_df, numeric_cols))
    figures.append(chart_pca_scatter(real_df, synth_df))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = OUTPUT_DIR / f"ctgan_evaluation_report_{timestamp}.html"
    synth_csv_path = OUTPUT_DIR / f"synthetic_samples_{timestamp}.csv"

    synth_df.to_csv(synth_csv_path, index=False)

    save_report(
        report_path=report_path,
        summary=summary,
        numeric_eval=numeric_eval,
        categorical_eval=categorical_eval,
        missing_eval=missing_eval,
        figures=figures,
        sdmetrics_score=sdmetrics_score,
        sdmetrics_props=sdmetrics_props,
        generation_counts=generation_result.generated_counts,
    )

    print(f"Synthetic CSV saved to: {synth_csv_path}")
    print(f"HTML report saved to:   {report_path}")


if __name__ == "__main__":
    main()
