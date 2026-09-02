"""
modules/health.py
DAN Automation Agent — Health module

Features:
- habit <name>              -> add a new habit to track
- habits                     -> show all habits with current streaks
- habitdone <number>         -> mark today's habit as done, updates streak
- delhabit <number>          -> delete a habit
- workout <exercise> <reps>  -> log a workout (e.g. 'workout pushups 30')
- workouts                   -> show recent workout log
- sleep <hours>               -> log hours slept (e.g. 'sleep 7.5')
- sleeplog                    -> show recent sleep log
- medicine <HH:MM> <name>     -> schedule a medicine reminder notification
- meds                        -> show scheduled medicine reminders
- delmed <number>             -> delete a medicine reminder

Follows the same conventions as the other modules:
- Each public function takes the raw command text (after the keyword) and
  the shared APP_DATA dict, and returns a plain string reply for the chat bubble.
- Uses existing APP_DATA keys already defined in main.py: habits, workouts,
  sleep_log, medicine_log — each a list.
- parser.py should call save_data(APP_DATA) after any state-mutating call,
  same as the pattern used elsewhere.
- Medicine reminders use Termux's `at` command to schedule a one-off
  `termux-notification` call. Requires the `at` package:
    pkg install at
  and the atd service running (termux-services + `sv-enable atd`, or just
  `atd` started manually). Falls back to a friendly error if `at` isn't set up.
  NOTE: `at` schedules a ONE-TIME notification for the next occurrence of
  that time (today if still ahead, otherwise tomorrow). For a truly daily
  repeating reminder, re-run the 'medicine' command each day, or later wire
  this into automation.py's cron-based daily briefing scheduler.
"""

import subprocess
from datetime import datetime, timedelta


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


def _today_str():
    return datetime.now().strftime("%Y-%m-%d")


def _yesterday_str():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# HABITS
# ---------------------------------------------------------------------------
def add_habit(text, APP_DATA):
    name = text.strip()
    if not name:
        return "What habit? e.g. 'habit drink water'."

    habits = _ensure_list(APP_DATA, "habits")
    habits.append({"name": name, "streak": 0, "last_done": None})
    return f"Now tracking habit: {name}"


def show_habits(text, APP_DATA):
    habits = _ensure_list(APP_DATA, "habits")
    if not habits:
        return "No habits yet. Add one with 'habit <name>'."

    today = _today_str()
    lines = ["Your habits:"]
    for i, h in enumerate(habits, 1):
        streak = h.get("streak", 0)
        done_today = "done today" if h.get("last_done") == today else "not done today"
        lines.append(f"{i}. {h.get('name', '')} — streak: {streak} ({done_today})")
    return "\n".join(lines)


def mark_habit_done(text, APP_DATA):
    habits = _ensure_list(APP_DATA, "habits")
    idx = _parse_index(text, len(habits))
    if idx is None:
        return "Usage: habitdone <habit number> — check 'habits' for the numbers."

    habit = habits[idx]
    today = _today_str()
    yesterday = _yesterday_str()

    if habit.get("last_done") == today:
        return f"'{habit['name']}' is already marked done for today. Streak: {habit.get('streak', 0)}."

    if habit.get("last_done") == yesterday:
        habit["streak"] = habit.get("streak", 0) + 1
    else:
        habit["streak"] = 1

    habit["last_done"] = today
    return f"'{habit['name']}' marked done. Streak: {habit['streak']} day(s)."


def delete_habit(text, APP_DATA):
    habits = _ensure_list(APP_DATA, "habits")
    idx = _parse_index(text, len(habits))
    if idx is None:
        return "Usage: delhabit <habit number> — check 'habits' for the numbers."

    removed = habits.pop(idx)
    return f"Stopped tracking: {removed['name']}"


