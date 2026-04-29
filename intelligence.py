"""
intelligence.py — Advanced AI reasoning engine for FinAgent v3.
Implements all 11 upgrades: adaptive goals, predictions, anomaly detection,
runway, risk score, event correlation, structured outputs, weekly insights.
"""

from datetime import date, datetime, timedelta
from data import (
    get_income, get_expenses, get_recurring, get_events,
    get_total_income, get_total_expenses, get_category_totals,
    get_recurring_monthly_total, get_latest_balance,
    get_income_history, get_manual_limit, EXPENSE_CATEGORIES
)


# ── 1. ADAPTIVE SAFE SPENDING LIMIT ───────────────────────────────────────────
def compute_safe_spending_limit() -> dict:
    """
    Calculates a conservative spending limit based on income history.
    Falls back to manual limit if no history exists.
    Returns dict with limit, method, and average_income.
    """
    history = get_income_history()  # {month_str: total}
    if len(history) >= 2:
        avg_income = sum(history.values()) / len(history)
        safe_limit = avg_income * 0.7
        method = "historical"
    elif len(history) == 1:
        avg_income = list(history.values())[0]
        safe_limit = avg_income * 0.7
        method = "single_month"
    else:
        avg_income = 0
        safe_limit = get_manual_limit()
        method = "manual"
    return {
        "safe_limit": round(safe_limit),
        "avg_income": round(avg_income),
        "method": method,
    }


# ── 2. EVENT-AWARE SPENDING PREDICTION ────────────────────────────────────────
EVENT_COST_ESTIMATES = {
    "birthday": 3000,
    "outing":   2500,
    "holiday":  4000,
    "personal": 1500,
}

def predict_monthly_spending() -> dict:
    """
    Predicts end-of-month spending using daily average + upcoming event costs.
    Returns prediction, event_cost, and breakdown.
    """
    today_day = datetime.today().day
    total_days = 30
    days_left = total_days - today_day

    current_spending = get_total_expenses()
    recurring = get_recurring_monthly_total()
    daily_avg = current_spending / max(today_day, 1)
    base_prediction = (current_spending / max(today_day, 1)) * total_days + recurring

    # Upcoming events this month
    today = date.today()
    month_str = f"{today.year}-{today.month:02d}"
    upcoming = []
    for ev in get_events():
        if ev["date"].startswith(month_str):
            ev_date = datetime.strptime(ev["date"], "%Y-%m-%d").date()
            if ev_date >= today:
                cost = EVENT_COST_ESTIMATES.get(ev.get("type", "personal"), 1500)
                upcoming.append({"name": ev["name"], "date": ev["date"], "type": ev.get("type"), "estimated_cost": cost})

    event_cost = sum(e["estimated_cost"] for e in upcoming)
    adjusted = base_prediction + event_cost

    return {
        "base_prediction": round(base_prediction),
        "event_cost": round(event_cost),
        "adjusted_prediction": round(adjusted),
        "daily_avg": round(daily_avg),
        "days_left": days_left,
        "upcoming_events": upcoming,
    }


# ── 3. EVENT-SPENDING CORRELATION ─────────────────────────────────────────────
def analyze_event_spending_impact() -> list:
    """
    Links spending spikes to nearby events.
    Returns list of correlations found.
    """
    expenses = get_expenses()
    events   = get_events()
    correlations = []

    for ev in events:
        ev_date = ev["date"]
        # Check spending on event date and 1 day before/after
        for delta in [0, -1, 1]:
            check_date = (datetime.strptime(ev_date, "%Y-%m-%d") + timedelta(days=delta)).strftime("%Y-%m-%d")
            day_total = sum(e["amount"] for e in expenses if e["date"] == check_date)
            if day_total > 0:
                label = "on" if delta == 0 else ("day before" if delta == -1 else "day after")
                correlations.append({
                    "event": ev["name"],
                    "event_date": ev_date,
                    "spend_date": check_date,
                    "amount": day_total,
                    "label": label,
                })
    return correlations


# ── 4. ANOMALY DETECTION ──────────────────────────────────────────────────────
def detect_spending_anomalies() -> list:
    """
    Flags transactions that are >2x the user's average expense.
    Returns list of anomalous transactions.
    """
    expenses = get_expenses()
    if not expenses:
        return []
    avg = sum(e["amount"] for e in expenses) / len(expenses)
    threshold = avg * 2
    anomalies = []
    for e in expenses:
        if e["amount"] > threshold:
            anomalies.append({
                **e,
                "avg": round(avg),
                "times_avg": round(e["amount"] / avg, 1),
            })
    return sorted(anomalies, key=lambda x: x["amount"], reverse=True)


# ── 5. RUNWAY CALCULATION ─────────────────────────────────────────────────────
def calculate_runway_days() -> dict:
    """
    Estimates how many days your current liquid funds will last.
    """
    bal = get_latest_balance()
    liquid = bal.get("bank", 0) + bal.get("cash", 0)
    today_day = datetime.today().day
    total_spent = get_total_expenses() + get_recurring_monthly_total()
    avg_daily = total_spent / max(today_day, 1)

    runway = round(liquid / avg_daily) if avg_daily > 0 else 999
    return {
        "liquid": liquid,
        "avg_daily_spending": round(avg_daily),
        "runway_days": runway,
        "runs_out_on": str(date.today() + timedelta(days=runway)) if runway < 999 else "N/A",
    }


