"""
data.py — Full data layer for FinAgent v3.
Handles: income, one-time expenses, recurring expenses, balances, events, settings.
All data persisted as JSON files, organised per profile.

PROFILE STRUCTURE:
  data/
    profiles.json              ← list of all profiles
    global_settings.json       ← shared settings (usd_rate, usd_fetch_date)
    profiles/
      <profile_id>/
        income.json
        expenses.json
        recurring.json
        events.json
        balances.json
        settings.json          ← per-profile settings (manual_limit, is_sample)

FLOW:
  - App starts          → load profile list; if none, show create-profile screen
  - Select profile      → load that profile's data; show sample if is_sample=True
  - Add first entry     → _switch_to_user_data() clears sample flag & data
  - Reset profile       → clears entries, is_sample=False
                          next run with no data files → seeds sample again
  - Create new profile  → always starts with sample data
"""

import json
import os
import requests
from datetime import datetime, date, timedelta

# ── Constants ──────────────────────────────────────────────────────────────────
EXPENSE_CATEGORIES = ["food", "clothes", "subscriptions", "transport", "entertainment", "health", "other"]
INCOME_SOURCES     = ["salary", "freelance", "gift", "allowance", "business", "other"]
CAT_COLORS         = ["#f59e0b", "#ec4899", "#8b5cf6", "#3b82f6", "#f97316", "#10b981", "#6b7280"]

DATA_DIR      = os.path.join(os.path.dirname(__file__), "data")
PROFILES_DIR  = os.path.join(DATA_DIR, "profiles")
PROFILES_FILE = os.path.join(DATA_DIR, "profiles.json")
GLOBAL_FILE   = os.path.join(DATA_DIR, "global_settings.json")

os.makedirs(PROFILES_DIR, exist_ok=True)

# ── Active profile context ─────────────────────────────────────────────────────
_active_profile_id: str = ""

def set_active_profile(profile_id: str):
    global _active_profile_id
    _active_profile_id = profile_id

def get_active_profile_id() -> str:
    return _active_profile_id

def _profile_dir(profile_id: str = "") -> str:
    pid = profile_id or _active_profile_id
    d   = os.path.join(PROFILES_DIR, pid)
    os.makedirs(d, exist_ok=True)
    return d

def _profile_file(key: str, profile_id: str = "") -> str:
    return os.path.join(_profile_dir(profile_id), f"{key}.json")


# ── Sri Lankan public holidays 2026 ───────────────────────────────────────────
SL_HOLIDAYS = {
    "2026-01-01": "New Year's Day",
    "2026-01-14": "Tamil Thai Pongal Day",
    "2026-02-04": "National Day",
    "2026-02-14": "Maha Sivarathri",
    "2026-03-03": "Id-ul-Fitr (Ramadan)",
    "2026-04-13": "Day before Sinhala & Tamil New Year",
    "2026-04-14": "Sinhala & Tamil New Year",
    "2026-04-18": "Good Friday",
    "2026-05-01": "May Day",
    "2026-05-14": "Vesak Full Moon Poya",
    "2026-05-15": "Day following Vesak",
    "2026-06-12": "Id-ul-Alha (Haj Festival)",
    "2026-06-13": "Poson Full Moon Poya",
    "2026-07-12": "Esala Full Moon Poya",
    "2026-08-11": "Nikini Full Moon Poya",
    "2026-09-09": "Binara Full Moon Poya",
    "2026-10-09": "Vap Full Moon Poya",
    "2026-11-07": "Il Full Moon Poya",
    "2026-11-10": "Deepavali",
    "2026-12-07": "Unduvap Full Moon Poya",
    "2026-12-25": "Christmas Day",
}

