"""
modules/automation.py
DAN Automation Agent — Automation module

Features:
- setbriefing <HH:MM>    -> schedule a daily morning briefing notification
- briefingtime             -> show the currently set briefing time
- stopbriefing              -> cancel the daily briefing
- monitor <url>             -> start monitoring a site for uptime
- monitored                 -> show all monitored sites and last known status
- stopmonitor <number>       -> stop monitoring a site
- checksites                 -> manually check all monitored sites right now

Follows the same conventions as the other modules:
- Each public function takes the raw command text (after the keyword) and
  the shared APP_DATA dict, and returns a plain string reply for the chat bubble.
- Uses existing APP_DATA keys: briefing_time (string), monitored_sites (list).
- parser.py should call save_data(APP_DATA) after any state-mutating call
  (setbriefing, stopbriefing, monitor, stopmonitor).

SCHEDULING NOTE (important):
Kivy apps aren't kept alive in the background by default, so true
"runs every day even when the app is closed" scheduling needs OS-level
help. Two practical options on your setup:
  1. Termux:Widget + Termux:Boot — a shortcut script that runs
     termux-notification, triggered by a daily `at`/`cron` job (needs
     `pkg install at cronie`, then `sv-enable atd`/`sv-enable crond`).
  2. A cron entry added via `crontab -e` in Termux that calls a small
     shell script (which this module can generate) at the set time.
This module schedules using `at` for the *next* occurrence (same pattern
as health.py's medicine reminders) — good enough for a single day. For a
truly recurring daily job, re-run 'setbriefing' each morning, or install
cronie and add a proper crontab entry (this module logs the exact cron
line you'd need, so it's copy-paste ready once cronie is set up).

URL monitoring uses plain `requests` — no external monitoring service,
so it only checks when the app is open and 'checksites' or a scheduled
check is triggered (same background-limitation as above applies to any
"auto-check every hour" feature; for now 'checksites' is manual/on-demand).
"""

import subprocess
import requests
from datetime import datetime, timedelta

REQUEST_TIMEOUT = 10


# ---------------------------------------------------------------------------
# DATA HELPERS
# ---------------------------------------------------------------------------
def _ensure_list(APP_DATA, key):
    if key not in APP_DATA or not isinstance(APP_DATA[key], list):
        APP_DATA[key] = []
    return APP_DATA[key]


def _parse_index(text, list_len):
    text = text.strip()
    if not text.isdigit():
        return None
    idx = int(text) - 1
    if idx < 0 or idx >= list_len:
        return None
    return idx


# ---------------------------------------------------------------------------
# DAILY BRIEFING
# ---------------------------------------------------------------------------
def set_briefing(text, APP_DATA):
    time_str = text.strip()
    try:
        target_time = datetime.strptime(time_str, "%H:%M")
    except ValueError:
        return "Use 24-hour HH:MM format — e.g. 'setbriefing 07:00'."

    now = datetime.now()
    scheduled = now.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)
    if scheduled <= now:
        scheduled += timedelta(days=1)

    at_time_str = scheduled.strftime("%H:%M")
    notify_cmd = (
        'termux-notification --title "Good Morning" '
        '--content "Here\'s your daily briefing — open DAN to see it."'
    )

    try:
        result = subprocess.run(
            f'echo \'{notify_cmd}\' | at {at_time_str}',
            shell=True,
            capture_output=True,
            text=True,
            timeout=REQUEST_TIMEOUT,
        )
        if result.returncode != 0:
            return (
                "Couldn't schedule the briefing — install the 'at' package first: "
                "pkg install at, then sv-enable atd."
            )
    except (subprocess.SubprocessError, FileNotFoundError):
        return "Couldn't schedule the briefing — install the 'at' package first: pkg install at"

    APP_DATA["briefing_time"] = time_str

    cron_line = f"{target_time.minute} {target_time.hour} * * * termux-notification --title 'Good Morning' --content 'Here is your daily briefing'"

    return (
        f"Briefing scheduled for {time_str} (next: {scheduled.strftime('%Y-%m-%d %H:%M')}). "
        f"Note: this fires once. For a repeating daily briefing, install cronie "
        f"(pkg install cronie && sv-enable crond) and add this line via crontab -e:\n{cron_line}"
    )


