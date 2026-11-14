# valuebet

System do wyszukiwania zakładów +EV na polskim rynku bukmacherskim.
Uczciwa cena z rynku ostrego (Pinnacle po Shinie) → kurs polskiego
bukmachera grającego bez podatku → próg i stawka → przegląd dnia.
**Człowiek klika ręcznie.** Bot nigdy nie składa zakładu.

Odpowiadaj po polsku. Komentarze i docstringi po polsku, nazwy
identyfikatorów po angielsku.

---

## Dlaczego ten projekt jest trudny (przeczytaj, zanim coś zaproponujesz)

Polski podatek obrotowy 12% od stawki oznacza, że próg opłacalności to
`p * k >= 1.1364`, czyli wymagana przewaga ~13.6%. To jest poza zasięgiem
kogokolwiek na rynkach płynnych. Cały projekt opiera się na promocjach
"gra bez podatku" (współczynnik 1.00 zamiast 0.88) — bez nich matematyka
się nie spina i **należy to powiedzieć wprost, a nie szukać obejścia**.

Konsekwencja dla Ciebie jako asystenta: jeśli backtest pokaże yield
powyżej ~8%, domyślnym wyjaśnieniem jest błąd w kodzie, nie odkrycie.
Traktuj wysoki wynik jako objaw bugu i szukaj go, zanim pogratulujesz.

---

## Reguły nienaruszalne

Złamanie którejkolwiek z nich unieważnia cały wynik backtestu. Jeśli
zadanie wymaga złamania reguły, **zatrzymaj się i zapytaj**, zamiast
obchodzić ją po cichu.

### Look-ahead bias

1. Każda cecha dla meczu o czasie `t` liczona jest **wyłącznie** z
   danych dostępnych przed `t`. Zero wyjątków.
2. Wszystkie znaczniki czasu są **timezone-aware w UTC**. Naiwny
   `datetime` w kodzie produkcyjnym to błąd (ruff `DTZ` to wyłapuje).
   Godzina rozpoczęcia meczu jest granicą odcięcia — nie data.
3. Zabronione: `groupby().transform()`, `.mean()`, `.std()`, `fillna()`
   liczone na pełnym zbiorze przed podziałem train/test. Statystyki
   normalizacyjne liczy się na trainie i **stosuje** do testu.
4. `rolling()` i `expanding()` zawsze z `closed="left"` albo jawnym
   `.shift(1)`. Okno zawierające bieżący mecz to leakage.
5. Tabela ligowa, forma, Elo, xG — stan **przed** kolejką, nie po niej.
   Jeśli źródło daje tabelę końcową, jest bezużyteczna.
6. Kontuzje i składy: tylko jeśli masz znacznik czasu publikacji
   wcześniejszy niż mecz. Retrospektywna lista kontuzji to leakage.
7. Kurs bukmachera: używamy kursu z momentu, w którym realnie
   postawilibyśmy zakład. Kurs zamknięcia (`PSCH` itd.) służy **tylko**
   do liczenia CLV, nigdy jako cena wejścia.

### Backtest

8. Wyłącznie **walk-forward** po sezonach lub oknach czasowych. Losowy
   `train_test_split` i `KFold` bez wariantu czasowego są zabronione.
9. Zbiór do kalibracji jest rozłączny ze zbiorem do trenowania modelu i
   ze zbiorem testowym. Kalibracja na trainie to przeciek.
10. Hiperparametry stroimy na foldach walidacyjnych wewnątrz trainu,
    nigdy patrząc na wynik testu. Jeśli dostroiłeś coś po zobaczeniu
    yieldu na teście, wynik jest spalony — powiedz o tym.
11. Każdy raport z backtestu podaje **liczbę zakładów** i przedział
    ufności yieldu. Yield bez `n` i CI nie znaczy nic. Przy średnim
    kursie 2.0 rozróżnienie 3% od zera wymaga ~4300 zakładów.

### Dane

12. `data/raw/` jest **niemodyfikowalne**. Nigdy nie nadpisuj ani nie
    czyść pliku w raw. Transformacje zapisują do `data/interim/`.
