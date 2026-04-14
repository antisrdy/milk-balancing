# Milk Balancing — LP Supply Chain Optimisation

A pedagogical project demonstrating **linear programming** applied to a real-world supply chain problem: routing raw milk across a three-plant dairy network at minimum cost.

## The Problem

Three dairy plants (North, South, Central) must cover their monthly production needs over a 12-month horizon.  Each plant has:

- **Farm contracts** — cheap but fixed volume (cannot increase)
- **Spot market** — flexible but expensive; each supplier is co-located with one plant
- **Inter-plant transfers** — allows surplus at one plant to cover a deficit at another

The LP minimises total cost (spot purchases + transport) minus sales revenue from excess milk.

### Decision variables (252 total)

| Variable | Meaning | Count |
|---|---|---|
| `x[p,s,t]` | Volume bought from spot supplier `s` at plant `p` in month `t` | 108 |
| `u[i,j,t]` | Volume transferred from plant `i` to plant `j` in month `t` | 72 |
| `e[p,k,t]` | Excess milk sold from plant `p` to customer `k` in month `t` | 72 |

### Constraints (48 total)

- **36 balance constraints** — inflows = production need at every (plant, month)
- **12 capacity constraints** — S3 total monthly purchases ≤ 150 kL

## Project Structure

```
milk-balancing/
├── milk_balancing/          # Installable Python package
│   ├── __init__.py
│   ├── constants.py         # Shared dimensions, names, routes
│   ├── data_loader.py       # Excel reader + built-in defaults
│   ├── lp_model.py          # Variable indices, LP matrix builders
│   └── solver.py            # solve() and solve_scenario()
├── app.py                   # Streamlit interactive dashboard
├── check_env.py             # Environment validation script
├── data/
│   └── milk_planning_dataset.xlsx
├── tests/
│   ├── conftest.py          # Shared fixtures
│   ├── test_data_loader.py  # Input validation tests
│   ├── test_lp_model.py     # LP structure tests
│   └── test_solver.py       # Solution correctness tests
├── .github/workflows/ci.yml # GitHub Actions CI
├── pyproject.toml
├── Makefile
└── README.md
```

## Quick Start

### Requirements

- Python ≥3.10
- Git (for cloning the repository)

### 1 — Set up the environment

```bash
git clone https://github.com/antisrdy/milk-balancing.git
cd milk-balancing
```

Then:
```bash
make install          # creates .venv and installs dependencies
source .venv/bin/activate
```
Or manually (use `python3` if `python` is not available):
```bash
python -m venv .venv          # or: python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Now, check the installation:
```bash
make check
```
Or manually (use `python3` if `python` is not available):
```bash
python check_env.py           # or: python3 check_env.py
```

This validates that all dependencies are installed and the LP solver works correctly.

### 2 — Work through the exercises

```bash
make notebook
```
Or manually (use `python3` if `python` is not available):
```bash
jupyter lab exercises/
```

Open `exercises/build_lp.ipynb` to learn how the LP model is constructed step-by-step.

### 3 — Use the solver in Python

```python
from milk_balancing import load_data, solve_scenario

data   = load_data()               # reads data/milk_planning_dataset.xlsx
result = solve_scenario(data)      # baseline optimisation

print(f"Farm cost:   €{result['farm_cost']:,.0f}")
print(f"Spot cost:   €{result['spot_cost']:,.0f}")
print(f"Net total:   €{result['total_cost']:,.0f}")

# Scenario: Farm C supply drops 30%, S3 cap tightened to 100 kL
result_shock = solve_scenario(
    data,
    farm_vol_mult=[1.0, 1.0, 0.7],
    s3_cap=100_000,
)
```

### 4 — Run the interactive dashboard

```bash
make run
```
Or manually (use `python3` if `python` is not available):
```bash
streamlit run app.py
```

Open <http://localhost:8501> in your browser.  The sidebar lets you adjust demand, farm supply, spot prices, transport costs, S3 capacity, and plant headroom. The LP re-solves instantly on every change.

**Reset functionality**: Use the "↺ Reset all to defaults" button to restore all parameters to their original values.

## Running the Tests

```bash
make test
# or
pytest tests/ -v
```

The test suite covers:

- **Data loader** — array shapes, business-logic sanity (spot > farm prices, P3 deficit)
- **LP model** — variable count (252), no index collisions, matrix dimensions, RHS values
- **Solver** — mass balance, S3 cap, non-negativity, cost accounting identity, scenario responses

### Why tests matter here

The LP model is built by hand: index helpers, constraint matrices, cost vector.  A single off-by-one error in `idx_x()` would corrupt every constraint silently — the solver would still return a "feasible" solution, but it would be meaningless.  Tests on the *structure* of the LP (before solving) catch these bugs early.

## LP Formulation

**Objective** (minimise):

```
Σ_{p,s,t}  (c_spot[s,t] + transport[p,s]) / 1000  ×  x[p,s,t]
+ Σ_{route,t}  TC[route] / 1000  ×  u[route,t]
− Σ_{p,k,t}  r_sales[k,t] / 1000  ×  e[p,k,t]
```

Farm costs are fixed by contracts and excluded.

**Balance constraint** (one per plant p, month t):

```
V[p,t]  +  Σ_s x[p,s,t]  +  Σ_{(j,p)} u[(j,p),t]
        −  Σ_{(p,j)} u[(p,j),t]  −  Σ_k e[p,k,t]  =  R[p,t]
```

**S3 capacity** (one per month t):

```
Σ_p x[p, S3, t]  ≤  150 000 L
```

**Non-negativity**: all variables ≥ 0.

Solved with `scipy.optimize.linprog` using the HiGHS backend.

## Dashboard Tabs

| Tab | What you learn |
|---|---|
| 🌐 Network flows | Where each plant gets its milk; spot price landscape; S3 utilisation |
| 🏭 Plant details | Monthly source mix per plant; expensive months highlighted |
| 💸 Cost breakdown | Waterfall: farm → spot → transfer → sales → net; monthly evolution |
| 🔀 Transfers | Which routes are active; why Plant 3 is chronically undersupplied |
| 📐 Shadow prices | Value of relaxing constraints; sensitivity to supply and capacity |

## Key Insight: Shadow Prices

The **shadow price** of a constraint tells you how much the optimal cost would change if you relaxed that constraint by one unit.

- A **positive** balance shadow price at plant p means: "one extra litre of raw milk at P{p} would save €X" — the plant is short.
- A **non-zero** S3 shadow price means the S3 cap is binding — relaxing it by 1 kL would save money.

Try: reduce Farm C to 0.5× → watch P3's shadow price spike.  Then set transport costs to 0× → the network fully arbitrages and all shadow prices equalise.

## Development

```bash
make lint      # ruff check + format check
make format    # auto-fix formatting
make test      # pytest
make clean     # remove .venv, caches, build artefacts
```

CI runs on every push and pull request via GitHub Actions (see [.github/workflows/ci.yml](.github/workflows/ci.yml)).
