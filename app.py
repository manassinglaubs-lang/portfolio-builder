import streamlit as st, pandas as pd, numpy as np
import plotly.express as px, plotly.graph_objects as go
from io import BytesIO
from pathlib import Path

st.set_page_config(page_title="Smart Portfolio Builder", page_icon="📈", layout="wide")

# ============================================================ STYLE
C = {"Large": "#4F46E5", "Mid": "#14B8A6", "Small": "#F59E0B",
     "good": "#10B981", "warn": "#F59E0B", "bad": "#F43F5E"}
st.markdown("""
<style>
.block-container {padding-top: 1.5rem; max-width: 1250px;}
.hero {background: linear-gradient(120deg,#4F46E5 0%,#7C3AED 55%,#14B8A6 100%);
       color:white; padding:28px 32px; border-radius:20px; margin-bottom:18px;}
.hero h1 {margin:0; font-size:2.1rem; color:white;}
.hero p {margin:6px 0 0 0; font-size:1.05rem; opacity:.92; color:white;}
.card {background: rgba(128,128,128,.09); border:1px solid rgba(128,128,128,.18);
       border-radius:16px; padding:16px 18px; height:100%;}
.card .lbl {font-size:.82rem; opacity:.7; text-transform:uppercase; letter-spacing:.04em;}
.card .val {font-size:1.7rem; font-weight:700; line-height:1.25;}
.card .sub {font-size:.85rem; opacity:.7;}
.verdict {border-radius:16px; padding:18px 22px; margin:10px 0 4px 0; border-left:8px solid;}
.step {background: rgba(79,70,229,.08); border-radius:14px; padding:14px 16px; height:100%;}
.step b {color:#4F46E5;}
.pill {display:inline-block; padding:2px 10px; border-radius:99px; font-size:.78rem;
       color:white; margin-right:6px;}
div[data-testid="stTabs"] button {font-size:1rem;}
</style>""", unsafe_allow_html=True)

def card(label, value, sub=""):
    return f'<div class="card"><div class="lbl">{label}</div><div class="val">{value}</div><div class="sub">{sub}</div></div>'

def explain(text):
    st.markdown(f"<div style='opacity:.8;margin:-4px 0 12px 0'>{text}</div>", unsafe_allow_html=True)

# ============================================================ SIDEBAR
PRESETS = {
    "Recommended: growth-focused": {"Growth": 30, "Profitability": 20, "Size": 15, "Valuation": 15, "Risk": 10, "Technical": 10},
    "Balanced": {"Growth": 20, "Profitability": 20, "Size": 15, "Valuation": 20, "Risk": 15, "Technical": 10},
    "Safety-first": {"Growth": 15, "Profitability": 20, "Size": 20, "Valuation": 10, "Risk": 30, "Technical": 5},
    "Custom": None}

with st.sidebar:
    st.title("⚙️ Settings")
    st.caption("Everything is pre-set. Open a section only if you want to experiment.")
    up = st.file_uploader("Use your own data file (optional)", type="csv")
    preset = st.selectbox("Investment style", list(PRESETS),
                          help="Decides how much each factor matters when ranking stocks.")
    if preset == "Custom":
        wraw = {k: st.slider(k, 0, 50, v) for k, v in PRESETS["Recommended: growth-focused"].items()}
    else:
        wraw = PRESETS[preset]
        st.caption("Growth {Growth}% · Quality {Profitability}% · Size {Size}% · Price {Valuation}% · "
                   "Safety {Risk}% · Trend {Technical}%".format(**wraw))
    tot = sum(wraw.values()) or 1
    W = {k: v / tot for k, v in wraw.items()}

    with st.expander("💰 Money and target"):
        CAPITAL = st.number_input("Starting money (Rs)", value=10_000_000, step=500_000)
        T_LOW = st.number_input("Target, low (x your money)", value=2.00, step=0.05)
        T_HIGH = st.number_input("Target, high (x your money)", value=2.15, step=0.05)
    with st.expander("🔎 Stock quality rules"):
        MIN_ROE = st.number_input("Minimum ROE %", value=15.0)
        MIN_ROCE = st.number_input("Minimum ROCE % (not for banks)", value=15.0)
        G_LARGE = st.number_input("Minimum sales growth % (Large)", value=10.0)
        G_MIDSMALL = st.number_input("Minimum sales growth % (Mid/Small)", value=15.0)
        MAX_BETA = st.number_input("Maximum beta", value=1.5)
        MAX_SECTOR = st.number_input("Max stocks from one industry", value=3, step=1)
    with st.expander("🧩 Portfolio mix"):
        a_l = st.slider("Big companies (Large-cap) %", 0, 100, 30)
        a_m = st.slider("Medium companies (Mid-cap) %", 0, 100, 40)
        a_s = max(0, 100 - a_l - a_m)
        st.caption(f"Small companies (Small-cap): {a_s}%")
        MAX_STOCK = st.slider("Max % in any one stock", 5, 25, 12) / 100
    with st.expander("📐 Return assumptions"):
        RF = st.number_input("Safe return, e.g. govt bonds %", value=7.0) / 100
        ERP = st.number_input("Extra return expected from stocks %", value=7.0) / 100

