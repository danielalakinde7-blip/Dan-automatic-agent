"""
modules/communication.py
DAN Automation Agent — Communication module

Features:
- call <number>              -> call a number directly
- sms <number> <message>      -> open SMS app with number and message pre-filled
- whatsapp <number> <message>  -> open a WhatsApp chat via wa.me deep link
- openwhatsapp                  -> just open WhatsApp
- readsms                        -> read the last 5 SMS messages
- emaildraft <address> <subject> -> open email app with a draft started
- findcontact <name>              -> search contacts by name

Follows the same conventions as the other modules:
- Each public function takes the raw command text (after the keyword) and
  the shared APP_DATA dict, and returns a plain string reply for the chat bubble.
- Uses Android intents via "am start ..." and Termux:API's termux-sms-list
  and termux-contact-list.
- Nigerian numbers are auto-formatted: strip to digits, if it starts with
  0, replace with +234 (matches the convention used elsewhere in the app).
- No APP_DATA mutation — everything here is stateless.
"""

import subprocess
import json

REQUEST_TIMEOUT = 10


def _run(cmd, timeout=REQUEST_TIMEOUT):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.SubprocessError:
        return None


def _format_nigerian_number(number):
    digits = "".join(ch for ch in number if ch.isdigit() or ch == "+")
    if digits.startswith("0"):
        digits = "+234" + digits[1:]
    elif not digits.startswith("+"):
        digits = "+234" + digits
    return digits


# ---------------------------------------------------------------------------
# CALL
# ---------------------------------------------------------------------------
def call_number(text, APP_DATA):
    number = text.strip()
    if not number:
        return "Usage: call <number> — e.g. 'call 08012345678'."

    formatted = _format_nigerian_number(number)
    result = _run(f'am start -a android.intent.action.CALL -d "tel:{formatted}"')
    if result is None or result.returncode != 0:
        return f"Couldn't start the call to {formatted} — check phone permission is granted."

    return f"Calling {formatted}..."


# ---------------------------------------------------------------------------
# SMS
# ---------------------------------------------------------------------------
def send_sms(text, APP_DATA):
    """Expected: '<number> <message>' e.g. 'sms 08012345678 running late'"""
    parts = text.strip().split(" ", 1)
    if len(parts) < 2:
        return "Usage: sms <number> <message> — e.g. 'sms 08012345678 running late'."

    number, message = parts[0].strip(), parts[1].strip()
    formatted = _format_nigerian_number(number)

    cmd = (
        f'am start -a android.intent.action.SENDTO '
        f'-d "sms:{formatted}" --es sms_body "{message}"'
    )
    result = _run(cmd)
    if result is None or result.returncode != 0:
        return f"Couldn't open the SMS app for {formatted}."

    return f"Opened SMS to {formatted} with your message pre-filled."


def read_sms(text, APP_DATA):
    result = _run("termux-sms-list -l 5")
    if result is None or result.returncode != 0 or not result.stdout.strip():
        return "Couldn't read SMS — check Termux:API has SMS permission."

    try:
        messages = json.loads(result.stdout)
        if not messages:
            return "No SMS messages found."

        lines = ["Last 5 SMS messages:"]
        for m in messages[:5]:
            sender = m.get("number", m.get("sender", "unknown"))
            body = m.get("body", "").strip()
            if len(body) > 60:
                body = body[:60] + "..."
            lines.append(f"{sender}: {body}")
        return "\n".join(lines)
    except (json.JSONDecodeError, ValueError):
        return "Got SMS data but couldn't parse it."


# ---------------------------------------------------------------------------
# WHATSAPP
# ---------------------------------------------------------------------------
def whatsapp_message(text, APP_DATA):
    """Expected: '<number> <message>' e.g. 'whatsapp 08012345678 hey there'"""
    parts = text.strip().split(" ", 1)
    if len(parts) < 2:
        return "Usage: whatsapp <number> <message> — e.g. 'whatsapp 08012345678 hey there'."

    number, message = parts[0].strip(), parts[1].strip()
    formatted = _format_nigerian_number(number).lstrip("+")
    encoded_message = message.replace(" ", "%20")

    cmd = f'am start -a android.intent.action.VIEW -d "https://wa.me/{formatted}?text={encoded_message}"'
    result = _run(cmd)
    if result is None or result.returncode != 0:
        return f"Couldn't open WhatsApp for {formatted} — check it's installed."

    return f"Opening WhatsApp chat with {formatted}..."


def open_whatsapp(text, APP_DATA):
    result = _run("am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -p com.whatsapp")
    if result is None or result.returncode != 0:
        return "Couldn't open WhatsApp — check it's installed."
    return "Opening WhatsApp..."


# ---------------------------------------------------------------------------
# EMAIL
# ---------------------------------------------------------------------------
def email_draft(text, APP_DATA):
    """Expected: '<address> <subject>' e.g. 'emaildraft boss@work.com update'"""
    parts = text.strip().split(" ", 1)
    if not parts or not parts[0]:
        return "Usage: emaildraft <address> [subject] — e.g. 'emaildraft boss@work.com update'."

    address = parts[0].strip()
    subject = parts[1].strip() if len(parts) > 1 else ""

    cmd = f'am start -a android.intent.action.SENDTO -d "mailto:{address}"'
    if subject:
        cmd += f' --es android.intent.extra.SUBJECT "{subject}"'

    result = _run(cmd)
    if result is None or result.returncode != 0:
        return f"Couldn't open an email draft to {address}."

    return f"Opened an email draft to {address}."


# ---------------------------------------------------------------------------
# CONTACTS
# ---------------------------------------------------------------------------
def find_contact(text, APP_DATA):
    name = text.strip().lower()
    if not name:
        return "Usage: findcontact <name> — e.g. 'findcontact John'."

    result = _run("termux-contact-list")
    if result is None or result.returncode != 0 or not result.stdout.strip():
        return "Couldn't read contacts — check Termux:API has contacts permission."

    try:
        contacts = json.loads(result.stdout)
        matches = [c for c in contacts if name in c.get("name", "").lower()]

        if not matches:
            return f"No contacts found matching '{name}'."

        lines = [f"Contacts matching '{name}':"]
        for c in matches[:5]:
            contact_name = c.get("name", "Unknown")
            numbers = c.get("number", "")
            lines.append(f"{contact_name}: {numbers}")
        return "\n".join(lines)
    except (json.JSONDecodeError, ValueError):
        return "Got contact data but couldn't parse it."


# ---------------------------------------------------------------------------
# ROUTER — called from modules/parser.py
# ---------------------------------------------------------------------------
def handle(keyword, rest, APP_DATA):
    """
    keyword: first word of the command (e.g. 'call', 'sms', 'whatsapp',
             'openwhatsapp', 'readsms', 'emaildraft', 'findcontact')
    rest:    everything after the keyword, as typed by the user
    APP_DATA: shared app state dict from main.py

    Returns a reply string, or None if this module doesn't handle the keyword.
    NOTE: no APP_DATA mutation in this module, so no save_data() call needed.
    """
    keyword = keyword.lower().strip()

    if keyword == "call":
        return call_number(rest, APP_DATA)
    elif keyword == "sms":
        return send_sms(rest, APP_DATA)
    elif keyword == "readsms":
        return read_sms(rest, APP_DATA)
    elif keyword == "whatsapp":
        return whatsapp_message(rest, APP_DATA)
    elif keyword == "openwhatsapp":
        return open_whatsapp(rest, APP_DATA)
    elif keyword == "emaildraft":
        return email_draft(rest, APP_DATA)
    elif keyword == "findcontact":
        return find_contact(rest, APP_DATA)

    return None
