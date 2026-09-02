"""
modules/device.py
DAN Automation Agent — Device module

Features:
- torch / torchoff              -> flashlight on/off
- battery                        -> battery status
- volup / voldown / mute          -> volume control via Termux:API
- silent / soundon                -> ringer mute/unmute (Termux:API based)
- batterysaver / batterysaveroff   -> battery saver toggle
- alarm <HH:MM>                    -> set an Android alarm
- wifi                              -> current wifi connection info
- wifiscan                           -> scan nearby wifi networks
- deviceinfo                         -> basic device info (model, android version)
- vibrate                             -> vibrate the device

Follows the same conventions as the other modules:
- Each public function takes the raw command text (after the keyword) and
  the shared APP_DATA dict, and returns a plain string reply for the chat bubble.
- Volume/silent use termux-volume (Termux:API), which works without any
  special permission grant. Raw `input keyevent` / `screencap` require
  shell/system-level Android permission that a regular Termux process can
  never get (not even via ADB) — so screen on/off, screenshot, and the
  home button shortcut were removed as unfixable without root. `back` and
  `recents` still use `input keyevent` and likely have the same problem —
  kept for now but not guaranteed to work.
- No network calls, no APP_DATA mutation — everything here is offline and stateless.
"""

import subprocess
import json

REQUEST_TIMEOUT = 10


def _run(cmd, timeout=REQUEST_TIMEOUT):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.SubprocessError:
        return None


# ---------------------------------------------------------------------------
# TORCH
# ---------------------------------------------------------------------------
def torch_on(text, APP_DATA):
    result = _run("termux-torch on")
    if result is None or result.returncode != 0:
        return "Couldn't turn on the torch — check Termux:API has camera permission."
    return "Torch on."


def torch_off(text, APP_DATA):
    result = _run("termux-torch off")
    if result is None or result.returncode != 0:
        return "Couldn't turn off the torch — check Termux:API has camera permission."
    return "Torch off."


# ---------------------------------------------------------------------------
# BATTERY
# ---------------------------------------------------------------------------
def battery_status(text, APP_DATA):
    result = _run("termux-battery-status")
    if result is None or result.returncode != 0 or not result.stdout.strip():
        return "Couldn't read battery status — check Termux:API is installed."

    try:
        data = json.loads(result.stdout)
        percentage = data.get("percentage", "?")
        status = data.get("status", "unknown")
        plugged = data.get("plugged", "UNPLUGGED")
        temp = data.get("temperature", None)

        line = f"Battery: {percentage}% ({status.lower()})"
        if plugged and plugged != "UNPLUGGED":
            line += f", charging via {plugged.lower()}"
        if temp:
            line += f", {temp:.1f}°C"
        return line
    except (json.JSONDecodeError, ValueError):
        return "Got a battery reading but couldn't parse it."


def battery_saver_on(text, APP_DATA):
    result = _run("settings put global low_power 1")
    if result is None:
        return "Couldn't enable battery saver."
    return "Battery saver enabled."


def battery_saver_off(text, APP_DATA):
    result = _run("settings put global low_power 0")
    if result is None:
        return "Couldn't disable battery saver."
    return "Battery saver disabled."


# ---------------------------------------------------------------------------
# VOLUME
# ---------------------------------------------------------------------------
def _get_volume(stream):
    result = _run(f"termux-volume {stream}")
    if result is None or result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        data = json.loads(result.stdout)
        if isinstance(data, list):
            for item in data:
                if item.get("stream") == stream:
                    return item.get("volume"), item.get("max_volume")
        return None
    except (json.JSONDecodeError, ValueError):
        return None


def volume_up(text, APP_DATA):
    info = _get_volume("music")
    if info is None:
        return "Couldn't read volume — check Termux:API is installed."
    current, maxv = info
    newv = min(maxv, current + 1)
    _run(f"termux-volume music {newv}")
    return f"Volume up ({newv}/{maxv})."


def volume_down(text, APP_DATA):
    info = _get_volume("music")
    if info is None:
        return "Couldn't read volume — check Termux:API is installed."
    current, maxv = info
    newv = max(0, current - 1)
    _run(f"termux-volume music {newv}")
    return f"Volume down ({newv}/{maxv})."


def mute(text, APP_DATA):
    _run("termux-volume music 0")
    _run("termux-volume ring 0")
    return "Muted (music and ringer set to 0)."


# ---------------------------------------------------------------------------
# SILENT MODE (mutes ringer via Termux:API — a real Do Not Disturb toggle
# needs WRITE_SECURE_SETTINGS granted via ADB; see focus mode's docstring)
# ---------------------------------------------------------------------------
def silent_on(text, APP_DATA):
    result = _run("termux-volume ring 0")
    if result is None or result.returncode != 0:
        return "Couldn't enable silent mode — check Termux:API is installed."
    return "Silent mode on (ringer muted)."


