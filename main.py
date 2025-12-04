from __future__ import annotations
import logging
import math
from typing import Sequence, Tuple, Dict, Optional

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

# Configure module-level logger
logger = logging.getLogger("bass_model")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


# ---------------- Bass analytic functions ----------------------------------


def bass_F(t: np.ndarray | float, p: float, q: float) -> np.ndarray:
    """
    Cumulative adoption fraction F(t) = (1 - exp(-(p+q)t)) / (1 + (q/p) exp(-(p+q)t))
    Handles scalar or array t.
    """
    t_arr = np.asarray(t, dtype=float)
    eps = 1e-16
    p_safe = p if abs(p) > eps else math.copysign(eps, p if p != 0 else 1.0)
    a = p + q
    expo = np.exp(-a * t_arr)
    F = (1.0 - expo) / (1.0 + (q / p_safe) * expo)
    return F


def bass_instantaneous_rate(t: np.ndarray | float, p: float, q: float) -> np.ndarray:
    """
    Instantaneous adoption fraction f(t) = F'(t)
    """
    t_arr = np.asarray(t, dtype=float)
    eps = 1e-16
    p_safe = p if abs(p) > eps else math.copysign(eps, p if p != 0 else 1.0)
    a = p + q
    exp_term = np.exp(-a * t_arr)
    denom = (1.0 + (q / p_safe) * exp_term) ** 2
    f = (a ** 2 / p_safe) * exp_term / denom
    return f


def adopters_at_time(t: np.ndarray | float, m: float, p: float, q: float) -> np.ndarray:
    """
    New adopters (counts) at time t: s(t) = m * f(t)
    """
    return m * bass_instantaneous_rate(t, p, q)


def cumulative_adopters(t: np.ndarray | float, m: float, p: float, q: float) -> np.ndarray:
    """
    Cumulative adopters at time t: m * F(t)
    """
    return m * bass_F(t, p, q)


# ---------------- Simulation helper ----------------------------------------


def simulate_bass(
    T: int,
    m: float,
    p: float,
    q: float,
    noise_sd: float = 0.0,
    seed: Optional[int] = None,
    dt: float = 1.0,
) -> pd.DataFrame:
    """
    Simulate discrete-time Bass adopters for T time steps (0..T-1).
    Returns DataFrame with columns: t, adopters, cumulative
    noise_sd: additive Gaussian noise std applied to adopters.
    dt: time-step size (units)
    """
    rng = np.random.default_rng(seed)
    t = np.arange(0, T) * dt
    true_adopters = np.maximum(0.0, adopters_at_time(t, m, p, q))
    if noise_sd and noise_sd > 0.0:
        noisy = true_adopters + rng.normal(0.0, noise_sd, size=true_adopters.shape)
        noisy = np.clip(noisy, a_min=0.0, a_max=None)
    else:
        noisy = true_adopters.copy()
    cumulative = np.cumsum(noisy)
    df = pd.DataFrame({"t": t, "adopters": noisy, "cumulative": cumulative})
    return df


# ---------------- Fitting (nonlinear least squares) ------------------------


def _bass_adopters_for_curvefit(t, m, p, q):
    t = np.asarray(t, dtype=float)
    return adopters_at_time(t, m, p, q)


