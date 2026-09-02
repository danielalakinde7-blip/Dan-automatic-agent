"""
modules/timemod.py
DAN Automation Agent — Time module

Features:
- remindme <minutes> <message>  -> notification reminder in X minutes
- timer <minutes>                 -> simple countdown timer notification
- pomodoro                        -> start a 25-min work / 5-min break cycle
- focus <minutes>                  -> enable Do Not Disturb for X minutes, auto-off after
- countdown <YYYY-MM-DD> <label>   -> days remaining until a date

Follows the same conventions as the other modules:
- Each public function takes the raw command text (after the keyword) and
  the shared APP_DATA dict, and returns a plain string reply for the chat bubble.
- Time-delayed actions (remindme, timer, pomodoro, focus) run as detached
  background shell processes (nohup ... &) so they don't block the Kivy UI
  thread. They fire a termux-notification when the delay is up.
- Requires Termux:API (already installed) for termux-notification and the
  Do Not Disturb toggle (settings put, same pattern as device.py's silent mode).
- No network calls in this module.
"""

import subprocess
from datetime import datetime


REQUEST_TIMEOUT = 5  # for the quick subprocess launch calls, not the delay itself


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _run_background(delay_seconds, notify_title, notify_content):
    """
    Launches a detached background process that sleeps for delay_seconds
    then fires a termux-notification. Returns True if launched OK.
    """
    title = notify_title.replace('"', "'")
    content = notify_content.replace('"', "'")
    cmd = (
        f'nohup sh -c "sleep {int(delay_seconds)} && '
        f'termux-notification --title \\"{title}\\" --content \\"{content}\\"" '
        f'> /dev/null 2>&1 &'
    )
    try:
        subprocess.run(cmd, shell=True, timeout=REQUEST_TIMEOUT)
        return True
    except subprocess.SubprocessError:
        return False


def _parse_minutes(text):
    text = text.strip()
    try:
        minutes = float(text)
        if minutes <= 0:
            return None
        return minutes
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# REMIND ME
# ---------------------------------------------------------------------------
def remind_me(text, APP_DATA):
    """Expected: '<minutes> <message>' e.g. 'remindme 20 check the rice'"""
    parts = text.strip().split(" ", 1)
    if len(parts) < 2:
        return "Usage: remindme <minutes> <message> — e.g. 'remindme 20 check the rice'."

    minutes = _parse_minutes(parts[0])
    message = parts[1].strip()
    if minutes is None:
        return "Give me a valid number of minutes — e.g. 'remindme 20 check the rice'."
    if not message:
        return "What should I remind you about?"

    ok = _run_background(minutes * 60, "Reminder", message)
    if not ok:
        return "Couldn't set that reminder — check Termux:API is installed."

    return f"Got it — I'll remind you about '{message}' in {minutes:g} minute(s)."


# ---------------------------------------------------------------------------
# TIMER
# ---------------------------------------------------------------------------
def start_timer(text, APP_DATA):
    minutes = _parse_minutes(text)
    if minutes is None:
        return "Usage: timer <minutes> — e.g. 'timer 10'."

    ok = _run_background(minutes * 60, "Timer Done", f"Your {minutes:g}-minute timer is up.")
    if not ok:
        return "Couldn't start that timer — check Termux:API is installed."

    return f"Timer started for {minutes:g} minute(s). I'll notify you when it's done."


# ---------------------------------------------------------------------------
# POMODORO
# ---------------------------------------------------------------------------
def start_pomodoro(text, APP_DATA):
    """
    25 min work -> notification -> 5 min break -> notification.
    Both stages scheduled up front as background jobs, work stage first.
    """
    work_minutes, break_minutes = 25, 5

    ok1 = _run_background(
        work_minutes * 60,
        "Pomodoro",
        "Work session done — take a 5 minute break.",
    )
    ok2 = _run_background(
        (work_minutes + break_minutes) * 60,
        "Pomodoro",
        "Break's over — back to work!",
    )

    if not (ok1 and ok2):
        return "Couldn't start the pomodoro — check Termux:API is installed."

    return (
        f"Pomodoro started: {work_minutes} min work, then a {break_minutes} min break. "
        f"I'll notify you at each stage."
    )


# ---------------------------------------------------------------------------
# FOCUS MODE (Do Not Disturb for X minutes)
# ---------------------------------------------------------------------------
def start_focus(text, APP_DATA):
    minutes = _parse_minutes(text)
    if minutes is None:
        return "Usage: focus <minutes> — e.g. 'focus 45'."

    try:
        subprocess.run(
            "settings put global zen_mode 1",
            shell=True,
            timeout=REQUEST_TIMEOUT,
        )
    except subprocess.SubprocessError:
        return "Couldn't enable Do Not Disturb — check Termux has the needed permissions."

    ok = _run_background(
        minutes * 60,
        "Focus Mode Ended",
        f"Your {minutes:g}-minute focus session is over. Notifications are back on.",
    )

    off_cmd = (
        f'nohup sh -c "sleep {int(minutes * 60)} && '
        f'settings put global zen_mode 0" > /dev/null 2>&1 &'
    )
    try:
        subprocess.run(off_cmd, shell=True, timeout=REQUEST_TIMEOUT)
    except subprocess.SubprocessError:
        pass  # DND was still enabled; worst case it stays on until manually turned off

    if not ok:
        return "Focus mode enabled, but couldn't schedule the end notification."

    return f"Focus mode on for {minutes:g} minute(s) — Do Not Disturb enabled. I'll let you know when it ends."


# ---------------------------------------------------------------------------
# COUNTDOWN TO A DATE
# ---------------------------------------------------------------------------
def countdown_to_date(text, APP_DATA):
    """Expected: '<YYYY-MM-DD> <label>' e.g. 'countdown 2026-12-25 Christmas'"""
    parts = text.strip().split(" ", 1)
    if not parts or not parts[0]:
        return "Usage: countdown <YYYY-MM-DD> <label> — e.g. 'countdown 2026-12-25 Christmas'."

    date_str = parts[0].strip()
    label = parts[1].strip() if len(parts) > 1 else "your event"

    try:
        target = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return "Use YYYY-MM-DD format — e.g. 'countdown 2026-12-25 Christmas'."

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    delta = (target - today).days

    if delta > 0:
        return f"{delta} day(s) until {label} ({date_str})."
    elif delta == 0:
        return f"{label} is today!"
    else:
        return f"{label} was {abs(delta)} day(s) ago ({date_str})."


# ---------------------------------------------------------------------------
# ROUTER — called from modules/parser.py
# ---------------------------------------------------------------------------
def handle(keyword, rest, APP_DATA):
    """
    keyword: first word of the command (e.g. 'remindme', 'timer', 'pomodoro',
             'focus', 'countdown')
    rest:    everything after the keyword, as typed by the user
    APP_DATA: shared app state dict from main.py

    Returns a reply string, or None if this module doesn't handle the keyword.
    NOTE: no APP_DATA mutation happens here, so no save_data() call needed
    from parser.py for this module.
    """
    keyword = keyword.lower().strip()

    if keyword == "remindme":
        return remind_me(rest, APP_DATA)
    elif keyword == "timer":
        return start_timer(rest, APP_DATA)
    elif keyword == "pomodoro":
        return start_pomodoro(rest, APP_DATA)
    elif keyword == "focus":
        return start_focus(rest, APP_DATA)
    elif keyword == "countdown":
        return countdown_to_date(rest, APP_DATA)

    return None
