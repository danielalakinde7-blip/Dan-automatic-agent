"""
modules/internet.py
DAN Automation Agent — Internet module

Features:
- weather <city>            -> current weather (OpenWeatherMap free tier)
- wiki <topic>               -> Wikipedia summary
- news [topic]                -> top headlines (NewsAPI free tier)
- translate <lang> <text>     -> translation (MyMemory free API, no key needed)
- search <query>              -> DuckDuckGo instant answer / web search
- scrape <url>                -> pull readable text from a page

Follows the same conventions as the other modules:
- Each public function takes the raw command text (after the keyword) and
  the shared APP_DATA dict, and returns a plain string reply for the chat bubble.
- Network functions fail soft: on any error they return a friendly
  "couldn't reach that / try again" message instead of raising.
- Premium gating (if any feature becomes premium-only later) should be
  checked in parser.py before calling into this module, same as other modules.

Requires: requests (pip install requests inside Termux / bundle via buildozer requirements)
"""

import requests

# ---------------------------------------------------------------------------
# CONFIG — put real free-tier API keys here before building the APK.
# Leaving a key blank disables that specific feature gracefully.
# ---------------------------------------------------------------------------
OPENWEATHER_API_KEY = ""   # https://openweathermap.org/api (free tier)
NEWSAPI_KEY = ""           # https://newsapi.org (free tier)

REQUEST_TIMEOUT = 10  # seconds — keep short, phone data can be slow


# ---------------------------------------------------------------------------
# WEATHER
# ---------------------------------------------------------------------------
def get_weather(city, APP_DATA):
    city = city.strip()
    if not city:
        return "Tell me a city — e.g. 'weather Lagos'."

    if not OPENWEATHER_API_KEY:
        return "Weather isn't set up yet — add your free OpenWeatherMap API key in internet.py."

    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
        }
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if r.status_code == 404:
            return f"Couldn't find a place called '{city}'."
        r.raise_for_status()
        data = r.json()

        desc = data["weather"][0]["description"].capitalize()
        temp = data["main"]["temp"]
        feels = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        wind = data["wind"]["speed"]
        name = data.get("name", city)

        return (
            f"Weather in {name}: {desc}, {temp:.0f}°C "
            f"(feels like {feels:.0f}°C), humidity {humidity}%, "
            f"wind {wind} m/s."
        )
    except requests.exceptions.RequestException:
        return "Couldn't reach the weather service — check your connection and try again."
    except (KeyError, IndexError):
        return "Got a weird response from the weather service. Try again in a bit."


# ---------------------------------------------------------------------------
# WIKIPEDIA
# ---------------------------------------------------------------------------
def get_wiki_summary(topic, APP_DATA):
    topic = topic.strip()
    if not topic:
        return "Give me a topic — e.g. 'wiki black holes'."

    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(topic)}"
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        if r.status_code == 404:
            return f"No Wikipedia page found for '{topic}'."
        r.raise_for_status()
        data = r.json()

        if data.get("type") == "disambiguation":
            return f"'{topic}' could mean a few things — try being more specific."

        extract = data.get("extract", "").strip()
        title = data.get("title", topic)
        if not extract:
            return f"Found '{title}' but there's no summary available."

        if len(extract) > 700:
            extract = extract[:700].rsplit(".", 1)[0] + "."

        return f"{title}: {extract}"
    except requests.exceptions.RequestException:
        return "Couldn't reach Wikipedia — check your connection and try again."


# ---------------------------------------------------------------------------
# NEWS
# ---------------------------------------------------------------------------
def get_news(topic, APP_DATA):
    topic = topic.strip()

    if not NEWSAPI_KEY:
        return "News isn't set up yet — add your free NewsAPI key in internet.py."

    try:
        if topic:
            url = "https://newsapi.org/v2/everything"
            params = {"q": topic, "sortBy": "publishedAt", "pageSize": 5, "apiKey": NEWSAPI_KEY}
        else:
            url = "https://newsapi.org/v2/top-headlines"
            params = {"country": "ng", "pageSize": 5, "apiKey": NEWSAPI_KEY}

        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()

        articles = data.get("articles", [])
        if not articles:
            return f"No news found{' for ' + topic if topic else ''} right now."

        lines = [f"Top headlines{' on ' + topic if topic else ''}:"]
        for i, a in enumerate(articles[:5], 1):
            title = a.get("title", "Untitled")
            source = a.get("source", {}).get("name", "")
            lines.append(f"{i}. {title} ({source})")

        return "\n".join(lines)
    except requests.exceptions.RequestException:
        return "Couldn't reach the news service — check your connection and try again."


