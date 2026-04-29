import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import calendar
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

from data import (
    get_income, add_income, get_total_income,
    get_expenses, add_expense, get_total_expenses, get_category_totals, get_daily_totals,
    get_recurring, add_recurring, toggle_recurring, get_recurring_monthly_total,
    get_events, add_event, get_all_calendar_events,
    get_balances, add_balance_snapshot, get_latest_balance,
    get_usd_rate, set_usd_rate, fetch_live_usd_rate, get_usd_fetch_date, get_settings,
    get_manual_limit, set_manual_limit,
    reset_profile_data, is_sample_data, ensure_profile_data,
    get_profiles, create_profile, delete_profile, rename_profile,
    get_profile, set_active_profile,
    EXPENSE_CATEGORIES, INCOME_SOURCES, CAT_COLORS, SL_HOLIDAYS
)
from intelligence import (
    compute_safe_spending_limit, predict_monthly_spending,
    evaluate_goal, calculate_risk_score, detect_spending_anomalies,
    analyze_event_spending_impact, calculate_runway_days,
    build_financial_summary, get_net_this_month
)
from agent import chat as agent_chat, analyze_new_entry, generate_weekly_insight

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="FinAgent", page_icon="💰", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,300&family=DM+Mono:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
.stApp{background:#0d0f14;}
div[data-testid="stSidebar"]{background:#0a0c10 !important;border-right:1px solid #1e2130;}
.block-container{padding-top:1.2rem;}
.metric-card{background:#13151f;border:1px solid #1e2130;border-radius:14px;padding:16px 20px;margin-bottom:10px;}
.metric-label{font-size:11px;color:#5a6070;letter-spacing:.08em;text-transform:uppercase;margin-bottom:6px;}
.metric-value{font-size:22px;font-weight:600;color:#e8eaf0;font-family:'DM Mono',monospace;}
.metric-sub{font-size:12px;color:#5a6070;margin-top:3px;}
.metric-value.pos{color:#22c55e;} .metric-value.warn{color:#f59e0b;} .metric-value.neg{color:#ef4444;}
.card{background:#13151f;border:1px solid #1e2130;border-radius:14px;padding:16px 20px;margin-bottom:12px;}
.section-label{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:#3d4255;font-weight:600;margin-bottom:10px;}
.ai-bubble{background:#0f1520;border:1px solid #1e3050;border-radius:12px;padding:12px 16px;font-size:13px;line-height:1.7;color:#b0bcd0;margin-top:8px;}
.alert-danger{background:rgba(239,68,68,.08);border-left:3px solid #ef4444;border-radius:8px;padding:10px 14px;margin-bottom:8px;font-size:13px;color:#e8eaf0;}
.alert-warn{background:rgba(245,158,11,.08);border-left:3px solid #f59e0b;border-radius:8px;padding:10px 14px;margin-bottom:8px;font-size:13px;color:#e8eaf0;}
.alert-info{background:rgba(59,130,246,.08);border-left:3px solid #3b82f6;border-radius:8px;padding:10px 14px;margin-bottom:8px;font-size:13px;color:#e8eaf0;}
.alert-green{background:rgba(34,197,94,.08);border-left:3px solid #22c55e;border-radius:8px;padding:10px 14px;margin-bottom:8px;font-size:13px;color:#e8eaf0;}
.badge{display:inline-block;padding:2px 9px;border-radius:99px;font-size:11px;font-weight:500;}
.badge-food{background:#fef3c7;color:#92400e;} .badge-clothes{background:#fce7f3;color:#831843;}
.badge-subscriptions{background:#ede9fe;color:#4c1d95;} .badge-transport{background:#dbeafe;color:#1e3a8a;}
.badge-entertainment{background:#ffedd5;color:#7c2d12;} .badge-health{background:#dcfce7;color:#14532d;}
.badge-other{background:#f1f5f9;color:#334155;}
.risk-bar{height:10px;background:#1e2130;border-radius:99px;overflow:hidden;margin-top:6px;}
.cal-day{background:#13151f;border:1px solid #1e2130;border-radius:8px;padding:6px 8px;min-height:58px;font-size:12px;}
.cal-day.holiday{border-color:#f59e0b44;background:#1a1710;}
.cal-day.event{border-color:#3b82f644;background:#0f1520;}
.cal-day.today{border-color:#6366f1;background:#111228;}
.cal-day.empty{background:transparent;border-color:transparent;}
.cal-day-num{font-size:13px;font-weight:500;color:#9ca3b0;margin-bottom:2px;}
.cal-day-num.today-num{color:#818cf8;font-weight:700;}
.cal-tag{font-size:10px;line-height:1.3;border-radius:4px;padding:1px 5px;margin-top:2px;display:block;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;}
.cal-tag.holiday{background:#f59e0b22;color:#f59e0b;}
.cal-tag.event,.cal-tag.outing,.cal-tag.personal{background:#3b82f622;color:#60a5fa;}
.cal-tag.birthday{background:#ec489922;color:#f472b6;}
.sample-banner{background:rgba(245,158,11,.12);border:1px solid #f59e0b44;border-radius:10px;padding:10px 16px;font-size:13px;color:#f59e0b;margin-bottom:16px;}
</style>
""", unsafe_allow_html=True)

# ── Session state init ─────────────────────────────────────────────────────────
for k, v in [("client", None), ("chat_history", []), ("ai_insight", ""),
             ("usd_fetched", False), ("active_profile_id", "")]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── API Key from .env ──────────────────────────────────────────────────────────
_env_key = os.getenv("GROQ_API_KEY", "")
if _env_key and _env_key != "your_api_key_here" and not st.session_state.client:
    st.session_state.client = Groq(api_key=_env_key)

# ── Fetch live USD rate once per session (data.py deduplicates by date on disk) ─
if not st.session_state.usd_fetched:
    rate, _ = fetch_live_usd_rate()
    st.session_state.live_usd_rate = rate
    st.session_state.usd_fetched   = True

# ── Greeting helper ────────────────────────────────────────────────────────────
def get_greeting(name: str = "") -> str:
    h = datetime.now().hour
    if h < 12:   time_str = "Good morning"
    elif h < 17: time_str = "Good afternoon"
    elif h < 21: time_str = "Good evening"
    else:        time_str = "Good night"
    return f"{time_str}, {name}!" if name else f"{time_str}!"

# ── Profile emoji options ──────────────────────────────────────────────────────
PROFILE_EMOJIS = ["👤", "💼", "🏠", "🎓", "🚀", "🎯", "💡", "🌟", "🎨", "🏋️"]

# ══════════════════════════════════════════════════════════════════════════════
# PROFILE SELECTION SCREEN
# Shown when no profile is active in session (fresh run or switched out).
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.active_profile_id:
    profiles = get_profiles()

    st.markdown("""
    <div style='text-align:center;padding:40px 0 24px'>
      <div style='font-size:52px;margin-bottom:12px'>💰</div>
      <h1 style='color:#e8eaf0;font-size:30px;margin-bottom:6px'>FinAgent</h1>
      <p style='color:#5a6070;font-size:15px'>Select a profile or create a new one to get started.</p>
    </div>
    """, unsafe_allow_html=True)

    col_main = st.columns([1, 3, 1])[1]
    with col_main:
        if profiles:
            st.markdown("<div style='margin-bottom:12px;font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:#3d4255;font-weight:600'>Your profiles</div>", unsafe_allow_html=True)
            for p in profiles:
                c1, c2 = st.columns([5, 1])
                with c1:
                    if st.button(f"{p['emoji']}  {p['name']}", key=f"sel_{p['id']}", use_container_width=True):
                        st.session_state.active_profile_id = p["id"]
                        st.session_state.chat_history = []
                        set_active_profile(p["id"])
                        ensure_profile_data()
                        st.rerun()
                with c2:
                    if st.button("🗑", key=f"del_{p['id']}", help="Delete this profile"):
                        st.session_state[f"confirm_del_{p['id']}"] = True
                        st.rerun()
                if st.session_state.get(f"confirm_del_{p['id']}"):
                    st.warning(f"Delete **{p['name']}**? This cannot be undone.")
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        if st.button("Yes, delete", key=f"yes_del_{p['id']}", type="primary"):
                            delete_profile(p["id"])
                            st.session_state.pop(f"confirm_del_{p['id']}", None)
                            st.rerun()
                    with dc2:
                        if st.button("Cancel", key=f"no_del_{p['id']}"):
                            st.session_state.pop(f"confirm_del_{p['id']}", None)
                            st.rerun()

            st.markdown("<div style='margin:20px 0 12px;border-top:1px solid #1e2130'></div>", unsafe_allow_html=True)

        # ── Create new profile form ────────────────────────────────────────────
        st.markdown("<div style='font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:#3d4255;font-weight:600;margin-bottom:10px'>Create new profile</div>", unsafe_allow_html=True)
        new_name  = st.text_input("Profile name", placeholder="e.g. Personal, Work, Studies…", label_visibility="collapsed", key="new_profile_name")
        new_emoji = st.selectbox("Pick an icon", PROFILE_EMOJIS, label_visibility="collapsed", key="new_profile_emoji")
        if st.button("Create profile →", type="primary", use_container_width=True):
            if new_name.strip():
                p = create_profile(new_name.strip(), new_emoji)
                st.session_state.active_profile_id = p["id"]
                st.session_state.chat_history = []
                set_active_profile(p["id"])
                st.rerun()
            else:
                st.warning("Enter a name for the profile.")
    st.stop()

# ── Active profile is set — wire it up ────────────────────────────────────────
set_active_profile(st.session_state.active_profile_id)
ensure_profile_data()
active_profile = get_profile(st.session_state.active_profile_id)
user_name      = active_profile.get("name", "")

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"## 💰 FinAgent")
    st.markdown(f"<span style='color:#5a6070;font-size:13px'>{get_greeting(user_name)}</span>", unsafe_allow_html=True)
    st.markdown("---")

    if not st.session_state.client:
        api_key = st.text_input("GROQ API Key", type="password", help="Or add to .env file")
        if api_key:
            st.session_state.client = Groq(api_key=api_key)
            st.rerun()
    else:
        st.success("AI connected ✓")

    usd_rate = st.session_state.get("live_usd_rate", get_usd_rate())
    st.markdown(f"<span style='font-size:14px;color:#5a6070'>💱 USD → LKR: <strong style='color:#e8eaf0'>{usd_rate}</strong> <span style='color:#22c55e;font-size:15px'>(live)</span></span>", unsafe_allow_html=True)
    st.markdown("---")

    income = get_total_income()
    spent  = get_total_expenses() + get_recurring_monthly_total()
    net    = get_net_this_month()
    goal   = evaluate_goal()
    pct    = goal["usage_pct"] / 100
    risk   = calculate_risk_score()

    st.markdown("**This month**")
    st.progress(min(pct, 1.0))
    color = "#ef4444" if pct > 0.9 else "#f59e0b" if pct > 0.7 else "#22c55e"
    st.markdown(f"""
    <div style='font-size:13px;'>
      <div style='display:flex;justify-content:space-between;'><span style='color:#5a6070'>Income</span><span style='color:#e8eaf0;font-family:DM Mono'>LKR {income:,.0f}</span></div>
      <div style='display:flex;justify-content:space-between;'><span style='color:#5a6070'>Spent</span><span style='color:{color};font-family:DM Mono'>LKR {spent:,.0f}</span></div>
      <div style='display:flex;justify-content:space-between;'><span style='color:#5a6070'>Net</span><span style='color:{"#22c55e" if net>=0 else "#ef4444"};font-family:DM Mono'>LKR {net:,.0f}</span></div>
      <div style='display:flex;justify-content:space-between;margin-top:4px;'><span style='color:#5a6070'>Risk</span><span style='color:{risk["color"]};font-weight:600'>{risk["score"]}/100 {risk["label"]}</span></div>
    </div>""", unsafe_allow_html=True)

    st.markdown("---")
    bal    = get_latest_balance()
    runway = calculate_runway_days()
    st.markdown(f"""<div style='font-size:13px;'>
      <div style='display:flex;justify-content:space-between;'><span style='color:#5a6070'>Bank</span><span style='color:#e8eaf0;font-family:DM Mono'>LKR {bal.get('bank',0):,.0f}</span></div>
      <div style='display:flex;justify-content:space-between;'><span style='color:#5a6070'>Cash</span><span style='color:#e8eaf0;font-family:DM Mono'>LKR {bal.get('cash',0):,.0f}</span></div>
      <div style='display:flex;justify-content:space-between;margin-top:4px;'><span style='color:#5a6070'>Runway</span><span style='color:{"#ef4444" if runway["runway_days"]<14 else "#f59e0b" if runway["runway_days"]<30 else "#22c55e"};font-family:DM Mono'>{runway["runway_days"]} days</span></div>
    </div>""", unsafe_allow_html=True)

    st.markdown("---")
    if st.button("⚙️ Change name"):
        st.session_state.user_name = ""
        st.session_state.chat_history = []
        st.rerun()

    page = st.radio("", ["📊 Overview", "💰 Income", "💳 Expenses", "🔁 Recurring",
                         "🗓 Calendar", "🏦 Balances", "📋 Summary Table", "🤖 AI Chat"],
                    label_visibility="collapsed")

# ══════════════════════════════════════════════════════════════════════════════
# OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
if page == "📊 Overview":
    st.markdown(f"<h2 style='color:#e8eaf0;margin-bottom:2px'>{get_greeting(user_name)}</h2>", unsafe_allow_html=True)
    st.caption(f"Here's your financial snapshot for {date.today().strftime('%B %Y')}")

    # Sample data banner — always shown after name entry until Reset is clicked
    if is_sample_data():
        st.markdown("""<div class="sample-banner">
        📌 You're viewing <strong>sample data</strong> to help you get started.
        Click <strong>Reset & Start Fresh</strong> below to clear it and add your own entries.
        </div>""", unsafe_allow_html=True)
        if st.button("🗑️ Reset & Start Fresh", type="secondary"):
            # Clear data only — user_name stays, no name screen redirect
            reset_all_data()
            st.session_state.chat_history = []
            st.session_state.ai_insight = ""
            st.success("Sample data cleared! Start adding your own entries below.")
            st.rerun()
        st.markdown("---")

    income = get_total_income()
    spent  = get_total_expenses() + get_recurring_monthly_total()
    net    = get_net_this_month()
    goal   = evaluate_goal()
    pred   = predict_monthly_spending()
    risk   = calculate_risk_score()
    runway = calculate_runway_days()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Income this month</div><div class="metric-value pos">LKR {income:,.0f}</div><div class="metric-sub">variable — not fixed</div></div>', unsafe_allow_html=True)
    with c2:
        cls = "neg" if goal["status"] == "exceeded" else "warn" if goal["status"] in ["warning", "caution"] else ""
        st.markdown(f'<div class="metric-card"><div class="metric-label">Total spent</div><div class="metric-value {cls}">LKR {spent:,.0f}</div><div class="metric-sub">{goal["usage_pct"]}% of safe limit</div></div>', unsafe_allow_html=True)
    with c3:
        cls = "neg" if net < 0 else "pos"
        st.markdown(f'<div class="metric-card"><div class="metric-label">Net remaining</div><div class="metric-value {cls}">LKR {net:,.0f}</div><div class="metric-sub">{"⚠ Deficit" if net < 0 else "Available"}</div></div>', unsafe_allow_html=True)
    with c4:
        cls = "neg" if pred["adjusted_prediction"] > goal["safe_limit"] else "warn" if pred["adjusted_prediction"] > goal["safe_limit"] * 0.85 else "pos"
        st.markdown(f'<div class="metric-card"><div class="metric-label">Projected expenses</div><div class="metric-value {cls}">LKR {pred["adjusted_prediction"]:,.0f}</div><div class="metric-sub">incl. {len(pred["upcoming_events"])} upcoming events</div></div>', unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Safe spending limit</div><div class="metric-value">LKR {goal["safe_limit"]:,.0f}</div><div class="metric-sub">based on {goal["method"]} income</div></div>', unsafe_allow_html=True)
    with c6:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Daily budget left</div><div class="metric-value {"warn" if goal["daily_budget_remaining"] < 500 else ""}">LKR {goal["daily_budget_remaining"]:,.0f}</div><div class="metric-sub">per day for {30 - date.today().day} days</div></div>', unsafe_allow_html=True)
    with c7:
        r_color = "neg" if runway["runway_days"] < 14 else "warn" if runway["runway_days"] < 30 else "pos"
        st.markdown(f'<div class="metric-card"><div class="metric-label">Financial runway</div><div class="metric-value {r_color}">{runway["runway_days"]} days</div><div class="metric-sub">at LKR {runway["avg_daily_spending"]:,.0f}/day avg</div></div>', unsafe_allow_html=True)
    with c8:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Risk score</div><div class="metric-value" style="color:{risk["color"]}">{risk["score"]}/100</div><div class="metric-sub">{risk["label"]}</div></div>', unsafe_allow_html=True)

    st.markdown("")

    col_l, col_r = st.columns([3, 2])
    with col_l:
        st.markdown('<div class="section-label">Spending by category</div>', unsafe_allow_html=True)
        cat_totals = get_category_totals()
        df = pd.DataFrame({"Category": list(cat_totals.keys()), "Amount": list(cat_totals.values())})
        df = df[df["Amount"] > 0]
        if not df.empty:
            fig = px.pie(df, names="Category", values="Amount", hole=0.55,
                         color="Category",
                         color_discrete_map={c: CAT_COLORS[i] for i, c in enumerate(EXPENSE_CATEGORIES)})
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font=dict(color="#9ca3b0", size=12), margin=dict(t=10, b=10, l=10, r=10),
                              legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)))
            fig.update_traces(textfont_color="#fff", textinfo="percent")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No expenses recorded yet.")

    with col_r:
        st.markdown('<div class="section-label">Income vs Expenses</div>', unsafe_allow_html=True)
        fig2 = go.Figure(go.Bar(
            x=["Income", "Spent", "Safe Limit"],
            y=[income, spent, goal["safe_limit"]],
            marker_color=["#22c55e", "#ef4444" if goal["status"] == "exceeded" else "#f59e0b", "#6366f1"],
            text=[f"LKR {v:,.0f}" for v in [income, spent, goal["safe_limit"]]],
            textposition="outside", textfont=dict(color="#9ca3b0", size=11),
        ))
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           font=dict(color="#9ca3b0"), margin=dict(t=20, b=10, l=10, r=10),
                           height=250, xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#1a1d2a"))
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown('<div class="section-label">Daily spending — last 7 days</div>', unsafe_allow_html=True)
    daily = get_daily_totals(7)
    fig3 = go.Figure(go.Bar(x=daily["dates"], y=daily["amounts"], marker_color="#6366f1",
                            text=[f"LKR {v:,.0f}" for v in daily["amounts"]],
                            textposition="outside", textfont=dict(color="#9ca3b0", size=11)))
    fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                       font=dict(color="#9ca3b0"), margin=dict(t=20, b=10, l=10, r=10), height=190,
                       xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#1a1d2a"))
    st.plotly_chart(fig3, use_container_width=True)

    st.markdown('<div class="section-label">Alerts & Insights</div>', unsafe_allow_html=True)
    alerts = []
    if goal["status"] == "exceeded":
        alerts.append(("danger", f"You've exceeded your safe spending limit by LKR {goal['overshoot']:,.0f}. Reduce spending immediately."))
    elif goal["status"] == "warning":
        alerts.append(("warn", f"You've used {goal['usage_pct']}% of your safe spending limit (LKR {goal['safe_limit']:,.0f}). Only LKR {goal['safe_limit'] - goal['total_spent']:,.0f} remains."))
    if net < 0:
        alerts.append(("danger", f"Your expenses exceed your income by LKR {abs(net):,.0f} this month."))
    if runway["runway_days"] < 14:
        alerts.append(("warn", f"At your current spending rate, your funds will last only {runway['runway_days']} more days."))
    anomalies = detect_spending_anomalies()
    if anomalies:
        alerts.append(("warn", f"{len(anomalies)} unusual transaction(s) detected. Largest: {anomalies[0]['note']} — LKR {anomalies[0]['amount']:,.0f} ({anomalies[0]['times_avg']}x your average)."))
    correlations = analyze_event_spending_impact()
    for c in correlations[:2]:
        alerts.append(("info", f"Spending of LKR {c['amount']:,.0f} on {c['spend_date']} appears linked to {c['event']}."))
    upcoming_ev = [(d, e) for d, e in get_all_calendar_events().items()
                   if date.today() < datetime.strptime(d, "%Y-%m-%d").date() <= date.today() + timedelta(days=7)]
    for d, e in upcoming_ev:
        alerts.append(("info", f"Upcoming: {e['name']} on {d}. Budget ahead for any related spending."))
    if not alerts:
        alerts.append(("green", "All good! Your finances look healthy this month."))
    for atype, msg in alerts:
        st.markdown(f'<div class="alert-{atype}">{msg}</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="section-label" style="margin-top:16px">Goal: Stay within safe spending limit (LKR {goal["safe_limit"]:,.0f})</div>', unsafe_allow_html=True)
    bar_pct   = min(goal["usage_pct"], 100)
    bar_color = "#ef4444" if bar_pct >= 100 else "#f59e0b" if bar_pct >= 80 else "#22c55e"
    st.markdown(f"""<div class="risk-bar" style="height:12px;">
      <div style="height:100%;width:{bar_pct}%;background:{bar_color};border-radius:99px;transition:width .4s;"></div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:12px;color:#5a6070;margin-top:4px;">
      <span>LKR {goal['total_spent']:,.0f} spent</span><span>{bar_pct:.0f}%</span><span>LKR {goal['safe_limit']:,.0f} limit</span>
    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# INCOME
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💰 Income":
    st.markdown("## Income")
    st.caption("Track all money coming in — salary, freelance, gifts, allowances.")

    with st.expander("➕ Add income entry", expanded=True):
        c1, c2, c3, c4 = st.columns([2, 2, 3, 1])
        with c1: amt    = st.number_input("Amount (LKR)", min_value=0.0, step=100.0, key="inc_amt")
        with c2: source = st.selectbox("Source", INCOME_SOURCES, key="inc_src")
        with c3: note   = st.text_input("Note", placeholder="e.g. April allowance", key="inc_note")
        with c4:
            st.markdown("<br>", unsafe_allow_html=True)
            add_btn = st.button("Add ✓", type="primary", key="inc_add")
        inc_date = st.date_input("Date", value=date.today(), key="inc_date")
        if add_btn:
            if amt > 0:
                entry = {"amount": float(amt), "source": source, "note": note, "date": str(inc_date)}
                add_income(entry)
                if st.session_state.client:
                    st.session_state.ai_insight = analyze_new_entry(st.session_state.client, "income", entry, user_name)
                st.success(f"Added LKR {amt:,.0f} from {source}"); st.rerun()
            else:
                st.warning("Enter an amount.")

    if st.session_state.ai_insight:
        st.markdown(f'<div class="ai-bubble">💡 {st.session_state.ai_insight}</div>', unsafe_allow_html=True)
        st.session_state.ai_insight = ""

    icons   = {"salary": "💼", "freelance": "💻", "gift": "🎁", "allowance": "🏠", "business": "🏪", "other": "💵"}
    incomes = sorted(get_income(), key=lambda x: x["date"], reverse=True)
    st.markdown(f'<div class="section-label">{len(incomes)} income entries · Total: LKR {get_total_income():,.0f}</div>', unsafe_allow_html=True)
    for e in incomes:
        c1, c2, c3 = st.columns([0.5, 5, 2])
        with c1: st.markdown(f"<span style='font-size:20px'>{icons.get(e['source'], '💵')}</span>", unsafe_allow_html=True)
        with c2: st.markdown(f"**{e['note'] or e['source'].title()}**  \n<span style='font-size:12px;color:#5a6070'>{e['date']} · {e['source']}</span>", unsafe_allow_html=True)
        with c3: st.markdown(f"<span style='color:#22c55e;font-family:DM Mono'>+LKR {e['amount']:,.0f}</span>", unsafe_allow_html=True)
        st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# EXPENSES
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💳 Expenses":
    st.markdown("## Expenses")
    st.caption("Day-to-day spending — groceries, transport, eating out, etc.")

    with st.expander("➕ Add expense", expanded=True):
        c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
        with c1: exp_amt  = st.number_input("Amount (LKR)", min_value=0.0, step=50.0, key="exp_amt")
        with c2: exp_cat  = st.selectbox("Category", EXPENSE_CATEGORIES, key="exp_cat")
        with c3: exp_note = st.text_input("Description", placeholder="e.g. Groceries", key="exp_note")
        with c4:
            st.markdown("<br>", unsafe_allow_html=True)
            exp_add = st.button("Add ✓", type="primary", key="exp_add")
        c5, c6 = st.columns([2, 3])
        with c5: exp_date = st.date_input("Date", value=date.today(), key="exp_date")
        with c6: exp_spec = st.text_input("Specify (optional)", placeholder="e.g. KFC, Keells, Uber", key="exp_spec")
        if exp_add:
            if exp_amt > 0 and exp_note:
                entry = {"amount": float(exp_amt), "cat": exp_cat, "note": exp_note, "spec": exp_spec, "date": str(exp_date)}
                add_expense(entry)
                if st.session_state.client:
                    st.session_state.ai_insight = analyze_new_entry(st.session_state.client, "expense", entry, user_name)
                st.success(f"Added: {exp_note} — LKR {exp_amt:,.0f}"); st.rerun()
            else:
                st.warning("Fill in amount and description.")

    if st.session_state.ai_insight:
        st.markdown(f'<div class="ai-bubble">💡 {st.session_state.ai_insight}</div>', unsafe_allow_html=True)
        st.session_state.ai_insight = ""

    icons       = {"food": "🍜", "clothes": "👕", "subscriptions": "📱", "transport": "🚌", "entertainment": "🎬", "health": "💊", "other": "📦"}
    exps        = sorted(get_expenses(), key=lambda x: x["date"], reverse=True)
    anomaly_ids = {a["id"] for a in detect_spending_anomalies()}
    st.markdown(f'<div class="section-label">{len(exps)} expenses · Total: LKR {get_total_expenses():,.0f}</div>', unsafe_allow_html=True)
    for e in exps:
        c1, c2, c3 = st.columns([0.5, 5, 2])
        with c1: st.markdown(f"<span style='font-size:20px'>{icons.get(e['cat'], '📦')}</span>", unsafe_allow_html=True)
        with c2:
            spec_str = f" · <em style='color:#3d4255'>{e['spec']}</em>" if e.get("spec") else ""
            anom_str = " <span style='color:#f59e0b;font-size:11px'>⚠ unusual</span>" if e["id"] in anomaly_ids else ""
            st.markdown(f"**{e['note']}**{spec_str}{anom_str}  \n<span style='font-size:12px;color:#5a6070'>{e['date']}</span> <span class='badge badge-{e['cat']}'>{e['cat']}</span>", unsafe_allow_html=True)
        with c3: st.markdown(f"<span style='color:#ef4444;font-family:DM Mono'>−LKR {e['amount']:,.0f}</span>", unsafe_allow_html=True)
        st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# RECURRING
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔁 Recurring":
    usd_rate = st.session_state.get("live_usd_rate", get_usd_rate())
    st.markdown("## Recurring Expenses")
    st.caption(f"Subscriptions and fixed monthly costs. Live rate: 1 USD = LKR {usd_rate}")

    with st.expander("➕ Add recurring expense", expanded=False):
        c1, c2, c3 = st.columns([3, 2, 2])
        with c1: r_name = st.text_input("Name", placeholder="e.g. Netflix", key="r_name")
        with c2: r_curr = st.selectbox("Currency", ["USD", "LKR"], key="r_curr")
        with c3: r_amt  = st.number_input("Amount", min_value=0.0, step=0.5, key="r_amt")
        c4, c5, c6 = st.columns([2, 2, 1])
        with c4: r_cat = st.selectbox("Category", EXPENSE_CATEGORIES, index=2, key="r_cat")
        with c5: r_day = st.number_input("Billing day of month", 1, 28, 1, key="r_day")
        with c6:
            st.markdown("<br>", unsafe_allow_html=True)
            r_add = st.button("Add ✓", type="primary", key="r_add")
        if r_add:
            if r_name and r_amt > 0:
                entry = {"name": r_name, "currency": r_curr,
                         "amount_usd": float(r_amt) if r_curr == "USD" else None,
                         "amount_lkr": float(r_amt) if r_curr == "LKR" else None,
                         "cat": r_cat, "active": True, "day_of_month": int(r_day)}
                add_recurring(entry)
                if st.session_state.client:
                    st.session_state.ai_insight = analyze_new_entry(st.session_state.client, "recurring", entry, user_name)
                st.success(f"Added: {r_name}"); st.rerun()

    if st.session_state.ai_insight:
        st.markdown(f'<div class="ai-bubble">💡 {st.session_state.ai_insight}</div>', unsafe_allow_html=True)
        st.session_state.ai_insight = ""

    recurring = get_recurring()
    active    = [r for r in recurring if r["active"]]
    inactive  = [r for r in recurring if not r["active"]]
    total     = get_recurring_monthly_total()

    st.markdown(f'<div class="section-label">Active — LKR {total:,.0f}/month</div>', unsafe_allow_html=True)
    for r in active:
        lkr = r["amount_usd"] * usd_rate if r["currency"] == "USD" else r["amount_lkr"]
        c1, c2, c3, c4 = st.columns([3, 3, 2, 1])
        with c1: st.markdown(f"**{r['name']}** <span class='badge badge-{r['cat']}'>{r['cat']}</span>", unsafe_allow_html=True)
        with c2:
            if r["currency"] == "USD":
                st.markdown(f"<span style='color:#9ca3b0;font-family:DM Mono'>${r['amount_usd']} → LKR {lkr:,.0f}</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"<span style='color:#9ca3b0;font-family:DM Mono'>LKR {lkr:,.0f}</span>", unsafe_allow_html=True)
        with c3: st.markdown(f"<span style='color:#5a6070;font-size:12px'>day {r['day_of_month']}</span>", unsafe_allow_html=True)
        with c4:
            if st.button("Pause", key=f"p_{r['id']}"): toggle_recurring(r["id"], False); st.rerun()
        st.divider()

    if inactive:
        st.markdown('<div class="section-label">Paused</div>', unsafe_allow_html=True)
        for r in inactive:
            lkr = r["amount_usd"] * usd_rate if r["currency"] == "USD" else r["amount_lkr"]
            c1, c2, c3 = st.columns([4, 3, 1])
            with c1: st.markdown(f"<span style='color:#3d4255'>~~{r['name']}~~</span>", unsafe_allow_html=True)
            with c2: st.markdown(f"<span style='color:#3d4255;font-family:DM Mono'>LKR {lkr:,.0f}/mo</span>", unsafe_allow_html=True)
            with c3:
                if st.button("Resume", key=f"r_{r['id']}"): toggle_recurring(r["id"], True); st.rerun()
            st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# CALENDAR
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🗓 Calendar":
    st.markdown("## Calendar")

    if "cal_month" not in st.session_state: st.session_state.cal_month = date.today().month
    if "cal_year"  not in st.session_state: st.session_state.cal_year  = date.today().year

    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("← Prev"):
            st.session_state.cal_month -= 1
            if st.session_state.cal_month == 0:
                st.session_state.cal_month = 12
                st.session_state.cal_year -= 1
            st.rerun()
    with col2:
        st.markdown(f"<h3 style='text-align:center;color:#e8eaf0;margin:0'>{date(st.session_state.cal_year, st.session_state.cal_month, 1).strftime('%B %Y')}</h3>", unsafe_allow_html=True)
    with col3:
        if st.button("Next →"):
            st.session_state.cal_month += 1
            if st.session_state.cal_month == 13:
                st.session_state.cal_month = 1
                st.session_state.cal_year += 1
            st.rerun()

    all_events = get_all_calendar_events()
    m, y       = st.session_state.cal_month, st.session_state.cal_year
    first_day, num_days = calendar.monthrange(y, m)
    today = date.today()

    cols = st.columns(7)
    for i, h in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        cols[i].markdown(f"<div style='text-align:center;font-size:11px;color:#3d4255;font-weight:600;padding:4px 0;letter-spacing:.06em'>{h}</div>", unsafe_allow_html=True)

    cells = [""] * first_day + list(range(1, num_days + 1))
    while len(cells) % 7: cells.append("")
    for row in [cells[i:i + 7] for i in range(0, len(cells), 7)]:
        cols = st.columns(7)
        for ci, day in enumerate(row):
            if day == "":
                cols[ci].markdown('<div class="cal-day empty"></div>', unsafe_allow_html=True)
            else:
                ds       = f"{y}-{m:02d}-{day:02d}"
                ev       = all_events.get(ds)
                is_today = (date(y, m, day) == today)
                cls      = "today" if is_today else ("holiday" if ev and ev["type"] == "holiday" else "event" if ev else "")
                num_cls  = "today-num" if is_today else ""
                tag_html = ""
                if ev:
                    tc       = "holiday" if ev["type"] == "holiday" else ev.get("type", "event")
                    tag_html = f'<span class="cal-tag {tc}">{ev["name"][:14]}{"…" if len(ev["name"]) > 14 else ""}</span>'
                cols[ci].markdown(f'<div class="cal-day {cls}"><div class="cal-day-num {num_cls}">{day}</div>{tag_html}</div>', unsafe_allow_html=True)

    st.markdown('<div style="display:flex;gap:16px;font-size:12px;color:#5a6070;margin:10px 0;">🟡 Holiday &nbsp; 🔵 Event &nbsp; 🟣 Birthday &nbsp; <span style="color:#818cf8">◼ Today</span></div>', unsafe_allow_html=True)

    with st.expander("➕ Add personal event"):
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        with c1: ev_name     = st.text_input("Event name", key="ev_name")
        with c2: ev_type     = st.selectbox("Type", ["birthday", "outing", "personal"], key="ev_type")
        with c3: ev_date_inp = st.date_input("Date", key="ev_date2")
        with c4:
            st.markdown("<br>", unsafe_allow_html=True)
            ev_add = st.button("Add ✓", type="primary", key="ev_add")
        if ev_add and ev_name:
            entry = {"name": ev_name, "date": str(ev_date_inp), "type": ev_type}
            add_event(entry)
            if st.session_state.client:
                st.session_state.ai_insight = analyze_new_entry(st.session_state.client, "event", entry, user_name)
            st.success(f"Added: {ev_name}"); st.rerun()

    if st.session_state.ai_insight:
        st.markdown(f'<div class="ai-bubble">💡 {st.session_state.ai_insight}</div>', unsafe_allow_html=True)
        st.session_state.ai_insight = ""

    upcoming = [(d, n) for d, n in SL_HOLIDAYS.items() if datetime.strptime(d, "%Y-%m-%d").date() >= today]
    st.markdown('<div class="section-label" style="margin-top:12px">Upcoming Sri Lankan public holidays</div>', unsafe_allow_html=True)
    for d, n in sorted(upcoming)[:5]:
        days_away = (datetime.strptime(d, "%Y-%m-%d").date() - today).days
        st.markdown(f'<div style="display:flex;justify-content:space-between;padding:8px 12px;background:#13151f;border-radius:8px;margin-bottom:6px;font-size:13px;"><span style="color:#e8eaf0">🎌 {n}</span><span style="color:#5a6070">{d} · in {days_away} days</span></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# BALANCES
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🏦 Balances":
    st.markdown("## Bank & Cash Balances")
    bal    = get_latest_balance()
    liquid = bal.get("bank", 0) + bal.get("cash", 0)
    runway = calculate_runway_days()

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(f'<div class="metric-card"><div class="metric-label">Bank balance</div><div class="metric-value">LKR {bal.get("bank", 0):,.0f}</div><div class="metric-sub">updated {bal.get("date", "—")}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-card"><div class="metric-label">Cash in hand</div><div class="metric-value">LKR {bal.get("cash", 0):,.0f}</div><div class="metric-sub">updated {bal.get("date", "—")}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-card"><div class="metric-label">Total liquid</div><div class="metric-value pos">LKR {liquid:,.0f}</div><div class="metric-sub">bank + cash</div></div>', unsafe_allow_html=True)
    with c4:
        r_color = "neg" if runway["runway_days"] < 14 else "warn" if runway["runway_days"] < 30 else "pos"
        st.markdown(f'<div class="metric-card"><div class="metric-label">Runway</div><div class="metric-value {r_color}">{runway["runway_days"]} days</div><div class="metric-sub">at LKR {runway["avg_daily_spending"]:,.0f}/day</div></div>', unsafe_allow_html=True)

    with st.expander("📝 Update balance", expanded=True):
        c1, c2, c3, c4 = st.columns([2, 2, 3, 1])
        with c1: new_bank = st.number_input("Bank (LKR)", min_value=0.0, value=float(bal.get("bank", 0)), step=100.0)
        with c2: new_cash = st.number_input("Cash (LKR)", min_value=0.0, value=float(bal.get("cash", 0)), step=100.0)
        with c3: bal_note = st.text_input("Note (optional)", placeholder="e.g. after salary deposit")
        with c4:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Save ✓", type="primary"):
                add_balance_snapshot({"bank": new_bank, "cash": new_cash, "date": str(date.today()), "note": bal_note})
                st.success("Balance updated!"); st.rerun()

    with st.expander("⚙️ Manual spending limit (if no income history)"):
        manual = st.number_input("Monthly safe spending limit (LKR)", min_value=0.0, value=float(get_manual_limit()), step=500.0)
        if st.button("Save limit"):
            set_manual_limit(int(manual)); st.success("Limit saved!")

    st.markdown('<div class="section-label">Balance history</div>', unsafe_allow_html=True)
    for b in sorted(get_balances(), key=lambda x: x["date"], reverse=True):
        c1, c2, c3 = st.columns([2, 4, 2])
        with c1: st.markdown(f"<span style='color:#5a6070;font-size:13px'>{b['date']}</span>", unsafe_allow_html=True)
        with c2: st.markdown(f"<span style='color:#9ca3b0;font-size:13px'>Bank: LKR {b.get('bank', 0):,.0f} · Cash: LKR {b.get('cash', 0):,.0f} {('· ' + b['note']) if b.get('note') else ''}</span>", unsafe_allow_html=True)
        with c3: st.markdown(f"<span style='color:#e8eaf0;font-family:DM Mono;font-size:13px'>LKR {b.get('bank', 0) + b.get('cash', 0):,.0f}</span>", unsafe_allow_html=True)
        st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY TABLE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Summary Table":
    st.markdown("## Summary Table")
    st.caption("Quick view of all your entries in one place.")

    tab1, tab2, tab3 = st.tabs(["💰 Income", "💳 Expenses", "📊 Category Summary"])

    with tab1:
        incomes = sorted(get_income(), key=lambda x: x["date"], reverse=True)
        if incomes:
            df = pd.DataFrame(incomes)[["date", "source", "note", "amount"]]
            df.columns = ["Date", "Source", "Note", "Amount (LKR)"]
            df["Amount (LKR)"] = df["Amount (LKR)"].apply(lambda x: f"{x:,.0f}")
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.markdown(f"**Total: LKR {get_total_income():,.0f}**")
        else:
            st.info("No income entries yet.")

    with tab2:
        exps = sorted(get_expenses(), key=lambda x: x["date"], reverse=True)
        if exps:
            anomaly_ids = {a["id"] for a in detect_spending_anomalies()}
            df = pd.DataFrame(exps)[["date", "cat", "note", "spec", "amount"]]
            df.columns = ["Date", "Category", "Description", "Specify", "Amount (LKR)"]
            df["Amount (LKR)"] = df["Amount (LKR)"].apply(lambda x: f"{x:,.0f}")
            df["⚠"] = df.index.map(lambda i: "⚠ unusual" if exps[i]["id"] in anomaly_ids else "")
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.markdown(f"**Total: LKR {get_total_expenses():,.0f}**")
        else:
            st.info("No expense entries yet.")

    with tab3:
        cat_totals  = get_category_totals()
        total_spent = sum(cat_totals.values())
        income      = get_total_income()
        goal        = evaluate_goal()
        rows = []
        for cat, amt in cat_totals.items():
            rows.append({
                "Category":        cat.title(),
                "Amount (LKR)":    f"{amt:,.0f}",
                "% of Income":     f"{amt / max(income, 1) * 100:.1f}%",
                "% of Safe Limit": f"{amt / max(goal['safe_limit'], 1) * 100:.1f}%",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.markdown(f"""
        **Total spent: LKR {total_spent:,.0f}** &nbsp;|&nbsp;
        **Income: LKR {income:,.0f}** &nbsp;|&nbsp;
        **Safe limit: LKR {goal['safe_limit']:,.0f}** &nbsp;|&nbsp;
        **Net: LKR {get_net_this_month():,.0f}**
        """)

        st.markdown("---")
        st.markdown("**Recurring Expenses**")
        rate     = get_usd_rate()
        rec_rows = []
        for r in get_recurring():
            lkr = r["amount_usd"] * rate if r["currency"] == "USD" else r["amount_lkr"]
            rec_rows.append({
                "Name":        r["name"],
                "Category":    r["cat"].title(),
                "Amount":      f"${r['amount_usd']}" if r["currency"] == "USD" else f"LKR {r['amount_lkr']:,.0f}",
                "LKR/month":   f"{lkr:,.0f}",
                "Billing Day": r["day_of_month"],
                "Status":      "✅ Active" if r["active"] else "⏸ Paused",
            })
        if rec_rows:
            st.dataframe(pd.DataFrame(rec_rows), use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# AI CHAT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🤖 AI Chat":
    st.markdown("## AI Financial Advisor")

    if not st.session_state.client:
        st.warning("Add your GROQ API key in `.env` file or the sidebar to use the AI advisor.")
        st.code("GROQ_API_KEY=your_key_here", language="bash")
        st.stop()

    risk   = calculate_risk_score()
    goal   = evaluate_goal()
    pred   = predict_monthly_spending()
    runway = calculate_runway_days()
    st.markdown(f"""
    <div style='display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;'>
      <div style='background:#13151f;border:1px solid #1e2130;border-radius:10px;padding:10px 16px;font-size:13px;'>
        🎯 Risk: <strong style='color:{risk["color"]}'>{risk["score"]}/100 {risk["label"]}</strong>
      </div>
      <div style='background:#13151f;border:1px solid #1e2130;border-radius:10px;padding:10px 16px;font-size:13px;'>
        📊 Limit used: <strong style='color:#e8eaf0'>{goal["usage_pct"]}%</strong>
      </div>
      <div style='background:#13151f;border:1px solid #1e2130;border-radius:10px;padding:10px 16px;font-size:13px;'>
        🔮 Projected: <strong style='color:#e8eaf0'>LKR {pred["adjusted_prediction"]:,.0f}</strong>
      </div>
      <div style='background:#13151f;border:1px solid #1e2130;border-radius:10px;padding:10px 16px;font-size:13px;'>
        ⏱ Runway: <strong style='color:{"#ef4444" if runway["runway_days"] < 14 else "#e8eaf0"}'>{runway["runway_days"]} days</strong>
      </div>
    </div>""", unsafe_allow_html=True)

    if st.button("🧠 Generate Weekly Financial Insight", type="secondary"):
        with st.spinner("Generating your weekly insight..."):
            insight = generate_weekly_insight(st.session_state.client, user_name)
        st.markdown(f'<div class="ai-bubble">{insight.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="section-label">Quick questions</div>', unsafe_allow_html=True)
    q1, q2, q3, q4 = st.columns(4)
    quick = None
    with q1:
        if st.button("📈 Spending analysis"): quick = "Analyze my spending this month and give me specific advice based on my safe limit."
    with q2:
        if st.button("🎂 Event planning"):    quick = "I'm having my friend's birthday this month. How should I manage my expenses to afford it without exceeding my safe limit?"
    with q3:
        if st.button("🔮 End-of-month"):      quick = "Based on my current spending pattern and upcoming events, what will my financial situation look like at end of month?"
    with q4:
        if st.button("✂️ Where to cut"):      quick = "Where exactly should I cut my spending, and by how much, to improve my financial position?"

    st.markdown("---")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"], avatar="💰" if msg["role"] == "assistant" else None):
            st.markdown(msg["content"])

    if not st.session_state.chat_history:
        with st.chat_message("assistant", avatar="💰"):
            st.markdown(f"{get_greeting(user_name)} I'm FinAgent, your AI financial advisor. I have full visibility into your income, expenses, subscriptions, balances, and upcoming events. What would you like to know?")

    user_input = st.chat_input("Ask anything about your finances...") or quick
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"): st.markdown(user_input)
        with st.chat_message("assistant", avatar="💰"):
            with st.spinner("Thinking..."):
                try:
                    reply = agent_chat(st.session_state.client, st.session_state.chat_history[:-1], user_input, user_name)
                except Exception as e:
                    reply = f"Something went wrong: {str(e)}. Please try again."
            st.markdown(reply)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        st.rerun()