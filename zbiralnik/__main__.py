"""Zbiralnik: prebere vire iz podatki/viri.json in zapiše dogodke v podatki/dogodki/<vir>.json.

Zagon:
  python -m zbiralnik                   vsi redni bralniki (+ poceni hash-cached AI, če je ključ nastavljen)
  python -m zbiralnik sng-ng.si         le izbrani viri
  python -m zbiralnik --status          pregled stanja vseh virov (napake, zastareli, ročni, AI)
  python -m zbiralnik --check-ai        prenese spremenjene AI-vire v .cache/ai-pending/ (0 $; za Hydrogena)
  python -m zbiralnik --apply-ai KEY    shrani JSON dogodke za AI-vir (iz datoteke ali stdin) in zapiše hash
  python -m zbiralnik --prune-manual    odstrani pretekle dogodke iz podatki/rocni.json

Če vir odpove, ostanejo prejšnji podatki; napaka se zapiše v podatki/stanje.json.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

from . import ai
from .bralniki import reader
from .skupno import CATS, TZ, today, window

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "podatki")
OUT = os.path.join(DATA, "dogodki")
MANUAL = os.path.join(DATA, "rocni.json")
PENDING_DIR = os.path.join(ROOT, ".cache", "ai-pending")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
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


def days_since(iso_ts):
    if not iso_ts:
        return 9999
    try:
        return (today() - dt.date.fromisoformat(iso_ts[:10])).days
    except ValueError:
        return 9999


def ai_min_days(src):
    env_days = os.environ.get("AI_MIN_DAYS")
    base = int(env_days) if (env_days and env_days.isdigit()) else 3
    if src.get("status") in ("seasonal", "stale"):
        return max(base, 14)
    return base


def collect_coded(src, prev):
    fn = reader(src)
    try:
        return tidy(fn(src, prev))
    except Exception:
        if not ai.enabled():
            raise
        return tidy(ai.read(src, prev))


def cmd_status(viri, stanje):
    coded_ok, coded_err, coded_stale = 0, [], []
    ai_active, ai_due = 0, 0
    total_events = 0

    for src in viri:
        key = src["key"]
        st = stanje.get(key) or {}
        if reader(src) is not None:
            age = days_since(st.get("ok"))
            n = st.get("n", 0)
            total_events += n
            if st.get("error"):
                coded_err.append((key, st.get("ok", "nikoli")[:10], st["error"]))
            elif age > 3:
                coded_stale.append((key, st.get("ok", "nikoli")[:10], age))
            else:
                coded_ok += 1
        elif src.get("fetch") == "ai" and src.get("status") == "active":
            ai_active += 1
            total_events += st.get("n", 0)
            if days_since(st.get("checked") or st.get("ok")) >= ai_min_days(src):
                ai_due += 1

    manual = load(MANUAL, [])
    start, _ = window()
    manual_live = [e for e in manual if isinstance(e, dict) and (e.get("date") or "") >= start]
    manual_expired = len(manual) - len(manual_live)

    print(f"Datum: {today().isoformat()} | AI ključ: {ai.provider() or 'ni nastavljen (ročni/Hydrogen način)'}")
    print(f"Redni bralniki: {coded_ok} zdravih, {len(coded_err)} z napako, {len(coded_stale)} zastarelih")
    for key, last_ok, err in coded_err:
        print(f"  ✗ {key} (zadnji ok: {last_ok}): {err}")
    for key, last_ok, age in coded_stale:
        print(f"  ? {key} (zastarel {age} dni, zadnji ok: {last_ok})")
    print(f"AI viri (aktivni): {ai_active} skupaj, {ai_due} čaka na pregled (--check-ai)")
    print(f"Ročni dogodki (podatki/rocni.json): {len(manual_live)} prihajajočih, {manual_expired} preteklih")
    print(f"Skupaj shranjenih vnosov (pred združevanjem dvojnikov): {total_events + len(manual_live)}")


def cmd_check_ai(viri, stanje, only, include_all=False, force=False):
    """Prenese aktivne AI strani, preskoči nespremenjene (hash) in zapiše spremenjene v .cache/ai-pending/."""
    now = dt.datetime.now(TZ).isoformat(timespec="minutes")
    os.makedirs(PENDING_DIR, exist_ok=True)
    changed, unchanged, skipped_cadence, failed = [], 0, 0, []

    for src in viri:
        key = src["key"]
        if src.get("fetch") != "ai":
            continue
        if only and key not in only:
            continue
        if not only and not include_all:
            if src.get("status") != "active" or src.get("prio", 9) > 2:
                continue
        if src.get("status") == "dead":
            continue

        st = stanje.setdefault(key, {})
        if not force and not only and days_since(st.get("checked") or st.get("ok")) < ai_min_days(src):
            skipped_cadence += 1
            continue

        try:
            text, h = ai.fetch_page(src)
        except Exception as ex:
            err = f"{type(ex).__name__}: {ex}"[:200]
            failed.append((key, err))
            print(f"✗ {key}: {err}")
            continue

        if not force and h == st.get("hash") and st.get("ok"):
            unchanged += 1
            st["checked"] = now
            # re-tidy existing events so expired ones drop out even without LLM call
            path = os.path.join(OUT, key + ".json")
            if os.path.exists(path):
                prev = tidy(load(path, []))
                save(path, prev)
                st["n"] = len(prev)
            print(f"= {key}: brez sprememb (hash {h})")
            continue

        txt_path = os.path.join(PENDING_DIR, f"{key}.txt")
        meta_path = os.path.join(PENDING_DIR, f"{key}.meta.json")
        header = (
            f"KEY: {key}\n"
            f"NAME: {src['name']}\n"
            f"URL: {src['url']}\n"
            f"SIDE: {src['side']} | ZONE: {src.get('zone', 'core')} | PRIO: {src.get('prio', 2)}\n"
            f"NOTE: {src.get('how', '')}\n"
            f"HASH: {h}\n"
            f"WINDOW: {' .. '.join(window())}\n"
            + "=" * 60 + "\n"
        )
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(header + text + "\n")
        save(meta_path, {"key": key, "hash": h, "fetched": now, "url": src["url"]})
        changed.append((key, txt_path, len(text)))
        print(f"★ {key}: SPREMENJENO ({len(text)} znakov) -> .cache/ai-pending/{key}.txt")

    save(os.path.join(DATA, "stanje.json"), stanje)
    print(f"\nPovzetek --check-ai: {len(changed)} za pregled, {unchanged} nespremenjenih, {skipped_cadence} še svežih, {len(failed)} napak.")


def cmd_apply_ai(viri, stanje, key, json_file=None):
    src = next((s for s in viri if s["key"] == key), None)
    if not src:
        raise SystemExit(f"Neznan vir: {key}")
    raw_txt = open(json_file, encoding="utf-8").read() if json_file else sys.stdin.read()
    parsed = json.loads(raw_txt)
    raw_events = parsed["events"] if isinstance(parsed, dict) and "events" in parsed else parsed
    if not isinstance(raw_events, list):
        raise SystemExit("Pričakovan JSON seznam dogodkov ali {\"events\": [...]}")

    meta_path = os.path.join(PENDING_DIR, f"{key}.meta.json")
    txt_path = os.path.join(PENDING_DIR, f"{key}.txt")
    meta = load(meta_path, {})
    page_body = None
    if os.path.exists(txt_path):
        full = open(txt_path, encoding="utf-8").read()
        page_body = full.split("=" * 60 + "\n", 1)[-1]

    events = tidy(ai.normalize_events(src, raw_events, page_text_str=page_body))
    save(os.path.join(OUT, key + ".json"), events)

    now = dt.datetime.now(TZ).isoformat(timespec="minutes")
    st = stanje.setdefault(key, {})
    st.update(ok=now, checked=now, n=len(events))
    if meta.get("hash"):
        st["hash"] = meta["hash"]
    st.pop("error", None)
    st.pop("failed", None)
    save(os.path.join(DATA, "stanje.json"), stanje)

    for p in (meta_path, txt_path):
        if os.path.exists(p):
            os.remove(p)
    print(f"✓ {key}: shranjeno {len(events)} dogodkov (hash {st.get('hash', '-')})")


def cmd_prune_manual():
    if not os.path.exists(MANUAL):
        print("podatki/rocni.json ne obstaja (nič za čistiti).")
        return
    raw = load(MANUAL, [])
    start, _ = window()
    seen, kept = set(), []
    for e in sorted(raw, key=lambda x: (x.get("date") or "", x.get("time") or "99", x.get("title") or "")):
        if not isinstance(e, dict):
            continue
        if (e.get("date") or "") < start or not e.get("title") or e.get("cat") not in CATS or e.get("city") not in ("NG", "GO"):
            continue
        k = (e.get("date"), e.get("time"), re.sub(r"\W+", "", e["title"].lower()))
        if k not in seen:
            seen.add(k)
            kept.append(e)
    removed = len(raw) - len(kept)
    save(MANUAL, kept)
    print(f"✓ podatki/rocni.json: obdržano {len(kept)}, odstranjenih preteklih/neveljavnih {removed}")


def run_collect(viri, stanje, only, force_ai=False):
    now = dt.datetime.now(TZ).isoformat(timespec="minutes")
    os.makedirs(OUT, exist_ok=True)
    force = force_ai or os.environ.get("AI_FORCE") == "1"

    for src in viri:
        key = src["key"]
        if only and key not in only:
            continue
        has_reader = reader(src) is not None
        is_ai = src.get("fetch") == "ai"
        if not has_reader and not (is_ai and ai.enabled()):
            continue

        path = os.path.join(OUT, key + ".json")
        prev = load(path, [])
        st = stanje.setdefault(key, {})

        if not has_reader and is_ai:
            if src.get("status") == "dead":
                continue
            if not force and not only and days_since(st.get("checked") or st.get("ok")) < ai_min_days(src):
                continue
            try:
                text, h = ai.fetch_page(src)
                if not force and h == st.get("hash") and st.get("ok"):
                    kept = tidy(prev)
                    save(path, kept)
                    st.update(checked=now, ok=now, n=len(kept))
                    st.pop("error", None)
                    st.pop("failed", None)
                    print(f"= {key}: {len(kept)} (brez sprememb)")
                    continue
                events = tidy(ai.extract(src, text))
            except Exception as ex:
                st.update(error=f"{type(ex).__name__}: {ex}"[:300], failed=now)
                print(f"✗ {key}: {st['error']}")
                continue
            save(path, events)
            st.update(ok=now, checked=now, hash=h, n=len(events))
            st.pop("error", None)
            st.pop("failed", None)
            print(f"✓ {key} [ai/{ai.provider()}]: {len(events)}")
            continue

        try:
            events = collect_coded(src, prev)
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


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m zbiralnik", description="Zbiralnik dogodkov za Goriški napovednik")
    ap.add_argument("keys", nargs="*", help="Neobvezno: posamezni ključi virov iz podatki/viri.json")
    ap.add_argument("--status", action="store_true", help="Prikaže stanje virov (napake, zastareli, ročni, AI)")
    ap.add_argument("--check-ai", action="store_true", help="Prenese spremenjene aktivne AI-strani v .cache/ai-pending/")
    ap.add_argument("--all", action="store_true", help="Z --check-ai vključi tudi prio=3 in sezonske vire")
    ap.add_argument("--force-ai", action="store_true", help="Ignorira hash-predpomnilnik in interval AI_MIN_DAYS")
    ap.add_argument("--apply-ai", metavar="KEY", help="Shrani JSON dogodke za AI-vir (iz datoteke ali stdin)")
    ap.add_argument("--file", metavar="JSON", help="Datoteka z JSON dogodki za --apply-ai")
    ap.add_argument("--prune-manual", action="store_true", help="Odstrani pretekle dogodke iz podatki/rocni.json")
    args = ap.parse_args(argv)

    viri = load(os.path.join(DATA, "viri.json"), [])
    stanje = load(os.path.join(DATA, "stanje.json"), {})

    if args.status:
        cmd_status(viri, stanje)
    elif args.check_ai:
        cmd_check_ai(viri, stanje, set(args.keys), include_all=args.all, force=args.force_ai)
    elif args.apply_ai:
        cmd_apply_ai(viri, stanje, args.apply_ai, args.file)
    elif args.prune_manual:
        cmd_prune_manual()
    else:
        run_collect(viri, stanje, set(args.keys), force_ai=args.force_ai)


if __name__ == "__main__":
    main()
