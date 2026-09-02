"""
modules/location.py
DAN Automation Agent — Location module

Features:
- markspot <name>       -> save current GPS location under a name
- spots                  -> show all saved spots
- delspot <number>       -> delete a saved spot
- whereami                -> show current location (and log it to history)
- locationhistory [count] -> show last N location log entries (default 5)
- remindatspot <name> <message>  -> placeholder: saves an intent to notify
                                     when near a spot (real geofencing needs
                                     a background service — see note below)

Follows the same conventions as the other modules:
- Each public function takes the raw command text (after the keyword) and
  the shared APP_DATA dict, and returns a plain string reply for the chat bubble.
- Uses Termux:API's termux-location for GPS. No external network APIs.
- Uses existing/new APP_DATA keys: spots (list), location_history (list).
  'spots' was already listed in main.py's APP_DATA; location_history is
  new and this module creates it on first use.
- parser.py should call save_data(APP_DATA) after any state-mutating call
  (markspot, delspot, whereami, remindatspot).

NOTE ON GEOFENCING: 'remindatspot' currently just stores the request —
Termux/Kivy has no built-in background geofence listener. True "notify me
when I'm near X" needs a persistent background service checking
termux-location on a timer (best wired up later in automation.py, e.g. a
cron job that runs every few minutes and compares location to saved spots).
For now this function is a placeholder that saves the intent so it's ready
to hook up once that scheduler exists.
"""

import subprocess
import json
from datetime import datetime


REQUEST_TIMEOUT = 20  # GPS fix can take a few seconds, give it room


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


def _get_gps_fix():
    """
    Calls termux-location and returns (lat, lon) or (None, None) on failure.
    Tries GPS first, then falls back to network-based location if GPS
    doesn't get a fix quickly (e.g. indoors).
    """
    for provider in ("gps", "network"):
        try:
            result = subprocess.run(
                f"termux-location -p {provider} -r once",
                shell=True,
                capture_output=True,
                text=True,
                timeout=REQUEST_TIMEOUT,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                lat, lon = data.get("latitude"), data.get("longitude")
                if lat is not None and lon is not None:
                    return lat, lon
        except (subprocess.SubprocessError, json.JSONDecodeError, ValueError):
            continue
    return None, None


# ---------------------------------------------------------------------------
# MARK / SHOW / DELETE SPOTS
# ---------------------------------------------------------------------------
def mark_spot(text, APP_DATA):
    name = text.strip()
    if not name:
        return "What should I call this spot? e.g. 'markspot home'."

    lat, lon = _get_gps_fix()
    if lat is None:
        return (
            "Couldn't get a GPS fix. This is usually a permission issue, not a bug: "
            "open your phone's Settings → Apps → Termux:API → Permissions → Location, "
            "and set it to Allowed. Then also make sure Location is turned on in your "
            "phone's quick settings, and try again."
        )

    spots = _ensure_list(APP_DATA, "spots")
    spots.append({
        "name": name,
        "lat": lat,
        "lon": lon,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    return f"Saved spot '{name}' at {lat:.5f}, {lon:.5f}."


def show_spots(text, APP_DATA):
    spots = _ensure_list(APP_DATA, "spots")
    if not spots:
        return "No spots saved yet. Try 'markspot home' while you're there."

    lines = ["Saved spots:"]
    for i, s in enumerate(spots, 1):
        lines.append(f"{i}. {s.get('name', '')} — {s.get('lat', 0):.5f}, {s.get('lon', 0):.5f}")
    return "\n".join(lines)


def delete_spot(text, APP_DATA):
    spots = _ensure_list(APP_DATA, "spots")
    idx = _parse_index(text, len(spots))
    if idx is None:
        return "Usage: delspot <spot number> — check 'spots' for the numbers."

    removed = spots.pop(idx)
    return f"Deleted spot: {removed['name']}"


# ---------------------------------------------------------------------------
# WHERE AM I / HISTORY
# ---------------------------------------------------------------------------
def where_am_i(text, APP_DATA):
    lat, lon = _get_gps_fix()
    if lat is None:
        return (
            "Couldn't get a GPS fix. This is usually a permission issue, not a bug: "
            "open your phone's Settings → Apps → Termux:API → Permissions → Location, "
            "and set it to Allowed. Then also make sure Location is turned on in your "
            "phone's quick settings, and try again."
        )

    history = _ensure_list(APP_DATA, "location_history")
    history.append({
        "lat": lat,
        "lon": lon,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })

    return f"Current location: {lat:.5f}, {lon:.5f}"


def show_location_history(text, APP_DATA):
    history = _ensure_list(APP_DATA, "location_history")
    if not history:
        return "No location history yet. Try 'whereami' to log your current spot."

    text = text.strip()
    count = 5
    if text.isdigit():
        count = int(text)

    recent = history[-count:][::-1]
    lines = ["Location history:"]
    for h in recent:
        lines.append(f"{h.get('date', '')}: {h.get('lat', 0):.5f}, {h.get('lon', 0):.5f}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# REMIND AT SPOT (placeholder — see note at top of file)
# ---------------------------------------------------------------------------
def remind_at_spot(text, APP_DATA):
    """Expected: '<spot name> <message>' e.g. 'remindatspot market buy tomatoes'"""
    parts = text.strip().split(" ", 1)
    if len(parts) < 2:
        return "Usage: remindatspot <spot name> <message> — e.g. 'remindatspot market buy tomatoes'."

    spot_name, message = parts[0].strip(), parts[1].strip()

    spots = _ensure_list(APP_DATA, "spots")
    if not any(s.get("name", "").lower() == spot_name.lower() for s in spots):
        return f"No spot called '{spot_name}' — save it first with 'markspot {spot_name}'."

    reminders = APP_DATA.setdefault("spot_reminders", [])
    reminders.append({"spot": spot_name, "message": message})

    return (
        f"Saved: remind me '{message}' near '{spot_name}'. "
        f"Heads up — this needs the background location checker from automation.py "
        f"to actually trigger; for now it's just stored and ready."
    )


# ---------------------------------------------------------------------------
# ROUTER — called from modules/parser.py
# ---------------------------------------------------------------------------
def handle(keyword, rest, APP_DATA):
    """
    keyword: first word of the command (e.g. 'markspot', 'spots', 'delspot',
             'whereami', 'locationhistory', 'remindatspot')
    rest:    everything after the keyword, as typed by the user
    APP_DATA: shared app state dict from main.py

    Returns a reply string, or None if this module doesn't handle the keyword.
    NOTE: parser.py should call save_data(APP_DATA) after any state-mutating
    call (markspot, delspot, whereami, remindatspot).
    """
    keyword = keyword.lower().strip()

    if keyword == "markspot":
        return mark_spot(rest, APP_DATA)
    elif keyword == "spots":
        return show_spots(rest, APP_DATA)
    elif keyword == "delspot":
        return delete_spot(rest, APP_DATA)
    elif keyword == "whereami":
        return where_am_i(rest, APP_DATA)
    elif keyword == "locationhistory":
        return show_location_history(rest, APP_DATA)
    elif keyword == "remindatspot":
        return remind_at_spot(rest, APP_DATA)

    return None