13. Format: parquet. CSV tylko na wejściu z zewnętrznych źródeł.
    Wyjątek: dziennik zakładów `data/bets/bets.csv` — append-only i
    czytelny dla człowieka (`TOR_S_PLAN.md` §7); reguła 14 obowiązuje.
14. Każdy zapisany zbiór ma kolumnę `ingested_at` (UTC) i `source`.
15. Normalizacja nazw drużyn przechodzi przez
    `ingest/team_mapping.py`. Nowy alias dopisujemy do słownika, nie
    łatamy fuzzy-matchem w miejscu wywołania.

### Wycena

16. Usuwanie marży: **wyłącznie** `pricing/shin.shin_probabilities`.
    Normalizacja proporcjonalna (`(1/k) / sum(1/k)`) jest zabroniona w
    kodzie produkcyjnym — zawyża longshoty i produkuje fałszywe +EV.
    Wolno jej użyć tylko jako punktu odniesienia w testach.
17. Shin wymaga **kompletnego rynku**. Podanie 2 z 3 wyników 1X2 daje
    bezsensowny booksum. Waliduj kompletność przed wywołaniem.
18. Model zwraca prawdopodobieństwa **skalibrowane**. Surowy
    `predict_proba` z LightGBM/XGBoost nie nadaje się do liczenia EV.
    Kalibracja izotoniczna albo Platt na osobnym zbiorze.
19. Kurs rynkowy **nie może** być cechą modelu. Model uczy się wtedy
    odtwarzać rynek i z definicji nie może go pobić. Dopuszczalne
    wyłącznie jako shrinkage target, i to jawnie oznaczone.
    **Wyjątek — tor S (ROADMAP, od 2026-10-01):** wyceniacz rynkowy
    `p = Shin(Pinnacle)` w chwili decyzji to osobna strategia, nie cecha
    modelu. Raportowany osobno, nigdy nie mieszany z modelem bez jawnego
    shrinkage.
19a. Macierz DC **nie wycenia** totali, handicapów ani kombinacji
    (`STEP4_ENSEMBLE.md` §11.10: oś otwartości ściśnięta ~2×). Do takich
    rynków wyłącznie λ, μ dopasowane do kursów Pinnacle 1X2 **i** totali,
    z korektą DC `ρ ≈ −0.07` (zwalidowaną na Premier League).
20. EV liczymy ze współczynnikiem podatkowym podanym jawnie:
    `ev = p * k * tax_factor - 1`, gdzie `tax_factor` ∈ {1.00, 0.94, 0.88}.
    Nigdy nie zaszywaj 0.88 w kodzie — to parametr konfiguracji.
    Warunki promocji (progi, okna, definicja AKO) — wyłącznie z
    `docs/promocje.md`: cytat z paragrafu regulaminu albo jawnie oznaczony
    wariant pesymistyczny. Stała bez jednego z tych dwóch to błąd.
    Podatek od wygranej (10% przy wypłacie kuponu > 2280 zł) to osobny
    czynnik `winnings_factor` ∈ {1.00, 0.90}, nigdy wliczany w `tax_factor`.

### Stawkowanie

