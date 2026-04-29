# 💰 FinAgent v3 — AI Financial Intelligence Agent

An autonomous, context-aware AI financial agent for students with variable income. Built with Streamlit + Claude (Anthropic API).

---

## 🚀 Quick Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Add your API key (one-time setup)
Open the `.env` file and replace the placeholder:
```
ANTHROPIC_API_KEY=your_actual_key_here
```
Get your key at: https://console.anthropic.com

### 3. Run the app
```bash
python -m streamlit run app.py
```

---

## 📁 File Structure

```
finagent_v3/
├── app.py              # Streamlit UI — all 8 pages
├── data.py             # Data layer — JSON persistence, all CRUD + reset
├── intelligence.py     # AI reasoning engine — 11 upgrade modules
├── agent.py            # Claude API layer — prompts, chat, insights
├── .env                # API key (never commit this)
├── requirements.txt    # Dependencies
└── data/               # Auto-created — stores all JSON files
    ├── income.json
    ├── expenses.json
    ├── recurring.json
    ├── events.json
    ├── balances.json
    └── settings.json
```

---

## ✨ Features

| Feature | Description |
|---|---|
| 📊 Overview | Metrics, charts, alerts, goal progress, risk score |
| 💰 Income | Variable income tracking (salary, freelance, gifts, etc.) |
| 💳 Expenses | One-time expenses with optional sub-specification |
| 🔁 Recurring | USD/LKR subscriptions, pause/resume, live USD rate |
| 🗓 Calendar | Visual calendar with Sri Lankan public holidays + personal events |
| 🏦 Balances | Bank + cash tracking, runway calculation |
| 📋 Summary Table | Full income/expense/category tables with anomaly flags |
| 🤖 AI Chat | Context-aware Claude agent with structured reasoning |

---

## 🧠 AI Intelligence Modules (intelligence.py)

| Module | Function |
|---|---|
| Adaptive Goal | `compute_safe_spending_limit()` — based on income history |
| Event-Aware Prediction | `predict_monthly_spending()` — accounts for upcoming events |
| Event Correlation | `analyze_event_spending_impact()` — links spending to events |
| Anomaly Detection | `detect_spending_anomalies()` — flags 2x average transactions |
| Runway Calculation | `calculate_runway_days()` — days until funds run out |
| Goal Evaluation | `evaluate_goal()` — tracks safe limit usage |
| Risk Score | `calculate_risk_score()` — 0-100 financial risk score |
| Financial Summary | `build_financial_summary()` — full context for AI |
| Weekly Insight | `generate_weekly_insight()` — AI weekly report |

---

## 💡 Key Design Decisions

- **No fixed income assumed** — the agent adapts to variable income patterns
- **Safe spending limit** — derived from income history (70% of average), not a fixed budget
- **Live USD rate** — auto-fetched from open.er-api.com on startup
- **API key in .env** — no need to paste it in the UI every time
- **Sample data reset** — click "Reset & Start Fresh" on the Overview to clear all demo data
- **Name + greeting** — personalized with time-based greeting (morning/afternoon/evening)

---

## 🏫 Assignment Info
- Course: Data Science Applications and AI [LB3114]  
- University: General Sir John Kotelawala Defence University  
- Deadline: 30th April 2026
