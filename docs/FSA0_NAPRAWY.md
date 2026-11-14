# FSA0_NAPRAWY.md — naprawy po FSA #0 i przejście do Filaru 1

Spisane 2026-10-02 po decyzji Pawła (11:33). Wiąże razem z `CLAUDE.md`
(reguły 1–31), `docs/FULL_SYSTEM_AUDIT.md`, `docs/promocje.md` i raportem
`reports/audit/FSA_2026-10-01_F0.md` (dalej: **raport**). Numery F-xx są
numerami z raportu; tam są mechanizm, linie i reprodukcja. Pozycje A-xx
dopisał Architekt po przeglądzie tej specyfikacji (2026-10-02).

---

## 0. Decyzje i zakres

- Znalezisk jest **32** (F-01…F-32): **18 POWAŻNYCH**, 14 DROBNYCH, zero
  KRYTYCZNYCH. „F-01 do F-25” z wiadomości Pawła to skrót — naprawiamy
  **wszystkie 18 POWAŻNYCH**, także F-26, F-28 i F-32, DROBNE z §3, dziury
  W.6, W.8, W.10 z raportu oraz A-01…A-03 poniżej.
- **F-25:** wariant najmniej korzystny dla gracza, ze stałą i komentarzem w
  kodzie; powrót przy optymalizacji. Specyfikacja: `docs/promocje.md`.
- **Każda naprawa najpierw oblewa test** (`CLAUDE.md` reguła 31).
- **Akceptacja przejścia F0 → F1 udzielona z góry, warunkowo** — cytat do
  raportu FSA #0b: „Jeśli testy i audyt dadzą zielone światło – wreszcie
  otworzy bramkę i automatycznie przejdzie do Filaru 1” (Paweł,
  2026-10-02 11:33). Liczby do warunku podaje audytor (§5–§6).

### Pozycje dopisane przez Architekta

- **A-01 (traktuj jak POWAŻNE) — `backtest/clv.py:102`.** `closing` jest
  kluczowane samym `match_id`: jedno `p_close` na mecz dla każdego wyniku
  i rynku. Dwa zakłady na jeden mecz (1 i powyżej 2.5) dostają to samo
  `p_close`. Dziś latentne (moduł niepodłączony), w Filarze 1 —
  KRYTYCZNE: test znanej odpowiedzi z `BACKTEST_FIN_PLAN.md` §4.1 by padł.
  Naprawa: klucz `(match_id, market, outcome, line)`. Test (dziś czerwony):
  dwa zakłady na jeden mecz, różne wyniki → różne `p_close`.
- **A-02 (POWAŻNE) — podatek od wygranej.** 10% od wygranej powyżej
  2280 zł z jednego kuponu (`CONTEXT.md` §2) nie jest nigdzie modelowany.
  Specyfikacja: `docs/promocje.md` T13 — osobny czynnik `winnings_factor`
  w `ev`, `min_odds`, `kelly_fraction`, rozliczeniu (dziennik, backtest,
  `reconcile_bets.py`). Wymagany parametr (lista reguły 30).
- **A-03 (DROBNE) — W.6.** `shin_probabilities` przy braku zbieżności
  zwraca normalizację proporcjonalną (reguła 16). Gałąź awaryjna zwraca
  wynik oznaczony tak, że nie da się go użyć bez jawnego sprawdzenia
  (np. `p = None` albo wyjątek w wariancie `strict`), a wszyscy trzej
  konsumenci z raportu przechodzą na ten wariant.

## 1. Protokół jednej naprawy

1. **Test regresji** w `tests/regression/test_fsa0_<id>_<opis>.py` opisuje
   **ścieżkę niebezpieczną** (pominięty parametr, dane z przyszłości,
   wartość spoza dziedziny, drugi zapis do raw), nie bezpieczną.
2. **Czerwony na starym kodzie, z właściwego powodu**: `AssertionError`,
   `Failed: DID NOT RAISE` albo inna asercja o zachowaniu. `TypeError` z
   powodu zmienionej sygnatury nie jest dowodem — test buduje obiekty przez
   pomocnika, który odfiltrowuje nieznane argumenty, żeby stary kod doszedł
   do asercji. `ImportError` dopuszczalny tylko tam, gdzie znaleziskiem jest
   **brak mechanizmu** (F-12, F-26, F-24) — oznacz w logu „brak modułu”.
3. Wpis PRZED w `reports/audit/FIX_LOG_F0.md`: commit bazowy (= commit
   PRZED tej naprawy), komenda, ostatnie linie wyniku pytest.
4. Łatka. Test zielony, cały zestaw zielony (meta-test reguły 30 jest
   zielony dzięki liście przejściowej z §3 etap B), `ruff`,
   `mypy --strict`.
5. Commit. **Jeden na znalezisko** albo na grupę z §3 opisaną jako jedna
   pozycja. `git add` z jawnymi ścieżkami. Komunikat `fix(FSA0 <id>): …`.
   Hash commita i wynik PO dopisujesz do logu w **następnym** commicie
   (wiersz logu nie może zawierać hasha commita, w którym sam powstaje).
6. Zakazane: `skip`, `xfail`, osłabianie asercji, nowe `type: ignore`,
   `noqa`, `pragma: no cover`, usuwanie testów. **Wyjątki z wpisem w
   logu:** testy usuwanego `ingest/snapshots.py` (F-28) i usuwanego
   `BetJournal.real_turnover` (F-03); testy, które dziś oczekują `c = 0.5`
   po G-K, **zmieniają oczekiwanie** na 0.25 (F-19/F-06) — to zmiana
   specyfikacji (`CLAUDE.md` reguła 21), nie osłabienie.
7. Wyłącznie tekstowe DROBNE (F-27, F-29): dowodem jest diff. Wszystko
   inne, łącznie z dokumentami sprawdzalnymi mechanicznie (F-30, F-32),
   dostaje test.

