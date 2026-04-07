"""
Milk Planning — Interactive LP Dashboard (3-plant network)
==========================================================
Run with:
    streamlit run app.py

The dashboard re-solves the LP on every sidebar change and shows five tabs:
  1. Network flows   — supply vs production need for all three plants
  2. Plant details   — per-plant monthly breakdown + table
  3. Cost breakdown  — waterfall, component bars, monthly evolution
  4. Transfers       — route volumes, cost summary, P3 deficit analysis
  5. Shadow prices   — dual variables for balance and S3 cap constraints
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from milk_balancing.constants import (
    FARM_NAMES,
    MONTHS,
    NP,
    NS,
    P_NAMES,
    ROUTE_LBL,
    ROUTES,
    S_NAMES,
    T,
)
from milk_balancing.data_loader import get_default_data, load_excel
from milk_balancing.solver import solve

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Milk Planning LP",
    page_icon="🥛",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Colour palette (one source of truth for every chart) ──────────────────────
P_COLORS = ["#2E75B6", "#0F6E56", "#7D3C98"]  # Plant 1, 2, 3
S_COLORS = ["#E07B39", "#17A589", "#C0392B"]  # S1, S2, S3
R_COLORS = ["#5499C7", "#1ABC9C", "#9B59B6", "#E67E22", "#E74C3C", "#95A5A6"]
COL_TRANS_IN = "#9B59B6"
COL_TRANS_OUT = "#6C3483"
COL_EXCESS = "#27AE60"
COL_NEED = "#1F4E79"
COL_S3_CAP = "#C0392B"

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
  .kpi { background:#f8f9fa; border-radius:8px; padding:14px 18px;
         border-left:4px solid #2E75B6; margin-bottom:4px; }
  .kpi.red    { border-left-color:#C0392B; }
  .kpi.green  { border-left-color:#27AE60; }
  .kpi.gold   { border-left-color:#E67E22; }
  .kpi.purple { border-left-color:#7D3C98; }
  .kpi-lbl { font-size:.72rem; color:#666; text-transform:uppercase;
             letter-spacing:.05em; margin-bottom:2px; }
  .kpi-val { font-size:1.4rem; font-weight:600; color:#1F4E79; }
  .kpi.red    .kpi-val { color:#C0392B; }
  .kpi.green  .kpi-val { color:#27AE60; }
  .kpi.gold   .kpi-val { color:#E67E22; }
  .kpi.purple .kpi-val { color:#7D3C98; }
  h2 { color:#2E75B6 !important; border-bottom:1px solid #D6E4F0; padding-bottom:4px; }
  h3 { color:#1F4E79 !important; }
</style>
""",
    unsafe_allow_html=True,
)


def kpi(label: str, value: str, col: str = "blue") -> None:
    cls = {"blue": "", "red": "red", "green": "green", "gold": "gold", "purple": "purple"}[col]
    st.markdown(
        f'<div class="kpi {cls}"><div class="kpi-lbl">{label}</div>'
        f'<div class="kpi-val">{value}</div></div>',
        unsafe_allow_html=True,
    )


def fmt(v: float) -> str:
    return f"€{v:,.0f}"


def pdef(template=None, legend=None) -> dict:
    return dict(
        template=template or "plotly_white",
        font=dict(family="Arial, sans-serif", size=12),
        margin=dict(l=50, r=20, t=40, b=40),
        legend=legend if legend is not None else dict(orientation="h", y=-0.25),
    )


# ── Load base data ─────────────────────────────────────────────────────────────
@st.cache_data
def _load_base():
    data = load_excel()
    if data is None:
        st.info(
            "ℹ️ `data/milk_planning_dataset.xlsx` not found — using built-in defaults. "
            "Place the file in the `data/` folder to load the full dataset.",
            icon="ℹ️",
        )
        return get_default_data()
    return data


BASE = _load_base()

# ── Sidebar ───────────────────────────────────────────────────────────────────
# Initialize session state with defaults if not already set
if "yr_skim" not in st.session_state:
    st.session_state["yr_skim"] = 1.05
