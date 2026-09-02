"""
modules/nlu.py
DAN Automation Agent — Natural Language Interpreter

Only invoked when a raw command doesn't match any known keyword, saved
routine, or built-in. Takes what the user actually typed and asks Claude
to translate it into DAN's real command syntax (e.g. "what's it like
outside today" -> "weather Lagos"). This keeps costs low — DAN's own
keyword matching handles the vast majority of messages for free; the AI
call only fires as a fallback.

REQUIRES an Anthropic API key. Since this app is publicly distributed,
embedding a shared key in the APK is a real security risk (anyone can
extract it and run up charges on your account) — so each user supplies
their OWN key via 'setnluapikey <key>' (stored in APP_DATA, never shipped
in the app itself). Free/cheap keys are available at
https://console.anthropic.com

This is a good candidate for a premium-gated feature, since it's an
ongoing API cost per user, unlike everything else in the app which is
free API calls or purely local.
"""

import requests
import json

REQUEST_TIMEOUT = 15
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-3-5-haiku-20241022"  # fast and cheap, good enough for intent mapping

KNOWN_COMMAND_FORMATS = """
torch, torchoff, battery, alarm HH:MM, wifi, wifiscan, deviceinfo, vibrate, silent, soundon, volup, voldown, mute, batterysaver, batterysaveroff
open <app>, installedapps, settings <screen>, navigate <place>, showmap <place>, back, recents
call <number>, sms <number> <msg>, whatsapp <number> <msg>, readsms, emaildraft <addr> <subject>, findcontact <name>
weather <city>, wiki <topic>, news [topic], translate <lang> <text>, search <query>, scrape <url>
convert <amt> <from> <to>, dollar <amt>, crypto <coin>, budget, income <amt> [note], expense <amt> [note], expenses
task <text>, tasks, done <n>, deltask <n>, note <text>, notes, readnote <n>, delnote <n>, shop <item>, shopping, boughtshop <n>, clearshop, diary <text>, diaryread [n]
habit <name>, habits, habitdone <n>, delhabit <n>, workout <exercise> <reps>, workouts, sleep <hours>, sleeplog, medicine HH:MM <name>, meds, delmed <n>
remindme <min> <msg>, timer <min>, pomodoro, focus <min>, countdown YYYY-MM-DD <label>
joke, trivia, quote, story, wordoftheday
markspot <name>, spots, delspot <n>, whereami, locationhistory [n], remindatspot <name> <msg>
genpass [length], savepass <name> <pass>, getpass <name>, passnames, delpass <name>
record [sec], stoprecord, play, recordings, delrecording <n>
setbriefing HH:MM, briefingtime, stopbriefing, monitor <url>, monitored, stopmonitor <n>, checksites
remember <text> is <value>, recall <topic>, stats, conversations
createroutine <name>: <cmd1> | <cmd2> | ..., runroutine <name>, routines, delroutine <name>
"""

SYSTEM_PROMPT = (
    "You translate a user's casual message into ONE exact command from this "
    "list of formats (fill in the placeholders with what the user actually "
    "said):\n" + KNOWN_COMMAND_FORMATS +
    "\n\nReply with ONLY the resulting command text, nothing else — no "
    "explanation, no quotes, no punctuation around it. If nothing on this "
    "list reasonably matches what the user wants, reply with exactly: NONE"
)


def interpret(user_text, APP_DATA):
    """
    Returns a re-mapped command string (e.g. "weather Lagos") if Claude can
    confidently match the user's natural language to a known command format,
    or None if it can't / no API key is configured / the call fails.
    """
    api_key = (APP_DATA.get("nlu_api_key") or "").strip()
    if not api_key:
        return None

    try:
        response = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 60,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_text}],
            },
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            return None

        data = response.json()
        content = data.get("content", [])
        if not content:
            return None

        result = content[0].get("text", "").strip()
        if not result or result.upper() == "NONE":
            return None

        return result
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError, IndexError):
        return None
