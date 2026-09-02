"""
modules/passwords.py
DAN Automation Agent — Passwords module

Features:
- genpass [length]              -> generate a random strong password
- savepass <name> <password>    -> save a password under a name (encrypted)
- getpass <name>                -> recall a saved password by name
- passnames                      -> list saved password names (never values)
- delpass <name>                 -> delete a saved password

Follows the same conventions as the other modules:
- Each public function takes the raw command text (after the keyword) and
  the shared APP_DATA dict, and returns a plain string reply for the chat bubble.
- Uses the existing APP_DATA['passwords'] dict, storing name -> encrypted value.
- No network calls in this module.
- parser.py should call save_data(APP_DATA) after any state-mutating call
  (savepass, delpass).

SECURITY NOTE (important, read before relying on this):
This uses a simple reversible XOR + base64 obfuscation, NOT real
cryptography. It will stop a casual look at dan_data.json but will NOT
stop anyone who knows what they're doing. The key lives in this file
(DEVICE_KEY) — anyone with your source has the key too. For real security
later, swap _encrypt/_decrypt for the `cryptography` package's Fernet
(pip install cryptography), which needs a proper key derivation step.
Flagging this clearly so it doesn't get treated as production-grade
encryption by mistake.
"""

import base64
import random
import string


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
# Change this to something unique to you before first use. Changing it
# AFTER you've saved passwords will make old ones unreadable.
DEVICE_KEY = "dan-automation-change-me"


# ---------------------------------------------------------------------------
# SIMPLE XOR OBFUSCATION (see security note above — not real encryption)
# ---------------------------------------------------------------------------
def _xor(text, key):
    return "".join(
        chr(ord(c) ^ ord(key[i % len(key)]))
        for i, c in enumerate(text)
    )


def _encrypt(plain_text):
    xored = _xor(plain_text, DEVICE_KEY)
    return base64.b64encode(xored.encode("utf-8", errors="surrogateescape")).decode("ascii")


def _decrypt(encrypted_text):
    try:
        xored = base64.b64decode(encrypted_text.encode("ascii")).decode("utf-8", errors="surrogateescape")
        return _xor(xored, DEVICE_KEY)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# DATA HELPERS
# ---------------------------------------------------------------------------
def _ensure_dict(APP_DATA, key):
    if key not in APP_DATA or not isinstance(APP_DATA[key], dict):
        APP_DATA[key] = {}
    return APP_DATA[key]


# ---------------------------------------------------------------------------
# GENERATE PASSWORD
# ---------------------------------------------------------------------------
def generate_password(text, APP_DATA):
    text = text.strip()
    length = 16
    if text.isdigit():
        length = int(text)
        length = max(6, min(length, 64))  # keep it sane

    chars = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    password = "".join(random.SystemRandom().choice(chars) for _ in range(length))

    return f"Generated password ({length} chars): {password}"


# ---------------------------------------------------------------------------
# SAVE / GET / LIST / DELETE
# ---------------------------------------------------------------------------
def save_password(text, APP_DATA):
    """Expected: '<name> <password>' e.g. 'savepass gmail Xy9!kLp2Qz'"""
    parts = text.strip().split(" ", 1)
    if len(parts) < 2:
        return "Usage: savepass <name> <password> — e.g. 'savepass gmail Xy9!kLp2Qz'."

    name, password = parts[0].strip(), parts[1].strip()
    if not name or not password:
        return "Usage: savepass <name> <password> — e.g. 'savepass gmail Xy9!kLp2Qz'."

    passwords = _ensure_dict(APP_DATA, "passwords")
    passwords[name] = _encrypt(password)

    return f"Saved password for '{name}'. (Reminder: this is basic obfuscation, not strong encryption.)"


def get_password(text, APP_DATA):
    name = text.strip()
    if not name:
        return "Usage: getpass <name> — e.g. 'getpass gmail'."

    passwords = _ensure_dict(APP_DATA, "passwords")
    if name not in passwords:
        return f"No saved password for '{name}'. Check 'passnames' for what's saved."

    decrypted = _decrypt(passwords[name])
    if decrypted is None:
        return f"Couldn't decrypt the password for '{name}' — it may be corrupted."

    return f"Password for '{name}': {decrypted}"


def list_password_names(text, APP_DATA):
    passwords = _ensure_dict(APP_DATA, "passwords")
    if not passwords:
        return "No passwords saved yet."

    names = sorted(passwords.keys())
    lines = ["Saved password names:"] + [f"- {n}" for n in names]
    return "\n".join(lines)


def delete_password(text, APP_DATA):
    name = text.strip()
    if not name:
        return "Usage: delpass <name> — e.g. 'delpass gmail'."

    passwords = _ensure_dict(APP_DATA, "passwords")
    if name not in passwords:
        return f"No saved password for '{name}'."

    del passwords[name]
    return f"Deleted password for '{name}'."


# ---------------------------------------------------------------------------
# ROUTER — called from modules/parser.py
# ---------------------------------------------------------------------------
def handle(keyword, rest, APP_DATA):
    """
    keyword: first word of the command (e.g. 'genpass', 'savepass',
             'getpass', 'passnames', 'delpass')
    rest:    everything after the keyword, as typed by the user
    APP_DATA: shared app state dict from main.py

    Returns a reply string, or None if this module doesn't handle the keyword.
    NOTE: parser.py should call save_data(APP_DATA) after any state-mutating
    call (savepass, delpass).
    """
    keyword = keyword.lower().strip()

    if keyword == "genpass":
        return generate_password(rest, APP_DATA)
    elif keyword == "savepass":
        return save_password(rest, APP_DATA)
    elif keyword == "getpass":
        return get_password(rest, APP_DATA)
    elif keyword == "passnames":
        return list_password_names(rest, APP_DATA)
    elif keyword == "delpass":
        return delete_password(rest, APP_DATA)

    return None
