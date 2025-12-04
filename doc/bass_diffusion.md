# Bass Diffusion Module

This package (`app.products.popularity.bass_diffusion`) provides a production-ready implementation of the Bass diffusion model including parameter definitions, deterministic simulation, and calibration utilities.

## Quick Start

```python
from app.products.popularity.bass_diffusion import (
    BassModelParams,
    BassDiffusionModel,
    BassCalibrator,
)

params = BassModelParams(innovation=0.03, imitation=0.38, market_potential=150_000)
model = BassDiffusionModel(params)
forecast = model.simulate(horizon=36)

calibrator = BassCalibrator(time_points, observed_cumulative)
calibrated = calibrator.fit()
```

Refer to inline docstrings for additional options such as calibration constraints, weighting schemes, and exporting simulation results to pandas.