if "yr_cream" not in st.session_state:
    st.session_state["yr_cream"] = 20.0
if "yr_ufr" not in st.session_state:
    st.session_state["yr_ufr"] = 2.80
if "yr_nfr" not in st.session_state:
    st.session_state["yr_nfr"] = 2.75
if "demand_mult" not in st.session_state:
    st.session_state["demand_mult"] = 1.0
if "fa_vol" not in st.session_state:
    st.session_state["fa_vol"] = 1.0
if "fb_vol" not in st.session_state:
    st.session_state["fb_vol"] = 1.0
if "fc_vol" not in st.session_state:
    st.session_state["fc_vol"] = 1.0
if "s1_mult" not in st.session_state:
    st.session_state["s1_mult"] = 1.0
if "s2_mult" not in st.session_state:
    st.session_state["s2_mult"] = 1.0
if "s3_mult" not in st.session_state:
    st.session_state["s3_mult"] = 1.0
if "s3_cap_kl" not in st.session_state:
    st.session_state["s3_cap_kl"] = 150
if "tc_mult" not in st.session_state:
    st.session_state["tc_mult"] = 1.0
if "cap_pct" not in st.session_state:
    st.session_state["cap_pct"] = 5

with st.sidebar:
    st.header("⚙️ Parameters")

    # Reset functionality
    if st.button("↺  Reset all to defaults", width="stretch"):
        # Set all parameters back to their default values
        st.session_state["yr_skim"] = 1.05
        st.session_state["yr_cream"] = 20.0
        st.session_state["yr_ufr"] = 2.80
        st.session_state["yr_nfr"] = 2.75
        st.session_state["demand_mult"] = 1.0
        st.session_state["fa_vol"] = 1.0
        st.session_state["fb_vol"] = 1.0
        st.session_state["fc_vol"] = 1.0
        st.session_state["s1_mult"] = 1.0
        st.session_state["s2_mult"] = 1.0
        st.session_state["s3_mult"] = 1.0
        st.session_state["s3_cap_kl"] = 150
        st.session_state["tc_mult"] = 1.0
        st.session_state["cap_pct"] = 5
        st.rerun()

    st.subheader("Yield ratios (L / kg)")
    yr_skim = st.number_input(
        "Skimmed Milk", min_value=0.5, max_value=5.0, step=0.05, key="yr_skim"
    )
    yr_cream = st.number_input("Cream", min_value=5.0, max_value=40.0, step=0.5, key="yr_cream")
    yr_ufr = st.number_input("UFR", min_value=1.0, max_value=8.0, step=0.05, key="yr_ufr")
    yr_nfr = st.number_input("NFR", min_value=1.0, max_value=8.0, step=0.05, key="yr_nfr")
    st.divider()

    st.subheader("Demand")
    demand_mult = st.slider("All demand ×", 0.5, 2.0, step=0.05, key="demand_mult")
    st.divider()

    st.subheader("Farm supply shocks")
    fa_vol = st.slider("Farm A volume ×", 0.5, 1.5, step=0.05, key="fa_vol")
    fb_vol = st.slider("Farm B volume ×", 0.5, 1.5, step=0.05, key="fb_vol")
    fc_vol = st.slider(
        "Farm C volume ×",
        0.5,
        1.5,
        step=0.05,
        key="fc_vol",
        help="Farm C normally covers ~65-74% of P3 need",
    )
    st.divider()

    st.subheader("Spot price shocks")
    s1_mult = st.slider("S1 price ×", 0.7, 1.5, step=0.05, key="s1_mult")
    s2_mult = st.slider("S2 price × (cheapest)", 0.7, 1.5, step=0.05, key="s2_mult")
    s3_mult = st.slider("S3 price ×", 0.7, 1.5, step=0.05, key="s3_mult")
    st.divider()

    st.subheader("S3 capacity cap")
    s3_cap_kl = st.slider(
        "S3 monthly cap (kL)",
        0,
        400,
        step=10,
        key="s3_cap_kl",
        help="Default 150 kL. Setting to 0 forces all P3 deficit to transfers.",
    )
    st.divider()

    st.subheader("Transport costs")
    tc_mult = st.slider(
        "All transport costs ×",
        0.0,
        3.0,
        step=0.1,
        key="tc_mult",
        help="0 = free transfers — useful to see the unconstrained optimal network",
    )
    st.divider()

    st.subheader("Plant capacity headroom")
    cap_pct = st.slider("% above peak demand", 0, 30, step=1, key="cap_pct")

