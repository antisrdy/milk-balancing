"""Data loading utilities — Excel reader and built-in defaults.

The Excel workbook is expected at data/milk_planning_dataset.xlsx relative
to the project root.  If it cannot be read, get_default_data() returns the
same figures hard-coded, so the solver works in any environment.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from .constants import MONTHS, ROUTES

_DEFAULT_XLSX = Path(__file__).parent.parent / "data" / "milk_planning_dataset.xlsx"


def load_excel(path=None) -> dict | None:
    """Load planning data from an Excel workbook.

    Returns a data dict on success, or None if the file cannot be read.

    The returned dict has keys:
        R       : (3, 12) production need per plant per month [L]
        V       : (3, 12) farm contracted volume per plant per month [L]
        c_farm  : (3, 12) farm contract price [€/1000L]
        c_spot  : (3, 12) spot market price per supplier per month [€/1000L]
        r_sales : (2, 12) selling price per customer per month [€/1000L]
        TC      : dict mapping route tuple (i, j) → transport cost [€/1000L]
    """
    path = Path(path or _DEFAULT_XLSX)
    try:
        xl = pd.ExcelFile(path)

        def row(sheet: str, label: str) -> np.ndarray:
            df = pd.read_excel(xl, sheet_name=sheet, index_col=0)
            return df.loc[label, MONTHS].values.astype(float)

        yr = {"Skimmed Milk": 1.05, "Cream": 20.0, "UFR": 2.80, "NFR": 2.75}
        R = np.array(
            [
                row("Demand", "Skimmed Milk (P1)") * yr["Skimmed Milk"] * 1000
                + row("Demand", "Cream (P1)") * yr["Cream"] * 1000,
                row("Demand", "UFR (P2)") * yr["UFR"] * 1000,
                row("Demand", "NFR (P3)") * yr["NFR"] * 1000,
            ]
        )
        V = np.array(
            [
                row("Farm_Contracts", "Farm A — Volume (L) [→ P1]"),
                row("Farm_Contracts", "Farm B — Volume (L) [→ P2]"),
                row("Farm_Contracts", "Farm C — Volume (L) [→ P3]"),
            ]
        )
        c_farm = np.array(
            [
                row("Farm_Contracts", "Farm A — Price (€/1000L)"),
                row("Farm_Contracts", "Farm B — Price (€/1000L)"),
                row("Farm_Contracts", "Farm C — Price (€/1000L)"),
            ]
        )
        c_spot = np.array(
            [
                row("Spot_Markets", "S1 — Price (€/1000L) [near P1, North]"),
                row("Spot_Markets", "S2 — Price (€/1000L) [near P2, South]"),
                row("Spot_Markets", "S3 — Price (€/1000L) [near P3, Central]"),
            ]
        )
        r_sales = np.array(
            [
                row("Sales_Prices", "C1 — Price (€/1000L)"),
                row("Sales_Prices", "C2 — Price (€/1000L)"),
            ]
        )
        df_tc = pd.read_excel(xl, sheet_name="Transport_Costs", index_col=0)
        route_labels = [
            "P1 → P2",
            "P2 → P1",
            "P2 → P3",
            "P3 → P2",
            "P1 → P3",
            "P3 → P1",
        ]
        TC = {r: float(df_tc.loc[lbl, "Cost (€/1000L)"]) for lbl, r in zip(route_labels, ROUTES)}
        return dict(R=R, V=V, c_farm=c_farm, c_spot=c_spot, r_sales=r_sales, TC=TC)

    except Exception:
        return None


def get_default_data() -> dict:
    """Return the built-in 2023 baseline dataset (matches the Excel workbook exactly)."""
    return dict(
        R=np.array(
            [
                [
                    2447450,
                    2263745,
                    2098160,
                    1966870,
                    1889370,
                    1909065,
                    1975135,
                    2061235,
                    2228570,
                    2218305,
                    2289810,
                    2407370,
                ],
                [
                    933240,
                    937440,
                    825160,
                    799680,
                    770840,
                    721000,
                    798280,
                    797440,
                    830200,
                    943320,
                    971880,
                    984200,
                ],
                [
                    567875,
                    540375,
                    535150,
                    490325,
                    454025,
                    466400,
                    465300,
                    530200,
                    523325,
                    566775,
                    562925,
                    590975,
                ],
            ],
            dtype=float,
        ),
        V=np.array(
            [
                [
                    1941097,
                    1716738,
                    1981331,
                    2227423,
                    2356863,
                    2231088,
                    2000349,
                    1983791,
                    2135026,
                    2220054,
                    2059816,
                    1961304,
                ],
                [
                    753028,
                    728981,
                    792133,
                    928738,
                    995200,
                    873527,
                    829639,
                    788657,
                    819604,
                    995670,
                    912406,
                    816525,
                ],
                [
                    310160,
                    294237,
                    339506,
                    373232,
                    386133,
                    359604,
                    311910,
                    326875,
                    343867,
                    384955,
                    344107,
                    329062,
                ],
            ],
            dtype=float,
        ),
        c_farm=np.array(
            [
                [
                    319.3,
                    319.6,
                    320.0,
                    317.2,
                    317.5,
                    315.8,
                    315.3,
                    319.5,
                    319.6,
                    318.2,
                    320.4,
                    319.8,
                ],
                [
                    312.3,
                    311.9,
                    307.7,
                    306.2,
                    304.7,
                    309.0,
                    308.5,
                    310.2,
                    312.4,
                    308.3,
                    310.2,
                    313.2,
                ],
                [
                    336.1,
                    335.3,
                    335.2,
                    332.8,
                    336.6,
                    336.4,
                    336.5,
                    338.4,
                    337.8,
                    334.0,
                    338.9,
                    337.5,
                ],
            ],
            dtype=float,
        ),
        c_spot=np.array(
            [
                [
                    380.7,
                    381.6,
                    375.2,
                    372.0,
                    372.4,
                    374.6,
                    379.1,
                    379.9,
                    372.1,
                    376.5,
                    376.2,
                    375.1,
                ],
                [
                    342.7,
                    342.0,
                    342.7,
                    330.9,
                    328.1,
                    331.2,
                    335.2,
                    340.8,
                    339.8,
                    333.5,
                    341.0,
                    342.8,
                ],
                [
                    368.7,
                    365.2,
                    366.7,
                    358.0,
                    352.3,
                    355.7,
                    364.4,
                    362.4,
                    360.9,
                    360.9,
                    369.9,
                    368.5,
                ],
            ],
            dtype=float,
        ),
        r_sales=np.array(
            [
                [
                    317.8,
                    318.3,
                    316.1,
                    320.2,
                    318.6,
                    319.8,
                    319.0,
                    318.1,
                    315.5,
                    320.1,
                    316.5,
                    315.2,
                ],
                [
                    307.8,
                    311.0,
                    312.7,
                    310.1,
                    313.8,
                    311.6,
                    313.1,
                    309.9,
                    313.1,
                    311.4,
                    314.1,
                    308.7,
                ],
            ],
            dtype=float,
        ),
        TC={(0, 1): 80.0, (1, 0): 80.0, (1, 2): 60.0, (2, 1): 60.0, (0, 2): 130.0, (2, 0): 130.0},
    )


def load_data(path=None) -> dict:
    """Load data from Excel if available, otherwise return built-in defaults."""
    data = load_excel(path)
    return data if data is not None else get_default_data()
