import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))

from dataclasses import dataclass, field


@dataclass
class ModelParams:
    growth_rate: float            = 0.03
    cannib_sensitivity: float     = 0.5
    price_elasticity: float       = 1.50
    similarity_threshold: float   = 0.05
    cannib_cap: float             = 0.25
    expected_new_market_pct: float = 0.5
    feature_weights: dict = field(default_factory=lambda: {
        "volume_mb":    1.0,
        "minutes":      1.0,
        "sms":          1.0,
        "price":        1.0,
        "validity_days": 0.5,   # generated has this, existing does not → down-weighted
    })
