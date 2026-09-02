"""
modules/finance.py
DAN Automation Agent — Finance module

Features:
- convert <amount> <from> <to>   -> currency conversion (ExchangeRate-API, free)
- dollar <amount>                 -> quick USD -> NGN shortcut
- crypto <coin>                   -> live price in USD (CoinGecko, free, no key)
- budget                          -> show current budget summary
- income <amount> [note]          -> add income
- expense <amount> [note]         -> add expense
- expenses                        -> list recent expenses

Follows the same conventions as the other modules:
- Each public function takes the raw command text (after the keyword) and
  the shared APP_DATA dict, and returns a plain string reply for the chat bubble.
- Network functions fail soft: on any error they return a friendly
  message instead of raising.
- Budget/expense data persists in APP_DATA['budget'] and is saved to
  dan_data.json by main.py's existing save routine (call save_data(APP_DATA)
  after any function that mutates APP_DATA — wire that in from parser.py
  the same way personal.py's task/note functions will).

Requires: requests
"""

import requests
from datetime import datetime

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
# ExchangeRate-API free tier needs a key: https://www.exchangerate-api.com
EXCHANGERATE_API_KEY = ""

REQUEST_TIMEOUT = 10

# CoinGecko free API needs no key. Add more coins here as needed.
COINGECKO_IDS = {
    "btc": "bitcoin", "bitcoin": "bitcoin",
    "eth": "ethereum", "ethereum": "ethereum",
    "usdt": "tether", "tether": "tether",
    "bnb": "binancecoin",
    "sol": "solana", "solana": "solana",
    "doge": "dogecoin", "dogecoin": "dogecoin",
    "xrp": "ripple", "ripple": "ripple",
}


# ---------------------------------------------------------------------------
# BUDGET DATA HELPERS
# ---------------------------------------------------------------------------
def _ensure_budget(APP_DATA):
    """Make sure APP_DATA['budget'] has the shape we expect."""
    if "budget" not in APP_DATA or not isinstance(APP_DATA["budget"], dict):
        APP_DATA["budget"] = {"income": 0, "expenses": 0, "log": []}
    APP_DATA["budget"].setdefault("income", 0)
    APP_DATA["budget"].setdefault("expenses", 0)
    APP_DATA["budget"].setdefault("log", [])
    return APP_DATA["budget"]


def _parse_amount_and_note(text):
    """'5000 groceries' -> (5000.0, 'groceries'); '5000' -> (5000.0, '')"""
    parts = text.strip().split(" ", 1)
    try:
        amount = float(parts[0].replace(",", ""))
    except (ValueError, IndexError):
        return None, ""
    note = parts[1].strip() if len(parts) > 1 else ""
    return amount, note


# ---------------------------------------------------------------------------
# CURRENCY CONVERSION
# ---------------------------------------------------------------------------
def convert_currency(command_text, APP_DATA):
    """Expected: '<amount> <from_code> <to_code>' e.g. 'convert 100 usd ngn'"""
    parts = command_text.strip().split()
    if len(parts) < 3:
        return "Usage: convert <amount> <from> <to> — e.g. 'convert 100 usd ngn'."

    try:
        amount = float(parts[0].replace(",", ""))
    except ValueError:
        return "That doesn't look like a valid amount."

    from_code, to_code = parts[1].upper(), parts[2].upper()

    if not EXCHANGERATE_API_KEY:
        return "Currency conversion isn't set up yet — add your free ExchangeRate-API key in finance.py."

    try:
        url = f"https://v6.exchangerate-api.com/v6/{EXCHANGERATE_API_KEY}/pair/{from_code}/{to_code}/{amount}"
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()

        if data.get("result") != "success":
            return f"Couldn't convert {from_code} to {to_code} — check the currency codes."

        converted = data.get("conversion_result")
        rate = data.get("conversion_rate")
        return f"{amount:,.2f} {from_code} = {converted:,.2f} {to_code} (rate: {rate})"
    except requests.exceptions.RequestException:
        return "Couldn't reach the currency service — check your connection and try again."


def dollar_to_naira(command_text, APP_DATA):
    """Shortcut: 'dollar 50' -> converts 50 USD to NGN."""
    amount_text = command_text.strip()
    if not amount_text:
        return "Give me an amount — e.g. 'dollar 50'."
    return convert_currency(f"{amount_text} usd ngn", APP_DATA)


