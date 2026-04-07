"""Shared pytest fixtures for the milk_balancing test suite."""

import pytest

from milk_balancing.data_loader import get_default_data
from milk_balancing.solver import solve_scenario


@pytest.fixture(scope="session")
def default_data():
    """Base planning dataset (built-in defaults, no file I/O)."""
    return get_default_data()


@pytest.fixture(scope="session")
def default_result(default_data):
    """Optimal LP solution for the default dataset."""
    return solve_scenario(default_data)
