"""Skupne pomožne funkcije: prenos strani, čiščenje besedila, datumi, cene, zvrsti in območje."""
import datetime as dt
import html
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Ljubljana")
DAYS = 91  # koliko dni vnaprej zbiramo (enako kot stran)
CATS = ("glasba", "gledalisce", "film")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36 (goriski-napovednik)"

# Območje. Okolico (Brda, Krmin, Gradišče ...) označimo z ring=True (na strani privzeto skrita za stikalom Okolica).
INCLUDE_RING = True
SI_CORE = ["nova gorica", "novi gorici", "solkan", "kromberk", "rožna dolina", "šempeter", "vrtojba", "branik", "prvačina", "šempas",
           "osek", "vitovlje", "ozeljan", "grgar", "ravnica", "banjšice", "trnovo", "lokve", "čepovan", "lokovec", "ajševica",
           "loke", "stara gora", "dornberk", "gradišče nad prvačino", "zalošče", "saksid", "pristava"]
IT_CORE = ["gorizia", "gorica", "gorici", "štandrež", "standrez", "sant'andrea", "pevma", "piuma", "podgora", "piedimonte",
           "ločnik", "lucinico", "oslavje", "oslavia", "straccis"]
SI_RING = ["renče", "vogrsko", "bukovica", "volčja draga", "bilje", "miren", "orehovlje", "kostanjevica na krasu", "opatje selo",
           "brda", "dobrovo", "vipolže", "kojsko", "šmartno", "medana", "kanal", "deskle", "plave"]
IT_RING = ["cormons", "cormòns", "krmin", "gradisca", "gradišče", "mossa", "san floriano", "števerjan", "savogna", "sovodnje",
           "farra", "doberdò", "doberdob", "capriva", "romans", "sagrado"]


def _rx(words):
    return re.compile(r"(?<!\w)(" + "|".join(re.escape(w) for w in words) + r")(?!\w)", re.I)


_SI, _IT, _SIR, _ITR = _rx(SI_CORE), _rx(IT_CORE), _rx(SI_RING), _rx(IT_RING)


def area_zone(text):
    """Vrne (mesto, okolica): ('NG'|'GO', False) za jedro, ('NG'|'GO', True) za okolico ali (None, False).
    Slovensko stran preverimo prvo, ker 'Nova Gorica' vsebuje 'Gorica'; okolico pred Gorico,
    ker italijanski naslovi končajo s pokrajino (npr. 'Cormòns, Gorizia')."""
    t = text or ""
    if _SI.search(t):
        return "NG", False
    if _SIR.search(t):
        return ("NG", True) if INCLUDE_RING else (None, False)
    if _ITR.search(t):
        return ("GO", True) if INCLUDE_RING else (None, False)
    if _IT.search(t):
        return "GO", False
    return None, False


def area(text):
    """Vrne 'NG' (slovenska stran), 'GO' (italijanska stran) ali None, če kraj ni na našem območju."""
    return area_zone(text)[0]


def today():
    return dt.datetime.now(TZ).date()


def window():
    """Prvi in zadnji dan, ki ju prikažemo (ISO niza)."""
    t = today()
    return t.isoformat(), (t + dt.timedelta(days=DAYS)).isoformat()


# ——— prenos ———

def get(url, data=None, headers=None, timeout=40, tries=2):
    """Prenese stran in vrne besedilo. Pokvarjen SSL certifikat (npr. Mostovna) prenosa ne ustavi."""
    h = {"User-Agent": UA, "Accept-Language": "sl,it;q=0.8,en;q=0.5", **(headers or {})}
    body = urllib.parse.urlencode(data, doseq=True).encode() if isinstance(data, (dict, list)) else data
    err = None
    for attempt in range(tries):
        req = urllib.request.Request(url, data=body, headers=h)
        try:
            try:
                r = urllib.request.urlopen(req, timeout=timeout)
            except urllib.error.URLError as e:
                if not isinstance(e.reason, ssl.SSLError):
                    raise
                r = urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context())
            with r:
                return r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            err = e
            if attempt + 1 < tries:
                time.sleep(4)
    raise err