**`FIX_LOG_F0.md`:** nagłówek, tabela
`| id | klasa | test | PRZED (commit, wynik) | PO (commit, wynik) | rewers | stan |`,
pod nią blok na każde znalezisko, plus wiersze `KOLEKTOR` (wyłączony /
włączony / heartbeat po włączeniu). **Wznawianie:** przerwana sesja → nowa
czyta log i kontynuuje od pierwszego wiersza bez PO; jeśli `KOLEKTOR` jest
„wyłączony” bez „włączony”, ten stan jest częścią wznowienia.

**Rewers** (§4, i audytor w §5) — dla każdej naprawy na **jej** commicie
PRZED: `git worktree add ../vb-rewers-<id> <commit>`, `uv sync` w tym
katalogu, skopiowane z HEAD: plik testu i pomocnicze `tests/conftest.py`
oraz `tests/helpers/` (jeśli istnieją), uruchomienie `uv run --project
../vb-rewers-<id> pytest <test>`. Test sprawdza na starcie, że
`valuebet.__file__` leży w katalogu worktree. Wynik: czerwony z powodu z
pkt 2. Worktree usuwasz po zapisie wyniku.

## 2. Kolejność

| etap | treść | dlaczego tu |
|---|---|---|
| 0 | agent, stan bazowy, kolektor wyłączony | punkt odniesienia |
| A | F-09, F-10, **F-14 → F-12** (z F-17) | manifest dopiero po wyniesieniu stanu z raw |
| B | meta-testy reguły 30 → F-05, F-04, A-01, F-19 + F-06, F-20; F-01 + F-21 + W.8 | bezpieczniki przed wszystkim, co je wywołuje |
| C | F-25 + F-08 (kod), A-02, F-02 + F-03 + F-31 | reżim podatkowy i dziennik |
| D | F-26 → F-15 + F-16 → F-13; **F-25b** (regulamin słowo w słowo); kolektor włączony | sieć, potem to, co z niej korzysta |
| E | F-24, F-28 + meta-test reguły 29, F-32, A-03, F-07, F-11, F-18, F-22, F-23 + W.10, F-27, F-29, F-30 | proweniencja, porządek, dokumenty |
| F | weryfikacja całości (§4) | — |
| G | FSA #0b (§5) | audytor bez kontekstu napraw |
| H | bramka (§6) → Filar 1 (§7) | — |

## 3. Specyfikacja napraw

### Etap 0 — start

- **Agent.** `.claude/agents/full-system-auditor.md` śledzony przez gita
  (`git ls-files`), frontmatter poprawny (`name`, `description`, `tools`,
  `model`). Popraw w treści „26 reguł nienaruszalnych plus 27–29” na
  „reguły 1–31” i dopisz: „Na końcu raportu, jako ostatnią linię, wypisz
  dokładnie: `BRAMKA: KRYT=<n> POWAŻNE=<m> OTWARTE=[<id>, …]`”. Commit.
  Jeśli `full-system-auditor` **nie jest** na liście dostępnych agentów w
  tej sesji → **STOP** z prośbą o restart CLI. Bez zastępowania go agentem
  ogólnym.
- Stan bazowy: `pytest`, `ruff`, `mypy`, pokrycie — do logu.
- **Kolektor wyłączony na etapy A–D:** `schtasks /change /tn valuebet-odds
  /disable`, wiersz `KOLEKTOR` w logu. Zadanie uruchamia kod z drzewa
  roboczego, a w etapach A–D zmieniają się jego ścieżki, budżet i sieć.
  Ta przerwa w danych jest zamierzona — audytor dostaje ją w zleceniu (§5).

### Etap A — repozytorium i dane

**F-09, F-10 (DROBNE).** Zacommituj `TOR_S_PLAN.md`, `reports/audit/` i
bieżące zmiany dokumentów Architekta. `.gitignore`: usuń drugi `.env`,
dodaj `.coverage`, `htmlcov/`, `data/bets/*`, `data/state/*`,
`data/manifest/*`, `config/*.local.yaml` (wzorem `data/raw/*`). `git
ls-files data/` — poza `.gitkeep` nic tam nie może być śledzone. Test:
`git check-ignore` dla tych ścieżek.

**F-14 (POWAŻNE) — stan kolektora poza raw.**
- `state.json` i `heartbeat.jsonl` (dopisywany, więc zmienia hash) →
  `data/state/odds_api/`. Zapis stanu atomowo (plik tymczasowy w tym samym
  katalogu + `os.replace`, ponowienie z krótką przerwą przy
  `PermissionError` — Windows, antywirus, OneDrive).
- **Wyjątek od reguły 12, jednorazowy:** przeniesienie istniejących plików
  stanu z raw (to nie są dane surowe, leżały tam przez błąd): kopia →
  zgodność hashy → usunięcie z raw; hashe w logu.
- Przenieś też odwołania: `scripts/odds_budget.py` (`STATE`),
  `docs/task_scheduler.md` (ścieżka heartbeatu). Klucze `done` przenoszone
  bez zmian — żadna zebrana kotwica nie jest pobierana drugi raz.
- Test (dziś czerwony): domyślne ścieżki stanu i heartbeatu nie leżą pod
  `data/raw/`.

**F-12 (POWAŻNE) + F-17 (DROBNE) — manifest i jeden zapis do raw.**
- `ingest/raw_store.py: write_raw(subdir, stem, suffix, data) -> Path`:
  nazwę generuje sam — `<stem>.<UTC %Y%m%dT%H%M%S%fZ>.<8 znaków sha256><suffix>`
  (bez dwukropków, NTFS); zapis do pliku tymczasowego w
  `data/raw/.incoming/`, hash, przeniesienie na nazwę docelową tak, by
  istniejący plik powodował błąd (`os.link` + usunięcie tymczasowego albo
  `os.rename`, które na Windows odmawia przy istniejącym celu; na POSIX
  sprawdź `open(…, "xb")`), dopisanie wiersza do
  `data/manifest/raw_sha256.jsonl` pod blokadą. Ścieżki w manifeście
  względne wobec `data/raw`, z `/`. To zamyka F-17.
