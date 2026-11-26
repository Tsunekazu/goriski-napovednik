"""Združi podatke iz ../podatki/dogodki/*.json, odstrani podvojene in zgradi ../_site/index.html."""
import datetime as dt
import html
import json
import os
import re
from collections import Counter
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "podatki")
OUT = os.path.join(ROOT, "_site")
CATS = {"glasba", "gledalisce", "film"}
DAYS = 91  # obzorje: danes + 91 dni (stran prikaže 92 dni)
STALE_DAYS = 3  # redni vir, ki se toliko dni ni posodobil, je v nogi označen
AI_STALE_DAYS = 14  # AI viri se preverjajo na nekaj dni ali ročno
FIELDS = ("date", "time", "title", "sub", "venue", "city", "cat", "url", "price", "free", "regular", "ring")


def clean_sub(sub):
    """Odstrani podvojene ponovitve (npr. 'Abonma · Velika dvorana – Abonma')."""
    if not sub:
        return None
    parts = [p.strip() for p in sub.split(" · ") if p.strip()]
    if len(parts) == 2 and parts[0].lower() in parts[1].lower():
        parts[1] = re.sub(r"\s*[–—-]\s*" + re.escape(parts[0]) + r"\s*$", "", parts[1], flags=re.I).strip()
        if parts[1].lower() == parts[0].lower():
            parts.pop()
    return " · ".join(p for p in parts if p) or None


def norm(s):
    s = html.unescape(s or "").lower()
    s = re.sub(r"[^\w]+", " ", s)
    return " ".join(s.split())


COMMON = {"festival", "koncert", "gorizia", "gorica", "komedija", "predstava", "musical", "concerto", "teatro"}


def words(e):
    return {w for w in norm(e["title"]).split() if len(w) >= 5 and w not in COMMON}


def same(k, e):
    """Moč ujemanja dveh dogodkov z različnih virov (0 = različna dogodka)."""
    if k["date"] != e["date"] or k.get("src") == e.get("src") or k.get("regular") or e.get("regular"):
        return 0
    tk, te = norm(k["title"]), norm(e["title"])
    times_ok = not k.get("time") or not e.get("time") or k["time"] == e["time"]
    if times_ok and (tk[:18] == te[:18] or (min(len(tk), len(te)) >= 5 and (tk.startswith(te) or te.startswith(tk)))):
        return 3
    if norm(k["venue"]) == norm(e["venue"]):
        if times_ok and words(k) & words(e):
            return 2
        if k.get("time") and k["time"] == e.get("time"):
            return 1
    return 0


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def load(viri, start, end):
    prio = {s["key"]: s.get("prio", 9) for s in viri}
    prio["rocni"] = 0
    events = []
    sources_data = [(s["key"], read_json(os.path.join(DATA, "dogodki", s["key"] + ".json"), [])) for s in viri]
    manual = read_json(os.path.join(DATA, "rocni.json"), [])
    if isinstance(manual, list) and manual:
        sources_data.append(("rocni", manual))
    for key, items in sources_data:
        for raw in items:
            if not isinstance(raw, dict):
                continue
            e = dict(raw)
            e.setdefault("src", key)
            if (e.get("cat") in CATS and e.get("city") in ("NG", "GO") and e.get("title")
                    and start <= e.get("date", "") <= end):
                if not re.match(r"https?://", e.get("url") or ""):
                    e.pop("url", None)
                if e.get("sub"):
                    e["sub"] = clean_sub(e["sub"])
                    if not e["sub"]:
                        e.pop("sub", None)
                events.append(e)
    # isti dogodek na več virih: obdržimo zapis z glavnega vira (najnižji prio), manjkajoče podatke dopolnimo z drugih
    events.sort(key=lambda e: (e["date"], prio.get(e.get("src"), 9), e.get("time") or "99", -len(e.get("sub") or "")))
    kept = []
    for e in events:
        score, i = max(((same(k, e), i) for i, k in enumerate(kept)), default=(0, -1))
        if score:
            k = kept[i]
            k.setdefault("also", []).append(e.get("src"))
            for f in ("time", "sub", "price", "free", "url"):
                if not k.get(f) and e.get(f):
                    k[f] = e[f]
            continue
        kept.append(e)
    kept.sort(key=lambda e: (e["date"], e.get("time") or "99", e["title"]))
    by_src = Counter()
    for e in kept:
        by_src[e.get("src")] += 1
        for s in e.get("also", []):
            by_src[s] += 1
    return kept, by_src


def main():
    today = dt.datetime.now(ZoneInfo("Europe/Ljubljana")).date()
    harvest = os.environ.get("HARVEST") or today.isoformat()
    end = (dt.date.fromisoformat(harvest) + dt.timedelta(days=DAYS)).isoformat()
    viri = read_json(os.path.join(DATA, "viri.json"), [])
    stanje = read_json(os.path.join(DATA, "stanje.json"), {})
    events, by_src = load(viri, harvest, end)

    # v nogi le viri, ki jih res beremo; tisti, ki se dlje časa niso posodobili, dobijo datum zadnje posodobitve
    sources = []
    for s in viri:
        st = stanje.get(s["key"]) or {}
        ok = st.get("checked") or st.get("ok") if s.get("fetch") == "ai" else st.get("ok")
        if not ok:
            continue
        if s.get("fetch") == "ai" and not by_src.get(s["key"]) and s.get("status") != "active":
            continue
        src = {"name": s["name"], "url": s["url"]}
        last = dt.date.fromisoformat(ok[:10])
        limit = AI_STALE_DAYS if s.get("fetch") == "ai" else STALE_DAYS
        if (today - last).days >= limit or st.get("error"):
            src["stale"] = f"{last.day}. {last.month}. {last.year}"
        sources.append(src)

    public = [{k: v for k, v in e.items() if k in FIELDS} for e in events]
    as_js = lambda x: json.dumps(x, ensure_ascii=False, indent=0).replace("<", "\\u003c")
    page = open(os.path.join(HERE, "index.template.html"), encoding="utf-8").read()
    page = page.replace("/*__EVENTS__*/[]", as_js(public))
    page = page.replace("/*__SOURCES__*/[]", as_js(sources))
    page = page.replace("/*__HARVEST__*/", harvest)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)

    nonreg = [e for e in events if not e.get("regular")]
    ring = [e for e in nonreg if e.get("ring")]
    print(f"{len(events)} dogodkov ({len(nonreg)} brez rednega kino sporeda, {len(ring)} v okolici), {harvest} – {end}")
    print("po mesecih:", dict(sorted(Counter(e["date"][:7] for e in nonreg).items())))
    print("po zvrsteh:", dict(Counter(e["cat"] for e in nonreg)))
    print("po virih:", dict(by_src))
    print("združeni dvojniki:", [(e["date"], e["title"][:24], e.get("src"), e["also"]) for e in events if e.get("also")])


if __name__ == "__main__":
    main()