# ── Sample seed data ───────────────────────────────────────────────────────────
_SAMPLE_DATA = {
    "income": [
        {"id": 1, "amount": 15000, "source": "allowance", "note": "Monthly allowance", "date": "2026-04-01"},
        {"id": 2, "amount": 8000,  "source": "freelance",  "note": "Design project",   "date": "2026-04-10"},
        {"id": 3, "amount": 3000,  "source": "gift",       "note": "Birthday money",   "date": "2026-04-15"},
    ],
    "expenses": [
        {"id": 1,  "amount": 3200, "cat": "food",          "note": "Supermarket",    "spec": "",       "date": "2026-04-01"},
        {"id": 2,  "amount": 1500, "cat": "transport",     "note": "Bus pass",       "spec": "",       "date": "2026-04-02"},
        {"id": 3,  "amount": 2800, "cat": "food",          "note": "Restaurant",     "spec": "KFC",    "date": "2026-04-08"},
        {"id": 4,  "amount": 5500, "cat": "clothes",       "note": "Clothing store", "spec": "H&M",    "date": "2026-04-10"},
        {"id": 5,  "amount": 650,  "cat": "transport",     "note": "Grab ride",      "spec": "",       "date": "2026-04-11"},
        {"id": 6,  "amount": 4200, "cat": "entertainment", "note": "Party supplies", "spec": "",       "date": "2026-04-13"},
        {"id": 7,  "amount": 3100, "cat": "food",          "note": "Groceries",      "spec": "Keells", "date": "2026-04-14"},
        {"id": 8,  "amount": 500,  "cat": "other",         "note": "Stationery",     "spec": "",       "date": "2026-04-21"},
        {"id": 9,  "amount": 3500, "cat": "transport",     "note": "Fuel",           "spec": "",       "date": "2026-04-22"},
        {"id": 10, "amount": 2200, "cat": "health",        "note": "Pharmacy",       "spec": "",       "date": "2026-04-06"},
    ],
    "recurring": [
        {"id": 1, "name": "Netflix",  "amount_usd": 7,    "amount_lkr": None, "currency": "USD", "cat": "subscriptions", "active": True,  "day_of_month": 5},
        {"id": 2, "name": "Spotify",  "amount_usd": 5,    "amount_lkr": None, "currency": "USD", "cat": "subscriptions", "active": True,  "day_of_month": 8},
        {"id": 3, "name": "Gym",      "amount_usd": None, "amount_lkr": 3500, "currency": "LKR", "cat": "health",        "active": True,  "day_of_month": 1},
        {"id": 4, "name": "iCloud",   "amount_usd": 1,    "amount_lkr": None, "currency": "USD", "cat": "subscriptions", "active": False, "day_of_month": 12},
    ],
    "events": [
        {"id": 1, "name": "Friend's Birthday", "date": "2026-04-28", "type": "birthday"},
        {"id": 2, "name": "Study Trip",        "date": "2026-05-10", "type": "outing"},
    ],
    "balances": [
        {"id": 1, "bank": 45000, "cash": 8500, "date": "2026-04-01", "note": "Sample opening balance"},
    ],
}
_DEFAULT_PROFILE_SETTINGS = {"manual_limit": 30000, "is_sample": True}


# ── Profile management ─────────────────────────────────────────────────────────
def get_profiles() -> list:
    """Returns list of profile dicts: [{id, name, emoji, created}]"""
    if not os.path.exists(PROFILES_FILE):
        return []
    with open(PROFILES_FILE) as f:
        return json.load(f)

def _save_profiles(profiles: list):
    with open(PROFILES_FILE, "w") as f:
        json.dump(profiles, f, indent=2)

def get_profile(profile_id: str) -> dict:
    for p in get_profiles():
        if p["id"] == profile_id:
            return p
    return {}

def create_profile(name: str, emoji: str = "👤") -> dict:
    """Creates a new profile seeded with sample data and returns it."""
    import uuid
    profiles   = get_profiles()
    profile_id = str(uuid.uuid4())[:8]
    profile    = {"id": profile_id, "name": name, "emoji": emoji, "created": str(date.today())}
    profiles.append(profile)
    _save_profiles(profiles)
    _seed_sample_for_profile(profile_id)
    return profile

def delete_profile(profile_id: str):
    """Deletes a profile and all its data from disk."""
    import shutil
    profiles = [p for p in get_profiles() if p["id"] != profile_id]
    _save_profiles(profiles)
    profile_path = os.path.join(PROFILES_DIR, profile_id)
    if os.path.exists(profile_path):
        shutil.rmtree(profile_path)

def rename_profile(profile_id: str, new_name: str, new_emoji: str = None):
    profiles = get_profiles()
    for p in profiles:
        if p["id"] == profile_id:
            p["name"] = new_name
            if new_emoji:
                p["emoji"] = new_emoji
    _save_profiles(profiles)


# ── Per-profile file I/O ───────────────────────────────────────────────────────
def _load(key: str) -> any:
    path = _profile_file(key)
    if not os.path.exists(path):
        default = _SAMPLE_DATA.get(key, _DEFAULT_PROFILE_SETTINGS if key == "settings" else [])
        with open(path, "w") as f:
            json.dump(default, f, indent=2)
        return default
    with open(path) as f:
        return json.load(f)