- **Blokada:** plik `<cel>.lock` tworzony przez `os.open(O_CREAT | O_EXCL)`,
  z przeterminowaniem po 60 s — przenośne, bez `fcntl`. Ta sama dla
  manifestu i dla stanu throttlingu (F-26).
- Wszyscy piszący do raw przechodzą przez `write_raw`: `football_data`,
  `football_data_main`, `odds_collector`, `validate_instrument`, pobranie
  regulaminu. Test AST: żadnego `open(…, "w"/"a"/"x")`, `write_text`,
  `write_bytes`, `to_csv`, `to_parquet` z celem pod `data/raw` poza
  `raw_store.py`.
- `scripts/verify_raw.py`: kod 1, gdy plik bez wpisu, hash niezgodny albo
  wpis bez pliku; pomija `.incoming/`. `--init-baseline` raz, dla plików
  już istniejących (`recorded_by = "baseline-2026-10-02"`; integralności
  sprzed tej daty nie da się udowodnić — tak to zapisz).
  `--adopt-orphan <ścieżka>` — jedyna sankcjonowana naprawa po awarii
  między przeniesieniem a manifestem: dopisuje wpis z
  `recorded_by = "adopted-<data>"`, każda adopcja w logu i w raporcie FSA.
- Artefakty ignorowane przez gita, na których stoją liczby
  (`reports/**/*.parquet`), → `data/manifest/artifacts_sha256.jsonl`, ta
  sama funkcja hashująca.
- Kotwica dla audytu: liczba wierszy manifestu i sha256 tych wierszy
  (prefiks), nie hash całego rosnącego pliku.
- Test (dziś czerwony): zmieniony bajt w pliku z tymczasowego raw →
  `verify_raw` zwraca błąd; drugi zapis pod tę samą nazwę → wyjątek.

### Etap B — bezpieczniki

**Meta-testy reguły 30 — najpierw.**
- `tests/test_rule30_guards.py`, AST po `src/valuebet/{pricing,backtest,live,ingest,net}/**`
  i `scripts/**`.
- `GUARD_PARAMS = {as_of, now, decision_time, kickoffs, tax_factor,
  clv_report, bankroll, peak_bankroll, open_exposure, match_exposure,
  edge_threshold, winnings_factor, bets, usage_guard, journal_path,
  regime_config}` oraz
  `mode` **tylko** w `pricing/`, `live/`, `backtest/`. Taki parametr
  funkcji/metody: bez wartości domyślnej, keyword-only, adnotacja bez
  `None`. Pole dataclassy: bez wartości domyślnej i bez `None` w typie.
  Lista może tylko rosnąć.
- Drugi test: zakaz `datetime.now(`, `datetime.utcnow(`, `time.time(`,
  `date.today(` w `pricing/`, `backtest/`, `live/` i w funkcjach
  bibliotecznych `ingest/` — zegar bierze wyłącznie punkt wejścia
  (`scripts/`, blok `__main__`) i przekazuje go jako `now`.
- **Lista przejściowa** `KNOWN_VIOLATIONS` w teście: każde dzisiejsze
  naruszenie z nazwą naprawy, która je usuwa. Kolejność: test bez listy →
  czerwony, wypisuje naruszenia (PRZED w logu) → lista uzupełniona →
  zielony → commit. Wpis, którego naruszenia już nie ma, też czerwieni
  test — każda naprawa musi usunąć swoje wpisy. **Pusta lista jest
  warunkiem §4.** Przydział:
  `clv.as_of` → F-04; `fair.kickoffs` → F-20; pola i `stake`
  `KellyPolicy` → F-19; pozycyjne `tax_factor` w `ev`, `min_odds`,
  `evaluate`, `double_ev`, `kelly_fraction`, `KellyPolicy.stake` i
  `edge_threshold` → F-05; `BetclicTaxRegime.bets` → F-25;
  `BetJournal.path` (→ `journal_path`), `settle` z `datetime.now` → F-02; `fetch_odds`
  `usage_guard` → F-15; `odds_collector` (`is_due`,
  `decision_window_utc`, `decision_due`, `due_calls`, `_write_raw`,
  `run_once`, `refresh_schedule` z `now=None`) → F-13 i F-15; reszta, w tym
  `scripts/`, → pozycja „R30-porządek” na końcu etapu B.
- Wyjątek od listy nazw tylko w stałej `EXEMPT` z uzasadnieniem przy każdym
  wpisie — audytor ją czyta.

**F-05 (POWAŻNE) — walidacja podatku i progu.** Jedna funkcja
`validate_tax_factor()` w `ev.py`, wołana przez `ev`, `min_odds`,
`evaluate`, `double_ev`, `kelly_fraction`. `tax_factor` i `edge_threshold`
keyword-only. `edge_threshold` skończone i ≥ 0; źródło: `config/strategy.yaml`
(`edge_threshold: 0.02`), czytane przez punkty wejścia i przekazywane
jawnie. Test (dziś czerwony): `min_odds(p, 0.5, …)` zwraca liczbę.

**F-04 (POWAŻNE) — CLV.** `as_of: datetime` wymagane, keyword-only, ze
strefą. Poza agregatem (i liczone osobno jako `excluded_future`):
`placed_at > as_of`; mecz bez kickoffu; kickoff `> as_of`; migawka
zamknięcia z `observed_at > as_of` → n/d. Test (dziś czerwony): dziennik z
meczem z przyszłości o wysokim CLV wchodzi do CI.

**A-01** — opis w §0. Razem z F-04 albo osobno; osobny wpis w logu.

**F-19 + F-06 (POWAŻNE) — Kelly.**
- Usuń `clv_to_ev_ratio` i całą gałąź korekty (martwy kod).
- `c = 0.25` na każdej ścieżce. `HALF_KELLY_ENABLED: Final = False` z
  komentarzem: włączenie wymaga implementacji `e_użyte = e · min(1,
  CLV/EV)` (`TOR_S_PLAN.md` §5), testu i FSA w Filarze 3; nie jest czytane
  z `.env` ani z argumentu.
