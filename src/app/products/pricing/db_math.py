import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

import math
import logging
from typing import List, Tuple, Dict

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

Point = Tuple[float, float]
Points = List[Point]
PremiumConfig = Dict[int, float]


class PricingMath:

    @staticmethod
    def recalculate_decay(
        anchor_price: float,
        anchor_rate: float,
        floor_rate: float,
        max_price: float
    ) -> float:
        if anchor_rate <= floor_rate or max_price <= anchor_price:
            return math.nan
    
        rate_at_max = floor_rate + 0.01
        numerator = math.log(
            (rate_at_max - floor_rate) /
            (anchor_rate - floor_rate)
        )
        denominator = max_price - anchor_price

        return -numerator / denominator


    @staticmethod
    def interpolate(
        x: float,
        points: Points
    ) -> float:
        # Handle left boundary: extrapolate using initial slope
        if x < points[0][0]:
            x1, y1 = points[0]
            x2, y2 = points[1]
            slope = (y2 - y1) / (x2 - x1) if (x2 - x1) != 0 else 0

            return y1 + (x - x1) * slope
        
        # Find containing interval via linear scan
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            if x1 <= x < x2:
                return y1 + (x - x1) * (y2 - y1) / (x2 - x1)
            
        # Right boundary: return last known value
        return points[-1][1]


    @staticmethod
    def get_vpm(
        validity_days: int,
        premiums_config: PremiumConfig
    ) -> float:
        points = sorted(
            [(int(k), v) for k, v in premiums_config.items()]
        )

        premium = PricingMath.interpolate(validity_days, points)

        return 1 + premium / 100.0