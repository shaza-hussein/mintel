import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))


import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.app.products.pricing.config import PRICING_CONFIG
from src.app.products.pricing.db_math import PricingMath


Point = Tuple[float, float]


class PricingVisualizationData:
    DEFAULT_VALIDITIES = [1, 2, 7, 30]
    DEFAULT_N_POINTS = 400

    VALIDITY_COLORS = {
        1: "#2563eb",
        2: "#16a34a",
        7: "#dc2626",
        30: "#7c3aed",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or PRICING_CONFIG

    def build_all_service_charts(
        self,
        validities: Optional[Sequence[int]] = None,
        n_points: int = DEFAULT_N_POINTS,
    ) -> Dict[str, Any]:
        return {
            "charts": {
                service: self.build_service_chart(service, validities, n_points)
                for service in self.config["services"]
            }
        }

    def build_service_chart(
        self,
        service: str,
        validities: Optional[Sequence[int]] = None,
        n_points: int = DEFAULT_N_POINTS,
    ) -> Dict[str, Any]:
        if service not in self.config["services"]:
            raise ValueError(f"Unknown pricing service: {service}")

        validities = list(validities or self.DEFAULT_VALIDITIES)
        service_config = self.config["services"][service]

        traces: List[Dict[str, Any]] = []
        shapes: List[Dict[str, Any]] = []
        annotations: List[Dict[str, Any]] = []

        for validity in validities:
            color = self.VALIDITY_COLORS.get(validity, "#111827")
            rows = self._build_curve_rows(service, validity, n_points)

            for mode, dash in (("interpolation", "solid"), ("decay", "dash")):
                part = [row for row in rows if row["mode"] == mode]
                if not part:
                    continue

                traces.append({
                    "type": "scatter",
                    "mode": "lines",
                    "name": f"{validity}d | {mode}",
                    "x": [row["price"] for row in part],
                    "y": [row["effective_rate"] for row in part],
                    "line": {
                        "color": color,
                        "width": 3,
                        "dash": dash,
                    },
                    "customdata": [
                        [row["vpm"], row["rule"]]
                        for row in part
                    ],
                    "hovertemplate": (
                        "<b>%{fullData.name}</b><br>"
                        "Price: NGN %{x:,.0f}<br>"
                        "Effective rate: %{y:.4f}<br>"
                        "Validity multiplier: %{customdata[0]:.2f}x<br>"
                        "Rule: %{customdata[1]}"
                        "<extra></extra>"
                    ),
                })

            points, vpm, _ = self._get_curve_points_and_vpm(service, validity)

            if points:
                traces.append({
                    "type": "scatter",
                    "mode": "markers",
                    "name": f"{validity}d anchor points",
                    "showlegend": False,
                    "x": [price for price, _ in points],
                    "y": [rate * vpm for _, rate in points],
                    "marker": {
                        "color": color,
                        "size": 8,
                        "symbol": "circle",
                        "line": {
                            "color": "white",
                            "width": 1,
                        },
                    },
                    "hovertemplate": (
                        "<b>Anchor / calibration point</b><br>"
                        f"Service: {service}<br>"
                        f"Validity: {validity} days<br>"
                        "Price: NGN %{x:,.0f}<br>"
                        "Effective rate: %{y:.4f}"
                        "<extra></extra>"
                    ),
                })

                switch_price = points[-1][0]
                shapes.append({
                    "type": "line",
                    "xref": "x",
                    "yref": "paper",
                    "x0": switch_price,
                    "x1": switch_price,
                    "y0": 0,
                    "y1": 1,
                    "line": {
                        "color": color,
                        "dash": "dot",
                        "width": 1,
                    },
                    "opacity": 0.35,
                })

        traces.append({
            "type": "scatter",
            "mode": "markers+text",
            "name": "config anchor",
            "showlegend": False,
            "x": [service_config["anchor_price"]],
            "y": [service_config["anchor_rate"]],
            "text": ["config anchor"],
            "textposition": "top center",
            "marker": {
                "color": "black",
                "size": 12,
                "symbol": "diamond",
            },
            "hovertemplate": (
                "<b>Config anchor</b><br>"
                f"Service: {service}<br>"
                "Anchor price: NGN %{x:,.0f}<br>"
                "Anchor rate: %{y:.4f}"
                "<extra></extra>"
            ),
        })

        shapes.append({
            "type": "line",
            "xref": "paper",
            "yref": "y",
            "x0": 0,
            "x1": 1,
            "y0": service_config["floor_rate"],
            "y1": service_config["floor_rate"],
            "line": {
                "color": "black",
                "dash": "dash",
                "width": 1,
            },
            "opacity": 0.55,
        })

        annotations.append({
            "xref": "paper",
            "yref": "y",
            "x": 1,
            "y": service_config["floor_rate"],
            "xanchor": "right",
            "yanchor": "bottom",
            "showarrow": False,
            "text": f"floor = {service_config['floor_rate']}",
        })

        return {
            "service": service,
            "data": traces,
            "layout": {
                "title": {
                    "text": (
                        f"{service.upper()} Pricing Algorithm Curve<br>"
                        "<sup>Solid = interpolation | Dashed = decay | "
                        "Dots = anchor points | Black dashed = floor</sup>"
                    )
                },
                "template": "plotly_white",
                "height": 650,
                "hovermode": "closest",
                "legend": {
                    "title": {
                        "text": "Validity / method"
                    }
                },
                "xaxis": {
                    "title": {
                        "text": "Price, NGN"
                    }
                },
                "yaxis": {
                    "title": {
                        "text": f"Effective rate, NGN / {service_config['unit_name']}"
                    }
                },
                "shapes": shapes,
                "annotations": annotations,
            },
            "config": {
                "responsive": True,
                "displaylogo": False,
            },
            "meta": {
                "validities": validities,
                "n_points": n_points,
                "unit_name": service_config["unit_name"],
                "anchor_price": service_config["anchor_price"],
                "anchor_rate": service_config["anchor_rate"],
                "floor_rate": service_config["floor_rate"],
                "max_price": service_config["max_price"],
            },
        }

    def _build_curve_rows(
        self,
        service: str,
        validity: int,
        n_points: int,
    ) -> List[Dict[str, Any]]:
        min_price, max_price = self._get_price_range(service)
        prices = self._linspace(min_price, max_price, n_points)

        rows = []
        for price in prices:
            effective_rate, mode, vpm, rule = self._calculate_effective_rate(
                service,
                price,
                validity,
            )

            rows.append({
                "service": service,
                "validity": validity,
                "price": price,
                "effective_rate": effective_rate,
                "mode": mode,
                "vpm": vpm,
                "rule": rule,
            })

        return rows

    def _calculate_effective_rate(
        self,
        service: str,
        price: float,
        validity: int,
    ) -> Tuple[float, str, float, str]:
        service_config = self.config["services"][service]
        decay_k = self._get_decay_k(service)
        points, vpm, rule = self._get_curve_points_and_vpm(service, validity)

        if service == "sms":
            base_rate = (
                service_config["floor_rate"]
                + (service_config["anchor_rate"] - service_config["floor_rate"])
                * math.exp(-decay_k * (price - service_config["anchor_price"]))
            )
            return base_rate * vpm, "decay", vpm, rule

        if not points:
            raise ValueError(f"No curve points configured for service: {service}")

        last_price, last_rate = points[-1]

        if price <= last_price:
            base_rate = PricingMath.interpolate(price, points)
            mode = "interpolation"
        else:
            base_rate = (
                service_config["floor_rate"]
                + (last_rate - service_config["floor_rate"])
                * math.exp(-decay_k * (price - last_price))
            )
            mode = "decay"

        return base_rate * vpm, mode, vpm, rule

    def _get_curve_points_and_vpm(
        self,
        service: str,
        validity: int,
    ) -> Tuple[Optional[List[Point]], float, str]:
        service_config = self.config["services"][service]

        if service == "voice":
            if validity == 7 and "weekly_points" in service_config:
                return (
                    self._normalize_points(service_config["weekly_points"]),
                    1.0,
                    "native 7-day voice curve",
                )

            return (
                self._normalize_points(service_config["daily_points"]),
                PricingMath.get_vpm(validity, self.config["validity_premiums"]),
                "daily voice curve + validity premium",
            )

        if service == "data":
            return (
                self._normalize_points(service_config["daily_points"]),
                PricingMath.get_vpm(validity, self.config["validity_premiums"]),
                "daily data curve + validity premium",
            )

        return (
            None,
            PricingMath.get_vpm(validity, self.config["validity_premiums"]),
            "decay only + validity premium",
        )

    def _get_decay_k(self, service: str) -> float:
        service_config = self.config["services"][service]

        if service_config.get("decay_k") is not None:
            return service_config["decay_k"]

        return PricingMath.recalculate_decay(
            service_config["anchor_price"],
            service_config["anchor_rate"],
            service_config["floor_rate"],
            service_config["max_price"],
        )

    def _get_price_range(self, service: str) -> Tuple[float, float]:
        service_config = self.config["services"][service]

        if service == "voice":
            all_points = (
                service_config.get("daily_points", [])
                + service_config.get("weekly_points", [])
            )
            min_price = min(point[0] for point in all_points)
        elif service == "data":
            min_price = service_config["daily_points"][0][0]
        else:
            min_price = max(1, service_config["anchor_price"] * 0.2)

        return float(min_price), float(service_config["max_price"])

    @staticmethod
    def _normalize_points(points: Sequence[Sequence[float]]) -> List[Point]:
        return [(float(price), float(rate)) for price, rate in points]

    @staticmethod
    def _linspace(start: float, stop: float, count: int) -> List[float]:
        if count <= 1:
            return [float(start)]

        step = (stop - start) / (count - 1)
        return [float(start + step * index) for index in range(count)]