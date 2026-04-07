"""Tests for milk_balancing.data_loader.

These tests ensure the dataset is consistent and ready for the LP solver.
They also demonstrate good practice: test your inputs, not just your outputs.
"""

from milk_balancing.constants import NK, NP, NS, T
from milk_balancing.data_loader import load_data, load_excel

# ── Shape tests ───────────────────────────────────────────────────────────────


class TestDefaultDataShapes:
    """Every array in the default dataset must have the expected shape."""

    def test_production_need_shape(self, default_data):
        assert default_data["R"].shape == (NP, T)

    def test_farm_volumes_shape(self, default_data):
        assert default_data["V"].shape == (NP, T)

    def test_farm_prices_shape(self, default_data):
        assert default_data["c_farm"].shape == (NP, T)

    def test_spot_prices_shape(self, default_data):
        assert default_data["c_spot"].shape == (NS, T)

    def test_sales_prices_shape(self, default_data):
        assert default_data["r_sales"].shape == (NK, T)

    def test_transport_costs_has_six_routes(self, default_data):
        assert len(default_data["TC"]) == 6


# ── Value sanity checks ───────────────────────────────────────────────────────


class TestDefaultDataValues:
    """Business-logic sanity checks on the default dataset."""

    def test_all_volumes_positive(self, default_data):
        assert (default_data["V"] > 0).all(), "Farm volumes must be positive"

    def test_all_demand_positive(self, default_data):
        assert (default_data["R"] > 0).all(), "Production need must be positive"

    def test_spot_prices_above_farm_prices_on_average(self, default_data):
        """On average, spot market prices exceed farm contract prices.

        This is the core economic incentive: farms are the preferred source,
        and the LP only buys spot to cover deficits.  Note that cheap spot
        suppliers (S2) can occasionally dip below expensive farm contracts
        (Farm C) in summer months — the model handles this correctly.
        """
        mean_cheapest_spot = default_data["c_spot"].min(axis=0).mean()
        mean_most_expensive_farm = default_data["c_farm"].max(axis=0).mean()
        assert mean_cheapest_spot > mean_most_expensive_farm, (
            f"Mean cheapest spot ({mean_cheapest_spot:.1f} €/1000L) should exceed "
            f"mean most expensive farm ({mean_most_expensive_farm:.1f} €/1000L)"
        )

    def test_transport_costs_positive(self, default_data):
        """All transport costs must be strictly positive (no free transfers by default)."""
        for route, cost in default_data["TC"].items():
            assert cost > 0, f"Transport cost for route {route} must be positive"

    def test_farm_covers_significant_fraction_of_demand(self, default_data):
        """Farm supply should cover a meaningful share of total demand.

        If farm supply were near zero the LP would trivially buy everything spot,
        which would be an unrealistic scenario for a planning model.
        """
        total_farm = default_data["V"].sum()
        total_demand = default_data["R"].sum()
        farm_coverage = total_farm / total_demand
        assert farm_coverage > 0.5, (
            f"Farm supply covers only {farm_coverage:.1%} of total demand; expected > 50%"
        )

    def test_p3_is_undersupplied_by_farm(self, default_data):
        """Plant 3's farm (C) covers less than 100% of P3 demand in every month.

        This is the root cause of all S3 spot purchases and inter-plant transfers.
        """
        V_p3 = default_data["V"][2]
        R_p3 = default_data["R"][2]
        assert (V_p3 < R_p3).all(), (
            "Farm C should never fully cover P3 demand; "
            "the model depends on this chronic deficit to exercise spot and transfers"
        )


# ── Excel loader ──────────────────────────────────────────────────────────────


class TestExcelLoader:
    def test_missing_file_returns_none(self):
        result = load_excel("/nonexistent/path/to/file.xlsx")
        assert result is None

    def test_load_data_falls_back_to_defaults_when_file_missing(self):
        """load_data() must never raise — it returns defaults if Excel is absent."""
        data = load_data("/nonexistent/path/to/file.xlsx")
        assert data is not None
        assert "R" in data

    def test_load_data_from_real_file(self):
        """If the dataset Excel file is present, verify it loads successfully."""
        data = load_data()  # uses default path data/milk_planning_dataset.xlsx
        assert data is not None
        assert data["R"].shape == (NP, T)