# ---------------------------------------------------------------------------
# CRYPTO PRICES
# ---------------------------------------------------------------------------
def get_crypto_price(coin_text, APP_DATA):
    coin_text = coin_text.strip().lower()
    if not coin_text:
        return "Which coin? e.g. 'crypto btc' or 'crypto solana'."

    coin_id = COINGECKO_IDS.get(coin_text, coin_text)

    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": coin_id, "vs_currencies": "usd", "include_24hr_change": "true"}
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()

        if coin_id not in data:
            return f"Couldn't find a coin called '{coin_text}'. Try 'btc', 'eth', 'sol', etc."

        price = data[coin_id]["usd"]
        change = data[coin_id].get("usd_24h_change", 0)
        arrow = "up" if change >= 0 else "down"

        return f"{coin_text.upper()}: ${price:,.2f} ({arrow} {abs(change):.2f}% in 24h)"
    except requests.exceptions.RequestException:
        return "Couldn't reach the crypto price service — check your connection and try again."


# ---------------------------------------------------------------------------
# BUDGET TRACKER
# ---------------------------------------------------------------------------
def add_income(command_text, APP_DATA):
    amount, note = _parse_amount_and_note(command_text)
    if amount is None:
        return "Usage: income <amount> [note] — e.g. 'income 50000 salary'."

    budget = _ensure_budget(APP_DATA)
    budget["income"] += amount
    budget["log"].append({
        "type": "income",
        "amount": amount,
        "note": note,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })

    balance = budget["income"] - budget["expenses"]
    note_txt = f" ({note})" if note else ""
    return f"Added income of {amount:,.2f}{note_txt}. Current balance: {balance:,.2f}."


def add_expense(command_text, APP_DATA):
    amount, note = _parse_amount_and_note(command_text)
    if amount is None:
        return "Usage: expense <amount> [note] — e.g. 'expense 2000 transport'."

    budget = _ensure_budget(APP_DATA)
    budget["expenses"] += amount
    budget["log"].append({
        "type": "expense",
        "amount": amount,
        "note": note,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })

    balance = budget["income"] - budget["expenses"]
    note_txt = f" ({note})" if note else ""
    return f"Logged expense of {amount:,.2f}{note_txt}. Current balance: {balance:,.2f}."


def show_budget(command_text, APP_DATA):
    budget = _ensure_budget(APP_DATA)
    income = budget["income"]
    expenses = budget["expenses"]
    balance = income - expenses

    return (
        f"Budget summary:\n"
        f"Income: {income:,.2f}\n"
        f"Expenses: {expenses:,.2f}\n"
        f"Balance: {balance:,.2f}"
    )


def show_expenses(command_text, APP_DATA):
    budget = _ensure_budget(APP_DATA)
    entries = [e for e in budget["log"] if e["type"] == "expense"]

    if not entries:
        return "No expenses logged yet."

    recent = entries[-5:][::-1]
    lines = ["Recent expenses:"]
    for e in recent:
        note_txt = f" — {e['note']}" if e["note"] else ""
        lines.append(f"{e['date']}: {e['amount']:,.2f}{note_txt}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ROUTER — called from modules/parser.py
# ---------------------------------------------------------------------------
def handle(keyword, rest, APP_DATA):
    """
    keyword: first word of the command (e.g. 'convert', 'dollar', 'crypto',
             'budget', 'income', 'expense', 'expenses')
    rest:    everything after the keyword, as typed by the user
    APP_DATA: shared app state dict from main.py

    Returns a reply string, or None if this module doesn't handle the keyword.
    NOTE: parser.py should call save_data(APP_DATA) after any call that
    mutates state (income, expense) — same as it does for other modules.
    """
    keyword = keyword.lower().strip()

    if keyword == "convert":
        return convert_currency(rest, APP_DATA)
    elif keyword == "dollar":
        return dollar_to_naira(rest, APP_DATA)
    elif keyword == "crypto":
        return get_crypto_price(rest, APP_DATA)
    elif keyword == "budget":
        return show_budget(rest, APP_DATA)
    elif keyword == "income":
        return add_income(rest, APP_DATA)
    elif keyword == "expense":
        return add_expense(rest, APP_DATA)
    elif keyword == "expenses":
        return show_expenses(rest, APP_DATA)

    return None
