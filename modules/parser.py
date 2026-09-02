"""
modules/parser.py
DAN Automation Agent — Command Router

This is the central dispatcher. main.py calls handle_command(text, APP_DATA)
for every message the user sends. In order, it tries:
1. Username capture, if this is the very first message (no username set yet).
2. Routine management commands (createroutine, runroutine, routines, delroutine)
   and the NLU API key setter (setnluapikey) — these are parser-level, not
   delegated to a feature module.
3. Built-in commands (help, memory, greetings, stats/dashboard, conversation log).
4. Every feature module's handle(keyword, rest, APP_DATA), in order.
5. A routine TRIGGER PHRASE check — if the whole message matches a saved
   routine's name exactly, run it (e.g. saying "leaving work" runs whatever
   steps were saved under that name). Checked here, AFTER normal commands,
   so a routine can never accidentally shadow a real command.
6. Natural language fallback via modules/nlu.py — if NOTHING above matched
   and the user has set an API key, ask Claude to re-map the message into
   a known command format, then resolve that instead.
7. A friendly "try help" message if nothing at all matched.

Every command is logged to APP_DATA['conversations'].
"""

from datetime import datetime

from modules import device, apps, communication
from modules import internet, finance, personal, health, timemod
from modules import entertainment, location, passwords, audio, automation
from modules import nlu


# Modules tried in this order for every command (after built-ins below)
FEATURE_MODULES = [
    device,
    apps,
    communication,
    internet,
    finance,
    personal,
    health,
    timemod,
    entertainment,
    location,
    passwords,
    audio,
    automation,
]

HELP_TEXT = (
    "Here's what I can help with — type any of these (some take extra "
    "words, e.g. 'weather Lagos'), or just talk to me normally once you've "
    "set an API key with 'setnluapikey <key>':\n\n"
    "Device: torch, silent, battery, alarm, vibrate\n"
    "Apps: open <app name>, settings <screen>, navigate <place>\n"
    "Contact: call <number>, sms <number>, whatsapp <number>, email\n"
    "Internet: weather, wiki, news, translate, search, scrape\n"
    "Finance: convert, dollar, crypto, budget, income, expense\n"
    "Personal: task, tasks, note, notes, shop, shopping, diary\n"
    "Health: habit, habits, workout, sleep, medicine, meds\n"
    "Time: remindme, timer, pomodoro, focus, countdown\n"
    "Fun: joke, trivia, quote, story, wordoftheday\n"
    "Location: markspot, spots, whereami, locationhistory\n"
    "Passwords: genpass, savepass, getpass, passnames\n"
    "Audio: record, play, recordings\n"
    "Automation: setbriefing, monitor, monitored, checksites\n"
    "Routines: createroutine <name>: <cmd1> | <cmd2>, runroutine <name>, routines\n"
    "Other: remember <text>, recall <topic>, stats, conversations"
)

GREETING_WORDS_MORNING = ("good morning", "morning dan", "morning")
GREETING_WORDS_NIGHT = ("good night", "night dan", "goodnight")

FALLBACK_MESSAGE = "I didn't catch that. Type 'help' to see what I can do."


# ---------------------------------------------------------------------------
# ENTRY POINT — called from main.py
# ---------------------------------------------------------------------------
def handle_command(text, APP_DATA):
    raw = text.strip()
    if not raw:
        return "Say something and I'll help out."

    if not APP_DATA.get("username"):
        name = raw.strip()
        APP_DATA["username"] = name
        return f"Nice to meet you, {name}! Type 'help' to see what I can do."

    # Parser-level commands (routines management, NLU key) — checked before
    # normal routing since they have their own special syntax (colons, pipes).
    reply = _handle_parser_commands(raw, APP_DATA)

    # Normal resolution: built-ins, then feature modules.
    if reply is None:
        reply = _resolve_command(raw, APP_DATA)

    # Routine TRIGGER PHRASE — only checked if nothing above matched, so a
    # routine can never shadow a real command like "battery".
    if reply is None:
        reply = _check_routine_trigger(raw, APP_DATA)

    # Natural language fallback — last resort, costs an API call.
    if reply is None:
        mapped = nlu.interpret(raw, APP_DATA)
        if mapped:
            resolved = _resolve_command(mapped, APP_DATA)
            if resolved:
                reply = resolved

    if reply is None:
        reply = FALLBACK_MESSAGE

    _log_conversation(raw, reply, APP_DATA)
    return reply