# ── Apply shocks and solve ─────────────────────────────────────────────────────
R = BASE["R"].copy() * demand_mult
R[0] *= yr_skim / 1.05 * 0.5 + yr_cream / 20.0 * 0.5  # approximate P1 yield blend
R[1] *= yr_ufr / 2.80
R[2] *= yr_nfr / 2.75

V = BASE["V"].copy()
V[0] *= fa_vol
V[1] *= fb_vol
V[2] *= fc_vol

c_spot = BASE["c_spot"].copy()
c_spot[0] *= s1_mult
c_spot[1] *= s2_mult
c_spot[2] *= s3_mult

TC = {k: v * tc_mult for k, v in BASE["TC"].items()}
S3_CAP = s3_cap_kl * 1000.0

res = solve(R, V, BASE["c_farm"], c_spot, BASE["r_sales"], TC, S3_CAP, cap_pct)

if "error" in res:
    st.error("⛔ Infeasible configuration\n\n" + "\n".join(res["error"]))
    st.stop()

x_sol = res["x_sol"]
u_sol = res["u_sol"]
e_sol = res["e_sol"]
R_ = res["R"]
V_ = res["V"]

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🥛 Milk Planning — Three-Plant LP Dashboard")
st.caption(
    "3 plants · 3 farms · 3 spot suppliers · 6 transfer routes · S3 capacity cap · "
    "252 variables · 48 constraints. Re-solves on every change."
)

# ── KPI row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    kpi("Farm cost (fixed)", fmt(res["farm_cost"]), "blue")
with k2:
    kpi("Spot purchase cost", fmt(res["spot_cost"]), "red")
with k3:
    kpi("Transfer cost", fmt(res["trans_cost"]), "purple")
with k4:
    kpi("Sales revenue", fmt(res["sales_rev"]), "green")
