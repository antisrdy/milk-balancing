"""LP solver for the milk supply chain optimisation problem.

Public API
----------
solve(R, V, c_farm, c_spot, r_sales, TC, s3_cap, cap_headroom_pct)
    Core solver — takes pre-processed numpy arrays.

solve_scenario(data, demand_mult, spot_mult, farm_vol_mult, s3_cap, cap_headroom_pct)
    Convenience wrapper — applies scalar/array multipliers to a base data dict.
"""

import numpy as np
from scipy.optimize import linprog

from .constants import MONTHS, NK, NP, NS, ROUTES, T
from .lp_model import (
    N_VARS,
    build_equality_constraints,
    build_inequality_constraints,
    build_objective,
    idx_e,
    idx_u,
    idx_x,
    spot_transport_matrix,
)


def solve(
    R: np.ndarray,
    V: np.ndarray,
    c_farm: np.ndarray,
    c_spot: np.ndarray,
    r_sales: np.ndarray,
    TC: dict,
    s3_cap: float = 150_000.0,
    cap_headroom_pct: float = 5.0,
) -> dict:
    """Build and solve the milk supply chain LP.

    Parameters
    ----------
    R                : (NP, T) production need per plant per month [L]
    V                : (NP, T) farm contracted volume per plant per month [L]
    c_farm           : (NP, T) farm contract price [€/1000L]  (cost reporting only)
    c_spot           : (NS, T) spot market price per supplier per month [€/1000L]
    r_sales          : (NK, T) selling price per customer per month [€/1000L]
    TC               : dict mapping route (i, j) → transport cost [€/1000L]
    s3_cap           : monthly S3 supply cap across all plants [L]
    cap_headroom_pct : plant capacity headroom above peak demand [%]

    Returns
    -------
    dict with solution arrays and cost breakdown,
    or {'error': [str, ...]} if the problem is infeasible.

    Result keys
    -----------
    x_sol     : (NP, NS, T)  spot purchases
    u_sol     : dict route → (T,)  transfer volumes
    e_sol     : (NP, NK, T)  excess sales
    duals_eq  : (NP, T)  shadow prices for balance constraints [€/L]
    duals_s3  : (T,)    shadow prices for S3 cap constraints [€/L]
    farm_cost, spot_cost, trans_cost, sales_rev, total_cost : float [€]
    R, V, CAP, c_eff, TC, r_sales, s3_cap : echoed for downstream use
    """
    CAP = R.max(axis=1) * (1 + cap_headroom_pct / 100)

    # Pre-solve feasibility check
    issues = []
    for p in range(NP):
        for t, m in enumerate(MONTHS):
            if R[p, t] > CAP[p]:
                issues.append(
                    f"P{p + 1} production need ({R[p, t] / 1e3:.0f} kL) > "
                    f"capacity ({CAP[p] / 1e3:.0f} kL) in {m}"
                )
    if issues:
        return {"error": issues}

    # Effective spot cost: base price + transport surcharge for non-local purchases
    st = spot_transport_matrix(TC)
    c_eff = c_spot[np.newaxis, :, :] + st[:, :, np.newaxis]  # (NP, NS, T)

    c_obj = build_objective(c_eff, r_sales, TC)
    A_eq, b_eq = build_equality_constraints(R, V)
    A_ub, b_ub = build_inequality_constraints(s3_cap)
    bounds = [(0, None)] * N_VARS

    result = linprog(
        c_obj,
        A_ub=A_ub,
        b_ub=b_ub,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )

    if result.status != 0:
        return {"error": [f"Solver: {result.message}"]}

    z = result.x

    # Unpack flat solution vector into structured arrays
    x_sol = np.array(
        [[[z[idx_x(p, s, t)] for t in range(T)] for s in range(NS)] for p in range(NP)]
    )  # (NP, NS, T)

    u_sol = {r: np.array([z[idx_u(r, t)] for t in range(T)]) for r in ROUTES}

    e_sol = np.array(
        [[[z[idx_e(p, k, t)] for t in range(T)] for k in range(NK)] for p in range(NP)]
    )  # (NP, NK, T)

    duals_eq = result.eqlin.marginals.reshape(NP, T)  # shadow prices: balance constraints
    duals_s3 = result.ineqlin.marginals  # shadow prices: S3 cap

    # Cost breakdown
    farm_cost = float(np.sum(c_farm * V / 1000))
    spot_cost = float(np.sum(c_eff * x_sol / 1000))
    trans_cost = float(sum(TC[r] * u_sol[r].sum() / 1000 for r in ROUTES))
    sales_rev = float(np.sum(r_sales[np.newaxis, :, :] * e_sol / 1000))

    return dict(
        x_sol=x_sol,
        u_sol=u_sol,
        e_sol=e_sol,
        duals_eq=duals_eq,
        duals_s3=duals_s3,
        farm_cost=farm_cost,
        spot_cost=spot_cost,
        trans_cost=trans_cost,
        sales_rev=sales_rev,
        total_cost=farm_cost + spot_cost + trans_cost - sales_rev,
        R=R,
        V=V,
        CAP=CAP,
        c_eff=c_eff,
        TC=TC,
        r_sales=r_sales,
        s3_cap=s3_cap,
    )


def solve_scenario(
    data: dict,
    demand_mult: float = 1.0,
    spot_mult=None,
    farm_vol_mult=None,
    s3_cap: float = 150_000.0,
    cap_headroom_pct: float = 5.0,
) -> dict:
    """Apply scenario multipliers to a base data dict and solve.

    Parameters
    ----------
    data          : base dataset from load_data()
    demand_mult   : scalar multiplier applied to all demand values
    spot_mult     : array-like of shape (NS,), price multiplier per supplier
    farm_vol_mult : array-like of shape (NP,), volume multiplier per farm
    s3_cap        : monthly S3 cap [L]
    cap_headroom_pct : plant capacity headroom [%]
    """
    R = data["R"] * demand_mult
    V = data["V"] * (1.0 if farm_vol_mult is None else np.array(farm_vol_mult)[:, None])
    c_spot = data["c_spot"] * (1.0 if spot_mult is None else np.array(spot_mult)[:, None])

    return solve(
        R=R,
        V=V,
        c_farm=data["c_farm"],
        c_spot=c_spot,
        r_sales=data["r_sales"],
        TC=data["TC"],
        s3_cap=s3_cap,
        cap_headroom_pct=cap_headroom_pct,
    )
