"""LP model construction for the milk supply chain problem.

Decision variables
------------------
x[p, s, t]  volume bought from spot supplier s at plant p in month t  [L]
            p ∈ {0,1,2}  s ∈ {0,1,2}  t ∈ {0..11}  → 108 variables

u[i, j, t]  volume transferred from plant i to plant j in month t  [L]
            (i,j) ∈ ROUTES  t ∈ {0..11}  → 72 variables

e[p, k, t]  excess milk sold from plant p to customer k in month t  [L]
            p ∈ {0,1,2}  k ∈ {0,1}  t ∈ {0..11}  → 72 variables

Total: 252 variables, all ≥ 0.

Constraints
-----------
[C1] Mass balance at each plant p and month t  (36 equality constraints):
     V[p,t] + Σ_s x[p,s,t] + Σ_{j:(j,p)∈ROUTES} u[(j,p),t]
            - Σ_{j:(p,j)∈ROUTES} u[(p,j),t] - Σ_k e[p,k,t]  =  R[p,t]

[C2] S3 total capacity across all plants, per month  (12 inequality constraints):
     Σ_p x[p, 2, t] ≤ S3_CAP

Objective
---------
min  Σ_{p,s,t} (c_eff[p,s,t] / 1000) · x[p,s,t]
   + Σ_{route,t} (TC[route] / 1000) · u[route,t]
   - Σ_{p,k,t} (r_sales[k,t] / 1000) · e[p,k,t]

where c_eff[p,s,t] = c_spot[s,t] + transport_surcharge[p,s].
Farm costs are fixed and excluded from the objective.
"""

import numpy as np

from .constants import NK, NP, NS, ROUTES, T

# ── Total variable count ───────────────────────────────────────────────────────

N_VARS = NP * NS * T + len(ROUTES) * T + NP * NK * T  # 252


# ── Variable index helpers ─────────────────────────────────────────────────────


def idx_x(p: int, s: int, t: int) -> int:
    """Flat index of spot-purchase variable x[p, s, t].  Range: 0 … 107."""
    return p * NS * T + s * T + t


def idx_u(r: tuple, t: int) -> int:
    """Flat index of transfer variable u[r, t].  Range: 108 … 179."""
    return NP * NS * T + ROUTES.index(r) * T + t


def idx_e(p: int, k: int, t: int) -> int:
    """Flat index of excess-sales variable e[p, k, t].  Range: 180 … 251."""
    return NP * NS * T + len(ROUTES) * T + p * NK * T + k * T + t


# ── Spot transport surcharge ───────────────────────────────────────────────────


def spot_transport_matrix(TC: dict) -> np.ndarray:
    """Return (NP, NS) array of transport cost to ship spot from supplier s to plant p.

    Each spot supplier is co-located with one plant (S0↔P0, S1↔P1, S2↔P2).
    Buying from a non-local supplier adds the inter-plant transport cost.

    Example: P3 buying from S2 (near P2) pays c_s2 + TC[(1,2)] = c_s2 + 60 €/1000L.
    """
    st = np.zeros((NP, NS))
    # S0 is local to P0 → P1 and P2 pay transport to get S0
    st[1, 0] = TC[(1, 0)]
    st[2, 0] = TC[(2, 0)]
    # S1 is local to P1 → P0 and P2 pay transport to get S1
    st[0, 1] = TC[(0, 1)]
    st[2, 1] = TC[(2, 1)]
    # S2 is local to P2 → P0 and P1 pay transport to get S2
    st[0, 2] = TC[(0, 2)]
    st[1, 2] = TC[(1, 2)]
    return st


# ── LP matrix builders ────────────────────────────────────────────────────────


def build_objective(
    c_eff: np.ndarray,
    r_sales: np.ndarray,
    TC: dict,
) -> np.ndarray:
    """Build the (N_VARS,) cost vector c for linprog (minimise c @ x).

    Parameters
    ----------
    c_eff   : (NP, NS, T) effective spot cost including transport surcharge [€/1000L]
    r_sales : (NK, T) selling price per customer per month [€/1000L]
    TC      : dict mapping route tuple to unit transport cost [€/1000L]
    """
    c_obj = np.zeros(N_VARS)

    for p in range(NP):
        for s in range(NS):
            for t in range(T):
                c_obj[idx_x(p, s, t)] = c_eff[p, s, t] / 1000.0

    for r in ROUTES:
        for t in range(T):
            c_obj[idx_u(r, t)] = TC[r] / 1000.0

    for p in range(NP):
        for k in range(NK):
            for t in range(T):
                c_obj[idx_e(p, k, t)] = -r_sales[k, t] / 1000.0

    return c_obj


def build_equality_constraints(
    R: np.ndarray,
    V: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Build mass-balance constraints: net inflow = production need.

    For each plant p and month t:
        Σ_s x[p,s,t]  +  Σ_{j:(j,p)} u[(j,p),t]
        - Σ_{j:(p,j)} u[(p,j),t]  - Σ_k e[p,k,t]  =  R[p,t] - V[p,t]

    Returns
    -------
    A_eq : (NP*T, N_VARS)
    b_eq : (NP*T,)
    """
    n_eq = NP * T
    A_eq = np.zeros((n_eq, N_VARS))
    b_eq = np.zeros(n_eq)

    for p in range(NP):
        for t in range(T):
            row = p * T + t

            for s in range(NS):
                A_eq[row, idx_x(p, s, t)] = 1.0  # spot purchase

            for i, j in ROUTES:
                if j == p:
                    A_eq[row, idx_u((i, j), t)] = 1.0  # incoming transfer
                if i == p:
                    A_eq[row, idx_u((i, j), t)] = -1.0  # outgoing transfer

            for k in range(NK):
                A_eq[row, idx_e(p, k, t)] = -1.0  # excess sold

            b_eq[row] = R[p, t] - V[p, t]  # net deficit to cover

    return A_eq, b_eq


def build_inequality_constraints(s3_cap: float) -> tuple[np.ndarray, np.ndarray]:
    """Build S3 monthly capacity cap: Σ_p x[p, 2, t] ≤ s3_cap.

    Returns
    -------
    A_ub : (T, N_VARS)
    b_ub : (T,)
    """
    A_ub = np.zeros((T, N_VARS))
    b_ub = np.full(T, s3_cap)

    for t in range(T):
        for p in range(NP):
            A_ub[t, idx_x(p, 2, t)] = 1.0  # s=2 is S3

    return A_ub, b_ub
