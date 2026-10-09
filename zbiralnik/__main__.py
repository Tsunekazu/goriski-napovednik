"""Zbiralnik: prebere vire iz podatki/viri.json in zapiše dogodke v podatki/dogodki/<vir>.json.
Zagon: python -m zbiralnik            (vsi viri)
       python -m zbiralnik sng-ng.si  (le izbrani viri)
Če vir odpove, ostanejo prejšnji podatki; napaka se zapiše v podatki/stanje.json."""
import datetime as dt
import json
import os
import re
import sys

from . import ai
from .bralniki import reader
from .skupno import TZ, window

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "podatki")
OUT = os.path.join(DATA, "dogodki")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def tidy(events):
    """Le dogodki v oknu, brez podvojenih, urejeni po času."""
    start, end = window()
    seen, out = set(), []
    for e in sorted(events, key=lambda e: (e.get("date") or "", e.get("time") or "99", e.get("title") or "")):
        k = (e.get("date"), e.get("time"), re.sub(r"\W+", "", (e.get("title") or "").lower()))
        if e.get("date") and e.get("title") and start <= e["date"] <= end and k not in seen:
            seen.add(k)
            out.append(e)
    return out


def collect(src, prev):
    """Lasten bralnik; če odpove in je na voljo AI, poskusi še z AI."""
    fn = reader(src)
    if fn is None:
        return tidy(ai.read(src, prev))
    try:
        return tidy(fn(src, prev))
    except Exception:
        if not ai.enabled():
            raise
        return tidy(ai.read(src, prev))


def main(only):
    viri = load(os.path.join(DATA, "viri.json"), [])
    stanje = load(os.path.join(DATA, "stanje.json"), {})
    now = dt.datetime.now(TZ).isoformat(timespec="minutes")
    os.makedirs(OUT, exist_ok=True)
    for src in viri:
        key = src["key"]
        if (only and key not in only) or (reader(src) is None and not (src["fetch"] == "ai" and ai.enabled())):
            continue
        path = os.path.join(OUT, key + ".json")
        prev = load(path, [])
        st = stanje.setdefault(key, {})
        try:
            events = collect(src, prev)
        except Exception as ex:
            st.update(error=f"{type(ex).__name__}: {ex}"[:300], failed=now)
            print(f"✗ {key}: {st['error']}")
            continue
        if not events and len(tidy(prev)) >= 3:
            st.update(error="0 dogodkov, prej jih je bilo več: morda se je stran spremenila", failed=now)
            print(f"? {key}: {st['error']}")
            continue
        save(path, events)
        st.update(ok=now, n=len(events))
        st.pop("error", None)
        st.pop("failed", None)
        print(f"✓ {key}: {len(events)}")
    save(os.path.join(DATA, "stanje.json"), stanje)


if __name__ == "__main__":
    main(set(sys.argv[1:]))
