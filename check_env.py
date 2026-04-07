"""Quick environment check — run this before the lesson: python check_env.py"""

import sys

OK = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
errors = 0


def check(label, fn):
    global errors
    try:
        fn()
        print(f"  {OK}  {label}")
    except Exception as e:
        print(f"  {FAIL}  {label}  →  {e}")
        errors += 1


print("\nMilk-balancing environment check\n")


# ── Python version ────────────────────────────────────────────────────────────
def _python_version():
    assert sys.version_info >= (3, 10), f"need ≥ 3.10, got {sys.version.split()[0]}"


check("Python ≥ 3.10", _python_version)

# ── Required packages ─────────────────────────────────────────────────────────
for pkg in ["numpy", "pandas", "scipy", "openpyxl", "streamlit", "plotly"]:
    check(f"import {pkg}", lambda p=pkg: __import__(p))


# ── Data file ─────────────────────────────────────────────────────────────────
def _data_file():
    from pathlib import Path

    candidates = list(Path("data").glob("*.xlsx"))
    assert candidates, "no .xlsx file found in data/"


check("data/*.xlsx present", _data_file)


# ── LP solver round-trip ──────────────────────────────────────────────────────
def _lp_solve():
    from milk_balancing.data_loader import load_data
    from milk_balancing.solver import solve_scenario

    data = load_data()
    result = solve_scenario(data)
    import math

    assert math.isfinite(result["total_cost"]), "solver returned non-finite cost"


check("LP solve returns Optimal", _lp_solve)

# ── Summary ───────────────────────────────────────────────────────────────────
print()
if errors:
    print(f"  {errors} problem(s) found — fix them before the lesson.\n")
    sys.exit(1)
else:
    print("  All checks passed. You're good to go!\n")
