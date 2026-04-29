"""
agent.py — AI agent for FinAgent v3.
Uses structured financial summary for all AI calls.
Forces structured reasoning: insight / risk / action / confidence.
"""

from datetime import date, datetime, timedelta
from groq import Groq
from data import (
    get_income, get_expenses, get_recurring, get_events,
    get_total_income, get_total_expenses, get_category_totals,
    get_recurring_monthly_total, get_latest_balance,
    get_usd_rate, SL_HOLIDAYS, EXPENSE_CATEGORIES
)
from intelligence import (
    build_financial_summary, compute_safe_spending_limit,
    predict_monthly_spending, evaluate_goal, calculate_risk_score,
    detect_spending_anomalies, analyze_event_spending_impact,
    calculate_runway_days, get_net_this_month, EVENT_COST_ESTIMATES
)


def build_system_prompt(user_name: str = "") -> str:
    name_str = user_name or "the user"
    summary  = build_financial_summary()
    goal     = evaluate_goal()
    pred     = predict_monthly_spending()
    runway   = calculate_runway_days()
    risk     = calculate_risk_score()
    anomalies = detect_spending_anomalies()
    correlations = analyze_event_spending_impact()
    cat_totals = get_category_totals()
    today = date.today()

    # Format correlations
    corr_str = "\n".join(f"  - {c}" for c in summary["event_correlations"]) or "  None detected"

    # Format anomalies
    anom_str = "\n".join(
        f"  - {a['note']} LKR {a['amount']:,.0f} ({a['times_avg']}x avg of LKR {a['avg']:,.0f})"
        for a in anomalies[:3]
    ) or "  None detected"

    # Format category breakdown
    cat_str = "\n".join(
        f"  {cat}: LKR {amt:,.0f} ({amt/max(summary['safe_limit'],1)*100:.1f}% of safe limit)"
        for cat, amt in cat_totals.items() if amt > 0
    )

    return f"""You are FinAgent — an intelligent, empathetic AI financial advisor for students in Sri Lanka.
You are speaking with {name_str}.

== FINANCIAL SUMMARY ==
Income this month:     LKR {summary['income']:,.0f}
One-time expenses:     LKR {summary['expenses']:,.0f}
Recurring costs:       LKR {summary['recurring']:,.0f}
Net remaining:         LKR {get_net_this_month():,.0f} {"⚠ DEFICIT" if get_net_this_month() < 0 else ""}
Safe spending limit:   LKR {summary['safe_limit']:,.0f} (method: {summary['safe_limit_method']})
Limit used:            {summary['spending_used_pct']}% → Status: {summary['goal_status'].upper()}
Projected spending:    LKR {summary['projected_spending']:,.0f} (includes LKR {summary['projected_event_cost']:,.0f} for upcoming events)
Top category:          {summary['top_category']} at LKR {summary['top_category_amt']:,.0f}

== GOAL STATUS ==
Safe limit: LKR {goal['safe_limit']:,.0f}
Used: {goal['usage_pct']}% | Status: {goal['status']}
Overshoot: LKR {goal['overshoot']:,.0f}
Remaining daily budget: LKR {goal['daily_budget_remaining']:,.0f}/day

== RISK & RUNWAY ==
Risk score:     {risk['score']}/100 ({risk['label']})
Runway:         {runway['runway_days']} days (liquid: LKR {runway['liquid']:,.0f})
Avg daily spend: LKR {runway['avg_daily_spending']:,.0f}

== CATEGORY BREAKDOWN ==
{cat_str}

== ANOMALIES DETECTED ==
{anom_str}

== EVENT-SPENDING CORRELATIONS ==
{corr_str}

== UPCOMING EVENTS ==
{chr(10).join('  - ' + e for e in summary['upcoming_events']) if summary['upcoming_events'] else '  None'}

== USD RATE ==
1 USD = LKR {get_usd_rate()} (live rate)

== BEHAVIOR RULES ==
1. Address {name_str} by name naturally (not in every sentence, just when appropriate).
2. NEVER say "you spent X% of income" — always reference the safe spending limit instead.
3. For event questions (e.g. "friend's birthday"), give a concrete plan: estimate cost, identify where to cut, calculate if affordable.
4. For structured questions, respond in this JSON format:
   {{"insight": "...", "risk": "...", "action": "...", "confidence": "low/medium/high"}}
5. For conversational questions, respond naturally but stay data-grounded.
6. Reference actual LKR amounts. No generic advice.
7. User has VARIABLE income — never assume next month will be the same.
8. Be warm, direct, student-friendly. No financial jargon.
9. Currency: LKR. USD only for subscription context.
"""


def chat(client: Groq, history: list, user_msg: str, user_name: str = "") -> str:
    messages = [{"role": "system", "content": build_system_prompt(user_name)}]
    for m in history:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_msg})
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1000,
        messages=messages,
    )
    return resp.choices[0].message.content


