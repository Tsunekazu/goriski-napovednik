# Goriški napovednik — Agent Refresh Guide (Hydrogen / AI Assistant)

When Jure opens this repo and says **"refresh"**, **"update"**, **"osveži"**, or pastes events/flyers/links from Facebook or Instagram, follow this exact checklist.

GitHub Actions (`.github/workflows/posodobi.yml`) already updates the 14 coded scrapers every night for $0 and deploys to `https://tsunekazu.github.io/goriski-napovednik/`. Your periodic manual run handles:
1. Checking & repairing any broken coded scraper.
2. Refreshing active `"fetch": "ai"` pages that actually changed — using **your own reading** ($0 API cost).
3. Adding any Facebook/Instagram/manual gigs Jure shares into `podatki/rocni.json` and pruning expired ones.
4. Rebuilding, verifying, and pushing to `origin/main` so GitHub Pages redeploys automatically.

---

## Standard Refresh Checklist

### 1. Pull nightly commits first (mandatory!)
GitHub Actions commits daily data to `origin/main`, so always sync before editing:
```bash
git pull --rebase origin main
```

### 2. Check scraper health
```bash
python3 -m zbiralnik --status
```
- If any coded source shows `ERROR` or `STALE` (>3 days old), probe its URL and fix either its URL in `podatki/viri.json` or its parser in `zbiralnik/bralniki.py`.
- Re-run `python3 -m zbiralnik` to refresh all coded scrapers.

### 3. Refresh changed AI-only websites ($0 cost, hash-cached)
Run:
```bash
python3 -m zbiralnik --check-ai
```
(Add `--all` once a month if you also want to sweep `prio: 3` / seasonal sites.)

This fetches active `"fetch": "ai"` websites, skips any page whose text hash hasn't changed since the last check, and saves **only changed/new pages** into `.cache/ai-pending/<key>.txt`.

For each file reported in `.cache/ai-pending/<key>.txt`:
1. Read the text file carefully.
2. Extract **only** real public events within the next 91 days in these 3 categories:
   - `"glasba"` — concerts, live music, recitals, choirs, jazz, rock/punk/metal, DJ/electronic live sets
   - `"gledalisce"` — theatre, dance, opera, puppetry, cabaret, stand-up
   - `"film"` — film screenings, cineforum, film festivals
   - **Skip** exhibitions, workshops, lectures, book launches, markets, sports, private/school-only events.
   - **Never invent** dates, times, prices, or events not explicitly in the page text.
3. Apply the extracted events (even `[]` if there are 0 qualifying upcoming events, so its hash is recorded and skipped next time!):
   ```bash
   python3 -m zbiralnik --apply-ai <key> <<'EOF'
   [
     {
       "date": "2026-12-05",
       "time": "20:00",
       "title": "Exact Event Title",
       "venue": "Venue Name",
       "place": "Nova Gorica",
       "category": "glasba",
       "price": "10 €",
       "url": "https://..."
     }
   ]
   EOF
   ```
   (`--apply-ai` automatically validates dates, normalizes titles/venues/cities/ring, verifies titles exist in the fetched page text, saves `podatki/dogodki/<key>.json`, and updates `podatki/stanje.json` with the new hash!)

### 4. Manual / Facebook / Instagram events (if Jure provided any)
If Jure pasted text, links, or flyers (e.g. ARCI Gong, Mama Angela, Carinarnica, Marco Polo, SKD Hrast, local gigs):
- Add them to `podatki/rocni.json` (array of objects):
  ```json
  {
    "date": "2026-12-12",
    "time": "21:00",
    "title": "Band Name",
    "sub": "Optional genre / support act",
    "venue": "Circolo ARCI Gong",
    "city": "GO",
    "cat": "glasba",
    "url": "https://...",
    "price": "10 €",
    "free": false,
    "ring": false
  }
  ```
  Required fields: `date` (`YYYY-MM-DD`), `title`, `venue`, `city` (`"NG"` or `"GO"`), `cat` (`"glasba"` | `"gledalisce"` | `"film"`). Optional: `time` (`"HH:MM"`), `sub`, `url`, `price`, `free` (`true`), `ring` (`true` for Brda/Krmin/Gradišče/Miren/Renče/Kanal/Števerjan/Doberdob).
- Always prune past manual events afterward:
  ```bash
  python3 -m zbiralnik --prune-manual
  ```

### 5. Build, verify, and push
```bash
python3 stran/build.py
git status --short
git add podatki zbiralnik stran README.md AGENTS.md
git commit -m "Osvežitev $(date +%Y-%m-%d)"
git push origin main
```
Then report concisely to Jure:
- Any broken scrapers fixed (or "all 14 coded scrapers healthy")
- Which AI sites had new events (and how many)
- Manual events added/pruned
- Total upcoming events on the rebuilt site & confirmation that `git push` succeeded (GitHub Pages deploys in ~30–60s).