def silent_off(text, APP_DATA):
    info = _get_volume("ring")
    if info is None:
        return "Couldn't disable silent mode — check Termux:API is installed."
    _, maxv = info
    restored = max(1, maxv // 2)
    _run(f"termux-volume ring {restored}")
    return "Silent mode off (ringer restored)."


# ---------------------------------------------------------------------------
# ALARM
# ---------------------------------------------------------------------------
def set_alarm(text, APP_DATA):
    time_str = text.strip()
    parts = time_str.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return "Usage: alarm <HH:MM> — e.g. 'alarm 06:30'."

    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return "That's not a valid time — use 24-hour HH:MM."

    cmd = (
        f'am start -a android.intent.action.SET_ALARM '
        f'-e android.intent.extra.alarm.HOUR {hour} '
        f'-e android.intent.extra.alarm.MINUTES {minute} '
        f'-e android.intent.extra.alarm.SKIP_UI true'
    )
    result = _run(cmd)
    if result is None or result.returncode != 0:
        return "Couldn't send the alarm request — check the Clock app is installed."
    return (
        f"Sent to your Clock app for {hour:02d}:{minute:02d}. "
        f"If it opened the app instead of saving directly, tap Save to confirm "
        f"(some clock apps, including Samsung's, ignore the auto-confirm request)."
    )


# ---------------------------------------------------------------------------
# WIFI
# ---------------------------------------------------------------------------
def wifi_info(text, APP_DATA):
    result = _run("termux-wifi-connectioninfo")
    if result is None or result.returncode != 0 or not result.stdout.strip():
        return "Couldn't read wifi info — check Termux:API is installed and wifi is on."

    try:
        data = json.loads(result.stdout)
        ssid = data.get("ssid", "unknown")
        ip = data.get("ip", "unknown")
        speed = data.get("link_speed_mbps", "?")
        return f"Connected to '{ssid}', IP {ip}, link speed {speed} Mbps."
    except (json.JSONDecodeError, ValueError):
        return "Got wifi info but couldn't parse it."


def wifi_scan(text, APP_DATA):
    result = _run("termux-wifi-scaninfo", timeout=20)
    if result is None or result.returncode != 0 or not result.stdout.strip():
        return "Couldn't scan for wifi networks — check Termux:API and location permission."

    try:
        networks = json.loads(result.stdout)
        if not networks:
            return "No wifi networks found nearby."

        seen = set()
        lines = ["Nearby wifi networks:"]
        for net in networks:
            ssid = net.get("ssid", "").strip()
            if ssid and ssid not in seen:
                seen.add(ssid)
                lines.append(f"- {ssid}")
            if len(seen) >= 10:
                break
        return "\n".join(lines)
    except (json.JSONDecodeError, ValueError):
        return "Got scan results but couldn't parse them."


# ---------------------------------------------------------------------------
# DEVICE INFO
# ---------------------------------------------------------------------------
def device_info(text, APP_DATA):
    model = _run("getprop ro.product.model")
    android_version = _run("getprop ro.build.version.release")

    model_str = model.stdout.strip() if model and model.stdout else "unknown"
    version_str = android_version.stdout.strip() if android_version and android_version.stdout else "unknown"

    return f"Device: {model_str}, Android {version_str}"


# ---------------------------------------------------------------------------
# VIBRATE
# ---------------------------------------------------------------------------
def vibrate(text, APP_DATA):
    result = _run("termux-vibrate")
    if result is None or result.returncode != 0:
        return "Couldn't vibrate — check Termux:API is installed."
    return "Buzz!"


# ---------------------------------------------------------------------------
# ROUTER — called from modules/parser.py
# ---------------------------------------------------------------------------
def handle(keyword, rest, APP_DATA):
    """
    keyword: first word of the command
    rest:    everything after the keyword (mostly unused in this module)
    APP_DATA: shared app state dict from main.py

    Returns a reply string, or None if this module doesn't handle the keyword.
    NOTE: no APP_DATA mutation in this module, so no save_data() call needed.
    """
    keyword = keyword.lower().strip()

    if keyword == "torch":
        return torch_on(rest, APP_DATA)
    elif keyword == "torchoff":
        return torch_off(rest, APP_DATA)
    elif keyword == "battery":
        return battery_status(rest, APP_DATA)
    elif keyword == "batterysaver":
        return battery_saver_on(rest, APP_DATA)
    elif keyword == "batterysaveroff":
        return battery_saver_off(rest, APP_DATA)
    elif keyword == "volup":
        return volume_up(rest, APP_DATA)
    elif keyword == "voldown":
        return volume_down(rest, APP_DATA)
    elif keyword == "mute":
        return mute(rest, APP_DATA)
    elif keyword == "silent":
        return silent_on(rest, APP_DATA)
    elif keyword == "soundon":
        return silent_off(rest, APP_DATA)
    elif keyword == "alarm":
        return set_alarm(rest, APP_DATA)
    elif keyword == "wifi":
        return wifi_info(rest, APP_DATA)
    elif keyword == "wifiscan":
        return wifi_scan(rest, APP_DATA)
    elif keyword == "deviceinfo":
        return device_info(rest, APP_DATA)
    elif keyword == "vibrate":
        return vibrate(rest, APP_DATA)

    return None
