import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

PRICING_CONFIG = {
    'services': {
        'voice': {
            'anchor_price': 200,
            'anchor_rate': 13.3,
            'floor_rate': 6.0,
            'max_price': 10000,
            'unit_name': 'Minutes',
            'daily_points': [
                [100, 20.0], [150, 16.67], [175, 15.91], [200, 12.5], [220, 12.22],
                [230, 12.11], [300, 10.71], [450, 8.82], [540, 8.44], [750, 7.14], [800, 6.67]
            ],
            'weekly_points': [
                [300, 18.75], [420, 14.0], [525, 12.21], [650, 10.83], [750, 10.0],
                [840, 9.13], [935, 8.90], [1650, 7.5], [3520, 7.04], [5000, 6.25], [5390, 6.19]
            ],
            'decay_k': None
        },
        'data': {
            'anchor_price': 650,
            'anchor_rate': 0.42,
            'floor_rate': 0.2,
            'max_price': 10000,
            'unit_name': 'MB',
            'daily_points': [
                [100, 2.0], [190, 1.583], [220, 1.294], [290, 1.16], [650, 0.42]
            ],
            'decay_k': None
        },
        'sms': {
            'anchor_price': 50,
            'anchor_rate': 1.3,
            'floor_rate': 0.2,
            'max_price': 500,
            'unit_name': 'SMS',
            'decay_k': None
        }
    },
    'validity_premiums': {
        1: 0,
        2: 25,
        3: 50,
        7: 120,
        30: 235
    },
    'mixed_bundle_discounts': {
        1: 0,
        2: 10,
        3: 20
    },
    'btl_discounts': {
        'atl': 0,
        'diy_mode': -5,
        'promotion_mode':0,
        'btl_normal': 20,
        'btl_moderate': 30,
        'btl_aggressive': 40
    },
    'rounding_rules': {
        'data_round_to': 5
    },
    'minimums': {
        'price': {'voice': 100, 'data': 100},
        'volume': {'voice': 5, 'data': 50},
        'multi_service_volume': {'voice': 5, 'data': 50, 'sms': 0}
    },
    'promotion_mode_param': {
        'voice': {'starting_price': 150, 'ending_price': 2000,'discount':35,'validity':-1},
        'data': {'starting_price': 0, 'ending_price': 0,'discount':0,'validity':-1},
        'sms': {'starting_price': 0, 'ending_price': 0,'discount':0,'validity':-1},
    }
}