# ---------------------------------------------------------------------------
# TRANSLATE  (MyMemory — free, no API key required)
# ---------------------------------------------------------------------------
def translate_text(command_text, APP_DATA):
    """
    Expected format: '<lang_code> <text to translate>'
    e.g. 'translate fr Good morning, how are you?'
    lang_code is the TARGET language (ISO 639-1, e.g. fr, es, yo, ha, ig).
    Source language is auto-detected as English by default (en|<target>).
    """
    parts = command_text.strip().split(" ", 1)
    if len(parts) < 2:
        return "Usage: translate <language code> <text> — e.g. 'translate fr good morning'."

    lang_code, text = parts[0].strip(), parts[1].strip()
    if not text:
        return "You gave me a language but no text to translate."

    try:
        url = "https://api.mymemory.translated.net/get"
        params = {"q": text, "langpair": f"en|{lang_code}"}
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()

        translated = data.get("responseData", {}).get("translatedText")
        if not translated:
            return "Couldn't translate that — try a different language code (e.g. fr, es, yo, ha, ig)."

        return f"'{text}' → {translated}"
    except requests.exceptions.RequestException:
        return "Couldn't reach the translation service — check your connection and try again."


# ---------------------------------------------------------------------------
# WEB SEARCH  (DuckDuckGo Instant Answer API — free, no key)
# ---------------------------------------------------------------------------
def web_search(query, APP_DATA):
    query = query.strip()
    if not query:
        return "What do you want me to search for?"

    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_redirect": 1, "no_html": 1, "skip_disambig": 1}
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()

        abstract = data.get("AbstractText", "").strip()
        if abstract:
            source = data.get("AbstractSource", "")
            return f"{abstract}" + (f" (via {source})" if source else "")

        related = data.get("RelatedTopics", [])
        snippets = []
        for item in related:
            if isinstance(item, dict) and item.get("Text"):
                snippets.append(item["Text"])
            if len(snippets) >= 3:
                break

        if snippets:
            lines = [f"Results for '{query}':"] + [f"- {s}" for s in snippets]
            return "\n".join(lines)

        return (
            f"Couldn't find a quick answer for '{query}'. "
            f"Try: https://duckduckgo.com/?q={requests.utils.quote(query)}"
        )
    except requests.exceptions.RequestException:
        return "Couldn't reach the search service — check your connection and try again."


# ---------------------------------------------------------------------------
# SCRAPE URL  (requests + BeautifulSoup)
# ---------------------------------------------------------------------------
def scrape_url(url, APP_DATA):
    url = url.strip()
    if not url:
        return "Give me a URL to scrape — e.g. 'scrape https://example.com'."

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        from bs4 import BeautifulSoup  # imported here so the module still loads without bs4 installed

        headers = {"User-Agent": "Mozilla/5.0 (DAN Automation Agent)"}
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else "Untitled page"

        text = " ".join(soup.get_text(separator=" ").split())
        if len(text) > 800:
            text = text[:800].rsplit(" ", 1)[0] + "..."

        if not text:
            return f"{title} — couldn't find readable text on that page."

        return f"{title}\n\n{text}"
    except ImportError:
        return "Scraping needs BeautifulSoup — install with: pip install beautifulsoup4"
    except requests.exceptions.RequestException:
        return "Couldn't reach that page — check the URL and your connection."


# ---------------------------------------------------------------------------
# ROUTER — called from modules/parser.py
# ---------------------------------------------------------------------------
def handle(keyword, rest, APP_DATA):
    """
    keyword: the first word of the command (e.g. 'weather', 'wiki', 'news',
             'translate', 'search', 'scrape')
    rest:    everything after the keyword, as typed by the user
    APP_DATA: shared app state dict from main.py

    Returns a reply string, or None if this module doesn't handle the keyword
    (lets parser.py fall through to its default "type help" message).
    """
    keyword = keyword.lower().strip()

    if keyword == "weather":
        return get_weather(rest, APP_DATA)
    elif keyword == "wiki":
        return get_wiki_summary(rest, APP_DATA)
    elif keyword == "news":
        return get_news(rest, APP_DATA)
    elif keyword == "translate":
        return translate_text(rest, APP_DATA)
    elif keyword == "search":
        return web_search(rest, APP_DATA)
    elif keyword == "scrape":
        return scrape_url(rest, APP_DATA)

    return None
