"""Poceni branje navadnih spletnih strani z AI (Gemini ali Claude) in hash-predpomnjenjem.

Deluje z enim od obeh ključev (skrivnost v GitHub Actions ali okoljska spremenljivka):
- GEMINI_API_KEY   -> privzeto gemini-2.5-flash (brez dodatnih knjižnic; brezplačni nivo ali centi/mesec)
- ANTHROPIC_API_KEY -> privzeto claude-haiku-5-5 (~0,20–1 $/mesec s hash-predpomnjenjem)

Model lahko vedno preglasiš z AI_MODEL.
"""
import hashlib
import json
import os
import re
import urllib.request

from .skupno import CATS, area_zone, clean, event, get, hhmm, nice_title, price_from, today, venue_name, window

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-5-5"
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}

EVENT_PROPS = {
    "date": {"type": "string", "description": "YYYY-MM-DD"},
    "time": {"type": "string", "description": "HH:MM, or empty if the page gives no start time"},
    "title": {"type": "string"},
    "venue": {"type": "string"},
    "place": {"type": "string", "description": "town or village, or empty"},
    "category": {"type": "string", "enum": ["glasba", "gledalisce", "film", "other"]},
    "price": {"type": "string", "description": "ticket price as written, 'free', or empty"},
    "url": {"type": "string", "description": "link to the event's own page, or empty"},
}
EVENT_REQ = ["date", "time", "title", "venue", "place", "category", "price", "url"]

ANTHROPIC_SCHEMA = {
    "type": "object",
    "properties": {"events": {"type": "array", "items": {
        "type": "object",
        "properties": EVENT_PROPS,
        "required": EVENT_REQ,
        "additionalProperties": False,
    }}},
    "required": ["events"],
    "additionalProperties": False,
}

GEMINI_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "events": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "date": {"type": "STRING"},
                    "time": {"type": "STRING"},
                    "title": {"type": "STRING"},
                    "venue": {"type": "STRING"},
                    "place": {"type": "STRING"},
                    "category": {"type": "STRING", "enum": ["glasba", "gledalisce", "film", "other"]},
                    "price": {"type": "STRING"},
                    "url": {"type": "STRING"},
                },
                "required": EVENT_REQ,
            },
        }
    },
    "required": ["events"],
}

PROMPT = """Below is the text of the events page of {name} ({url}). Today is {today}.
List every public event on the page that takes place between {start} and {end}.
Use category "glasba" for concerts and other live music, "gledalisce" for theatre, dance, opera and other stage shows,
"film" for screenings, and "other" for everything else (exhibitions, talks, workshops, sport, markets).
If a date has no year, pick the year that puts it nearest to today. Copy titles as written.
Leave a field empty when the page doesn't say. Never invent events or details.
{note}
<page>
{text}
</page>"""


def provider():
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def enabled():
    return provider() is not None


def page_text(html):
    """Besedilo strani s povezavami v oglatih oklepajih, da model lahko vrne naslov dogodka."""
    html = re.sub(r"(?is)<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r'(?is)<a\s[^>]*href="(http[^"]+)"[^>]*>(.*?)</a>', r"\2 [\1]", html)
    return clean(html)[:60000]


def page_hash(text):
    """Kratek prstni odtis besedila strani za preskakovanje nespremenjenih strani."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def fetch_page(src):
    text = page_text(get(src["url"]))
    return text, page_hash(text)


def _title_grounded(title, page_low):
    if not page_low:
        return True
    low = title.lower()
    if low[:14] in page_low:
        return True
    words = [w for w in re.findall(r"[^\W\d_]{4,}", low)]
    if not words:
        return True
    hits = sum(1 for w in words if w in page_low)
    return hits >= max(1, (len(words) + 1) // 2)


def normalize_events(src, raw_events, page_text_str=None):
    """Preveri in uredi dogodke (uporablja tako API kot ročni --apply-ai)."""
    start, end = window()
    page_low = (page_text_str or "").lower()
    default_city = "NG" if src["side"] == "SI" else "GO"
    out = []
    for e in raw_events or []:
        if not isinstance(e, dict):
            continue
        title = clean(e.get("title"))
        cat = e.get("category") or e.get("cat")
        date = (e.get("date") or "").strip()
        if cat not in CATS or not title or not (start <= date <= end):
            continue
        if page_low and not _title_grounded(title, page_low):
            continue
        place = e.get("place") or ""
        venue_raw = e.get("venue") or ""
        city_explicit = e.get("city") if e.get("city") in ("NG", "GO") else None
        city, ring = area_zone(f"{place} {venue_raw}")
        if not city and not place:
            city = city_explicit or default_city
            ring = bool(e.get("ring")) if "ring" in e else (src.get("zone") == "ring")
        if not city:
            continue
        m = re.match(r"(\d{1,2})[:.](\d{2})$", (e.get("time") or "").strip())
        raw_price = (e.get("price") or "").strip()
        if e.get("free") is True or raw_price.lower() in ("free", "prost vstop", "brezplačno", "ingresso libero"):
            price, free = None, True
        elif raw_price:
            price, free = price_from(raw_price)
        else:
            price, free = None, False
        url = e.get("url") if (e.get("url") or "").startswith("http") else src["url"]
        sub = clean(e.get("sub")) or None
        out.append(event(src["key"], date, nice_title(title), venue_name(venue_raw, venue_raw or src["name"]),
                         city, cat, hhmm(*m.groups()) if m else None, sub, url, price, free, ring=ring))
    return out


def _call_gemini(prompt):
    api_key = os.environ["GEMINI_API_KEY"]
    model = os.environ.get("AI_MODEL") or DEFAULT_GEMINI_MODEL
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": GEMINI_SCHEMA,
            "temperature": 0.1,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        resp = json.loads(r.read().decode("utf-8"))
    parts = resp.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    raw = next((p["text"] for p in parts if "text" in p), "{}")
    return json.loads(raw)


def _call_anthropic(prompt):
    import anthropic

    model = os.environ.get("AI_MODEL") or DEFAULT_ANTHROPIC_MODEL
    params = dict(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": ANTHROPIC_SCHEMA}},
    )
    client = anthropic.Anthropic()
    if model in FALLBACK_MODELS:
        r = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params)
    else:
        r = client.messages.create(**params)
    if r.stop_reason == "refusal":
        raise RuntimeError("model je zavrnil zahtevo")
    return json.loads(next(b.text for b in r.content if b.type == "text"))


def extract(src, text):
    start, end = window()
    note = f"Source note: {src['how']}\n" if src.get("how") else ""
    prompt = PROMPT.format(name=src["name"], url=src["url"], today=today(), start=start, end=end, note=note, text=text)
    prov = provider()
    if prov == "gemini":
        data = _call_gemini(prompt)
    elif prov == "anthropic":
        data = _call_anthropic(prompt)
    else:
        raise RuntimeError("AI ključ ni nastavljen (GEMINI_API_KEY ali ANTHROPIC_API_KEY)")
    return normalize_events(src, data.get("events", []), page_text_str=text)


def read(src, prev, prefetched=None):
    text = prefetched if prefetched is not None else fetch_page(src)[0]
    return extract(src, text)
