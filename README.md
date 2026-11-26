# Goriški napovednik

Koncerti, predstave in projekcije v Novi Gorici in Gorici, od danes naprej.
Stran: https://tsunekazu.github.io/goriski-napovednik/

## Kako deluje (0 € samodejno)

Vsako noč GitHub Actions (`.github/workflows/posodobi.yml`) zažene zbiralnik, ki prebere 14 glavnih virov iz `podatki/viri.json`,
shrani dogodke v `podatki/dogodki/` in na novo objavi stran na GitHub Pages. Ročno ni treba ničesar delati.

- `zbiralnik/`: bralniki virov (Python). Velika prizorišča imajo svoje bralnike, nekateri viri imajo iCal ali WordPress REST API.
- `stran/`: predloga strani (`index.template.html`) in `build.py`, ki združi dogodke z vseh virov in odstrani podvojene.
- `podatki/stanje.json`: zadnja uspešna posodobitev, hash strani in morebitna napaka za vsak vir.
- `raziskava/`: kako so bili izbrani viri; `izloceni.json` so prizorišča brez spletne strani (samo Facebook/Instagram ipd.).

Okolica (Brda, Krmin, Gradišče, Miren ...) se zbira samodejno z oznako `"ring": true` in je na strani skrita za stikalom **+ Okolica**.

## Hitro ročno osveževanje z AI pomočnikom (Hydrogen)

Vsakih nekaj dni lahko preprosto odpreš to mapo v Hydrogenu (ali drugem AI pomočniku) in napišeš **"refresh"** (po želji prilepiš še kak Facebook/Instagram dogodek).
Pomočnik samodejno sledi navodilom v `AGENTS.md`:

1. `git pull --rebase origin main` (povleče nočne podatke z GitHuba)
2. `python3 -m zbiralnik --status` (preveri, ali se je kateri bralnik pokvaril)
3. `python3 -m zbiralnik --check-ai` (prenese le *spremenjene* AI-strani v `.cache/ai-pending/`, da jih pomočnik prebere brez API stroškov)
4. Doda morebitne Facebook/IG dogodke v `podatki/rocni.json` in počisti pretekle (`python3 -m zbiralnik --prune-manual`)
5. Zgradi stran (`python3 stran/build.py`) in potisne na GitHub.

## Poceni samodejno AI-branje v GitHub Actions (neobvezno)

23 manjših strani v `viri.json` ima `"fetch": "ai"`. Če v **Settings → Secrets and variables → Actions** dodaš enega od ključev:
- `GEMINI_API_KEY` — privzeto `gemini-2.5-flash` (brez dodatnih knjižnic; brezplačni nivo ali nekaj centov/mesec), **ali**
- `ANTHROPIC_API_KEY` — privzeto `claude-haiku-5-5` (približno 0,20–1 $/mesec).

Zbiralnik samodejno preverja **hash vsebine** (nespremenjenih strani ne pošilja AI modelu) in AI vire preverja največ vsake 3 dni (sezonske na 14 dni; nastavljivo z `AI_MIN_DAYS` in `AI_MODEL`).

## Ročni zagon

    pip install -r requirements.txt
    python3 -m zbiralnik --status      # hiter pregled zdravja
    python3 -m zbiralnik               # pobere dogodke
    python3 stran/build.py             # zgradi _site/index.html