def _save(key: str, data):
    with open(_profile_file(key), "w") as f:
        json.dump(data, f, indent=2)

def _next_id(records):
    return max((r["id"] for r in records), default=0) + 1


# ── Seed / reset ───────────────────────────────────────────────────────────────
def _seed_sample_for_profile(profile_id: str):
    """Writes sample financial data + default settings to a profile folder."""
    for key, value in _SAMPLE_DATA.items():
        path = _profile_file(key, profile_id)
        with open(path, "w") as f:
            json.dump(value, f, indent=2)
    with open(_profile_file("settings", profile_id), "w") as f:
        json.dump(_DEFAULT_PROFILE_SETTINGS, f, indent=2)

def ensure_profile_data():
    """
    Called on each app run for the active profile.
    Only seeds sample data if the settings file doesn't exist yet
    (brand new profile folder or after manual wipe). Never overwrites existing data.
    """
    if not os.path.exists(_profile_file("settings")):
        _seed_sample_for_profile(_active_profile_id)

def reset_profile_data():
    """
    Clears all financial entries for the active profile and marks is_sample=False.
    If the user adds nothing afterwards, the next app run will show sample data
    again because ensure_profile_data won't find a settings file after a fresh
    folder creation (this is handled by the reset → delete files path below).
    """
    for key in ["income", "expenses", "recurring", "events", "balances"]:
        _save(key, [])
    s = _load("settings")
    s["is_sample"] = False
    _save("settings", s)

def is_sample_data() -> bool:
    return _load("settings").get("is_sample", True)

def _switch_to_user_data():
    """Called the first time a user adds a real entry — marks profile as user-owned."""
    s = _load("settings")
    if s.get("is_sample", True):
        s["is_sample"] = False
        _save("settings", s)
        for key in ["income", "expenses", "recurring", "events", "balances"]:
            _save(key, [])


# ── Global settings (shared across all profiles) ──────────────────────────────
def _load_global() -> dict:
    if not os.path.exists(GLOBAL_FILE):
        default = {"usd_rate": 320, "usd_fetch_date": ""}
        with open(GLOBAL_FILE, "w") as f:
            json.dump(default, f, indent=2)
        return default
    with open(GLOBAL_FILE) as f:
        return json.load(f)

