"""Bralniki virov. Vsak dobi vnos iz podatki/viri.json in prejšnje dogodke tega vira, vrne seznam dogodkov.
Ob napaki sprožijo izjemo; zbiralnik takrat obdrži prejšnje podatke."""
import datetime as dt
import re
import time
import urllib.parse
from collections import defaultdict
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .skupno import (MONTH_RX, MONTHS, SKIP_RX, TZ, area, clean, event, get, get_json, guess_cat, guess_year, hhmm, nice_title,
                     price_from, today, venue_name, window, ymd)


def soup_of(url, **kw):
    return BeautifulSoup(get(url, **kw), "html.parser")


def txt(el):
    return clean(str(el)) if el is not None else ""


SMALL = {"e", "ed", "di", "da", "del", "della", "dei", "il", "la", "le", "lo", "in", "za", "na", "v", "z", "s", "the", "of", "and", "a"}


def nice_label(s):
    """Oznaka (festival, organizator) s samimi velikimi črkami: vsaka beseda z veliko začetnico."""
    s = clean(s)
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 4 or sum(c.isupper() for c in letters) / len(letters) < 0.8:
        return s
    words = s.lower().split(" ")
    return " ".join(w if (i and w in SMALL) else w[:1].upper() + w[1:] for i, w in enumerate(words))


def split_title(raw):
    """'NASLOV – dodatek' razdeli na naslov in podnaslov."""
    parts = re.split(r"\s+[–—]\s+|\s+-\s+", clean(raw), maxsplit=1)
    return nice_title(parts[0]), (nice_label(parts[1]) if len(parts) > 1 else None)


# ——— The Events Calendar (WordPress REST) ———

def tribe_events(base):
    start, end = window()
    q = urllib.parse.urlencode({"per_page": 50, "start_date": start, "end_date": end + " 23:59:59"})
    url, out, seen = f"{base}/wp-json/tribe/events/v1/events?{q}", [], set()
    while url and url not in seen:
        seen.add(url)
        d = get_json(url)
        out += d.get("events") or []
        url = d.get("next_rest_url")
    return out


def tribe_when(e):
    s = e.get("start_date") or ""
    t = None if e.get("all_day") else hhmm(s[11:13], s[14:16])
    return s[:10], (None if t == "00:00" else t)


def tribe_venue(e):
    v = e.get("venue") if isinstance(e.get("venue"), dict) else {}
    return clean(v.get("venue", "")), clean(" ".join(str(v.get(k) or "") for k in ("address", "city")))


def kdgo(src, prev):
    """Kulturni dom Gorica: kategorije na strani povedo zvrst."""
    out = []
    for e in tribe_events(src["fetch"].split(":", 1)[1]):
        cats = " ".join(c.get("name", "") for c in e.get("categories") or [])
        if re.search(r"koncert", cats, re.I):
            cat = "glasba"
        elif re.search(r"gledali|predstav|balet|ples", cats, re.I):
            cat = "gledalisce"
        elif re.search(r"film|kino", cats, re.I):
            cat = "film"
        else:
            cat = guess_cat(f"{e.get('title', '')} {cats}")
        if not cat:
            continue
        date, tm = tribe_when(e)
        title, sub = split_title(e.get("title", ""))
        vname, vplace = tribe_venue(e)
        price, free = price_from(e.get("cost") or "")
        out.append(event(src["key"], date, title, venue_name(f"{vname} {vplace}", "Kulturni dom Gorica"),
                         area(f"{vname} {vplace}") or "GO", cat, tm, sub, e.get("url"), price, free))
    return out


