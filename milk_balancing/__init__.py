"""milk_balancing — LP-based milk supply chain optimisation.

Quick start
-----------
>>> from milk_balancing import load_data, solve_scenario
>>> data = load_data()
>>> result = solve_scenario(data)
>>> print(f"Net total cost: €{result['total_cost']:,.0f}")
"""

from .data_loader import get_default_data, load_data, load_excel
from .solver import solve, solve_scenario

__all__ = [
    "load_data",
    "load_excel",
    "get_default_data",
    "solve",
    "solve_scenario",
]
