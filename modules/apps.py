"""
modules/apps.py
DAN Automation Agent — Apps module

Features:
- open <app name>          -> launch a known app by name
- installedapps              -> list installed apps (package names)
- settings <screen>          -> jump to an Android settings screen
- navigate <place>            -> open Google Maps directions to a place
- showmap <place>              -> show a place on Google Maps (no directions)
- back / recents                -> navigation shortcuts (may not work — see note)

Follows the same conventions as the other modules:
- Each public function takes the raw command text (after the keyword) and
  the shared APP_DATA dict, and returns a plain string reply for the chat bubble.
- Uses Android intents via "am start ..." for launches (switched from
  "monkey", which needs instrumentation permission that isn't reliably
  available). No network calls, no APP_DATA mutation.
- NOTE: 'back' and 'recents' use raw `input keyevent`, which needs a
  shell/system-level permission a regular Termux process can't get, even
  via ADB. They're kept here but likely won't actually work. 'home' and
  'screenshot' were removed entirely for the same reason — no fix exists
  without root.

NOTE ON PACKAGE NAMES: Android app launches need the actual package name
(e.g. com.whatsapp), not the display name. APP_PACKAGES below maps common
app names to their package IDs. Add more as needed — if an app isn't in
the map, 'open <name>' will say so instead of guessing wrong.
"""

import subprocess

REQUEST_TIMEOUT = 10

APP_PACKAGES = {
    "whatsapp": "com.whatsapp",
    "instagram": "com.instagram.android",
    "facebook": "com.facebook.katana",
    "messenger": "com.facebook.orca",
    "twitter": "com.twitter.android",
    "x": "com.twitter.android",
    "tiktok": "com.zhiliaoapp.musically",
    "telegram": "org.telegram.messenger",
    "snapchat": "com.snapchat.android",
    "chrome": "com.android.chrome",
    "gmail": "com.google.android.gm",
    "maps": "com.google.android.apps.maps",
    "youtube": "com.google.android.youtube",
    "playstore": "com.android.vending",
    "spotify": "com.spotify.music",
    "netflix": "com.netflix.mediaclient",
    "camera": "com.android.camera",
    "gallery": "com.google.android.apps.photos",
    "photos": "com.google.android.apps.photos",
    "calculator": "com.google.android.calculator",
    "calendar": "com.google.android.calendar",
    "clock": "com.google.android.deskclock",
    "contacts": "com.google.android.contacts",
    "phone": "com.google.android.dialer",
    "messages": "com.google.android.apps.messaging",
    "drive": "com.google.android.apps.docs",
    "playmusic": "com.google.android.music",
    "amazon": "com.amazon.mShop.android.shopping",
    "jumia": "com.jumia.android",
    "opay": "team.opay.pay",
    "palmpay": "com.transsnet.palmpay",
    "kuda": "com.kudabank.app",
    "gtbank": "com.gtbank.gtworld",
    "firstbank": "com.firstbank.fbnmobile",
    "zenith": "com.zenithbank.mobile",
    "uba": "com.ubagroup.ubamobile",
    "accessbank": "com.accessbank.accessmore",
    "termux": "com.termux",
}

SETTINGS_SCREENS = {
    "wifi": "android.settings.WIFI_SETTINGS",
    "bluetooth": "android.settings.BLUETOOTH_SETTINGS",
    "battery": "android.settings.BATTERY_SAVER_SETTINGS",
    "display": "android.settings.DISPLAY_SETTINGS",
    "sound": "android.settings.SOUND_SETTINGS",
    "apps": "android.settings.APPLICATION_SETTINGS",
    "storage": "android.settings.INTERNAL_STORAGE_SETTINGS",
    "location": "android.settings.LOCATION_SOURCE_SETTINGS",
    "date": "android.settings.DATE_SETTINGS",
    "security": "android.settings.SECURITY_SETTINGS",
    "accessibility": "android.settings.ACCESSIBILITY_SETTINGS",
    "developer": "android.settings.APPLICATION_DEVELOPMENT_SETTINGS",
    "notifications": "android.settings.APP_NOTIFICATION_SETTINGS",
    "vpn": "android.net.vpn.SETTINGS",
    "general": "android.settings.SETTINGS",
}


def _run(cmd, timeout=REQUEST_TIMEOUT):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.SubprocessError:
        return None