def robin(src, prev):
    """Radio Robin: regionalni koledar, naslovi so oblike 'KRAJ, prizorišče - Opis'."""
    out = []
    for e in tribe_events(src["fetch"].split(":", 1)[1]):
        raw = clean(e.get("title", ""))
        head, sep, desc = raw.partition(" - ")
        if not sep:
            continue
        parts = [p.strip() for p in head.split(",") if p.strip()]
        places = [p for p in parts if p == p.upper()]
        venue = ", ".join(p for p in parts if p != p.upper())
        city = area(" ".join(places))
        cat = guess_cat(desc)
        if not city or not cat:
            continue
        label, colon, rest = desc.partition(": ")
        sub = None
        if colon and len(label.split()) >= 2:
            sub, desc = label, rest
        title = re.sub(r"^(film|predstava|koncert|gledališka predstava)\s*:?\s+", "", desc.strip(), flags=re.I)
        date, tm = tribe_when(e)
        out.append(event(src["key"], date, nice_title(title), venue_name(f"{venue} {' '.join(places)}", venue or places[0].title()),
                         city, cat, tm, sub, e.get("url")))
    return out


def tribe_generic(src, prev):
    """Krovne zveze (ZKD, ZSKP): zvrst po ključnih besedah v naslovu in kategorijah."""
    out = []
    default_city = "NG" if src["side"] == "SI" else "GO"
    for e in tribe_events(src["fetch"].split(":", 1)[1]):
        cats = " ".join(c.get("name", "") for c in e.get("categories") or [])
        cat = guess_cat(f"{e.get('title', '')} {cats}")
        if not cat:
            continue
        vname, vplace = tribe_venue(e)
        city = area(f"{vname} {vplace}") if (vname or vplace) else default_city
        if not city:
            continue
        date, tm = tribe_when(e)
        title, sub = split_title(e.get("title", ""))
        price, free = price_from(e.get("cost") or "")
        out.append(event(src["key"], date, title, venue_name(f"{vname} {vplace}", vname or src["name"]), city, cat, tm, sub,
                         e.get("url"), price, free))
    return out


# ——— iCal ———

def ical_unescape(v):
    return re.sub(r"\\([,;\\])", r"\1", v.replace("\\n", " ").replace("\\N", " ")).strip()


def ical_events(url):
    s = get(url).replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"\n[ \t]", "", s)  # razgrnjene vrstice
    out = []
    for block in re.findall(r"BEGIN:VEVENT\n(.*?)\nEND:VEVENT", s, re.S):
        ev = {}
        for line in block.split("\n"):
            name, sep, value = line.partition(":")
            if sep:
                key, *params = name.split(";")
                ev.setdefault(key.upper(), (params, ical_unescape(value)))
        out.append(ev)
    return out


def ical_when(prop):
    """(datum, ura) iz DTSTART/DTEND; čas v UTC ali drugem pasu pretvori v slovenskega."""
    if not prop:
        return None, None
    params, v = prop
    m = re.match(r"(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})\d{2}(Z)?)?", v)
    if not m:
        return None, None
    y, mo, d, h, mi, z = m.groups()
    if h is None:
        return ymd(y, mo, d), None
    t = dt.datetime(int(y), int(mo), int(d), int(h), int(mi))
    tzid = next((p.split("=", 1)[1] for p in params if p.upper().startswith("TZID=")), None)
    try:
        t = t.replace(tzinfo=dt.timezone.utc if z else ZoneInfo(tzid) if tzid else TZ).astimezone(TZ)
    except Exception:
        pass
    tm = t.strftime("%H:%M")
    return t.date().isoformat(), (None if tm == "00:00" else tm)


def ical_span_days(ev):
    d0, _ = ical_when(ev.get("DTSTART"))
    d1, _ = ical_when(ev.get("DTEND"))
    if not d0 or not d1:
        return 0
    return (dt.date.fromisoformat(d1) - dt.date.fromisoformat(d0)).days


def val(ev, key):
    return ev.get(key, ([], ""))[1]