21. Kelly zawsze **ułamkowy**, domyślnie 0.25. Pełny Kelly na modelu z
    błędem estymacji prowadzi do ruiny — to nie jest ostrożność, to
    matematyka. 0.5 wyłącznie po bramce G-K (ROADMAP §7), sprawdzanej
    kodem, nie flagą. Nigdy powyżej 0.5. **Do Filaru 3 c = ½ jest
    zablokowane w kodzie** — brak implementacji korekty
    `e_użyte = e · min(1, CLV/EV)` (`TOR_S_PLAN.md` §5, FSA #0 F-06).
    Odblokowanie: implementacja korekty + test + FSA, nie zmiana stałej.
22. Kelly uwzględnia podatek:
    `f* = (p * k * tax - 1) / (k * tax - 1)`.
23. Twardy limit: `min(f*, 0.02)` bankrolla na zakład.

### Metryki — w tej kolejności

24. Log loss → reliability diagram → **CLV vs zamknięcie Pinnacle po
    Shinie** → symulowany yield.
25. **Accuracy jest zabroniona** jako metryka jakości modelu. Value
    betting żyje z kalibracji, nie z trafień.
26. CLV jest metryką nadrzędną. Model, który nie bije zamknięcia, nie
    ma przewagi — niezależnie od tego, co pokazuje yield na backteście.

### Audyt i spójność kodu (od 2026-10-01)

27. **FULL_SYSTEM_AUDIT** — pełny audyt według `docs/FULL_SYSTEM_AUDIT.md`,
    wykonywany przez subagenta `full-system-auditor`, jest obowiązkowy:
    po zamknięciu każdego Filaru (ROADMAP §0), przed każdym przejściem
    między Filarami i przed pierwszym zakładem za prawdziwe pieniądze.
    Przejście dozwolone tylko przy zerze otwartych znalezisk KRYTYCZNYCH
    i POWAŻNYCH **oraz** po akceptacji Pawła w czacie. Akceptacja może być
    udzielona z góry, warunkowo („jeśli audyt da zero — przechodzimy") —
    wtedy raport FSA cytuje ją dosłownie z datą i sprawdza warunek. Liczbę
    otwartych znalezisk podaje audytor, nie ten, kto naprawiał.
28. Backtest finansowy i tryb live używają **tych samych** modułów
    (`pricing/fair.py`, `pricing/ev.py`, `pricing/kelly.py`,
    `live/bets.py`, `backtest/clv.py`). Równoległa implementacja tej logiki
    w backteście jest zabroniona — backtest ma testować kod, który postawi
    pieniądze, a nie jego kopię.
29. Moduł bez wywołań poza testami to dług, nie gotowa funkcja. Raportuj
    go jako „niepodłączony" (2026-10-01: fair, ev i kelly przez pół dnia —
    dwa błędy KRYTYCZNE wyszły dopiero przy audycie). Każdy taki moduł ma
    pozycję w `ROADMAP.md` §2: „czeka na podłączenie w Filarze N" albo
    „uśpiony". Pilnuje tego `tests/test_rule29_wiring.py`.
30. **Bezpiecznik nigdy nie jest parametrem opcjonalnym.** Parametr, którego
    pominięcie osłabia ochronę — granica czasu (`as_of`, `now`,
    `decision_time`, `kickoffs`), podatek, tryb paper/real, ekspozycja,
    raport CLV — jest wymagany, keyword-only, bez wartości domyślnej i bez
    `None` znaczącego „nie sprawdzaj". Test bezpiecznika sprawdza ścieżkę
    **niebezpieczną** (pominięcie, wartość z przyszłości, wartość spoza
    dziedziny), nie tylko bezpieczną. Pilnuje tego
    `tests/test_rule30_guards.py`. (FSA #0, 2026-10-01: F-04, F-19, F-20 —
    trzy bezpieczniki opcjonalne, każdy z zielonym testem ścieżki
    bezpiecznej. To ten sam wzorzec, który dał oba błędy KRYTYCZNE.)
31. **Naprawa zaczyna się od czerwonego testu.** Najpierw test regresji,
    który na starym kodzie failuje z właściwego powodu, potem łatka, potem
    zielony. Wynik przed i po — w `reports/audit/FIX_LOG_<filar>.md`. Test,
    który przechodził przed naprawą, nie jest dowodem naprawy. Zakazane,
    żeby coś przeszło: `skip`, `xfail`, osłabienie asercji, nowe
    `type: ignore` albo `noqa`.

---

## Granice projektu

- **Nie automatyzujemy składania zakładów.** Regulaminy polskich
  bukmacherów zakazują zautomatyzowanego dostępu, sankcją bywa
  zamknięcie konta z zatrzymaniem środków. Nie proponuj clickerów,
  nie pisz kodu logującego się na konto bukmachera.
- Scraping: tylko odczyt publicznie dostępnych kursów, z rozsądnym
  throttlingiem. Bez omijania captchy i bez podszywania się pod
  mobilną aplikację.
- **Każde** zapytanie sieciowe idzie przez jeden klient
  (`valuebet/net/http.py`): odstęp per host ≥ max(10 s, `Crawl-delay`),
  stan dzielony między procesami, robots.txt (`COLLECTOR_PLAN.md` §2).
  Bezpośrednie `httpx`/`requests`/`urllib` poza nim są zabronione
  (FSA #0 F-26).
- Playwright wyłącznie do jednorazowego rozpoznania endpointów i
  odświeżania sesji. Polling idzie przez `httpx`.
- Nie dodawaj rynków o znanych problemach z integralnością (Setka Cup,
  najniższe ligi z minimalnymi limitami) bez wyraźnej decyzji
  użytkownika. Wysokie "value" tam zwykle oznacza adverse selection.

---

## Stos i konwencje

- Python 3.12+, `uv` do zarządzania zależnościami. **Nie używaj pip.**
- `uv run pytest` / `uv run ruff check` / `uv run mypy src`
- Typowanie: mypy strict. Nowy kod ma pełne adnotacje.
- Logi: `logging` ze standardowej biblioteki; logger `httpx` na poziomie
  WARNING (klucze API siedzą w URL-ach). Bez `print` w kodzie
  produkcyjnym. (`structlog` i `pydantic-settings` nigdy nie weszły do
  kodu — usunięte z zależności, FSA #0 F-11.)
- Konfiguracja: zmienne `VB_*` z `.env` (wzór w `.env.example`), warunki
  promocji w `config/bookmakers.yaml`. Bez sekretów w repo.

## Układ

Stan na 2026-10-11 (Filar 1, wariant B). „Niepodłączony” = bez ścieżki od
punktu wejścia (reguła 29, `tests/test_rule29_wiring.py`).

```
src/valuebet/
  schema.py       kanoniczne modele (Match, Selection, OddsSnapshot)
  config.py       config/strategy.yaml (θ, observed_at, kapitał 10 000, min. stawka) + live.yaml (1000 zł)  bramka §4
  closing.py      CLOSING_TOLERANCE 30 min, CLOSING_TARGET 7 min (kolektor + CLV)
  provenance.py   frozen_commit(), generated_by — etykiety raportów
  fsutil.py       zapis atomowy, blokada plikowa
  net/
    http.py       JEDYNY klient sieciowy: odstęp ≥ 10 s/host, robots.txt
  ingest/
    raw_store.py  jedyny zapis do data/raw + manifest sha256
    team_mapping.py  aliasy drużyn (reguła 15)
    football_data.py        POL.csv (extra leagues)
    football_data_main.py   główne ligi (E0, D1, …)
    odds_api.py     klient The Odds API, budżet 450 (UsageGuard)
    odds_collector.py  kolektor S1, kotwice, heartbeat (data/state/)
  features/
    base.py       mechanizmy point-in-time (tu mieszka leakage!)  uśpiony
    elo.py        Elo przed meczem
  models/
    dixon_coles.py   DC — zamknięty jako model 1X2
    elo_ordinal.py   Elo → 1X2
  pricing/
    shin.py       Shin (reguła 16; bez zbieżności → NaN / strict)
    fair.py       Pinnacle po Shinie w chwili decyzji   bramka §4
    ev.py         EV, k_min, reżim Betclica, T13        bramka §4
    kelly.py      Kelly ¼, limity, wyłącznik, G-K raportowana  bramka §4
  backtest/
    metrics.py           log loss, reliability, bootstrap
    elo_baseline.py      walk-forward Elo (cechy liczone tu — leakage!)
    dixon_coles_baseline.py  walk-forward DC
    market_benchmark.py  nachylenia, instrument sumy goli
    lockbox.py           lockbox toru M (zużyty 2026-10-01), parse_season
    replay.py            football-data → migawka decyzyjna, zamknięcie, wynik osobno
    financial.py         pętla zdarzeń backtestu na modułach live (reguła 28)
    strategies.py        tabela strategii A, A3, B365, B-BW, B-WH, D, E (runner kroku 5)
    strategy_c.py        C: kontrfaktyczny reżim Betclica, dublety (bramka §4, runner)
    clv.py               CLV kuponu vs zamknięcie   bramka §4
  live/
    bets.py       dziennik kuponów (append-only CSV)    bramka §4
    digest.py     przegląd dnia, Telegram/plik          niepodłączony → Filar 2
```

## Klasy dostępności danych

Ten podział rządzi tym, co wolno zbacktestować:

- **Klasa A** — wyprowadzalne z historii wyników (Elo, forma, odpoczynek,
  atut boiska). Rekonstruowalne point-in-time. Backtest na pełnej historii.
- **Klasa B** — egzogeniczne z czasem obserwacji (kontuzje, składy, zmiana
  trenera, wartości rynkowe). **Nierekonstruowalne wstecz.** Wolno ich
  używać wyłącznie na okresie zebranym przez własny kolektor ze znacznikiem
  czasu obserwacji. Takiego kolektora nie ma (`ingest/snapshots.py`
  usunięty 2026-10-02, FSA #0 F-28) — **dopuszczalny okres klasy B jest
  dziś pusty**.
- **Klasa C** — przewidywane składy, newsy przedmeczowe. Nie istnieją
  historycznie. Tylko live, nigdy w backteście.

Historia kontuzji z Transfermarktu **nie jest** klasą B — jest
rekonstrukcją retrospektywną i jej użycie w backteście to look-ahead bias.
Jeśli pojawi się pokusa "przecież mamy daty urazów", odpowiedź brzmi nie.

## Mechanizmy cech

Są **dwa** i mieszanie ich to najczęstsze źródło przecieku:

- **Fakty sekwencyjne** (wyniki, strzały, gole): oś w formacie długim
  (`build_timeline`) + `rolling_prior`, który robi `shift(1)` PRZED
  `rolling()`. Nigdy odwrotnie.
- **Fakty egzogeniczne** (kontuzje, składy): `PointInTimeStore.asof_join`,
  czyli `merge_asof` z `allow_exact_matches=False`. Zawsze podawaj
  `tolerance` — bez niej kontuzja sprzed pół roku trafi do dzisiejszej cechy.

Moment odcięcia to `asof_utc = kickoff_utc - bet_lead_time`, nie gwizdek.
`bet_lead_time` jest osią eksperymentu: porównaj CLV dla 24h i 1h, żeby
empirycznie sprawdzić, czy dane o składach są u tego bukmachera cokolwiek
warte.

## Zanim uznasz zadanie za skończone

- `git add` wyłącznie z jawnymi ścieżkami — nigdy `-A` ani `.`
  (2026-10-01: tak wypadł z repo `.env.example`)
- naprawa znaleziska z audytu → wpis w `reports/audit/FIX_LOG_<filar>.md`
  z wynikiem testu przed i po (reguła 31)
- dotknąłeś `ingest/` albo `data/` → `uv run python scripts/verify_raw.py`
  przechodzi
- `uv run pytest` przechodzi
- `uv run ruff check src tests` czysto
- `uv run mypy src` czysto
- Jeśli dotknąłeś `features/` lub `backtest/`:
  - `uv run pytest -k future_poison` przechodzi
  - **dopisałeś nową cechę → dopisz ją do `_build_all` w
    `tests/test_features_base.py`.** Test trucizny sprawdza tylko te
    cechy, które są w pipeline testowym. Cecha poza nim nie jest chroniona.
  - uruchom subagenta `backtest-auditor` i napraw to, co znajdzie

## Czego od Ciebie oczekuję

Chłodna ocena inżynierska zamiast optymizmu. Jeśli podejście jest
wątpliwe, powiedz to wprost i uzasadnij liczbami. Jeśli liczba wygląda
zbyt dobrze — znajdź błąd, zanim się ucieszysz.