- `gk_passed` liczone dalej i wystawiane w decyzji (`gk_would_unlock`) —
  backtest raportuje, kiedy bramka by się otworzyła. Liczba zakładów do
  G-K = liczba **kuponów** prawdziwych z dziennika tego przebiegu.
- Jedyna droga konstrukcji: `KellyPolicy.from_journal(*, bankroll,
  peak_bankroll, clv_report: ClvReport, n_real_bets, open_exposure,
  match_exposure)` — wszystko wymagane, `ClvReport` typowany (bez
  `getattr`). Konstrukcja bezpośrednia → wyjątek.
- Testy (dziś czerwone): konstrukcja wprost z `clv_report_unlocks_gk=True`
  daje `c = 0.5`; pominięcie `open_exposure` omija limit 15%.
  Parametryzowany test: `c ≤ 0.25` na każdej ścieżce.

**F-20 (POWAŻNE) — wycena.** `kickoffs` wymagane; mecz bez kickoffu → brak
wyceny; `decision_time ≥ kickoff` → brak wyceny. `fair_prices` zwraca obok
cen licznik pominięć według powodu. Test (dziś czerwony): migawka z
trwającego meczu bez `kickoffs` zostaje wyceniona.

**F-01 + F-21 + W.8 (POWAŻNE) — lockbox.**
- Zakres: lockbox to zbiór **toru M** — Ekstraklasa, 2025/26–2026/27,
  zużyty 2026-10-01. Opisz to w docstringu `lockbox.py`.
- `parse_season(label) -> "RRRR/RR"`: przyjmuje `2025/26`, `2025-26`,
  `2025/2026`, `2025-2026`; rok końcowy = początkowy + 1; wszystko inne →
  `ValueError`. Jedyne miejsce zamiany etykiet sezonu.
- `assert_no_lockbox`: brak kolumny `season`, `NaN` albo etykieta nie do
  sparsowania → `ValueError`; porównanie po parsowaniu. Test (dziś
  czerwony): ramka z `"2025-26"` przechodzi po cichu.
- Kanoniczne etykiety `"2025/26"` i `"2026/27"` jako literały tylko w
  `lockbox.py` — test grep w plikach toru M (`scripts/run_*.py`,
  `scripts/validate_instrument.py`, `backtest/elo_baseline.py`,
  `backtest/dixon_coles_baseline.py`, `backtest/market_benchmark.py`).
  Kody sezonów w URL-ach football-data (`2526`) tego nie dotyczą.
  `validate_instrument.py` importuje stałe stąd i woła `assert_no_lockbox`
  przed liczeniem.
- Rejestr `reports/lockbox_views.jsonl` z jednym wpisem (2026-10-01,
  `lockbox_3433f2c.json`, odnośnik do pliku proweniencji z F-24 — odnośnik
  może wskazywać plik tworzony w etapie E). `run_lockbox.py` przy ≥ 1
  wpisie kończy się błędem, bez flagi obejścia.
- **Test `run_lockbox.main()` nie może obejrzeć lockboxa** — także na
  starym kodzie (PRZED, rewers). Funkcje ładujące dane i liczące ewaluację
  podmień w teście na wartownika, który rzuca `LockboxViewAttempted`.
  Dziś test jest czerwony właśnie przez wartownika, nie przez przebieg.
- Test meta: każdy skrypt, który woła producentów liczb toru M
  (`run_elo_baseline`, `run_dixon_coles_baseline`, `clustered_slope`),
  woła też `assert_no_lockbox`; wyjątek tylko `run_lockbox.py`. Kod Filaru 1
  tych producentów nie woła.
- Pokrycie: `uv run pytest --cov=valuebet.backtest.lockbox --cov-branch
  --cov-fail-under=100`.

### Etap C — podatek i dziennik