def aa(src, prev):
    """ArtistiAssociati: kategorije sezone povedo zvrst, LOCATION kraj (večina v Krminu in Gradišču)."""
    out = []
    for ev in ical_events(src["fetch"].split(":", 1)[1]):
        cats, loc, summ = val(ev, "CATEGORIES"), val(ev, "LOCATION"), val(ev, "SUMMARY")
        if ical_span_days(ev) > 1 or re.search(r"laborator|scuola|corso", f"{cats} {summ}", re.I):
            continue
        if re.search(r"cinema", cats, re.I):
            cat = "film"
        elif re.search(r"teatro|danza|innesti|ragazzi", cats, re.I):
            cat = "gledalisce"
        else:
            cat = guess_cat(f"{summ} {cats}")
        city = area(loc)
        if not cat or not city:
            continue
        date, tm = ical_when(ev.get("DTSTART"))
        sub = nice_label(re.sub(r"\s*[-–]?\s*(stagione\s*)?20\d\d/(20)?\d\d\s*$", "", cats.split(",")[0], flags=re.I))
        out.append(event(src["key"], date, nice_title(summ), venue_name(loc, loc.split(",")[0]), city, cat, tm, sub or None,
                         val(ev, "URL") or None))
    return out


def zskd(src, prev):
    """ZSKD: koledar vseh slovenskih društev v Italiji; obdržimo le dogodke, ki omenjajo kraj z našega območja."""
    out = []
    for ev in ical_events(src["fetch"].split(":", 1)[1]):
        summ, loc = val(ev, "SUMMARY"), val(ev, "LOCATION")
        m = re.match(r"(.*?)\s*\(([^()]*)\)\s*$", summ)
        title, society = (m.group(1), m.group(2)) if m else (summ, "")
        city, cat = area(f"{summ} {loc}"), guess_cat(title)
        if not city or not cat or ical_span_days(ev) > 1:
            continue
        date, tm = ical_when(ev.get("DTSTART"))
        link = re.search(r"https?://[^\s\"<>]+", val(ev, "DESCRIPTION"))
        out.append(event(src["key"], date, nice_title(title), venue_name(loc, loc or society or "Gorica"), city, cat, tm,
                         society or None, link.group(0) if link else None))
    return out


def scopri(src, prev):
    """Scopri Gorizia: mestni turistični koledar; ura je kvečjemu v opisu."""
    out = []
    for ev in ical_events(src["fetch"].split(":", 1)[1]):
        summ, desc = val(ev, "SUMMARY"), clean(val(ev, "DESCRIPTION"))
        if ical_span_days(ev) > 1 or SKIP_RX.search(f"{summ} {desc[:300]}"):
            continue
        cat = guess_cat(summ) or guess_cat(desc[:300])
        if not cat:
            continue
        date, tm = ical_when(ev.get("DTSTART"))
        m = re.search(r"(?:alle|ore|dalle)\s*(?:ore\s*)?(\d{1,2})[.:](\d{2})", desc, re.I)
        tm = tm or (hhmm(m.group(1), m.group(2)) if m else None)
        out.append(event(src["key"], date, nice_title(summ), venue_name(desc, "Gorizia"), "GO", cat, tm, None, val(ev, "URL") or None))
    return out


# ——— lastni bralniki za velika prizorišča ———

def kdng(src, prev):
    """Kulturni dom Nova Gorica: en dolg seznam; cene so na strani dogodka (shranimo jih in beremo le za nove dogodke)."""
    known = {e["url"]: e for e in prev if e.get("url")}
    out, fetched = [], 0
    for art in soup_of(src["url"]).select("div.events-article"):
        a = art.find("a", href=True)
        when = txt(art.select_one(".events-article__date"))
        m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", when)
        hm = re.search(r"(\d{1,2})[.:](\d{2})\s*$", when)
        line = art.select_one(".events-article__line")
        kind = line.get("data-type", "") if line else ""
        typ, raw, hall = (txt(art.select_one(f".events-article__{k}")) for k in ("type", "title", "place"))
        if not (a and m) or "culture-education" in kind or "gallery" in kind or re.search(r"zaključen", raw, re.I):
            continue
        cat = "film" if "movie" in kind else "glasba" if "music" in kind else guess_cat(f"{typ} {raw}", "gledalisce")
        if not cat:
            continue
        url = a["href"]
        if url in known:
            price, free = known[url].get("price"), known[url].get("free")
        elif fetched < 40:
            fetched += 1
            price, free = kdng_price(url)
            time.sleep(0.3)
        else:
            price = free = None
        sub = " · ".join(x for x in (typ if typ not in ("Kino", "Gostujoča prireditev") else "", hall) if x)
        out.append(event(src["key"], ymd(m.group(3), m.group(2), m.group(1)), nice_title(raw), "Kulturni dom Nova Gorica", "NG",
                         cat, hhmm(*hm.groups()) if hm else None, sub, url, price, free))
    return out