YEARS = 3
tb = (a_l + a_m + a_s) or 1
BUCKET_ALLOC = {"Large": a_l / tb, "Mid": a_m / tb, "Small": a_s / tb}

# ============================================================ DATA
@st.cache_data
def load(file):
    d = pd.read_csv(file if file is not None else "stock_data.csv")
    d = d.dropna(subset=["MarketCap_Cr"]).reset_index(drop=True)
    d["Financial"] = d["Sector"].isin(["Banking", "NBFC"])
    return d

if up is None and not Path("stock_data.csv").exists():
    st.error("stock_data.csv not found. Put it in the same folder as app.py, or upload it in the sidebar.")
    st.stop()
raw = load(up)

# ============================================================ CORE LOGIC
def pct(s, higher=True):
    r = s.rank(pct=True, na_option="keep") * 100
    return r if higher else 100 - r + 100 / len(s)

def screen_and_score(df, W):
    df = df.copy()
    df["T_ROE"] = df["ROE_%"] > MIN_ROE
    df["T_ROCE"] = df["Financial"] | (df["ROCE_%"] > MIN_ROCE)
    df["T_Growth"] = df["SalesYoY_%"] > df["Cap_Bucket"].map(
        {"Large": G_LARGE, "Mid": G_MIDSMALL, "Small": G_MIDSMALL})
    df["T_Beta"] = df["Beta"] < MAX_BETA
    tests = ["T_ROE", "T_ROCE", "T_Growth", "T_Beta"]
    df["Tests_Passed"] = df[tests].sum(axis=1)
    df["Screen_Pass"] = df["Tests_Passed"] == len(tests)
    S = pd.DataFrame(index=df.index)
    for b, g in df.groupby("Cap_Bucket"):
        i = g.index
        S.loc[i, "Growth"] = (pct(g["SalesYoY_%"]).fillna(0) + pct(g["NI_Growth_%"]).fillna(0)) / 2
        roce = pct(g["ROCE_%"]).fillna(pct(g["ROE_%"]))
        S.loc[i, "Profitability"] = (pct(g["ROE_%"]).fillna(0) + roce) / 2
        S.loc[i, "Size"] = pct(g["MarketCap_Cr"])
        S.loc[i, "Valuation"] = (pct(g["PE"], False).fillna(0) + pct(g["PEG"], False).fillna(0)
                                 + pct(g["PBV"], False).fillna(0)) / 3
        S.loc[i, "Risk"] = (pct(g["Beta"], False) + pct(g["StdDev_%"], False)) / 2
        S.loc[i, "Technical"] = g["Above_200DMA"].astype(float) * 50 + pct(g["Price"] / g["DMA200"]) * .5
    df = df.join(S.add_prefix("S_"))
    df["Total_Score"] = sum(df[f"S_{k}"] * w for k, w in W.items())
    return df.sort_values(["Screen_Pass", "Tests_Passed", "Total_Score"], ascending=False), tests