**F-25 + F-08 (POWAŻNE) — reżim Betclica, wariant pesymistyczny.**
Wiersze T1–T13 z `docs/promocje.md` — każdy z testem.
- Stałe z odnośnikiem do wiersza (`# promocje.md T5`), blok komentarza
  „WARIANT PESYMISTYCZNY — decyzja Pawła 2026-10-02 (FSA #0 F-25); powrót
  przy optymalizacji”, `BETCLIC_READING: Final = "pesymistyczny-2026-10-02"`.
- `BetclicTaxRegime(*, now, bets, regime_config)` — `RegimeConfig` z
  **wszystkimi** polami wymaganymi i typowanymi (bez `None`). Wartości
  brakujące w `config/bookmakers.yaml` rozstrzyga **ładowacz konfiguracji
  live** według promocje.md, zanim reżim powstanie; backtest buduje
  `RegimeConfig` jawnie (wariant kontrfaktyczny z promocje.md). Świeżość
  weryfikacji regulaminu (T1) sprawdza ładowacz live — reżim jej nie zna.
- Daty z YAML: data → północ Europe/Warsaw → UTC.
- Udział AKO: `stake_share` i `coupon_share`, warunek = oba ≥ 0.50 (T4);
  obrót spoza dziennika wchodzi do mianownika jako nie-AKO (T2).
- Okno (T7), AKO (T6), wielokrotny niekwalifikujący się → 0.88 (T10),
  kolejność kandydatów (T3), wyłączenia z regulaminu (T12), podatek od
  wygranej (T13 — osobno jako A-02).
- Testy (dziś czerwone): (a) duże AKO + wiele małych singli: po stawkach
  96%, po kuponach 9% → 0.94, dziś 1.00; (b) dwie nogi z jednego meczu →
  dziś AKO; (c) zakład sprzed 362 dni → dziś poza oknem 360 dni, w
  kalendarzowym w środku; (d) wielokrotny z nogą 1.15 → dziś podatek
  singla, ma być 0.88; (e) brak `external_turnover_pln` → dziś 1.00
  poniżej 1000 zł.
- Popraw `CONTEXT.md` §2 (lektura „50% kuponów” przeczy §3 ust. 5).

**A-02 (POWAŻNE)** — opis w §0, T13 w promocje.md. Testy (dziś czerwone):
wypłata 2500 zł z jednego kuponu → rozliczenie 2250 zł; EV kandydata, którego
wypłata przy wyliczonej stawce przekracza 2280 zł, liczone z `w = 0.90`.

**F-02 + F-03 + F-31 (POWAŻNE) — kupon w dzienniku.**
- `BetRecord` dostaje: `coupon_type` (`single`/`multi`), `n_legs`,
  `leg_index`, `ingested_at`, `source` (`manual` albo
  `backtest:<run_id>`) — reguła 14. `stake` = stawka **kuponu**,
  powtórzona na każdej nodze.
- **Jedna funkcja** `coupons(journal_rows, *, now) -> list[Coupon]` w
  `live/bets.py`: grupuje po `coupon_id`, status nóg i kuponu wyprowadza z
  wierszy rozliczeniowych z `settled_at ≤ now` (wiersz zakładu ma zawsze
  stan otwarty — dziennik jest append-only). **Każdy** konsument —
  reżim, ekspozycja, G-K, CLV, `reconcile_bets.py` — pracuje na kuponach.
  Test: dziennik z dubletem — każdy konsument liczy stawkę raz.
- `qualifies_as_ako` jedną funkcją z `ev.py`: przy zapisie — na nogach
  postawionych (do wglądu w CSV); przy ocenie reżimu — na stanie kuponu w
  chwili `now` (nogi zwrócone poza liczeniem, T6). Wartość zapisana i
  wartość „na postawieniu” muszą się zgadzać — rozjazd = wyjątek; stan po
  zwrotach to osobne pole kuponu, nie rozjazd.
- `BetJournal(journal_path=…)` — pole przemianowane, żeby objęła je lista
  reguły 30; wymagane, bez domyślnej.
  `add_coupon(legs)` atomowo, spójność nóg (`placed_at`, `mode`,
  `bookmaker`, `stake`, `n_legs == len(legs)`). `settle(…, *, now)` —
  czas rozliczenia podany, nie `datetime.now`. Wynik nogi: `won`, `lost`,
  `void`; `half_*` tylko dla singli na liniach ćwiartkowych (dziś żadnych).
- Live: reżim i G-K czytające `data/bets/bets.csv` odrzucają wiersze z
  `source != "manual"` — wyjątek, nie filtr po cichu. Backtest: zakłady
  `mode="real"`, `source="backtest:<run_id>"`, osobny plik per przebieg
  (`BACKTEST_FIN_PLAN.md` §2).
- Usuń `BetJournal.real_turnover` — jedna implementacja obrotu w `ev.py`.
  Test grep: brak definicji `real_turnover` poza `ev.py`.
- CLV kuponu wielokrotnego: `Π(k_i · p_close_i) · tax − 1`; brak zamknięcia
  dla którejkolwiek nogi → n/d. Jeden kupon = jedna obserwacja.
- Istniejący `data/bets/bets.csv`: zero wierszy `real` → przenieś plik do
  `data/bets/archive/bets_pre_F02_<UTC>.csv` (nic nie znika) i zacznij nowy
  z nowym nagłówkiem; są wiersze `real` → **STOP** i pytanie do Pawła.
- Test (dziś czerwony): AKO z 2 nóg po 100 zł + singiel 50 zł → dziś
  `ako_share = 0` i obrót 250; ma być udział po stawkach 100/150 i obrót
  150.

### Etap D — sieć i kolektor

**F-26 (POWAŻNE) — jeden klient sieciowy `valuebet/net/http.py`.**
- Odstęp per host ≥ max(10 s, `Crawl-delay`); stan między procesami w
  `data/state/throttle/<host>.json` pod blokadą z F-12; zegar i usypianie
  wstrzykiwane.
- robots.txt per host, cache 24 h w `data/state/robots/`; ścieżka
  zabroniona → wyjątek. Hosty API — **stała w kodzie** `API_HOSTS =
  {"api.the-odds-api.com", "api.telegram.org"}`, odzwierciedlona w
  `docs/sources.md`: robots ich nie dotyczy, odstęp tak.
- `User-Agent` z nazwą projektu, bez danych osobowych. Redakcja `apiKey`
  i ścieżki `/bot…/` w logach, wyjątkach i `repr`.
- Migracja wszystkich wywołań: `odds_api`, `odds_collector`,
  `football_data`, `football_data_main`, `validate_instrument`,
  `live/digest`.
- Testy (dziś czerwone): dwa zapytania do jednego hosta na fałszywym
  zegarze → odstęp ≥ 10 s; pętla pobierania w `validate_instrument` →
  odstępy ≥ 10 s; test AST: import `httpx`, `requests`, `urllib.request`,
  `urllib3`, `http.client`, `aiohttp` poza `net/http.py`; `read_csv`,
  `read_json`, `read_parquet`, `read_html` z literałem `http…`;
  `subprocess` z `curl`/`wget` — wszystko poza testami = błąd.

**F-15 + F-16 (POWAŻNE + DROBNE) — budżet The Odds API.**
- Prawda = nagłówki dostawcy (`x-requests-used`, `x-requests-remaining`,
  `x-requests-last`) zapisywane po każdym wywołaniu do
  `data/state/odds_api/usage.jsonl`. `credits_spent` z `x-requests-last`
  (F-16).
- `usage_guard` wymagany w `fetch_odds`. Przed **każdym** płatnym
  wywołaniem, także odświeżeniem terminarza: `used + koszt > 450` →
  pominięcie z wpisem `budget_skip`; `450 − used < 60` → wyłącznie
  zamknięcia. Licznik odświeżany na początku przebiegu bezpłatnym
  zapytaniem (`/sports`, a jeśli dokumentacja potwierdza — `/events` do
  terminarza), żeby stary stan z poprzedniego miesiąca nie blokował
  wszystkiego.
- Testy na fałszywym transporcie (dziś czerwone): `used = 449`, koszt 2 →
  dziś wywołanie idzie; `used = 395` → migawka decyzyjna dziś idzie, ma
  być pominięta.

**F-13 (POWAŻNE) — zamknięcia.**
- Okno kolektora i tolerancja CLV to **dwie różne stałe w jednym module**
  (reguła 28): `CLOSING_TOLERANCE = 30 min` (CLV przyjmuje migawkę z
  `[KO − 30, KO]`) i `CLOSING_TARGET = 7 min`.
- Zamknięcie główne: pierwszy przebieg w `[KO − 7 min, KO)`. Zapasowe:
  pierwszy przebieg w `[KO − 30, KO − 7)`, tylko poza trybem oszczędnym
  F-15. CLV bierze najpóźniejszą migawkę ≤ KO w tolerancji. Klucz
  kotwicy: zdarzenie, nie przedział — migracja kluczy `done` bez
  ponownego pobierania.
- Koszt przelicz w `scripts/odds_budget.py`. > 450/mies. → zapasowe tylko
  dla Premier League i Bundesligi; nadal > 450 → **STOP** i raport.
- Diagnoza luk bez zmian ustawień systemu: `Get-ScheduledTaskInfo`
  (`LastRunTime`, `LastTaskResult`, `NumberOfMissedRuns`), XML zadania
  (`schtasks /query /tn valuebet-odds /xml`), zdarzenia uśpienia i
  wybudzenia z dziennika System (Kernel-Power, Power-Troubleshooter).
  Dziennika `TaskScheduler/Operational` nie włączasz. Przyczyna →
  `docs/task_scheduler.md`.
- Zadanie `valuebet-odds` (wolno zmieniać **tylko jego** ustawienia):
  interwał 5 min (kredyty idą tylko przy należnej kotwicy), uruchom przy
  pierwszej okazji po pominięciu, budź komputer, bez warunku zasilania z
  sieci, nowa instancja ignorowana, limit czasu 10 min. Plan zasilania i
  usypianie Windows → lista dla Pawła.
- Zamknięcie przegapione → `data/state/odds_api/closing_missed.jsonl`;
  tygodniowe pokrycie zamknięć (`ROADMAP.md` §8).
- Test (dziś czerwony): przebiegi o zmierzonym wzorcu odstępów — co
  najmniej jeden przypadek, w którym okno 25 min gubi zamknięcie, a nowe
  okna przy kroku 5 min je łapią; drugi test: migawka główna ląduje w
  `[KO − 7, KO)`. Strata kotwic przed i po → log.
- **Kryterium zamknięcia F-13:** kod + testy + XML zadania z ustawieniami
  powyżej + diagnoza w `docs/task_scheduler.md`. Pokrycie ≥ 95% mierzy się
  w Filarze 2, nie przy audycie — ryzyko szczątkowe (komputer wyłączony w
  porze meczu) opisane w logu; bramki G-S i G-K i tak wymagają pokrycia.

**F-25b — regulamin słowo w słowo** (po F-26).
- robots.txt hosta `dam.begmedia.com`; dozwolone → PDF raz przez
  `net/http.py` do raw z manifestem. Zabronione albo niedostępne → nie
  pobierasz; prośba do Pawła o ręczne pobranie do
  `data/raw/tc/betclic/` i wpis „niezweryfikowane” — Filar 1 i tak może
  ruszyć (strategia A nie zależy od reżimu), strategia C w raporcie
  oznaczona „na niezweryfikowanym regulaminie”.
- Odczyt narzędziem Read; cytaty wstępne w `docs/promocje.md` → dosłowne z
  numerem paragrafu; wypisz T12.
- **Weryfikacja nie może zrobić kodu łagodniejszym.** Regulamin surowszy
  niż kod (wyższy kurs nogi, więcej nóg, minimalna stawka, wyłączone
  rynki) → zaostrzasz kod: test czerwony → zielony, wpis w logu.
  Łagodniejszy → kod zostaje, różnica opisana dla Pawła.

**Kolektor włączony** po F-13 i F-25b: `schtasks /change /tn valuebet-odds
/enable` z nowymi ustawieniami; w ciągu 15 min nowy wiersz heartbeatu w
`data/state/odds_api/` z `errors = []` — inaczej **STOP**. Wiersz
`KOLEKTOR` w logu.

### Etap E — proweniencja, porządek, dokumenty

**F-24 (POWAŻNE) — etykieta lockboxa.** Lockboxa **nie uruchamiasz
ponownie**. JSON zostaje bez zmian — jest dowodem. Obok
`reports/lockbox_3433f2c.PROVENANCE.md`: fakty z raportu (gita), teza
jakościowa wiarygodna, liczby nieodtwarzalne z deklarowanego commita,
żadna decyzja nie zależy od cyfr (tor M zamknięty). Przyczyna:
`valuebet/provenance.py: frozen_commit()` — wyjątek, gdy `git status
--porcelain` pokazuje zmiany w `src/`, `scripts/`, `config/`,
`pyproject.toml`, `uv.lock`, `docs/promocje.md` albo w samym skrypcie;
woła go **każdy** skrypt zapisujący `reports/*_<commit>.*` (dziś i w
Filarze 1) i dopisuje pole `generated_by`. Test proweniencji: dla każdego
`reports/**/*_<hash>.json` w gicie drzewo `<hash>` zawiera skrypt z
`generated_by`; pliki starsze — jawna lista w teście z odnośnikiem do
pliku PROVENANCE (dziś czerwony).

**F-28 (POWAŻNE) + meta-test reguły 29.**
- `ingest/snapshots.py` usuń wraz z testami (brak planu, klucza i budżetu;
  historia zostaje w gicie). `features/base.py` zostaje jako uśpiony —
  wiersz w `ROADMAP.md` §2 już jest.
- `tests/test_rule29_wiring.py`: **osiągalność** z punktów wejścia
  (`scripts/*.py`, moduły z blokiem `__main__`) po grafie importów, bez
  testów. Moduł nieosiągalny musi być na liście `DORMANT` albo
  `PENDING_WIRING` (z Filarem), zgodnej z `ROADMAP.md` §2. Dziś czerwony.
  W Filarze 1 moduły toru S przechodzą z `PENDING_WIRING` do osiągalnych —
  aktualizujesz listę i wiersz §2.

**F-32 (POWAŻNE) — `CONTEXT.md` §5.** Wpis o audycie toru S
(`AUDIT_REPORT_2.md`, `eac437c`) i o FSA #0: (a) opcjonalny bezpiecznik =
brak bezpiecznika → reguła 30; (b) zielony test ścieżki bezpiecznej nie
jest dowodem → reguła 31; (c) komunikat commita nie zastępuje weryfikacji
(F-19, F-21); (d) druga implementacja tej samej logiki (F-03) → reguła 28;
(e) regulamin Betclica — udział po stawkach (§3 ust. 5); (f) A-01, A-02.
Test: **jawna lista** `AUDITS_IN_CONTEXT = ["AUDIT_REPORT.md",
"AUDIT_REPORT_2.md", "reports/audit/FSA_2026-10-01_F0.md"]`, niepusta, każdy
ma odnośnik w `CONTEXT.md` §5. Raport FSA #0b dopisujesz do listy razem z
jego wpisem w CONTEXT w etapie H.

**A-03 (DROBNE)** — opis w §0.

**DROBNE.**
- F-07: usuń punkt wejścia `vb` z `pyproject.toml`.
- F-11: `uv remove structlog pydantic-settings`, jeśli grep potwierdza brak
  użyć; `.env.example`: puste `VB_TELEGRAM_*` w nazwach, których używa
  `digest.py`. Żadnych wartości.
- F-18: porządek rynków w `digest.py` z jednej stałej z nazwami
  kanonicznymi, z `h2h`.
- F-22: `MIN_CLUSTERS_RELIABLE = 8` dla każdego werdyktu (`beats_closing`,
  `unlocks_gk`, `describe`); 5 wyłącznie do policzenia i wydrukowania CI z
  adnotacją „poniżej progu wiarygodności”.
- F-23 + W.10: `validate_instrument.py` czyta pliki z raw (pobiera tylko
  brakujące), przebieg z `frozen_commit()`, nowy raport
  `reports/instrument_validation_<commit>.json` z polem `reliable`
  (klastry ≥ 8) i werdyktem **generowanym z liczb**: „ważny” tylko przy
  `reliable` i CI nachylenia obejmującym 1; CI wykluczające 1 → „obciążony
  (skala)”; nie `reliable` → „niewiarygodny statystycznie”. Stary plik
  zostaje z notą. Premier League do 2024/25 — lockboxa nie dotyczy.
- F-27: docstring `digest.py` zgodny z kodem (token w ścieżce URL).
- F-29: zrobione w `ROADMAP.md` przez Architekta — sprawdź.
- F-30: sekcja „Układ” w `CLAUDE.md` — **jedyna**, którą zmieniasz w tym
  pliku. Test: każdy moduł z `src/valuebet/` wymieniony w „Układzie”.

## 4. Weryfikacja całości (etap F)

- `uv run pytest -q`; `uv run pytest -k future_poison`; `uv run ruff check
  src tests scripts`; `uv run mypy src` (strict) — czysto.
- `KNOWN_VIOLATIONS` w `test_rule30_guards.py` — pusta.
- Pokrycie: `lockbox.py` 100% linii i gałęzi; `pricing/` ≥ 90% linii;
  `net/http.py`, `raw_store.py`, `provenance.py` ≥ 95%.
- `scripts/verify_raw.py` → 0.
- Rewers każdej pozycji POWAŻNEJ i A-01, A-02 (§1) — kolumna `rewers`.
- `git status` czysty. Skan historii pod sekrety — tylko liczby trafień.

## 5. FSA #0b (etap G)

Zlecenie dla `full-system-auditor` — **dosłownie**, bez skrótów i bez
komentarzy od siebie:

> FSA #0b — audyt powtórkowy wyjścia z Filaru 0. Raport:
> `reports/audit/FSA_2026-10-02_F0b.md`, zapis przyrostowy. Wykonaj
> wszystkie sekcje 1–7 z `docs/FULL_SYSTEM_AUDIT.md` w zakresie dla F0,
> zaczynając od „Audyt powtórkowy — weryfikacja napraw”. Wejście:
> `reports/audit/FSA_2026-10-01_F0.md` (poprzedni raport),
> `docs/FSA0_NAPRAWY.md` (specyfikacja napraw i kryteria zamknięcia —
> możesz je zakwestionować), `reports/audit/FIX_LOG_F0.md` (twierdzenia
> wykonawcy do sprawdzenia, nie dowód). Status każdej pozycji F-01…F-32,
> W.6, W.8, W.10, A-01…A-03; rewers co najmniej dla F-01, F-02, F-04,
> F-19, F-20, F-25, A-01. Potem nowe znaleziska, numerowane `F0b-01`,
> `F0b-02`, … Zamierzone i nie będące znaleziskiem: przerwa w heartbeat
> kolektora w czasie napraw (wiersze `KOLEKTOR` w logu); pokrycie
> zamknięć ≥ 95% mierzone dopiero w Filarze 2 (kryterium F-13 w §3).
> Ostatnia linia raportu dokładnie: `BRAMKA: KRYT=<n> POWAŻNE=<m>
> OTWARTE=[<id>, …]`.

- Raportu audytora **nie edytujesz**. Liczba otwartych = to, co w linii
  `BRAMKA`. Za otwarte uznajesz każdy status inny niż ZAMKNIĘTE albo
  PRZEKLASYFIKOWANE na DROBNE (także „częściowo”, „do sprawdzenia”).
- Otwarte KRYT albo POWAŻNE → naprawy wg §1 (identyfikatory audytora) →
  FSA #0c: ten sam tekst zlecenia, z dopisanym wejściem — wszystkie
  poprzednie raporty rundy 0b…; nowe znaleziska `F0c-xx`. **Najwyżej dwie
  dodatkowe rundy** (0c, 0d); potem STOP i raport dla Pawła.

**Dopisek (2026-10-03, decyzja Pawła po FSA #0d — dosłownie):** „Decyzja Pawła (2026-10-03): zgoda na JEDNĄ dodatkową rundę FSA #0e, ponad limit z docs/FSA0_NAPRAWY.md §5. Zapisz ją dosłownie w FIX_LOG_F0.md i jako dopisek w §5. Rundy #0f nie ma: po #0e każde otwarte KRYT/POWAŻNE → STOP.”
Pełna treść decyzji (zakres rundy 0e): `reports/audit/FIX_LOG_F0.md`, sekcja
„Runda 0e”.

## 6. Bramka F0 → F1 (etap H)

Wszystkie naraz:

1. linia `BRAMKA` ostatniego raportu: `KRYT=0 POWAŻNE=0`;
2. każde zamknięte POWAŻNE: test, czerwony → zielony, rewers czerwony;
3. §4 zielone; `verify_raw` = 0; `git status` czysty;
4. akceptacja Pawła z §0 zacytowana w `FIX_LOG_F0.md` i w raporcie
   końcowym etapu H, z datą.

Spełnione → wpis w `CONTEXT.md` §5 o FSA #0b (i dopisanie raportu do
`AUDITS_IN_CONTEXT`); `ROADMAP.md` §0: F0 „ZAMKNIĘTY <data> (FSA #0b)”, F1
„W TOKU”; commit `docs: bramka F0→F1 otwarta (FSA #0b)`. Niespełnione
którekolwiek → **STOP**, raport, Filar 1 nie startuje.

## 7. Filar 1 (etap I) — `BACKTEST_FIN_PLAN.md` §7, kroki 2–5

- **Krok 2:** ingest 22 lig × 7 sezonów przez `net/http.py` i
  `raw_store.py`; raport kolumn; reguła `observed_at` z `notes.txt`,
  konserwatywnie. robots.txt zabrania ścieżki z plikami → STOP.
- **Krok 3:** `replay.py`, `financial.py`, `reconcile_bets.py` — wyłącznie
  moduły toru S (reguła 28); `frozen_commit()` w każdym runnerze;
  konstrukcja strategii C dokładnie wg `BACKTEST_FIN_PLAN.md` §3.
- **Krok 4:** testy §4 1–7. **Czerwone → STOP bez uruchamiania strategii.**
- **Krok 4a:** `backtest-auditor` na `backtest/` i skrócony FSA (sekcje 3–4,
  `docs/FULL_SYSTEM_AUDIT.md` „Kiedy” pkt 4) → `reports/audit/FSA_<data>_F1a.md`
  z linią `BRAMKA`. Otwarte KRYT/POWAŻNE → naprawa wg §1, powtórka kroku 4
  i 4a. Dopiero zero → krok 5. Po kroku 5 każda zmiana kodu wymaga nowego
  przebiegu i zapisu, że poprzedni wynik był oglądany.
- **Krok 5:** jeden przebieg A–F + wrażliwość θ →
  `reports/backtest_fin/<commit>/RAPORT.md` + JSON + PNG (duże tabele w
  parquet z hashem w manifeście artefaktów). Werdykt z §6 planu oznaczony
  „WSTĘPNY — do potwierdzenia przez FSA #1”. **Alarm** wg §6 planu → STOP
  i szukanie przyczyny, bez wniosków. Zero strojenia.
- **FSA #1:** audytor, wszystkie sekcje, pełna sekcja 4 →
  `reports/audit/FSA_<data>_F1.md`.
- **STOP.** Decyzja o Filarze 2 należy do Pawła. Bez paper tradingu, bez
  Telegrama, bez Filaru 2.
- Kończy się kontekst → domknij bieżący krok, commit, stan w
  `reports/backtest_fin/PROGRESS.md`, STOP. Następna sesja wznawia stamtąd.

## 8. Granice tej pracy

- Żadnych zakładów, logowania do bukmachera, adaptera Betclica (S2 czeka na
  decyzję Pawła).
- Kolektora ręcznie nie uruchamiasz (poza kontrolą heartbeatu po
  włączeniu zadania); testy sieci i budżetu na fałszywym transporcie.
  Jedyne prawdziwe zapytania z kodu projektu: pliki football-data (krok 2 i
  brakujące w F-23), regulamin Betclica, `notes.txt`, robots.txt tych
  hostów, bezpłatne `/sports` The Odds API z kolektora.
- Lockbox: zero przebiegów ewaluacji modelu (`run_lockbox.py`, DC/Elo na
  Ekstraklasie 2025/26–2026/27). Strategia F (kursy zamknięcia
  Ekstraklasy, bez modelu) obejmuje 2025/26 — to nie jest obejrzenie
  lockboxa.
- `CLAUDE.md` — tylko „Układ”. `ROADMAP.md` — wiersze stanu w §0 i §2.
  `BACKTEST_FIN_PLAN.md`, `TOR_S_PLAN.md`, `COLLECTOR_PLAN.md` — bez zmian.
  Sprzeczność specyfikacji z kodem albo z danymi → STOP i pytanie, nie
  wybór po cichu.
- Sekretów nie wypisujesz, nie logujesz, nie commitujesz.
- **Dopisek (2026-10-03, decyzja Pawła, runda 0e):** dozwolone prawdziwe
  zapytanie z kolektora: `GET /v4/sports/{sport}/events` (bezpłatne —
  dokumentacja v4: „does not count against the usage quota”; pierwsze
  prawdziwe wywołanie musi mieć `x-requests-last = 0`, inaczej zadanie
  wyłączone i STOP).
