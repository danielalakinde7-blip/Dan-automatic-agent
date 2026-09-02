"""
modules/audio.py
DAN Automation Agent — Audio module

Features:
- record [seconds]     -> record audio (default 30s, or stop manually)
- stoprecord            -> stop an in-progress recording early
- play                  -> play back the last recording
- recordings            -> list saved recordings
- transcribe            -> placeholder (needs internet/offline STT — not built yet)

Follows the same conventions as the other modules:
- Each public function takes the raw command text (after the keyword) and
  the shared APP_DATA dict, and returns a plain string reply for the chat bubble.
- Uses Termux:API's termux-microphone-record and termux-media-player.
- Recordings are saved to the app's own storage folder so they persist
  between runs; APP_DATA['recordings'] just tracks filenames/metadata.
- parser.py should call save_data(APP_DATA) after any state-mutating call
  (record, delrecording).
"""

import subprocess
import os
from datetime import datetime


REQUEST_TIMEOUT = 10
RECORDINGS_DIR = os.path.expanduser("~/dan_automation/assets/recordings")


# ---------------------------------------------------------------------------
# DATA HELPERS
# ---------------------------------------------------------------------------
def _ensure_list(APP_DATA, key):
    if key not in APP_DATA or not isinstance(APP_DATA[key], list):
        APP_DATA[key] = []
    return APP_DATA[key]


def _ensure_dir():
    os.makedirs(RECORDINGS_DIR, exist_ok=True)


def _parse_index(text, list_len):
    text = text.strip()
    if not text.isdigit():
        return None
    idx = int(text) - 1
    if idx < 0 or idx >= list_len:
        return None
    return idx


# ---------------------------------------------------------------------------
# RECORD
# ---------------------------------------------------------------------------
def start_recording(text, APP_DATA):
    text = text.strip()
    seconds = 30
    if text.isdigit():
        seconds = max(1, min(int(text), 600))  # cap at 10 min to be safe

    _ensure_dir()
    filename = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.m4a"
    filepath = os.path.join(RECORDINGS_DIR, filename)

    try:
        result = subprocess.run(
            f'termux-microphone-record -f "{filepath}" -l {seconds}',
            shell=True,
            capture_output=True,
            text=True,
            timeout=REQUEST_TIMEOUT,
        )
        if result.returncode != 0:
            return "Couldn't start recording — check Termux:API has microphone permission."
    except subprocess.SubprocessError:
        return "Couldn't start recording — check Termux:API is installed."

    recordings = _ensure_list(APP_DATA, "recordings")
    recordings.append({
        "filename": filename,
        "path": filepath,
        "seconds": seconds,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })

    return f"Recording started for {seconds}s. Say 'stoprecord' to stop early, or it'll stop on its own."


def stop_recording(text, APP_DATA):
    try:
        result = subprocess.run(
            "termux-microphone-record -q",
            shell=True,
            capture_output=True,
            text=True,
            timeout=REQUEST_TIMEOUT,
        )
        if result.returncode != 0:
            return "Nothing seems to be recording right now."
    except subprocess.SubprocessError:
        return "Couldn't stop the recording — check Termux:API is installed."

    return "Recording stopped."


# ---------------------------------------------------------------------------
# PLAY BACK
# ---------------------------------------------------------------------------
def play_last_recording(text, APP_DATA):
    recordings = _ensure_list(APP_DATA, "recordings")
    if not recordings:
        return "No recordings yet. Try 'record 10' to make one."

    last = recordings[-1]
    filepath = last.get("path", "")

    if not os.path.exists(filepath):
        return f"Couldn't find that recording file on disk — it may have been moved or deleted."

    try:
        result = subprocess.run(
            f'termux-media-player play "{filepath}"',
            shell=True,
            capture_output=True,
            text=True,
            timeout=REQUEST_TIMEOUT,
        )
        if result.returncode != 0:
            return "Couldn't start playback — check Termux:API is installed."
    except subprocess.SubprocessError:
        return "Couldn't start playback — check Termux:API is installed."

    return f"Playing: {last.get('filename', 'recording')}"


def list_recordings(text, APP_DATA):
    recordings = _ensure_list(APP_DATA, "recordings")
    if not recordings:
        return "No recordings yet. Try 'record 10' to make one."

    lines = ["Saved recordings:"]
    for i, r in enumerate(recordings, 1):
        lines.append(f"{i}. {r.get('filename', '')} — {r.get('seconds', 0)}s ({r.get('date', '')})")
    return "\n".join(lines)


def delete_recording(text, APP_DATA):
    recordings = _ensure_list(APP_DATA, "recordings")
    idx = _parse_index(text, len(recordings))
    if idx is None:
        return "Usage: delrecording <number> — check 'recordings' for the numbers."

    removed = recordings.pop(idx)
    filepath = removed.get("path", "")
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError:
            pass  # metadata is gone either way; file cleanup is best-effort

    return f"Deleted recording: {removed.get('filename', '')}"


# ---------------------------------------------------------------------------
# TRANSCRIBE (placeholder — no offline STT wired up yet)
# ---------------------------------------------------------------------------
def transcribe(text, APP_DATA):
    return (
        "Transcription isn't available offline yet. This would need either an "
        "internet-based speech-to-text API (e.g. a free-tier Whisper API) or an "
        "on-device model bundled into the APK — not wired up yet."
    )


# ---------------------------------------------------------------------------
# ROUTER — called from modules/parser.py
# ---------------------------------------------------------------------------
def handle(keyword, rest, APP_DATA):
    """
    keyword: first word of the command (e.g. 'record', 'stoprecord', 'play',
             'recordings', 'delrecording', 'transcribe')
    rest:    everything after the keyword, as typed by the user
    APP_DATA: shared app state dict from main.py

    Returns a reply string, or None if this module doesn't handle the keyword.
    NOTE: parser.py should call save_data(APP_DATA) after any state-mutating
    call (record, delrecording).
    """
    keyword = keyword.lower().strip()

    if keyword == "record":
        return start_recording(rest, APP_DATA)
    elif keyword == "stoprecord":
        return stop_recording(rest, APP_DATA)
    elif keyword == "play":
        return play_last_recording(rest, APP_DATA)
    elif keyword == "recordings":
        return list_recordings(rest, APP_DATA)
    elif keyword == "delrecording":
        return delete_recording(rest, APP_DATA)
    elif keyword == "transcribe":
        return transcribe(rest, APP_DATA)

    return None
