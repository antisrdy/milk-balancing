"""Tests for milk_balancing.lp_model.

These tests verify the LP problem structure before it is ever solved.
Catching a mis-specified matrix early (wrong shape, wrong coefficient)
is much easier than debugging an unexpected optimal solution.
"""

import numpy as np
import pytest

from milk_balancing.constants import NK, NP, NS, ROUTES, T
from milk_balancing.lp_model import (
    N_VARS,
    build_equality_constraints,
    build_inequality_constraints,
    idx_e,
    idx_u,
    idx_x,
    spot_transport_matrix,
)

# ── Variable count and index ranges ───────────────────────────────────────────


class TestVariableCount:
    def test_total_variable_count(self):
        """The model has exactly 252 decision variables."""
        assert N_VARS == 252

    def test_x_variable_range(self):
        """Spot-purchase variables occupy indices 0 … 107."""
        assert idx_x(0, 0, 0) == 0
        assert idx_x(NP - 1, NS - 1, T - 1) == 107

    def test_u_variable_range(self):
        """Transfer variables occupy indices 108 … 179."""
        assert idx_u(ROUTES[0], 0) == 108
        assert idx_u(ROUTES[-1], T - 1) == 179

    def test_e_variable_range(self):
        """Excess-sales variables occupy indices 180 … 251."""
        assert idx_e(0, 0, 0) == 180
        assert idx_e(NP - 1, NK - 1, T - 1) == 251

    def test_no_index_overlaps(self):
        """Every decision variable must have a unique flat index."""
        indices = set()
        for p in range(NP):
            for s in range(NS):
                for t in range(T):
                    indices.add(idx_x(p, s, t))
        for r in ROUTES:
            for t in range(T):
                indices.add(idx_u(r, t))
        for p in range(NP):
            for k in range(NK):
                for t in range(T):
                    indices.add(idx_e(p, k, t))

        assert len(indices) == N_VARS, (
            f"Expected {N_VARS} unique indices, got {len(indices)}. "
            "Index collision in variable layout."
        )


# ── Spot transport matrix ──────────────────────────────────────────────────────


class TestSpotTransportMatrix:
    @pytest.fixture
    def tc(self):
        return {
            (0, 1): 80.0,
            (1, 0): 80.0,
            (1, 2): 60.0,
            (2, 1): 60.0,
            (0, 2): 130.0,
            (2, 0): 130.0,
        }

    def test_local_suppliers_have_zero_surcharge(self, tc):
        """Buying from a co-located supplier costs no extra transport."""
        st = spot_transport_matrix(tc)
        assert st[0, 0] == 0.0  # P0 buys S0 (local)
        assert st[1, 1] == 0.0  # P1 buys S1 (local)
        assert st[2, 2] == 0.0  # P2 buys S2 (local)

    def test_remote_purchases_add_transport(self, tc):
        """Buying from a remote supplier includes inter-plant transport cost."""
        st = spot_transport_matrix(tc)
        assert st[1, 0] == tc[(1, 0)]  # P1 buys S0 (near P0): pays P0→P1 cost
        assert st[0, 2] == tc[(0, 2)]  # P0 buys S2 (near P2): pays P2→P0 cost

    def test_matrix_shape(self, tc):
        st = spot_transport_matrix(tc)
        assert st.shape == (NP, NS)

    def test_matrix_non_negative(self, tc):
        st = spot_transport_matrix(tc)
        assert (st >= 0).all()


# ── LP matrix dimensions ───────────────────────────────────────────────────────


class TestConstraintMatrices:
    @pytest.fixture
    def simple_data(self, default_data):
        return default_data

    def test_equality_matrix_shape(self, simple_data):
        """Balance constraints: one row per (plant, month) pair."""
        A_eq, b_eq = build_equality_constraints(simple_data["R"], simple_data["V"])
        assert A_eq.shape == (NP * T, N_VARS)
        assert b_eq.shape == (NP * T,)

    def test_inequality_matrix_shape(self):
        """S3 capacity constraints: one row per month."""
        A_ub, b_ub = build_inequality_constraints(s3_cap=150_000.0)
        assert A_ub.shape == (T, N_VARS)
        assert b_ub.shape == (T,)

    def test_s3_cap_rhs_matches_parameter(self):
        cap = 200_000.0
        _, b_ub = build_inequality_constraints(s3_cap=cap)
        assert (b_ub == cap).all()

    def test_equality_rhs_is_net_deficit(self, simple_data):
        """b_eq[p*T + t] must equal R[p,t] - V[p,t] (net deficit each plant/month)."""
        R, V = simple_data["R"], simple_data["V"]
        _, b_eq = build_equality_constraints(R, V)
        for p in range(NP):
            for t in range(T):
                expected = R[p, t] - V[p, t]
                actual = b_eq[p * T + t]
                assert abs(actual - expected) < 1e-6, (
                    f"b_eq mismatch at P{p + 1}, month {t}: "
                    f"expected {expected:.0f}, got {actual:.0f}"
                )

    def test_each_balance_row_sums_to_zero_at_optimum(self, simple_data, default_result):
        """Verify A_eq @ x_sol = b_eq (balance constraints are satisfied)."""
        R, V = default_result["R"], default_result["V"]
        A_eq, b_eq = build_equality_constraints(R, V)

        # Reconstruct flat solution vector from result arrays
        x_flat = np.zeros(N_VARS)
        for p in range(NP):
            for s in range(NS):
                for t in range(T):
                    x_flat[idx_x(p, s, t)] = default_result["x_sol"][p, s, t]
        for r in ROUTES:
            for t in range(T):
                x_flat[idx_u(r, t)] = default_result["u_sol"][r][t]
        for p in range(NP):
            for k in range(NK):
                for t in range(T):
                    x_flat[idx_e(p, k, t)] = default_result["e_sol"][p, k, t]

        residual = np.abs(A_eq @ x_flat - b_eq)
        assert residual.max() < 1.0, (
            f"Balance constraint violated — max residual: {residual.max():.2f} L"
        )
