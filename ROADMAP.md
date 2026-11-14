# ROADMAP — valuebet

**Aktualizacja 2026-10-01, 22:50 — Filary i audyty.** Nic nie idzie na żywo
(ani paper trading, ani Telegram), zanim silnik wyceny nie przejdzie historii
(Filar 1, `BACKTEST_FIN_PLAN.md`). Każde przejście między Filarami wymaga
FULL_SYSTEM_AUDIT (`docs/FULL_SYSTEM_AUDIT.md`) i akceptacji Pawła.

**Aktualizacja 2026-10-01, 14:07 — model hybrydowy.** Decyzja Pawła: projekt
jest portfolio, ale ma zarabiać prawdziwe pieniądze — wyłącznie legalnie:
licencjonowani polscy bukmacherzy, zgodnie z ich regulaminami, bez ryzyka z
KKS. Ocena czterech ścieżek z 13:29 (brokerzy azjatyccy, sygnały VIP,
live/HFT z botem, krypto) obowiązuje — wszystkie odrzucone. Archiwa:
`docs/archive/ROADMAP_decyzja_2026-10-01.md` (13:29) i
`docs/archive/ROADMAP_zaklady_2026-10-01.md` (12:58). Część II bez zmian.

---

# CZĘŚĆ I — MODEL HYBRYDOWY

## 0. Filary i audyty (2026-10-01, 22:50)