def select(df):
    picked = []
    for b in ["Large", "Mid", "Small"]:
        n = 0
        for idx, r in df[df.Cap_Bucket == b].iterrows():
            same = sum(df.loc[p, "Sector"] == r["Sector"] for p in picked)
            if n < 5 and same < MAX_SECTOR:
                picked.append(idx); n += 1
    return df.loc[picked].copy()

def allocate(sel):
    sel = sel.copy(); sel["Weight"] = 0.0
    for b, share in BUCKET_ALLOC.items():
        g = sel[sel.Cap_Bucket == b]
        if g.empty or share == 0: continue
        w = g.Total_Score / g.Total_Score.sum() * share
        for _ in range(10):
            over = w > MAX_STOCK
            if not over.any() or (~over).sum() == 0: break
            excess = (w[over] - MAX_STOCK).sum(); w[over] = MAX_STOCK
            w[~over] += excess * w[~over] / w[~over].sum()
        sel.loc[g.index, "Weight"] = w
    sel["Amount_Rs"] = sel.Weight * CAPITAL
    sel["Shares"] = (sel.Amount_Rs // sel.Price).astype(int)
    sel["Invested_Rs"] = sel.Shares * sel.Price
    return sel

@st.cache_data(show_spinner="Downloading price history...")
def get_cov(tickers):
    try:
        import yfinance as yf
        p = yf.download(list(tickers), start="2023-10-01", end="2026-09-30",
                        auto_adjust=True, progress=False)["Close"]
        r = p.pct_change().dropna(how="all")[list(tickers)].fillna(0)
        return r.cov().values * 252
    except Exception:
        return None

@st.cache_data
def simulate(mu, sigma, capital, years=3, n=5000, seed=42):
    rng = np.random.default_rng(seed); steps = years * 12
    drift = (np.log(1 + mu) - 0.5 * sigma ** 2) / 12
    z = rng.standard_normal((n, steps))
    return capital * np.exp(np.cumsum(drift + sigma / np.sqrt(12) * z, axis=1))

# plain-English helpers
def beta_label(b): return "Low" if b < .9 else ("Moderate" if b < 1.1 else "High")
def pe_label(pe): return "relatively cheap" if pe < 20 else ("fairly priced" if pe < 40 else "expensive")
def money(x): return f"₹{x/1e7:.2f} cr" if x >= 1e7 else f"₹{x/1e5:.1f} lakh"

def why_points(r, tests):
    pts = [f"💪 **Quality:** earns ₹{r['ROE_%']:.0f} profit for every ₹100 of shareholders' money (ROE)."]
    pts.append(f"🚀 **Growth:** sales grew {r['SalesYoY_%']:+.0f}% and profit {r['NI_Growth_%']:+.0f}% last year.")
    pts.append(f"🏷️ **Price:** P/E of {r.PE:.0f} means it is {pe_label(r.PE)}.")
    pts.append(f"🎢 **Ups and downs:** market sensitivity (beta) {r.Beta:.2f} → {beta_label(r.Beta).lower()} risk.")
    pts.append("📈 **Trend:** price is above its 200-day average (healthy uptrend)." if r.Above_200DMA
               else "📉 **Trend:** price is below its 200-day average (weak trend right now).")
    if not r.Screen_Pass:
        failed = {"ROE": "ROE", "ROCE": "ROCE", "Growth": "sales growth", "Beta": "beta"}
        pts.append("⚠️ **Heads-up:** narrowly missed the quality rule on " +
                   ", ".join(failed[t[2:]] for t in tests if not r[t]) +
                   ". Included to complete the 5 per size group.")
    return pts

# ============================================================ PIPELINE
ranked, tests = screen_and_score(raw, W)
sel = select(ranked)
port = allocate(sel)
cash = CAPITAL - port.Invested_Rs.sum()

port["Ret_CAPM"] = RF + port.Beta * ERP
port["Ret_Hist"] = (port["Return_3Y_CAGR_%"] / 100).clip(upper=.40)
port["Ret_Fund"] = (port["NI_Growth_%"] / 100).clip(-.10, .35) * .7
SCEN = {"Cautious": ("Based on market-wide returns for this risk level", float((port.Weight * port.Ret_CAPM).sum())),
        "Realistic": ("Based on 70% of the companies' recent profit growth", float((port.Weight * port.Ret_Fund).sum())),
        "Optimistic": ("Assumes each stock repeats its last 3 years", float((port.Weight * port.Ret_Hist).sum()))}

cov = get_cov(tuple(port.Ticker))
if cov is None:
    s_ = (port["StdDev_%"] / 100).values
    cov = np.outer(s_, s_) * (0.5 + 0.5 * np.eye(len(s_)))
    cov_note = "Live price download unavailable, so stocks were assumed to move together moderately (correlation 0.5)."
else:
    cov_note = "Calculated from 3 years of real daily price movements."
w_ = port.Weight.values
SIGMA = float(np.sqrt(w_ @ cov @ w_))
P_BETA = float((port.Weight * port.Beta).sum())
REQ_LOW, REQ_HIGH = T_LOW ** (1 / YEARS) - 1, T_HIGH ** (1 / YEARS) - 1

rows = []
for name, (desc, m) in SCEN.items():
    f = simulate(m, SIGMA, CAPITAL)[:, -1]
    rows.append({"Scenario": name, "Assumption": desc, "Yearly return": m,
                 "Typical outcome": np.median(f), "Bad case": np.percentile(f, 10),
                 "Good case": np.percentile(f, 90),
                 "Chance of reaching target": float(np.mean(f >= T_LOW * CAPITAL))})
res = pd.DataFrame(rows)
mid_prob = float(res.loc[res.Scenario == "Realistic", "Chance of reaching target"].iloc[0])
if mid_prob < .20: vtxt, vcol, vicon = "Unlikely", C["bad"], "🔴"
elif mid_prob < .50: vtxt, vcol, vicon = "Possible, but uncertain", C["warn"], "🟡"
else: vtxt, vcol, vicon = "Likely", C["good"], "🟢"

cols = ["Company", "Cap_Bucket", "Sector", "Screen_Pass", "Tests_Passed", "Total_Score"] + [f"S_{k}" for k in W]
show = port[["Company", "Ticker", "Cap_Bucket", "Sector", "Total_Score", "Weight", "Amount_Rs",
             "Price", "Shares", "Invested_Rs", "Beta"]].copy()
show["Weight"] = (show.Weight * 100).round(2)

# ============================================================ HEADER
st.markdown(f"""<div class="hero"><h1>📈 Smart Portfolio Builder</h1>
<p>Turning {money(CAPITAL)} into {money(T_LOW*CAPITAL)}–{money(T_HIGH*CAPITAL)} in {YEARS} years:
how the 15 stocks were chosen, how the money is split, and whether the goal is realistic.</p></div>""",
            unsafe_allow_html=True)

tabs = st.tabs(["🏁 Overview", "🔎 Stocks", "⚖️ What matters", "🏆 Ranking",
                "💼 Portfolio", "🎯 Will we hit the target?", "📥 Download", "📖 Glossary"])

# ------------------------------------------------------------ OVERVIEW
with tabs[0]:
    c = st.columns(4)
    c[0].markdown(card("Starting money", money(CAPITAL), "invested today"), unsafe_allow_html=True)
    c[1].markdown(card("Goal in 3 years", f"{money(T_LOW*CAPITAL)} – {money(T_HIGH*CAPITAL)}",
                       f"{T_LOW:.2f}x to {T_HIGH:.2f}x your money"), unsafe_allow_html=True)
    c[2].markdown(card("Growth needed", f"{REQ_LOW:.0%} – {REQ_HIGH:.0%} / year",
                       "Indian stocks have averaged roughly 12–15%"), unsafe_allow_html=True)
    c[3].markdown(card("Risk level", beta_label(P_BETA), f"swings about ±{SIGMA:.0%} a year"),
                  unsafe_allow_html=True)
    st.markdown(f"""<div class="verdict" style="background:{vcol}22;border-color:{vcol}">
    <div style="font-size:1.25rem;font-weight:700">{vicon} Reaching {money(T_LOW*CAPITAL)}: {vtxt}
    ({mid_prob:.0%} chance in the realistic case)</div>
    <div style="opacity:.85;margin-top:4px">The goal needs a return well above normal market returns, so even a
    carefully chosen portfolio reaches it only if things go better than average. Details in the
    "Will we hit the target?" tab.</div></div>""", unsafe_allow_html=True)

    st.markdown("### How this works, in 5 steps")
    steps = [("1. Start wide", "30 well-known companies: large, medium and small."),
             ("2. Filter", "Drop companies that are not profitable, growing or stable enough."),
             ("3. Score", "Rate every company from 0–100 on growth, quality, price, safety and trend."),
             ("4. Pick 15", "The 5 best from each size group, with no industry overloaded."),
             ("5. Split money", "Higher score gets more money, with a cap on any single stock.")]
    sc = st.columns(5)
    for col, (t, d) in zip(sc, steps):
        col.markdown(f'<div class="step"><b>{t}</b><br>{d}</div>', unsafe_allow_html=True)

    st.markdown("### Money needed to reach the goal")
    yrs = np.arange(0, YEARS + 1)
    fig = go.Figure()
    fig.add_scatter(x=yrs, y=CAPITAL * (1 + REQ_LOW) ** yrs / 1e7, name=f"To reach {T_LOW:.2f}x",
                    line=dict(color=C["Large"], width=4))
    fig.add_scatter(x=yrs, y=CAPITAL * (1 + REQ_HIGH) ** yrs / 1e7, name=f"To reach {T_HIGH:.2f}x",
                    line=dict(color=C["Mid"], width=4))
    fig.update_layout(template="plotly_white", height=330, xaxis_title="Years from now",
                      yaxis_title="Value (₹ crore)", margin=dict(t=10), legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------ STOCKS
with tabs[1]:
    st.subheader("The 30 companies we started with")
    explain("Figures are for financial year 2025-26 (consolidated). Hover over a column title for what it means. "
            "Open the 📖 Glossary for plain-English definitions.")
    pick = st.radio("Show", ["All", "Large", "Mid", "Small"], horizontal=True)
    d = raw if pick == "All" else raw[raw.Cap_Bucket == pick]
    friendly = d[["Company", "Sector", "Cap_Bucket", "MarketCap_Cr", "SalesYoY_%", "NI_Growth_%", "ROE_%", "ROCE_%",
                  "PE", "PEG", "PBV", "Beta", "StdDev_%", "RSI14"]].rename(columns={
        "Cap_Bucket": "Size", "MarketCap_Cr": "Market value (₹ cr)", "SalesYoY_%": "Sales growth %",
        "NI_Growth_%": "Profit growth %", "ROE_%": "ROE %", "ROCE_%": "ROCE %", "PE": "P/E", "PBV": "P/B",
        "Beta": "Beta", "StdDev_%": "Volatility %", "RSI14": "RSI"})
    st.dataframe(friendly.round(2), use_container_width=True, hide_index=True, height=480)
    st.plotly_chart(px.scatter(raw, x="SalesYoY_%", y="ROE_%", color="Cap_Bucket", size="MarketCap_Cr",
                               hover_name="Company", color_discrete_map=C, template="plotly_white",
                               labels={"SalesYoY_%": "Sales growth % (higher = growing faster)",
                                       "ROE_%": "ROE % (higher = more profitable)", "Cap_Bucket": "Size"},
                               title="Growth vs profitability: top-right is the sweet spot"),
                    use_container_width=True)

# ------------------------------------------------------------ WEIGHTS
with tabs[2]:
    st.subheader("What matters when choosing a stock?")
    explain("Each factor gets a share of 100%. More weight means more influence on a stock's final score. "
            f"You are using the style: <b>{preset}</b>. Change it in the sidebar and everything updates.")
    info = {"Growth": ("🚀 Growth", "Sales and profit growth", "We need 26–29% a year, so growth matters most."),
            "Profitability": ("💪 Quality", "ROE and ROCE", "Checks that growth is profitable and lasting."),
            "Size": ("🏢 Size", "Company market value", "Bigger firms are more stable and easier to trade."),
            "Valuation": ("🏷️ Price", "P/E, PEG, P/B", "Stops us overpaying for growth."),
            "Risk": ("🛡️ Safety", "Beta and volatility", "Limits sharp falls; less weight because we want returns."),
            "Technical": ("📈 Trend", "Price vs 200-day average", "Helps timing, but noisy, so smallest weight.")}
    wt = pd.DataFrame({"Factor": [info[k][0] for k in W], "Measured by": [info[k][1] for k in W],
                       "Weight %": [round(v * 100, 1) for v in W.values()],
                       "Why it matters": [info[k][2] for k in W]})
    a, b = st.columns([3, 2])
    a.dataframe(wt, use_container_width=True, hide_index=True,
                column_config={"Weight %": st.column_config.ProgressColumn("Weight %", min_value=0, max_value=50, format="%.0f%%")})
    b.plotly_chart(px.pie(wt, names="Factor", values="Weight %", hole=.55, template="plotly_white",
                          color_discrete_sequence=px.colors.qualitative.Vivid).update_layout(margin=dict(t=10, b=10)),
                   use_container_width=True)

# ------------------------------------------------------------ RANKING
with tabs[3]:
    st.subheader("How the stocks ranked")
    explain(f"Step 1: a stock must pass 4 quality checks (ROE above {MIN_ROE:.0f}%, ROCE above {MIN_ROCE:.0f}%, "
            f"enough sales growth, beta below {MAX_BETA}). Step 2: passing stocks are scored 0–100 against others "
            f"in their own size group. <b>{int(ranked.Screen_Pass.sum())} of {len(ranked)} passed all four checks.</b>")
    contrib = port[["Company", "Cap_Bucket"]].copy()
    for k in W: contrib[info[k][0]] = port[f"S_{k}"] * W[k]
    contrib["Total"] = contrib[[info[k][0] for k in W]].sum(axis=1)
    contrib = contrib.sort_values("Total")
    long = contrib.melt(id_vars=["Company", "Cap_Bucket", "Total"], var_name="Factor", value_name="Points")
    fig = px.bar(long, x="Points", y="Company", color="Factor", orientation="h", template="plotly_white",
                 color_discrete_sequence=px.colors.qualitative.Vivid, height=520,
                 title="Selected 15 stocks: score and where the points came from")
    fig.update_layout(yaxis=dict(categoryorder="array", categoryarray=contrib.Company))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Why each stock was picked")
    for b in ["Large", "Mid", "Small"]:
        st.markdown(f"<span class='pill' style='background:{C[b]}'>{b}-cap</span>", unsafe_allow_html=True)
        for _, r in port[port.Cap_Bucket == b].sort_values("Total_Score", ascending=False).iterrows():
            tag = "" if r.Screen_Pass else "  ⚠️"
            with st.expander(f"{r.Company}  ·  {r.Sector}  ·  score {r.Total_Score:.0f}/100{tag}"):
                for p in why_points(r, tests): st.markdown(p)

    with st.expander("See the full ranking of all 30 companies"):
        full = ranked[cols].round(0).rename(columns={"Cap_Bucket": "Size", "Screen_Pass": "Passed all checks",
                                                     "Tests_Passed": "Checks passed (of 4)", "Total_Score": "Total score"})
        st.dataframe(full, use_container_width=True, hide_index=True,
                     column_config={"Total score": st.column_config.ProgressColumn(
                         "Total score", min_value=0, max_value=100, format="%.0f")})

# ------------------------------------------------------------ PORTFOLIO
with tabs[4]:
    st.subheader("Where the money goes")
    explain("Each size group gets a fixed share of the money. Inside a group, stronger stocks get more, "
            f"but no single stock gets more than {MAX_STOCK:.0%}.")
    c = st.columns(4)
    c[0].markdown(card("Invested", money(port.Invested_Rs.sum()), "in 15 stocks"), unsafe_allow_html=True)
    c[1].markdown(card("Left as cash", f"₹{cash:,.0f}", "too small to buy another share"), unsafe_allow_html=True)
    c[2].markdown(card("Industries", f"{port.Sector.nunique()}", "spread across sectors"), unsafe_allow_html=True)
    c[3].markdown(card("Market sensitivity", f"{P_BETA:.2f}", "1.00 = moves like the market"), unsafe_allow_html=True)
    st.write("")
    a, b = st.columns(2)
    fig = px.pie(port, names="Company", values="Weight", hole=.5, template="plotly_white",
                 color_discrete_sequence=px.colors.qualitative.Vivid, title="Share of money by stock")
    fig.update_traces(textposition="inside", textinfo="percent"); a.plotly_chart(fig, use_container_width=True)
    g = port.groupby("Cap_Bucket").Weight.sum().reset_index()
    fig = px.pie(g, names="Cap_Bucket", values="Weight", hole=.5, template="plotly_white",
                 color="Cap_Bucket", color_discrete_map=C, title="Share of money by company size")
    b.plotly_chart(fig, use_container_width=True)
    sec = port.groupby("Sector").Weight.sum().reset_index().sort_values("Weight")
    st.plotly_chart(px.bar(sec, x="Weight", y="Sector", orientation="h", template="plotly_white",
                           title="Share of money by industry", color_discrete_sequence=[C["Large"]]),
                    use_container_width=True)
    t = show.rename(columns={"Cap_Bucket": "Size", "Total_Score": "Score", "Weight": "Share %",
                             "Amount_Rs": "Planned ₹", "Price": "Price ₹", "Shares": "Shares to buy",
                             "Invested_Rs": "Actual ₹"}).round(2)
    st.dataframe(t, use_container_width=True, hide_index=True)

# ------------------------------------------------------------ FEASIBILITY
with tabs[5]:
    st.subheader("Can this portfolio reach the goal?")
    explain("We ran 5,000 possible futures for each scenario. Each future randomly moves stock prices up and down "
            "by the amounts seen historically. The share of futures that end above the goal is the chance of success.")
    show_res = res.copy()
    st.dataframe(show_res, use_container_width=True, hide_index=True, column_config={
        "Yearly return": st.column_config.NumberColumn(format="percent"),
        "Typical outcome": st.column_config.NumberColumn(format="₹%.0f"),
        "Bad case": st.column_config.NumberColumn("Bad case (1 in 10)", format="₹%.0f"),
        "Good case": st.column_config.NumberColumn("Good case (1 in 10)", format="₹%.0f"),
        "Chance of reaching target": st.column_config.ProgressColumn(
            f"Chance of reaching {T_LOW:.2f}x", min_value=0, max_value=1, format="percent")})
    cc = st.columns(3)
    for col, (nm, (_, m)) in zip(cc, SCEN.items()):
        pr = float(res.loc[res.Scenario == nm, "Chance of reaching target"].iloc[0])
        med = float(res.loc[res.Scenario == nm, "Typical outcome"].iloc[0])
        col.markdown(card(nm, f"{pr:.0%} chance", f"typical result {money(med)}"), unsafe_allow_html=True)
    st.write("")
    pick = st.radio("Show the range of outcomes for:", list(SCEN), index=1, horizontal=True)
    p = simulate(SCEN[pick][1], SIGMA, CAPITAL) / 1e7
    q = {k: np.percentile(p, k, axis=0) for k in (10, 25, 50, 75, 90)}
    mo = np.arange(1, p.shape[1] + 1)
    fig = go.Figure()
    fig.add_scatter(x=mo, y=q[90], line=dict(width=0), showlegend=False)
    fig.add_scatter(x=mo, y=q[10], fill="tonexty", line=dict(width=0), name="Likely range (80% of futures)",
                    fillcolor="rgba(79,70,229,.15)")
    fig.add_scatter(x=mo, y=q[75], line=dict(width=0), showlegend=False)
    fig.add_scatter(x=mo, y=q[25], fill="tonexty", line=dict(width=0), name="Middle half of futures",
                    fillcolor="rgba(79,70,229,.30)")
    fig.add_scatter(x=mo, y=q[50], name="Typical path", line=dict(color=C["Large"], width=4))
    fig.add_hline(y=T_LOW * CAPITAL / 1e7, line_dash="dash", line_color=C["good"], annotation_text="Goal (low)")
    fig.add_hline(y=T_HIGH * CAPITAL / 1e7, line_dash="dash", line_color=C["bad"], annotation_text="Goal (high)")
    fig.update_layout(template="plotly_white", height=430, xaxis_title="Months from now",
                      yaxis_title="Portfolio value (₹ crore)", legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)
    fig = px.histogram(x=p[:, -1], nbins=60, template="plotly_white", color_discrete_sequence=[C["Mid"]],
                       labels={"x": "Value after 3 years (₹ crore)"}, title="Where we could end up after 3 years")
    fig.add_vline(x=T_LOW * CAPITAL / 1e7, line_dash="dash", line_color=C["good"])
    st.plotly_chart(fig, use_container_width=True)
    best = res["Typical outcome"].max()
    st.info(f"**In plain words:** the best typical result across scenarios is {money(best)}, against a goal of "
            f"{money(T_LOW*CAPITAL)}–{money(T_HIGH*CAPITAL)}. {cov_note} The simulation ignores taxes, trading costs "
            "and rebalancing, and past performance does not guarantee future results.")

# ------------------------------------------------------------ DOWNLOAD
with tabs[6]:
    st.subheader("Download everything as Excel")
    explain("One file with the raw data, weights, full ranking, selected stocks, portfolio and feasibility results.")
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        raw.drop(columns=["Financial"]).to_excel(xw, sheet_name="Raw data", index=False)
        pd.DataFrame({"Factor": list(W), "Weight": list(W.values())}).to_excel(xw, sheet_name="Weights", index=False)
        ranked[cols].round(2).to_excel(xw, sheet_name="Ranking", index=False)
        pd.DataFrame({"Company": port.Company,
                      "Why picked": [" | ".join(why_points(r, tests)).replace("**", "") for _, r in port.iterrows()]}
                     ).to_excel(xw, sheet_name="Justification", index=False)
        show.to_excel(xw, sheet_name="Portfolio", index=False)
        res.to_excel(xw, sheet_name="Feasibility", index=False)
    st.download_button("⬇️ Download Excel report", buf.getvalue(), "Portfolio_Report.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")

# ------------------------------------------------------------ GLOSSARY
with tabs[7]:
    st.subheader("Plain-English glossary")
    G = {"Large / Mid / Small-cap": "Company size by stock-market value. Large = biggest and most stable; Small = riskiest but can grow fastest.",
         "Market value (market cap)": "Share price × number of shares: what the whole company is worth on the stock market.",
         "ROE (Return on Equity)": "Profit earned for every ₹100 of shareholders' money. Higher is better.",
         "ROCE (Return on Capital Employed)": "Profit earned on all the money the business uses (own plus borrowed). Not used for banks.",
         "Sales growth (YoY)": "How much sales grew compared with the previous year.",
         "EPS (Earnings per share)": "Profit per share. We measure its growth, since raw EPS can't be compared between companies.",
         "P/E": "Price you pay for ₹1 of yearly profit. Lower is cheaper, but fast growers usually have higher P/E.",
         "PEG": "P/E divided by profit growth. Below 1 is cheap for the growth you get; above 2 is pricey.",
         "P/B": "Share price compared with the company's book value (net assets).",
         "Beta": "How strongly a stock moves with the market. 1.0 = same as the market; above 1 swings more; below 1 swings less.",
         "Volatility (Std deviation)": "How much the price jumps around in a year. Higher means a bumpier ride.",
         "200-day average": "The average price over about 10 months. Trading above it suggests an uptrend.",
         "RSI": "A 0–100 momentum gauge. Above 70 can mean overheated; below 30 can mean oversold.",
         "CAGR": "Average yearly growth rate. Doubling in 3 years needs about 26% a year.",
         "Monte Carlo simulation": "Running thousands of random 'what if' futures to see how often the goal is reached.",
         "Diversification": "Spreading money across many stocks and industries so one bad stock hurts less."}
    q = st.text_input("Search a term", placeholder="e.g. beta")
    for k, v in G.items():
        if q.lower() in k.lower() or q.lower() in v.lower():
            with st.expander(k): st.write(v)
    st.caption("This project is for education. It is not investment advice.")