def kdng_price(url):
    try:
        t = clean(get(url))
    except Exception:
        return None, None
    m = re.search(r"Cen\w* vstopnic\w*(.{0,160})", t)
    return price_from(m.group(1)) if m else (None, None)


SNG_OWN = re.compile(r"\boder\b|foyer|preddverj|dvoran|sng", re.I)


def sng(src, prev):
    """SNG Nova Gorica: spored po mesecih; naslednji mesec objavijo pozno."""
    out, t = [], today()
    for i in range(3):
        y, mth = t.year + (t.month - 1 + i) // 12, (t.month - 1 + i) % 12 + 1
        for item in soup_of(f"https://www.sng-ng.si/sl/spored/?changedYearMonth={y}-{mth:02d}").select("div.schedule-item"):
            dm = re.findall(r"\d+", txt(item.select_one(".schedule-left h2")))
            if len(dm) < 2:
                continue
            day, mon = int(dm[0]), int(dm[1])
            year = y if mon >= mth else y + 1
            for r in item.select("div.schedule-right"):
                info = txt(r)
                abonma = txt(r.select_one("p.abonma"))
                if "Odpovedano" in info or "Zaključena predstava" in info or re.search(r"(^|, )ŠOLA(,|$)", abonma):
                    continue
                link = r.select_one("a.play-link") or r.find("a", href=True)
                times = [txt(p) for p in r.select(".schedule-time p")]
                tm = re.match(r"(\d{1,2})[.:](\d{2})", times[0]) if times else None
                stage = times[1] if len(times) > 1 else ""
                city = "NG" if not stage or SNG_OWN.search(stage) else area(stage)
                if not link or not city:
                    continue
                venue = "SNG Nova Gorica" if city == "NG" and (not stage or SNG_OWN.search(stage)) else venue_name(stage)
                sub = " · ".join(x for x in (txt(r.select_one(".schedule-title-info span")), txt(r.select_one("p.genre")), stage) if x)
                out.append(event(src["key"], ymd(year, mon, day), nice_title(txt(link)), venue, city, "gledalisce",
                                 hhmm(*tm.groups()) if tm else None, sub, urllib.parse.urljoin("https://www.sng-ng.si", link["href"])))
    return out


def mostovna(src, prev):
    """Mostovna: mesečni seznami; oznaka #koncert pove zvrst."""
    out, t = [], today()
    for i in range(3):
        y, mth = t.year + (t.month - 1 + i) // 12, (t.month - 1 + i) % 12 + 1
        for post in soup_of(f"https://www.mostovna.com/dogodki&month={mth}&year={y}").select("div.post"):
            h = post.select_one(".text h2 a") or post.select_one("h2 a")
            when = txt(post.select_one(".cat-name"))
            m = re.search(rf"(\d{{1,2}})\.\s*({MONTH_RX})\s*(\d{{4}})", when, re.I)
            if not h or not m:
                continue
            meta = txt(post.select_one(".meta"))
            tags = " ".join(txt(a) for a in post.select("a.tag"))
            cat = "glasba" if re.search(r"koncert|concert", tags, re.I) else guess_cat(f"{txt(h)} {tags}")
            if not cat:
                continue
            st = re.search(r"Start:\s*(\d{1,2})[.:](\d{2})", meta) or re.search(r"Vrata:\s*(\d{1,2})[.:](\d{2})", meta)
            price, free = price_from(meta)
            out.append(event(src["key"], ymd(m.group(3), MONTHS[m.group(2).lower()], m.group(1)), clean(h.get_text()), "Mostovna", "NG",
                             cat, hhmm(*st.groups()) if st else None, None, urllib.parse.urljoin("https://www.mostovna.com/", h["href"]),
                             price, free))
    return out


