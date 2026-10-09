"""Branje navadnih spletnih strani s Claudom. Deluje le, če je nastavljen ANTHROPIC_API_KEY (skrivnost v GitHubu).
Model izbereš s spremenljivko AI_MODEL: claude-haiku-5-5 (približno 1 $ na mesec) ali claude-opus-5-5 (privzeto, dražji)."""
import json
import os
import re

from .skupno import CATS, area, clean, event, get, hhmm, nice_title, price_from, today, venue_name, window

MODEL = os.environ.get("AI_MODEL") or "claude-opus-5-5"
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}

SCHEMA = {
    "type": "object",
    "properties": {"events": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "YYYY-MM-DD"},
            "time": {"type": "string", "description": "HH:MM, or empty if the page gives no start time"},
            "title": {"type": "string"},
            "venue": {"type": "string"},
            "place": {"type": "string", "description": "town or village, or empty"},
            "category": {"type": "string", "enum": ["glasba", "gledalisce", "film", "other"]},
            "price": {"type": "string", "description": "ticket price as written, 'free', or empty"},
            "url": {"type": "string", "description": "link to the event's own page, or empty"},
        },
        "required": ["date", "time", "title", "venue", "place", "category", "price", "url"],
        "additionalProperties": False,
    }}},
    "required": ["events"],
    "additionalProperties": False,
}

PROMPT = """Below is the text of the events page of {name} ({url}). Today is {today}.
List every public event on the page that takes place between {start} and {end}.
Use category "glasba" for concerts and other live music, "gledalisce" for theatre, dance, opera and other stage shows,
"film" for screenings, and "other" for everything else (exhibitions, talks, workshops, sport, markets).
If a date has no year, pick the year that puts it nearest to today. Copy titles as written.
Leave a field empty when the page doesn't say. Never invent events or details.

<page>
{text}
</page>"""


def enabled():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def page_text(html):
    """Besedilo strani s povezavami v oglatih oklepajih, da model lahko vrne naslov dogodka."""
    html = re.sub(r"(?is)<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r'(?is)<a\s[^>]*href="(http[^"]+)"[^>]*>(.*?)</a>', r"\2 [\1]", html)
    return clean(html)[:60000]


def read(src, prev):
    import anthropic

    start, end = window()
    text = page_text(get(src["url"]))
    params = dict(model=MODEL, max_tokens=16000,
                  messages=[{"role": "user", "content": PROMPT.format(name=src["name"], url=src["url"], today=today(),
                                                                       start=start, end=end, text=text)}],
                  output_config={"format": {"type": "json_schema", "schema": SCHEMA}})
    client = anthropic.Anthropic()
    if MODEL in FALLBACK_MODELS:
        r = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params)
    else:
        r = client.messages.create(**params)
    if r.stop_reason == "refusal":
        raise RuntimeError("model je zavrnil zahtevo")
    data = json.loads(next(b.text for b in r.content if b.type == "text"))
    low = text.lower()
    default_city = "NG" if src["side"] == "SI" else "GO"
    out = []
    for e in data.get("events", []):
        title = clean(e.get("title"))
        if e.get("category") not in CATS or not title or not (start <= e.get("date", "") <= end):
            continue
        if title.lower()[:15] not in low:  # naslova ni na strani: verjetno izmišljen
            continue
        city = area(f"{e.get('place', '')} {e.get('venue', '')}") or (None if e.get("place") else default_city)
        if not city:
            continue
        m = re.match(r"(\d{1,2})[:.](\d{2})$", e.get("time") or "")
        price, free = price_from(e.get("price")) if e.get("price") not in ("", "free") else (None, e.get("price") == "free")
        url = e.get("url") if (e.get("url") or "").startswith("http") else src["url"]
        out.append(event(src["key"], e["date"], nice_title(title), venue_name(e.get("venue", ""), e.get("venue") or src["name"]),
                         city, e["category"], hhmm(*m.groups()) if m else None, None, url, price, free))
    return out