def _resolve_command(raw, APP_DATA):
    """Tries built-ins, then feature modules. Returns None if nothing matched."""
    reply = _handle_builtin(raw, APP_DATA)
    if reply is None:
        keyword, rest = _tokenize(raw)
        reply = _route_to_modules(keyword, rest, APP_DATA)
    return reply


def _tokenize(raw):
    parts = raw.split(" ", 1)
    keyword = parts[0].lower().strip()
    rest = parts[1] if len(parts) > 1 else ""
    return keyword, rest


def _route_to_modules(keyword, rest, APP_DATA):
    for module in FEATURE_MODULES:
        try:
            reply = module.handle(keyword, rest, APP_DATA)
        except Exception as e:
            return f"Something went wrong running that command: {e}"
        if reply is not None:
            return reply
    return None


# ---------------------------------------------------------------------------
# BUILT-IN COMMANDS (not delegated to a feature module)
# ---------------------------------------------------------------------------
def _handle_builtin(raw, APP_DATA):
    lower = raw.lower().strip()

    if lower == "help":
        return HELP_TEXT

    if lower in GREETING_WORDS_MORNING:
        name = APP_DATA.get("username", "there")
        return f"Good morning, {name}! Ready when you are — type 'help' if you need ideas."

    if lower in GREETING_WORDS_NIGHT:
        name = APP_DATA.get("username", "there")
        return f"Good night, {name}! Rest well."

    if lower.startswith("remember "):
        return _remember(raw[9:], APP_DATA)

    if lower.startswith("recall "):
        return _recall(raw[7:], APP_DATA)

    if lower in ("stats", "dashboard"):
        return _show_stats(APP_DATA)

    if lower in ("conversations", "history", "chatlog"):
        return _show_conversations(APP_DATA)

    return None


def _remember(text, APP_DATA):
    text = text.strip()
    if " is " not in text and " as " not in text:
        return "Tell me what to remember like: 'remember wifi password is 12345'."

    separator = " is " if " is " in text else " as "
    key, value = text.split(separator, 1)
    key, value = key.strip().lower(), value.strip()

    memory = APP_DATA.setdefault("memory", {})
    memory[key] = value
    return f"Got it — I'll remember that {key} is {value}."


def _recall(topic, APP_DATA):
    topic = topic.strip().lower()
    memory = APP_DATA.get("memory", {})

    if not topic:
        if not memory:
            return "I don't have anything remembered yet."
        lines = ["Here's everything I remember:"]
        for k, v in memory.items():
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)

    if topic in memory:
        return f"{topic}: {memory[topic]}"

    matches = [k for k in memory if topic in k]
    if matches:
        lines = [f"Closest matches for '{topic}':"]
        for k in matches:
            lines.append(f"- {k}: {memory[k]}")
        return "\n".join(lines)

    return f"I don't remember anything about '{topic}'."


def _show_stats(APP_DATA):
    tasks = APP_DATA.get("tasks", [])
    open_tasks = len([t for t in tasks if not t.get("done")])
    habits = APP_DATA.get("habits", [])
    budget = APP_DATA.get("budget", {"income": 0, "expenses": 0})
    balance = budget.get("income", 0) - budget.get("expenses", 0)

    return (
        f"Dashboard:\n"
        f"Open tasks: {open_tasks}\n"
        f"Habits tracked: {len(habits)}\n"
        f"Notes saved: {len(APP_DATA.get('notes', []))}\n"
        f"Budget balance: {balance:,.2f}\n"
        f"Monitored sites: {len(APP_DATA.get('monitored_sites', []))}\n"
        f"Conversations logged: {len(APP_DATA.get('conversations', []))}"
    )