# ---------------------------------------------------------------------------
# WORKOUT LOG
# ---------------------------------------------------------------------------
def log_workout(text, APP_DATA):
    """Expected: '<exercise> <reps>' e.g. 'workout pushups 30'"""
    parts = text.strip().rsplit(" ", 1)
    if len(parts) < 2 or not parts[1].isdigit():
        return "Usage: workout <exercise> <reps> — e.g. 'workout pushups 30'."

    exercise, reps = parts[0].strip(), int(parts[1])
    if not exercise:
        return "Usage: workout <exercise> <reps> — e.g. 'workout pushups 30'."

    workouts = _ensure_list(APP_DATA, "workouts")
    workouts.append({
        "exercise": exercise,
        "reps": reps,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    return f"Logged: {exercise} x{reps}"


def show_workouts(text, APP_DATA):
    workouts = _ensure_list(APP_DATA, "workouts")
    if not workouts:
        return "No workouts logged yet. Try 'workout pushups 30'."

    recent = workouts[-5:][::-1]
    lines = ["Recent workouts:"]
    for w in recent:
        lines.append(f"{w.get('date', '')}: {w.get('exercise', '')} x{w.get('reps', 0)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SLEEP LOG
# ---------------------------------------------------------------------------
def log_sleep(text, APP_DATA):
    text = text.strip()
    try:
        hours = float(text)
    except ValueError:
        return "Usage: sleep <hours> — e.g. 'sleep 7.5'."

    if hours < 0 or hours > 24:
        return "That doesn't look like a valid number of hours."

    sleep_log = _ensure_list(APP_DATA, "sleep_log")
    sleep_log.append({
        "hours": hours,
        "date": datetime.now().strftime("%Y-%m-%d"),
    })
    return f"Logged {hours} hours of sleep."


def show_sleep(text, APP_DATA):
    sleep_log = _ensure_list(APP_DATA, "sleep_log")
    if not sleep_log:
        return "No sleep logged yet. Try 'sleep 7.5'."

    recent = sleep_log[-7:][::-1]
    lines = ["Recent sleep log:"]
    for s in recent:
        lines.append(f"{s.get('date', '')}: {s.get('hours', 0)} hrs")

    avg = sum(s.get("hours", 0) for s in sleep_log[-7:]) / len(sleep_log[-7:])
    lines.append(f"7-day average: {avg:.1f} hrs")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MEDICINE REMINDERS
# ---------------------------------------------------------------------------
def add_medicine_reminder(text, APP_DATA):
    """Expected: '<HH:MM> <medicine name>' e.g. 'medicine 08:00 vitamin C'"""
    parts = text.strip().split(" ", 1)
    if len(parts) < 2:
        return "Usage: medicine <HH:MM> <name> — e.g. 'medicine 08:00 vitamin C'."

    time_str, med_name = parts[0].strip(), parts[1].strip()

    try:
        target_time = datetime.strptime(time_str, "%H:%M")
    except ValueError:
        return "Use 24-hour HH:MM format — e.g. 'medicine 20:30 malaria tablet'."

    now = datetime.now()
    scheduled = now.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)
    if scheduled <= now:
        scheduled += timedelta(days=1)

    at_time_str = scheduled.strftime("%H:%M")
    notify_cmd = f'termux-notification --title "Medicine Reminder" --content "Time for: {med_name}"'

    try:
        result = subprocess.run(
            f'echo \'{notify_cmd}\' | at {at_time_str}',
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return (
                "Couldn't schedule that reminder — make sure the 'at' package is installed "
                "and atd is running (pkg install at, then sv-enable atd or start atd manually)."
            )
    except (subprocess.SubprocessError, FileNotFoundError):
        return "Couldn't schedule that reminder — install the 'at' package first: pkg install at"

    medicine_log = _ensure_list(APP_DATA, "medicine_log")
    medicine_log.append({
        "name": med_name,
        "time": time_str,
        "scheduled_for": scheduled.strftime("%Y-%m-%d %H:%M"),
    })

    return f"Reminder set: {med_name} at {time_str} (next: {scheduled.strftime('%Y-%m-%d %H:%M')})."


def show_medicine_reminders(text, APP_DATA):
    medicine_log = _ensure_list(APP_DATA, "medicine_log")
    if not medicine_log:
        return "No medicine reminders set. Try 'medicine 08:00 vitamin C'."

    lines = ["Medicine reminders:"]
    for i, m in enumerate(medicine_log, 1):
        lines.append(f"{i}. {m.get('name', '')} at {m.get('time', '')} (next: {m.get('scheduled_for', '')})")
    return "\n".join(lines)


def delete_medicine_reminder(text, APP_DATA):
    medicine_log = _ensure_list(APP_DATA, "medicine_log")
    idx = _parse_index(text, len(medicine_log))
    if idx is None:
        return "Usage: delmed <reminder number> — check 'meds' for the numbers."

    removed = medicine_log.pop(idx)
    return f"Deleted reminder: {removed['name']} (note: any already-scheduled 'at' job will still fire once)."


# ---------------------------------------------------------------------------
# ROUTER — called from modules/parser.py
# ---------------------------------------------------------------------------
def handle(keyword, rest, APP_DATA):
    """
    keyword: first word of the command (e.g. 'habit', 'habits', 'habitdone',
             'delhabit', 'workout', 'workouts', 'sleep', 'sleeplog',
             'medicine', 'meds', 'delmed')
    rest:    everything after the keyword, as typed by the user
    APP_DATA: shared app state dict from main.py

    Returns a reply string, or None if this module doesn't handle the keyword.
    NOTE: parser.py should call save_data(APP_DATA) after any state-mutating
    call (habit, habitdone, delhabit, workout, sleep, medicine, delmed).
    """
    keyword = keyword.lower().strip()

    if keyword == "habit":
        return add_habit(rest, APP_DATA)
    elif keyword == "habits":
        return show_habits(rest, APP_DATA)
    elif keyword == "habitdone":
        return mark_habit_done(rest, APP_DATA)
    elif keyword == "delhabit":
        return delete_habit(rest, APP_DATA)
    elif keyword == "workout":
        return log_workout(rest, APP_DATA)
    elif keyword == "workouts":
        return show_workouts(rest, APP_DATA)
    elif keyword == "sleep":
        return log_sleep(rest, APP_DATA)
    elif keyword == "sleeplog":
        return show_sleep(rest, APP_DATA)
    elif keyword == "medicine":
        return add_medicine_reminder(rest, APP_DATA)
    elif keyword == "meds":
        return show_medicine_reminders(rest, APP_DATA)
    elif keyword == "delmed":
        return delete_medicine_reminder(rest, APP_DATA)

    return None
