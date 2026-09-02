"""
cli_test.py
DAN Automation Agent — CLI Test Harness

Lets you test EVERY feature of DAN directly in the Termux terminal, no
Kivy, no X11, no touch/display issues at all. Uses the exact same
load_data/save_data and parser.handle_command that main.py uses, and
reads/writes the SAME dan_data.json file — so anything you do here
(add a task, save a password, etc.) will show up in the real app too,
and vice versa.

This is the fastest way to test all ~90 commands across all 13 modules
without fighting Termux:X11's display/touch quirks.

RUN:
    cd ~/dan_automation
    python3 cli_test.py

Type 'exit' or 'quit' to stop. Type 'help' to see all commands.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules import parser
import json

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dan_data.json")

DEFAULT_DATA = {
    "theme": "dark",
    "is_premium": False,
    "username": None,
    "tasks": [],
    "notes": [],
    "shopping": [],
    "diary": [],
    "habits": [],
    "budget": {"income": 0, "expenses": 0, "log": []},
    "spots": [],
    "location_history": [],
    "spot_reminders": [],
    "emergency_contact": "",
    "passwords": {},
    "memory": {},
    "workouts": [],
    "sleep_log": [],
    "medicine_log": [],
    "recordings": [],
    "conversations": [],
    "monitored_sites": [],
    "briefing_time": None,
    "routines": {},
    "nlu_api_key": None,
}


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, default_value in DEFAULT_DATA.items():
                data.setdefault(key, default_value)
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_DATA)


def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except OSError:
        return False


def main():
    APP_DATA = load_data()

    print("=" * 60)
    print(f"DAN Automation Agent — CLI Test Mode")
    print(f"(using {DATA_FILE})")
    print("Type 'help' for commands, 'exit' or 'quit' to stop.")
    print("=" * 60)

    name = APP_DATA.get("username")
    if not name:
        print("\nDAN: Hey! I don't think we've met — what should I call you?\n")
    else:
        print(f"\nDAN: Hey {name}! Type 'help' to see what I can do.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nDAN: See you later.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            print("DAN: See you later.")
            break

        reply = parser.handle_command(user_input, APP_DATA)
        save_data(APP_DATA)

        print(f"DAN: {reply}\n")


if __name__ == "__main__":
    main()
