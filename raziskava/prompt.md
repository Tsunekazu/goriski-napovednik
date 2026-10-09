# Research brief: event sources for a Nova Gorica + Gorizia culture calendar

**Context.** I'm building a free public calendar of music, theatre and film events in the twin towns of Nova Gorica (Slovenia) and Gorizia (Italy), 1–3 months ahead. It will be filled automatically from organisers' own websites. Facebook and Instagram won't be used. I need a complete, verified list of the websites that announce such events, above all those of non-governmental organisations (društva, zavodi, associazioni, circoli, APS), which run most of the small-scale culture here. Today is 9 October 2026.

Don't ask me clarifying questions; use the defaults below. Don't collect the events themselves: I only need the sources.

## Area
- **core** (cover exhaustively): Mestna občina Nova Gorica (incl. Solkan, Kromberk, Rožna Dolina, Branik), Občina Šempeter-Vrtojba, Comune di Gorizia (incl. Štandrež/Sant'Andrea, Pevma/Piuma, Podgora/Piedimonte, Ločnik/Lucinico).
- **ring** (as far as you get after the core): neighbouring municipalities within ~15 km, e.g. Renče-Vogrsko, Miren-Kostanjevica, Brda; Savogna d'Isonzo/Sovodnje, San Floriano del Collio/Števerjan, Mossa, Cormons/Krmin, Farra d'Isonzo, Gradisca d'Isonzo, Doberdò del Lago/Doberdob.

## In scope
Anyone who publicly announces:
- **music**: concerts of any genre (classical, choirs, jazz, rock/punk/metal, folk, electronic, open mic)
- **theatre**: professional and amateur theatre, puppetry, dance, opera, cabaret/stand-up
- **film**: screenings, film clubs/cineforum, film festivals, open-air cinema

That includes NGOs (cultural societies, choirs, amateur theatre groups, youth and student organisations, the Slovenian and Friulian associations in Gorizia), venues with their own programme (incl. bars and clubs with regular live music), public institutions, music schools, universities and libraries that run public concerts or screenings, festivals with their own website, and aggregators (event portals, ticketing sites) that list many local organisers.
Leave out organisations that only do exhibitions, talks, workshops, sport, markets or religious services, unless they also host concerts, performances or screenings.

## Already known: re-check these and include them as rows
- Kulturni dom Nova Gorica: https://kulturnidom-ng.si/dogodki/
- SNG Nova Gorica: https://www.sng-ng.si/sl/spored/
- Kulturni dom Gorica: https://kulturnidom.it/wp/eventi/
- KC Lojze Bratuž: https://www.centerbratuz.org/dogodki.html
- Mostovna: https://www.mostovna.com/dogodki
- Kinemax Gorizia: https://www.kinemax.it/orari.php
- GO! 2025: https://www.go2025.eu/en/whats-up/events
- TIC Nova Gorica in Vipavska dolina: https://dogodki.turizem-novagorica-vipavskadolina.si/sl/koledar-dogodkov/
- Comune di Gorizia: https://www.comune.gorizia.it/it/events
- Carinarnica: https://www.carinarnica.org/blog/categories/events (looked dead)
- Knjigarna in kavarna Maks: https://knjigarna-maks.si/category/aktualno/ (looked dead)
- Circolo ARCI Gong and Enoteca Mama Angela (Gorizia): seemed Facebook-only; check whether they have a website

## Where to look
Don't rely on a few searches. Work through lists of organisations, then open each one's site:
- municipal culture grants (who received funding from MO Nova Gorica, Šempeter-Vrtojba, Comune di Gorizia) and municipal registers of societies/associations
- umbrella bodies and their member lists: JSKD Območna izpostava Nova Gorica and the local union of cultural societies; for the Slovenian community in Gorizia ZSKD, ZCPZ, SKGZ and SSO; Italian and Friulian cultural networks; the regional NGO hub for Goriška (regionalno stičišče NVO)
- the Culture.si directory (Nova Gorica)
- GO! 2025 and EZTS/GECT GO partner lists and small-project grantees (many local NGOs ran cross-border projects)
- the organisers named on aggregators: the TIC calendar, the Comune di Gorizia events, ERT FVG (regional theatre circuit), napovednik.com, ticketing sites
- event listings in local media: Primorske novice, Primorski dnevnik, Novi glas, Il Piccolo (Gorizia)
- searches in Slovenian and Italian: "kulturno društvo", "gledališka skupina", "pevski zbor", "napovednik", "dogodki", "abonma" / "associazione culturale", "circolo", "rassegna", "stagione", "cineforum", "concerti", "eventi", each with the place names above

## Rules
- Open every website you list. Never guess a URL or take it from a search snippet. If a site won't load for you, keep the row and say so in `notes`.
- `events_url` is the exact page that lists events (calendar, programme, or the news category where events get posted).
- Freshness is what I care about most: record the latest-dated event you actually saw on the site, plus one example event.
- I'd rather have a long, honest list than a short, polished one: include small and inactive organisations too, with the right status. But every row must be a real organisation.
- When you're unsure whether something is in scope, include it and explain in `notes`.

## Status (as of 9 October 2026)
- `active`: upcoming events listed, or an event on or after 9 Jul 2026
- `seasonal`: annual festival or series with a 2025 or 2026 edition, next dates not out yet
- `stale`: latest event between 9 Oct 2025 and 8 Jul 2026
- `dead`: latest event before 9 Oct 2025, or the site is down or parked
- `no_listing`: the website works but doesn't announce events
- `social_only`: no website, events only on Facebook/Instagram (list the ones you come across; don't hunt for them)

## Output
1. A short summary: counts by status and by country, the most important finds, and what you couldn't cover.
2. One CSV in a code block, one row per organisation, every field in double quotes, with these columns in this order:
   `name,type,side,municipality,zone,categories,website,events_url,last_event_date,upcoming_count,sample_event,language,status,social_url,notes`
   - `type`: ngo | public | venue | festival | aggregator
   - `side`: SI | IT
   - `zone`: core | ring
   - `categories`: music, theatre, film; join several with `|`
   - `last_event_date`: the latest event date listed on the site, future or past (YYYY-MM-DD)
   - `upcoming_count`: number of events after 9 Oct 2026 listed on the site (0 if none)
   - `sample_event`: one event you saw, written as date and title, e.g. 2026-10-17 Alba Caduca live
   - `language`: sl | it | en | fur; join several with `|`
   Output every row. Don't shorten or summarise the table.
3. Notes: organisations whose events are published on someone else's site, sites whose programme is only a PDF, and aggregators that already cover many organisers.
