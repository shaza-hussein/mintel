"""Core Bass diffusion model implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np

from .parameters import BassModelParams


@dataclass
class SimulationResult:
    """Container for simulation outputs."""

    time: np.ndarray
    incremental_adopters: np.ndarray
    cumulative_adopters: np.ndarray
    adoption_rate: np.ndarray

    def to_frame(self):  # type: ignore[override]
        """Return a pandas DataFrame if pandas is installed."""

        try:
            import pandas as pd  # type: ignore
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("pandas is required for to_frame()") from exc

        return pd.DataFrame(
            {
                "time": self.time,
                "incremental": self.incremental_adopters,
                "cumulative": self.cumulative_adopters,
                "rate": self.adoption_rate,
            }
        )


class BassDiffusionModel:
    """Deterministic Bass diffusion simulator."""

    def __init__(self, params: BassModelParams, step: float = 1.0) -> None:
        if step <= 0:
            raise ValueError("step must be positive")
        self.params = params
        self.step = step

    @property
    def innovation(self) -> float:
        return self.params.innovation

    @property
    def imitation(self) -> float:
        return self.params.imitation

    @property
    def market_potential(self) -> float:
        return self.params.market_potential

    def hazard(self, cumulative: Iterable[float] | np.ndarray) -> np.ndarray:
        """Return instantaneous adoption hazard for given cumulative adopters."""

        cumulative_arr = np.asarray(cumulative, dtype=float)
        saturation = np.clip(cumulative_arr / self.market_potential, 0.0, 1.0)
        return self.innovation + self.imitation * saturation

    def _normalize_time(self, time: Iterable[float]) -> np.ndarray:
        shifted = np.asarray(time, dtype=float) - self.params.launch_time
        return np.clip(shifted, 0.0, None)

    def closed_form_cumulative(self, time: Iterable[float]) -> np.ndarray:
        t = self._normalize_time(time)
        p, q, m = self.innovation, self.imitation, self.market_potential
        exp_term = np.exp(-(p + q) * t)
        denom = 1.0 + (q / p) * exp_term
        cumulative = m * (1 - exp_term) / denom
        return np.clip(cumulative, 0.0, m)

    def density(self, time: Iterable[float]) -> np.ndarray:
        t = self._normalize_time(time)
        p, q, m = self.innovation, self.imitation, self.market_potential
        exp_term = np.exp(-(p + q) * t)
        numerator = (p + q) ** 2 * exp_term
        denom = p * (1 + (q / p) * exp_term) ** 2
        return m * numerator / denom

    def incremental(self, time: Iterable[float]) -> np.ndarray:
        time_arr = np.asarray(time, dtype=float)
        if not np.all(np.diff(time_arr) >= 0):
            raise ValueError("time points must be sorted ascending for incremental output")
        cumulative = self.closed_form_cumulative(time_arr)
        incremental = np.zeros_like(cumulative)
        incremental[1:] = np.diff(cumulative)
        return incremental

    def simulate(
        self,
        horizon: float,
        initial_adopters: float = 0.0,
        num_steps: Optional[int] = None,
    ) -> SimulationResult:
        if horizon <= 0:
            raise ValueError("horizon must be positive")
        total_steps = num_steps or int(np.ceil(horizon / self.step)) + 1
        time = np.linspace(0.0, horizon, total_steps)
        cumulative = np.zeros_like(time)
        incremental = np.zeros_like(time)
        adoption_rate = np.zeros_like(time)
        cumulative[0] = initial_adopters

        for idx in range(1, total_steps):
            prev = cumulative[idx - 1]
            hazard = float(self.hazard(prev))
            adoption_rate[idx] = hazard * (self.market_potential - prev)
            delta = adoption_rate[idx] * (time[idx] - time[idx - 1])
            incremental[idx] = max(delta, 0.0)
            cumulative[idx] = min(prev + incremental[idx], self.market_potential)

        return SimulationResult(time, incremental, cumulative, adoption_rate)

    def predict(self, time_points: Iterable[float], output: str = "cumulative") -> np.ndarray:
        if output not in {"cumulative", "incremental"}:
            raise ValueError("output must be 'cumulative' or 'incremental'")
        if output == "cumulative":
            return self.closed_form_cumulative(time_points)
        return self.incremental(time_points)
