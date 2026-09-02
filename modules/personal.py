"""
modules/personal.py
DAN Automation Agent — Personal module

Features:
- task <text>            -> add a task
- tasks                   -> show all tasks (numbered, done marked)
- done <number>           -> mark a task complete
- deltask <number>        -> delete a task
- note <text>             -> save a note
- notes                   -> list all notes (numbered)
- readnote <number>       -> read a specific note in full
- delnote <number>        -> delete a note
- shop <item>             -> add item to shopping list
- shopping                -> show shopping list
- boughtshop <number>     -> remove item from shopping list (bought it)
- clearshop               -> clear entire shopping list
- diary <entry>           -> write a diary entry (timestamped)
- diaryread [count]       -> read last N diary entries (default 3)

Follows the same conventions as the other modules:
- Each public function takes the raw command text (after the keyword) and
  the shared APP_DATA dict, and returns a plain string reply for the chat bubble.
- All data is offline / local — no network calls in this module.
- Uses the existing APP_DATA keys already defined in main.py:
  tasks, notes, shopping, diary — each a list.
- parser.py should call save_data(APP_DATA) after any function here that
  mutates state (everything except the "show/read/list" ones), same as
  the pattern used elsewhere.
"""

from datetime import datetime


# ---------------------------------------------------------------------------
# DATA HELPERS
# ---------------------------------------------------------------------------
def _ensure_list(APP_DATA, key):
    if key not in APP_DATA or not isinstance(APP_DATA[key], list):
        APP_DATA[key] = []
    return APP_DATA[key]


def _parse_index(text, list_len):
    """Parse a 1-based index from user text, return 0-based int or None."""
    text = text.strip()
    if not text.isdigit():
        return None
    idx = int(text) - 1
    if idx < 0 or idx >= list_len:
        return None
    return idx


# ---------------------------------------------------------------------------
# TASKS
# ---------------------------------------------------------------------------
def add_task(text, APP_DATA):
    text = text.strip()
    if not text:
        return "What's the task? e.g. 'task buy phone credit'."

    tasks = _ensure_list(APP_DATA, "tasks")
    tasks.append({"text": text, "done": False})
    return f"Added task: {text}"


def show_tasks(text, APP_DATA):
    tasks = _ensure_list(APP_DATA, "tasks")
    if not tasks:
        return "No tasks yet. Add one with 'task <what you need to do>'."

    lines = ["Your tasks:"]
    for i, t in enumerate(tasks, 1):
        mark = "[x]" if t.get("done") else "[ ]"
        lines.append(f"{i}. {mark} {t.get('text', '')}")
    return "\n".join(lines)


def complete_task(text, APP_DATA):
    tasks = _ensure_list(APP_DATA, "tasks")
    idx = _parse_index(text, len(tasks))
    if idx is None:
        return "Usage: done <task number> — check 'tasks' for the numbers."

    tasks[idx]["done"] = True
    return f"Marked done: {tasks[idx]['text']}"


def delete_task(text, APP_DATA):
    tasks = _ensure_list(APP_DATA, "tasks")
    idx = _parse_index(text, len(tasks))
    if idx is None:
        return "Usage: deltask <task number> — check 'tasks' for the numbers."

    removed = tasks.pop(idx)
    return f"Deleted task: {removed['text']}"


