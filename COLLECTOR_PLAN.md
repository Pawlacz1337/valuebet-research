# COLLECTOR_PLAN.md — kolektor kursów przy zerowym budżecie

Spisane 2026-09-30, po decyzji: budżet zerowy, własny scraper zamiast
płatnego API. Obowiązuje razem z `CLAUDE.md` — tam, gdzie ten plik jest
ostrzejszy, wygrywa ten plik.

---

## 0. Decyzje i dlaczego

- **Nie płacimy za API-Football.** Plan darmowy nie obejmuje bieżącego
  sezonu (API zwraca „Free plans do not have access to this season, try from
  2022 to 2024"), więc `ingest/snapshots.py` na darmowym kluczu nie zbierze
  nic. Moduł zostaje w repo, uśpiony. Nie kasujemy.
- **Kolektor zbiera najpierw KURSY, nie dane klasy B.** Powody, w kolejności
  wagi:
  1. Bez kursów nie ma EV, alertów ani produktu. Model mamy; cen wejścia
     nie mamy wcale.
  2. Historia z football-data to wyłącznie zamknięcie 1X2 (Pinnacle do
     2024/25, BFEC, B365, Max, Avg). Zero kursów polskich bukmacherów, zero
     O/U i AH (raport CLI 21:56). **Historia cen wejścia jest tak samo
     nieodtwarzalna jak kontuzje** — każdy dzień bez kolektora przepada.
  3. Model nie używa dziś żadnej danej klasy B. Wartość składów i kontuzji
     w Ekstraklasie jest niezbadana, a zamknięcie rynku i tak je zawiera.
  4. Darmowe źródła klasy B to głównie serwisy, których regulaminy
     zabraniają automatycznego pobierania albo które stoją za anty-botami.
- Klasa B wraca jako **Faza 2**, osobną decyzją, najwcześniej po dwóch
  tygodniach stabilnej Fazy 1.

---

## 1. Źródła i ich role

| źródło | co daje | rola | koszt |
|---|---|---|---|
| polscy bukmacherzy — własny scraper publicznych stron | 1X2, O/U, AH przed meczem; Ekstraklasa + I liga | **ceny wejścia**: EV, backtest właściwej strategii, zamknięcie u bukmachera | 0 zł, praca |
| The Odds API, plan darmowy | Pinnacle, Betfair Exchange, Matchbook: `h2h`, `totals`, `spreads`; **tylko Ekstraklasa** | **linia ostra**: CLV na wszystkich rynkach, bezpośredni benchmark totali | 0 zł, 500 kredytów/mies. |
| football-data.co.uk (już mamy) | zamknięcie 1X2: BFEC, B365, Max, Avg | CLV 1X2 z opóźnieniem, kontrola krzyżowa | 0 zł |

The Odds API (stan na 2026-09-30, strona dostawcy): 500 kredytów/mies.,
wszystkie rynki, **bez historii** w planie darmowym. Koszt wywołania `/odds`
= liczba rynków × liczba regionów; parametr `bookmakers` z ≤ 10 bukmacherami
liczy się jak 1 region. `/sports` nie kosztuje. Pinnacle według dostawcy:
„Odds are from public website which may incur a delay" — do zamknięcia
wystarczy. I liga nie jest pokryta.

**I liga nie ma linii ostrej w żadnym darmowym źródle.** CLV na I lidze
liczymy względem konsensusu polskich bukmacherów na zamknięciu (mediana
prawdopodobieństw po Shinie). Słabszy wzorzec — raportowany osobno, nigdy
uśredniany z Ekstraklasą.

---

## 2. Granice (nienaruszalne)

1. Tylko **publicznie widoczne kursy przedmeczowe**. Bez logowania, bez
   endpointów powiązanych z kontem, bez ciasteczek z przeglądarki Pawła.
2. **Regulamin i robots.txt przed pierwszą linijką adaptera.** Jeśli
   regulamin wprost zakazuje automatycznego pobierania danych z serwisu —
   źródło odpada. Werdykt z datą i cytatem w `docs/sources.md`.
   Powód praktyczny, nie tylko etyczny: Paweł ma tam konto, a naruszenie
   regulaminu to gotowy pretekst do zamknięcia konta z zatrzymaniem środków.
2a. **robots.txt obowiązuje — per host, łącznie z `Crawl-delay`** (decyzja
   2026-10-01, po `docs/sources.md`). Ścieżki zabronionej w robots.txt hosta,
   z którego faktycznie pobieramy, nie pobieramy. robots.txt działa per host
   (RFC 9309): endpoint kursów na innym hoście niż strona (API, CDN) podlega
   robots.txt **tamtego** hosta — sprawdź go, zanim uznasz źródło za
   stracone. Drugi zgodny wariant: kursy osadzone w HTML-u dozwolonej strony
   (stan początkowy aplikacji w `<script>`). Obchodzenia robots.txt nie ma w
   projekcie — uzasadnienie w `ROADMAP.md` §9.
3. **Wyzwanie anty-botowe = źródło odpada.** Captcha, Cloudflare Turnstile,
   Akamai, DataDome, JS-owe „sprawdzamy przeglądarkę" — nie obchodzimy ich
   ani Playwrightem, ani w żaden inny sposób.
4. Zero proxy, rotacji IP, podrabiania odcisku przeglądarki, udawania
   aplikacji mobilnej.
5. HTTP 403 lub 429 → to źródło stoi 24 h + alert. Bez agresywnych ponowień.
6. **Tempo ludzkie:** odstęp ≥ max(10 s, `Crawl-delay` hosta) między
   zapytaniami do jednej domeny (z losowym rozrzutem; Fortuna: 20 s),
   ≤ ~150 zapytań na dobę na bukmachera.
7. Playwright wyłącznie jednorazowo do rozpoznania, jeśli DevTools nie
   wystarczą. Polling tylko `httpx`.
8. Wyłącznie Ekstraklasa i I liga, wyłącznie przed meczem. Bez live.
9. Kursy bukmacherów nigdy nie są cechą modelu (reguła 19).
10. Sekrety (klucz The Odds API, token Telegrama) tylko w `.env`. Klucz
    The Odds API idzie w parametrze URL `apiKey` → **żaden zapisany ani
    zalogowany URL nie może go zawierać** (redakcja + test). Logger `httpx`
    loguje pełne URL-e na poziomie INFO — ustaw mu WARNING.

---

## 3. Architektura

### 3.1 Zasada nadrzędna: pobieraj głupio, parsuj później

```
Task Scheduler (co 15 min)
  └─ collector run   jeden punkt wejścia, idempotentny, plik blokady
       ├─ plan pobrań: co jest należne teraz (kadencja / kotwice)
       ├─ adaptery źródeł: httpx + throttle per domena
       ├─ SnapshotWriter → data/raw/odds/...   surowa odpowiedź + observed_at UTC
       └─ heartbeat      → data/raw/_heartbeat/...
parse   (osobno, powtarzalnie, na całym raw)
  raw → walidacja → TeamResolver → match_id → OddsSnapshot → data/interim/odds/
raport dzienny + alerty (Telegram)
```

Dlaczego tak:
- błąd parsera nigdy nie gubi danych — raw jest niemodyfikowalny (reguła 12),
  poprawiony parser przelicza całą historię;
- **pobieranie może ruszyć na żywo, zanim parser będzie gotowy**;
- zmiana formatu po stronie bukmachera psuje parsowanie, nie zbieranie.

`SnapshotWriter` z `ingest/snapshots.py` nadaje się bez zmian: odpowiedź
zapisujesz jako rekord, a w `context` URL **po redakcji**, kod HTTP, czas
odpowiedzi, identyfikator ligi. `observed_at` = chwila odebrania odpowiedzi.

### 3.2 Adapter źródła

Każde źródło to adapter z dwiema odpowiedzialnościami, trzymanymi osobno:

- `fetch` — wie, jakie URL-e odpytać i z jakimi nagłówkami; zwraca surową
  odpowiedź. Żadnej logiki biznesowej.
- `parse` — czysta funkcja: surowa odpowiedź → `ParseResult` = migawki +
  odrzucone (z powodem) + nierozpoznane nazwy. **Nic nie ginie po cichu.**

Rejestr źródeł w konfiguracji: domena, limit tempa, identyfikatory lig u
danego bukmachera, flaga `enabled`. Wyłączenie źródła = zmiana konfiguracji,
nie kodu.

### 3.3 Harmonogram

**v0 (Faza 1a):** lista meczów ligi co 30 min w godzinach 08:00–23:00 czasu
warszawskiego. Dwie ligi → ≤ 60 zapytań na dobę. Zamknięcie z dokładnością
do 30 min — na start wystarczy.

**v1 (Faza 1b):** kotwice liczone od `kickoff_utc` odczytanego z list:
T−24 h, T−6 h, T−2 h, T−60 min, T−30 min, T−10 min. Między kotwicami lista
ligi co 60 min. Strona pojedynczego meczu (pełne linie O/U i AH) tylko na
kotwicach.
- Oś eksperymentu `bet_lead_time` z `CLAUDE.md` = migawki decyzyjne (czas do
  gwizdka ok. 4–40 h) kontra zamknięcie; CLV raportowane w przedziałach czasu
  do gwizdka, nie w dwóch stałych punktach 24 h i 1 h (decyzja Pawła 2026-10-04).
- T−10 min to nasze zamknięcie.
- Zmiana godziny meczu między migawkami → zapisz historię zmian, przelicz
  kotwice. Mecz przełożony → zamknięcie liczone od faktycznego rozpoczęcia.

Task Scheduler co 15 min; kolektor sam decyduje, czy coś jest należne
(zwykle nie — kończy po sekundzie). Opcje zadania: „uruchom jak najszybciej
po pominiętym starcie", „wybudź komputer" (na laptopach z Modern Standby
bywa zawodne — heartbeat to pokaże), bez usypiania na zasilaczu w dni meczowe.

### 3.4 Luki są daną, nie błędem do zamiecenia

Laptop oznacza luki: sen, brak sieci, restart. Każdy przebieg zapisuje
heartbeat (start, koniec, per źródło: zapytania, sukcesy, błędy, kody HTTP).

W backteście kurs dla chwili `t` to **ostatnia migawka przed `t` w
tolerancji** (`PointInTimeStore.asof_join`, tolerancja 20 min na kotwicach).
Poza tolerancją → brak zakładu. **Nigdy** nie interpolujemy i nie
przeciągamy kursu w przód — to byłaby cena, której nikt nie oferował.

### 3.5 Tożsamość meczów

- Nazwy drużyn → `TeamResolver`, który nigdy nie zgaduje. Nierozpoznane →
  `data/interim/unresolved_names.parquet` + alert. Alias dopisuje człowiek
  do `data/team_aliases.yaml` (reguła 15). Pokrycie per źródło per dzień w
  raporcie.
- `match_id = make_match_id(competition, date, home, away)`, data w UTC.
  Zapisuj też `source_event_id`.
- **Kontrola zamiany gospodarz/gość:** ten sam mecz w dwóch źródłach z
  odwróconymi drużynami → wyjątek, nie ostrzeżenie. To klasyczny błąd
  scrapera, który po cichu produkuje „value" na faworycie.
- Druga kontrola: prawdopodobieństwo gospodarza po Shinie u jednego źródła
  bliskie prawdopodobieństwu gościa u pozostałych → flaga do przeglądu.

### 3.6 Rynki i walidacja

- Nazwy rynków bukmachera → `MARKET_OUTCOMES`: `1X2`, `OVER_UNDER` z linią,
  `ASIAN_HANDICAP` z linią. Linie ćwiartkowe (2.25, −0.75) zapisujemy tak,
  jak są; rozbicie przez `split_handicap` dopiero przy wycenie.
- Kompletność przed zapisem kanonicznym (reguła 17): niekompletny rynek
  zostaje tylko w raw i w liczniku odrzuceń.
- Sanity: kurs ≥ 1.01; booksum 1X2 w [1.00, 1.20], O/U i AH w [1.00, 1.15].
  Poza zakresem → odrzucenie z powodem. Rynek zawieszony → pominięty i
  policzony.
- Zapisuj wszystkie linie O/U i AH, które strona podaje bez dodatkowych
  zapytań. Linia „główna" bywa inna niż 2.5.
- `tax_factor` w kolektorze zostaje domyślne 0.88 (zachowawcze). Właściwy
  współczynnik dokłada moduł EV z konfiguracji z datami obowiązywania
  promocji (reguła 20). Nigdy 1.00 z domysłu — to fabryka fałszywego EV.

### 3.7 The Odds API

- `GET /v4/sports/soccer_poland_ekstraklasa/odds`,
  `bookmakers=pinnacle,<Betfair Exchange>,<Matchbook>` (dokładne klucze z
  listy dostawcy), `markets=h2h,totals,spreads`, `oddsFormat=decimal`,
  `dateFormat=iso`. Koszt: 3 kredyty za wywołanie; jedno wywołanie zwraca
  wszystkie nadchodzące mecze.
- Budżet 450 kredytów/mies. (50 zapasu). Kolejność ważności:
  1. zamknięcie — jedno wywołanie ~10 min przed każdym slotem godzinowym
     rozpoczęć (mecze o tej samej godzinie obsługuje jedno wywołanie);
  2. migawka decyzyjna — raz dziennie 08:30 Warszawa, gdy liga gra w ciągu 48 h
     (T−24 h usunięta 2026-10-04: dublowała migawki decyzyjne).
  Szacunek: ~35 kredytów na kolejkę, ~150–180 miesięcznie.
- Źródłem prawdy jest licznik zużycia z nagłówków odpowiedzi (nazwy w
  dokumentacji v4), nie lokalny plik. Pozostało < 60 → tylko zamknięcia;
  < 10 → stop + alert.
- Klucz w `.env` jako `VB_ODDS_API_KEY`. Brak klucza → głośny błąd, jak w
  `snapshots.py`.
- To jest legalna, udokumentowana usługa — **nie** obchodzimy nią niczego.
  Pinnacle i Betfair są w Polsce nielicencjonowane; ich strony bezpośrednio
  nie wchodzą w grę.

### 3.8 Alerty i raport

Telegram (token i chat id w `.env`), minimalny moduł `live/telegram.py` —
ten sam posłuży później do alertów value. Alert, gdy:
- źródło zawiodło 3 przebiegi z rzędu albo zwróciło 403/429;
- odsetek odrzuceń parsera > 5% w przebiegu;
- pojawiła się nierozpoznana nazwa drużyny;
- w dniu meczowym lista ligi zwróciła 0 meczów;
- kredyty The Odds API spadły poniżej progu.

Raport dzienny per źródło: zapytania, migawki, odrzucenia z powodami,
pokrycie aliasów, pokrycie kotwic, najdłuższa luka w heartbeat.

### 3.9 Testy — minimum

- **Zero sieci w testach.** Fixture w `conftest.py` podmienia transport
  `httpx`; test, który spróbuje wyjść do internetu, ma się wywalić.
- Parsery: nagrane odpowiedzi w `tests/fixtures/odds/<źródło>/`, testy
  złote. Przed zapisem fixture'a: bez ciasteczek, tokenów, identyfikatorów
  sesji.
- Throttle: fałszywy zegar, ≥ 10 s między zapytaniami do domeny.
- Kotwice i strefy czasowe: mecz 2026-10-24 17:30 czasu warszawskiego =
  15:30 UTC; mecz 2026-10-25 17:30 = **16:30 UTC** (tej nocy koniec czasu
  letniego).
- Zamiana gospodarz/gość w dwóch źródłach → wyjątek.
- Luka: brak migawki w tolerancji → brak zakładu, nie ffill.
- The Odds API: redakcja `apiKey` w zapisanym URL i w logach; progi kredytów.

### 3.10 Bukmacher bez zgodnej ścieżki odczytu: alert progowy (`k_min`)

Jeśli dla bukmachera, u którego gramy, nie ma ścieżki zgodnej z §2 pkt 2a,
system **nie czyta jego kursów**. Liczy prawdopodobieństwo uczciwe `p`
(Pinnacle po Shinie — silnik S z `ROADMAP.md`; albo model) i wysyła próg:

```
k_min = (1 + θ) / (p · tax_factor)          θ = minimalne EV, np. 0.02
„Lech–Legia, Over 2.5: grasz, jeśli Betclic daje ≥ 1.93"
```

Paweł sprawdza kurs w chwili kliknięcia — przy ręcznym stawianiu i tak to
robi, a przy okazji weryfikuje żywotność kursu. Koszt: brak automatycznego
skanowania tego bukmachera i brak historii jego cen. Historia powstaje z
dziennika zakładów: każdy zawarty zakład = ręczny wpis kursu, stawki i
godziny.

### 3.11 Skalowanie na kolejne ligi (rękaw A, po bramce G-A2)

Architektura to udźwignie, pod trzema warunkami:
1. **Rejestr lig w konfiguracji** — identyfikatory lig per źródło, aliasy
   drużyn per liga. Nowa liga = wpis w konfiguracji + aliasy + testy
   parsera, nie nowy kod.
2. **Strona meczu tylko z prescreenu.** Lista ligi (jedno zapytanie) daje
   główne rynki; pełne linie pobieramy tylko dla meczów, w których lista
   pokazuje cenę powyżej uczciwej z Pinnacle. Bez tego 6 lig rozsadza limit
   ~150 zapytań na dobę na bukmachera.
3. **Kredyty The Odds API są twardym sufitem.** Szacunek na weekend:
   ~40 slotów godzinowych w pięciu ligach. Same zamknięcia z dwoma rynkami
   (`h2h`, `totals`) to ~340 kredytów miesięcznie; trzy rynki ~520 — już
   ponad plan darmowy. Przy pięciu ligach: tylko zamknięcia, tylko dwa
   rynki, migawki decyzyjne raz dziennie (bez T−24 h, decyzja Pawła 2026-10-04).

---

## 4. Fazy

### Faza 0 — rozpoznanie (w trakcie przebiegu diagnostycznego)

**Paweł** — ok. 10 minut na bukmachera:
1. Okno prywatne, **niezalogowany**. Strona Ekstraklasy u bukmachera.
2. F12 → Network → filtr Fetch/XHR → odśwież stronę.
3. Znajdź odpowiedź z kursami: w polu wyszukiwania DevTools wpisz nazwę
   drużyny z tej kolejki (np. „Legia").
4. Prawy klik na zapytaniu → Copy → Copy as cURL (bash) → zapisz do
   `docs/discovery/<bukmacher>_ekstraklasa_curl.txt`. **Usuń linie
   `cookie:`, `authorization:` i nagłówki `x-…` z identyfikatorem
   urządzenia lub sesji** przed zapisem.
5. Prawy klik → Copy response → zapisz jako
   `docs/discovery/<bukmacher>_ekstraklasa_response.json`.
6. To samo dla I ligi i dla strony jednego meczu (pełne O/U, AH).
7. Jeśli w Fetch/XHR nie ma kursów, zajrzyj w zakładkę WS. Kursy tylko przez
   WebSocket → ten bukmacher idzie na później.

Kolejność bukmacherów: najpierw ten, u którego Paweł gra bez podatku
(bukmacher główny), potem dwóch największych — dla konsensusu i jako
zapas, gdy któryś odpadnie na regulaminie.

**Stan 2026-10-01:** `docs/discovery/` zawiera jeden pusty plik (0 bajtów).
Krytyczny jest Betclic: robots.txt `www.betclic.pl` zabrania wszystkich
query stringów, więc o wszystkim decyduje **host**, pod który faktycznie
idzie zapytanie z kursami (§2 pkt 2a). W pliku z cURL-em musi być widać pełny
adres. Przy okazji sprawdź, czy Fortuna albo STS mają własną promocję bez
podatku — bukmacher ze zgodną ścieżką odczytu i promocją byłby lepszym
głównym niż Betclic w trybie `k_min` (§3.10).

**Paweł** też: rejestracja w The Odds API (plan darmowy) → klucz do `.env`
— zrobione 2026-10-01, klucz działa.

**CLI** — tylko nowe pliki, dopóki trwa przebieg diagnostyczny:
1. Regulamin serwisu + robots.txt dla kandydatów → `docs/sources.md`:
   bukmacher, data sprawdzenia, werdykt, cytat z regulaminu, co mówi
   robots.txt, czy strona stawia wyzwanie anty-botowe.
2. Klient The Odds API + testy (mocki). Pierwsze prawdziwe wywołanie:
   darmowe `/sports`, dopiero gdy klucz jest w `.env`.
3. Gdy są pliki z `docs/discovery/`: jedno zapytanie `httpx` **bez
   ciasteczek** — czy odpowiada, czy nie ma wyzwania, jakie rynki zwraca.
   Endpoint wymagający ciasteczka, którego nie da się dostać zwykłym GET-em
   (bez wykonywania JS) → źródło odpada albo wraca do mnie.
4. `docs/discovery/` do `.gitignore` — to materiał roboczy, nie wchodzi do
   repo (repo ma być portfolio, więc kiedyś może być publiczne). Do
   `tests/fixtures/` trafiają tylko przycięte, oczyszczone odpowiedzi.
   Przed każdym commitem fixture'ów: grep na `cookie`, `authorization`,
   `token`, `session`. Trafienie = nie commitujemy.

### Faza 1a — pionowy przekrój: jeden bukmacher, tylko surowe dane

Pobieranie listy ligi (v0 z §3.3) → raw → heartbeat → Task Scheduler →
**włączone na żywo**. Parser może dojść później; surowe dane już się
zbierają. Cel: bukmacher główny zbiera dane przed najbliższą kolejką.

### Faza 1b — parser, kanonizacja, kotwice v1, raport, Telegram

Parser na nagranych odpowiedziach, przeliczenie całego raw zebranego w 1a,
kontrole z §3.5–3.6, raport dzienny, alerty.

### Faza 1c — The Odds API na żywo

Może iść równolegle z 1a, gdy tylko jest klucz. Harmonogram wg §3.7.

### Faza 1d — drugi i trzeci bukmacher

Dopiero gdy 1a–1b przetrwały jedną pełną kolejkę bez ręcznych poprawek.

### Faza 2 — klasa B (osobna decyzja)

Najwcześniej po dwóch tygodniach stabilnej Fazy 1. Składy to jedyna dana
klasy B z realnym potencjałem (ogłaszane ok. godzinę przed meczem). Źródło
wybierane tą samą procedurą: regulamin, robots.txt, bez anty-botów.
Kontuzje — najniższy priorytet.

---

## 5. „Faza 1 gotowa" — po dwóch kolejnych kolejkach

- ≥ 95% meczów Ekstraklasy z migawką zamknięcia (≤ 15 min przed gwizdkiem)
  u bukmachera głównego **i** w The Odds API
- 100% pokrycia aliasów; każde odrzucenie parsera ma powód
- heartbeat bez luk > 60 min w oknach meczowych albo luki wyjaśnione
- `uv run pytest`, `ruff`, `mypy --strict` czysto; test „zero sieci" zielony

---

## 6. Czego nie robić

- agregatory (OddsPortal, BetExplorer, Flashscore, Sofascore): regulaminy,
  anty-boty, udawanie cudzego frontu
- Pinnacle i Betfair bezpośrednio: nielicencjonowane w Polsce; linia ostra
  wyłącznie przez The Odds API
- kursy live, niższe ligi, rynki egzotyczne (strzelcy, kartki, rożne)
- cokolwiek z zalogowanej sesji Pawła
- „naprawianie" luk interpolacją

---

## 7. Co to odblokowuje

- **CLV na żywo względem Pinnacle** na każdym rynku Ekstraklasy — metryka
  nadrzędna (reguła 26), od dziś mierzona, a nie odtwarzana
- **bezpośredni benchmark totali**: `P(over)` Pinnacle vs nasze — G4 w
  wersji rynkowej, na danych zbieranych od teraz (historycznie niemożliwy)
- **eksperyment `bet_lead_time`**: migawki decyzyjne (ok. 4–40 h do gwizdka)
  kontra zamknięcie, CLV w przedziałach czasu do gwizdka, na prawdziwych cenach wejścia
- **detektor value i alerty** — ostatnie ogniwo produktu
