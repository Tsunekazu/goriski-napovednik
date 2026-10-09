# Goriški napovednik

Koncerti, predstave in projekcije v Novi Gorici in Gorici, od danes naprej.
Stran: https://tsunekazu.github.io/goriski-napovednik/

## Kako deluje

Vsako noč GitHub (`.github/workflows/posodobi.yml`) zažene zbiralnik, ki prebere vire iz `podatki/viri.json`,
shrani dogodke v `podatki/dogodki/` in na novo objavi stran. Ročno ni treba ničesar delati.

- `zbiralnik/`: bralniki virov (Python). Velika prizorišča imajo svoje bralnike, nekateri viri imajo koledar (iCal ali API).
- `stran/`: predloga strani in `build.py`, ki združi dogodke z vseh virov in odstrani podvojene.
- `podatki/stanje.json`: kdaj se je posamezen vir nazadnje uspešno posodobil in morebitna napaka.
- `raziskava/`: kako smo poiskali vire; `izloceni.json` so viri brez uporabne spletne strani (samo Facebook ipd.).

Če se vir tri dni ne posodobi, je v nogi strani obarvan sivo. Takrat je njegova stran najverjetneje spremenila obliko
in bralnik v `zbiralnik/bralniki.py` je treba popraviti (zna vsak AI pomočnik, če mu pokažeš datoteko in napako iz `stanje.json`).

Okolico (Brda, Krmin, Gradišče ...) vklopiš v `zbiralnik/skupno.py` z `INCLUDE_RING = True`.

## Lastna domena

V repozitoriju odpri Settings → Pages → Custom domain in vpiši domeno. Pri ponudniku domene dodaj zapis CNAME
na `tsunekazu.github.io` (za `www`) ali štiri zapise A za golo domeno:
185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153.

## Branje ostalih strani z AI (neobvezno)

23 virov v `viri.json` ima `"fetch": "ai"`: manjše strani brez koledarja (Glasbe sveta, Lipizer, Kinoatelje, Controtempo ...).
Brez ključa jih zbiralnik preskoči. Ko v Settings → Secrets and variables → Actions dodaš skrivnost `ANTHROPIC_API_KEY`
(račun na console.anthropic.com), jih bere Claude. Model izbereš s spremenljivko `AI_MODEL`: `claude-haiku-5-5`
stane okoli 1 $ na mesec, privzeti `claude-opus-5-5` precej več. Ta del še ni bil preizkušen s pravim ključem,
zato po prvem nočnem zagonu poglej `podatki/stanje.json`.

## Ročni zagon

    pip install -r requirements.txt
    python -m zbiralnik        # pobere dogodke
    python stran/build.py      # zgradi _site/index.html