def fit_bass_nlls(
    t: Sequence[float],
    y: Sequence[float],
    initial_guess: Optional[Tuple[float, float, float]] = None,
    bounds: Optional[Tuple[Sequence[float], Sequence[float]]] = None,
    method: str = "trf",
    sigma: Optional[Sequence[float]] = None,
    max_nfev: int = 20000,
) -> Dict[str, object]:
    """
    Fit Bass model to observed new-adopter counts y(t) using nonlinear least-squares.
    Returns a dict containing:
      - params: {'m', 'p', 'q'}
      - pcov: covariance matrix returned by curve_fit
      - fitted: fitted y values
      - r2: coefficient of determination on adopters
      - t, y (input)
    """
    t_arr = np.asarray(t, dtype=float)
    y_arr = np.asarray(y, dtype=float)

    # defaults
    y_sum = float(np.sum(y_arr))
    y_max = float(np.max(y_arr))
    if initial_guess is None:
        m0 = max(y_sum * 1.5, y_max * 5.0, 1.0)
        p0 = 0.03
        q0 = 0.38
    else:
        m0, p0, q0 = initial_guess

    if bounds is None:
        # lower bounds: market size at least somewhat > observed sum; p,q positive
        lower = [max(1.0, y_sum * 0.5), 1e-8, 1e-8]
        upper = [max(y_sum * 50.0, m0 * 100.0), 1.0, 5.0]
        bounds = (lower, upper)

    try:
        popt, pcov = curve_fit(
            _bass_adopters_for_curvefit,
            t_arr,
            y_arr,
            p0=[m0, p0, q0],
            bounds=bounds,
            method=method,
            sigma=sigma,
            absolute_sigma=False if sigma is None else True,
            max_nfev=max_nfev,
        )
    except Exception as exc:
        logger.error("curve_fit failed: %s", exc)
        raise

    m_hat, p_hat, q_hat = popt
    fitted = _bass_adopters_for_curvefit(t_arr, *popt)
    ss_res = np.sum((y_arr - fitted) ** 2)
    ss_tot = np.sum((y_arr - np.mean(y_arr)) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    result = {
        "params": {"m": float(m_hat), "p": float(p_hat), "q": float(q_hat)},
        "pcov": pcov,
        "fitted": fitted,
        "r2": r2,
        "t": t_arr,
        "y": y_arr,
    }
    logger.info("Fitted params: m=%.3f, p=%.6f, q=%.6f, R2=%.4f", m_hat, p_hat, q_hat, r2)
    return result


# ---------------- Bootstrap uncertainties ---------------------------------


def bootstrap_bass(
    t: Sequence[float],
    y: Sequence[float],
    n_boot: int = 500,
    random_seed: Optional[int] = None,
    fit_kwargs: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Residual bootstrap for parameter uncertainty.
    Returns DataFrame with columns ['m','p','q'] for each successful bootstrap replicate.
    """
    rng = np.random.default_rng(random_seed)
    fit_kwargs = fit_kwargs or {}
    base_fit = fit_bass_nlls(t, y, **fit_kwargs)
    fitted0 = np.array(base_fit["fitted"])
    resid = np.array(y) - fitted0
    n = len(t)
    boot_params = []
    for i in range(n_boot):
        resampled = rng.choice(resid, size=n, replace=True)
        y_star = fitted0 + resampled
        y_star = np.clip(y_star, 0.0, None)
        try:
            f = fit_bass_nlls(t, y_star, **fit_kwargs)
            boot_params.append([f["params"]["m"], f["params"]["p"], f["params"]["q"]])
        except Exception as exc:
            # skip failed fits, but log occasionally
            if i % 50 == 0:
                logger.debug("Bootstrap replicate %d failed: %s", i, exc)
            continue
    df = pd.DataFrame(boot_params, columns=["m", "p", "q"])
    if df.empty:
        logger.warning("Bootstrap produced zero successful replicates.")
    else:
        logger.info("Bootstrap completed: %d successful replicates", len(df))
    return df


# ---------------- Plotting helpers ----------------------------------------


def plot_bass_fit(t: Sequence[float], y: Sequence[float], fit_result: Dict[str, object], ax=None):
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 6))
    t_arr = np.asarray(t)
    fitted = fit_result["fitted"]
    params = fit_result["params"]
    ax.scatter(t_arr, y, marker="o", label="observed adopters")
    ax.plot(t_arr, fitted, "-", lw=2, label=f"fitted adopters (m={params['m']:.0f}, p={params['p']:.4f}, q={params['q']:.4f})")
    ax.set_xlabel("t")
    ax.set_ylabel("adopters")
    ax.legend()
    ax.grid(True)
    return ax


def plot_cumulative_and_components(m: float, p: float, q: float, T: int = 52, dt: float = 1.0, ax=None):
    t = np.arange(0, T) * dt
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(12, 6))
    cum = cumulative_adopters(t, m, p, q)
    inst = adopters_at_time(t, m, p, q)
    innovators = m * p * (1 - bass_F(t, p, q))
    imitators = m * q * bass_F(t, p, q) * (1 - bass_F(t, p, q))
    ax.plot(t, cum, label="cumulative adopters")
    ax.plot(t, inst, label="new adopters (instantaneous)")
    ax.plot(t, innovators, "--", label="innovators")
    ax.plot(t, imitators, ":", label="imitators")
    ax.set_xlabel("t")
    ax.legend()
    ax.grid(True)
    return ax


# ---------------- Simple self-checks / demo --------------------------------


def _demo():
    logger.info("Running Bass model demo (no PyMC).")
    # True params
    T = 52
    true_m, true_p, true_q = 10000.0, 0.02, 0.35
    df = simulate_bass(T, true_m, true_p, true_q, noise_sd=25.0, seed=42)
    t = df["t"].values
    y = df["adopters"].values

    # Fit
    fit = fit_bass_nlls(t, y)
    logger.info("NLLS params: %s", fit["params"])

    # Bootstrap (fast for demo)
    boots = bootstrap_bass(t, y, n_boot=200, random_seed=1)
    if not boots.empty:
        ci_lower = boots.quantile(0.025)
        ci_upper = boots.quantile(0.975)
        logger.info("Bootstrap 95%% CI (m,p,q): lower=%s upper=%s", ci_lower.values, ci_upper.values)
    else:
        logger.info("No bootstrap replicates were successful.")

    # Plots
    fig, axs = plt.subplots(2, 1, figsize=(10, 10))
    plot_bass_fit(t, y, fit, ax=axs[0])
    plot_cumulative_and_components(fit["params"]["m"], fit["params"]["p"], fit["params"]["q"], T=T, ax=axs[1])
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    _demo()
