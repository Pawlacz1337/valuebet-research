# Źródła kursów — werdykty regulaminowe i techniczne

Wymóg z `COLLECTOR_PLAN.md` §2 pkt 2: **regulamin i robots.txt przed
pierwszą linijką adaptera.** Powód nie jest tylko etyczny — Paweł ma u
tych bukmacherów konto, a naruszenie regulaminu to gotowy pretekst do
zamknięcia konta z zatrzymaniem środków.

Data sprawdzenia: **2026-10-01**. Sprawdzał: Claude Code (CLI), Faza 0.

Ten plik jest żywy. Regulaminy się zmieniają — przy każdej zmianie
adaptera sprawdź datę powyżej i, jeśli minął kwartał, zweryfikuj ponownie.

---

## Jak czytać werdykty

| Werdykt | Znaczenie |
|---|---|
| **ODPADA** | Regulamin wprost zakazuje, albo stoi wyzwanie anty-botowe. Nie obchodzimy. |
| **WARUNKOWO** | Brak wyraźnego zakazu odczytu, ale są ograniczenia co do sposobu. Wymaga decyzji Pawła. |
| **DO WERYFIKACJI** | Nie sprawdzone. Nie wolno pisać adaptera. |

Rozróżnienie, które przewija się niżej i jest najważniejsze w całym pliku:
**automatyczne SKŁADANIE zakładów to co innego niż automatyczny ODCZYT
publicznych kursów.** Pierwsze jest zakazane wprost i projekt tego nie
robi (`CLAUDE.md`, „Granice projektu"). Drugie bywa nieuregulowane w
regulaminie, a ograniczone w `robots.txt`.

## Klient sieciowy — tempo i robots.txt w kodzie (2026-10-02, FSA #0 F-26)

Każde zapytanie idzie przez `src/valuebet/net/http.py`: odstęp per host
≥ max(10 s, `Crawl-delay`), stan dzielony między procesami
(`data/state/throttle/`), robots.txt z cache 24 h (`data/state/robots/`),
ścieżka zabroniona albo robots.txt niedostępny → odmowa. Hosty API, których
robots.txt nie dotyczy (udokumentowane API, nie strony) — stała
`API_HOSTS` w kodzie, odstęp 10 s obowiązuje także je:

| host | usługa |
|---|---|
| `api.the-odds-api.com` | The Odds API (sekcja niżej) |
| `api.telegram.org` | Telegram Bot API — przegląd dnia (`live/digest.py`) |

---

## The Odds API — ZIELONE

Legalna, udokumentowana usługa pośrednicząca. Nie obchodzimy nią niczego:
Pinnacle i Betfair nie mają polskiej licencji, więc ich strony są poza grą,
a dostawca sprzedaje dostęp do danych jako swój produkt.

**Zweryfikowane na żywo 2026-10-01** jednym darmowym wywołaniem `/sports`
(0 kredytów, klucz z `.env`):

- odpowiedź: 83 dyscypliny/ligi, w tym 46 piłkarskich;
- `soccer_poland_ekstraklasa` — **obecna i aktywna** (`active=True`,
  title `Ekstraklasa - Poland`);
- **I ligi NIE MA** na liście. Dla I ligi nie będzie benchmarku totali z
  tego źródła — to ograniczenie do zapisania w planie, nie do obejścia.

Klucz idzie w parametrze URL `apiKey`, więc moduł redaguje go w każdym
zapisanym URL-u, w każdym komunikacie wyjątku i podnosi logger `httpx` do
WARNING (`ingest/odds_api.py`, testy w `tests/test_odds_api.py`).

Budżet: 450 kredytów/mies. z 500 (50 zapasu); kredyt za rynek, dziś dwa
rynki (`h2h`, `totals`) → 2 kredyty za wywołanie `/odds`. Plan z
`scripts/odds_budget.py` (2026-10-07): 374/mies. Źródłem prawdy są nagłówki
`x-requests-remaining` / `x-requests-used` / `x-requests-last`, nie licznik
lokalny.

Terminarz: `GET /v4/sports/{sport}/events` — **bezpłatne** (dokumentacja v4:
„does not count against the usage quota”), od rundy 0e jedyne źródło
terminarza kolektora, odświeżane co ≥ 60 min na ligę (3 ligi → ~72
zapytania/dobę). Bezpiecznik: odpowiedź z `x-requests-last > 0` wyłącza
`/events` do decyzji człowieka (`events_cost_alarm`). Dozwolone decyzją
Pawła 2026-10-03 (`docs/FSA0_NAPRAWY.md` §8).

---

## Betclic — WARUNKOWO, decyzja Pawła

Kandydat na bukmachera głównego (promocja „Gra Bez Podatku 2.0",
`CONTEXT.md` §2).

### Regulamin

Źródło: `Regulamin zakładów wzajemnych`, wersja z **08.06.2026 v3**,
`https://dam.begmedia.com/rox/images/Global/COMMON/TnC/PL/Regulamin_zak_ad_w_wzajemnych_08.06.2026_v3.pdf`
(22 strony, pobrane i przeszukane 2026-10-01).

> [Fragment usunięty z wersji publicznej: dotyczył prywatnego konta autora i korespondencji z obsługą bukmachera.]

**pkt 3.8 — czego Użytkownik zobowiązuje się nie robić, cytaty dosłowne:**

> 3.8.1. korzystania z oprogramowania powodującego zachwianie pracy lub
> przeciążenie systemów teleinformatycznych BEM lub innych podmiotów
> biorących bezpośredni lub pośredni udział w świadczeniu usług drogą
> elektroniczną;

> 3.8.3. obchodzenia lub podejmowania przez Użytkownika czynności
> zmierzających do obejścia zabezpieczeń systemów teleinformatycznych BEM
> lub innych podmiotów biorących bezpośredni lub pośredni udział w
> świadczeniu usług drogą elektroniczną.

### Co z tego wynika

1. [Fragment usunięty z wersji publicznej: dotyczył prywatnego konta autora i korespondencji z obsługą bukmachera.]
2. **Odczytu publicznych kursów regulamin nie zakazuje wprost.** Nie
   znalazłem w 22 stronach ani jednego wystąpienia zakazu scrapingu,
   eksploracji danych czy automatycznego pobierania treści. Przeszukane
   wzorce: `zautomatyzow`, `automatyczn`, `robot`, `bot`, `scrap`,
   `oprogramowani`, `skrypt`, `program komputerow`, `eksploracj`,
   `data mining`, `nieuprawnion`, `ingerencj`, `interfejs`, `API`.
3. **Ograniczenia co do sposobu są:** 3.8.1 zabrania obciążania systemów,
   3.8.3 obchodzenia zabezpieczeń. Tempo z `COLLECTOR_PLAN` §2 pkt 6
   (≥ 10 s na domenę, ≤ ~150 zapytań/dobę) mieści się w 3.8.1 z zapasem.
   3.8.3 oznacza: jeśli endpoint wymaga ciasteczka, którego nie da się
   dostać zwykłym GET-em, **źródło odpada** — dobieranie się do niego jest
   obchodzeniem zabezpieczenia.

### robots.txt — tu jest problem

`https://www.betclic.pl/robots.txt`, pobrane 2026-10-01, **całość pliku**:

```
User-agent: *
Disallow: /*?*
```

Jedna reguła, ale szeroka: **zabrania wszystkich URL-i z query stringiem.**
Endpointy XHR z kursami praktycznie zawsze mają parametry (id ligi, id
meczu, rynek), więc robots.txt obejmuje dokładnie to, co chcielibyśmy
pollować.

`robots.txt` nie jest prawem i nie jest częścią regulaminu, ale jest
**oświadczoną, maszynowo czytelną polityką serwisu**.

### Werdykt

**WARUNKOWO — wymaga świadomej decyzji Pawła, nie mojej.** Regulamin nie
zakazuje odczytu, ale robots.txt obejmuje docelowe endpointy. Zderzenie
tych dwóch rzeczy to decyzja o apetycie na ryzyko wobec własnego konta, a
nie kwestia techniczna. Do czasu decyzji: **nie piszę adaptera Betclica.**

Jeśli decyzja będzie „nie" — nie tracimy modelu. Tracimy jedno źródło
kursów do porównań; The Odds API zostaje, a kursy bukmachera, u którego
realnie stawiamy, można odczytywać ręcznie w momencie zakładu.

### Przy okazji znalezione

`https://dam.begmedia.com/rox/images/Global/COMMON/TnC/PL/Bez_Podatku_2.0_T_Cs_21.05.2026_v2.pdf`
— regulamin promocji „Bez Podatku 2.0", wersja 21.05.2026 v2. To jest
dokument, którego `CONTEXT.md` §2 wymaga od Pawła do weryfikacji (czy
ratio AKO liczy się po liczbie kuponów czy po obrocie, minimalna stawka
kwalifikująca, klauzula o nadużywaniu promocji). **Nie czytałem go** —
jest poza zakresem Fazy 0, ale adres jest teraz znany.

---

## STS — DO WERYFIKACJI (regulamin), robots.txt sprawdzony

Największy bukmacher w Polsce, kandydat na konsensus.

### robots.txt

`https://www.sts.pl/robots.txt`, pobrane 2026-10-01, całość:

```
User-agent: *
Allow: /pl/user/wplata/
Disallow: /index.php*
Disallow: /pl/user/
Disallow: /returnFromPayu.php
Disallow: /ru/
Disallow: /uk/
Disallow: *action=offer*
Disallow: *actionpage*
Disallow: *btag*
Disallow: *day=*
Disallow: *page=*
Disallow: *parent=*
Disallow: *resetpassword*
Disallow: *resultDate*
Disallow: *show-ticket-detail*
Disallow: *switchToTicket*
Disallow: /redirect*

Sitemap: https://www.sts.pl/sitemap.xml
Sitemap: https://www.sts.pl/blog/sitemap_index.xml
```

Reguły są **punktowe, nie całościowe** — w przeciwieństwie do Betclica nie
ma zakazu wszystkich query stringów. Istotne: `Disallow: *action=offer*`
dotyczy wprost ofert, więc URL oferty w tym kształcie jest wykluczony.
Czy endpoint kursów ma taki parametr — rozstrzygnie dopiero plik z
`docs/discovery/`.

### Regulamin

**NIE SPRAWDZONY.** Nie wolno pisać adaptera.

Metoda: znaleźć `Regulamin zakładów wzajemnych` (najpewniej PDF),
przeszukać wzorcami z sekcji Betclica, zacytować dosłownie z numerem
punktu. Dopóki tego nie ma, werdykt pozostaje DO WERYFIKACJI.

---

## Fortuna — DO WERYFIKACJI (regulamin), robots.txt sprawdzony

### robots.txt

`https://www.efortuna.pl/robots.txt`, pobrane 2026-10-01, całość:

```
Sitemap: https://www.efortuna.pl/sitemap.xml
User-Agent: *
Crawl-delay: 20
# private account / ticket pages - not indexable
Disallow: /my-account
# user profile, bonus area & registration pages
Disallow: /profil-uzytkownika
Disallow: /uzytkownik/
Disallow: /rejestracja
# query-param crawl traps on offer/results pages
Disallow: /*?filter=*
Disallow: /*?rateFrom=*
Disallow: /*?redirect=*
Disallow: /*?type=*
Disallow: /*?selectDates=*
Disallow: /*?date=*
Disallow: /*?pop=*
Disallow: /*?import=*
```

Najbardziej przyjazny z czterech: **jawny `Crawl-delay: 20`**, czyli
serwis wprost podaje akceptowalne tempo. Nasze ≥ 10 s z
`COLLECTOR_PLAN` §2 pkt 6 jest **za szybkie wobec tej deklaracji** — dla
Fortuny trzeba ustawić ≥ 20 s. Zakazy dotyczą kont, rejestracji i
konkretnych parametrów filtrujących, nie ofert jako takich.

### Regulamin

**NIE SPRAWDZONY.** Jak wyżej.

---

## Superbet — DO WERYFIKACJI (regulamin), robots.txt sprawdzony, sygnał ostrzegawczy

### robots.txt

`https://www.superbet.pl/robots.txt`, pobrane 2026-10-01. Plik jest długi;
fragmenty istotne dla nas, dosłownie:

```
User-agent: *
Allow: /*?title=
Allow: /*?ct=m
Disallow: /*.html$
Disallow: /*?*
Disallow: */offer-event/*
...
Allow: /kursy/pilka-nozna/*-vs-*
Disallow: /kursy/pilka-nozna/*-vs-*?t=offer
Disallow: /kursy/pilka-nozna/
```

Oraz osobny blok na końcu — **wymienia imiennie ~40 botów, w tym agentów
AI, i zabrania im wszystkiego**:

```
User-agent: AI2Bot
...
User-agent: NovaAct
User-agent: Operator
...
Disallow: /
```

### Co z tego wynika

1. `Disallow: /*?*` jak u Betclica — wszystkie query stringi.
2. `Disallow: */offer-event/*` i `Disallow: /kursy/pilka-nozna/*-vs-*?t=offer`
   obejmują **dokładnie** ścieżki z kursami. Strona meczu jest dozwolona
   (`Allow: /kursy/pilka-nozna/*-vs-*`), ale wariant z ofertą — nie.
3. Imienna lista blokowanych botów, z `NovaAct` i `Operator` (agenci AI),
   to **wyraźnie zadeklarowana intencja** serwisu wobec automatów. Nie
   dotyczy nas literalnie, bo nie udajemy żadnego z nich, ale nie da się
   tego czytać jako zaproszenia.

### Werdykt

**DO WERYFIKACJI regulaminowo, a technicznie najmniej obiecujący z
trzech.** Robots.txt wyklucza docelowe ścieżki wprost i precyzyjnie.
Proponuję traktować jako ostatniego w kolejce.

---

## Wyzwania anty-botowe — stan nierozstrzygnięty

`COLLECTOR_PLAN` §2 pkt 3: captcha, Cloudflare Turnstile, Akamai,
DataDome, JS-owe „sprawdzamy przeglądarkę" = **źródło odpada**, nie
obchodzimy.

Czego da się powiedzieć dziś: `robots.txt` wszystkich czterech domen
pobrał się zwykłym żądaniem HTTP bez ciasteczek. To **nic nie dowodzi** —
pliki `robots.txt` są z zasady wystawiane bez ochrony, a wyzwanie
anty-botowe stawia się na stronach i endpointach z treścią.

Rozstrzygnięcie wymaga jednego żądania `httpx` bez ciasteczek pod
**prawdziwy endpoint kursów** (`COLLECTOR_PLAN` Faza 0, CLI pkt 3). Do
tego potrzebny jest plik z `docs/discovery/`.

**Stan `docs/discovery/` na 2026-10-01:** jest tam jeden plik,
`bukmacher_url.txt.txt`, o rozmiarze **0 bajtów**. Nie ma więc ani cURL-a,
ani nagranej odpowiedzi. Endpointów **nie zgaduję** — zgadnięty adres to
albo ślepy strzał, albo trafienie w coś, czego nie miałem prawa dotknąć.

---

## football-data.co.uk — historia kursów do Filaru 1 (2026-10-08)

### robots.txt (2026-10-08 13:36, `data/state/robots/www.football-data.co.uk.json`)

`User-agent: *` / `Disallow:` (puste) — ścieżki z plikami (`/mmz4281/`,
`/notes.txt`) **dozwolone** dla UA projektu. Ten sam plik ma `Disallow: /`
dla agentów AI: `GPTBot`, `ChatGPT-User`, `Google-Extended`, `Anthropic-AI`,
`Claude-Web`, `ClaudeBot`, `PerplexityBot`, `Applebot-Extended`, `CCBot`,
`Meta-ExternalAgent`, `Diffbot`, `Omgilibot`. Konsekwencja (decyzja Pawła
2026-10-08): pobieranie plików uruchamia **Paweł**
(`scripts/ingest_football_data.py`), nie asystent AI. Asystent wysłał jedno
zapytanie o plik — `notes.txt`, 2026-10-08 13:36, zanim odczytał treść
robots.txt.

### Warunki serwisu i nasze zasady (Paweł, 2026-10-08)

Warunki football-data według Pawła (2026-10-08; tekstu strony asystent nie
pobierał — zob. robots.txt wyżej):

- dane są przeznaczone dla **osób prywatnych**, nie dla produktów
  komercyjnych ani do trenowania z użyciem botów/AI;
- prośby o zgodę serwis ignoruje;
- przy przeciążeniu serwera dane mogą zniknąć.

Zasady projektu wobec tego źródła:

- **jednorazowy ingest** (2026-10-08, 148 plików + `notes.txt`, uruchomił
  Paweł); kolejne uruchomienie pobiera wyłącznie brakujące pliki
  (`ingest_files` pomija zweryfikowane sumą kontrolną) — **bez ponownego
  pobierania całości**;
- **uczciwy User-Agent** projektu (`net/http.py`, `USER_AGENT`), odstęp
  ≥ 10 s na host, robots.txt;
- **CSV nigdy w publicznym repo**: `data/raw/*` jest w `.gitignore`;
  w repo tylko raporty kolumn (`reports/ingest/`), bez kursów i wyników.

Plan prośby o zgodę do właściciela serwisu („courtesy mail”) —
**skreślony** (serwis prośby ignoruje).

### Moment obserwacji kursów sprzed meczu — ZAŁOŻENIE, nie fakt

`notes.txt` (raw `football_data_main/notes.*.txt`, pobrane 2026-10-08),
dosłownie:

> Betting odds for weekend games are collected Friday afternoons, and on
> Tuesday afternoons for midweek games.

Opis dotyczy **obecnej praktyki serwisu**. Nie jest zweryfikowany dla
starszych sezonów (2019/20–2024/25) — plik nie podaje daty ani zakresu
obowiązywania. Reguła konserwatywna (decyzja Pawła 2026-10-08), jedno miejsce
wyboru wariantu: `config/strategy.yaml` → `fd_observed_at_rule`, kod
`ingest/football_data_main.py` → `ObservedAtRule`, `pre_match_observed_at`:

| gwizdek (czas London) | `observed_at` (przebieg główny) | wariant wrażliwości |
|---|---|---|
| piątek–poniedziałek | piątek tego weekendu, 18:00 Europe/London | 23:59 Europe/London |
| wtorek–czwartek | wtorek tego tygodnia, 18:00 Europe/London | 23:59 Europe/London |
| gwizdek ≤ `observed_at` | mecz wyłączony ze strategii przedmeczowych, licznik per liga i sezon w raporcie kolumn | jw. |

Mecze przełożone (kurs mógł być zebrany pod pierwotny termin) — ograniczenie
nienaprawialne z tych plików. Filar 1: po głównym przebiegu A–F przebieg
wrażliwości z wariantem 23:59, obie liczby obok siebie, bez uśredniania.

### Strefa czasowa kolumny `Time` — test na meczach o znanej godzinie

`notes.txt` strefy **nie podaje** („Time = Time of match kick off”).
Hipoteza: Europe/London (`KICKOFF_TZ`). Decyzja Pawła 2026-10-08: reguła
obowiązuje tylko, gdy zgadzają się wszystkie przypadki; niezgodność, zmiana
formatu między sezonami albo brak kolumny `Time` → STOP i raport.

| przypadek | mecz | rzeczywisty gwizdek (źródło) | oczekiwane w pliku (London) | w pliku | wynik |
|---|---|---|---|---|---|
| D1, lato, najstarszy sezon | Bayern–Hertha 16.08.2019 | 20:30 CEST ([fcbayern.com](https://fcbayern.com/en/matches/profis/bundesliga/2019-2020/fc-bayern-muenchen-hertha-bsc-16-08-2019/statistics): „Fri \| 16/08/19 \| 20:30”) | 19:30 | 19:30 (`D1-1920`, „Bayern Munich - Hertha”) | zgodne |
| D1, zima | RB Leipzig–Bayern 20.01.2023 | 20:30 CET ([bundesliga.com](https://www.bundesliga.com/de/bundesliga/news/tipico-blog-rb-leipzig-fc-bayern-munchen-topspiel-kracher-jahresstart-22190): „20.30 Uhr”) | 19:30 | 19:30 (`D1-2223`, „RB Leipzig - Bayern Munich”) | zgodne |
| D1, najnowszy sezon | Bayern–RB Leipzig 22.08.2025 | 20:30 CEST ([fcbayern.com](https://fcbayern.com/kidsclub/de/news/2025/08/vorbericht-1.-bundesliga-spieltag-fc-bayern---rb-leipzig): „Freitag, 22. August 2025, 20:30 Uhr”) | 19:30 | 19:30 (`D1-2526`, „Bayern Munich - RB Leipzig”) | zgodne |
| SP1 | Real Madrid–Barcelona 26.10.2024 | 21:00 CEST — wyliczone z 14:00 czasu Ekwadoru (UTC−5) ([Expreso](https://www.expreso.ec/deportes/real-madrid-vs-fc-barcelona-fecha-hora-ver-clasico-espana-218415.html)); dowód pośredni | 20:00 | 20:00 (`SP1-2425`, „Real Madrid - Barcelona”) | zgodne |
| Ekstraklasa, zima | Legia–Lech 26.10.2025 | 20:15 CET ([meczyki.pl](https://www.meczyki.pl/newsy/pilka-nozna/legia-warszawa-lech-poznan-typy-i-kursy-na-mecz-26-10-2025/284292)), 19:15 UTC ([FotMob](https://www.fotmob.com/matches/lech-poznan-vs-legia-warszawa/z32dp)) | 19:15 | 19:15 (`POL.csv`) | zgodne |
| Ekstraklasa, lato | Lech–Legia 26.04.2026 | 15:30 UTC ([FotMob](https://www.fotmob.com/livescores/3346633)); jedna strona FotMob podaje 25.04 16:00 UTC — duplikat, niezgodny z wynikiem i kolejką | 16:30 | 16:30 (`POL.csv`) | zgodne |

**Wynik (2026-10-08, dane z ingestu `82f3963`): zgodne wszystkie 6 przypadków.**
Kolumna `Time` obecna i w formacie `HH:MM` we wszystkich 154 plikach
(22 ligi x 7 sezonów), bez zmiany formatu między sezonami → reguła
**Europe/London obowiązuje** (`KICKOFF_TZ`).

Zimą London = UTC, więc przypadki zimowe nie odróżniają czasu UK od UTC;
rozstrzygają letnie (Bayern–Hertha, Bayern–Leipzig, Lech–Legia). Test liczy
`scripts/ingest_football_data.py` (sekcja „Strefa kolumny `Time`” w
`reports/ingest/<commit>/COLUMNS.md`).

---

## Podsumowanie

| Źródło | Regulamin | robots.txt wobec kursów | Anty-boty | Werdykt |
|---|---|---|---|---|
| The Odds API | legalna usługa, zgodne z przeznaczeniem | n/d | n/d | **ZIELONE, zweryfikowane na żywo** |
| Betclic | brak zakazu odczytu | `Disallow: /*?*` — obejmuje | nieznane | **WARUNKOWO — decyzja Pawła** |
| STS | **nie sprawdzony** | punktowo, `*action=offer*` | nieznane | **DO WERYFIKACJI** |
| Fortuna | **nie sprawdzony** | punktowo; `Crawl-delay: 20` | nieznane | **DO WERYFIKACJI** |
| Superbet | **nie sprawdzony** | wprost wyklucza ścieżki kursów | nieznane | **DO WERYFIKACJI, najmniej obiecujący** |

Adaptera nie ma prawa dostać żadne źródło poza The Odds API, dopóki jego
wiersz w tej tabeli ma „nie sprawdzony" albo „nieznane".