with k5:
    kpi("Net total cost", fmt(res["total_cost"]), "gold")

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tabs = st.tabs(
    [
        "🌐 Network flows",
        "🏭 Plant details",
        "💸 Cost breakdown",
        "🔀 Transfers",
        "📐 Shadow prices",
    ]
)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Network flows overview
# ══════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.markdown("### Supply vs production need — all three plants")

    fig = make_subplots(rows=1, cols=3, subplot_titles=P_NAMES, shared_yaxes=False)

    for p in range(NP):
        in_trans_p = sum((u_sol[(i, j)] for (i, j) in ROUTES if j == p), np.zeros(T))
        fig.add_trace(
            go.Bar(
                name=FARM_NAMES[p],
                x=MONTHS,
                y=V_[p] / 1e3,
                marker_color=P_COLORS[p],
                opacity=0.75,
                legendgroup=FARM_NAMES[p],
                showlegend=True,
                hovertemplate=f"%{{y:.0f}} kL — {FARM_NAMES[p]}<extra></extra>",
            ),
            row=1,
            col=p + 1,
        )

        for s in range(NS):
            fig.add_trace(
                go.Bar(
                    name=f"Spot {S_NAMES[s]}",
                    x=MONTHS,
                    y=x_sol[p, s] / 1e3,
                    marker_color=S_COLORS[s],
                    opacity=0.85,
                    legendgroup=f"spot_{s}",
                    showlegend=(p == 0),
                    hovertemplate=f"%{{y:.1f}} kL — Spot {S_NAMES[s]}<extra></extra>",
                ),
                row=1,
                col=p + 1,
            )

        fig.add_trace(
            go.Bar(
                name="Incoming transfer",
                x=MONTHS,
                y=in_trans_p / 1e3,
                marker_color=COL_TRANS_IN,
                opacity=0.8,
                legendgroup="trans_in",
                showlegend=(p == 0),
                hovertemplate="%{y:.1f} kL — transfer in<extra></extra>",
            ),
            row=1,
            col=p + 1,
        )

        fig.add_trace(
            go.Scatter(
                name="Production need",
                x=MONTHS,
                y=R_[p] / 1e3,
                mode="lines+markers",
                line=dict(color=COL_NEED, width=2.5, dash="dash"),
                marker=dict(size=5),
                legendgroup="need",
                showlegend=(p == 0),
                hovertemplate="%{y:.0f} kL needed<extra></extra>",
            ),
            row=1,
            col=p + 1,
        )

    fig.update_layout(
        **pdef(legend=dict(orientation="h", y=-0.22, tracegroupgap=4)),
        barmode="stack",
        height=400,
        title_text="Inflows (farm + spot + transfers) vs production need",
    )
    for p in range(NP):
        fig.update_yaxes(title_text="kL", row=1, col=p + 1)
    st.plotly_chart(fig, width="stretch")

    st.markdown("### Price landscape")
    fig2 = go.Figure()
    for s in range(NS):
        fig2.add_trace(
            go.Scatter(
                name=S_NAMES[s],
                x=MONTHS,
                y=c_spot[s],
                mode="lines+markers",
                line=dict(color=S_COLORS[s], width=2),
                marker=dict(size=6),
            )
        )
    fig2.add_trace(
        go.Scatter(
            name="S2 effective at P3 (+transport)",
            x=MONTHS,
            y=c_spot[1] + TC.get((1, 2), 60),
            mode="lines",
            line=dict(color=S_COLORS[1], width=1.5, dash="dot"),
        )
    )
    for p in range(NP):
        fig2.add_trace(
            go.Scatter(
                name=f"Farm {['A', 'B', 'C'][p]}",
                x=MONTHS,
                y=BASE["c_farm"][p],
                mode="lines",
                line=dict(color=P_COLORS[p], width=1.5, dash="longdash"),
                opacity=0.65,
            )
        )
    fig2.update_layout(
        **pdef(),
        height=340,
        yaxis_title="€ / 1 000 L",
        title_text="Spot prices vs farm prices (spot always above farm)",
    )
    st.plotly_chart(fig2, width="stretch")

    st.markdown("### S3 monthly utilisation vs cap")
    fig3 = go.Figure()
    for p in range(NP):
        fig3.add_trace(
            go.Bar(
                name=P_NAMES[p],
                x=MONTHS,
                y=x_sol[p, 2] / 1e3,
                marker_color=P_COLORS[p],
                opacity=0.85,
            )
        )
    fig3.add_hline(
        y=S3_CAP / 1e3,
        line_dash="dash",
        line_color=COL_S3_CAP,
        annotation_text=f"S3 cap: {S3_CAP / 1e3:.0f} kL",
        annotation_position="right",
    )
    fig3.update_layout(
        **pdef(),
        barmode="stack",
        height=280,
        yaxis_title="kL",
        title_text="S3 usage by plant vs monthly cap",
    )
    st.plotly_chart(fig3, width="stretch")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Per-plant detail