# ---------------------------------------------------------------------------
# OPEN APP
# ---------------------------------------------------------------------------
def open_app(text, APP_DATA):
    name = text.strip().lower()
    if not name:
        return "Which app? e.g. 'open whatsapp'."

    package = APP_PACKAGES.get(name)
    if not package:
        return f"I don't know the package for '{name}' yet — add it to APP_PACKAGES in apps.py."

    result = _run(f"am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -p {package}")
    if result is None or result.returncode != 0:
        return f"Couldn't open {name} — is it installed?"

    return f"Opening {name}..."


def list_installed_apps(text, APP_DATA):
    result = _run("pm list packages -3")
    if result is None:
        return "Couldn't list installed apps — the command failed to run."

    output = result.stdout.strip() if result.stdout else ""
    if not output:
        err = result.stderr.strip() if result and result.stderr else "no output and no error message"
        return f"Couldn't list installed apps ({err})."

    packages = [line.replace("package:", "").strip() for line in output.splitlines() if line.strip()]
    if not packages:
        return "No user-installed apps found."

    packages = packages[:20]
    lines = ["Installed apps (first 20):"] + [f"- {p}" for p in packages]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SETTINGS SCREENS
# ---------------------------------------------------------------------------
def open_settings_screen(text, APP_DATA):
    name = text.strip().lower()
    if not name:
        return "Which settings screen? e.g. 'settings wifi'."

    action = SETTINGS_SCREENS.get(name)
    if not action:
        available = ", ".join(sorted(SETTINGS_SCREENS.keys()))
        return f"Don't know that settings screen. Try one of: {available}"

    result = _run(f"am start -a {action}")
    if result is None or result.returncode != 0:
        return f"Couldn't open {name} settings."

    return f"Opening {name} settings..."


# ---------------------------------------------------------------------------
# MAPS
# ---------------------------------------------------------------------------
def navigate_to(text, APP_DATA):
    place = text.strip()
    if not place:
        return "Where to? e.g. 'navigate Ikeja City Mall'."

    encoded = place.replace(" ", "+")
    cmd = f'am start -a android.intent.action.VIEW -d "google.navigation:q={encoded}"'
    result = _run(cmd)
    if result is None or result.returncode != 0:
        return "Couldn't start navigation — check Google Maps is installed."

    return f"Starting navigation to {place}..."


def show_on_map(text, APP_DATA):
    place = text.strip()
    if not place:
        return "Show what on the map? e.g. 'showmap Lekki Phase 1'."

    encoded = place.replace(" ", "+")
    cmd = f'am start -a android.intent.action.VIEW -d "geo:0,0?q={encoded}"'
    result = _run(cmd)
    if result is None or result.returncode != 0:
        return "Couldn't open the map — check a maps app is installed."

    return f"Showing {place} on the map..."


# ---------------------------------------------------------------------------
# NAVIGATION SHORTCUTS
# ---------------------------------------------------------------------------
def go_back(text, APP_DATA):
    _run("input keyevent 4")
    return "Going back."


def show_recents(text, APP_DATA):
    _run("input keyevent 187")
    return "Showing recent apps."


# ---------------------------------------------------------------------------
# ROUTER — called from modules/parser.py
# ---------------------------------------------------------------------------
def handle(keyword, rest, APP_DATA):
    """
    keyword: first word of the command (e.g. 'open', 'installedapps',
             'settings', 'navigate', 'showmap', 'back', 'recents')
    rest:    everything after the keyword, as typed by the user
    APP_DATA: shared app state dict from main.py

    Returns a reply string, or None if this module doesn't handle the keyword.
    NOTE: no APP_DATA mutation in this module, so no save_data() call needed.
    """
    keyword = keyword.lower().strip()

    if keyword == "open":
        return open_app(rest, APP_DATA)
    elif keyword == "installedapps":
        return list_installed_apps(rest, APP_DATA)
    elif keyword == "settings":
        return open_settings_screen(rest, APP_DATA)
    elif keyword == "navigate":
        return navigate_to(rest, APP_DATA)
    elif keyword == "showmap":
        return show_on_map(rest, APP_DATA)
    elif keyword == "back":
        return go_back(rest, APP_DATA)
    elif keyword == "recents":
        return show_recents(rest, APP_DATA)

    return None