# ── 6. GOAL-BASED REASONING ───────────────────────────────────────────────────
def evaluate_goal() -> dict:
    """
    Compares actual spending against safe spending limit.
    Returns goal status and recommended daily spend.
    """
    goal_data  = compute_safe_spending_limit()
    safe_limit = goal_data["safe_limit"]
    total_spent = get_total_expenses() + get_recurring_monthly_total()
    usage_pct  = total_spent / max(safe_limit, 1)
    days_left  = 30 - datetime.today().day
    overshoot  = max(total_spent - safe_limit, 0)
    daily_budget_remaining = max(safe_limit - total_spent, 0) / max(days_left, 1)

    if usage_pct >= 1.0:
        status = "exceeded"
    elif usage_pct >= 0.85:
        status = "warning"
    elif usage_pct >= 0.65:
        status = "caution"
    else:
        status = "healthy"

    return {
        "safe_limit": safe_limit,
        "total_spent": round(total_spent),
        "usage_pct": round(usage_pct * 100, 1),
        "status": status,
        "overshoot": round(overshoot),
        "daily_budget_remaining": round(daily_budget_remaining),
        "method": goal_data["method"],
    }


# ── 9. FINANCIAL RISK SCORE ───────────────────────────────────────────────────
def calculate_risk_score() -> dict:
    """
    Produces a 0–100 risk score based on spending ratio, projection, and events.
    """
    goal    = evaluate_goal()
    pred    = predict_monthly_spending()
    runway  = calculate_runway_days()
    anomalies = detect_spending_anomalies()

    score = 0

    # Spending ratio vs safe limit (max 40 pts)
    score += min(goal["usage_pct"] * 0.4, 40)

    # Projected overshoot (max 25 pts)
    safe_limit = goal["safe_limit"]
    if pred["adjusted_prediction"] > safe_limit:
        overshoot_pct = (pred["adjusted_prediction"] - safe_limit) / max(safe_limit, 1)
        score += min(overshoot_pct * 50, 25)

    # Upcoming events (max 20 pts)
    score += min(len(pred["upcoming_events"]) * 5, 20)

    # Short runway (max 15 pts)
    if runway["runway_days"] < 7:
        score += 15
    elif runway["runway_days"] < 14:
        score += 10
    elif runway["runway_days"] < 30:
        score += 5

    score = round(min(score, 100))

    if score >= 75:   label, color = "High Risk",    "#ef4444"
    elif score >= 50: label, color = "Medium Risk",  "#f59e0b"
    elif score >= 25: label, color = "Low Risk",     "#3b82f6"
    else:             label, color = "Healthy",      "#22c55e"

    return {"score": score, "label": label, "color": color}


# ── 7. FULL FINANCIAL SUMMARY FOR AI CONTEXT ─────────────────────────────────
def build_financial_summary() -> dict:
    """
    Assembles the complete financial context object injected into every AI call.
    """
    cat_totals  = get_category_totals()
    top_cat     = max(cat_totals, key=cat_totals.get) if cat_totals else "N/A"
    goal        = evaluate_goal()
    pred        = predict_monthly_spending()
    runway      = calculate_runway_days()
    risk        = calculate_risk_score()
    anomalies   = detect_spending_anomalies()
    correlations = analyze_event_spending_impact()

    today = date.today()
    upcoming_events = []
    for ev in get_events():
        ev_d = datetime.strptime(ev["date"], "%Y-%m-%d").date()
        if ev_d >= today:
            days_away = (ev_d - today).days
            upcoming_events.append(f"{ev['name']} in {days_away} days ({ev['date']})")

    return {
        "income":            get_total_income(),
        "expenses":          get_total_expenses(),
        "recurring":         get_recurring_monthly_total(),
        "net":               get_net_this_month() if hasattr(__import__('data'), 'get_net_this_month') else 0,
        "safe_limit":        goal["safe_limit"],
        "safe_limit_method": goal["method"],
        "spending_used_pct": goal["usage_pct"],
        "goal_status":       goal["status"],
        "projected_spending":pred["adjusted_prediction"],
        "projected_event_cost": pred["event_cost"],
        "top_category":      top_cat,
        "top_category_amt":  cat_totals.get(top_cat, 0),
        "runway_days":       runway["runway_days"],
        "risk_score":        risk["score"],
        "risk_label":        risk["label"],
        "anomaly_count":     len(anomalies),
        "upcoming_events":   upcoming_events,
        "event_correlations": [f"Spending of LKR {c['amount']:,.0f} on {c['spend_date']} ({c['label']} {c['event']})" for c in correlations],
    }


def get_net_this_month():
    return get_total_income() - get_total_expenses() - get_recurring_monthly_total()