def get_json(url, **kw):
    return json.loads(get(url, **kw))


# ——— besedilo ———

def clean(s):
    """HTML v navadno besedilo v eni vrstici."""
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s or "")
    s = re.sub(r"(?i)<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(html.unescape(s))).strip()


ACRONYMS = {"SNG", "SSG", "KUD", "KD", "KC", "SKD", "SKRD", "ZSKD", "ZKD", "DJ", "FVG", "GO!", "UK", "USA", "LP", "MC", "TV", "EU",
            "ARCI", "RAI", "NATO", "AI", "ZSKP", "TIC", "GO", "NG", "KGBL", "BBC", "CD", "EP", "VIP", "DIY", "JSKD", "EZTS", "GECT"}
LOWER_SHORT = {"of", "in", "on", "at", "to", "by", "or", "as", "an", "di", "da", "de", "ed", "il", "la", "le", "lo", "li", "un",
               "su", "al", "na", "za", "po", "ob", "od", "do", "iz", "ki", "pa", "se", "si", "je", "ni", "ne", "so", "bo", "bi",
               "ta", "to", "te", "ti", "et", "du", "au", "en", "el"}
PROPER_NOUNS = {"gorica", "gorici", "gorice", "gorico", "gorizia", "ljubljana", "ljubljani", "ljubljane", "ljubljano",
                "slovenija", "sloveniji", "slovenije", "slovenka", "slovenec", "italija", "italiji", "italije", "italia",
                "evropa", "evrope", "europa", "solkan", "kromberk", "šempeter", "vrtojba", "brda", "vipolže", "dobrovo",
                "šmartno", "medana", "vipava", "ajdovščina", "tolmin", "idrija", "bovec", "kobarid", "kanal", "miren",
                "renče", "branik", "prvačina", "kostanjevica", "soča", "soče", "soči", "sočo", "isonzo", "kras", "trst", "trieste", "koper",
                "piran", "maribor", "celje", "kranj", "videm", "udine", "krmin", "cormons", "cormòns", "gradišče", "gradisca",
                "števerjan", "štandrež", "doberdob", "doberdò", "furlanija", "friuli", "venezia", "giulia", "tartini",
                "verdi", "bratuž", "bevk", "modugno", "mozart", "bach", "beethoven", "chopin", "vivaldi", "puccini",
                "rossini", "shakespeare", "cankar", "prešeren"}
_ROMAN = re.compile(r"^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})\.$")


def _keep(w):
    """Besede, ki ostanejo z velikimi črkami: kratice, rimske številke (XIV.), oznake držav (I) in besede s števkami (MNA3)."""
    if re.match(r"^\([A-Z]{1,3}\)$", w):
        return True
    core = w.strip("()[]\"'„“”,:;")
    return core.strip(".!?/|&") in ACRONYMS or _ROMAN.match(core) or any(c.isdigit() for c in core)


def _title_first(w):
    m = re.search(r"[^\W\d_]", w)
    return w[:m.start()] + w[m.start()].upper() + w[m.start() + 1:] if m else w


def _cap_part(p, force_cap=False):
    core = p.strip("()[]\"'„“”,:;.!?")
    if not core or _keep(p):
        return p
    if core.isupper():
        low = p.lower()
        if not force_cap and core.lower() in LOWER_SHORT:
            return low
        if sum(c.isalpha() for c in core) >= 3 or force_cap:
            return _title_first(low)
    return p


def _cap(w, force_cap=False):
    if _keep(w):
        return w
    parts = re.split(r"([&/])", w)
    if len(parts) > 1:
        return "".join(
            sep if i % 2 else _cap_part(sep, force_cap=(force_cap or i > 0))
            for i, sep in enumerate(parts)
        )
    return _cap_part(w, force_cap=force_cap)


def _restore_proper(w, cap_next):
    if _keep(w):
        return w
    parts = re.split(r"([&/])", w)
    out = []
    for i, p in enumerate(parts):
        if i % 2:
            out.append(p)
            continue
        core = p.strip("()[]\"'„“”,:;.!?").lower()
        low = p.lower()
        if cap_next or i > 0 or core in PROPER_NOUNS:
            out.append(_title_first(low))
        else:
            out.append(low)
    return "".join(out)


def nice_title(s):
    """Naslov, napisan s samimi velikimi črkami, pretvori v običajno pisavo (obdrži kratice in znana lastna imena)."""
    s = clean(s).strip(" -–—|·")
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 4 or sum(c.isupper() for c in letters) / len(letters) < 0.8:
        words = s.split(" ")
        return " ".join(_cap(w, force_cap=(i == 0)) for i, w in enumerate(words))
    words, out = s.split(" "), []
    cap_next = True
    for w in words:
        if w in ("/", "|", "–", "—", "-", ":"):
            out.append(w)
            cap_next = True
            continue
        out.append(_restore_proper(w, cap_next))
        cap_next = w.endswith((":", "?", "!", "/", "|"))
    res = " ".join(out)
    res = re.sub(r"\bnova gorica\b", "Nova Gorica", res, flags=re.I)
    res = re.sub(r"\bnovi gorici\b", "Novi Gorici", res, flags=re.I)
    res = re.sub(r"\bdan d\b", "Dan D", res, flags=re.I)
    return res


# ——— datumi ———

MONTHS = {}
for _names in ("januar februar marec april maj junij julij avgust september oktober november december",
               "januarja februarja marca aprila maja junija julija avgusta septembra oktobra novembra decembra",
               "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre",
               "january february march april may june july august september october november december"):
    for _i, _m in enumerate(_names.split(), 1):
        MONTHS[_m] = _i
MONTH_RX = "|".join(sorted(MONTHS, key=len, reverse=True))


def ymd(y, m, d):
    """Datum kot ISO niz ali None, če ne obstaja."""
    try:
        return dt.date(int(y), int(m), int(d)).isoformat()
    except (ValueError, TypeError):
        return None


def guess_year(m, d):
    """Leto za datum brez letnice: tisto, pri katerem je datum najbližje danes (praviloma prihodnost)."""
    t = today()
    for y in (t.year, t.year + 1):
        try:
            if dt.date(y, int(m), int(d)) >= t - dt.timedelta(days=120):
                return y
        except ValueError:
            return None
    return t.year + 1


def hhmm(h, m="00"):
    try:
        h, m = int(h), int(m)
    except (TypeError, ValueError):
        return None
    return f"{h:02d}:{m:02d}" if 0 <= h < 24 and 0 <= m < 60 else None


# ——— cene ———

FREE_RX = re.compile(r"prost vstop|vstop (je )?prost|brezplač|ingresso (libero|gratuito)|entrata libera|gratuit|free entry|vstopnine ni", re.I)


def fmt_eur(x):
    return f"{x:.0f}" if x == int(x) else f"{x:.2f}".replace(".", ",")


def price_from(text):
    """Iz besedila pobere cene v evrih; vrne (cena, prost_vstop)."""
    t = text or ""
    if FREE_RX.search(t):
        return None, True
    nums = []
    for m in re.finditer(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:€|eur\b|evr)|(?:€|eur)\s*(\d{1,3}(?:[.,]\d{1,2})?)", t, re.I):
        v = float((m.group(1) or m.group(2)).replace(",", "."))
        if 0 < v < 500:
            nums.append(v)
    if not nums:
        return None, False
    lo, hi = min(nums), max(nums)
    return (f"{fmt_eur(lo)} €" if lo == hi else f"{fmt_eur(lo)}–{fmt_eur(hi)} €"), False


# ——— zvrsti ———

SKIP_RX = re.compile(r"razstav|predstavitev|\bmostra\b|esposizion|delavnic|workshop|laborator|predavanj|conferenz|pogovorn|okrogla miza|tavola rotonda|"
                     r"predstavitev knjig|presentazione del libro|pohod|maraton|\btek\b|tečaj|\bcorso\b|bazar|sejem|mercatin|"
                     r"zaključeno za šole|zaključena predstava|šolsk|teatro scuola|pravljičn|bralna|bralni|kviz|quiz|karaoke|"
                     r"odprtje|inaugurazion|vodstvo|visita guidata|benedizion|spominsk|komemoracij", re.I)
CAT_RX = [
    ("film", re.compile(r"\bfilm|\bkino\b|projekcij|proiezion|\bcinema\b|cineforum|screening|dokumentar", re.I)),
    ("glasba", re.compile(r"koncert|concert|glasb|\bmusic(?!al)|\bmusica\b|jazz|orkest|orchestr|\bzbor|\bcoro\b|\bcori\b|pevsk|\bband\b|"
                          r"\blive\b|recital|kvartet|quartet|kvintet|\btrio\b|\bdj\b|rock|punk|metal|klapa|\bcanta|akustičn|"
                          r"kantavtor|cantautor|tribute|sinfoni|simfoni|opera lirica", re.I)),
    ("gledalisce", re.compile(r"gledali|predstav[aeo]\b|predstavam|komedij|\bdrama|teatr|teatro|spettacol|\bprosa\b|commedia|musical|muzikal|\bples|"
                              r"danza|\bdance\b|balet|ballett|lutk|burattin|kabaret|cabaret|stand-?up|\bopera\b|operet|monolog|"
                              r"kamišibaj|improv", re.I)),
]


def guess_cat(text, default=None, skip=True):
    """Zvrst po ključnih besedah; None, če dogodek ni glasba, gledališče ali film."""
    t = text or ""
    if skip and SKIP_RX.search(t):
        return None
    if re.search(r"\bmusical|muzikal|operet", t, re.I):  # sicer bi 'musica' v opisu prevladala
        return "gledalisce"
    for cat, rx in CAT_RX:
        if rx.search(t):
            return cat
    return default


# ——— prizorišča ———

VENUES = [
    (r"kulturn\w* dom\w*.*nov\w* goric|nov\w* goric\w*.*kulturn\w* dom", "Kulturni dom Nova Gorica"),
    (r"bratu[žz]", "KC Lojze Bratuž"),
    (r"kulturn\w* dom\w*.*goric|goric\w*.*kulturn\w* dom|via brass|ulica i\. brass", "Kulturni dom Gorica"),
    (r"\bsng\b|slovensko narodno gledali", "SNG Nova Gorica"),
    (r"mostovn", "Mostovna"),
    (r"teatro\b.*verdi|verdi.*teatro", "Teatro Verdi"),
    (r"kinemax", "Kinemax Gorizia"),
    (r"kostanjevic.*samostan|samostan.*kostanjevic", "Samostan Kostanjevica"),
    (r"grad\w* kromberk|kromberk.*grad", "Grad Kromberk"),
    (r"knjižnic\w* franceta bevka", "Goriška knjižnica Franceta Bevka"),
    (r"palazzo attems", "Palazzo Attems Petzenstein"),
    (r"carinarnic", "Carinarnica"),
]
VENUES = [(re.compile(p, re.I), n) for p, n in VENUES]


def venue_name(text, default=None):
    """Enotno ime za znana prizorišča, da se isti dogodek z različnih virov združi."""
    for rx, name in VENUES:
        if rx.search(text or ""):
            return name
    return default if default is not None else clean(text)


def event(src, date, title, venue, city, cat, time=None, sub=None, url=None, price=None, free=None, regular=None, ring=None):
    e = {"date": date, "time": time, "title": title, "venue": venue, "city": city, "cat": cat, "src": src}
    for k, v in (("sub", sub), ("url", url), ("price", price), ("free", free), ("regular", regular), ("ring", ring)):
        if v:
            e[k] = v
    return e
