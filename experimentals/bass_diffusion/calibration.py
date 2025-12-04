"""Calibration utilities for the Bass diffusion model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import least_squares

from .model import BassDiffusionModel
from .parameters import BassModelParams


@dataclass
class BassCalibrationResult:
    """Holds output of the calibration step."""

    params: BassModelParams
    success: bool
    cost: float
    message: str


class BassCalibrator:
    """Estimate Bass diffusion parameters from observed adoption curves."""

    def __init__(
        self,
        time: Sequence[float],
        observations: Sequence[float],
        observation_type: str = "cumulative",
        weights: Optional[Sequence[float]] = None,
    ) -> None:
        self.time = np.asarray(time, dtype=float)
        self.observations = np.asarray(observations, dtype=float)
        if self.time.shape != self.observations.shape:
            raise ValueError("time and observations must share shape")
        if not np.all(np.diff(self.time) >= 0):
            raise ValueError("time values must be sorted ascending")
        if observation_type not in {"cumulative", "incremental"}:
            raise ValueError("observation_type must be 'cumulative' or 'incremental'")
        self.observation_type = observation_type
        if weights is None:
            self.weights = np.ones_like(self.time)
        else:
            weights_arr = np.asarray(weights, dtype=float)
            if weights_arr.shape != self.time.shape:
                raise ValueError("weights must match time shape")
            self.weights = weights_arr

    def _initial_guess(self) -> Tuple[float, float, float]:
        if self.observation_type == "cumulative":
            target = float(self.observations[-1])
        else:
            target = float(self.observations.sum())
        market = max(target * 1.2, target + 1e-3)
        return 0.03, 0.38, market

    def fit(
        self,
        initial_guess: Optional[Tuple[float, float, float]] = None,
        bounds: Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = None,
        launch_time: float = 0.0,
        regularization: Optional[Tuple[float, Sequence[float]]] = None,
    ) -> BassCalibrationResult:
        guess = initial_guess or self._initial_guess()
        if self.observation_type == "cumulative":
            min_market = float(self.observations[-1])
        else:
            min_market = float(self.observations.sum())
        lower = np.array((1e-5, 0.0, max(min_market, 1.0)), dtype=float)
        upper = np.array((1.0, 1.0, max(min_market * 100.0, min_market + 1.0)), dtype=float)
        if bounds is not None:
            lower, upper = (np.asarray(b, dtype=float) for b in bounds)  # type: ignore
        if regularization is None:
            reg_weight = 0.0
            reg_target = np.zeros(3, dtype=float)
        else:
            reg_weight = float(regularization[0])
            reg_target = np.asarray(regularization[1], dtype=float)
            if reg_target.shape != (3,):
                raise ValueError("regularization target must have length 3")

        def residual(theta: np.ndarray) -> np.ndarray:
            params = BassModelParams(theta[0], theta[1], theta[2], launch_time)
            model = BassDiffusionModel(params)
            if self.observation_type == "cumulative":
                prediction = model.closed_form_cumulative(self.time)
            else:
                prediction = model.incremental(self.time)
            mismatch = (prediction - self.observations) * self.weights
            if reg_weight:
                mismatch = np.concatenate((mismatch, reg_weight * (theta - reg_target)))
            return mismatch

        result = least_squares(
            residual,
            x0=np.asarray(guess, dtype=float),
            bounds=(lower, upper),
            method="trf",
        )
        params = BassModelParams(
            innovation=float(result.x[0]),
            imitation=float(result.x[1]),
            market_potential=float(result.x[2]),
            launch_time=launch_time,
        )
        return BassCalibrationResult(
            params=params,
            success=result.success,
            cost=result.cost,
            message=result.message,
        )