def _show_conversations(APP_DATA):
    conversations = APP_DATA.get("conversations", [])
    if not conversations:
        return "No conversation history yet."

    recent = conversations[-10:][::-1]
    lines = ["Recent conversation log:"]
    for entry in recent:
        lines.append(f"[{entry.get('date', '')}] You: {entry.get('you', '')}")
    return "\n".join(lines)


def _log_conversation(user_text, reply_text, APP_DATA):
    conversations = APP_DATA.setdefault("conversations", [])
    conversations.append({
        "you": user_text,
        "dan": reply_text,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    # keep the log from growing forever — trim to last 200 entries
    if len(conversations) > 200:
        APP_DATA["conversations"] = conversations[-200:]


# ---------------------------------------------------------------------------
# ROUTINES / MACROS
# ---------------------------------------------------------------------------
def _handle_parser_commands(raw, APP_DATA):
    """Handles createroutine, runroutine, routines, delroutine, setnluapikey."""
    lower = raw.lower().strip()

    if lower.startswith("createroutine "):
        return _create_routine(raw[14:], APP_DATA)

    if lower.startswith("runroutine "):
        return _run_routine(raw[11:].strip(), APP_DATA)

    if lower == "routines":
        return _list_routines(APP_DATA)

    if lower.startswith("delroutine "):
        return _delete_routine(raw[11:].strip(), APP_DATA)

    if lower.startswith("setnluapikey "):
        key = raw[13:].strip()
        if not key:
            return "Usage: setnluapikey <your-anthropic-api-key>"
        APP_DATA["nlu_api_key"] = key
        return "API key saved. You can now talk to me in plain language, not just exact commands."

    return None


def _create_routine(text, APP_DATA):
    """Expected: '<name>: <cmd1> | <cmd2> | ...' e.g. 'leaving work: silent | navigate home'"""
    if ":" not in text:
        return (
            "Usage: createroutine <name>: <command1> | <command2> | ... — "
            "e.g. 'createroutine leaving work: silent | navigate home'."
        )

    name, steps_text = text.split(":", 1)
    name = name.strip()
    steps = [s.strip() for s in steps_text.split("|") if s.strip()]

    if not name:
        return "Give the routine a name — e.g. 'createroutine leaving work: silent | navigate home'."
    if not steps:
        return "A routine needs at least one command — e.g. 'createroutine leaving work: silent | navigate home'."

    routines = APP_DATA.setdefault("routines", {})
    routines[name.lower()] = {"name": name, "steps": steps}

    steps_preview = ", ".join(steps)
    return f"Routine '{name}' saved with {len(steps)} step(s): {steps_preview}. Trigger it by saying '{name}' or 'runroutine {name}'."


def _run_routine(name, APP_DATA):
    routines = APP_DATA.get("routines", {})
    entry = routines.get(name.lower())
    if not entry:
        return f"No routine called '{name}'. Check 'routines' for what's saved."

    return _execute_routine(entry, APP_DATA)


def _execute_routine(entry, APP_DATA):
    name = entry.get("name", "routine")
    steps = entry.get("steps", [])

    lines = [f"Running '{name}':"]
    for i, step in enumerate(steps, 1):
        result = _resolve_command(step, APP_DATA)
        if result is None:
            result = "(no matching command)"
        lines.append(f"{i}. {step} -> {result}")

    return "\n".join(lines)


def _list_routines(APP_DATA):
    routines = APP_DATA.get("routines", {})
    if not routines:
        return "No routines saved yet. Try 'createroutine leaving work: silent | navigate home'."

    lines = ["Saved routines:"]
    for entry in routines.values():
        step_count = len(entry.get("steps", []))
        lines.append(f"- {entry.get('name', '')} ({step_count} step(s))")
    return "\n".join(lines)


def _delete_routine(name, APP_DATA):
    routines = APP_DATA.get("routines", {})
    if name.lower() not in routines:
        return f"No routine called '{name}'."

    del routines[name.lower()]
    return f"Deleted routine '{name}'."


def _check_routine_trigger(raw, APP_DATA):
    """If the WHOLE message matches a saved routine's name, run it."""
    routines = APP_DATA.get("routines", {})
    entry = routines.get(raw.lower().strip())
    if entry:
        return _execute_routine(entry, APP_DATA)
    return None
