"""
modules/entertainment.py
DAN Automation Agent — Entertainment module

Features:
- joke                -> random joke (free API, falls back to local bank offline)
- trivia               -> random trivia question (Open Trivia DB free API)
- quote                -> motivational quote (type.fit free API, falls back offline)
- story                -> short story from a local bank (works fully offline)
- wordoftheday         -> a word, its meaning, and example (local bank, offline)

Follows the same conventions as the other modules:
- Each public function takes the raw command text (after the keyword) and
  the shared APP_DATA dict, and returns a plain string reply for the chat bubble.
- Network functions fail soft: if the API call fails, they fall back to a
  local bank so entertainment features still work offline.

Requires: requests
"""

import random
import requests

REQUEST_TIMEOUT = 8


# ---------------------------------------------------------------------------
# LOCAL FALLBACK BANKS (used offline or if an API call fails)
# ---------------------------------------------------------------------------
LOCAL_JOKES = [
    "Why don't scientists trust atoms? Because they make up everything.",
    "I told my computer I needed a break, and now it won't stop sending me KitKats.",
    "Why did the developer go broke? Because they used up all their cache.",
    "Parallel lines have so much in common. It's a shame they'll never meet.",
    "Why do programmers prefer dark mode? Because light attracts bugs.",
]

LOCAL_QUOTES = [
    "Small steps every day still get you there.",
    "Discipline is choosing what you want most over what you want now.",
    "You don't have to be great to start, but you have to start to be great.",
    "Progress, not perfection.",
    "The best time to plant a tree was 20 years ago. The second best time is now.",
]

LOCAL_STORIES = [
    (
        "The Tortoise's Patience: A tortoise once challenged a hare to a race. "
        "The hare laughed and sprinted ahead, then stopped to nap, certain of victory. "
        "The tortoise kept moving, slow and steady, and crossed the finish line while "
        "the hare was still asleep. Sometimes steady effort beats a burst of speed."
    ),
    (
        "The Full Cup: A young man asked a teacher to share his wisdom. The teacher "
        "poured tea into the man's cup until it overflowed. 'Your mind is like this "
        "cup,' the teacher said. 'Too full of your own ideas to receive anything new. "
        "Come back when it's empty.'"
    ),
    (
        "The Two Wolves: An old woman told her grandson that inside every person two "
        "wolves fight — one of fear, one of courage. 'Which one wins?' the boy asked. "
        "'Whichever one you feed,' she said."
    ),
]

WORD_BANK = [
    ("Resilience", "The ability to recover quickly from difficulties.",
     "Her resilience helped her rebuild the business after it failed the first time."),
    ("Ephemeral", "Lasting for a very short time.",
     "The beauty of the sunset was ephemeral, gone in minutes."),
    ("Tenacity", "Firmness in holding to a purpose or course of action.",
     "His tenacity is why he finally finished the app after months of setbacks."),
    ("Serendipity", "Finding something good without looking for it.",
     "Meeting his business partner on that bus was pure serendipity."),
    ("Diligent", "Showing care and effort in one's work or duties.",
     "She was diligent about logging every expense, no matter how small."),
]


# ---------------------------------------------------------------------------
# JOKE
# ---------------------------------------------------------------------------
def get_joke(text, APP_DATA):
    try:
        url = "https://official-joke-api.appspot.com/random_joke"
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        setup = data.get("setup", "").strip()
        punchline = data.get("punchline", "").strip()
        if setup and punchline:
            return f"{setup}\n{punchline}"
    except requests.exceptions.RequestException:
        pass

    return random.choice(LOCAL_JOKES)


# ---------------------------------------------------------------------------
# TRIVIA
# ---------------------------------------------------------------------------
def get_trivia(text, APP_DATA):
    try:
        url = "https://opentdb.com/api.php"
        params = {"amount": 1, "type": "multiple"}
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()

        results = data.get("results", [])
        if not results:
            return "Couldn't fetch a trivia question right now — try again shortly."

        q = results[0]
        question = _unescape_html(q.get("question", ""))
        correct = _unescape_html(q.get("correct_answer", ""))
        incorrect = [_unescape_html(a) for a in q.get("incorrect_answers", [])]

        options = incorrect + [correct]
        random.shuffle(options)

        lines = [f"Trivia: {question}"]
        letters = ["A", "B", "C", "D"]
        for letter, opt in zip(letters, options):
            lines.append(f"{letter}. {opt}")
        lines.append(f"(Answer: {correct})")

        return "\n".join(lines)
    except requests.exceptions.RequestException:
        return "Couldn't reach the trivia service — check your connection and try again."


def _unescape_html(text):
    replacements = {
        "&quot;": '"', "&#039;": "'", "&amp;": "&",
        "&lt;": "<", "&gt;": ">", "&eacute;": "e",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


# ---------------------------------------------------------------------------
# MOTIVATIONAL QUOTE
# ---------------------------------------------------------------------------
def get_quote(text, APP_DATA):
    try:
        url = "https://type.fit/api/quotes"
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            pick = random.choice(data)
            quote_text = pick.get("text", "").strip()
            author = (pick.get("author") or "Unknown").split(",")[0].strip()
            if quote_text:
                return f'"{quote_text}" — {author}'
    except requests.exceptions.RequestException:
        pass

    return random.choice(LOCAL_QUOTES)


# ---------------------------------------------------------------------------
# STORY (offline — local bank)
# ---------------------------------------------------------------------------
def get_story(text, APP_DATA):
    return random.choice(LOCAL_STORIES)


# ---------------------------------------------------------------------------
# WORD OF THE DAY (offline — local bank)
# ---------------------------------------------------------------------------
def get_word_of_the_day(text, APP_DATA):
    word, meaning, example = random.choice(WORD_BANK)
    return f"{word}: {meaning}\nExample: {example}"


# ---------------------------------------------------------------------------
# ROUTER — called from modules/parser.py
# ---------------------------------------------------------------------------
def handle(keyword, rest, APP_DATA):
    """
    keyword: first word of the command (e.g. 'joke', 'trivia', 'quote',
             'story', 'wordoftheday')
    rest:    everything after the keyword, as typed by the user
    APP_DATA: shared app state dict from main.py

    Returns a reply string, or None if this module doesn't handle the keyword.
    NOTE: no APP_DATA mutation happens here, so no save_data() call needed
    from parser.py for this module.
    """
    keyword = keyword.lower().strip()

    if keyword == "joke":
        return get_joke(rest, APP_DATA)
    elif keyword == "trivia":
        return get_trivia(rest, APP_DATA)
    elif keyword == "quote":
        return get_quote(rest, APP_DATA)
    elif keyword == "story":
        return get_story(rest, APP_DATA)
    elif keyword == "wordoftheday":
        return get_word_of_the_day(rest, APP_DATA)

    return None
