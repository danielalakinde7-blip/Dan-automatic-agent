"""
verify_modules.py
DAN Automation Agent — Module Integrity Checker

Checks every module's handle(keyword, rest, APP_DATA) function against the
list of keywords it SHOULD contain. This catches the exact bug we found in
timemod.py — where a paste error silently replaced one module's content
with another's, and everything still ran/compiled fine, it just routed
commands to the wrong (or no) place.

Run from the project root:
    cd ~/dan_automation
    python3 verify_modules.py

For each module, it reports:
- OK: all expected keywords found, no unexpected ones
- MISSING: expected keywords not found in the file (likely wrong content pasted)
- UNEXPECTED: keywords found that shouldn't be there (likely wrong content pasted)
"""

import inspect
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules import (
    device, apps, communication,
    internet, finance, personal, health, timemod,
    entertainment, location, passwords, audio, automation,
)

EXPECTED_KEYWORDS = {
    "device": {
        "torch", "torchoff", "battery", "batterysaver", "batterysaveroff",
        "volup", "voldown", "mute", "silent", "soundon", "alarm", "wifi",
        "wifiscan", "deviceinfo", "vibrate",
    },
    "apps": {
        "open", "installedapps", "settings", "navigate", "showmap",
        "back", "recents",
    },
    "communication": {
        "call", "sms", "readsms", "whatsapp", "openwhatsapp",
        "emaildraft", "findcontact",
    },
    "internet": {
        "weather", "wiki", "news", "translate", "search", "scrape",
    },
    "finance": {
        "convert", "dollar", "crypto", "budget", "income", "expense", "expenses",
    },
    "personal": {
        "task", "tasks", "done", "deltask", "note", "notes", "readnote",
        "delnote", "shop", "shopping", "boughtshop", "clearshop",
        "diary", "diaryread",
    },
    "health": {
        "habit", "habits", "habitdone", "delhabit", "workout", "workouts",
        "sleep", "sleeplog", "medicine", "meds", "delmed",
    },
    "timemod": {
        "remindme", "timer", "pomodoro", "focus", "countdown",
    },
    "entertainment": {
        "joke", "trivia", "quote", "story", "wordoftheday",
    },
    "location": {
        "markspot", "spots", "delspot", "whereami", "locationhistory",
        "remindatspot",
    },
    "passwords": {
        "genpass", "savepass", "getpass", "passnames", "delpass",
    },
    "audio": {
        "record", "stoprecord", "play", "recordings", "delrecording", "transcribe",
    },
    "automation": {
        "setbriefing", "briefingtime", "stopbriefing", "monitor",
        "monitored", "stopmonitor", "checksites",
    },
}

MODULES = {
    "device": device, "apps": apps, "communication": communication,
    "internet": internet, "finance": finance, "personal": personal,
    "health": health, "timemod": timemod, "entertainment": entertainment,
    "location": location, "passwords": passwords, "audio": audio,
    "automation": automation,
}


def extract_keywords_from_handle(module):
    """Pulls every 'keyword == "..."' string out of a module's handle() source."""
    try:
        source = inspect.getsource(module.handle)
    except (OSError, TypeError, AttributeError):
        return None

    matches = re.findall(r'keyword\s*==\s*"([^"]+)"', source)
    return set(matches)


def main():
    print("=" * 60)
    print("DAN Automation Agent — Module Integrity Check")
    print("=" * 60)

    all_ok = True

    for name, module in MODULES.items():
        expected = EXPECTED_KEYWORDS.get(name, set())
        actual = extract_keywords_from_handle(module)

        if actual is None:
            print(f"\n[ERROR] {name}.py — couldn't read handle() at all (missing function?)")
            all_ok = False
            continue

        missing = expected - actual
        unexpected = actual - expected

        if not missing and not unexpected:
            print(f"[OK]    {name}.py — {len(actual)} keywords match")
        else:
            all_ok = False
            print(f"\n[ISSUE] {name}.py")
            if missing:
                print(f"        MISSING (expected but not found): {sorted(missing)}")
            if unexpected:
                print(f"        UNEXPECTED (found but shouldn't be here): {sorted(unexpected)}")
                for other_name, other_expected in EXPECTED_KEYWORDS.items():
                    if other_name != name and unexpected.issubset(other_expected):
                        print(f"        ^ these keywords match {other_name}.py's expected set —")
                        print(f"          likely {other_name}.py's content got pasted into {name}.py")

    print("\n" + "=" * 60)
    if all_ok:
        print("ALL MODULES OK — no corruption detected.")
    else:
        print("ISSUES FOUND — see above. Re-paste the affected file(s).")
    print("=" * 60)


if __name__ == "__main__":
    main()
