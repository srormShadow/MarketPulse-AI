"""Service package for business logic modules."""

from marketpulse.services.discount_simulation import (
    compute_simulation_deltas,
    compute_supply_stability_index,
    simulate_discounted_forecast,
)

__all__ = [
    "simulate_discounted_forecast",
    "compute_simulation_deltas",
    "compute_supply_stability_index",
]