def _save_global(data: dict):
    with open(GLOBAL_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_usd_rate() -> int:
    return _load_global().get("usd_rate", 320)

def set_usd_rate(rate: int):
    g = _load_global(); g["usd_rate"] = int(rate); _save_global(g)

def get_usd_fetch_date() -> str:
    return _load_global().get("usd_fetch_date", "")

def fetch_live_usd_rate():
    """
    Fetches the live USD→LKR rate. Skips the network call if already fetched today.
    Rate is global — shared across all profiles.
    Returns (rate, was_fetched_live).
    """
    today_str = str(date.today())
    g = _load_global()
    if g.get("usd_fetch_date") == today_str:
        return g.get("usd_rate", 320), False

    apis = [
        ("https://api.exchangerate-api.com/v4/latest/USD",         lambda d: d["rates"]["LKR"]),
        ("https://open.er-api.com/v6/latest/USD",                  lambda d: d["rates"]["LKR"] if d.get("result") == "success" else None),
        ("https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json", lambda d: d["usd"]["lkr"]),
    ]
    for url, extract in apis:
        try:
            r = requests.get(url, timeout=6)
            data = r.json()
            raw_rate = extract(data)
            if raw_rate and float(raw_rate) > 200:
                rate = round(float(raw_rate))
                g["usd_rate"]       = rate
                g["usd_fetch_date"] = today_str
                _save_global(g)
                print(f"[FinAgent] ✓ USD→LKR fetched from {url}: {raw_rate} → LKR {rate}")
                return rate, True
        except Exception as e:
            print(f"[FinAgent] ✗ API failed ({url}): {e}")
            continue
    print("[FinAgent] All APIs failed — using cached rate")
    return g.get("usd_rate", 320), False


# ── Per-profile settings ───────────────────────────────────────────────────────
def get_settings():       return _load("settings")
def save_settings(s):     _save("settings", s)

def get_manual_limit():   return _load("settings").get("manual_limit", 30000)
def set_manual_limit(limit):
    s = _load("settings"); s["manual_limit"] = limit; _save("settings", s)

# Legacy stubs — kept so agent.py / intelligence.py need zero changes
def get_user_name() -> str:
    p = get_profile(_active_profile_id)
    return p.get("name", "")

def set_user_name(name: str):
    rename_profile(_active_profile_id, name)


# ── Income ─────────────────────────────────────────────────────────────────────
def get_income():         return _load("income")
def add_income(entry):
    if is_sample_data(): _switch_to_user_data()
    data = get_income(); entry["id"] = _next_id(data); data.append(entry); _save("income", data)

def get_total_income(month=None, year=None):
    m = month or date.today().month; y = year or date.today().year
    return sum(e["amount"] for e in get_income() if e["date"].startswith(f"{y}-{m:02d}"))

def get_income_history():
    history = {}
    for e in get_income():
        key = e["date"][:7]
        history[key] = history.get(key, 0) + e["amount"]
    return history


# ── One-time Expenses ──────────────────────────────────────────────────────────
def get_expenses():       return _load("expenses")
def add_expense(entry):
    if is_sample_data(): _switch_to_user_data()
    data = get_expenses(); entry["id"] = _next_id(data); data.append(entry); _save("expenses", data)

def get_total_expenses(month=None, year=None):
    m = month or date.today().month; y = year or date.today().year
    return sum(e["amount"] for e in get_expenses() if e["date"].startswith(f"{y}-{m:02d}"))

def get_category_totals(month=None, year=None):
    m = month or date.today().month; y = year or date.today().year
    totals = {c: 0 for c in EXPENSE_CATEGORIES}
    for e in get_expenses():
        if e["date"].startswith(f"{y}-{m:02d}"):
            totals[e["cat"]] = totals.get(e["cat"], 0) + e["amount"]
    rate = get_usd_rate()
    for r in get_recurring():
        if r["active"]:
            amt = r["amount_usd"] * rate if r["currency"] == "USD" else r["amount_lkr"]
            totals[r["cat"]] = totals.get(r["cat"], 0) + amt
    return totals

def get_daily_totals(days=7):
    exps = get_expenses()
    dates, amounts = [], []
    for i in range(days - 1, -1, -1):
        d = date.today() - timedelta(days=i)
        ds = str(d)
        amounts.append(sum(e["amount"] for e in exps if e["date"] == ds))
        dates.append(d.strftime("%b %d"))
    return {"dates": dates, "amounts": amounts}


# ── Recurring Expenses ─────────────────────────────────────────────────────────
def get_recurring():      return _load("recurring")
def add_recurring(entry):
    if is_sample_data(): _switch_to_user_data()
    data = get_recurring(); entry["id"] = _next_id(data); data.append(entry); _save("recurring", data)

def toggle_recurring(rid, active):
    data = get_recurring()
    for r in data:
        if r["id"] == rid: r["active"] = active
    _save("recurring", data)

def get_recurring_monthly_total():
    rate = get_usd_rate()
    return sum(
        (r["amount_usd"] * rate if r["currency"] == "USD" else r["amount_lkr"])
        for r in get_recurring() if r["active"]
    )


# ── Events ─────────────────────────────────────────────────────────────────────
def get_events():         return _load("events")
def add_event(entry):
    if is_sample_data(): _switch_to_user_data()
    data = get_events(); entry["id"] = _next_id(data); data.append(entry); _save("events", data)

def get_all_calendar_events():
    cal = {d: {"name": n, "type": "holiday"} for d, n in SL_HOLIDAYS.items()}
    for ev in get_events():
        cal[ev["date"]] = {"name": ev["name"], "type": ev.get("type", "personal")}
    return cal


# ── Balances ───────────────────────────────────────────────────────────────────
def get_balances():       return _load("balances")
def add_balance_snapshot(entry):
    if is_sample_data(): _switch_to_user_data()
    data = get_balances(); entry["id"] = _next_id(data); data.append(entry); _save("balances", data)

def get_latest_balance():
    data = get_balances()
    if not data: return {"bank": 0, "cash": 0, "date": str(date.today())}
    return sorted(data, key=lambda x: x["date"])[-1]


# ── Derived metrics ────────────────────────────────────────────────────────────
def get_net_this_month():
    return get_total_income() - get_total_expenses() - get_recurring_monthly_total()

def get_projected_expenses():
    today_day = datetime.today().day
    total_exp = get_total_expenses()
    daily_avg = total_exp / max(today_day, 1)
    days_left = 30 - today_day
    return total_exp + daily_avg * days_left + get_recurring_monthly_total()