BRATUZ_CAT = {"gledalisce": "gledalisce", "balet": "gledalisce", "kamisibaj": "gledalisce", "koncerti": "glasba"}


def bratuz(src, prev):
    """KC Lojze Bratuž: seznam po straneh brez ure; uro preberemo na strani dogodka."""
    base, start, end = "https://www.centerbratuz.org/", *window()
    out, seen = [], set()
    for p in range(1, 15):  # ?p=1 je prva stran
        page = soup_of(f"{base}dogodki.html?p={p}")
        new = 0
        for art in page.select("div.novice article"):
            a = art.find("a", href=True)
            if not a or a["href"] in seen:
                continue
            seen.add(a["href"])
            new += 1
            m = re.search(rf"(\d{{1,2}})\.\s*({MONTH_RX}),?\s*(\d{{4}})", txt(art.select_one(".datum")), re.I)
            cat = BRATUZ_CAT.get(a["href"].split("/")[0])
            date = ymd(m.group(3), MONTHS[m.group(2).lower()], m.group(1)) if m else None
            if not cat or not date or not (start <= date <= end):
                continue
            url = urllib.parse.urljoin(base, a["href"])
            try:
                page_text = clean(get(url))
                tm = (re.search(r"\d{4}\s*[-–]\s*(\d{1,2})[.:](\d{2})", page_text)
                      or re.search(r"\b(?:ob|alle|ore)\s+(\d{1,2})[.:](\d{2})", page_text))
            except Exception:
                tm = None
            label = txt(art.select_one(".opispodsliko"))
            out.append(event(src["key"], date, nice_title(txt(art.select_one("h4"))), "KC Lojze Bratuž", "GO", cat,
                             hhmm(*tm.groups()) if tm else None, nice_label(label) or None, url))
            time.sleep(0.3)
        if not new:
            break
    return out


def verdi(src, prev):
    """Teatro Verdi: cela sezona na eni strani (dnevi brez letnice); točen datum in ura sta na strani predstave."""
    start, end = window()
    out = []
    for ev in soup_of(src["url"]).select("div.type-tribe_events"):
        head = ev.find_previous("h2", class_="tribe-events-list-separator-month")
        ym = re.search(rf"({MONTH_RX})\s+(\d{{4}})", txt(head), re.I)
        day = re.search(r"\d+", txt(ev.select_one(".cmsmasters_event_big_day")))
        a = ev.select_one("h2 a[href]")
        if not (ym and day and a):
            continue
        date = ymd(ym.group(2), MONTHS[ym.group(1).lower()], day.group(0))
        if not date or not (start <= date <= end):
            continue
        kind = txt(ev.select_one(".cmsmasters_project_category")).upper()
        title = txt(a)
        desc = txt(ev.select_one(".tribe-events-list-event-description"))[:400]
        if "PROSA" in kind or "YOUNG" in kind or "RACCONTA" in kind:
            cat = "gledalisce"
        elif "MUSICA" in kind:
            cat = "gledalisce" if re.search(r"ballett|danza|dance", f"{title} {desc}", re.I) else "glasba"
        else:
            cat = guess_cat(f"{title} {desc}", "gledalisce", skip=False)
        tm = None
        try:
            page = clean(get(a["href"]))
            # 'Sabato 28 novembre 2026 Inizio Rappresentazione h 20:45' (letnica včasih manjka)
            hits = re.findall(rf"(\d{{1,2}})\s+({MONTH_RX})(?:\s+\d{{4}})?.{{0,40}}?Inizio[^0-9]{{0,40}}(\d{{1,2}})[.:](\d{{2}})", page, re.I)
            same = [h for h in hits if (int(h[0]), MONTHS[h[1].lower()]) == (int(date[8:]), int(date[5:7]))]
            if same or hits:
                h = (same or hits)[0]
                tm = hhmm(h[2], h[3])
            time.sleep(0.3)
        except Exception:
            pass
        out.append(event(src["key"], date, nice_title(title), "Teatro Verdi", "GO", cat, tm, nice_label(kind) or None, a["href"]))
    return out


