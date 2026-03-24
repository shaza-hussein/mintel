import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

import math
import logging
from typing import Dict, List, Tuple, Any
from src.app.products.pricing.db_math import PricingMath

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


Point = Tuple[float, float]
Points = List[Point]

ServiceConfig = Dict[str, Any]
ServicesConfig = Dict[str, ServiceConfig]

PricingConfig = Dict[str, Any]
ServiceAllocations = Dict[str, float]
TargetVolumes = Dict[str, float]


class DynamicPricingEngine:

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config: Dict[str, Any] = config
        logger.info("Dynamic Pricing Engine init.")


    def calculate_volume_from_price(
        self,
        price: float,
        service: str,
        validity_days: int,
        num_services: int,
        offer_type: str,
        mbdf_per: float
    ) -> float:
        s_config: Dict[str, Any] = self.config['services'][service]

        mbdf: float = 1 - (
            mbdf_per
            * self.config['mixed_bundle_discounts'].get(2, 0)
            / 100.0
        )

        starting_price: float = self.config['promotion_mode_param'][service].get('starting_price', 0)
        ending_price: float = self.config['promotion_mode_param'][service].get('ending_price', 0)
        promo_val: int = self.config['promotion_mode_param'][service].get('validity', 0)

        if (
            num_services == 1
            and offer_type == 'promotion_mode'
            and price >= starting_price
            and price <= ending_price
            and (promo_val == -1 or promo_val == validity_days)
        ):
            tdf: float = 1 - (
                self.config['promotion_mode_param'][service]
                .get('discount', 0) / 100.0
            )

        else:
            tdf = 1 - (
                self.config['btl_discounts'].get(offer_type, 0) / 100.0
            )

        if s_config.get('decay_k') is None:
            s_config['decay_k'] = PricingMath.recalculate_decay(
                s_config['anchor_price'],
                s_config['anchor_rate'],
                s_config['floor_rate'],
                s_config['max_price']
            )

        final_er: float = 0

        if service == 'voice':
            points = (
                s_config['weekly_points']
                if validity_days == 7
                else s_config['daily_points']
            )
            last_price_point: float = points[-1][0]

            if price > last_price_point:
                k: float = s_config['decay_k']
                er_price: float = (
                    s_config['floor_rate']
                    + (points[-1][1] - s_config['floor_rate'])
                    * math.exp(-k * (price - last_price_point))
                )

            else:
                er_price = PricingMath.interpolate(price, points)

            final_er = (
                er_price
                if validity_days == 7
                else er_price * PricingMath.get_vpm(
                    validity_days,
                    self.config['validity_premiums']
                )
            )

        elif service == 'data':
            if price <= s_config['anchor_price']:
                er_price_base: float = PricingMath.interpolate(
                    price,
                    s_config['daily_points']
                )

            else:
                k: float = s_config['decay_k']
                er_price_base = (
                    s_config['floor_rate']
                    + (s_config['anchor_rate'] - s_config['floor_rate'])
                    * math.exp(-k * (price - s_config['anchor_price']))
                )

            final_er = er_price_base * PricingMath.get_vpm(
                validity_days,
                self.config['validity_premiums']
            )

        else:
            k: float = s_config['decay_k']
            er_price: float = (
                s_config['floor_rate']
                + (s_config['anchor_rate'] - s_config['floor_rate'])
                * math.exp(-k * (price - s_config['anchor_price']))
            )

            final_er = er_price * PricingMath.get_vpm(
                validity_days,
                self.config['validity_premiums']
            )

        ultimate_er: float = final_er * mbdf * tdf

        return price / ultimate_er if ultimate_er > 0 else 0


    def calculate_bundle(
        self,
        service_allocations: Dict[str, float],
        validity_days: int,
        offer_type: str
    ) -> Dict[str, Dict[str, str]]:
        active_services: Dict[str, float] = {
            s: p for s, p in service_allocations.items() if p > 0
        }

        num_services: int = len(active_services)
        sorted_keys = sorted(active_services, key=active_services.get)

        smallest_ser: Dict[str, int] = {
            k: (1 if i < num_services - 1 else 0)
            for i, k in enumerate(sorted_keys)
        }

        final_offer: Dict[str, Dict[str, str]] = {'units': {}}

        for service, price in active_services.items():
            units: float = self.calculate_volume_from_price(
                price,
                service,
                validity_days,
                num_services,
                offer_type,
                smallest_ser[service]
            )

            s_config = self.config['services'][service]

            if service == 'data':
                rounded_units: int = (
                    math.ceil(
                        units
                        / self.config['rounding_rules']['data_round_to']
                    )
                    * self.config['rounding_rules']['data_round_to']
                )

            else:
                rounded_units = round(units)

            final_offer['units'][service] = f"{rounded_units} {s_config['unit_name']}"

        return final_offer


    def find_price_for_volume(
        self,
        service: str,
        target_volume: float,
        validity_days: int,
        offer_type: str,
        num_services: int,
        mbdf_per: float
    ) -> float:
        s_config = self.config['services'][service]

        low_price: float = 0.01
        high_price: float = s_config['max_price']

        for _ in range(100):
            guess_price: float = (low_price + high_price) / 2
            volume: float = self.calculate_volume_from_price(
                guess_price,
                service,
                validity_days,
                num_services,
                offer_type,
                mbdf_per
            )

            if service == 'data':
                rounded_units: int = (
                    math.ceil(
                        volume
                        / self.config['rounding_rules']['data_round_to']
                    )
                    * self.config['rounding_rules']['data_round_to']
                )

            else:
                rounded_units = round(volume)

            if rounded_units < target_volume:
                low_price = guess_price

            else:
                high_price = guess_price

            if (high_price - low_price) < 0.001:
                break

        return high_price


    def calculate_price_from_volume(
        self,
        target_volumes: Dict[str, float],
        validity_days: int,
        offer_type: str
    ) -> Dict[str, Any]:
        active_services: Dict[str, float] = {
            s: v for s, v in target_volumes.items() if v > 0
        }

        num_services: int = len(active_services)
        service_prices: Dict[str, float] = {
            service: active_services[service]
            * self.config['services'][service]['anchor_rate']
            for service in active_services
        }

        sorted_keys = sorted(service_prices, key=service_prices.get)
        smallest_ser: Dict[str, int] = {
            k: (1 if i < num_services - 1 else 0)
            for i, k in enumerate(sorted_keys)
        }

        if num_services > 1:
            for service, volume in active_services.items():
                min_vol = self.config['minimums']['multi_service_volume'].get(service)

                if min_vol and volume < min_vol:
                    return {
                        'error': f"Error: Minimum for {service} in a multi-buy is {min_vol}."
                    }

        individual_prices: Dict[str, float] = {}
        sub_total_price: float = 0
        for service, volume in active_services.items():
            price: float = self.find_price_for_volume(
                service,
                volume,
                validity_days,
                offer_type,
                num_services,
                smallest_ser[service]
            )

            min_price = self.config['minimums']['price'].get(service)
            final_price: float = price if min_price is None or price >= min_price else min_price
            individual_prices[service] = final_price
            sub_total_price += final_price

        final_total_price: int = round(sub_total_price)

        return {
            'calculated_price': final_total_price,
            'individual_prices': individual_prices
        }