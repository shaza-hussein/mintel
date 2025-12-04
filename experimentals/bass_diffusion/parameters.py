"""Parameter definitions for the Bass diffusion model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple


@dataclass
class BassModelParams:
    """Encapsulates diffusion parameters.

    Attributes
    ----------
    innovation: float
        Coefficient of innovation (p) capturing external influence.
    imitation: float
        Coefficient of imitation (q) capturing word-of-mouth effects.
    market_potential: float
        Total addressable market size (m) expressed in adopters or units.
    launch_time: float
        Time origin for the launch measured in the same units as model time.
    """

    innovation: float
    imitation: float
    market_potential: float
    launch_time: float = 0.0

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.innovation <= 0:
            raise ValueError("innovation coefficient must be positive")
        if self.imitation < 0:
            raise ValueError("imitation coefficient cannot be negative")
        if self.market_potential <= 0:
            raise ValueError("market_potential must be positive")
        if not self.innovation + self.imitation:
            raise ValueError("innovation + imitation must be > 0")
        if self.launch_time < 0:
            raise ValueError("launch_time cannot be negative")

    def as_tuple(self) -> Tuple[float, float, float, float]:
        """Return raw parameter tuple useful for optimization routines."""

        return self.innovation, self.imitation, self.market_potential, self.launch_time

    @classmethod
    def from_iterable(cls, values: Iterable[float]) -> "BassModelParams":
        items = list(values)
        if len(items) < 3:
            raise ValueError("values must contain at least innovation, imitation, market_potential")
        innovation, imitation, market_potential, *rest = items
        launch_time = rest[0] if rest else 0.0
        return cls(
            innovation=float(innovation),
            imitation=float(imitation),
            market_potential=float(market_potential),
            launch_time=float(launch_time),
        )