def kinemax(src, prev):
    """Kinemax Gorizia: redni spored (prodajna stran 18tickets) strnemo v en vnos na dan."""
    days = defaultdict(lambda: defaultdict(list))
    for mv in soup_of(src["fetch"].split(":", 1)[1]).select("div.movie"):
        t = mv.select_one("a.movie__title")
        if not t:
            continue
        title = nice_title(t.get_text())
        for a in mv.select("a[data-time]"):
            place = a.find_previous(class_="time-select__place")
            where = (txt(place) + " " + " ".join(x.get("title", "") for x in place.select("a[title]"))) if place else ""
            if area(where) != "GO":
                continue
            when = dt.datetime.fromtimestamp(int(a["data-time"]) / 1000, TZ)
            days[when.date().isoformat()][title].append(when.strftime("%H:%M"))
    out = []
    for date, films in sorted(days.items()):
        sub = " · ".join(f"{f} {', '.join(sorted(set(ts)))}" for f, ts in sorted(films.items(), key=lambda kv: min(kv[1])))
        out.append(event(src["key"], date, "Redni spored", "Kinemax Gorizia", "GO", "film", None, sub, src["url"], regular=True))
    return out


def tic(src, prev):
    """TIC Nova Gorica in Vipavska dolina: koledar za celotno obdobje naenkrat (lng=slo), le enodnevni dogodki."""
    start, end = window()
    fmt = lambda s: f"{s[8:10]}.{s[5:7]}.{s[:4]}"
    page = BeautifulSoup(get("https://dogodki.turizem-novagorica-vipavskadolina.si/util/ajaxresponse.php?lng=slo",
                             data={"func": "filterCalendar", "dateFrom": fmt(start), "dateTo": fmt(end)},
                             headers={"X-Requested-With": "XMLHttpRequest"}), "html.parser")
    out = []
    for g in page.select("div.event-grid"):
        a = g.select_one("h2 a[href]")
        dates = re.findall(r"(\d{2})\.(\d{2})\.(\d{4})", txt(g.select_one(".date")))
        if not a or not dates or len({d for d in dates}) > 1 or "event-type-sport" in g.get("class", []):
            continue
        loc = txt(g.select_one(".location"))
        title = txt(a)
        city, cat = area(loc), guess_cat(title)
        if not city or not cat:
            continue
        d = dates[0]
        hm = re.search(r"(\d{1,2}):(\d{2})", txt(g.select_one(".hour")))
        out.append(event(src["key"], ymd(d[2], d[1], d[0]), nice_title(title), venue_name(loc, loc.split(",")[0]), city, cat,
                         hhmm(*hm.groups()) if hm else None, None,
                         urllib.parse.urljoin("https://dogodki.turizem-novagorica-vipavskadolina.si/", a["href"])))
    return out


TRIBE = {"kulturnidom.it": kdgo, "robin.si": robin}
ICAL = {"artistiassociatigorizia.it": aa, "zskd.eu": zskd, "scopri.gorizia.it": scopri}
OWN = {"kdng": kdng, "sng": sng, "mostovna": mostovna, "bratuz": bratuz, "verdi": verdi, "kinemax": kinemax, "tic": tic}


def reader(src):
    """Izbere bralnik po polju 'fetch' v viri.json; None pomeni, da vira (še) ne beremo."""
    kind = src["fetch"].split(":", 1)[0]
    if kind == "tribe":
        return TRIBE.get(src["key"], tribe_generic)
    if kind == "ical":
        return ICAL.get(src["key"])
    return OWN.get(kind)
