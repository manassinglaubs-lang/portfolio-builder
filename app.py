import streamlit as st, pandas as pd, numpy as np
import plotly.express as px, plotly.graph_objects as go, plotly.io as pio
from io import BytesIO
from pathlib import Path

st.set_page_config(page_title="Smart Portfolio Builder", page_icon="📈", layout="wide")

# ============================================================ THEME
NAVY, BLUE, GREEN, AMBER, RED, SLATE = "#0B1F3A", "#0B5FFF", "#00B386", "#F5A623", "#E5484D", "#64748B"
FIN = [BLUE, GREEN, AMBER, RED, "#7B61FF", "#06B6D4"]
FIN_LONG = FIN + ["#64748B", "#0EA5E9", "#84CC16", "#EC4899", "#14B8A6", "#A855F7", "#F97316", "#94A3B8", "#22C55E"]
BUCKET = {"Large": BLUE, "Mid": GREEN, "Small": AMBER}

tpl = go.layout.Template(pio.templates["plotly_white"])
tpl.layout.colorway = FIN
tpl.layout.font = dict(family="Inter, sans-serif", color=NAVY)
tpl.layout.paper_bgcolor = "rgba(0,0,0,0)"
tpl.layout.plot_bgcolor = "rgba(0,0,0,0)"
pio.templates["fin"] = tpl
pio.templates.default = "fin"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {{font-family: 'Inter', sans-serif;}}
.block-container {{padding-top: 1.2rem; max-width: 1300px;}}
.hero {{background: linear-gradient(120deg,{NAVY} 0%,#123C69 60%,#0B6E7F 100%); color:white;
        padding:26px 32px; border-radius:18px; margin-bottom:16px; border-bottom:4px solid {GREEN};}}
.hero h1 {{margin:0; font-size:2rem; color:white; font-weight:700;}}
.hero p {{margin:6px 0 0 0; font-size:1rem; color:#D6E4F0;}}
.card {{background:white; border:1px solid #E3E8F0; border-left:5px solid {BLUE}; border-radius:12px;
        padding:14px 18px; height:100%; box-shadow:0 1px 4px rgba(11,31,58,.07); color:{NAVY};}}
.card .lbl {{font-size:.76rem; color:{SLATE}; text-transform:uppercase; letter-spacing:.05em; font-weight:600;}}
.card .val {{font-size:1.6rem; font-weight:700; line-height:1.3; color:{NAVY};}}
.card .sub {{font-size:.82rem; color:{SLATE};}}
.verdict {{border-radius:12px; padding:16px 22px; margin:12px 0 6px 0; border-left:8px solid; color:{NAVY};
           background:white; box-shadow:0 1px 4px rgba(11,31,58,.07);}}
.step {{background:white; border:1px solid #E3E8F0; border-top:4px solid {GREEN}; border-radius:12px;
        padding:12px 14px; height:100%; color:{NAVY}; font-size:.9rem;}}
.step b {{color:{BLUE};}}
.pill {{display:inline-block; padding:3px 12px; border-radius:99px; font-size:.78rem; color:white;
        font-weight:600; margin:6px 6px 6px 0;}}
.note {{background:#EAF2FF; border-left:5px solid {BLUE}; border-radius:8px; padding:10px 14px;
        color:{NAVY}; font-size:.88rem; margin:6px 0 10px 0;}}
button[data-baseweb="tab"] {{font-weight:600; font-size:.95rem;}}
button[data-baseweb="tab"][aria-selected="true"] {{color:{GREEN};}}
div[data-baseweb="tab-highlight"] {{background-color:{GREEN} !important;}}
section[data-testid="stSidebar"] {{border-right:1px solid #E3E8F0;}}
</style>""", unsafe_allow_html=True)

def card(label, value, sub="", accent=BLUE):
    return (f'<div class="card" style="border-left-color:{accent}"><div class="lbl">{label}</div>'
            f'<div class="val">{value}</div><div class="sub">{sub}</div></div>')

def explain(text):
    st.markdown(f"<div style='color:#475569;margin:-2px 0 12px 0;font-size:.95rem'>{text}</div>",
                unsafe_allow_html=True)

# ============================================================ CONSTANTS
REQUIRED = ["Company", "Ticker", "Sector", "Cap_Bucket", "MarketCap_Cr", "PE", "PBV", "EPS", "SalesYoY_%",
            "NI_Growth_%", "ROE_%", "PEG", "Beta", "StdDev_%", "Return_3Y_CAGR_%", "Price", "DMA200",
            "Above_200DMA", "RSI14", "ROCE_%"]
PRESETS = {
    "Recommended: growth-focused": {"Growth": 30, "Profitability": 20, "Size": 15, "Valuation": 15, "Risk": 10, "Technical": 10},
    "Balanced": {"Growth": 20, "Profitability": 20, "Size": 15, "Valuation": 20, "Risk": 15, "Technical": 10},
    "Safety-first": {"Growth": 15, "Profitability": 20, "Size": 20, "Valuation": 10, "Risk": 30, "Technical": 5},
    "Custom": None}
info = {"Growth": ("🚀 Growth", "Sales and profit growth", "Fast growth is what lifts returns towards a high goal."),
        "Profitability": ("💪 Quality", "ROE and ROCE", "Checks that growth is profitable and lasting."),
        "Size": ("🏢 Size", "Company market value", "Bigger firms are more stable and easier to trade."),
        "Valuation": ("🏷️ Price", "P/E, PEG, P/B", "Stops us overpaying for growth."),
        "Risk": ("🛡️ Safety", "Beta and volatility", "Limits sharp falls; lower weight because we want returns."),
        "Technical": ("📈 Trend", "Price vs 200-day average", "Helps timing, but noisy, so smallest weight.")}
GLOSSARY = {
    "Large / Mid / Small-cap": "Company size by stock-market value. Large = biggest and most stable; Small = riskiest but can grow fastest.",
    "Market value (market cap)": "Share price × number of shares: what the whole company is worth on the stock market.",
    "ROE (Return on Equity)": "Profit earned for every ₹100 of shareholders' money. Higher is better.",
    "ROCE": "Profit earned on all the money the business uses (own plus borrowed). Not used for banks and NBFCs.",
    "Sales growth (YoY)": "How much sales grew compared with the previous year.",
    "EPS": "Earnings per share. We measure its growth, since raw EPS can't be compared between companies.",
    "P/E": "Price you pay for ₹1 of yearly profit. Lower is cheaper, but fast growers usually have a higher P/E.",
    "PEG": "P/E divided by profit growth. Below 1 is cheap for the growth you get; above 2 is pricey.",
    "P/B": "Share price compared with the company's book value (net assets).",
    "Beta": "How strongly a stock moves with the market. 1.0 = same as the market; above 1 swings more; below 1 swings less.",
    "Volatility (Std deviation)": "How much the price jumps around in a year. Higher means a bumpier ride.",
    "200-day average": "The average price over about 10 months. Trading above it suggests an uptrend.",
    "RSI": "A 0–100 momentum gauge. Above 70 can mean overheated; below 30 can mean oversold.",
    "CAGR": "Average yearly growth rate. Doubling in 3 years needs about 26% a year.",
    "Monte Carlo simulation": "Running thousands of random 'what if' futures to see how often the goal is reached.",
    "Nifty 50": "India's main stock-market index. We compare the portfolio with it to see if we beat the market.",
    "Diversification": "Spreading money across many stocks and industries so one bad stock hurts less."}

# ============================================================ SIDEBAR
with st.sidebar:
    st.title("⚙️ Settings")
    st.caption("Everything is pre-set. Change the three goal boxes first, then experiment if you like.")

    st.markdown("**📂 Data file**")
    up = st.file_uploader("Upload your own CSV (optional)", type="csv")
    st.markdown("<div class='note'>⚠️ Upload a <b>.csv</b> file with the <b>same columns as the demo file</b>. "
                "Otherwise the demo data is used.</div>", unsafe_allow_html=True)
    if Path("stock_data.csv").exists():
        st.download_button("⬇️ Download demo file (for format)", Path("stock_data.csv").read_bytes(),
                           "demo_stock_data.csv", "text/csv")

    with st.expander("💰 Your goal", expanded=True):
        CAPITAL = st.number_input("1. How much money do you have? (₹)", value=10_000_000,
                                  step=100_000, min_value=10_000)
        TARGET = st.number_input("2. How much do you want it to become? (₹)", value=20_000_000,
                                 step=100_000, min_value=10_000)
        d1, d2 = st.columns([2, 1])
        dur = d1.number_input("3. In how long?", value=3, min_value=1, step=1)
        unit = d2.selectbox("Unit", ["Years", "Months"])
        YEARS = dur if unit == "Years" else dur / 12
        MONTHS = max(1, int(round(YEARS * 12)))
        DUR_TXT = f"{dur} {unit[:-1] if dur == 1 else unit}".lower()
        if TARGET <= CAPITAL:
            st.error("Your target must be more than the money you start with.")
            st.stop()
        T_LOW = TARGET / CAPITAL
        st.caption(f"Needs about **{T_LOW ** (1 / YEARS) - 1:.0%} growth per year**.")
        if YEARS < 3:
            st.warning("Stocks can fall a lot over short periods. Under 3 years, results are very uncertain.")

    preset = st.selectbox("Investment style", list(PRESETS),
                          help="Decides how much each factor matters when ranking stocks.")
    if preset == "Custom":
        wraw = {k: st.slider(info[k][0], 0, 50, v) for k, v in PRESETS["Recommended: growth-focused"].items()}
    else:
        wraw = PRESETS[preset]
        st.caption("Growth {Growth}% · Quality {Profitability}% · Size {Size}% · Price {Valuation}% · "
                   "Safety {Risk}% · Trend {Technical}%".format(**wraw))
    W = {k: v / (sum(wraw.values()) or 1) for k, v in wraw.items()}

    with st.expander("📏 Stock quality rules"):
        MIN_ROE = st.number_input("Minimum ROE %", value=15.0)
        MIN_ROCE = st.number_input("Minimum ROCE % (not for banks)", value=15.0)
        G_LARGE = st.number_input("Minimum sales growth % (Large)", value=10.0)
        G_MIDSMALL = st.number_input("Minimum sales growth % (Mid/Small)", value=15.0)
        MAX_BETA = st.number_input("Maximum beta", value=1.5)
        MAX_SECTOR = st.number_input("Max stocks from one industry", value=3, step=1)
    with st.expander("🧩 Money split by company size", expanded=True):
        a_l = st.slider("Large-cap %", 0, 100, 30, help="Biggest, most stable companies")
        a_m = st.slider("Mid-cap %", 0, 100, 40, help="Faster growth, moderate risk")
        a_s = st.slider("Small-cap %", 0, 100, 30, help="Highest growth potential, highest risk")
        tb = (a_l + a_m + a_s) or 1
        BUCKET_ALLOC = {"Large": a_l / tb, "Mid": a_m / tb, "Small": a_s / tb}
        if (a_l + a_m + a_s) != 100:
            st.warning(f"Your total is {a_l + a_m + a_s}%. It was scaled to 100%: "
                       f"Large {BUCKET_ALLOC['Large']:.0%}, Mid {BUCKET_ALLOC['Mid']:.0%}, "
                       f"Small {BUCKET_ALLOC['Small']:.0%}.")
        MAX_STOCK = st.slider("Max % in any one stock", 5, 25, 12) / 100
        if max(BUCKET_ALLOC.values()) > 5 * MAX_STOCK:
            st.warning("One size group has more money than 5 stocks can hold under the cap, "
                       "so the cap may be exceeded. Raise the cap or rebalance the split.")
    with st.expander("📐 Return assumptions"):
        RF = st.number_input("Safe return, e.g. govt bonds %", value=7.0) / 100
        ERP = st.number_input("Extra return expected from stocks %", value=7.0) / 100

    with st.expander("📖 Glossary"):
        term = st.selectbox("Look up a term", list(GLOSSARY))
        st.info(GLOSSARY[term])
        st.caption("For education only. Not investment advice.")

# ============================================================ DATA
def prepare(d):
    d = d.dropna(subset=["MarketCap_Cr"]).reset_index(drop=True)
    d["Above_200DMA"] = d["Above_200DMA"].astype(str).str.upper().eq("TRUE")
    d["Financial"] = d["Sector"].isin(["Banking", "NBFC"])
    return d

raw = None
if up is not None:
    try:
        tmp = pd.read_csv(up)
        missing = [c for c in REQUIRED if c not in tmp.columns]
        bad = set(tmp["Cap_Bucket"].dropna().unique()) - {"Large", "Mid", "Small"} if "Cap_Bucket" in tmp else set()
        if missing:
            st.sidebar.error("Missing columns: " + ", ".join(missing) + ". Showing the demo data instead.")
        elif bad:
            st.sidebar.error("Cap_Bucket must be Large, Mid or Small. Showing the demo data instead.")
        else:
            raw = prepare(tmp)
            st.sidebar.success(f"Using your file: {len(raw)} companies.")
    except Exception as e:
        st.sidebar.error(f"Could not read the file ({e}). Showing the demo data instead.")
if raw is None:
    if not Path("stock_data.csv").exists():
        st.error("stock_data.csv not found. Put it next to app.py.")
        st.stop()
    raw = prepare(pd.read_csv("stock_data.csv"))

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

@st.cache_data(ttl=900, show_spinner="Fetching latest prices...")
def get_history(tickers, start):
    try:
        import yfinance as yf
        h = yf.download(list(tickers) + ["^NSEI"], start=start, auto_adjust=True, progress=False)["Close"]
        return h.dropna(how="all")
    except Exception:
        return None

@st.cache_data
def simulate(mu, sigma, capital, years, n=5000, seed=42):
    rng = np.random.default_rng(seed); steps = max(1, int(round(years * 12)))
    drift = (np.log(1 + mu) - 0.5 * sigma ** 2) / 12
    z = rng.standard_normal((n, steps))
    return capital * np.exp(np.cumsum(drift + sigma / np.sqrt(12) * z, axis=1))

def beta_label(b): return "Low" if b < .9 else ("Moderate" if b < 1.1 else "High")
def pe_label(pe): return "relatively cheap" if pe < 20 else ("fairly priced" if pe < 40 else "expensive")
def money(x): return f"₹{x/1e7:.2f} cr" if x >= 1e7 else f"₹{x/1e5:.1f} lakh"

def why_points(r, tests):
    pts = [f"💪 **Quality:** earns ₹{r['ROE_%']:.0f} profit for every ₹100 of shareholders' money (ROE).",
           f"🚀 **Growth:** sales grew {r['SalesYoY_%']:+.0f}% and profit {r['NI_Growth_%']:+.0f}% last year.",
           f"🏷️ **Price:** P/E of {r.PE:.0f} means it is {pe_label(r.PE)}.",
           f"🎢 **Ups and downs:** beta {r.Beta:.2f} means {beta_label(r.Beta).lower()} market sensitivity."]
    pts.append("📈 **Trend:** price is above its 200-day average (healthy uptrend)." if r.Above_200DMA
               else "📉 **Trend:** price is below its 200-day average (weak trend right now).")
    if not r.Screen_Pass:
        names = {"ROE": "ROE", "ROCE": "ROCE", "Growth": "sales growth", "Beta": "beta"}
        pts.append("⚠️ **Heads-up:** narrowly missed the quality rule on " +
                   ", ".join(names[t[2:]] for t in tests if not r[t]) +
                   ". Included to complete 5 stocks per size group.")
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
REQ_LOW = T_LOW ** (1 / YEARS) - 1

rows = []
for name, (desc, m) in SCEN.items():
    f = simulate(m, SIGMA, CAPITAL, YEARS)[:, -1]
    rows.append({"Scenario": name, "Assumption": desc, "Yearly return": m,
                 "Typical outcome": np.median(f), "Bad case": np.percentile(f, 10),
                 "Good case": np.percentile(f, 90),
                 "Chance of reaching target": float(np.mean(f >= TARGET))})
res = pd.DataFrame(rows)
mid_prob = float(res.loc[res.Scenario == "Realistic", "Chance of reaching target"].iloc[0])
if mid_prob < .20: vtxt, vcol, vicon = "Unlikely", RED, "🔴"
elif mid_prob < .50: vtxt, vcol, vicon = "Possible, but uncertain", AMBER, "🟡"
else: vtxt, vcol, vicon = "Likely", GREEN, "🟢"

cols = ["Company", "Cap_Bucket", "Sector", "Screen_Pass", "Tests_Passed", "Total_Score"] + [f"S_{k}" for k in W]
show = port[["Company", "Ticker", "Cap_Bucket", "Sector", "Total_Score", "Weight", "Amount_Rs",
             "Price", "Shares", "Invested_Rs", "Beta"]].copy()
show["Weight"] = (show.Weight * 100).round(2)

def build_insights():
    out = []
    wa = lambda c: float((port.Weight * port[c].fillna(0)).sum() / port.Weight.sum())
    exp_real = SCEN["Realistic"][1]
    f_real = simulate(exp_real, SIGMA, CAPITAL, YEARS)[:, -1]
    p_loss = float(np.mean(f_real < CAPITAL))
    out.append(("🎯", "Goal vs reality",
        f"The goal needs about <b>{REQ_LOW:.0%} a year</b>. In the realistic case this portfolio is expected to earn "
        f"about <b>{exp_real:.0%}</b>, a gap of {REQ_LOW - exp_real:.0%} points. Chance of reaching the goal: "
        f"<b>{mid_prob:.0%}</b>. Chance of ending below the starting amount: <b>{p_loss:.0%}</b>.", BLUE))
    top3 = port.nlargest(3, "Weight")
    names = ", ".join(f"{r.Company} ({r.Weight:.0%})" for _, r in top3.iterrows())
    out.append(("🏆", "Biggest bets",
        f"The three largest holdings are {names}, together <b>{top3.Weight.sum():.0%}</b> of your money. "
        f"The highest-scoring stock overall is <b>{port.loc[port.Total_Score.idxmax(), 'Company']}</b>.", GREEN))
    sec = port.groupby("Sector").Weight.sum().sort_values(ascending=False)
    out.append(("🧩", "Diversification",
        f"Money is spread over <b>{port.Sector.nunique()} industries</b>. The largest is <b>{sec.index[0]}</b> at "
        f"{sec.iloc[0]:.0%}. No industry has more than {int(MAX_SECTOR)} stocks.", BLUE))
    out.append(("🚀", "Growth and quality",
        f"On average (weighted by money) sales grew <b>{wa('SalesYoY_%'):.0f}%</b> and profits "
        f"<b>{wa('NI_Growth_%'):.0f}%</b> last year, with an ROE of <b>{wa('ROE_%'):.0f}%</b>. "
        "Strong numbers, but past growth does not guarantee future growth.", GREEN))
    exp_share = float(port.loc[port.PE > 40, "Weight"].sum())
    out.append(("🏷️", "Price check",
        f"The average P/E is <b>{wa('PE'):.0f}</b>. About <b>{exp_share:.0%}</b> of the money is in stocks with a P/E "
        "above 40 (priced for high growth). If growth disappoints, these can fall sharply.", AMBER))
    up_share = float(port.loc[port.Above_200DMA, "Weight"].sum())
    out.append(("📈", "Market trend",
        f"<b>{up_share:.0%}</b> of the money is in stocks trading above their 200-day average. "
        + ("Most holdings are in an uptrend." if up_share >= .5 else
           "Most holdings are currently in a weak trend, which is a timing risk."), AMBER if up_share < .5 else GREEN))
    p10 = float(np.percentile(f_real, 10))
    out.append(("🎢", "Risk",
        f"Market sensitivity (beta) is <b>{P_BETA:.2f}</b> ({beta_label(P_BETA).lower()}) and yearly swings are about "
        f"<b>±{SIGMA:.0%}</b>. In a bad case (1 in 10), the portfolio could be worth about <b>{money(p10)}</b> "
        f"after {DUR_TXT}.", RED))
    notes = []
    neg = port[port["NI_Growth_%"] < 0].Company.tolist()
    hib = port[port.Beta >= 1.4].Company.tolist()
    fill = port[~port.Screen_Pass].Company.tolist()
    if neg: notes.append("profits fell last year at " + ", ".join(neg))
    if hib: notes.append("very volatile stocks (beta 1.4+): " + ", ".join(hib))
    if fill: notes.append("narrowly missed the quality rules: " + ", ".join(fill))
    out.append(("⚠️", "Watch-outs", ("; ".join(notes).capitalize() + ".") if notes else "No major red flags found.", RED))
    return out

# ============================================================ HEADER + TABS (pipeline order)
st.markdown(f"""<div class="hero"><h1>📈 Smart Portfolio Builder</h1>
<p>Turning {money(CAPITAL)} into {money(TARGET)} in {DUR_TXT}:
how stocks are chosen, how money is split, and whether the goal is realistic.</p></div>""",
            unsafe_allow_html=True)

tabs = st.tabs(["🏁 Overview", "🔎 Stocks", "📏 Stock quality rules", "🏆 Ranking",
                "💼 Portfolio", "📈 Live tracker", "🎯 Possibility of hitting target", "📝 Summary and insights"])

# ------------------------------------------------------------ 1. OVERVIEW
with tabs[0]:
    c = st.columns(4)
    c[0].markdown(card("Starting money", money(CAPITAL), "invested today", BLUE), unsafe_allow_html=True)
    c[1].markdown(card(f"Goal in {DUR_TXT}", money(TARGET), f"{T_LOW:.2f}x your money", GREEN),
                  unsafe_allow_html=True)
    c[2].markdown(card("Growth needed", f"{REQ_LOW:.0%} / year",
                       "Indian stocks have averaged roughly 12–15%", AMBER), unsafe_allow_html=True)
    c[3].markdown(card("Risk level", beta_label(P_BETA), f"swings about ±{SIGMA:.0%} a year", RED),
                  unsafe_allow_html=True)
    st.markdown(f"""<div class="verdict" style="border-color:{vcol}">
    <div style="font-size:1.2rem;font-weight:700">{vicon} Reaching {money(TARGET)}: {vtxt}
    ({mid_prob:.0%} chance in the realistic case)</div>
    <div style="color:#475569;margin-top:4px">A goal that needs a return well above normal market returns is reached
    only if things go better than average, however carefully the stocks are chosen. See the tab
    "Possibility of hitting target" for details.</div></div>""", unsafe_allow_html=True)

    st.markdown("### How this tool works (follow the tabs left to right)")
    steps = [("1. Overview", "Your money, goal, and the return needed."),
             ("2. Stocks", "The companies we started with and their numbers."),
             ("3. Quality rules", "Filters that remove weak companies, plus factor weights."),
             ("4. Ranking", "Every company scored 0–100; best 5 per size group picked."),
             ("5. Portfolio", "Money split across the 15 stocks."),
             ("6. Live tracker", "How the portfolio is doing at today's prices."),
             ("7. Possibility", "Simulation of whether the goal can be reached."),
             ("8. Summary", "Key insights and the Excel download.")]
    for row in (steps[:4], steps[4:]):
        sc = st.columns(4)
        for col, (t, d) in zip(sc, row):
            col.markdown(f'<div class="step"><b>{t}</b><br>{d}</div>', unsafe_allow_html=True)
        st.write("")

    st.markdown("### Growth path needed to reach the goal")
    mths = np.arange(0, MONTHS + 1)
    fig = go.Figure()
    fig.add_scatter(x=mths, y=CAPITAL * (1 + REQ_LOW) ** (mths / 12) / 1e7,
                    name="Growth needed to hit the goal", line=dict(color=BLUE, width=4))
    fig.update_layout(height=330, xaxis_title="Months from now", yaxis_title="Value (₹ crore)",
                      margin=dict(t=10), legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------ 2. STOCKS
with tabs[1]:
    st.subheader("The companies we started with")
    explain(f"{len(raw)} companies: Large {(raw.Cap_Bucket=='Large').sum()}, Mid {(raw.Cap_Bucket=='Mid').sum()}, "
            f"Small {(raw.Cap_Bucket=='Small').sum()}. Figures are for financial year 2025-26 (consolidated). "
            "See the Glossary in the left panel for definitions.")
    pick = st.radio("Show", ["All", "Large", "Mid", "Small"], horizontal=True)
    d = raw if pick == "All" else raw[raw.Cap_Bucket == pick]
    friendly = d[["Company", "Sector", "Cap_Bucket", "MarketCap_Cr", "SalesYoY_%", "NI_Growth_%", "ROE_%", "ROCE_%",
                  "PE", "PEG", "PBV", "Beta", "StdDev_%", "RSI14"]].rename(columns={
        "Cap_Bucket": "Size", "MarketCap_Cr": "Market value (₹ cr)", "SalesYoY_%": "Sales growth %",
        "NI_Growth_%": "Profit growth %", "ROE_%": "ROE %", "ROCE_%": "ROCE %", "PE": "P/E", "PBV": "P/B",
        "StdDev_%": "Volatility %"})
    st.dataframe(friendly.round(2), use_container_width=True, hide_index=True, height=460)
    st.plotly_chart(px.scatter(raw, x="SalesYoY_%", y="ROE_%", color="Cap_Bucket", size="MarketCap_Cr",
                               hover_name="Company", color_discrete_map=BUCKET,
                               labels={"SalesYoY_%": "Sales growth % (higher = growing faster)",
                                       "ROE_%": "ROE % (higher = more profitable)", "Cap_Bucket": "Size"},
                               title="Growth vs profitability: top-right is the sweet spot"),
                    use_container_width=True)

# ------------------------------------------------------------ 3. QUALITY RULES
with tabs[2]:
    st.subheader("Stock quality rules")
    explain("A company must pass all four rules to be a first-choice stock. Change the limits in the left panel "
            "under Stock quality rules.")
    n0 = len(ranked)
    c4 = int(ranked.Screen_Pass.sum())
    rules = pd.DataFrame({
        "Rule": ["ROE", "ROCE", "Sales growth", "Beta"],
        "Requirement": [f"above {MIN_ROE:.0f}%", f"above {MIN_ROCE:.0f}% (banks and NBFCs skip)",
                        f"above {G_LARGE:.0f}% (Large), {G_MIDSMALL:.0f}% (Mid/Small)", f"below {MAX_BETA}"],
        "Why": ["Earns good profit on shareholders' money", "Earns good profit on all money used",
                "Growing fast enough for the goal", "Not too jumpy versus the market"],
        "Share passing": [ranked.T_ROE.mean(), ranked.T_ROCE.mean(), ranked.T_Growth.mean(), ranked.T_Beta.mean()]})
    st.dataframe(rules, use_container_width=True, hide_index=True, column_config={
        "Share passing": st.column_config.ProgressColumn("Share passing", min_value=0, max_value=1, format="percent")})
    st.markdown(f"<div class='note'><b>{c4} of {n0}</b> companies passed all four rules. If a size group has fewer "
                "than 5 passers, the best of the rest fill the gap and are flagged with ⚠️ in the Ranking tab.</div>",
                unsafe_allow_html=True)

    st.markdown("### What matters when scoring? (factor weights)")
    explain(f"Each factor gets a share of 100%. Current style: <b>{preset}</b>. Change it in the left panel.")
    wt = pd.DataFrame({"Factor": [info[k][0] for k in W], "Measured by": [info[k][1] for k in W],
                       "Weight %": [round(v * 100, 1) for v in W.values()],
                       "Why it matters": [info[k][2] for k in W]})
    a, b = st.columns([3, 2])
    a.dataframe(wt, use_container_width=True, hide_index=True, column_config={
        "Weight %": st.column_config.ProgressColumn("Weight %", min_value=0, max_value=50, format="%.0f%%")})
    b.plotly_chart(px.pie(wt, names="Factor", values="Weight %", hole=.55).update_layout(
        margin=dict(t=10, b=10), height=300), use_container_width=True)

# ------------------------------------------------------------ 4. RANKING
with tabs[3]:
    st.subheader("How the stocks ranked")
    explain("Every company is scored 0–100 against others of its own size. Companies that passed all quality rules "
            "come first, then higher scores. The best 5 per size group are picked, with a limit per industry.")
    contrib = port[["Company", "Cap_Bucket"]].copy()
    for k in W: contrib[info[k][0]] = port[f"S_{k}"] * W[k]
    contrib["Total"] = contrib[[info[k][0] for k in W]].sum(axis=1)
    contrib = contrib.sort_values("Total")
    long = contrib.melt(id_vars=["Company", "Cap_Bucket", "Total"], var_name="Factor", value_name="Points")
    fig = px.bar(long, x="Points", y="Company", color="Factor", orientation="h", height=520,
                 title="Selected stocks: total score and where the points came from")
    fig.update_layout(yaxis=dict(categoryorder="array", categoryarray=contrib.Company))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Why each stock was picked")
    for b in ["Large", "Mid", "Small"]:
        st.markdown(f"<span class='pill' style='background:{BUCKET[b]}'>{b}-cap</span>", unsafe_allow_html=True)
        for _, r in port[port.Cap_Bucket == b].sort_values("Total_Score", ascending=False).iterrows():
            tag = "" if r.Screen_Pass else "  ⚠️"
            with st.expander(f"{r.Company}  ·  {r.Sector}  ·  score {r.Total_Score:.0f}/100{tag}"):
                for p in why_points(r, tests): st.markdown(p)
    with st.expander("See the full ranking of all companies"):
        full = ranked[cols].round(0).rename(columns={"Cap_Bucket": "Size", "Screen_Pass": "Passed all rules",
                                                     "Tests_Passed": "Rules passed (of 4)", "Total_Score": "Total score"})
        st.dataframe(full, use_container_width=True, hide_index=True, column_config={
            "Total score": st.column_config.ProgressColumn("Total score", min_value=0, max_value=100, format="%.0f")})

# ------------------------------------------------------------ 5. PORTFOLIO
with tabs[4]:
    st.subheader("Where the money goes")
    explain(f"Each size group gets a share of the money (Large {BUCKET_ALLOC['Large']:.0%}, Mid "
            f"{BUCKET_ALLOC['Mid']:.0%}, Small {BUCKET_ALLOC['Small']:.0%}; change it in the left panel). Inside a "
            f"group, stronger stocks get more, capped at {MAX_STOCK:.0%} per stock.")
    c = st.columns(4)
    c[0].markdown(card("Invested", money(port.Invested_Rs.sum()), f"in {len(port)} stocks", BLUE), unsafe_allow_html=True)
    c[1].markdown(card("Left as cash", f"₹{cash:,.0f}", "too small to buy another share", AMBER), unsafe_allow_html=True)
    c[2].markdown(card("Industries", f"{port.Sector.nunique()}", "spread across sectors", GREEN), unsafe_allow_html=True)
    c[3].markdown(card("Market sensitivity", f"{P_BETA:.2f}", "1.00 = moves like the market", RED), unsafe_allow_html=True)
    st.write("")
    a, b = st.columns(2)
    fig = px.pie(port, names="Company", values="Weight", hole=.5, color_discrete_sequence=FIN_LONG,
                 title="Share of money by stock")
    fig.update_traces(textposition="inside", textinfo="percent"); a.plotly_chart(fig, use_container_width=True)
    g = port.groupby("Cap_Bucket").Weight.sum().reset_index()
    b.plotly_chart(px.pie(g, names="Cap_Bucket", values="Weight", hole=.5, color="Cap_Bucket",
                          color_discrete_map=BUCKET, title="Share of money by company size"),
                   use_container_width=True)
    sec = port.groupby("Sector").Weight.sum().reset_index().sort_values("Weight")
    st.plotly_chart(px.bar(sec, x="Weight", y="Sector", orientation="h", title="Share of money by industry",
                           color_discrete_sequence=[BLUE]), use_container_width=True)
    t = show.rename(columns={"Cap_Bucket": "Size", "Total_Score": "Score", "Weight": "Share %",
                             "Amount_Rs": "Planned ₹", "Price": "Price ₹", "Shares": "Shares to buy",
                             "Invested_Rs": "Actual ₹"}).round(2)
    st.dataframe(t, use_container_width=True, hide_index=True)

# ------------------------------------------------------------ 6. LIVE TRACKER
with tabs[5]:
    st.subheader("Live tracker: how is the portfolio doing now?")
    explain("Imagine you bought this exact portfolio on the date below, at that day's closing prices. "
            "This compares today's value with what you put in, with the Nifty 50, and with the pace your goal needs. "
            "Prices refresh about every 15 minutes.")
    cA, cB = st.columns([2, 1])
    inv_date = cA.date_input("Investment date", value=pd.Timestamp("2026-10-09").date(),
                             max_value=pd.Timestamp.today().date())
    if cB.button("🔄 Refresh prices now"):
        st.cache_data.clear()
    hist = get_history(tuple(port.Ticker), str(inv_date))
    ok = [t for t in port.Ticker if hist is not None and t in hist.columns and hist[t].notna().any()]
    if hist is None or hist.empty or "^NSEI" not in hist.columns or not ok:
        st.warning("Could not fetch live prices right now (the data source may be busy). Try again in a few minutes.")
    else:
        hist = hist.ffill()
        buy, last = hist.iloc[0], hist.iloc[-1]
        tr = port[port.Ticker.isin(ok)].copy()
        tr["Buy price"] = tr.Ticker.map(buy)
        tr["Price now"] = tr.Ticker.map(last)
        tr["Shares_t"] = (tr.Amount_Rs // tr["Buy price"]).astype(int)
        tr["Invested"] = tr.Shares_t * tr["Buy price"]
        tr["Value now"] = tr.Shares_t * tr["Price now"]
        tr["P&L ₹"] = tr["Value now"] - tr["Invested"]
        tr["Change %"] = (tr["Price now"] / tr["Buy price"] - 1) * 100
        cash_t = CAPITAL - tr.Invested.sum()
        value_now = tr["Value now"].sum() + cash_t
        pl = value_now - CAPITAL
        ret = value_now / CAPITAL - 1
        nifty = float(last["^NSEI"] / buy["^NSEI"] - 1)
        days = max((hist.index[-1] - hist.index[0]).days, 0)
        pace_value = CAPITAL * (1 + REQ_LOW) ** (days / 365)
        c = st.columns(4)
        c[0].markdown(card("Value now", money(value_now), f"started at {money(CAPITAL)}", BLUE), unsafe_allow_html=True)
        c[1].markdown(card("Profit / loss", f"{'+' if pl >= 0 else '-'}₹{abs(pl):,.0f}", f"{ret:+.2%} in {days} days",
                           GREEN if pl >= 0 else RED), unsafe_allow_html=True)
        c[2].markdown(card("vs Nifty 50", f"{(ret - nifty):+.2%}", f"Nifty moved {nifty:+.2%}",
                           GREEN if ret >= nifty else RED), unsafe_allow_html=True)
        c[3].markdown(card("vs goal pace", "Ahead" if value_now >= pace_value else "Behind",
                           f"pace needs {money(pace_value)} by now", GREEN if value_now >= pace_value else AMBER),
                      unsafe_allow_html=True)
        st.write("")
        series = (hist[ok].mul(tr.set_index("Ticker").Shares_t)).sum(axis=1) + cash_t
        bench = CAPITAL * hist["^NSEI"] / hist["^NSEI"].iloc[0]
        goal_line = CAPITAL * (1 + REQ_LOW) ** (((hist.index - hist.index[0]).days) / 365)
        fig = go.Figure()
        fig.add_scatter(x=series.index, y=series / 1e7, name="Your portfolio", line=dict(color=BLUE, width=4))
        fig.add_scatter(x=bench.index, y=bench / 1e7, name="Nifty 50 (same start)", line=dict(color=AMBER, width=3))
        fig.add_scatter(x=hist.index, y=goal_line / 1e7, name="Pace needed for goal",
                        line=dict(color=GREEN, width=3, dash="dash"))
        fig.update_layout(height=400, xaxis_title="Date", yaxis_title="Value (₹ crore)",
                          legend=dict(orientation="h", y=1.12))
        st.plotly_chart(fig, use_container_width=True)
        t = tr[["Company", "Cap_Bucket", "Buy price", "Price now", "Change %", "P&L ₹"]].rename(
            columns={"Cap_Bucket": "Size"}).sort_values("Change %", ascending=False)
        t.insert(0, "", np.where(t["Change %"] >= 0, "▲", "▼"))
        st.dataframe(t.round(2), use_container_width=True, hide_index=True)
        if len(ok) < len(port):
            st.caption("No live price found for: " + ", ".join(port[~port.Ticker.isin(ok)].Company) + ".")
        st.markdown(f"<div class='note'><b>Read this carefully:</b> {days} day(s) of data say almost nothing about "
                    "whether the strategy works. Check back after several months. Prices come from Yahoo Finance "
                    "and can lag or be unavailable. This is a simulated tracker, not real trading.</div>",
                    unsafe_allow_html=True)

# ------------------------------------------------------------ 7. POSSIBILITY
with tabs[6]:
    st.subheader("Can this portfolio reach the goal?")
    explain("We ran 5,000 possible futures for each scenario. Each future randomly moves stock prices up and down "
            "by the amounts seen historically. The share of futures that end above the goal is the chance of success.")
    st.dataframe(res, use_container_width=True, hide_index=True, column_config={
        "Yearly return": st.column_config.NumberColumn(format="percent"),
        "Typical outcome": st.column_config.NumberColumn(format="₹%.0f"),
        "Bad case": st.column_config.NumberColumn("Bad case (1 in 10)", format="₹%.0f"),
        "Good case": st.column_config.NumberColumn("Good case (1 in 10)", format="₹%.0f"),
        "Chance of reaching target": st.column_config.ProgressColumn(
            f"Chance of reaching {money(TARGET)}", min_value=0, max_value=1, format="percent")})
    cc = st.columns(3)
    for col, (nm, (_, m)), accent in zip(cc, SCEN.items(), [AMBER, BLUE, GREEN]):
        pr = float(res.loc[res.Scenario == nm, "Chance of reaching target"].iloc[0])
        med = float(res.loc[res.Scenario == nm, "Typical outcome"].iloc[0])
        col.markdown(card(nm, f"{pr:.0%} chance", f"typical result {money(med)}", accent), unsafe_allow_html=True)
    st.write("")
    pick = st.radio("Show the range of outcomes for:", list(SCEN), index=1, horizontal=True)
    p = simulate(SCEN[pick][1], SIGMA, CAPITAL, YEARS) / 1e7
    q = {k: np.percentile(p, k, axis=0) for k in (10, 25, 50, 75, 90)}
    mo = np.arange(1, p.shape[1] + 1)
    fig = go.Figure()
    fig.add_scatter(x=mo, y=q[90], line=dict(width=0), showlegend=False)
    fig.add_scatter(x=mo, y=q[10], fill="tonexty", line=dict(width=0), name="Likely range (80% of futures)",
                    fillcolor="rgba(11,95,255,.14)")
    fig.add_scatter(x=mo, y=q[75], line=dict(width=0), showlegend=False)
    fig.add_scatter(x=mo, y=q[25], fill="tonexty", line=dict(width=0), name="Middle half of futures",
                    fillcolor="rgba(11,95,255,.30)")
    fig.add_scatter(x=mo, y=q[50], name="Typical path", line=dict(color=BLUE, width=4))
    fig.add_hline(y=TARGET / 1e7, line_dash="dash", line_color=GREEN, annotation_text="Your goal")
    fig.update_layout(height=430, xaxis_title="Months from now", yaxis_title="Portfolio value (₹ crore)",
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)
    fig = px.histogram(x=p[:, -1], nbins=60, color_discrete_sequence=[GREEN],
                       labels={"x": f"Value after {DUR_TXT} (₹ crore)"},
                       title=f"Where we could end up after {DUR_TXT}")
    fig.add_vline(x=TARGET / 1e7, line_dash="dash", line_color=RED)
    st.plotly_chart(fig, use_container_width=True)
    best = res["Typical outcome"].max()
    st.markdown(f"<div class='note'><b>In plain words:</b> the best typical result across scenarios is "
                f"{money(best)}, against a goal of {money(TARGET)}. {cov_note} "
                "The simulation ignores taxes, trading costs and rebalancing, and past performance does not "
                "guarantee future results.</div>", unsafe_allow_html=True)

# ------------------------------------------------------------ 8. SUMMARY AND INSIGHTS
with tabs[7]:
    st.subheader("Summary and key insights")
    st.markdown(f"""<div class="verdict" style="border-color:{vcol}">
    <div style="font-size:1.15rem;font-weight:700">{vicon} Bottom line: reaching {money(TARGET)} in
    {DUR_TXT} is <u>{vtxt.lower()}</u> ({mid_prob:.0%} chance, realistic case).</div>
    <div style="color:#475569;margin-top:4px">From {len(raw)} companies, {int(ranked.Screen_Pass.sum())} passed all
    quality rules. We picked {len(port)} stocks across {port.Sector.nunique()} industries, split
    {BUCKET_ALLOC['Large']:.0%} large, {BUCKET_ALLOC['Mid']:.0%} mid and {BUCKET_ALLOC['Small']:.0%} small-cap.
    Expected return in the realistic case is {SCEN['Realistic'][1]:.0%} a year against the {REQ_LOW:.0%} needed.</div>
    </div>""", unsafe_allow_html=True)
    st.write("")
    ins = build_insights()
    for i in range(0, len(ins), 2):
        cs = st.columns(2)
        for c_, (ic, t, tx, ac) in zip(cs, ins[i:i + 2]):
            c_.markdown(f'<div class="card" style="border-left-color:{ac}"><div class="lbl">{ic} {t}</div>'
                        f'<div style="margin-top:6px">{tx}</div></div>', unsafe_allow_html=True)
        st.write("")

    st.markdown("### Download everything")
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
        pd.DataFrame({"Insight": [t for _, t, _, _ in ins],
                      "Detail": [tx.replace("<b>", "").replace("</b>", "") for _, _, tx, _ in ins]}
                     ).to_excel(xw, sheet_name="Insights", index=False)
    st.download_button("⬇️ Download Excel report", buf.getvalue(), "Portfolio_Report.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
    st.caption("Educational tool. Not investment advice. Past performance does not guarantee future results.")