| Filar | treść | stan | bramka wyjścia | szacunek |
|---|---|---|---|---|
| **F0** Fundamenty i badania | kroki 1–4, DC jako model 1X2, M2, lockbox, moduły wyceny, kolektor S1 | **ZAMKNIĘTY 2026-10-07 (FSA #0e)** — FSA #0 (2026-10-01): 0 KRYTYCZNYCH, 18 POWAŻNYCH → naprawy wg `docs/FSA0_NAPRAWY.md` → FSA #0b (2026-10-03): 0 KRYT, 3 POWAŻNE (F0b-01…03) → naprawione → FSA #0c (2026-10-03): 0 KRYT, 3 POWAŻNE (F0c-01…03) → naprawione → FSA #0d (2026-10-03): 0 KRYT, 1 POWAŻNE (F0d-01) → naprawione → runda dodatkowa FSA #0e (decyzja Pawła 2026-10-03; `reports/audit/FSA_2026-10-04_F0e.md`): `BRAMKA: KRYT=0 POWAŻNE=0`; akceptacja Pawła udzielona z góry, warunkowo (2026-10-02 11:33), warunek spełniony. Otwarte DROBNE: F0e-02, F0e-05 (**warunek przed Filarem 2**; akceptacja F0e-05 związana z warunkami decyzji 2026-10-04 i 2026-10-07 — `FIX_LOG_F0.md`), F0e-03, F0e-04, F0e-06, F0b-04, F0b-05, F0b-07, F0b-10…F0b-13 | FSA #0e: zero KRYT i POWAŻNYCH — spełnione | 1–2 sesje |
| **F1** Historyczny backtest finansowy | `BACKTEST_FIN_PLAN.md`: testy poprawności silnika, potem strategie A–F na 22 ligach × 7 sezonów | **ZAMKNIĘTY 2026-11-13** (FSA #1, `reports/audit/FSA_2026-11-13_F1.md`: KRYT=0 POWAŻNE=0; akceptacja Pawła 2026-11-13) | werdykt z §6 planu + FSA #1 | 4–6 sesji, ~1–2 tygodnie |
| **F2** Polskie dane na żywo + paper | zgodny odczyt kursów polskiego bukmachera, polski backtest na zebranych danych, przegląd dnia, paper ≥ 4 kolejki | po F1 = POTWIERDZONA (A; dla Betclica także C — rekomendacja z `BACKTEST_FIN_PLAN.md`, zmiany 2026-10-11). Warunek „F1-P01 naprawione + bramka §4 na nowym hashu” **przeniesiony do Filaru 1** (wariant B, decyzja Pawła 2026-10-11) | G-S per liga + FSA #2 | 2–3 tygodnie budowy + 4–6 tygodni danych |
| **F3** Prawdziwe pieniądze | c = ¼, limity, wyłącznik, dziennik | po F2 | G-K po 150 zakładach + FSA #3 | ~5 miesięcy przy ~30 zakładach/mies. |
| **F4** Skalowanie | kolejne ligi i bukmacherzy, każda liga z własną G-S | po F3 | per liga | ciągłe |

> [Fragment usunięty z wersji publicznej: dotyczył prywatnego konta autora i korespondencji z obsługą bukmachera.]
- **Bierne zbieranie danych nie jest grą** i trwa we wszystkich Filarach:
  S1 zbiera migawki Pinnacle od 2026-10-01. Polskiej historii kursów nie ma
  w żadnym darmowym źródle — będzie tylko taka, jaką sami zbierzemy.
- Kalendarz F2–F3 wydłużają przerwy zimowe (Ekstraklasa dłuższa,
  Bundesliga krótsza); Premier League gra bez przerwy.
- Tor M (raport portfolio M5) — w dowolnym momencie, poza ścieżką krytyczną.

## 1. Dwa tory

- **Tor S — pieniądze.** Uczciwe prawdopodobieństwo z Pinnacle (The Odds API,
  po Shinie) kontra kurs polskiego bukmachera grającego bez podatku. Prawdziwe
  stawki dopiero po bramce G-S, osobno dla każdej ligi.
- **Tor M — model i portfolio.** Rozstrzygnięty 2026-10-01: DC zamknięte jako
  model 1X2, a test pokrywania (M2) pokazał, że model **nie wnosi informacji
  ponad Pinnacle** (`+0.0015 [−0.0003, +0.0040]`). Tor M to portfolio. Jego
  wkład w pieniądze: forma DC z `ρ ≈ −0.07`, zwalidowana na Premier League,
  przy wycenie kombinacji z danych rynkowych (§4.3).

Tempo wyznacza tor S: bez danych o kursach nie ma ani EV, ani zielonego
światła, a dzień bez migawek jest nie do odtworzenia.

## 2. Gdzie jesteśmy (2026-10-02)

| obszar | stan |
|---|---|
| Kroki 1–3 | zamknięte — Shin, schema, Elo, walk-forward, audyt bez przecieków |
| Tor M — DC | **zamknięte jako model 1X2** (`STEP4_ENSEMBLE.md` §11.10–11.11); M2: brak wkładu ponad Pinnacle; lockbox 2025/26–2026/27: DC ≈ Elo, różnice do rynku nieistotne, brak śladu przeuczenia; został raport |
| The Odds API (S1) | zadanie `valuebet-odds` od 2026-10-01 wieczorem; 3 z 500 kredytów zużyte; plan — wiersz „Odds API, kredyty” niżej (377/mies., 2026-10-16). FSA #0: luki harmonogramu 30–60 min (F-13), stan kolektora w `data/raw/` (F-14), budżet 450 niewymuszany w kodzie (F-15) — naprawy przed F1 |
| Moduły toru S | fair, ev, kelly, bets, clv, digest — po audycie (`AUDIT_REPORT_2.md`: 2 KRYTYCZNE i 9 POWAŻNYCH naprawione) i po naprawach FSA #0 (`reports/audit/FIX_LOG_F0.md`). **Podłączone 2026-10-08** (reguła 29, `tests/test_rule29_wiring.py`) przez `backtest/financial.py` i `backtest/replay.py` do skryptu bramki §4 `scripts/engine_tests.py`: `pricing/fair.py`, `pricing/ev.py`, `pricing/kelly.py`, `live/bets.py`, `backtest/clv.py`, `config.py`; tabela strategii `backtest/strategies.py` i strategia C `backtest/strategy_c.py` — **podłączone 2026-10-11** (wariant B) przez runner `scripts/run_backtest_fin.py` (krok 5, uruchamia Paweł po zielonej bramce) i bramkę §4 (C w testach 1–7); `live/digest.py` — czeka na podłączenie w Filarze 2 |
| Kursy Betclica | `docs/discovery/` — jeden plik z adresem, zgodna ścieżka odczytu nieznana; regulamin „Bez Podatku 2.0” — `docs/promocje.md` (cytaty §3, w kodzie wariant pesymistyczny) |
| Moduły uśpione (reguła 29) | `features/base.py` — mechanizmy point-in-time toru M (`CLAUDE.md` „Mechanizmy cech”), bez wywołań do odwołania; `ingest/snapshots.py` — usunięty 2026-10-02 (FSA #0 F-28), klasa B niedostępna |
| Bramka §4 silnika (F1) | **2026-10-15 (wariant B): 24/25 na `27ae469` + 4b-C na `737a111` (częściowy, tryb `--only 4b-C`) — ZIELONE** (`reports/backtest_fin/27ae469/ENGINE_TESTS.md`, `reports/backtest_fin/737a111/ENGINE_TESTS_4bC.md`). Decyzja Architekta 2026-10-15: zamiast pełnej bramki rerun samego 4b-C, bo src/ i config/ są bit-w-bit identyczne z `27ae469` (`git diff 27ae469 -- src config` pusty — runner w trybie `--only` odmawia startu przy niepustym), a zmiany w `scripts/engine_tests.py` ograniczone do audytu 4b-C i trybu częściowego. Zmienione definicje współdzielone: `SeedRun` (+pole `path_stats`, domyślnie `()`), `run_seed` (+przekazanie statystyk `path_audit`); poza tym `path_audit`, `check_4b_c`, `main`. Dowód obojętności: stary (`27ae469`) i nowy runner na tym samym src/, early i c120-early × A, C × nasiona 1, 2 — 8/8 identycznych bit w bit (25 pól `SeedRun` poza `path_stats`); przebieg dodatkowy c120-early, C, nasiono 1, wyniki spermutowane — jedyna różnica `path_errors`: stary `c1-001166: stawka 21.8 vs wzór z księgi 21.81`, nowy pusty (1 remis zaakceptowany, max |Δ kapitału| 3,5e-11) — zamierzona zmiana oceny remisu. Dowód AST: `path_stats` czytane wyłącznie w `check_4b_c` (`scripts/engine_tests.py:1414`). Wynik 4b-C: 89 958 kuponów, 28 remisów, 1 zaakceptowany dzięki remisowi, 0 odrzuconych, max |Δ kapitału| 6,5e-11 (`FIX_LOG_F1.md`). **Przegląd Architekta 2026-10-16: diff scripts/ i tests/ (`27ae469..447d64d`) przejrzany, raport `ENGINE_TESTS_4bC`, lista remisów, dowód obojętności i dowód AST — przyjęte**; bramka §4 PRZYJĘTA jako 24/25 na `27ae469` + 4b-C na `737a111`: 89 958 kuponów, 28 remisów, 1 zaakceptowany regułą remisu, 0 odrzuconych, max |Δ kapitału| 6,5e-11. **Zalecany PEŁNY rerun bramki na finalnym HEAD** przy najbliższej zmianie src/ (poprawka zaokrąglenia niżej) i przed FSA #1 — jeśli Paweł się zgodzi. Historia: 2026-10-12 bramka `2624fff` czerwona w 4b-C (#1, lista kuponów; zmiana kryterium 4b); `27ae469` czerwona w 4b-C (#2, remis zaokrąglenia, diagnoza klasa A). Wcześniej: **ZIELONA 12/12 na `2c7cc61`** (2026-10-09 10:15–12:29, 2 h 14 min, 1 robotnik; `reports/backtest_fin/2c7cc61/`). Poprzednio czerwona na `e66260a` (8.10 23:42): test 5 — szum float 1,06e-9 (naprawa: księga w groszach, `d06cda3`), test 6 — limity Kelly'ego stosowane do wymuszonego placebo 2b (naprawa: znacznik `FORCED_PLACEBO_NO_LIMITS`, własne literały limitów + test równości z `kelly.py`, `d06cda3`, `2c7cc61`). Obserwacja 3a: yield +0,0258 vs +0,0340 przy SE 0,0052 (−1,6 SE, w granicy 2 SE, bez alarmu) — do sprawdzenia w audycie 4a |
| Wyłącznik 25% (F1) | tryb PAPER **nigdy nie wraca** do real (gotówka zamrożona); w świecie e = +2,5% P(obsunięcie ≥ 25%) ≈ 0,18–0,19 (analiza CLI i symulacja Pawła, 2026-10-09). Raport A–F: data wyłącznika, wyniki real i paper osobno, **wariant bez wyłącznika** do oceny przewagi |
| DROBNE po wariancie B (audyt 2026-10-11, `FIX_LOG_F1.md`) | AB-7: komunikat PAPER w `pricing/kelly.py` na DEBUG — ostrzeżenie live dodać przy podłączaniu `live/digest.py` (Filar 2). AB-9: w C stawka < 0,50 zł odpada jako „kupon poza progiem po podatku” (0.88), nie w liczniku `SKIP_BELOW_MIN_STAKE`; przy czerwieni 4b najpierw sprawdzić stawki przy 0,50 zł — **ZAMKNIĘTE** (`8d63a12`, 2026-10-12; potwierdzone bramką `27ae469` i rerunem 4b-C na `737a111`) |
| DROBNE: zaokrąglenie stawki przy wiążącym limicie ekspozycji (2026-10-15) | `pricing/kelly.py:279,302` — `round(x, 2)`; przy remisie na pół grosza zaokrąglenie w górę daje ekspozycję 15,00003% — pół grosza ponad limit 15% (bramka `27ae469`, kupon c0-004274; drugi przypadek: c1-001166 w dowodzie obojętności). Bez wpływu na wnioski Filaru 1; **dotyczy także ścieżki live**. Naprawa (zaokrąglanie w dół przy wiążącym limicie albo arytmetyka groszowa) razem z innymi zmianami src/ **przed Filarem 3** + pełna bramka §4 |
| DROBNE: dryf floatów silnik vs księga (2026-10-15) | kapitał silnika (`cash + open_real`) i odtworzony z księgi różnią się o ~1e-11 (max 6,5e-11 w rerunie 4b-C) — kolejność sumowania floatów. Monitorowany twardym warunkiem |Δ kapitału| < 1e-6 w audycie 4b-C (`BACKTEST_FIN_PLAN.md` §4, dopisek 2026-10-15) |
| DROBNE: etykieta przyczyny odrzucenia (2026-10-16) | `backtest/financial.py` — etykieta przyczyny odrzucenia grupy bierze stawkę z PIERWSZEGO wywołania `stake_at`, więc nazwa przyczyny zależy od kolejności wywołań w planiście. Decyzje bez wpływu (odcisk PRZED = PO, `FIX_LOG_F1.md` AB-9) |
| DROBNE: mypy w skrypcie bramki (2026-10-16) | `mypy --strict scripts/engine_tests.py` — 29 błędów, zastane z `27ae469` (nie wprowadzone naprawą 4b-C #2). Do uporządkowania przed FSA #1 albo świadomie zostawione |
| DROBNE: okno remisu w audycie 4b-C (2026-10-16) | `REF_TIE_PLN = 1e-6` zł (`scripts/engine_tests.py`) — szersze, niż wymaga szum (~6,5e-11). Zawęzić (np. 1e-9) przy najbliższej pełnej bramce; wyniki bramki bez zmian |
| Oficjalny backtest kroku 5 (2026-10-16) | WYKONANY 2026-10-18 12:16–15:37 na 4599dca (38/38), kod 2 (alarm). Diagnoza K2/K4/K5 bez defektu. Alarm ZAMKNIĘTY decyzją Pawła 2026-10-18 (FIX_LOG_F1). Wynik mechaniczny §6: A i C spełniają kryteria. Werdykt formalny po FSA #1. |
| Luka danych football-data | OTWARTE (ograniczenie): Pinnacle od XI 2025 (2025/26: 38% meczów), Bwin brak ~37% 2024/25, WH brak 2025/26. Wpływa na każdy backtest obejmujący te sezony. |
| Kierunek projektu | DECYZJA Pawła 2026-10-18: Projekt domykany jako portfolio (CV/LinkedIn). Powód: oczekiwany zwrot w polskim reżimie podatkowym ok. 1–3% kapitału rocznie. Filar 2 i 3 nie są realizowane. Faza 0/1 (pomysł z 2026-10-18) — porzucone. |
| Kolektor VPS | ZAKOŃCZONY: Działał 24/7 od 2026-10-10 do wygaśnięcia okresu testowego Mikrusa ok. 2026-11-07; nieodnowiony (decyzja Pawła 2026-11-11). Kopie surowych danych: D:\vb-backup (12.10 i 16.10). |
| Następny krok | Publiczna wersja repo (portfolio) → README EN → studium przypadku → post LinkedIn |
| FSA #1 i werdykt Filaru 1 (2026-11-13) | FSA #1 zakończony 2026-11-13, BRAMKA KRYT=0 POWAŻNE=0, akceptacja Pawła 2026-11-13. WERDYKT FILARU 1: A — POTWIERDZONA w sensie §6 (CLV +1,97% [+1,52; +2,42]; odporne na metodę: potęgowa +1,52% [+1,05; +1,98]); zastrzeżenie audytu: wynik mechaniczny, nie dowód przewagi dziś (CLV 2025/26 ≈ 0, ceny zastępcze). C — §6 spełnione formalnie, wynik kruchy (CI yieldu [−1,17; +36,0], 10 wygranych = 110% zysku). D traci (kontrola podatku). Filar 1 ZAMKNIĘTY. Filar 2 i 3 nie są realizowane (decyzja 2026-10-18). Otwarte DROBNE: D01–D11 z FSA_2026-11-13_F1.md. |
| DROBNE: etykieta kuponu C (2026-10-16, F1-E02) | opcja (c): etykieta bukmachera kuponu z planisty w src/ (`Planner` + `backtest/financial.py:655`), z bukmacherem źródłowym nogi np. w `notes` — semantycznie właściwe dla live (kupon AKO u jednego bukmachera). Do rozważenia **przed Filarem 3, razem z pełną bramką** (zmiana src/ unieważnia tryb `--only`). Do tego czasu w C dziennik traci informację B365/BW per noga (wszystkie nogi `betclic`; źródło kursów tylko w `C_LABEL`) |
| DROBNE: F na 80 meczach (2026-10-16) | F (Ekstraklasa, zamknięcie vs zamknięcie, `POL.csv`) ma 80 meczów z jednego sezonu (2025/26): komplet kursów zamknięcia PSC i B365C w POL.csv jest tylko w 2025/26. Pominięte per sezon („brak kompletu PSC/B365C”): 2019/20 296, 2020/21 240, 2021/22 306, 2022/23 306, 2023/24 306, 2024/25 306, 2025/26 226 (smoke 2026-10-16). Nazwy kolumn sprawdzone (`backtest/replay.py:257`: `PSCH/PSCD/PSCA`, `B365CH/B365CD/B365CA` — obecne w ramce): `B365C*` puste do 2024/25 włącznie (niepustych 274 w 2025/26, 69 w 2026/27), a `PSC*` w 2025/26 tylko w 112 meczach (0 w 2026/27) — część wspólna 80. F jest informacyjna (§3, §6), nie wchodzi do werdyktu i NIE jest rankingowana do wyboru lig — próbka zbyt mała na jakikolwiek wniosek. Do zbadania po backteście: źródło zamknięć B365 i Pinnacle dla Ekstraklasy sprzed 2025/26 |
| OTWARTE (bezpieczeństwo, do klasyfikacji w FSA #1): klucz API w plikach surowych (2026-10-16) | kolektor zapisuje URL zapytania razem z kluczem API w plikach surowych (16/16 plików na VPS, kontrola 2026-10-12). Naprawa: redakcja klucza przed zapisem + test regresji; dopiero POTEM rotacja klucza; **przed fazą 5 (synchronizacja)**. **2026-11-13:** Redakcja klucza w kolektorze: istnieje od `6f4a07f` (`ingest/odds_api.py` `redact_api_key`/`redact_text`, `net/http.py` `redact`, strażnik `OddsResponse`); testy end-to-end: commit `4b3e55a` (gałąź fix/odds-api-key-redact), kod src/ bez zmian. Alarm „16/16” fałszywy: wszystkie pliki raw (laptop, D:\vb-backup 12.10 i 16.10) mają wyłącznie `apiKey=REDACTED`, 0 niezredagowanych; wartość klucza z lokalnego `.env` nie występuje w żadnym pliku repo ani D:\vb-backup. Rotacja klucza: do decyzji Pawła (higiena, nie konieczność). Stare raw nie przepisywane (niezmienność + sha256); VPS wygasł — jego `.env` niesprawdzalny |
| Odds API, kredyty (2026-10-16; zastępuje dawny plan 413/mies. i liczby z §5) | plan kalkulatora = **377 kredytów/mies.** — `odds_budget.py` na state.json z 2026-10-11, terminarz z /events: 63 mecze (Bundesliga 18, Premier League 30, Ekstraklasa 15); kod bez zmian, wyjście: `docs/discovery/out_B/odds_budget_2026-10-11.out` (poza gitem). Per liga: Ekstraklasa ~119 (zamknięcia 77,4 + decyzje 41,3), Premier League ~138 (zamknięcia 51,6 + zapasowe 51,6 + decyzje 34,4), Bundesliga ~120 (43,0 + 43,0 + 34,4); kotwice meczowe 267 (w tym zamknięcia główne 172), migawki decyzyjne 110; werdykt: „MIESCI SIE ponizej progu trybu oszczednego 390”. 2 kredyty na wywołanie (h2h + totals), budżet 450, limit 500, tryb oszczędny od 390 wydanych. Dawne 456 (Ekstraklasa ~198) to plan z 2026-10-04 **z kotwicą T-24h Ekstraklasy** (`reports/audit/FIX_LOG_F0.md:1601-1605`), usuniętą w F0e-01 (`67b31d5`; plan 374 — `FIX_LOG_F0.md:1697`) — nieaktualne. Pomiar z kopii VPS (`data/vps_check/usage.jsonl`): licznik 13 → 19 kredytów między 2026-10-10 18:25 UTC a 2026-10-11 07:52 UTC; 6 kredytów = 3 migawki decyzyjne po 2. Pomiar 45/500 do 12.10 przypada na przerwę reprezentacyjną i **NIE jest reprezentatywny** (377 to plan, nie pomiar). Plan wg odds_budget.py (state.json z 2026-10-11): 377 kredytów/mies. (Ekstraklasa ~119, Premier League ~138, Bundesliga ~120) wobec budżetu 450 i progu trybu oszczędnego 390: zapas do 390 ≈ 13, do 450 ≈ 73. Czwarta liga w darmowym planie się nie mieści (najtańsza konfiguracja ligi — zamknięcie główne + migawka decyzyjna — to ~77/mies. w Bundeslidze, 377 + 77 > 450); zmiana składu lig = ZAMIANA, nie dodanie, albo płatny plan po Filarze 3 (decyzja wg ROI). 456 z 2026-10-04 było nieaktualne (kotwica T-24h Ekstraklasy usunięta w F0e-01). **Reguła wyboru lig do Filaru 2 musi zapaść PRZED oficjalnym backtestem** (przedrejestracja: reguła, nie konkretne ligi; kryterium niezależne od wyniku) → ZAMKNIĘTE 2026-10-16, wiersz niżej |
| **ZAMKNIĘTE 2026-10-16:** liczba i wybór lig do Filaru 2 przed oficjalnym backtestem | liczba lig = **3** (plan 377/450 kredytów/mies. — `odds_budget.py` na state.json z 2026-10-11, `docs/discovery/out_B/odds_budget_2026-10-11.out`: „RAZEM: 377”, „MIESCI SIE ponizej progu trybu oszczednego 390”). Reguła = `BACKTEST_FIN_PLAN.md`, „Wybór lig do zbierania na żywo w Filarze 2”, pkt (a)–(e), zamrożona w `78bb13c` (2026-10-11 14:23 +0200, jedyny commit wprowadzający i zmieniający ten zapis — `git log -S`). Decyzja A (Paweł i Architekt, 2026-10-16, przed wynikami): (a)–(d) dosłownie; Ekstraklasa poza rankingiem 22 lig (POL.csv tylko zamknięcia → F, informacyjnie), bez zarezerwowanego miejsca, ewentualny powrót przez Filar 4. Obecny kolektor (Ekstraklasa, Premier League, Bundesliga) bez zmian do decyzji o Filarze 2; zmiana składu = zmiana kolektora + audyt + sprawdzenie budżetu 450 w `odds_budget.py` |
| OTWARTE (do wyjaśnienia w FSA #1): brakujące zamknięcia w kopii VPS (2026-10-16) | state.json z VPS (kopia 2026-10-11 10:02) zawiera closing_missed = 16 meczów (gwizdki 2026-10-09 18:xx i 2026-10-10 11:00–16:30 UTC); plik heartbeat.jsonl w tej kopii zaczyna się dopiero 2026-10-10 18:25 UTC. Przyczyna niewyjaśniona (start kolektora/wdrożenia vs luka w działaniu) — do ustalenia z pełnej kopii VPS i dziennika zadania; wpływa na zasób zamknięć do Filaru 3. |
| F1-P01 (reżim Betclica vs regulamin) | **2026-10-11, wariant B (decyzja Pawła, przed wynikiem): pkt 1–3 naprawiane W FILARZE 1** na gałęzi `fix/F1-P01-C` — `ev.py` wg regulaminu (udział po stawkach; po stawkach i kuponach tylko wrażliwość C), bramka §4 z testami 1–7 dla C, runner A–F, werdykt w trzech częściach (A, C, B) — `BACKTEST_FIN_PLAN.md`. Stan poprzedni, zastąpiony: **ZAMKNIĘTE dla Filaru 1** (decyzja Pawła 2026-10-10): kod reżimu (`pricing/ev.py:181-410`) bez zmian, bramka §4 na `2c7cc61` ważna. Warunek udziału po stawkach **i** po kuponach jest ostrzejszy od §3 ust. 5 → współczynnik podatku nie wyższy niż regulaminowy (kierunek konserwatywny). Pomiar na świecie bramki, C, nasiona 0–4: 22 229 kuponów, 0 z innym współczynnikiem, 0 przypadków kod > regulamin (świat ~97% dubletów — pomiar nie rozróżnia wariantów; `docs/promocje.md`). **Raport A–F (C):** licznik kuponów wg współczynnika podatku (1.00 / 0.94 / 0.88, single i wielokrotne osobno) oraz liczba kuponów, które wg regulaminu (udział tylko po stawkach) dostałyby wyższy współczynnik — z jawnym opisem: współczynniki C są nie wyższe niż regulaminowe (kierunek konserwatywny; zysk C nie jest przez to gwarantowanie dolną granicą, bo niższy podatek zmienia też, które single przechodzą `k_min`). **OTWARTE dla Filaru 2 — warunek startu:** naprawa pkt 1, 2, 3 w `ev.py`, czerwony test najpierw, bramka §4 zielona na nowym hashu — **obejmująca też C (pełna ścieżka testów 1–7)**, FSA przed przejściem |
| Audyt 4a (F1, krok 4a) | 2026-10-10 na `5831a92`: KRYT=0, POWAŻNE=3 (A4a-01 kurs miękki bez kontroli wiarygodności, FSA4a-01 podatek strategii z dwóch źródeł, FSA4a-02 trucizny 4b/4c bez porównania postawionych zakładów) — `reports/backtest_fin/5831a92/AUDIT_4a.md`, `reports/audit/FSA_2026-10-10_F1-4a.md`. Decyzje Pawła 2026-10-10 (przed wynikiem): reguły (a) booksum < 1.00 i (b) EV > 0.50 zamrożone; D = zakłady A rozliczone przy 0.88 (kontrola podatku); C poza bramką i werdyktem („bez dowodu poprawności”) — **werdykt Filaru 1 tylko z A**. Naprawy na gałęzi `audit/4a`; **bramka §4 do powtórzenia na nowym hashu przed krokiem 5**; runner A–F (część 2) — po zielonej bramce i akceptacji Pawła |
| Kolektor — ustalenia 2026-10-09 | zadanie `valuebet-odds`: Logon Mode Interactive only (po restarcie bez logowania nie działa), `python.exe` z oknem konsoli, ExecutionTimeLimit 10 min, IgnoreNew; 9.10 08:37 przebieg zawieszony po zapisie heartbeatu, ubity o 08:47 (zdarzenie 329). Hipoteza (nie potwierdzona): zapis do konsoli w trybie QuickEdit. Poprawka (`pythonw.exe` albo log do pliku) — razem z migracją na VPS. Pobrania zaplanowane od 1.10: 3/3 |
| Zakłady | zero; wydane złotówki: zero |

## 3. Stawkowanie — ile da się wycisnąć bez ryzyka bankructwa

Zwrot z kapitału rośnie liniowo z ułamkiem Kelly'ego `c`, ale ryzyko
obsunięcia rośnie szybciej: szansa, że kapitał kiedykolwiek spadnie do
ułamka `x`, wynosi ~`x^(2/c − 1)` — przy prawdziwej przewadze. Przy przewadze
przeszacowanej dwukrotnie nominalne „½ Kelly'ego" jest w rzeczywistości
pełnym Kellym.

Symulacja roku: kurs 2.0, limit 2% na zakład (reguła 23), procent składany,
20 000 ścieżek.

| scenariusz | c | stawka | E[zwrot] | mediana | P(strata po roku) | P(obsunięcie ≥ 30%) | P(≥ 50%) |
|---|---|---|---|---|---|---|---|
| Ekstraklasa, 8/mies., e = 2.5% | ¼ | 0.62% | 1.5% | 1.1% | 44% | 0.0% | 0.00% |
| ″ | ½ | 1.25% | 3.0% | 1.8% | 44% | 0.3% | 0.00% |
| + top ligi, 30/mies., e = 2.5% | ¼ | 0.62% | 5.8% | 4.4% | 34% | 0.1% | 0.00% |
| ″ | ½ | 1.25% | 12.1% | 10.2% | 38% | 15.7% | 0.16% |
| ″ | 1 (limit 2%) | 2.00% | 20.4% | 13.7% | 37% | 54.6% | 7.9% |
| + top ligi, 40/mies., e = 2.5% | ½ | 1.25% | 15.9% | 11.9% | 34% | 24.4% | 0.89% |
| ″ | 1 (limit 2%) | 2.00% | 27.3% | 15.5% | 37% | 67.7% | 13.3% |
| 30/mies., przewaga przeszacowana 2× | ½ | 1.25% | 5.7% | 2.2% | 47% | 20.7% | 0.36% |
| 30/mies., przewagi brak | ½ | 1.25% | 0.0% | −2.8% | 56% | 27.5% | 0.80% |

**Parametry dla 10–15% rocznie — wszystkie cztery naraz:**
1. ½ Kelly'ego, ale dopiero po potwierdzeniu przewagi przez CLV (bramka G-K);
2. 30–40 okazji miesięcznie — Ekstraklasa plus top ligi;
3. przewaga ≥ 2.5% potwierdzona CLV, a nie obiecana przez alert;
4. głównie single bez podatku (Betclic w reżimie 50/50, §4.1).

Wtedy: oczekiwanie 12–16% rocznie, mediana 10–12%, obsunięcie ≥ 50% poniżej
1%. Cena: mniej więcej co trzeci rok kończy się stratą mimo prawdziwej
przewagi, a co czwarty–szósty przechodzi przez obsunięcie ≥ 30%. Przy
kapitale 10 000 zł oczekiwanie to 1 200–1 600 zł rocznie.

**Pełny Kelly odpada.** Mediana rośnie z 10% do 14%, a szansa obsunięcia
≥ 30% z 16% do 55%. Bez przewagi pełny Kelly traci medianowo 7% i w 70% lat
przechodzi przez obsunięcie ≥ 30%. Powyżej pełnego Kelly'ego tempo wzrostu
spada — „agresywniej" nie znaczy „więcej".

**Wolumen to bezpieczna dźwignia; ułamek Kelly'ego — najniebezpieczniejsza.**

### 3.1 Polityka stawek

| etap | warunek | c | limity |
|---|---|---|---|
| start | G-S zaliczone dla ligi | ¼ | 2% na zakład, 3% na mecz, 15% łącznej otwartej ekspozycji |
| G-K | ≥ 150 zakładów za prawdziwe pieniądze; średnie CLV > 0, dolna granica CI > 0 | ½ — od przewagi skorygowanej: `e_użyte = e_alertu × min(1, CLV zrealizowane / EV przewidziane)` | jak wyżej |
| zawsze | — | nigdy > ½ | reguły 21–23 |

- **Wyłącznik:** obsunięcie 25% od szczytu → stop pieniędzy, powrót do paper,
  audyt.
- **Kapitał projektu** to osobna, z góry ustalona kwota: zero dopłat po
  stratach; zyski wolno wypłacać.
- Reguła 21 w `CLAUDE.md` („domyślnie 0.25") dostaje dopisek o bramce G-K
  razem z krokiem S4.

## 4. Bukmacherzy i podatek

**Podatku nie da się „ominąć".** Można tylko grać tam, gdzie bukmacher pokrywa
go w ramach promocji — na jego warunkach.

Oferty według serwisów porównawczych, wrzesień 2026 — **do weryfikacji w
regulaminach** (jak przy Betclicu):

| bukmacher | gra bez podatku | warunki | przydatność dla value |
|---|---|---|---|
| Betclic | Bez Podatku 2.0, bezterminowo | pierwsze 1000 zł stawek — wszystko; potem single bez podatku, jeśli ≥ 50% obrotu idzie w AKO (regulamin §3 ust. 3–12, `docs/promocje.md`; w kodzie wariant pesymistyczny: także ≥ 50% kuponów) | **jedyne single bez podatku** — bukmacher główny |
| TOTALbet | bezterminowo, pre-match i live | min. 3 zdarzenia, każde ≥ 1.30 | potrójne value — dodatkowa pojemność |
| Fortuna | BetBuilder bez podatku (od 05.2026, przełącznik) i AKO z warunkami | BetBuilder: min. 1 zdarzenie z oferty BetBuilder; AKO: min. 3–5 zdarzeń ≥ 1.30–1.35 | BetBuilder — nisza dla modelu (§4.3) |
| forBET, LVBET | czasowo po rejestracji (10–60 dni) | min. 3 zdarzenia, kurs ≥ 1.30–1.40 albo łączny ≥ 2.40 | krótko, mała pojemność |
| Superbet, Betters, Betfan | boosty AKO, nie „bez podatku" | 5–8+ zdarzeń | **bezużyteczne** dla value |
| STS | brak gry bez podatku | — | tylko oferta powitalna (§4.4) |

### 4.1 Wydajność form zakładu

Ta sama pula nóg value, ten sam ułamek Kelly'ego, kurs nogi ~2.0:

| forma | zwrot względem singli bez podatku |
|---|---|
| single bez podatku | 100% |
| **Betclic 50/50** — połowa obrotu w dublach, reszta single | **~75%** |
| same duble | ~67% |
| potrójne (TOTALbet) | ~43% |
| single z podatkiem 12% | ujemny przy przewadze < 13.6% |

Reżim 50/50 u Betclica odzyskuje większość tego, co zabierają same duble:
regulamin liczy udział AKO po obrocie, więc każda złotówka w dublach
„odblokowuje" złotówkę w singlach bez podatku. Moduł EV śledzi ten udział z
dziennika zakładów. Pozostali bukmacherzy nie zastąpią Betclica — **dokładają
pojemność**, gdy Betclic zacznie limitować.

### 4.2 Weryfikacja — zadania, nie założenia

- `docs/promocje.md` na wzór `docs/sources.md`: dla każdego bukmachera cytat
  z regulaminu promocji, data, warunki, klauzule wykluczenia.
- Marże z danych, nie z reklam: Paweł ręcznie zapisuje kursy 1X2 i O/U 2.5 z
  jednej kolejki u 4–5 bukmacherów (~20 minut) → booksum per bukmacher.
- Do sprawdzenia w regulaminie Fortuny: czy BetBuilder z jednym wyborem jest
  możliwy. Jeśli tak — to de facto single bez podatku u drugiego bukmachera.

### 4.3 BetBuilder — gdzie model zarabia tam, gdzie Pinnacle nie daje ceny

Kombinacje z jednego meczu („Legia wygra i powyżej 2.5 gola") — Pinnacle ich
nie wycenia, macierz wyników tak: λ i μ dopasowane jednocześnie do kursów
Pinnacle 1X2 **i** totali (oba zbiera S1) plus korekta DC. Nie z samego 1X2 —
suma goli wyprowadzona z 1X2 jest wrażliwa na formę funkcyjną
(`STEP4_ENSEMBLE.md` §11.10). Własne λ, μ modelu nie są tu używane.
Bramka G-M: 30 ręcznie zapisanych cen BetBuilder Fortuny, tylko kombinacje
oparte na wyniku, porównanych z naszą ceną uczciwą. Dopiero gdy mediana
rozbieżności po mnożniku bez podatku jest dodatnia — paper trading jak w
torze S.

### 4.4 Oferty powitalne — jednorazowy kapitał startowy

Zwroty, freebety, bonusy od depozytu: każdą ofertę liczymy kalkulatorem EV
(podatek, wymagany obrót, minimalne kursy) **po przeczytaniu regulaminu**.
Bonusy z dużym obrotem mają po podatku EV bliskie zera; wartościowe są
zwykle zwroty i freebety. Jednorazowe — nie wliczamy ich do rocznego zwrotu.

## 5. Wolumen i skalowanie lig

„Błyskawicznie", ale bez pomijania dowodu: **paper trading wszystkich lig
równolegle od pierwszego dnia, pieniądze per liga po jej własnej bramce
G-S.** Top ligi mają więcej meczów, więc mogą zaliczyć G-S wcześniej niż
Ekstraklasa. Dowód z Ekstraklasy nie przenosi się na Premier League —
każda liga ma własną efektywność rynku.

Budżet kredytów The Odds API (plan darmowy, 500/mies.) — liczby poniżej
nieaktualne; obowiązuje §2, wiersz „Odds API, kredyty” (2026-10-16):
- Ekstraklasa: 2 rynki, zamknięcia + migawka decyzyjna (bez T−24 h, decyzja
  Pawła 2026-10-04); plan wszystkich lig z `scripts/odds_budget.py`: 374/mies.;
- Premier League i Bundesliga (najmniej slotów godzinowych): tylko
  zamknięcia, 2 rynki — ~100 kredytów;
- kolejne ligi dopiero po pomiarze, gdzie polskie kursy najczęściej
  przebijają Pinnacle. Ligę dobieramy po liczbie okazji, nie po prestiżu.

**Ścieżka krytyczna wolumenu: zautomatyzowany, zgodny z regulaminem i
robots.txt odczyt kursów Betclica.** Bez niego zostaje tryb progowy `k_min`
(`COLLECTOR_PLAN.md` §3.10): ręczne sprawdzanie, realnie 10–20 kursów
dziennie — za mało na 30–40 okazji miesięcznie w trzech ligach. Dlatego
najważniejsze 10 minut w projekcie to zapis zapytania z kursami Betclica z
DevTools.

## 6. Droga do pierwszego prawdziwego zakładu

### Tor S

| # | krok | zależy od |
|---|---|---|
| S1 | The Odds API na żywo: Ekstraklasa + Premier League + Bundesliga (§5), z migawką decyzyjną (`TOR_S_PLAN.md` §2) | kod gotowy — rejestracja zadania wg `docs/task_scheduler.md` |
| S2 | Betclic: discovery → robots.txt hosta → automatyczny odczyt albo tryb `k_min` | 10 minut Pawła z DevTools |
| S3 | Kolektor Betclica, fazy 1a–1b (`COLLECTOR_PLAN.md`), jeśli S2 dał zgodną ścieżkę | S2 |
| S4 | Wycena, EV, reżim 50/50 Betclica, stawki, wyłącznik — `TOR_S_PLAN.md` §3–§5 | kod gotowy po audycie; pierwsze podłączenie w F1 |
| S5 | Przegląd dnia (Telegram albo plik), dziennik zakładów, CLV — `TOR_S_PLAN.md` §6–§8 | kod gotowy; przegląd dnia i Telegram uruchamiamy dopiero w F2 |
| S6 | Paper trading per liga → G-S per liga | **F1 = POTWIERDZONA + FSA #1** |
| S7 | Pierwsze prawdziwe zakłady przy c = ¼ → po 150 zakładach G-K → c = ½ | S6 |

Równolegle: `docs/promocje.md`, ręczny pomiar marż, próbka BetBuilder (§4.2–§4.3).

### Tor M

| # | krok |
|---|---|
| M1 | ~~Poprawka C → przebieg → §11.8~~ **zrobione:** DC zamknięte jako model 1X2 (§11.10); walidacja instrumentu totali na Premier League |
| M2 | ~~Test pokrywania~~ **zrobione:** pula − Pinnacle `+0.0015 [−0.0003, +0.0040]` — brak wkładu modelu |
| M3 | Wycena kombinacji BetBuilder z danych rynkowych (§4.3, reguła 19a) — gdy będą próbki z Fortuny |
| M4 | Lockbox jednorazowo, w zawężonym zakresie, i `backtest-auditor` (`STEP4_ENSEMBLE.md` §11.11); projekcja i stacking skreślone |
| M5 | Raport portfolio |

## 7. Bramki i wyłączniki

| bramka | warunek | skutek |
|---|---|---|
| **G-S** (per liga) | ≥ 50 alertów i ≥ 4 kolejki; średnie CLV vs zamknięcie Pinnacle > 0, dolna granica CI > 0 (klastry = kolejki); ≥ 70% alertów z kursem wciąż dostępnym przy kliknięciu | prawdziwe pieniądze w tej lidze, c = ¼ |
| **G-K** | ≥ 150 zakładów za pieniądze, CLV > 0 z dolną granicą CI > 0 | c = ½ od przewagi skorygowanej |
| **G-M** | 30 próbek BetBuilder, mediana rozbieżności po mnożniku > 0 | paper trading BetBuilder, potem bramka jak G-S |
| **Wyłącznik** | obsunięcie 25% od szczytu albo górna granica CI kroczącego CLV (50 zakładów) < 0 | stop pieniędzy, powrót do paper, audyt |
| **FSA** (między Filarami) | zero otwartych KRYTYCZNYCH i POWAŻNYCH (`docs/FULL_SYSTEM_AUDIT.md`) + akceptacja Pawła | przejście do następnego Filaru |
| **Reguła zabicia** | liga, bukmacher albo forma zakładu dwa razy nie zalicza bramki | archiwum |

## 8. Rytm audytów

| rytm | co | wyzwalacz |
|---|---|---|
| każdy commit | pytest, ruff, mypy strict, `future_poison`; `backtest-auditor` po zmianach w `models/`, `pricing/`, `backtest/` | czerwone = brak merge |
| co tydzień | kolektor: pokrycie zamknięć ≥ 95%, luki, odrzucenia parsera, aliasy; zgodność: zapytania per host vs limity i `Crawl-delay`, diff robots.txt; kredyty The Odds API | przekroczenie lub zmiana robots.txt → źródło stoi |
| co 2 kolejki | przewaga: kroczące CLV (50 zakładów) z CI, liczba okazji i średnie EV per liga, dostępność kursów przy kliknięciu | wyłącznik z §7 |
| co miesiąc | konta: limity per bukmacher, udział AKO u Betclica; budżet: zero złotych na usługi; zakres: przyrost kodu vs bramki | wydatek bez wpisu w ROADMAP = cofnięcie |
| co kwartał | regulaminy promocji i robots.txt od nowa, martwy kod, pełny `backtest-auditor` | werdykt starszy niż kwartał = źródło stoi |

Twarde reguły przeciw rozrostowi: nowa liga, bukmacher albo forma zakładu
dopiero po zaliczonej bramce bieżącej; abstrakcja przy trzecim użyciu; nowa
zależność tylko z uzasadnieniem; moduł bez pozycji w ROADMAP nie powstaje.

## 9. Granice (stałe)

- Bot nigdy nie składa zakładu. Człowiek klika.
- Tylko licencjonowani polscy operatorzy. Bez VPN, bez brokerów, giełd i
  platform krypto bez polskiej licencji.
- Regulaminy bukmacherów i promocji obowiązują; robots.txt per host, łącznie
  z `Crawl-delay`. Bez obchodzenia anty-botów, bez proxy, bez rotacji IP.
- Jedno konto na osobę u każdego bukmachera.
- Kapitał projektu z góry ustalony; zero dopłat po stratach.
- Budżet zerowy na usługi. Lockbox oglądany raz.
  - **Wyjątek (decyzja Pawła 2026-10-08):** VPS dla kolektora S1 — Mikrus 2.1,
    **75 zł/rok**; start od 30-dniowego testu za **7 zł**; ewentualny upgrade do
    Mikrus 3.0 za **130 zł/rok**. Specyfikacja migracji — osobno; do tego czasu
    kolektor zostaje na laptopie (zadanie `valuebet-odds`).

---

# CZĘŚĆ II — HISTORIA I DECYZJE

## Krok 3 — ZAMKNIĘTY (audyt 2026-09-30)

- [x] `ingest/football_data.py` — 4151 meczów Ekstraklasy 2012/13–2026/27,
      pokrycie nazw 100%.
- [x] Pierwszy przebieg Elo + sanity check (`backtest/elo_baseline.py`).
- [x] `backtest/metrics.py` — reliability diagram, log loss vs baseline'y
      (stała, Elo→1X2 przez ordered logit, rynek po Shinie).
- [x] Audyt `backtest-auditor` na `features/` i `backtest/` —
      `AUDIT_REPORT.md`, 14 znalezisk, **zero KRYTYCZNYCH, zero przecieków
      z przyszłości**. Dwa POWAŻNE naprawione, cztery DO SPRAWDZENIA opisane
      z konkretnym działaniem rozstrzygającym.
- [ ] CLV — **nieliczalne** z football-data (brak kursów sprzed zamknięcia).
      Wymaga własnych snapshotów kursów z pollera.

### Wynik po audycie (n=3319 OOS)

CI z bootstrapu **klastrowego po sezonach**. Poprzednia wersja liczyła iid
po meczach i była o 31% za wąska — patrz CONTEXT.md §5.19.

| referencja | n | sezony | luka Elo − rynek | CI 95% |
|---|---|---|---|---|
| Pinnacle po Shinie | 3055 | 2015/16–2025/26 (11) | **+0,0145** | [+0,0062, +0,0229] istotna |
| Betfair Exchange po Shinie | 656 | 2024/25–2026/27 (3) | **+0,0121** | [−0,0001, +0,0232] nieistotna, CI niewiarygodne (3 klastry) |

Rynek lepszy. Luka w strefie 0,01–0,03 → same ratingi nie wystarczą, ale
niosą większość sygnału. `elo − stała = −0,0200 [−0,0273, −0,0125]`.

**Wartości punktowe nie zmieniły się po audycie.** Zmieniła się deklarowana
pewność i porównywalność.

### Tych dwóch liczb NIE WOLNO porównywać między sobą

Stoją na różnych meczach: 2637 ma tylko Pinnacle, 238 tylko BFEC, wspólnych
jest 418. Różnica 0,0145 vs 0,0121 mierzy podzbiór, nie źródło.

Na wspólnych 418 meczach obie referencje są **nierozróżnialne**:

```
Elo − pinnacle +0,0166   Elo − bfec +0,0159   różnica luk +0,0006
LL(pinnacle) − LL(bfec) = −0,0006 [−0,0064, +0,0015]   NIEistotna
```

I to mimo booksumu 1,0415 vs 1,0096 oraz z = 0,0209 vs 0,0048. Szczegóły:
CONTEXT.md §5.20. W raporcie liczy to sekcja REFERENCJE NA WSPÓLNYM
PODZBIORZE — czytaj ją, zanim wyciągniesz wniosek „exchange łatwiej pobić".

**Decyzja o referencji CLV.** Pinnacle zamknięcie (`PSC*`) brakuje dla
194/306 meczów 2025/26 i całego 2026/27. Referencją jest:
- Pinnacle po Shinie — tam, gdzie jest (2012/13–2024/25);
- Betfair Exchange zamknięcie (`BFEC*`) po Shinie — od 2024/25.

**Dwie luki raportujemy osobno.** Nigdy nie mieszamy ich w jedną liczbę —
exchange ma inną strukturę marży niż book i inny profil graczy. Audyt
pokazał jednak, że przejście Pinnacle → BFEC w 2024/25 **nie wprowadza
skoku poziomu referencji**: na wspólnych meczach mierzą to samo. To
argument za ciągłością szeregu, nie za uśrednianiem.

### Selekcja próby — sprawdzona, nie jest problemem

Mecze bez kursu zamknięcia wypadają w dwóch miejscach (`football_data.py:391`
— policzone i zalogowane; `elo_baseline.py` inner join — teraz widoczne przez
`MarketGap.n` i `MarketGap.seasons`). Brakuje 264/4151 dla Pinnacle,
3495/4151 dla BFEC. Selekcja jest **kalendarzowa, nie wynikowa**: chi-kwadrat
rozkładu 1/X/2 usunięte vs zachowane daje p = 0,77–0,89. Kontrfaktyk bez
selekcji: luka +0,0144 zamiast +0,0149, czyli 3% w kierunku konserwatywnym.

### Otwarte po audycie (DO SPRAWDZENIA, opisane w AUDIT_REPORT.md)

- **DS-3** hiperparametry Elo bez foldu walidacyjnego — rozstrzyga fold
  wewnątrz trainu. Przesłanka, że reguła 10 nie jest złamana: luka rośnie
  monotonicznie z `k`, a `k=20` nie jest optimum. `home_advantage` jest
  nieidentyfikowalny obok ordered logit — **uwaga przy DC, gdzie `γ` jest
  estymowane razem z `α, β`** (STEP4_PLAN §1.2).
- **DS-4** `shin.py` przy `allow_underround=True` zwraca normalizację
  proporcjonalną (reguła 16). Dziś 0 wierszy, więc wpływ zerowy.
- **DS-5** kompletność rynku walidowana w ingeście, nie przy wywołaniu
  Shina (reguła 17). Dziś wszystkie wiersze mają 0 albo 3 kursy.
  **Krok 4 otwiera rynki dwustronne i wtedy to przestaje być teoretyczne.**
- **DS-6** `data/raw/` ma jeden snapshot, a źródło koryguje wstecz
  (reguła 12). Rozstrzyga drugie pobranie i diff.

## Lockbox — obowiązuje od 2026-09-30

Decyzja z `STEP4_ENSEMBLE.md` §2. Zbiór OOS z kroku 3 był oglądany trzy
razy (Elo, DC, mieszanka), więc przestał być zbiorem testowym w sensie
ścisłym. Dwa ostatnie sezony są odłożone.

| Zbiór | Sezony | n (OOS) | Rola |
|---|---|---|---|
| deweloperski | 2015/16 – 2024/25 | 2944 | wszystkie decyzje, diagnostyka, strojenie |
| **lockbox** | **2025/26, 2026/27** | **375** | **jedna ewaluacja, na końcu kroku 4** |

Egzekwowane kodem: `backtest/lockbox.py` — `split_dev_lockbox()` i
`assert_no_lockbox()`. Każda liczba wpływająca na decyzję przechodzi
przez bezpiecznik.

**Zastrzeżenie do protokołu.** Lockbox zadeklarowano PO tym, jak log loss
DC i Elo dla obu odłożonych sezonów pojawił się w raportach walk-forward
sesji z 2026-09-30. Żadna decyzja nie została na nich oparta (naprawa
regularyzacji DC wynikła z analizy sezonu 2017/18, wybór kryterium
strojenia — ze średniej po wszystkich sezonach), ale lockbox nie jest
dziewiczy i końcowy wynik trzeba czytać z tą poprawką.

**Do czasu zamknięcia kroku 4 nie raportujemy wyników per sezon dla
2025/26 i 2026/27.**

**Stan 2026-10-02: ZUŻYTY.** Obejrzany raz, 2026-10-01
(`reports/lockbox_3433f2c.json`; etykieta commita nieodtwarzalna —
`reports/lockbox_3433f2c.PROVENANCE.md`, FSA #0 F-24). Rejestr obejrzeń:
`reports/lockbox_views.jsonl`; kolejny przebieg `scripts/run_lockbox.py`
jest odrzucany kodem. Filaru 1 nie dotyczy — tam nic nie jest strojone.

## Krok 4 — Dixon-Coles i rynki pochodne

**§2 (bramka jakościowa) zastąpiona przez `STEP4_ENSEMBLE.md`.**
Pierwotna bramka porównywała model skalibrowany (Elo + ordered logit)
z nieskalibrowanym (surowa macierz DC) i mierzyła DC na rynku, którego
Elo w ogóle nie wycenia. Nowa bramka to G1-G4 z aneksu.

Model golowy DC z time decay (ξ ≈ 0,003/dzień). Z jednej macierzy
prawdopodobieństw wyników (i, j) wyceniamy **jednocześnie** 1X2, handicapy
azjatyckie i over/under — jedna estymacja, wiele rynków, spójna wycena.
Argument za DC zamiast GBM: ~36 parametrów na ~6000 obserwacji goli, co
przy naszej próbie jest zdrowe; GBM z 30 cechami na 3000 wierszy nie jest.

Warunek wejścia: Elo z kroku 3 ma policzoną lukę do rynku. Jeśli luka jest
mała (<0,01 log loss), DC ma coś do poprawienia; jeśli duża (>0,03), DC
jest koniecznością, nie opcją.

## Krok 4b — Symultaniczny Kelly

Zakłady na ten sam mecz są **skorelowane**: Over 2.5 i AH −0.5 wygrywają
i przegrywają razem. Niezależne Kelly per zakład sumuje ekspozycję tak,
jakby były niezależne, i przekracza limit 2% bankrolla na mecz bez
żadnego sygnału.

Implementacja etapami:
1. **Poziom 1 (start):** naiwne skalowanie — suma ułamków Kelly na jeden
   mecz ograniczona do limitu meczowego, proporcjonalnie ściągana w dół.
2. Poziom 2: pełny symultaniczny Kelly na wspólnej macierzy wyników z DC
   (ta sama macierz, która wycenia rynki, daje łączny rozkład wypłat).

Zawsze ułamkowy (0.25), z podatkiem, twardy limit 2% (reguły 21–23).

## Krok 5 — Steam chasing WYŁĄCZNIE jako walidator

Analiza ruchu linii (Pinnacle / BFEC między otwarciem a zamknięciem)
służy do jednego: sprawdzenia, czy nasze sygnały +EV wyprzedzają ruch
rynku (model ma informację) czy idą za nim (model odtwarza rynek z
opóźnieniem). To jest test skuteczności modelu, nie strategia.

**Nie gramy steam chasingu live.** Polski rynek nie ma płynności ani
szybkości, żeby to działało; soft-book kopiuje Pinnacle w minuty, a my
mamy bet delay i limity. Każdy pomysł „ale przecież widać ruch" wraca do
tego akapitu.

## Odrzucone — nie wracamy bez nowych danych

- **Pogoda.** Za mała próba, żeby wyestymować efekt na tle szumu; rynki
  golowe i tak to wyceniają przed meczem.
- **Sędzia.** Jak wyżej — efekt sędziego na kartki/rożne istnieje, ale
  próba per sędzia w Ekstraklasie to kilkanaście meczów na sezon.
- **Zmiana trenera, motywacja końcówki sezonu** — patrz CONTEXT.md §1.
- **Historia kontuzji z Transfermarktu** — look-ahead bias, CONTEXT.md §2.
- **Polymarket przez VPN, Betfair Exchange, Smarkets** (2026-10-01) — gra u
  operatora bez polskiej licencji; art. 107 § 2 KKS, przepadek wygranej.
  Archiwum planu zakładów §6.
- **Brokerzy azjatyccy, krypto (SX Bet), live/HFT z botem, sygnały VIP
  w skali 15 000 zł/mies.** (2026-10-01, 13:29) — archiwum decyzji §2.
- **Pełny Kelly** (2026-10-01, 14:07) — Część I §3: przy limicie 2% mediana
  +14% zamiast +10% za cenę 55% zamiast 16% szansy obsunięcia ≥ 30%.
- **Obchodzenie robots.txt** (2026-10-01) — archiwum planu zakładów §9;
  Część I §9.
- **Pinnacle i Betfair bezpośrednio jako źródło kursów** — bez polskiej
  licencji; linia ostra wyłącznie przez The Odds API.

## Po kroku 5

- ~~`live/` — poller `httpx`, detektor value, alerty Telegram. Dopiero gdy
  backtest DC bije zamknięcie na sensownym `n`.~~ **Zastąpione 2026-10-01:**
  najpierw przez silnik S (archiwum planu zakładów §3), o 13:29 przez
  ścieżkę C (archiwum decyzji §4), o 14:07 przez model hybrydowy
  (Część I): `live/` to tor S, pieniądze per liga po bramce G-S.
- `models/hierarchical.py` (PyMC) — dla lig z małą próbą, po DC.