# ══════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    sel_p = st.radio("Select plant", P_NAMES, horizontal=True)
    p = P_NAMES.index(sel_p)

    st.markdown(f"### {sel_p} — monthly raw milk flows")

    in_trans = sum((u_sol[(i, j)] for (i, j) in ROUTES if j == p), np.zeros(T))
    out_trans = sum((u_sol[(i, j)] for (i, j) in ROUTES if i == p), np.zeros(T))
    excess_p = e_sol[p].sum(axis=0)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name=f"Farm {['A', 'B', 'C'][p]}",
            x=MONTHS,
            y=V_[p] / 1e3,
            marker_color=P_COLORS[p],
            opacity=0.85,
        )
    )
    for s in range(NS):
        vals = x_sol[p, s] / 1e3
        fig.add_trace(
            go.Bar(
                name=f"Spot {S_NAMES[s]}",
                x=MONTHS,
                y=vals,
                marker_color=S_COLORS[s],
                opacity=0.85,
                visible=True if vals.sum() > 0 else "legendonly",
            )
        )
    fig.add_trace(
        go.Bar(
            name="Incoming transfers",
            x=MONTHS,
            y=in_trans / 1e3,
            marker_color=COL_TRANS_IN,
            opacity=0.8,
            visible=True if in_trans.sum() > 0 else "legendonly",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Outgoing transfers",
            x=MONTHS,
            y=-out_trans / 1e3,
            marker_color=COL_TRANS_OUT,
            opacity=0.75,
            visible=True if out_trans.sum() > 0 else "legendonly",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Excess → customers",
            x=MONTHS,
            y=-excess_p / 1e3,
            marker_color=COL_EXCESS,
            opacity=0.75,
            visible=True if excess_p.sum() > 0 else "legendonly",
        )
    )
    fig.add_trace(
        go.Scatter(
            name="Production need",
            x=MONTHS,
            y=R_[p] / 1e3,
            mode="lines+markers",
            line=dict(color=COL_NEED, width=2.5, dash="dash"),
            marker=dict(size=6),
        )
    )
    fig.add_hline(y=0, line_color="#CCCCCC", line_width=0.8)
    fig.update_layout(
        **pdef(),
        barmode="relative",
        height=420,
        yaxis_title="kL",
        title_text=f"{sel_p} — inflows above zero, outflows below",
    )
    st.plotly_chart(fig, width="stretch")

    # Monthly detail table
    rows_tbl = []
    for t, m in enumerate(MONTHS):
        src_parts = []
        if V_[p, t] > 100:
            src_parts.append(f"Farm: {V_[p, t] / 1e3:.0f}kL")
        for s in range(NS):
            if x_sol[p, s, t] > 100:
                src_parts.append(f"S{s + 1}: {x_sol[p, s, t] / 1e3:.1f}kL")
        for i, j in ROUTES:
            if j == p and u_sol[(i, j)][t] > 100:
                src_parts.append(f"P{i + 1}→: {u_sol[(i, j)][t] / 1e3:.1f}kL")
        rows_tbl.append(
            {
                "Month": m,
                "Need (kL)": round(R_[p, t] / 1e3, 1),
                "Farm (kL)": round(V_[p, t] / 1e3, 1),
                "Spot S1 (kL)": round(x_sol[p, 0, t] / 1e3, 1),
                "Spot S2 (kL)": round(x_sol[p, 1, t] / 1e3, 1),
                "Spot S3 (kL)": round(x_sol[p, 2, t] / 1e3, 1),
                "Transfer in (kL)": round(in_trans[t] / 1e3, 1),
                "Transfer out (kL)": round(out_trans[t] / 1e3, 1),
                "Excess sold (kL)": round(excess_p[t] / 1e3, 1),
                "Source mix": " | ".join(src_parts),
            }
        )

    df_tbl = pd.DataFrame(rows_tbl).set_index("Month")

    def hl_row(row):
        if row["Spot S1 (kL)"] > 0:
            return ["background-color:#FEF0EB"] * len(row)
        if row["Excess sold (kL)"] > 0:
            return ["background-color:#EAFAF1"] * len(row)
        return [""] * len(row)

    st.dataframe(df_tbl.style.apply(hl_row, axis=1), width="stretch")
    st.caption("Warm tint = buying expensive S1 spot.  Green tint = selling excess.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Cost breakdown
# ══════════════════════════════════════════════════════════════════════════════
with tabs[2]:
    col_a, col_b = st.columns(2)

    with col_a:
        fig_wf = go.Figure(
            go.Waterfall(
                orientation="v",
                measure=["absolute", "relative", "relative", "relative", "total"],
                x=["Farm cost", "Spot cost", "Transfer cost", "−Sales", "Net total"],
                y=[
                    res["farm_cost"],
                    res["spot_cost"],
                    res["trans_cost"],
                    -res["sales_rev"],
                    res["total_cost"],
                ],
                text=[
                    fmt(res["farm_cost"]),
                    fmt(res["spot_cost"]),
                    fmt(res["trans_cost"]),
                    f"−{fmt(res['sales_rev'])}",
                    fmt(res["total_cost"]),
                ],
                textposition="outside",
                connector=dict(line=dict(color="#CCCCCC", width=1, dash="dot")),
                increasing=dict(marker_color=COL_S3_CAP),
                decreasing=dict(marker_color=COL_EXCESS),
                totals=dict(marker_color=COL_NEED),
            )
        )
        fig_wf.update_layout(
            **pdef(), height=380, title_text="Annual cost waterfall", yaxis_title="€"
        )
        st.plotly_chart(fig_wf, width="stretch")

    with col_b:
        spot_by_plant = [float(np.sum(res["c_eff"][p] * x_sol[p] / 1000)) for p in range(NP)]
        tc_by_route = {r: float(TC[r] * u_sol[r].sum() / 1000) for r in ROUTES}
        sales_by_plant = [
            float(np.sum(BASE["r_sales"][np.newaxis, :, :] * e_sol[p : p + 1] / 1000))
            for p in range(NP)
        ]
        fig_br = go.Figure()
        for p in range(NP):
            fig_br.add_trace(
                go.Bar(
                    name=f"Spot — {P_NAMES[p]}",
                    x=["Spot"],
                    y=[spot_by_plant[p]],
                    marker_color=P_COLORS[p],
                    opacity=0.85,
                )
            )
        for ri, (r, lbl) in enumerate(zip(ROUTES, ROUTE_LBL)):
            if tc_by_route[r] > 0:
                fig_br.add_trace(
                    go.Bar(
                        name=f"Transfer {lbl}",
                        x=["Transfer"],
                        y=[tc_by_route[r]],
                        marker_color=R_COLORS[ri],
                        opacity=0.85,
                    )
                )
        for p in range(NP):
            fig_br.add_trace(
                go.Bar(
                    name=f"Sales — {P_NAMES[p]}",
                    x=["Sales"],
                    y=[-sales_by_plant[p]],
                    marker_color=P_COLORS[p],
                    opacity=0.45,
                )
            )
        fig_br.update_layout(
            **pdef(),
            barmode="relative",
            height=380,
            yaxis_title="€",
            title_text="Variable costs by component",
        )
        st.plotly_chart(fig_br, width="stretch")

    st.markdown("### Monthly variable cost evolution")
    fig_mn = go.Figure()
    for p in range(NP):
        monthly_spot = np.array(
            [float(np.sum(res["c_eff"][p, :, t] * x_sol[p, :, t] / 1000)) for t in range(T)]
        )
        monthly_sales = np.array(
            [float(np.sum(BASE["r_sales"][:, t] * e_sol[p, :, t] / 1000)) for t in range(T)]
        )
        monthly_trans = np.array(
            [sum(TC[r] * u_sol[r][t] / 1000 for r in ROUTES if r[0] == p) for t in range(T)]
        )
        fig_mn.add_trace(
            go.Scatter(
                name=P_NAMES[p],
                x=MONTHS,
                y=monthly_spot + monthly_trans - monthly_sales,
                mode="lines+markers",
                line=dict(color=P_COLORS[p], width=2),
                marker=dict(size=6),
            )
        )
    fig_mn.add_hline(y=0, line_dash="dash", line_color="#CCCCCC", line_width=1)
    fig_mn.update_layout(
        **pdef(),
        height=320,
        yaxis_title="€",
        title_text="Monthly net variable cost per plant (spot + transfer − sales)",
    )
    st.plotly_chart(fig_mn, width="stretch")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Transfers
# ══════════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.markdown("### Plant-to-plant transfer volumes (kL)")

    if not any(u_sol[r].sum() > 0.5 for r in ROUTES):
        st.info(
            "No plant-to-plant transfers in the current solution. "
            "Try reducing Farm C volume or the S3 cap to force transfers."
        )
    else:
        fig_tr = go.Figure()
        for ri, (r, lbl) in enumerate(zip(ROUTES, ROUTE_LBL)):
            vals = u_sol[r] / 1e3
            fig_tr.add_trace(
                go.Bar(
                    name=lbl,
                    x=MONTHS,
                    y=vals,
                    marker_color=R_COLORS[ri],
                    opacity=0.85,
                    visible=True if vals.sum() > 0 else "legendonly",
                )
            )
        fig_tr.update_layout(
            **pdef(),
            barmode="group",
            height=340,
            yaxis_title="kL",
            title_text="Transfer volumes by route",
        )
        st.plotly_chart(fig_tr, width="stretch")

    st.markdown("### Transfer cost and routing summary")
    _DIST = {(0, 1): 160, (1, 0): 160, (1, 2): 120, (2, 1): 120, (0, 2): 260, (2, 0): 260}
    tr_rows = [
        {
            "Route": lbl,
            "Distance (km)": _DIST[r],
            "Cost (€/1000L)": TC[r],
            "Total volume (kL)": round(u_sol[r].sum() / 1e3, 1),
            "Total cost (€)": round(TC[r] * u_sol[r].sum() / 1000, 0),
            "Busiest month": MONTHS[u_sol[r].argmax()],
        }
        for r, lbl in zip(ROUTES, ROUTE_LBL)
        if u_sol[r].sum() > 0
    ]
    if tr_rows:
        st.dataframe(pd.DataFrame(tr_rows).set_index("Route"), width="stretch")

    st.markdown("### Why transfers happen — P3 deficit vs supply options")
    in_to_p3 = sum((u_sol[(i, j)] for (i, j) in ROUTES if j == 2), np.zeros(T))
    fig_p3 = go.Figure()
    fig_p3.add_trace(
        go.Bar(
            name="Farm C",
            x=MONTHS,
            y=np.minimum(V_[2], R_[2]) / 1e3,
            marker_color=P_COLORS[2],
            opacity=0.8,
        )
    )
    fig_p3.add_trace(
        go.Bar(
            name=f"Spot {S_NAMES[2]} (capped at {S3_CAP / 1e3:.0f} kL)",
            x=MONTHS,
            y=x_sol[2, 2] / 1e3,
            marker_color=S_COLORS[2],
            opacity=0.85,
        )
    )
    fig_p3.add_trace(
        go.Bar(
            name=f"Spot {S_NAMES[1]} (with transport)",
            x=MONTHS,
            y=x_sol[2, 1] / 1e3,
            marker_color=S_COLORS[1],
            opacity=0.85,
        )
    )
    fig_p3.add_trace(
        go.Bar(
            name=f"Spot {S_NAMES[0]}",
            x=MONTHS,
            y=x_sol[2, 0] / 1e3,
            marker_color=S_COLORS[0],
            opacity=0.85,
            visible=True if x_sol[2, 0].sum() > 0 else "legendonly",
        )
    )
    fig_p3.add_trace(
        go.Bar(
            name="Incoming transfers",
            x=MONTHS,
            y=in_to_p3 / 1e3,
            marker_color=COL_TRANS_IN,
            opacity=0.8,
            visible=True if in_to_p3.sum() > 0 else "legendonly",
        )
    )
    fig_p3.add_trace(
        go.Scatter(
            name="Production need",
            x=MONTHS,
            y=R_[2] / 1e3,
            mode="lines+markers",
            line=dict(color=COL_NEED, width=2.5, dash="dash"),
            marker=dict(size=6),
        )
    )
    fig_p3.add_hline(
        y=S3_CAP / 1e3,
        line_dash="dot",
        line_color=COL_S3_CAP,
        annotation_text="S3 cap",
        annotation_position="right",
    )
    fig_p3.update_layout(
        **pdef(),
        barmode="stack",
        height=400,
        yaxis_title="kL",
        title_text="Plant 3 — how the monthly deficit is covered",
    )
    st.plotly_chart(fig_p3, width="stretch")
    st.caption(
        f"Plant 3 is chronically undersupplied. S3 is used to its cap ({S3_CAP / 1e3:.0f} kL) "
        "in most months. Remaining deficit is covered by S2 purchases (shipped from South) "
        "or inter-plant transfers. Adjust Farm C volume or S3 cap in the sidebar to see "
        "how the routing changes."
    )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Shadow prices
# ══════════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.markdown("### Shadow prices — balance constraints (€/kL)")
    st.markdown(
        "The shadow price of the balance constraint at plant p in month t is the change in "
        "total cost per additional litre of raw milk at that plant. "
        "**Positive** = plant is short (more supply saves money at the spot price). "
        "**Negative** = plant is long (less supply would save on purchases)."
    )

    duals_eq = res["duals_eq"] * 1000  # convert €/L → €/kL
    fig_sh = go.Figure()
    for p in range(NP):
        fig_sh.add_trace(
            go.Scatter(
                name=P_NAMES[p],
                x=MONTHS,
                y=duals_eq[p],
                mode="lines+markers",
                line=dict(color=P_COLORS[p], width=2),
                marker=dict(size=7),
            )
        )
    fig_sh.add_hline(y=0, line_dash="dash", line_color="#CCCCCC", line_width=1)
    fig_sh.update_layout(
        **pdef(),
        height=360,
        yaxis_title="Shadow price (€/kL)",
        title_text="Balance constraint shadow prices by plant",
    )
    st.plotly_chart(fig_sh, width="stretch")

    st.markdown("### S3 capacity constraint shadow prices (€/kL)")
    st.markdown(
        "Non-zero value means the S3 cap is binding that month. "
        "The magnitude tells you how much relaxing the cap by 1 kL would save."
    )
    duals_s3 = res["duals_s3"] * 1000
    fig_s3 = go.Figure(
        go.Bar(
            x=MONTHS,
            y=-duals_s3,
            marker_color=[COL_S3_CAP if v < -0.5 else "#CCCCCC" for v in duals_s3],
            text=[f"€{-v:.1f}" if abs(v) > 0.5 else "" for v in duals_s3],
            textposition="outside",
            hovertemplate="%{y:.2f} €/kL<extra></extra>",
            name="S3 shadow price",
        )
    )
    fig_s3.update_layout(
        **pdef(),
        height=280,
        yaxis_title="Value of relaxing S3 cap (€/kL)",
        title_text="S3 capacity shadow price — red = cap is binding",
    )
    st.plotly_chart(fig_s3, width="stretch")

    df_sh = pd.DataFrame(
        {P_NAMES[p]: duals_eq[p].round(2) for p in range(NP)},
        index=MONTHS,
    )
    df_sh["S3 cap (€/kL)"] = (-duals_s3).round(2)

    def colour_cells(val):
        if not isinstance(val, float):
            return ""
        if val > 1:
            return "color:#C0392B; font-weight:600"
        if val < -1:
            return "color:#27AE60; font-weight:600"
        return ""

    st.dataframe(df_sh.style.map(colour_cells), width="stretch")
    st.info(
        "💡 **Experiment:** reduce Farm C volume to 0.5× in the sidebar. "
        "Watch Plant 3's shadow price spike and S3 shadow prices increase — "
        "the solver is working hard to route milk from P2 via transfers. "
        "Then set transport costs to 0× and see the network fully arbitrage."
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Milk Planning LP Dashboard · 3 plants · "
    "252 variables · 48 constraints · scipy HiGHS exact LP · "
    "Re-solves on every input change."
)