def show_briefing_time(text, APP_DATA):
    briefing_time = APP_DATA.get("briefing_time")
    if not briefing_time:
        return "No briefing time set. Try 'setbriefing 07:00'."
    return f"Daily briefing is set for {briefing_time}."


def stop_briefing(text, APP_DATA):
    if not APP_DATA.get("briefing_time"):
        return "No briefing is currently scheduled."

    APP_DATA["briefing_time"] = None
    return (
        "Briefing time cleared. Note: if you'd already set up a recurring cron job, "
        "you'll need to remove it manually with 'crontab -e'."
    )


# ---------------------------------------------------------------------------
# URL MONITORING
# ---------------------------------------------------------------------------
def monitor_url(text, APP_DATA):
    url = text.strip()
    if not url:
        return "Usage: monitor <url> — e.g. 'monitor https://example.com'."

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    sites = _ensure_list(APP_DATA, "monitored_sites")
    if any(s.get("url") == url for s in sites):
        return f"Already monitoring {url}."

    status, code = _check_site(url)

    sites.append({
        "url": url,
        "status": status,
        "last_checked": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status_code": code,
    })

    return f"Now monitoring {url}. Current status: {status}."


def _check_site(url):
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        if r.status_code < 400:
            return "up", r.status_code
        return "down", r.status_code
    except requests.exceptions.RequestException:
        return "unreachable", None


def show_monitored_sites(text, APP_DATA):
    sites = _ensure_list(APP_DATA, "monitored_sites")
    if not sites:
        return "Not monitoring any sites yet. Try 'monitor https://example.com'."

    lines = ["Monitored sites:"]
    for i, s in enumerate(sites, 1):
        lines.append(
            f"{i}. {s.get('url', '')} — {s.get('status', 'unknown')} "
            f"(checked {s.get('last_checked', 'never')})"
        )
    return "\n".join(lines)


def stop_monitoring(text, APP_DATA):
    sites = _ensure_list(APP_DATA, "monitored_sites")
    idx = _parse_index(text, len(sites))
    if idx is None:
        return "Usage: stopmonitor <number> — check 'monitored' for the numbers."

    removed = sites.pop(idx)
    return f"Stopped monitoring: {removed.get('url', '')}"


def check_sites_now(text, APP_DATA):
    sites = _ensure_list(APP_DATA, "monitored_sites")
    if not sites:
        return "Not monitoring any sites yet. Try 'monitor https://example.com'."

    lines = ["Checked now:"]
    for s in sites:
        status, code = _check_site(s.get("url", ""))
        s["status"] = status
        s["status_code"] = code
        s["last_checked"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines.append(f"{s.get('url', '')} — {status}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ROUTER — called from modules/parser.py
# ---------------------------------------------------------------------------
def handle(keyword, rest, APP_DATA):
    """
    keyword: first word of the command (e.g. 'setbriefing', 'briefingtime',
             'stopbriefing', 'monitor', 'monitored', 'stopmonitor',
             'checksites')
    rest:    everything after the keyword, as typed by the user
    APP_DATA: shared app state dict from main.py

    Returns a reply string, or None if this module doesn't handle the keyword.
    NOTE: parser.py should call save_data(APP_DATA) after any state-mutating
    call (setbriefing, stopbriefing, monitor, stopmonitor, checksites).
    """
    keyword = keyword.lower().strip()

    if keyword == "setbriefing":
        return set_briefing(rest, APP_DATA)
    elif keyword == "briefingtime":
        return show_briefing_time(rest, APP_DATA)
    elif keyword == "stopbriefing":
        return stop_briefing(rest, APP_DATA)
    elif keyword == "monitor":
        return monitor_url(rest, APP_DATA)
    elif keyword == "monitored":
        return show_monitored_sites(rest, APP_DATA)
    elif keyword == "stopmonitor":
        return stop_monitoring(rest, APP_DATA)
    elif keyword == "checksites":
        return check_sites_now(rest, APP_DATA)

    return None