def analyze_new_entry(client: Groq, entry_type: str, entry: dict, user_name: str = "") -> str:
    """Short AI insight shown immediately when user adds any entry."""
    summary = build_financial_summary()
    goal    = evaluate_goal()
    name_str = user_name or "you"

    if entry_type == "income":
        prompt = f"""{name_str} just added income: LKR {entry['amount']:,.0f} from {entry['source']}.
Total income this month: LKR {summary['income']:,.0f}.
Safe spending limit: LKR {summary['safe_limit']:,.0f} | Used: {summary['spending_used_pct']}%.
Give a 1-2 sentence insight. Be specific about how this affects their financial position."""

    elif entry_type == "expense":
        anomalies = detect_spending_anomalies()
        is_anomaly = any(a["id"] == entry.get("id") for a in anomalies)
        cat_totals = get_category_totals()
        cat_total  = cat_totals.get(entry["cat"], 0)
        prompt = f"""{name_str} just added: LKR {entry['amount']:,.0f} for {entry['note']} ({entry['cat']}).
{'⚠ This expense is unusually high compared to their normal spending pattern.' if is_anomaly else ''}
{entry['cat'].title()} total this month: LKR {cat_total:,.0f}.
Safe limit used: {goal['usage_pct']}% (LKR {goal['total_spent']:,.0f} of LKR {goal['safe_limit']:,.0f}).
Net remaining: LKR {get_net_this_month():,.0f}.
Give 1-2 specific sentences. Flag if this is anomalous or if limit is getting tight."""

    elif entry_type == "recurring":
        rate = get_usd_rate()
        amt  = entry["amount_usd"] * rate if entry["currency"] == "USD" else entry["amount_lkr"]
        from data import get_recurring_monthly_total
        prompt = f"""{name_str} added a new recurring expense: {entry['name']} for LKR {amt:,.0f}/month.
Total monthly recurring is now LKR {get_recurring_monthly_total():,.0f}.
Safe spending limit: LKR {summary['safe_limit']:,.0f}.
Give a 1-2 sentence insight on the long-term impact of this subscription."""

    elif entry_type == "event":
        cost_est = EVENT_COST_ESTIMATES.get(entry.get("type", "personal"), 1500)
        pred = predict_monthly_spending()
        prompt = f"""{name_str} added event: '{entry['name']}' on {entry['date']} ({entry.get('type','personal')}).
Estimated event cost: LKR {cost_est:,.0f}.
Updated projected spending: LKR {pred['adjusted_prediction']:,.0f} (includes LKR {pred['event_cost']:,.0f} for events).
Safe limit: LKR {summary['safe_limit']:,.0f}.
Give 2 sentences: estimated financial impact and one specific tip to prepare."""
    else:
        return ""

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.choices[0].message.content


def generate_weekly_insight(client: Groq, user_name: str = "") -> str:
    """Generates a comprehensive weekly financial insight report."""
    summary      = build_financial_summary()
    anomalies    = detect_spending_anomalies()
    correlations = analyze_event_spending_impact()
    goal         = evaluate_goal()
    risk         = calculate_risk_score()
    pred         = predict_monthly_spending()
    cat_totals   = get_category_totals()

    # Find fastest growing category (simple heuristic: highest absolute spend)
    top_cats = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)[:3]

    prompt = f"""Generate a weekly financial insight report for {user_name or 'the user'}.

Data:
- Income: LKR {summary['income']:,.0f} | Spent: LKR {summary['expenses']:,.0f} | Recurring: LKR {summary['recurring']:,.0f}
- Safe limit: LKR {summary['safe_limit']:,.0f} | Used: {summary['spending_used_pct']}%
- Risk score: {risk['score']}/100 ({risk['label']})
- Projected month-end: LKR {pred['adjusted_prediction']:,.0f}
- Top spending categories: {', '.join(f"{c}: LKR {a:,.0f}" for c, a in top_cats)}
- Anomalies: {len(anomalies)} unusual transactions detected
- Event correlations: {len(correlations)} spending spikes linked to events
- Upcoming events: {', '.join(summary['upcoming_events'][:3]) or 'None'}

Write a structured weekly insight with these sections:
1. 📊 Spending Summary (2 sentences)
2. 🔍 Notable Patterns (what stands out, including any event correlations)
3. ⚠️ Risks to Watch (specific risks with LKR amounts)
4. 🎯 3 Action Items for this week (concrete, numbered, with LKR targets)

Keep it concise, specific, and student-friendly."""

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=600,
        messages=[{"role": "system", "content": build_system_prompt(user_name)}, {"role": "user", "content": prompt}]
    )
    return resp.choices[0].message.content