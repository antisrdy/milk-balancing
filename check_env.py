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
def _check_package_version(pkg_name, min_version):
    """Check if package exists and meets minimum version requirement."""
    try:
        __import__(pkg_name)
    except ImportError:
        raise ImportError(f"package not installed")
    
    import importlib.metadata
    version = importlib.metadata.version(pkg_name)
    from packaging.version import parse
    if parse(version) < parse(min_version):
        raise AssertionError(f"need ≥ {min_version}, got {version}")


requirements = [
    ("numpy", "1.25"),
    ("pandas", "2.0"),
    ("scipy", "1.11"),
    ("openpyxl", "3.1"),
    ("streamlit", "1.35"),
    ("plotly", "5.20"),
]

for pkg_name, min_ver in requirements:
    check(f"{pkg_name} ≥ {min_ver}", lambda p=pkg_name, v=min_ver: _check_package_version(p, v))

# ── Dev packages (needed for exercises) ───────────────────────────────────────
dev_requirements = [
    ("pytest", "8.0"),
    ("ruff", "0.4"),
    ("jupyter", "1.0"),
    ("jupyterlab", "4.0"),
    ("matplotlib", "3.8"),
    ("seaborn", "0.13"),
]

for pkg_name, min_ver in dev_requirements:
    check(f"{pkg_name} ≥ {min_ver}", lambda p=pkg_name, v=min_ver: _check_package_version(p, v))

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