# ---------------------------------------------------------------------------
# NOTES
# ---------------------------------------------------------------------------
def add_note(text, APP_DATA):
    text = text.strip()
    if not text:
        return "What's the note? e.g. 'note wifi password is on the router'."

    notes = _ensure_list(APP_DATA, "notes")
    notes.append({
        "text": text,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    return "Note saved."


def show_notes(text, APP_DATA):
    notes = _ensure_list(APP_DATA, "notes")
    if not notes:
        return "No notes yet. Add one with 'note <text>'."

    lines = ["Your notes:"]
    for i, n in enumerate(notes, 1):
        preview = n.get("text", "")
        if len(preview) > 40:
            preview = preview[:40] + "..."
        lines.append(f"{i}. {preview}")
    lines.append("Type 'readnote <number>' to read one in full.")
    return "\n".join(lines)


def read_note(text, APP_DATA):
    notes = _ensure_list(APP_DATA, "notes")
    idx = _parse_index(text, len(notes))
    if idx is None:
        return "Usage: readnote <note number> — check 'notes' for the numbers."

    n = notes[idx]
    return f"Note from {n.get('date', 'unknown date')}:\n{n.get('text', '')}"


def delete_note(text, APP_DATA):
    notes = _ensure_list(APP_DATA, "notes")
    idx = _parse_index(text, len(notes))
    if idx is None:
        return "Usage: delnote <note number> — check 'notes' for the numbers."

    notes.pop(idx)
    return "Note deleted."


# ---------------------------------------------------------------------------
# SHOPPING LIST
# ---------------------------------------------------------------------------
def add_shopping_item(text, APP_DATA):
    text = text.strip()
    if not text:
        return "What do you need to buy? e.g. 'shop rice'."

    shopping = _ensure_list(APP_DATA, "shopping")
    shopping.append(text)
    return f"Added to shopping list: {text}"


def show_shopping(text, APP_DATA):
    shopping = _ensure_list(APP_DATA, "shopping")
    if not shopping:
        return "Shopping list is empty."

    lines = ["Shopping list:"]
    for i, item in enumerate(shopping, 1):
        lines.append(f"{i}. {item}")
    return "\n".join(lines)


def bought_shopping_item(text, APP_DATA):
    shopping = _ensure_list(APP_DATA, "shopping")
    idx = _parse_index(text, len(shopping))
    if idx is None:
        return "Usage: boughtshop <item number> — check 'shopping' for the numbers."

    removed = shopping.pop(idx)
    return f"Removed from list: {removed}"


def clear_shopping(text, APP_DATA):
    shopping = _ensure_list(APP_DATA, "shopping")
    if not shopping:
        return "Shopping list is already empty."

    shopping.clear()
    return "Shopping list cleared."


# ---------------------------------------------------------------------------
# DIARY
# ---------------------------------------------------------------------------
def write_diary(text, APP_DATA):
    text = text.strip()
    if not text:
        return "What happened today? e.g. 'diary had a good day at work'."

    diary = _ensure_list(APP_DATA, "diary")
    diary.append({
        "text": text,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    return "Diary entry saved."


def read_diary(text, APP_DATA):
    diary = _ensure_list(APP_DATA, "diary")
    if not diary:
        return "No diary entries yet. Write one with 'diary <what happened>'."

    text = text.strip()
    count = 3
    if text.isdigit():
        count = int(text)

    recent = diary[-count:][::-1]
    lines = ["Recent diary entries:"]
    for d in recent:
        lines.append(f"[{d.get('date', 'unknown')}] {d.get('text', '')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ROUTER — called from modules/parser.py
# ---------------------------------------------------------------------------
def handle(keyword, rest, APP_DATA):
    """
    keyword: first word of the command (e.g. 'task', 'tasks', 'done',
             'deltask', 'note', 'notes', 'readnote', 'delnote', 'shop',
             'shopping', 'boughtshop', 'clearshop', 'diary', 'diaryread')
    rest:    everything after the keyword, as typed by the user
    APP_DATA: shared app state dict from main.py

    Returns a reply string, or None if this module doesn't handle the keyword.
    NOTE: parser.py should call save_data(APP_DATA) after any state-mutating
    call (everything except tasks/notes/shopping/diaryread which only read).
    """
    keyword = keyword.lower().strip()

    if keyword == "task":
        return add_task(rest, APP_DATA)
    elif keyword == "tasks":
        return show_tasks(rest, APP_DATA)
    elif keyword == "done":
        return complete_task(rest, APP_DATA)
    elif keyword == "deltask":
        return delete_task(rest, APP_DATA)
    elif keyword == "note":
        return add_note(rest, APP_DATA)
    elif keyword == "notes":
        return show_notes(rest, APP_DATA)
    elif keyword == "readnote":
        return read_note(rest, APP_DATA)
    elif keyword == "delnote":
        return delete_note(rest, APP_DATA)
    elif keyword == "shop":
        return add_shopping_item(rest, APP_DATA)
    elif keyword == "shopping":
        return show_shopping(rest, APP_DATA)
    elif keyword == "boughtshop":
        return bought_shopping_item(rest, APP_DATA)
    elif keyword == "clearshop":
        return clear_shopping(rest, APP_DATA)
    elif keyword == "diary":
        return write_diary(rest, APP_DATA)
    elif keyword == "diaryread":
        return read_diary(rest, APP_DATA)

    return None
