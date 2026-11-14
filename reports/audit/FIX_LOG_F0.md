# FIX_LOG_F0 — naprawy po FSA #0

Specyfikacja: `docs/FSA0_NAPRAWY.md` (protokół §1, kolejność §2). Raport
źródłowy: `reports/audit/FSA_2026-10-01_F0.md`. Ten plik to **twierdzenia
wykonawcy do sprawdzenia**, nie dowód (`docs/FULL_SYSTEM_AUDIT.md`).

Każdy wiersz: test regresji ścieżki niebezpiecznej, wynik na commicie
bazowym (PRZED — czerwony z powodu zachowania), commit naprawy i wynik PO,
rewers (§1, etap F). Hash commita naprawy dopisywany w następnym commicie.

**Akceptacja przejścia F0 → F1 (z góry, warunkowa):** „Jeśli testy i audyt
dadzą zielone światło – wreszcie otworzy bramkę i automatycznie przejdzie do
Filaru 1” (Paweł, 2026-10-02 11:33). Warunek sprawdza etap H (§6) na
podstawie linii `BRAMKA` raportu audytora.

## Tabela

<!-- TABELA -->
| id | klasa | test | PRZED (commit, wynik) | PO (commit, wynik) | rewers | stan |
|---|---|---|---|---|---|---|
| F-09+F-10 | DROBNE | `test_fsa0_f10_gitignore.py` | e6632f7: 9 failed, 3 passed in 1.37s | ce35c67: 12 passed in 1.18s | n/d (DROBNE; rewers §4 tylko POWAŻNE i A-01/A-02) | naprawione |
| F-14 | POWAŻNE | `test_fsa0_f14_state_outside_raw.py` | d19f8e4: 3 failed in 1.06s | b8129c0: 3 passed in 1.26s | czerwony @d19f8e4: 3 failed (asercje ścieżek) | naprawione |
| F-12+F-17 | POWAŻNE | `test_fsa0_f12_raw_manifest.py` | b8129c0: 1 failed, 1 passed, 5 errors in 0.88s | b9e1045: 7 passed in 1.61s | czerwony @b8129c0: brak modułu raw_store + 2 asercje rejestru | naprawione |
| R30-meta | POWAŻNE | `test_rule30_guards.py` | b9e1045: 2 failed, 3 passed in 1.08s | 3cdacf7: 5 passed in 1.18s | czerwony @b9e1045: 2 failed (53 naruszenia) | naprawione (KNOWN_VIOLATIONS puste od 3cdacf7) |
| F-05 | POWAŻNE | `test_fsa0_f05_tax_validation.py` | 5814adc: 21 failed, 2 passed in 2.31s | edd9881: 23 passed in 2.34s | czerwony @5814adc: 21 failed (DID NOT RAISE) | naprawione |
| F-04 | POWAŻNE | `test_fsa0_f04_clv_as_of.py` | edd9881: 4 failed in 3.15s | 48e254e: 4 passed in 2.60s | czerwony @edd9881: 4 failed (DID NOT RAISE, asercje) | naprawione |
| A-01 | POWAŻNE | `test_fsa0_a01_clv_closing_key.py` | edd9881: 2 failed in 2.66s | 48e254e: 2 passed in 2.38s | czerwony @edd9881: 2 failed (p_close None / CLV z klucza meczu) | naprawione |
| F-19+F-06 | POWAŻNE | `test_fsa0_f19_kelly_gate.py` | 25a62c9: 5 failed, 3 passed in 2.76s | 79db8f7: 8 passed in 2.96s | czerwony @25a62c9: 5 failed (c=0.5, DID NOT RAISE) | naprawione |
| F-20 | POWAŻNE | `test_fsa0_f20_fair_kickoffs.py` | 79db8f7: 3 failed, 1 passed in 2.93s | b26f520: 4 passed in 1.28s | czerwony @79db8f7: 3 failed (wycena kursu live) | naprawione |
| F-01+F-21+W.8 | POWAŻNE | `test_fsa0_f01_lockbox.py` | b26f520: 12 failed, 7 passed (worktree) | 85e8fc8: 19 passed in 2.97s | czerwony @b26f520: 12 failed (DID NOT RAISE, wartownik lockboxa) | naprawione |
| F-25+F-08 | POWAŻNE | `test_fsa0_f25_betclic_regime.py` | 25e8f9f: 6 failed in 0.64s | 62598d0: 6 passed in 0.60s | czerwony @25e8f9f: 6 failed (tax 1.0 zamiast 0.94/0.88) | naprawione |
| A-02 | POWAŻNE | `test_fsa0_a02_winnings_tax.py` | 62598d0: 2 failed, 1 passed in 3.02s | 06971e7: 3 passed in 2.15s | czerwony @62598d0: 2 failed (2500 zamiast 2250) | naprawione |
| F-02+F-03+F-31 | POWAŻNE | `test_fsa0_f02_coupons.py` | 06971e7: 5 failed in 0.90s | 97b5c60: 5 passed in 0.87s | czerwony @06971e7: 5 failed (obrót 250 zamiast 150) | naprawione |
| F-26 | POWAŻNE | `test_fsa0_f26_http_client.py` | 97b5c60: 1 error in 1.33s | a577291: 8 passed in 2.56s | czerwony @97b5c60: brak modułu net.http | naprawione |
| F-15+F-16 | POWAŻNE | `test_fsa0_f15_budget.py` | a577291: 3 failed, 1 passed in 1.84s | aea5d25: 4 passed in 1.49s | czerwony @a577291: 3 failed (kredyt mimo 449/450) | naprawione |
| F-13 | POWAŻNE | `test_fsa0_f13_closings.py` | aea5d25: 3 failed, 1 passed in 1.31s | 8171848: 4 passed in 0.94s | czerwony @aea5d25: 3 failed (zamknięcie przepada, migawka -25 min) | naprawione |
| F-24 | POWAŻNE | `test_fsa0_f24_provenance.py` | b990d07: 1 error in 0.59s | d7f66b7: 3 passed in 2.36s | czerwony @b990d07: brak modułu provenance | naprawione |
| F-28+R29 | POWAŻNE | `test_rule29_wiring.py` | d7f66b7: 1 failed, 2 passed in 0.83s | 3cdacf7: 3 passed in 0.81s | czerwony @d7f66b7: moduły bez wiersza w ROADMAP §2 | naprawione |
| F-32 | POWAŻNE | `test_fsa0_f32_context_audits.py` | 3cdacf7: 1 failed, 2 passed in 0.79s | 33fba89: 3 passed in 0.39s | czerwony @3cdacf7: audyty bez wpisu w CONTEXT §5 | naprawione |
| A-03 | DROBNE | `test_fsa0_a03_shin_fallback.py` | 33fba89: 2 failed in 1.38s | f12703c: 2 passed in 1.17s | n/d (DROBNE) | naprawione |
| DROBNE (F-07,F-11,F-18,F-22,F-30) | DROBNE | `test_fsa0_minor.py` | f12703c: 6 failed in 2.47s | 2b61e31: 6 passed in 3.21s | n/d (DROBNE) | naprawione |
| F-23+W.10 | DROBNE | `test_fsa0_f23_instrument_verdict.py` | 2b61e31: 6 failed in 2.76s | aba1199: 6 passed in 2.41s | n/d (DROBNE) | naprawione |
| F0b-03 | POWAŻNE | `test_fsa0b_03_journal_tax_factor.py` | 5580d9f: 10 failed in 2.50s | fe8d8cd: 10 passed in 15.91s | czerwony @5580d9f: 10 failed (DID NOT RAISE) | naprawione |
| F0b-02 | POWAŻNE | `test_fsa0b_02_t12_market.py` | fe8d8cd: 7 failed in 0.98s | a28ad51: 7 passed in 0.45s | czerwony @fe8d8cd: 7 failed (tax 1.0 zamiast 0.88, DID NOT RAISE) | naprawione |
| F0b-01 | POWAŻNE | `test_fsa0b_01_closing_coverage.py` | a28ad51: 2 failed, 1 passed in 2.16s | 2b681b4: 3 passed in 2.09s | czerwony @a28ad51: 2 failed ((1, 1) zamiast (1, 2)); zielony = warunek sceny | naprawione |
| F0c-03 | POWAŻNE | `test_fsa0c_03_t12_vocabulary.py` | 32fac6e: 14 failed, 1 passed in 0.79s | 72d77d6: 15 passed in 0.87s | czerwony @32fac6e: 14 failed, 1 passed (DID NOT RAISE, tax 1.0 zamiast 0.88) | naprawione |
| F0c-01+F0c-04 | POWAŻNE (+DROBNE) | `test_fsa0c_01_coverage_per_match.py` | 72d77d6: 4 failed | ff682fb: 4 passed in 2.16s | czerwony @72d77d6: 4 failed ((1, 2) zamiast (1, 6); (1, 1) zamiast (0, 1)) | naprawione |
| F0c-02 | POWAŻNE | `test_fsa0c_02_schedule_stall.py` | 72d77d6: 3 failed | ff682fb: 3 passed in 58.58s | czerwony @72d77d6: 3 failed (zero wywołań PL, brak schedule_empty) | naprawione |
| F0c-05 | DROBNE | diff `ROADMAP.md` §0 (tekstowe, §1 pkt 7) | — | 6a71b1e | n/d (DROBNE) | naprawione |
| F0d-01 (+F0d-02, F0d-03, F0d-05, F0b-08, F0b-09) | POWAŻNE (+DROBNE) | `test_fsa0e_collector_invariant.py` (500 światów), `test_fsa0e_by_construction.py` | de89be2: niezmiennik 10 failed, 1 passed (380/500 światów łamie); z konstrukcji 8 failed | 940bada: 11 passed in 286s; 9 passed | czerwony @de89be2 (worktree): 380/500 światów; 8/8 asercji zachowania | naprawione |
| F0d-04 | DROBNE | `test_fsa0e_f0d04_market_names.py` | 940bada: 5 failed in 3.66s | efac05b: 5 passed | czerwony @940bada (worktree): 5 failed | naprawione |
| F0d-06 | DROBNE | diff `docs/task_scheduler.md`, `schema.py` (tekstowe, §1 pkt 7) | — | 8b97419 | n/d (DROBNE) | naprawione |
| F0e-01 (kalkulator) | DROBNE | `test_fsa0e_01_budget_simulation.py` | a8fe087: 1 failed in 59.69s (412.8 ≠ 102 × 4.3 = 438.6) | d2437ea: 1 passed; z F0b-08: 10 passed in 33.07s | n/d (DROBNE) | naprawione (kalkulator) |
| F0e-01 (T-24h Ekstraklasy) | DROBNE | `test_fsa0e_t24_removed.py` | 7310a6e: 3 failed in 6.06s | 67b31d5: 3 passed; plan na żywym terminarzu 374/mies. | n/d (DROBNE) | naprawione (sesja 2026-10-07) |
| F0e-03 | DROBNE | `test_fsa0e_03_clv_keys.py` | 75ff3b2: 10 failed, 2 passed in 7.29s | 79ab9c9: 13 passed (z poprawką po backtest-auditor) | n/d (DROBNE) | naprawione (krok 1a Filaru 1) |
| F0e-06 | DROBNE | `test_fsa0e_06_docs.py` | 75ff3b2: 2 failed, 1 passed in 3.58s (wiersz ROADMAP naprawiony już w `75ff3b2`) | 79ab9c9: 3 passed | n/d (DROBNE) | naprawione (krok 1a Filaru 1) |
| F0e-05 | DROBNE (proceduralne → warunek przed F2) | `test_fsa0e_05_error_reasons.py`, `test_fsa0e_collector_invariant.py` | 67b31d5: 12 failed; niezmiennik [0],[1] 2 failed; 5fe017c: 8 failed, 12 passed | 71ae310: 20 passed; pełny pytest 877 passed | n/d (DROBNE) | naprawione — do weryfikacji przez audytora (FSA #1a) |
<!-- /TABELA -->

## Kolektor

| KOLEKTOR | kiedy (lokalnie) | stan | uwagi |
|---|---|---|---|
| wyłączony | 2026-10-02 12:19 | `schtasks /change /tn valuebet-odds /disable` → SUCCESS, „Scheduled Task State: Disabled” | ostatni przebieg 12:18:49, wynik 0; przerwa w heartbeat zamierzona (§3 etap 0) |
| włączony | 2026-10-02 17:16 | `Set-ScheduledTask` (wyzwalacz co 5 min, `StartWhenAvailable`, `WakeToRun`, bez warunku zasilania z sieci, `IgnoreNew`, limit 10 min) + `schtasks /change /enable`; XML: `Interval=PT5M` | po F-13, F-15, F-25b |
| heartbeat po włączeniu | 2026-10-02 17:17:55 (15:17:55 UTC) | `{"planned": [], "fetched": [], "budget_skip": [], "errors": [], "note": "nic nienależne"}` w `data/state/odds_api/heartbeat.jsonl` | ~1 min po włączeniu, `errors = []` |
| przerwa (uśpienie komputera) | 2026-10-02 18:42 → 2026-10-03 14:11 | System: Kernel-Power 42/107 (uśpienie 18:42, 19:15), wybudzenie Power-Troubleshooter 1 o 14:11:44; ostatni heartbeat przed: 16:37:57 UTC, pierwszy po: 12:21:52 UTC z `errors = []` | nie awaria kolektora; `LastTaskResult 0x800710E0` = start odrzucony, bo poprzednia instancja jeszcze trwała (`IgnoreNew`) — przebieg 14:17 po wybudzeniu trwał ~4 min |
| przerwa (zadanie Disabled) | 2026-10-03 14:28 → 14:43 | zaobserwowane przez audytora FSA #0b (F0b-06), nie zmiana wykonawcy; heartbeat 12:28:08 → 12:43:03 UTC, potem co 5 min z `errors = []`; dziennik Operational Harmonogramu wyłączony — przyczyna nieustalona | od 14:43 `Ready`; bez utraty danych (pierwsza należna kotwica 2026-10-08) |
| wyłączony (runda 0e) | 2026-10-03 19:23 | `schtasks /change /tn valuebet-odds /disable` → SUCCESS, State: Disabled | ostatni heartbeat 17:22:57 UTC `errors = []`; zmiany w `ingest/` (decyzja Pawła, pkt 0) |
| włączony (runda 0e, próba 1) | 2026-10-03 20:33 | `schtasks /change /enable` → SUCCESS, Ready | o 20:46 znów `Disabled`, przebieg 20:42:53 się nie odbył; przyczyna nieustalona |
| włączony (runda 0e, próba 2) | 2026-10-03 20:47:28 | `schtasks /change /enable` → Ready; przebieg 20:47:54 | **pierwsze prawdziwe `/events`** (`usage.jsonl` 18:47:58 UTC): ekstraklasa, premier_league, bundesliga — `last: 0`, `used: 3` bez zmian → warunek decyzji spełniony; o 20:48:20 zadanie znów `Disabled` (ten sam wzór co F0b-06: wyłączenie tuż po przebiegu) |
| włączony (runda 0e, próba 3) | 2026-10-03 20:49 | `Enable-ScheduledTask` (cmdlet zamiast `schtasks /change`) → Ready; obserwacja co 15 s | przebiegi 20:52:54, 20:57:54, 21:02:54 — stan `Ready` po każdym; hipoteza (nieudowodniona): `schtasks /change /enable` w tym środowisku zostawia zadanie, które Harmonogram wyłącza po przebiegu |
| heartbeat po włączeniu (15 min) | 2026-10-03 20:47:58 → 21:02:56 (18:47:58 → 19:02:56 UTC) | 4 linie, `errors = []`, `events_refreshed` co ≥ 60 min, `schedule_empty: []` | warunek §3 etap D spełniony |
| samoczynne wyłączenia (runda 0e) | 2026-10-03 ~21:13, 21:19:00 | `Disabled` bez udziału wykonawcy (obserwacja co 5–15 s): raz po przebiegu 21:12:54, raz bez przebiegu, w trakcie testów; próba odtworzenia (obciążenie CPU, pojedyncze testy kolektora) — nieudana; dziennik Operational wyłączony, brak uprawnień administratora (`wevtutil` → odmowa dostępu) | przyczyna NIEUSTALONA — do decyzji Pawła (włączenie dziennika jako administrator); po każdym wykryciu `Enable-ScheduledTask`, ostatnio 21:20:37 → Ready; luki widoczne w heartbeacie |
| bisekcja wyłączeń (runda 0e) | 2026-10-03 21:25 → 21:36 | pliki testów po kolei, stan zadania po każdym: `Disabled` po `test_fsa0_f14_state_outside_raw.py` (21:30:11) i po `test_fsa0c_03_t12_vocabulary.py` (21:33:03) — testy bez związku z Harmonogramem; oba tuż po przebiegach 21:27:54 i 21:32:54, ale epizod 21:19:00 był bez przebiegu | przyczyna NIEUSTALONA; w kodzie projektu brak odwołań do Harmonogramu (grep: `schtasks`, `ScheduledTask`, `win32com`, `ctypes.windll` — 0 w `src/`, `tests/`, `scripts/`); `Enable-ScheduledTask` 21:36 → Ready |
| czuwanie poprzedniej sesji | 2026-10-03 22:15 → ~22:51 | skrypt `task_guard2.ps1` (scratchpad sesji 4903cb05, poza repo): co 1 s czytał `TaskScheduler/Operational` (zdarzenia 140/142), zrzucał procesy do `data/state/diag/` (ignorowane przez gita) i włączał zadanie | przy wznowieniu 2026-10-04 proces już nie działał; pliki `data/state/diag/` zostają jako materiał diagnozy |
| przerwa (noc 3/4.10) | 2026-10-03 22:47:57 → 2026-10-04 12:58:55 | ostatni heartbeat 20:47:57 UTC; przebieg 22:52:54 zakończony `0xC000013A`; `Disabled` 22:57:26–23:19:38 i 23:19:45–23:26:28 (Avast, niżej), uśpienie 23:27 → 12:50 (Kernel-Power 42/107, krótkie wybudzenie 02:27); `NumberOfMissedRuns` 168 | pierwszy heartbeat po: 10:58:55 UTC, `errors = []`, `/events` ×3 `last: 0`; bez utraty zamknięć (pierwsza należna kotwica 2026-10-08) |
| **przyczyna wyłączeń — USTALONA** | 2026-10-04 13:05 | `TaskScheduler/Operational` (czytelny od 2026-10-03 21:56:42): każde z 10 wyłączeń `valuebet-odds` (142) w tej samej sekundzie co utworzenie `\AVAST Software\Gaming mode Task Scheduler recovery` (106); Avast wyłącza wtedy **wszystkie** zadania spoza `\Microsoft\` (Lenovo, McAfee, Edge, OneDrive, WD), przy wyjściu włącza je (140) i usuwa swoje (141). Na żywo: 12:56:55 → 12:59:26 i 13:09:01 → 13:13:58 (w trakcie pełnego `pytest`, 836 passed) | tryb gry Avasta; nie błąd kolektora ani Harmonogramu. Epizody sprzed 21:56:42 — ten sam wzór, bez zapisu w dzienniku. Tabela i lista dla Pawła: `docs/task_scheduler.md` §„Samoczynne wyłączenia”. Ustawień Avasta CLI nie zmienia |
| luki: tryb gry Avasta | 2026-10-04 15:58:52, 16:25:17, 16:58:07, 19:02:55/58 | 106 `\AVAST Software\Gaming mode Task Scheduler recovery` + 142 `\valuebet-odds` w tej samej sekundzie; heartbeat 14:23→14:52, 14:57→16:53, 16:57→17:48 UTC | powód: **tryb gry Avasta** |
| luki: komputer wyłączony | 2026-10-04 19:58 → 10-05 17:51, 10-05 20:02 → 10-06 18:38, 10-06 21:22 → 10-07 19:35 | heartbeat bez linii; w tych godzinach brak zdarzeń 106/142 Avasta | nie awaria; luki 10-05/10-06 10–71 min bez zdarzeń Avasta — przyczyna nieustalona (prawdopodobnie uśpienie) |
| luki: tryb gry Avasta | 2026-10-07 20:03:05, 20:12:58, 20:38:53 | 106 + 142 `\valuebet-odds` w tej samej sekundzie, przed startem sesji; heartbeat 18:03→18:33 UTC (30 min) | powód: **tryb gry Avasta** — mimo informacji Pawła o wyłączeniu trybu gry; decyzja Pawła: nie blokuje prac |
| stan przed wyłączeniem | 2026-10-07 20:55:13 | `schtasks /query /tn valuebet-odds /fo list`: Status **Ready**, Next Run 20:57:53, Logon Mode: Interactive only | ostatni przebieg 20:37:54, wynik 0; heartbeat 18:38:03 UTC `errors = []` |
| wyłączony (T-24h, F0e-05) | 2026-10-07 20:55 | `schtasks /change /tn valuebet-odds /disable` → SUCCESS | zmiany w `ingest/`; reguły uprawnień dodane przez Pawła w `/permissions` |
| włączony | 2026-10-07 21:32:58 | `schtasks /change /tn valuebet-odds /enable` → SUCCESS; `/query`: Status Ready, Next Run 21:37:53 | na starcie sesji było Ready (warunek Pawła); po commicie bramki `75ff3b2` |
| heartbeat po włączeniu | 2026-10-07 21:38:17 (19:38:17 UTC) | `errors = []`, `events_refreshed` ×3, `usage_remaining 497`; przebieg 21:37:54 wynik 0 | warunek §3 etap D spełniony |
| luka: tryb gry Avasta | 2026-10-07 21:42:11 | 106 `\AVAST Software\Gaming mode Task Scheduler recovery` + 142 `\valuebet-odds` w tej samej sekundzie (w trakcie pełnego `pytest`) → Disabled | powód: **tryb gry Avasta**; nie włączane ręcznie (warunek Pawła: nie na ślepo) — Avast przywraca zadanie przy wyjściu z trybu (140/141, np. 21:33:05); stan sprawdzany przed hard stopem |
| powrót z trybu gry + stan przed hard stopem | 2026-10-07 21:47:59 → 21:57:30 | Avast 140/141 o 21:47:59/21:48:00 (zadanie przywrócone bez udziału CLI); `schtasks /query` 21:57:30: **Ready**, Next Run 21:57:53; ostatni przebieg 21:52:54 wynik 0; heartbeat 19:53:08 UTC `errors = []` | luka 21:42–21:48 (tryb gry Avasta) |

## Stan bazowy (etap 0)

- commit: `e6632f7` (agent full-system-auditor — reguły 1–31, linia BRAMKA)
- `uv run pytest`: **541 passed** (188 s)
- `uv run ruff check src tests scripts`: All checks passed!
- `uv run mypy src`: Success: no issues found in 30 source files
- pokrycie (`--cov=src/valuebet`, gałęzie): TOTAL 91%; `pricing/ev.py` 84%,
  `fair.py` 90%, `kelly.py` 92%, `shin.py` 94%; `backtest/lockbox.py` 0%

## Bloki znalezisk

### F-09+F-10 — PRZED

- commit bazowy: `e6632f7`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f10_gitignore.py`
- wynik:

```
E       AssertionError: .coverage nie jest ignorowany przez .gitignore
E       assert 1 == 0
E        +  where 1 = CompletedProcess(args=['git', 'check-ignore', '--no-index', '-q', '.coverage'], returncode=1, stdout='', stderr='').returncode
E       AssertionError: htmlcov/index.html nie jest ignorowany przez .gitignore
E       assert 1 == 0
E        +  where 1 = CompletedProcess(args=['git', 'check-ignore', '--no-index', '-q', 'htmlcov/index.html'], returncode=1, stdout='', stderr='').returncode
E       AssertionError: data/bets/bets.csv nie jest ignorowany przez .gitignore
E       assert 1 == 0
E        +  where 1 = CompletedProcess(args=['git', 'check-ignore', '--no-index', '-q', 'data/bets/bets.csv'], returncode=1, stdout='', stderr='').returncode
E       AssertionError: data/bets/archive/bets_pre_F02.csv nie jest ignorowany przez .gitignore
E       assert 1 == 0
E        +  where 1 = CompletedProcess(args=['git', 'check-ignore', '--no-index', '-q', 'data/bets/archive/bets_pre_F02.csv'], returncode=1, stdout='', stderr='').returncode
...
FAILED tests/regression/test_fsa0_f10_gitignore.py::test_local_state_is_ignored[data/manifest/raw_sha256.jsonl]
FAILED tests/regression/test_fsa0_f10_gitignore.py::test_local_state_is_ignored[config/bookmakers.local.yaml]
FAILED tests/regression/test_fsa0_f10_gitignore.py::test_env_listed_once - As...
9 failed, 3 passed in 1.37s
```

### F-09+F-10 — PO

- commit naprawy: `ce35c67`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f10_gitignore.py`
- wynik:

```
............                                                             [100%]
12 passed in 1.18s
```

### F-14 — PRZED

- commit bazowy: `d19f8e4`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f14_state_outside_raw.py`
- wynik:

```
E       AssertionError: WindowsPath('data/raw/odds/odds_api/state.json')
E       assert not True
E        +  where True = _under_raw(WindowsPath('data/raw/odds/odds_api/state.json'))
E        +    where WindowsPath('data/raw/odds/odds_api/state.json') = OddsCollector(client=<test_fsa0_f14_state_outside_raw._NoClient object at 0x0000023660685BE0>, root=WindowsPath('data/...WindowsPath('data/raw/odds/odds_api/state.json'), heartbeat_file=WindowsPath('data/raw/odds/odds_api/heartbeat.jsonl')).state_file
E       AssertionError: WindowsPath('data/raw/odds/odds_api/heartbeat.jsonl')
E       assert not True
E        +  where True = _under_raw(WindowsPath('data/raw/odds/odds_api/heartbeat.jsonl'))
E        +    where WindowsPath('data/raw/odds/odds_api/heartbeat.jsonl') = OddsCollector(client=<test_fsa0_f14_state_outside_raw._NoClient object at 0x00000236606FD6D0>, root=WindowsPath('data/...WindowsPath('data/raw/odds/odds_api/state.json'), heartbeat_file=WindowsPath('data/raw/odds/odds_api/heartbeat.jsonl')).heartbeat_file
E       AssertionError: assert [WindowsPath(.../state.json')] == []
E         
E         Left contains 2 more items, first extra item: WindowsPath('<user>/AppData/Local/Temp/pytest-of-<user>/pytest-35/test_saving_state_writes_nothi0/data/raw/odds/odds_api/heartbeat.jsonl')
E         Use -v to get more diff
...
FAILED tests/regression/test_fsa0_f14_state_outside_raw.py::test_default_state_file_is_not_under_raw
FAILED tests/regression/test_fsa0_f14_state_outside_raw.py::test_default_heartbeat_is_not_under_raw
FAILED tests/regression/test_fsa0_f14_state_outside_raw.py::test_saving_state_writes_nothing_under_raw
3 failed in 1.06s
```

### F-14 — wyjątek od reguły 12 (jednorazowy, §3 etap A)

Przeniesienie plików stanu z `data/raw/odds/odds_api/` do
`data/state/odds_api/` (nie są danymi surowymi, leżały w raw przez błąd):
kopia (`cp -p`) → zgodność sha256 → usunięcie z raw. Klucze `done` bez zmian.

| plik | sha256 (raw) | sha256 (state) | wynik |
|---|---|---|---|
| `state.json` | `0ae3ecf68b62ac4e9cf86ed5a1d05ca1b0b97c1bf7819ced31df6244306feac1` | identyczny | usunięty z raw |
| `heartbeat.jsonl` | `a184ba27535f4236347817add0e63a4b4b331652f9139a35bb17e21cc9f2b2af` | identyczny | usunięty z raw |

`state.json` zgadza się z prefiksem z FSA #0 §2.1 (`0ae3ecf68b62ac4e`);
`heartbeat.jsonl` urósł od audytu (dopisywane przebiegi do 12:18:49).

### F-12+F-17 — PRZED

- commit bazowy: `b8129c0`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f12_raw_manifest.py tests/regression/test_fsa0_f12_single_raw_writer.py`
- wynik:

```
E       ModuleNotFoundError: No module named 'valuebet.ingest.raw_store'
E       ModuleNotFoundError: No module named 'valuebet.ingest.raw_store'
E       ModuleNotFoundError: No module named 'valuebet.ingest.raw_store'
E       ModuleNotFoundError: No module named 'valuebet.ingest.raw_store'
E       ModuleNotFoundError: No module named 'valuebet.ingest.raw_store'
E       AssertionError: zapis pliku poza rejestrem — jeśli cel jest w data/raw, użyj raw_store.RawStore.write_raw: ['scripts/validate_instrument.py::main::raw_path.write_text', 'src/valuebet/ingest/football_data.py::write_raw::frame.to_parquet', 'src/valuebet/ingest/odds_collector.py::_write_raw::path.write_text']
E       assert ['scripts/val...h.write_text'] == []
E         
E         Left contains 3 more items, first extra item: 'scripts/validate_instrument.py::main::raw_path.write_text'
E         Use -v to get more diff
...
ERROR tests/regression/test_fsa0_f12_raw_manifest.py::test_entry_without_file_is_an_error
ERROR tests/regression/test_fsa0_f12_raw_manifest.py::test_name_is_generated_and_ntfs_safe
FAILED tests/regression/test_fsa0_f12_single_raw_writer.py::test_every_write_site_is_registered_outside_raw
1 failed, 1 passed, 5 errors in 0.88s
```

### F-12 — baseline manifestu (2026-10-02)

`uv run python scripts/verify_raw.py --init-baseline` → 7 plików,
`recorded_by = "baseline-2026-10-02"`. **Integralności sprzed tej daty nie da
się udowodnić** — wpis stwierdza stan z dnia wpisania. Prefiksy sha256
wszystkich siedmiu plików są identyczne z tabelą FSA #0 §2.1 (zmierzoną
2026-10-01), więc od audytu pliki się nie zmieniły.

- kotwica manifestu raw: **7 wierszy**, sha256 wierszy
  `a099c16b0305ca3b4895507182c8a9e216a2e342d4cff7dd83ea784d51f149ec`
- artefakty (`--record-artifacts`, `reports/**/*.parquet`): 2 wiersze
  (`dev_313591a.parquet` `5fa28c66…`, `dev_fb9ec10.parquet` `2d3d1d33…`),
  sha256 wierszy `a32b6be926d5a590ce7f312e7e0f35b0fee0fa135e519ccee0a504541cc5b17f`
- `verify_raw.py` → 0. Adopcji sierot: 0.
- zmiana oczekiwania: `test_write_raw_is_append_only_and_stamped` —
  drugi zapis tych samych bajtów w tej samej chwili dawał drugi plik z
  losowym sufiksem, teraz `FileExistsError` (specyfikacja F-12);
  `test_raw_files_are_never_overwritten` (kolektor) — kolizja wywołana
  realnie powtórzonym zapisem, nie podrzuconym plikiem o starym formacie nazwy.

### F-14 — PO

- commit naprawy: `b8129c0`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f14_state_outside_raw.py`
- wynik:

```
...                                                                      [100%]
3 passed in 1.26s
```

### F-12+F-17 — PO

- commit naprawy: `b9e1045`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f12_raw_manifest.py tests/regression/test_fsa0_f12_single_raw_writer.py`
- wynik:

```
.......                                                                  [100%]
7 passed in 1.61s
```

### R30-meta — PRZED

- commit bazowy: `b9e1045`
- komenda: `uv run pytest -q tests/test_rule30_guards.py`
- wynik:

```
E       AssertionError: nowe naruszenia reguły 30:
E         src/valuebet/backtest/clv.py::clv_rows::as_of::dopuszcza None
E         src/valuebet/backtest/clv.py::clv_rows::as_of::wartość domyślna
E         src/valuebet/backtest/clv.py::clv_rows::bets::pozycyjny
E         src/valuebet/backtest/clv.py::clv_rows::kickoffs::pozycyjny
E         src/valuebet/ingest/football_data.py::parse_matches::now::dopuszcza None
E         src/valuebet/ingest/football_data.py::parse_matches::now::wartość domyślna
E         src/valuebet/ingest/odds_api.py::OddsApiClient.fetch_odds::usage_guard::dopuszcza None
E         src/valuebet/ingest/odds_api.py::OddsApiClient.fetch_odds::usage_guard::wartość domyślna
E         src/valuebet/ingest/odds_collector.py::Anchor.is_due::now::pozycyjny
E         src/valuebet/ingest/odds_collector.py::OddsCollector._write_raw::now::pozycyjny
E         src/valuebet/ingest/odds_collector.py::OddsCollector.refresh_schedule::now::dopuszcza None
...
=========================== short test summary info ===========================
FAILED tests/test_rule30_guards.py::test_guard_params_are_required_keyword_only
FAILED tests/test_rule30_guards.py::test_clock_only_at_entry_points - Asserti...
2 failed, 3 passed in 1.08s
```

### R30-meta — pełna lista naruszeń PRZED (53)

```
src/valuebet/backtest/clv.py::clv_rows::as_of::dopuszcza None
src/valuebet/backtest/clv.py::clv_rows::as_of::wartość domyślna
src/valuebet/backtest/clv.py::clv_rows::bets::pozycyjny
src/valuebet/backtest/clv.py::clv_rows::kickoffs::pozycyjny
src/valuebet/ingest/football_data.py::parse_matches::now::dopuszcza None
src/valuebet/ingest/football_data.py::parse_matches::now::wartość domyślna
src/valuebet/ingest/football_data.py::parse_matches::zegar utcnow
src/valuebet/ingest/football_data_main.py::parse_main_league::zegar datetime.now
src/valuebet/ingest/odds_api.py::OddsApiClient.fetch_odds::usage_guard::dopuszcza None
src/valuebet/ingest/odds_api.py::OddsApiClient.fetch_odds::usage_guard::wartość domyślna
src/valuebet/ingest/odds_collector.py::Anchor.is_due::now::pozycyjny
src/valuebet/ingest/odds_collector.py::OddsCollector._write_raw::now::pozycyjny
src/valuebet/ingest/odds_collector.py::OddsCollector.refresh_schedule::now::dopuszcza None
src/valuebet/ingest/odds_collector.py::OddsCollector.refresh_schedule::now::pozycyjny
src/valuebet/ingest/odds_collector.py::OddsCollector.refresh_schedule::now::wartość domyślna
src/valuebet/ingest/odds_collector.py::OddsCollector.refresh_schedule::zegar datetime.now
src/valuebet/ingest/odds_collector.py::OddsCollector.run_once::now::dopuszcza None
src/valuebet/ingest/odds_collector.py::OddsCollector.run_once::now::pozycyjny
src/valuebet/ingest/odds_collector.py::OddsCollector.run_once::now::wartość domyślna
src/valuebet/ingest/odds_collector.py::OddsCollector.run_once::zegar datetime.now
src/valuebet/ingest/odds_collector.py::decision_due::kickoffs::pozycyjny
src/valuebet/ingest/odds_collector.py::decision_due::now::pozycyjny
src/valuebet/ingest/odds_collector.py::decision_window_utc::now::pozycyjny
src/valuebet/ingest/odds_collector.py::due_calls::kickoffs::pozycyjny
src/valuebet/ingest/odds_collector.py::due_calls::now::pozycyjny
src/valuebet/ingest/raw_store.py::_stamp::now::pozycyjny
src/valuebet/ingest/snapshots.py::RequestBudget.__post_init__::zegar utcnow
src/valuebet/ingest/snapshots.py::_imminent_fixture_ids::now::pozycyjny
src/valuebet/ingest/snapshots.py::collect_once::now::dopuszcza None
src/valuebet/ingest/snapshots.py::collect_once::now::wartość domyślna
src/valuebet/ingest/snapshots.py::collect_once::zegar utcnow
src/valuebet/live/bets.py::BetJournal.settle::zegar datetime.now
src/valuebet/live/digest.py::build_digest::edge_threshold::wartość domyślna
src/valuebet/live/digest.py::send_digest::now::dopuszcza None
src/valuebet/live/digest.py::send_digest::now::wartość domyślna
src/valuebet/live/digest.py::send_digest::zegar datetime.now
src/valuebet/pricing/ev.py::BetclicTaxRegime::bets::pole z wartością domyślną
src/valuebet/pricing/ev.py::double_ev::tax_factor::pozycyjny
src/valuebet/pricing/ev.py::ev::tax_factor::pozycyjny
src/valuebet/pricing/ev.py::evaluate::edge_threshold::pozycyjny
src/valuebet/pricing/ev.py::evaluate::edge_threshold::wartość domyślna
src/valuebet/pricing/ev.py::evaluate::tax_factor::pozycyjny
src/valuebet/pricing/ev.py::min_odds::edge_threshold::pozycyjny
src/valuebet/pricing/ev.py::min_odds::edge_threshold::wartość domyślna
src/valuebet/pricing/ev.py::min_odds::tax_factor::pozycyjny
src/valuebet/pricing/fair.py::fair_prices::kickoffs::dopuszcza None
src/valuebet/pricing/fair.py::fair_prices::kickoffs::wartość domyślna
src/valuebet/pricing/kelly.py::KellyPolicy.from_journal::match_exposure::wartość domyślna
src/valuebet/pricing/kelly.py::KellyPolicy.from_journal::open_exposure::wartość domyślna
src/valuebet/pricing/kelly.py::KellyPolicy.stake::tax_factor::pozycyjny
src/valuebet/pricing/kelly.py::KellyPolicy::match_exposure::pole z wartością domyślną
src/valuebet/pricing/kelly.py::KellyPolicy::open_exposure::pole z wartością domyślną
src/valuebet/pricing/kelly.py::kelly_fraction::tax_factor::pozycyjny
```

### F-05 — PRZED

- commit bazowy: `5814adc`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f05_tax_validation.py`
- wynik:

```
E       Failed: DID NOT RAISE ValueError
E       Failed: DID NOT RAISE ValueError
E       Failed: DID NOT RAISE ValueError
E       ZeroDivisionError: float division by zero
E       Failed: DID NOT RAISE ValueError
E       Failed: DID NOT RAISE ValueError
E       Failed: DID NOT RAISE ValueError
E       Failed: DID NOT RAISE ValueError
E       Failed: DID NOT RAISE ValueError
E       Failed: DID NOT RAISE ValueError
E       Failed: DID NOT RAISE ValueError
E       Failed: DID NOT RAISE ValueError
...
FAILED tests/regression/test_fsa0_f05_tax_validation.py::test_kelly_stake_rejects_tax_outside_domain
FAILED tests/regression/test_fsa0_f05_tax_validation.py::test_edge_threshold_must_be_finite_and_nonnegative[nan]
FAILED tests/regression/test_fsa0_f05_tax_validation.py::test_edge_threshold_must_be_finite_and_nonnegative[inf]
21 failed, 2 passed in 2.31s
```

### F-04 — PRZED

- commit bazowy: `edd9881`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f04_clv_as_of.py`
- wynik:

```
E       Failed: DID NOT RAISE TypeError
E       AssertionError: assert None == 40
E        +  where None = getattr(ClvReport(n_total=40, n_with_clv=40, n_missing=0, mean=-0.010000000000000009, ci_low=-0.010000000000000009, ci_high=-0.010000000000000009, n_clusters=10, note=''), 'n_excluded_future', None)
E       AssertionError: assert 40 == 39
E        +  where 40 = ClvReport(n_total=40, n_with_clv=39, n_missing=1, mean=-0.010000000000000009, ci_low=-0.010000000000000009, ci_high=-0.010000000000000009, n_clusters=10, note='').n_total
E           TypeError: can't compare offset-naive and offset-aware datetimes
...
FAILED tests/regression/test_fsa0_f04_clv_as_of.py::test_future_matches_are_excluded_and_counted
FAILED tests/regression/test_fsa0_f04_clv_as_of.py::test_match_without_kickoff_is_excluded
FAILED tests/regression/test_fsa0_f04_clv_as_of.py::test_naive_as_of_is_rejected
4 failed in 3.15s
```

### A-01 — PRZED

- commit bazowy: `edd9881`
- komenda: `uv run pytest -q tests/regression/test_fsa0_a01_clv_closing_key.py`
- wynik:

```
E       assert None == 0.45 ± 4.5e-07
E         
E         comparison failed
E         Obtained: None
E         Expected: 0.45 ± 4.5e-07
E       AssertionError: assert -0.09999999999999998 is None
E        +  where -0.09999999999999998 = ClvRow(bet_id='a', mode='real', market='h2h', league='nieznana', cluster='2026-W09', clv=-0.09999999999999998, p_close=0.45, reason='').clv
...
=========================== short test summary info ===========================
FAILED tests/regression/test_fsa0_a01_clv_closing_key.py::test_two_bets_on_one_match_get_their_own_closing
FAILED tests/regression/test_fsa0_a01_clv_closing_key.py::test_bare_match_id_key_is_not_a_closing
2 failed in 2.66s
```

### F-05 — PO

- commit naprawy: `edd9881`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f05_tax_validation.py`
- wynik:

```
.......................                                                  [100%]
23 passed in 2.34s
```

### F-04 — PO

- commit naprawy: `48e254e`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f04_clv_as_of.py`
- wynik:

```
....                                                                     [100%]
4 passed in 2.60s
```

### A-01 — PO

- commit naprawy: `48e254e`
- komenda: `uv run pytest -q tests/regression/test_fsa0_a01_clv_closing_key.py`
- wynik:

```
..                                                                       [100%]
2 passed in 2.38s
```

### R30-meta — PO

- commit naprawy: `5814adc`
- komenda: `uv run pytest -q tests/test_rule30_guards.py`
- wynik:

```
.....                                                                    [100%]
5 passed in 1.00s
```

### F-19+F-06 — PRZED

- commit bazowy: `25a62c9`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f19_kelly_gate.py`
- wynik:

```
E       Failed: DID NOT RAISE RuntimeError
E       assert 0.5 <= 0.25
E        +  where 0.5 = KellyPolicy(bankroll=10000.0, peak_bankroll=10000.0, n_real_bets=200, clv_ci_low=0.01, clv_report_unlocks_gk=True, clv_to_ev_ratio=None, open_exposure=0.0, match_exposure=0.0).c
E       AssertionError: assert None is True
E        +  where None = getattr(StakeDecision(fraction=0.00966981132075483, stake=96.7, mode='real', kelly_full=0.01933962264150966, c=0.5, reasons=()), 'gk_would_unlock', None)
E       Failed: DID NOT RAISE TypeError
E       Failed: DID NOT RAISE TypeError
...
FAILED tests/regression/test_fsa0_f19_kelly_gate.py::test_gate_is_reported_not_applied
FAILED tests/regression/test_fsa0_f19_kelly_gate.py::test_open_exposure_cannot_be_omitted
FAILED tests/regression/test_fsa0_f19_kelly_gate.py::test_report_must_be_a_real_clv_report
5 failed, 3 passed in 2.76s
```

### F-19+F-06 — zmiany oczekiwań w istniejących testach (§1 pkt 6)

- `test_half_kelly_requires_the_gk_gate_not_a_flag`,
  `test_regression_clv_report_unlocks_gk_only_with_coverage_and_clusters`:
  po otwartej bramce G-K oczekiwanie `c == 0.5` → `c == 0.25` (zmiana
  specyfikacji, `CLAUDE.md` reguła 21: c = ½ zablokowane do Filaru 3).
  Bramka nadal liczona i asertowana (`gk_passed`, `gk_would_unlock`).
- `test_fraction_never_exceeds_half_kelly` → `..._quarter_before_pillar_three`:
  ta sama ścieżka (raport z CI [0.4, 0.6], 10 000 kuponów), oczekiwanie 0.25.
- `test_clv_correction_shrinks_but_never_inflates` → `test_dead_clv_correction_is_gone`:
  pole `clv_to_ev_ratio` usunięte ze specyfikacją (FSA0_NAPRAWY §3 F-19:
  „usuń `clv_to_ev_ratio` i całą gałąź korekty"); test sprawdza, że pola ani
  argumentu nie ma.
- `test_regression_gk_gate_needs_a_real_clv_report`: konstrukcja wprost →
  `RuntimeError` (wcześniej: konstrukcja wprost z c = 0.25 przy dwóch flagach).
- Wszystkie inne testy Kelly'ego budują politykę przez `from_journal` z
  jawnym kompletem bezpieczników.

### F-20 — PRZED

- commit bazowy: `79db8f7`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f20_fair_kickoffs.py`
- wynik:

```
E       Failed: DID NOT RAISE TypeError
E       AssertionError: assert [FairPrice(ma...733342949092)] == []
E         
E         Left contains 3 more items, first extra item: FairPrice(match_id='m1', market='h2h', outcome='home', p=0.5020518123580504, observed_at=datetime.datetime(2026, 10, 24, 16, 0, tzinfo=datetime.timezone.utc), line=None, source='pinnacle', booksum=1.0286935286935288, z=0.014373733342949092)
E         Use -v to get more diff
E       AssertionError: assert None == 1
E        +  where None = <built-in method get of dict object at 0x000002190A4CC600>('po gwizdku')
E        +    where <built-in method get of dict object at 0x000002190A4CC600> = {}.get
E        +      where {} = getattr([], 'skipped', {})
...
FAILED tests/regression/test_fsa0_f20_fair_kickoffs.py::test_pricing_without_kickoffs_is_refused
FAILED tests/regression/test_fsa0_f20_fair_kickoffs.py::test_match_without_known_kickoff_is_not_priced
FAILED tests/regression/test_fsa0_f20_fair_kickoffs.py::test_live_match_is_not_priced
3 failed, 1 passed in 2.93s
```

### F-20 — zmiany oczekiwań w istniejących testach

`test_regression_pricing_refuses_after_kickoff_when_given_kickoffs` →
`test_regression_pricing_refuses_after_kickoff`: druga asercja utrwalała błąd
(`fair_prices(..., bez kickoffs) != []`, czyli wycena kursu live); teraz
pominięcie `kickoffs` → `TypeError`. Pozostałe testy wyceny dostały jawne
`kickoffs=KO` i czytają `FairPricing.prices`.

### F-01+F-21+W.8 — PRZED

- commit bazowy: `b26f520` (uruchomione w czystym worktree tego commita,
  `valuebet.__file__` w worktree — test zmieniony po pierwszym przebiegu o izolację
  stanu loggerów, asercje bez zmian)
- komenda: `uv run --project ../vb-rewers-f01 pytest -q tests/regression/test_fsa0_f01_lockbox.py`
- wynik:

```
E       Failed: DID NOT RAISE RuntimeError
E       Failed: DID NOT RAISE RuntimeError
E       Failed: DID NOT RAISE RuntimeError
E       Failed: DID NOT RAISE RuntimeError
E       Failed: DID NOT RAISE ValueError
E       Failed: DID NOT RAISE ValueError
E       Failed: DID NOT RAISE ValueError
E       Failed: DID NOT RAISE ValueError
E       Failed: DID NOT RAISE ValueError
E   KeyError: 'season'
E           KeyError: 'season'
E       test_fsa0_f01_lockbox.LockboxViewAttemptedError: run_lockbox sięgnął po dane lockboxa
E       AssertionError: producenci liczb toru M bez assert_no_lockbox: ['scripts/validate_instrument.py', 'src/valuebet/backtest/elo_baseline.py']
E       assert ['scripts/val..._baseline.py'] == []
...
FAILED tests/regression/test_fsa0_f01_lockbox.py::test_unreadable_season_is_an_error[2025/27]
FAILED tests/regression/test_fsa0_f01_lockbox.py::test_unreadable_season_is_an_error[sezon]
FAILED tests/regression/test_fsa0_f01_lockbox.py::test_frame_without_season_is_an_error
FAILED tests/regression/test_fsa0_f01_lockbox.py::test_run_lockbox_refuses_second_view
FAILED tests/regression/test_fsa0_f01_lockbox.py::test_every_tor_m_entry_point_guards_the_lockbox
12 failed, 7 passed in 35.05s
```

### F-19+F-06 — PO

- commit naprawy: `79db8f7`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f19_kelly_gate.py`
- wynik:

```
........                                                                 [100%]
8 passed in 2.96s
```

### F-20 — PO

- commit naprawy: `b26f520`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f20_fair_kickoffs.py`
- wynik:

```
....                                                                     [100%]
4 passed in 1.28s
```

### F-01+F-21+W.8 — PO

- commit naprawy: `85e8fc8`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f01_lockbox.py`
- wynik:

```
...................                                                      [100%]
19 passed in 2.97s
```

### F-25+F-08 — PRZED

- commit bazowy: `25e8f9f`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f25_betclic_regime.py`
- wynik:

```
E       AssertionError: assert 1.0 == 0.94
E        +  where 1.0 = tax_for_single(10.0)
E        +    where tax_for_single = BetclicTaxRegime(now=datetime.datetime(2026, 1, 15, 12, 0, tzinfo=datetime.timezone.utc), bets=[PlacedBet(placed_at=da...time(2026, 1, 8, 12, 9, tzinfo=datetime.timezone.utc), stake=10.0, leg_odds=(2.0,), mode='real', is_settlement=False)]).tax_for_single
E       AssertionError: assert 1.0 == 0.88
E        +  where 1.0 = _tax_multi(BetclicTaxRegime(now=datetime.datetime(2026, 1, 15, 12, 0, tzinfo=datetime.timezone.utc), bets=[]), 50.0, [('m1', 1.5), ('m1', 1.6)])
E       assert False
E        +  where False = any(<generator object test_c_window_is_twelve_calendar_months.<locals>.<genexpr> at 0x0000017CC364E8E0>)
E       AssertionError: assert 1.0 == 0.88
E        +  where 1.0 = _tax_multi(BetclicTaxRegime(now=datetime.datetime(2026, 1, 15, 12, 0, tzinfo=datetime.timezone.utc), bets=[]), 50.0, [('m1', 1.15), ('m2', 1.6)])
E       assert 1.0 != 1.0
E        +  where 1.0 = tax_for_single(100.0)
E        +    where tax_for_single = BetclicTaxRegime(now=datetime.datetime(2026, 1, 15, 12, 0, tzinfo=datetime.timezone.utc), bets=[]).tax_for_single
...
FAILED tests/regression/test_fsa0_f25_betclic_regime.py::test_d_multi_with_short_leg_pays_statutory_tax
FAILED tests/regression/test_fsa0_f25_betclic_regime.py::test_e_unknown_external_turnover_means_threshold_used
FAILED tests/regression/test_fsa0_f25_betclic_regime.py::test_t1_bet_before_promotion_start_is_statutory
6 failed in 0.64s
```

### F-25+F-08 — zmiany w istniejących testach i dokumentach

- Testy reżimu w `test_tor_s.py` przepisane na kupony z nogami i jawny
  `RegimeConfig`. Zmiana oczekiwania wynikająca ze specyfikacji T4 (oba
  udziały ≥ 50%): `test_ako_share_above_half_keeps_singles_tax_free` dostał
  drugi kupon AKO, żeby spełniać też warunek po kuponach (dawny zestaw 900 AKO
  + 200 singiel: po kuponach 1/3 → teraz 0.94, zgodnie z wariantem
  pesymistycznym).
- `test_regression_settlement_rows_do_not_double_count_turnover`: rozliczenie
  nie jest już polem `PlacedBet` (`is_settlement` usunięte) — test idzie przez
  dziennik → `placed_bets_from_journal` → reżim; oczekiwanie bez zmian (500).
- `test_regression_journal_to_placed_bets_skips_settlements`: funkcja
  przejściowa pomija wiersze rozliczeniowe (1 kupon zamiast 2 obiektów, obrót
  bez zmian 100). Zastępuje ją `live.bets.coupons` w F-02.
- `CONTEXT.md` §2: „50% kuponów” → udział stawek (§3 ust. 5) + margines
  Pawła po kuponach.
- `config/bookmakers.yaml` utworzony wg `docs/promocje.md` (wszystkie pola
  `null` → ładowacz live: promocja nieaktywna do weryfikacji regulaminu,
  próg wykorzystany, warunek udziału niespełniony).
- T12: mechanizm (`min_stake_pln`, `excluded_markets`) gotowy, wartości po
  F-25b.

### A-02 — PRZED

- commit bazowy: `62598d0`
- komenda: `uv run pytest -q tests/regression/test_fsa0_a02_winnings_tax.py`
- wynik:

```
E       assert 2500.0 == 2250.0 ± 0.00225
E         
E         comparison failed
E         Obtained: 2500.0
E         Expected: 2250.0 ± 0.00225
E       AssertionError: assert None == 0.9
E        +  where None = getattr(StakeDecision(fraction=0.02, stake=4000.0, mode='real', kelly_full=0.19999999999999996, c=0.25, reasons=('limit na zakład 2%',), gk_would_unlock=False), 'winnings_factor', None)
...
=========================== short test summary info ===========================
FAILED tests/regression/test_fsa0_a02_winnings_tax.py::test_settlement_above_threshold_pays_ninety_percent
FAILED tests/regression/test_fsa0_a02_winnings_tax.py::test_candidate_ev_uses_winnings_factor_at_computed_stake
2 failed, 1 passed in 3.02s
```

### F-25+F-08 — PO

- commit naprawy: `62598d0`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f25_betclic_regime.py`
- wynik:

```
......                                                                   [100%]
6 passed in 0.60s
```

### A-02 — PO

- commit naprawy: `06971e7`
- komenda: `uv run pytest -q tests/regression/test_fsa0_a02_winnings_tax.py`
- wynik:

```
...                                                                      [100%]
3 passed in 2.15s
```

### F-02+F-03+F-31 — PRZED

- commit bazowy: `06971e7`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f02_coupons.py`
- wynik:

```
E       assert 250.0 == 150.0 ± 1.5e-04
E         
E         comparison failed
E         Obtained: 250.0
E         Expected: 150.0 ± 1.5e-04
E       AttributeError: module 'valuebet.live.bets' has no attribute 'coupons'
E       AssertionError: ['src/valuebet/live/bets.py', 'src/valuebet/pricing/ev.py', 'src/valuebet/pricing/ev.py']
E       assert {'src/valuebe...ricing/ev.py'} == {'src/valuebet/pricing/ev.py'}
E         
E         Extra items in the left set:
E         'src/valuebet/live/bets.py'
E         Use -v to get more diff
...
FAILED tests/regression/test_fsa0_f02_coupons.py::test_turnover_has_one_implementation
FAILED tests/regression/test_fsa0_f02_coupons.py::test_journal_carries_provenance
FAILED tests/regression/test_fsa0_f02_coupons.py::test_live_reader_rejects_non_manual_rows
5 failed in 0.90s
```

### F-02+F-03+F-31 — dziennik, zmiany oczekiwań

- Istniejący `data/bets/bets.csv`: **nie istnieje** (katalog `data/bets/`
  nie istnieje) — zero wierszy `real`, nic do archiwizacji, warunek STOP nie
  zachodzi. Nowy dziennik powstanie z nowym nagłówkiem.
- Usunięte `BetJournal.real_turnover` (F-03, wyjątek §1 pkt 6 — bez testów
  własnych) i przejściowe `ev.placed_bets_from_journal`; jedyne źródło kuponów
  to `live.bets.coupons(journal_rows, *, now)`.
- `test_tor_s.py`: `_record` z polami kuponu i proweniencji; testy dziennika
  przez `coupons`; `BetJournal(journal_path=…)`.
- `tests/regression/test_fsa0_f12_single_raw_writer.py`: rejestr miejsc zapisu
  dostał nowe nazwy w `live/bets.py` (`_ensure_header`, `_append` na
  `journal_path`) — cel nadal `data/bets`, poza raw.
- `BetJournal.settle(bet_id, result, *, now)` — rozliczenie nogi; status i
  wypłata kuponu wyprowadzane z wierszy z `settled_at ≤ now`.

### F-26 — PRZED

- commit bazowy: `97b5c60`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f26_http_client.py`
- wynik:

```
E   ModuleNotFoundError: No module named 'valuebet.net'
...
=========================== short test summary info ===========================
ERROR tests/regression/test_fsa0_f26_http_client.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 1.33s
```

### F-26 — uwaga do PRZED

Czerwony PRZED to `ModuleNotFoundError: valuebet.net` — dopuszczalny dla F-26
(„brak modułu”, FSA0_NAPRAWY §1 pkt 2). Migracja: `odds_api` (`OddsApiClient(http=…)`),
`football_data.download(http, url)`, `validate_instrument` (`load_or_fetch`: czyta z raw,
pobiera tylko brakujące), `live/digest.send_digest(…, http=…)`, `collect_odds.py`.
`snapshots.py` (nadal z httpx) wyłączony z testu AST jawnie do F-28 (`PENDING_REMOVAL`).
Pokrycie `net/http.py`: 100%.

### F-15+F-16 — PRZED

- commit bazowy: `a577291`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f15_budget.py`
- wynik:

```
E       AssertionError: 449 + 2 > 450 — kredyt nie może pójść
E       assert not True
E        +  where True = any(<generator object test_call_over_450_is_skipped.<locals>.<genexpr> at 0x0000023964367D30>)
E       AssertionError: zapas 55 < 60 — tylko zamknięcia
E       assert not True
E        +  where True = any(<generator object test_saving_mode_allows_only_closings.<locals>.<genexpr> at 0x00000239643E4930>)
E       AssertionError: nagłówki dostawcy mają trafiać do usage.jsonl
E       assert False
E        +  where False = exists()
E        +    where exists = WindowsPath('<user>/AppData/Local/Temp/pytest-of-<user>/pytest-103/test_credits_spent_comes_from_0/state/usage.jsonl').exists
...
FAILED tests/regression/test_fsa0_f15_budget.py::test_call_over_450_is_skipped
FAILED tests/regression/test_fsa0_f15_budget.py::test_saving_mode_allows_only_closings
FAILED tests/regression/test_fsa0_f15_budget.py::test_credits_spent_comes_from_provider_header
3 failed, 1 passed in 1.84s
```

### F-15+F-16 — zmiany w istniejących testach

- `test_odds_api.py`: progi `should_stop`/`closings_only` (liczone od `remaining`, stop po 490) zastąpione `test_budget_thresholds` dla `UsageGuard` (450, tryb oszczędny < 60); `test_guard_refuses_before_spending`; koszt z `x-requests-last` (F-16) zamiast stałej `CREDITS_PER_ODDS_CALL = 3` (stała usunięta).
- `test_odds_collector.py`: pomocnik odpowiada na bezpłatne `/sports` licznikiem; `test_budget_guard_stops_the_run` — licznik z `/sports` (449), nie ze stanu w pliku.
- `OddsApiSettings.monthly_budget/closings_only_below/stop_below` i `VB_ODDS_MONTHLY_BUDGET` usunięte — budżet jest stałą w kodzie (`MONTHLY_BUDGET`), nie zmienną środowiska.

### F-13 — PRZED

- commit bazowy: `aea5d25`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f13_closings.py`
- wynik:

```
E       AssertionError: zamknięcie przepadło przy luce 30 min: []
E       assert []
E       AssertionError: migawka główna poza [KO-7, KO): [-25]
E       assert False
E        +  where False = all(<generator object test_main_closing_lands_in_last_seven_minutes.<locals>.<genexpr> at 0x000002722BA9FE00>)
E       ImportError: cannot import name 'closing' from 'valuebet' (<user>\Desktop\value-bet\src\valuebet\__init__.py)
...
FAILED tests/regression/test_fsa0_f13_closings.py::test_measured_gap_pattern_still_yields_a_closing
FAILED tests/regression/test_fsa0_f13_closings.py::test_main_closing_lands_in_last_seven_minutes
FAILED tests/regression/test_fsa0_f13_closings.py::test_tolerance_and_target_are_two_constants_in_one_module
3 failed, 1 passed in 1.31s
```

### F-13 — koszt, strata kotwic, zmiany

- `scripts/odds_budget.py` po zmianie kluczy na gwizdek i dodaniu zamknięć zapasowych: **624** kredytów/mies. Ustępstwa w udokumentowanej kolejności: (1) `spreads` Ekstraklasy (TOR_S_PLAN §2 „najpierw”) → 508; (2) zamknięcia zapasowe tylko PL i Bundesliga (FSA0_NAPRAWY §3 F-13) → **430 ≤ 450**. Warunek STOP („nadal > 450”) nie zachodzi.
- Strata kotwic na rzeczywistych przebiegach z 2026-10-01 (14 przebiegów, 255 hipotetycznych gwizdków): stare okno 25 min — złapane 76.5%; nowe `[KO−30, KO)` na tych samych przebiegach — 82.4%. Krok 5 min zamyka luki z kroku harmonogramu; **ryzyko szczątkowe**: komputer uśpiony (Modern Standby) albo wyłączony w porze meczu — diagnoza w `docs/task_scheduler.md`.
- Testy: `test_odds_collector.py` — planowanie przez argumenty nazwane, kotwice zapasowe/główne, migracja kluczy `done`, przegapione zamknięcia, pokrycie; przebiegi Ekstraklasy przesunięte z KO−10 na KO−5 (bez zapasowego). `done` w stanie produkcyjnym był pusty — migracja bez skutków.
- Ustawienia zadania (krok 5 min) — przy włączeniu kolektora (wiersz KOLEKTOR).

### F-02+F-03+F-31 — PO

- commit naprawy: `97b5c60`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f02_coupons.py`
- wynik:

```
.....                                                                    [100%]
5 passed in 0.87s
```

### F-26 — PO

- commit naprawy: `a577291`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f26_http_client.py`
- wynik:

```
........                                                                 [100%]
8 passed in 2.56s
```

### F-15+F-16 — PO

- commit naprawy: `aea5d25`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f15_budget.py`
- wynik:

```
....                                                                     [100%]
4 passed in 1.49s
```

### F-13 — PO

- commit naprawy: `8171848`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f13_closings.py`
- wynik:

```
....                                                                     [100%]
4 passed in 0.94s
```

### F-25b — regulamin Betclica

- 2026-10-02: `uv run python scripts/fetch_betclic_tc.py` → `robots.txt dam.begmedia.com: HTTP 403 — nie wiadomo, czy wolno; nie pobieram` (rc=3). PDF niepobrany, zero zapisów do raw.
- Status: **niezweryfikowane** (`docs/promocje.md`). Cytaty pozostają wstępne; rozbieżności regulaminu względem promocje.md nie da się dziś stwierdzić. Kod bez zmian (weryfikacja i tak mogłaby go tylko zaostrzyć). Filar 1 może ruszyć — strategia C z flagą „na niezweryfikowanym regulaminie”.
- Dla Pawła: ręczne pobranie PDF do `data/raw/tc/betclic/` + `verify_raw.py --adopt-orphan`.

### F-24 — PRZED

- commit bazowy: `b990d07`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f24_provenance.py`
- wynik:

```
E   ModuleNotFoundError: No module named 'valuebet.provenance'
...
=========================== short test summary info ===========================
ERROR tests/regression/test_fsa0_f24_provenance.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.59s
```

### F-28+R29 — PRZED

- commit bazowy: `d7f66b7`
- komenda: `uv run pytest -q tests/test_rule29_wiring.py`
- wynik:

```
E       AssertionError: moduły bez ścieżki od punktu wejścia — podłącz albo wpisz do DORMANT/PENDING_WIRING i ROADMAP §2: ['valuebet.backtest.clv', 'valuebet.config', 'valuebet.features.base', 'valuebet.live.bets', 'valuebet.live.digest', 'valuebet.pricing.ev', 'valuebet.pricing.fair', 'valuebet.pricing.kelly']
E       assert ['valuebet.ba...cing.ev', ...] == []
E         
E         Left contains 8 more items, first extra item: 'valuebet.backtest.clv'
E         Use -v to get more diff
...
tests\test_rule29_wiring.py:98: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_rule29_wiring.py::test_every_module_is_reachable_or_listed
1 failed, 2 passed in 0.83s
```

### F-28+R29 — usunięcia i listy

- Usunięte `src/valuebet/ingest/snapshots.py` i `tests/test_snapshots.py` (wyjątek §1 pkt 6: testy usuwanego modułu; historia w gicie). Wpisy F-28 zniknęły z `KNOWN_VIOLATIONS`, z `PENDING_REMOVAL` w teście F-26 i z rejestru zapisów w teście F-12.
- `tests/test_rule29_wiring.py`: `DORMANT = {features.base}`, `PENDING_WIRING` = fair, ev, kelly, bets, clv, config (Filar 1), digest (Filar 2); każdy z wierszem w `ROADMAP.md` §2 (wiersz „Moduły toru S” uzupełniony ścieżkami).
- `KNOWN_VIOLATIONS` w `test_rule30_guards.py`: **pusta** (warunek §4).
- F-24, uwaga dodatkowa: poza `lockbox_3433f2c.json` także `diag_313591a.json` i `m2_313591a.json` mają etykietę commita, w którego drzewie nie ma generującego skryptu (dodane w `3e69a51` i `0208f64`) — obie dostały PROVENANCE; FSA #0 uznał je za wiarygodne, nie sprawdzając drzewa.

### F-32 — PRZED

- commit bazowy: `3cdacf7`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f32_context_audits.py`
- wynik:

```
E       AssertionError: assert ['AUDIT_REPOR...-10-01_F0.md'] == []
E         
E         Left contains 2 more items, first extra item: 'AUDIT_REPORT_2.md'
E         Use -v to get more diff
...
tests\regression\test_fsa0_f32_context_audits.py:36: AssertionError
=========================== short test summary info ===========================
FAILED tests/regression/test_fsa0_f32_context_audits.py::test_every_audit_is_referenced_in_section_five
1 failed, 2 passed in 0.79s
```

### A-03 — PRZED

- commit bazowy: `33fba89`
- komenda: `uv run pytest -q tests/regression/test_fsa0_a03_shin_fallback.py`
- wynik:

```
E       AssertionError: assert not True
E        +  where True = <function allclose at 0x000001CC3BE222F0>(array([0.40677966, 0.33898305, 0.25423729]), (array([0.4       , 0.33333333, 0.25      ]) / np.float64(0.9833333333333334)), equal_nan=False)
E        +    where <function allclose at 0x000001CC3BE222F0> = np.allclose
E        +    and   array([0.40677966, 0.33898305, 0.25423729]) = ShinResult(probabilities=array([0.40677966, 0.33898305, 0.25423729]), z=0.0, booksum=0.9833333333333334, iterations=0, converged=False, method='proportional').probabilities
E        +    and   np.float64(0.9833333333333334) = <built-in method sum of numpy.ndarray object at 0x000001CC4BBC2550>()
E        +      where <built-in method sum of numpy.ndarray object at 0x000001CC4BBC2550> = array([0.4       , 0.33333333, 0.25      ]).sum
E       Failed: DID NOT RAISE ValueError
...
=========================== short test summary info ===========================
FAILED tests/regression/test_fsa0_a03_shin_fallback.py::test_failed_fit_is_not_proportional_normalisation
FAILED tests/regression/test_fsa0_a03_shin_fallback.py::test_strict_variant_raises
2 failed in 1.38s
```

### DROBNE (F-07,F-11,F-18,F-22,F-30) — PRZED

- commit bazowy: `f12703c`
- komenda: `uv run pytest -q tests/regression/test_fsa0_minor.py`
- wynik:

```
E           AssertionError: punkt wejścia valuebet.cli:main wskazuje nieistniejący moduł
E           assert False
E            +  where False = is_file()
E            +    where is_file = WindowsPath('<user>/Desktop/value-bet/src/valuebet/cli.py').is_file
E       AssertionError: assert 'structlog' not in 'numpy>=2.1 ...yyaml>=6.0.3'
E         
E         'structlog' is contained here:
E           uzz>=3.10 structlog>=24.4 pyyaml>=6.0.3
E         ?           +++++++++
E       AssertionError: assert {'VB_TELEGRAM...LEGRAM_TOKEN'} == set()
E         
E         Extra items in the left set:
...
FAILED tests/regression/test_fsa0_minor.py::test_f18_h2h_is_ordered_first - A...
FAILED tests/regression/test_fsa0_minor.py::test_f22_verdict_needs_eight_clusters
FAILED tests/regression/test_fsa0_minor.py::test_f30_layout_names_every_module
6 failed in 2.47s
```

### DROBNE (F-07, F-11, F-18, F-22, F-27, F-29, F-30)

- F-07: `[project.scripts] vb = valuebet.cli:main` usunięte.
- F-11: `uv remove structlog pydantic-settings` (grep: zero użyć); `.env.example` — tylko zmienne czytane przez kod (`VB_ODDS_API_KEY`, `VB_ODDS_SPORT`, `VB_TELEGRAM_TOKEN`, `VB_TELEGRAM_CHAT_ID`), bez wartości; usunięte nieużywane `VB_API_FOOTBALL_KEY`, `VB_LEAGUES`, `VB_SEASON`, `VB_DAILY_BUDGET`, `VB_SNAPSHOTS_DIR`, `VB_ODDS_MONTHLY_BUDGET`. Plik `.env` nietknięty.
- F-18: `digest.MARKET_ORDER` z nazwami kanonicznymi i `h2h` na początku.
- F-22: `clv.MIN_CLUSTERS_RELIABLE = 8` dla `beats_closing`, `unlocks_gk`, `describe`; od 5 klastrów CI tylko liczone, z adnotacją „poniżej progu wiarygodności”. Zmiana oczekiwania w `test_regression_clv_report_unlocks_gk_only_with_coverage_and_clusters` (5 klastrów: `beats_closing` True → False).
- F-27 (tekstowe, dowód = diff): docstring `digest.py` — token w ścieżce URL, redakcja przez `net/http.py`.
- F-29 (tekstowe): `ROADMAP.md` §2 mówi już „`docs/discovery/` — jeden plik z adresem” (poprawione przez Architekta; sprawdzone).
- F-30: sekcja „Układ” w `CLAUDE.md` wymienia wszystkie 28 modułów z ich stanem podłączenia; test `test_f30_layout_names_every_module`.

### F-23+W.10 — PRZED

- commit bazowy: `2b61e31`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f23_instrument_verdict.py`
- wynik:

```
E       AssertionError: brak funkcji werdyktu — werdykt nie wynika z liczb
E       assert None is not None
E       AssertionError: brak funkcji werdyktu — werdykt nie wynika z liczb
E       assert None is not None
E       AssertionError: brak funkcji werdyktu — werdykt nie wynika z liczb
E       assert None is not None
E       AssertionError: brak funkcji werdyktu — werdykt nie wynika z liczb
E       assert None is not None
E       AssertionError: brak funkcji werdyktu — werdykt nie wynika z liczb
E       assert None is not None
E       AssertionError: assert False
E        +  where False = is_file()
...
FAILED tests/regression/test_fsa0_f23_instrument_verdict.py::test_verdict_follows_numbers[ci3-6-niewiarygodny statystycznie]
FAILED tests/regression/test_fsa0_f23_instrument_verdict.py::test_verdict_follows_numbers[ci4-3-niewiarygodny statystycznie]
FAILED tests/regression/test_fsa0_f23_instrument_verdict.py::test_old_report_has_a_note
6 failed in 2.76s
```

### F-24 — PO

- commit naprawy: `d7f66b7`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f24_provenance.py`
- wynik:

```
...                                                                      [100%]
3 passed in 2.36s
```

### F-28+R29 — PO

- commit naprawy: `3cdacf7`
- komenda: `uv run pytest -q tests/test_rule29_wiring.py`
- wynik:

```
...                                                                      [100%]
3 passed in 0.81s
```

### F-32 — PO

- commit naprawy: `33fba89`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f32_context_audits.py`
- wynik:

```
...                                                                      [100%]
3 passed in 0.39s
```

### A-03 — PO

- commit naprawy: `f12703c`
- komenda: `uv run pytest -q tests/regression/test_fsa0_a03_shin_fallback.py`
- wynik:

```
..                                                                       [100%]
2 passed in 1.17s
```

### F-23+W.10 — PO

- commit naprawy: `aba1199`
- komenda: `uv run pytest -q tests/regression/test_fsa0_f23_instrument_verdict.py`
- wynik:

```
......                                                                   [100%]
6 passed in 2.41s
```

### DROBNE (F-07,F-11,F-18,F-22,F-30) — PO

- commit naprawy: `2b61e31`
- komenda: `uv run pytest -q tests/regression/test_fsa0_minor.py`
- wynik:

```
......                                                                   [100%]
6 passed in 3.21s
```

### R30-meta — PO

- commit naprawy: `3cdacf7`
- komenda: `uv run pytest -q tests/test_rule30_guards.py`
- wynik:

```
.....                                                                    [100%]
5 passed in 1.18s
```

## Etap F — weryfikacja całości (§4), 2026-10-02

- `uv run pytest -q`: **768 passed** (183.8 s, z pokryciem).
- `uv run pytest -k future_poison`: 10 passed.
- `uv run ruff check src tests scripts`: All checks passed!
- `uv run mypy src` (strict): Success: no issues found in 36 source files.
- `KNOWN_VIOLATIONS` w `tests/test_rule30_guards.py`: **puste**; `GUARD_PARAMS`
  bez zmian względem listy z §3 etap B (test `test_guard_list_only_grows`).
- Pokrycie (linie+gałęzie): `backtest/lockbox.py` **100%**; `pricing/`: `ev.py`
  95%, `fair.py` 92%, `kelly.py` 90%, `shin.py` 95%; `net/http.py` **100%**,
  `ingest/raw_store.py` **97%** (po teście `latest`), `provenance.py` **100%**;
  TOTAL 93%.
- `scripts/verify_raw.py` → **0**; manifest raw 7 wierszy, sha256 wierszy
  `a099c16b0305ca3b4895507182c8a9e216a2e342d4cff7dd83ea784d51f149ec`;
  artefakty 2 wiersze, `a32b6be926d5a590ce7f312e7e0f35b0fee0fa135e519ccee0a504541cc5b17f`.
  Adopcji sierot: 0.
- Skan historii gita pod sekrety (307 blobów, liczby trafień): wzorzec
  „klucz + wartość ≥ 16 zn.” — 4 (wszystkie fałszywe: atrapa w
  `tests/test_odds_api.py`, długość 24, oraz puste pola `…KEY=`/`…TOKEN=` w
  `.env.example`, gdzie wzorzec przeskoczył przez znak nowej linii);
  `apiKey=` w URL — 0; token Telegrama — 0; AWS — 0; klucz prywatny — 0;
  prawdziwy `VB_ODDS_API_KEY` (32 zn.) w historii — **0**; `.env` nieśledzony.
- **Rewers** (§1, procedura: `git worktree add` na commicie PRZED, `uv sync`, kopia testu + `tests/conftest.py` + `tests/helpers/`, `valuebet.__file__` w worktree — sprawdzone w każdym przebiegu): wszystkie 18 pozycji POWAŻNYCH oraz A-01, A-02 **czerwone** z powodu zachowania (asercja / DID NOT RAISE); F-12, F-26, F-24 — „brak modułu” (dopuszczalne, §1 pkt 2). Uwaga do F-28: czerwień w rewersie pochodzi z testu zgodności list z ROADMAP §2 (na starym drzewie moduły toru S nie miały wiersza z Filarem); `snapshots.py` był wtedy osiągalny tylko przez własny blok `__main__`. Worktree usunięte po zapisie.
- `git status`: czysty po commicie tego wpisu.

## STOP przed etapem G (2026-10-02)

Agent `full-system-auditor` **zniknął z listy dostępnych agentów** w trakcie
sesji (był dostępny w etapie 0). FSA0_NAPRAWY §3 etap 0: bez agenta → STOP z
prośbą o restart CLI, bez zastępowania go agentem ogólnym. Etapy 0, A–F
zakończone; KOLEKTOR włączony i zdrowy.

**Wznowienie (nowa sesja po restarcie CLI):** sprawdzić, że
`full-system-auditor` jest na liście agentów; `git status` czysty; uruchomić
FSA #0b ze zleceniem z `docs/FSA0_NAPRAWY.md` §5 wklejonym dosłownie; potem
bramka §6 (akceptacja Pawła z §0 zacytowana na górze tego pliku) i Filar 1
wg §7. Nic z etapów A–F nie wymaga powtórzenia.

## STOP #2 przed etapem G (2026-10-03)

Po restarcie CLI agent `full-system-auditor` nadal niedostępny. Przyczyna
ustalona: edycja z etapu 0 (`e6632f7`) zapisała plik agenta z końcami linii
CRLF, a `description` zawierał niecytowany dwukropek („backtest-auditor:
obejmuje”) — frontmatter YAML przestał się parsować (`mapping values are not
allowed here`). Naprawione w `7cbad3e` (LF, opis w cudzysłowie; YAML parsuje
się do `name, description, tools, model`). Definicje agentów wczytuje start
sesji — potrzebny **jeszcze jeden restart CLI**, potem etap G od zera (zlecenie
§5 dosłownie). Etapy 0, A–F bez zmian; kolektor zdrowy (heartbeat
2026-10-03 12:21:52 UTC, `errors = []`).

## Etap G — FSA #0b (2026-10-03)

Raport audytora: `reports/audit/FSA_2026-10-02_F0b.md` (commit `5580d9f`,
nieedytowany). Ostatnia linia: `BRAMKA: KRYT=0 POWAŻNE=3 OTWARTE=[F0b-01,
F0b-02, F0b-03]` → bramka §6 niespełniona; naprawy wg §1, potem FSA #0c (§5).
DROBNE F0b-04…F0b-13 zostają otwarte (protokół §5 liczy tylko KRYT/POWAŻNE).

### F0b-03 — PRZED

- commit bazowy: `5580d9f`
- komenda: `uv run pytest -q tests/regression/test_fsa0b_03_journal_tax_factor.py`
- wynik:

```
E       Failed: DID NOT RAISE ValueError        (×10)
10 failed in 2.50s
```

### F0b-03 — PO

- commit naprawy: `fe8d8cd` — `validate_tax_factor` w `BetRecord.__post_init__` i w `clv_rows`
- wynik: `10 passed in 15.91s`

### F0b-02 — PRZED

- commit bazowy: `fe8d8cd`
- komenda: `uv run pytest -q tests/regression/test_fsa0b_02_t12_market.py`
- wynik:

```
E       AssertionError: assert 1.0 == 0.88
E        +  where 1.0 = build(tax_for_single, 100.0, market='spreads')
E       Failed: DID NOT RAISE any of (TypeError, ValueError)
E       Failed: DID NOT RAISE ValueError
E       AssertionError: assert 1.0 == 0.88      (×4, ładowacz: T12 null / brak kluczy)
7 failed in 0.98s
```

### F0b-02 — PO

- commit naprawy: `a28ad51` — `CouponLeg.market` wymagany i niepusty;
  `tax_for_single(stake, *, market)`; ładowacz: brak `min_stake_pln` albo
  `excluded_markets` → promocja nieaktywna (0.88), jawne `[]` = żaden rynek
  wyłączony; `config/bookmakers.yaml`: `excluded_markets: null`.
- dostosowane testy (nowa wymagana sygnatura, **asercje bez zmian**):
  `test_betclic_regime.py`, `test_tor_s.py` — dopisany `market="h2h"`, fixture
  `_yaml` uzupełniona o klucze T12; `test_fsa0_f25_betclic_regime.py` — nogi i
  `tax_for_single` przez `helpers.build` (rewers F-25 nadal działa na starych
  commitach).
- wynik: `7 passed in 0.45s`

### F0b-01 — PRZED

- commit bazowy: `a28ad51`
- komenda: `uv run pytest -q tests/regression/test_fsa0b_01_closing_coverage.py`
- wynik:

```
E       AssertionError: przegapione A zniknęło z mianownika
E       assert (1, 1) == (1, 2)
E       assert (2, 2) == (2, 3)
FAILED ...::test_coverage_counts_the_missed_match
FAILED ...::test_coverage_survives_later_calls
2 failed, 1 passed in 2.16s
```

Zielony przed naprawą: `test_closing_for_b_was_collected_and_a_was_missed` —
warunek sceny (B zebrane, A przegapione), nie dowód naprawy.

### F0b-01 — PO

- commit naprawy: `2b681b4` — stan trzyma `kickoffs_seen` (35 dni),
  utrwalane po wczytaniu stanu (przed `/odds`) i przed zapisem;
  `closing_coverage` i `_record_missed` liczą z `known_kickoffs`. Mecz
  przełożony zostaje ze starym terminem = przegapione (pokrycie zaniżone, nie
  zawyżone). Kolektor live po zmianie: `kickoffs_seen` w stanie, `errors = []`.
- wynik: `3 passed in 2.09s`

### Rewers (§1) i weryfikacja

Worktree na commicie PRZED każdej naprawy, `uv sync`, skopiowane test +
`tests/helpers/`, `uv run --project <worktree>`; `assert_from_checkout`
przeszło w każdym przebiegu. Wyniki w kolumnie `rewers`. Worktree usunięte
(`git worktree list` → tylko master).

Na `2b681b4`: `uv run pytest` — 789 passed; `ruff check src tests scripts` —
czysto; `mypy src` (strict) — czysto; `verify_raw.py` — OK (7 wierszy,
`a099c16b…f149ec`).

## Etap G, runda 0c — FSA #0c (2026-10-03)

Raport audytora: `reports/audit/FSA_2026-10-03_F0c.md` (commit `32fac6e`,
nieedytowany). Ostatnia linia: `BRAMKA: KRYT=0 POWAŻNE=3 OTWARTE=[F0c-01,
F0c-02, F0c-03]` → naprawy wg §1, potem FSA #0d — **ostatnia dopuszczalna
runda** (§5). Uwaga audytora wzięta do serca: naprawy F0b zamknęły ścieżkę z
reprodukcji, nie klasę błędu. Runda 0c celuje w klasę: jeden słownik rynków
(nie tylko „napis zamiast listy”), jednostka miary = mecz z kursem (nie tylko
krotność slotu), sonda dla każdej ligi bez przyszłego gwizdka (nie tylko
przerwa zimowa).

### F0c-03 — PRZED

- commit bazowy: `32fac6e`
- komenda: `uv run pytest -q tests/regression/test_fsa0c_03_t12_vocabulary.py`
- wynik:

```
E       Failed: DID NOT RAISE ValueError                 (×7: napis, mapa, nazwa z regulaminu, literówka, bool)
E       Failed: DID NOT RAISE any of (TypeError, ValueError)   (RegimeConfig z napisem)
E       AssertionError: assert 1.0 == 0.88                (×5: spreads≢asian_handicap, totals≢over_under, h2h≢1x2)
E       AssertionError: Regex pattern did not match.     („5 zł”: ValueError bez nazwy pola)
14 failed, 1 passed in 0.79s
```

Zielony przed naprawą: `min_stake_pln: -1` — odrzucał już `RegimeConfig`.

### F0c-03 — PO

- commit naprawy: `72d77d6` — `schema.canonical_market` (`MarketType` +
  klucze The Odds API: `h2h`, `totals`, `spreads`); `CouponLeg`, `BetRecord`,
  `RegimeConfig`, ładowacz odrzucają napis zamiast listy, nazwę spoza słownika,
  `bool`/napis jako stawkę; wyłączenia porównywane na kluczach kanonicznych.
  Polskie nazwy z regulaminu celowo **nie** są aliasami — przepisuje je
  człowiek; komentarz w `config/bookmakers.yaml` wymienia klucze.
- wynik: `15 passed in 0.87s`

### F0c-01+F0c-04 — PRZED

- commit bazowy: `72d77d6`
- komenda: `uv run pytest -q tests/regression/test_fsa0c_01_coverage_per_match.py`
- wynik:

```
E       AssertionError: pięć meczów slotu liczonych jako jeden
E       assert (1, 2) == (1, 6)                          (×2: z migawką decyzyjną i ze starego stanu)
E       AssertionError: zamknięcie bez kursu Pinnacle liczone jako zebrane
E       assert (1, 1) == (0, 1)                          (×2: bez Pinnacle, bez meczu w odpowiedzi)
4 failed
```

### F0c-02 — PRZED

- commit bazowy: `72d77d6`
- komenda: `uv run pytest -q tests/regression/test_fsa0c_02_schedule_stall.py`
- wynik:

```
E       AssertionError: zero wywołań PL po ostatnim znanym meczu — kolektor zamilkł
E       AssertionError: 0   assert 1 <= 0
E       assert 'premier_league' in []                    (heartbeat bez schedule_empty)
3 failed
```

### F0c-01+F0c-04, F0c-02 — PO

- commit naprawy: `ff682fb` (jedna łatka w `odds_collector.py`, dwa testy):
  - `events_seen` (id zdarzenia → gwizdek, 35 dni) zastępuje `kickoffs_seen`;
    stan bez identyfikatorów migrowany z krotności terminarza jako `legacy:`
    (niezebrane — kierunek ostrożny), wypierany przez prawdziwe zdarzenia;
  - `closing_events`: zebrane = odpowiedź zamknięcia głównego zawiera mecz o
    tym gwizdku z kompletem h2h Pinnacle (≥ 3 kursy > 1.0);
  - `schedule_probes`: liga bez znanego przyszłego gwizdka → `/odds` h2h
    (1 kredyt) raz na dobę warszawską, przez `UsageGuard` (tryb oszczędny
    pomija); heartbeat ma pole `schedule_empty`. Koszt górny: 1 kredyt/dobę
    na ligę z pustym terminarzem (przerwa zimowa ~6–8 tyg. ≈ 50 kredytów na
    ligę, w miesiącach bez kotwic).
- dostosowane testy (**oczekiwane wartości bez zmian**):
  `test_odds_collector.py` — fixture `_event` z kursem h2h Pinnacle; dwa testy
  „spokojnego przebiegu” dostają odległy mecz w każdej lidze (inaczej
  odpala sonda — to jest naprawa F0c-02); `test_weekly_closing_coverage`
  przez prawdziwy `run_once` zamiast ręcznego stanu, oczekiwanie `(1, 2)`
  bez zmian; `test_fsa0b_01_closing_coverage.py` — fixture z kursem Pinnacle.
  Pomocnik sceny w `tests/helpers/collector_scene.py` (kopiowany w rewersie).
- żywy kolektor po zmianie: heartbeat `schedule_empty: []`, `errors = []`;
  wszystkie trzy ligi mają przyszłe mecze, sonda nie odpala.
- wynik: `4 passed in 2.16s`, `3 passed in 58.58s`

### F0c-05 (DROBNE, tekstowe)

- `6a71b1e` — wiersz F0 w `ROADMAP.md` §0 z wynikami FSA #0b i #0c. Dowód: diff.

### Otwarte DROBNE

F0b-04, F0b-05, F0b-07…F0b-13 — bez zmian w tej rundzie (§5 liczy KRYT/POWAŻNE).

### Rewers (§1) i weryfikacja

Worktree na commicie PRZED, `uv sync`, skopiowane test + `tests/helpers/`,
`uv run --project <worktree>`; `assert_from_checkout` przeszło. Wyniki w
kolumnie `rewers`; katalogi usunięte, `git worktree list` → tylko master.

Na `ff682fb`: `uv run pytest` — 811 passed; `-k future_poison` — 10 passed;
`ruff check src tests scripts` — czysto; `mypy src` (strict) — czysto;
`verify_raw.py` — OK.

## STOP po FSA #0d (2026-10-03) — limit rund z §5 wyczerpany

Raport: `reports/audit/FSA_2026-10-03_F0d.md` (audytowany `6e6d2f7`,
nieedytowany). Ostatnia linia: `BRAMKA: KRYT=0 POWAŻNE=1 OTWARTE=[F0d-01]`.
Bramka §6 niespełniona (pkt 1). Warunek akceptacji Pawła z 2026-10-02 11:33
(„Jeśli testy i audyt dadzą zielone światło…”) **niespełniony** — Filar 1 nie
startuje. Rundy 0c i 0d wykorzystane; dalsze naprawy i ewentualna runda 0e
wyłącznie po decyzji Pawła.

- F0d-01 (POWAŻNE, kolektor): sonda terminarza wyłączona, gdy liga zna
  jakikolwiek przyszły gwizdek — jeden odległy mecz przywraca zastój F0c-02.
  Niezaczęte (czeka na decyzję).
- DROBNE otwarte: F0d-02…F0d-06, F0b-04, F0b-05, F0b-07…F0b-13.
- Kod wyceny, podatku, CLV i dziennika: bez otwartych KRYT/POWAŻNYCH (audytor).
- Kolektor zdrowy (heartbeat co 5 min, `errors = []`, `schedule_empty: []`).

## Runda 0e — decyzja Pawła (2026-10-03), dosłownie

> Decyzja Pawła (2026-10-03): zgoda na JEDNĄ dodatkową rundę FSA #0e, ponad limit z docs/FSA0_NAPRAWY.md §5. Zapisz ją dosłownie w FIX_LOG_F0.md i jako dopisek w §5. Rundy #0f nie ma: po #0e każde otwarte KRYT/POWAŻNE → STOP.
>
> Odrzucam propozycję „sonda gdy brak meczu w N dniach” — to kolejna heurystyka. Usuwamy przyczynę wskazaną przez audytora trzeci raz: terminarz kolektora żyje z odpowiedzi płatnych wywołań.
>
> 0. Kolektor: na czas zmian w ingest/ wyłącz valuebet-odds (wiersz KOLEKTOR), po zmianach włącz z kontrolą heartbeatu jak w §3 etap D (15 min, errors=[]). Dopisz do §8 dozwolone prawdziwe zapytanie: GET /v4/sports/{sport}/events.
>
> 1. F0d-01 (POWAŻNE) — terminarz wyłącznie z bezpłatnego /events:
>    - Dokumentacja v4: /events „does not count against the usage quota”. Pierwsze prawdziwe wywołanie po włączeniu kolektora musi mieć x-requests-last = 0 — inaczej wyłącz zadanie i STOP.
>    - Terminarz każdej ligi odświeżany BEZWARUNKOWO z /events, gdy ostatnie udane odświeżenie jest starsze niż 60 min (przez net/http.py, throttling bez zmian). Płatna sonda usunięta w całości, bez warunków typu „brak przyszłego meczu”.
>    - /events jest jedynym źródłem terminarza i mianownika pokrycia (events_seen); płatne odpowiedzi go nie zasilają. Budżet i tryb oszczędny nie dotyczą /events.
>    - closing_events kluczowane (id, kickoff); zamknięcie liczy się tylko dla bieżącego gwizdka (F0d-03).
>    - Przed każdym płatnym wywołaniem: wolne miejsce na dysku ≥ 200 MB, inaczej pominięcie z błędem w heartbeacie (F0d-05).
>    - Odpowiedź zamknięcia bez rynku Pinnacle → closing_missed z powodem „brak rynku Pinnacle”, raportowane osobno od luk kolektora.
>    - F0d-02, F0b-08 (odds_budget.py), F0b-09 zamykasz z konstrukcji — każde z dowodem w logu.
>
> 2. Test niezmiennika zamiast testu sceny: generator scenariuszy z ziarnem, ≥ 500 scenariuszy (odległe mecze, dziury w terminarzu, przełożenia, mecz wystawiony późno, zmiana godziny gwizdka, tryb oszczędny, przerwy w pracy komputera, błąd zapisu), prawdziwy run_once na fałszywym zegarze i transporcie. Niezmiennik: każdy mecz, który /events listował ≥ 60 min przed gwizdkiem, kończy się zamknięciem w [KO−30, KO] albo wpisem closing_missed z powodem z zamkniętej listy (komputer nie działał, budżet > 450, brak rynku Pinnacle, brak miejsca / błąd zapisu). Na dzisiejszym kodzie test MUSI znaleźć kontrprzykład — PRZED w logu. Bez nowej zależności; hypothesis tylko jako zależność dev z uzasadnieniem.
>
> 3. F0d-04: nazwy rynków kanonizowane przez MARKET_ALIASES na granicy dziennika; wewnątrz systemu jedna nazwa, clv.py porównuje kanoniczne. Test czerwony → zielony. F0d-06: docs/task_scheduler.md i komentarz w schema.py.
>
> 4. Protokół bez zmian (§1: czerwony → zielony, rewers, commit na pozycję, git add z jawnymi ścieżkami). Potem §4 i FSA #0e: zlecenie z §5 dosłownie, wejście poszerzone o raporty #0b, #0c, #0d, nowe znaleziska F0e-xx, raport reports/audit/FSA_<data>_F0e.md.
>
> 5. BRAMKA KRYT=0 POWAŻNE=0 → bramka wg §6 i Filar 1 wg §7 automatycznie (moja warunkowa akceptacja z 2026-10-02 obowiązuje). Inaczej STOP. Pozostałe DROBNE (F0b-04, F0b-05, F0b-07, F0b-10…F0b-13) mogą zostać otwarte z wpisem w raporcie.
>
> Raport końcowy: koszt /events z nagłówka, wynik testu niezmiennika przed i po (kontrprzykład z PRZED), linia BRAMKA z #0e, a jeśli Filar 1 ruszył — gdzie się zatrzymał.

## Etap G, runda 0e — naprawy (2026-10-03)

### F0d-01 — test niezmiennika (decyzja pkt 2)

`tests/helpers/collector_sim.py` + `tests/regression/test_fsa0e_collector_invariant.py`:
500 światów z ziarnem (`random.Random(seed)`, bez nowej zależności), 10 partii po
50, pula 8 procesów. Rodzaje światów (sprawdzane osobnym testem, że generator je
produkuje): odległe mecze, dziura w terminarzu (56–80 h), przełożenia, wystawiony
późno / za późno, ten sam gwizdek, tryb oszczędny, wyczerpany budżet, przerwy
komputera, mało miejsca, błąd zapisu. Prawdziwy `run_once` co 5 min fałszywego
zegara, fałszywy transport (`/events`, `/odds`, `/sports`). Wyrocznia nie czyta
stanu kolektora: zamknięcie = płatna odpowiedź w [KO-30, KO] z meczem i kompletem
h2h Pinnacle, zapisana do raw; inaczej wpis `closing_missed` z powodem z listy,
**prawdziwym w tym świecie** (komputer nie działał ⇔ opuszczony przebieg w
[KO-67, KO); budżet ⇔ used + koszt > 450 w [KO-30, KO); brak Pinnacle ⇔ świat bez
Pinnacle; miejsce/zapis ⇔ okno awarii w [KO-30, KO)). `os.fsync` wyłączony w
symulacji (trwałość zapisu, nie logika; 2/3 czasu).

**Jedno zawężenie niezmiennika — do akceptacji Pawła.** Mecz objęty
niezmiennikiem musi być *poznawalny*: w czasie jego listowania komputer działał
bez przerwy ≥ 60 min (pełny cykl odświeżania `/events` ze specyfikacji). Mecz
wystawiony i zdjęty z listy w całości w czasie przerw komputera jest
niepoznawalny — `/events` nie podaje meczów zakończonych, `/scores` jest płatne;
śladem jest luka w heartbeacie. Warunek zależy tylko od świata, ten sam dla kodu
sprzed i po naprawie. Drugi szczegół: mecz przełożony w czasie przerwy kolektor
raportuje pod gwizdkiem ostatnio widzianym w `/events` (nowego nie mógł znać) —
wyrocznia akceptuje ten gwizdek, prawdziwość powodu sprawdza wobec prawdziwego.

**Powód spoza listy z decyzji:** `błąd API dostawcy` (HTTP 5xx / nieznany
licznik przy zamknięciu) — piąta wartość `MISSED_REASONS`; świat testu go nie
generuje, więc niezmiennik sprawdza wyłącznie cztery powody z decyzji. Do
akceptacji Pawła.

#### PRZED (`de89be2`, worktree, ostateczna wersja testu i pomocników)

```
E       AssertionError: 38 z 50 scenariuszy łamie niezmiennik; pierwszy kontrprzykład:
E         ziarno 0: start 2026-11-28T16:25:00+00:00, koniec 2026-11-29T07:15:00+00:00, used0 170,
E           rodzaje ['odlegle-mecze', 'ten-sam-gwizdek', 'wystawiony-pozno', 'wystawiony-za-pozno']
E           s0-m2 soccer_germany_bundesliga listowany 2026-11-28T22:20 terminarz [(22:20, 2026-11-29T02:15)]
E           s0-far0, s0-far2 soccer_germany_bundesliga listowane od startu (2026-12-29, 2027-01-05)
E           NARUSZENIA:
E             s0-m2 KO 2026-11-29T02:15:00+00:00: brak zamknięcia i brak wpisu closing_missed
(partie: 38, 36, 34, 37, 37, 38, 40, 37, 41, 42 z 50 → 380/500)
10 failed, 1 passed in 279.15s
```

Kontrprzykład = mechanizm F0d-01: liga zna odległe mecze, mecz wystawiony późno
nie trafia do terminarza (sonda nie odpala) — zero zamknięć, zero wpisu.

#### Kontrprzykłady znalezione PO drodze (na kodzie rundy 0e, przed ostateczną łatką)

- ziarno 2 — **błąd żyjący od F-13** (także w kodzie produkcyjnym przed rundą):
  `migrate_done_keys` wołana przy KAŻDYM przebiegu traktowała każdy klucz jak stary
  klucz godzinowy — zamknięcie meczu o 17:15 oznaczało jako zrobione zamknięcie
  meczu o 18:00 (ta sama „godzina slotu”). Drugi mecz tracił zamknięcie po cichu.
  Naprawa: migracja jednorazowa (`done_keys_migrated`); osobny test
  `test_done_key_migration_does_not_swallow_next_kickoff` (czerwony na starym
  kolektorze: (1, 2) zamiast (2, 2)).
- ziarno 341 — mecz przełożony 11 min przed starym gwizdkiem: odpowiedź zamknięcia
  zawierała go pod nowym terminem, kolektor wpisywał „brak rynku Pinnacle”
  (nieprawda). Naprawa: mecz obecny pod innym gwizdkiem → bez powodu, wymuszone
  odświeżenie `/events` w następnym przebiegu (płatna odpowiedź nie zasila terminarza).

#### PO (`940bada`)

```
11 passed in 286.30s (0:04:46)      # 500/500 światów + test pokrycia rodzajów
```

### F0d-01 — łatka (`940bada`)

- `OddsApiClient.fetch_events` (`GET /sports/{sport}/events`, bez `UsageGuard`).
- `run_once`: terminarz każdej ligi z `/events` bezwarunkowo, gdy ostatnie udane
  odświeżenie ≥ 60 min; `events_seen` (id → aktualny gwizdek) wyłącznie z
  `/events`; płatne odpowiedzi go nie zasilają; zdarzenie znikające z listy zostaje
  z ostatnim gwizdkiem (chwilowo pusta odpowiedź nie wymaże terminarza przed
  zamknięciem; mecz odwołany kończy się wpisem „brak rynku Pinnacle”, nie ciszą).
- Płatna sonda (`schedule_probes`) i `refresh_schedule` usunięte;
  `collect_odds.py --refresh` → `refresh_events` (bezpłatne).
- `x-requests-last > 0` na `/events` → `events_cost_alarm` w stanie, `/events`
  wyłączone, błąd w każdym heartbeacie.
- `closing_events` kluczowane `id|gwizdek`; każda próba zamknięcia zapisuje
  powód porażki (`closing_failures`); po gwizdku `closing_missed` z `reason` i
  `collector_gap` (tylko „komputer nie działał”).
- ≥ 200 MB wolnego miejsca przed każdym płatnym wywołaniem (`free_bytes`,
  wstrzykiwalne); błąd zapisu `OSError` łapany (wcześniej wywracał przebieg).
- `BudgetExhaustedError` (used + koszt > 450) odróżniony od trybu oszczędnego.
- `migrate_state`: stary `kickoffs`, `kickoffs_seen`, wpisy `legacy:` usuwane;
  `migrate_done_keys` jednorazowo.

Dostosowane stare testy (asercje bez zmian, terminarz podawany przez `/events` w
fałszywym transporcie): `test_odds_collector.py` (pomocnik `_collector(schedule=…)`;
`seen` = wyłącznie płatne `/odds`), `test_fsa0_f15_budget.py` (`/events` z
`x-requests-last: 0`), `test_fsa0b_01_closing_coverage.py` (A poznany z `/events`
rano), `test_fsa0c_01_coverage_per_match.py` (mecz znany z `/events`, odpowiedź bez
niego), rejestr F-12 (`_record_missed` → `_report_missed`, nadal `data/state`).
**Zmiana specyfikacji (decyzja pkt 1), nie osłabienie:** `test_schedule_is_refreshed_from_every_response`
→ `test_schedule_comes_only_from_events`; F0c-01 „krotność ze starego stanu” →
„krotność z identyfikatorów `/events`” (oczekiwane (1, 6) bez zmian);
F0c-02 „sonda ≤ 1/dobę” → „zero płatnych wywołań bez meczów, `/events` ≥ 72 w 3 doby”.

### Zamknięte z konstrukcji — dowody (`test_fsa0e_by_construction.py`)

PRZED `de89be2` (worktree): **8 failed** — każda pozycja asercją zachowania:

```
F0d-02  tryb oszczędny zostawił ligę bez zamknięcia          assert (0, 0) == (1, 1)
F0d-03  mecz przełożony odziedziczył „zebrane”               assert (1, 1) == (0, 1)
F0d-05  płatne wywołanie mimo braku miejsca na zapis         assert ['/v4/sports/soccer_epl/odds'] == []
Pinnacle osobno od luk: brak wpisu z powodem
/events kosztowne: brak wyłączenia (planowane schedule_probe)
F0b-09  płatna ścieżka terminarza nadal istnieje             assert not True
F0b-08  kalkulator ma własny literał 450                     assert [450] == []
F0b-08  kalkulator bez funkcji planu                         assert None is not None
```

PO `940bada`: 9 passed (z testem migracji kluczy). `scripts/odds_budget.py` na
żywym terminarzu: „RAZEM 430 — W BUDŻECIE, ale powyżej progu trybu oszczędnego
390: ~9% cyklu bez migawek decyzyjnych, T-24h i zamknięć zapasowych” (wcześniej
„MIEŚCI SIĘ”). Sam plan 430 > 390 pozostaje decyzją budżetową Pawła (F0b-08 był
o deklaracji kalkulatora, nie o planie).

### F0d-04 (`efac05b`)

PRZED `940bada`: 5 failed (`clv=None, reason='brak migawki zamknięcia'` ×4;
`'h2h' == '1x2'`). Łatka: `BetRecord` zapisuje rynek kanoniczny; `closing_key` i
klucze `closing` w `clv_rows` kanonizowane. PO: 5 passed. Rewers @940bada: 5 failed.

### F0d-06 (`8b97419`, tekstowe)

`docs/task_scheduler.md`: `/events`, koszt w `usage.jsonl`, `events_cost_alarm`,
`events_refreshed`, `schedule_empty`, `closing_missed` z powodami, ~288
przebiegów/dobę (krok 5 min); `schema.py`: komentarz `MARKET_OUTCOMES` nad
właściwym obiektem. Dowód: diff.

### Weryfikacja całości (§4) na `b02e613`

- `uv run pytest` — **836 passed** (476.8 s, z testem niezmiennika 500 światów);
  `-k future_poison` — 10 passed; `ruff check src tests scripts` — czysto;
  `mypy src` (strict) — czysto; `KNOWN_VIOLATIONS` — pusta.
- Pokrycie (linie+gałęzie): TOTAL 94%; `lockbox.py` 100%; `pricing/` ev 95%,
  fair 92%, kelly 90%, shin 95%; `raw_store.py` 97%; `provenance.py` 100%;
  `odds_collector.py` 94%.
- `verify_raw.py` — OK (7 plików); `git status` — czysty; skan historii pod
  klucz API (`VB_ODDS_API_KEY=…`, `apiKey=<32 hex>`) — 0 trafień.


### FSA #0e — pierwsze podejście przerwane (2026-10-03)

Sesja 4903cb05 uruchomiła audytora; zapisał wyłącznie szkielet
`reports/audit/FSA_2026-10-03_F0e.md` (lista kontrolna bez odhaczeń, bez linii
`BRAMKA`) i sesja się skończyła. Plik zostaje bez edycji jako ślad przerwanego
przebiegu — **nie jest raportem**. Audyt uruchomiony ponownie 2026-10-04,
zlecenie z §5 dosłownie, raport `reports/audit/FSA_2026-10-04_F0e.md`.

## FSA #0e (2026-10-04) — wynik i STOP przed etapem H

Raport: `reports/audit/FSA_2026-10-04_F0e.md` (audytowany `299bbf3`,
nieedytowany). Ostatnia linia: `BRAMKA: KRYT=0 POWAŻNE=0 OTWARTE=[]`. Rewersy
audytora: F-01 12, F-02 5, F-04+A-01 6, F-19 5, F-20 3, F-25 6, F0d-04 5, F0d-01
19 failed (niezmiennik 380/500) na swoich PRZED, zielone na HEAD; niezmiennik
wykrywa 4/4 mutacje. pytest 836 passed, ruff/mypy czysto, `verify_raw` 0.

Nowe znaleziska — wszystkie DROBNE: F0e-01 (kalkulator budżetu zaniża migawki
decyzyjne, realny plan ~456/mies. zamiast 430), F0e-02 (ścieżki błędów API bez
testu; fałszywy powód „komputer nie działał” dla meczu poznanego po gwizdku),
F0e-03 (kanonizacja wyniku i kolizja kluczy `h2h`/`1x2` w mapie zamknięć —
latentne do Filaru 1), F0e-04 (tryb gry Avasta), F0e-05 (zawężenie niezmiennika
i piąty powód `closing_missed` bez akceptacji Pawła), F0e-06 (dokumenty).
Otwarte DROBNE wcześniejsze: F0b-04, F0b-05, F0b-07, F0b-10…F0b-13.

**Warunek §6 pkt 1 spełniony. Etap H NIE wykonany — STOP**, bo F0e-01 uruchamia
osobny punkt STOP specyfikacji: §3 F-13 „> 450/mies. → zapasowe tylko dla PL i
Bundesligi; nadal > 450 → **STOP** i raport” (zapasowe już tylko PL/BL; plan ~456).
Automatyczne przejście przepuściłoby też bez odpowiedzi Pawła dwie pozycje
oznaczone „do akceptacji” (F0e-05). Sprzeczność „bramka automatycznie” vs „STOP”
rozstrzyga Paweł (§8: sprzeczność → STOP i pytanie, nie wybór po cichu).
`ROADMAP.md` §0 i `CONTEXT.md` §5 bez zmian; Filar 1 nie wystartował.

## Decyzje Pawła (2026-10-04), dosłownie

> Decyzje Pawła (2026-10-04) — zapisz dosłownie w FIX_LOG_F0.md.
>
> 1. Budżet (F0e-01): nie (a) i nie proponowane cięcia. Zostają: zamknięcia główne wszystkich lig, zapasowe PL i Bundesligi, migawki decyzyjne „dziś i jutro” (TOR_S_PLAN §2). Usuwasz kotwicę T-24h Ekstraklasy — dubluje poranne migawki decyzyjne. Jeśli cokolwiek w kodzie albo w planach (TOR_S_PLAN, COLLECTOR_PLAN, ROADMAP) korzysta z T-24h Ekstraklasy — STOP i pytanie.
>    Kalkulator: zamiast własnej formuły symuluje prawdziwe due_calls kolektora co 5 min na terminarzu. Test: wynik kalkulatora = liczba płatnych wywołań z symulacji tego samego terminarza — dziś czerwony, potem zielony. Cel ≤ 420/mies.; powyżej 420 po zmianie → STOP i raport z liczbami per liga i typ kotwicy.
> 2. F0e-05 akceptuję z warunkami:
>    - zawężenie niezmiennika: test wypisuje liczbę meczów wyłączonych przez zawężenie i dla każdego sprawdza lukę w heartbeacie pokrywającą okres listowania;
>    - „błąd API dostawcy” wyłącznie dla 5xx, timeoutu i zerwanego połączenia, z kodem HTTP we wpisie; 401, 403 i pozostałe 4xx → errors w heartbeacie; 429 → budżet. Generator scenariuszy produkuje te błędy i niezmiennik obejmuje pięć powodów — to zamyka F0e-02.
>    Protokół §1, osobne commity.
> 3. Avast: tryb gry wyłączyłem około 13:30 (godzina przybliżona, dokładnej nie znam). Weryfikację licz od startu Twoich przebiegów testów, nie od tej godziny: dwa pełne uv run pytest, a w TaskScheduler/Operational od początku weryfikacji zero nowych zdarzeń 106 „AVAST Software\Gaming mode Task Scheduler recovery” i 142 dla valuebet-odds. Podaj też godzinę ostatniego zdarzenia 106 przed weryfikacją. Choć jedno nowe zdarzenie → STOP przed Filarem 1.
> 4. Zgoda na usunięcie 15 worktree z sesji wykonawcy: git worktree remove bez --force (odmowa → zgłoś), potem git worktree prune.
> 5. Potem bramka wg §6 (ROADMAP §0, CONTEXT §5) i Filar 1 wg §7. Krok 1a, przed ingestem: F0e-03 według opisu audytora (wynik kanonizowany tak jak rynek, kolizje kluczy bez zależności od kolejności słownika, nieznany rynek odrzucany już przy zapisie do dziennika) i F0e-06; protokół §1. Zmiany z punktów 1, 2 i 1a idą do przeglądu w FSA #1a (krok 4a).

### Pkt 3 — weryfikacja Avasta: start

- Start weryfikacji: 2026-10-04 14:29:40 (+02:00); ostatnie 106 Avasta przed
  weryfikacją: **14:19:27** (z 142 `valuebet-odds` 14:19:27) — po podanym ~13:30.

### Pkt 3 — weryfikacja Avasta: wynik — NIEZALICZONA → STOP przed Filarem 1

- `uv run pytest` #1: 14:29:50 → 14:36:56, **836 passed in 424.21s**.
- `uv run pytest` #2: 14:38:52 → 14:46:37, **836 passed in 463.24s**.
- `TaskScheduler/Operational` od 14:29:40: **2 nowe zdarzenia** — `14:36:58 id=106`
  (`AVAST Software\Gaming mode Task Scheduler recovery`) i `14:36:58 id=142`
  (`valuebet-odds` wyłączone), 2 s po końcu przebiegu #1.
- Ostatnie 106 przed weryfikacją: 14:19:27 (po podanym ~13:30).
- Zgodnie z pkt 3: **STOP przed Filarem 1** — bramka §6 i Filar 1 dziś nie
  ruszają; pkt 1 i 2 (przed Filarem 1) kontynuowane.

### Pkt 1 — STOP (T-24h Ekstraklasy używana w planach)

Odwołania do T-24h Ekstraklasy: `COLLECTOR_PLAN.md:138-141` (kotwica v1; „T−24 h
i T−60 min to oś eksperymentu `bet_lead_time` z CLAUDE.md”), `:201` (T−24 h
druga w kolejności ważności), `:271` („migawki T−24 h wyłącznie dla
Ekstraklasy”), `:381` („eksperyment `bet_lead_time`: 24 h vs 1 h na prawdziwych
cenach wejścia”); `ROADMAP.md:191` (budżet Ekstraklasy „zamknięcia + T−24 h”);
kod: `ingest/odds_collector.py:146, 200`, `scripts/odds_budget.py`,
`tests/test_odds_collector.py:127` (`test_t24_fires_only_for_ekstraklasa`).
Usunięcie kotwicy wstrzymane do odpowiedzi Pawła.

### Pkt 1 — odpowiedź Pawła na STOP (2026-10-04), dosłownie

> 3 — usuń T-24h Ekstraklasy i zaktualizuj plany. Zgoda na zmianę wyłącznie wskazanych wierszy COLLECTOR_PLAN.md (§3.3, l. 381) i ROADMAP.md (l. 191): oś bet_lead_time = migawki decyzyjne, z czasem do gwizdka od ok. 4 do 40 h, kontra zamknięcie; CLV raportowane w przedziałach czasu do gwizdka zamiast dwóch stałych punktów 24 h i 1 h. Kalkulator-symulacja jak w poleceniu, cel ≤ 420.
>
> Okno pracy: komputer wyłączam ok. 17:30. Do 17:15 domknij bieżącą pozycję, zrób commit, zapisz stan w FIX_LOG_F0.md (a jeśli Filar 1 ruszył — w reports/backtest_fin/PROGRESS.md) i STOP. Nie zaczynaj niczego, czego nie skończysz do 17:15, w szczególności przebiegów strategii. Ingest Filaru 1 może ruszyć tylko wtedy, gdy przerwany da się bezpiecznie wznowić (pliki już pobrane są pomijane, a niedokończone nie trafiają do manifestu). Jeśli nie masz pewności — nie zaczynaj go dziś.

### Pkt 4 — worktree: ODMOWA (2026-10-04 14:4x)

`git worktree remove` (bez `--force`) odmówił dla **wszystkich 15** (`wt/F01`,
`F02`, `F04A01`, `F0b01`–`F0b03`, `F0c01`–`F0c03`, `F0d01c`, `F0d01i`, `F0d04`,
`F19`, `F20`, `F25`): „contains modified or untracked files”. Nieśledzone pliki to
w każdym kopie z HEAD wkładane przez procedurę rewersu (§1):
`tests/helpers/{__init__,collector_scene,collector_sim}.py` + plik testu regresji
danej pozycji. `git worktree prune` — bez zmian (katalogi istnieją). Zgłoszone
Pawłowi; `--force` nieużyte.

### F0e-01 — kalkulator-symulacja (pkt 1, część niezależna od T-24h)

PRZED (`a8fe087`, `uv run pytest tests/regression/test_fsa0e_01_budget_simulation.py`):

```
E       AssertionError: kalkulator 412.8/mies. ≠ kolektor 102 kredytów × 4.3 = 438.6
1 failed in 59.69s
```

Test: jedna kolejka na ligę (9/10/9 meczów), prawdziwy `run_once` co 5 min od
wtorku do wtorku na fałszywym transporcie; płatne wywołania i kredyty kolektora
= wynik kalkulatora (`total`, `window_calls`, `window_credits`). Różnica PRZED =
6 kredytów = 3 dni migawek decyzyjnych sprzed pierwszego dnia kolejki (mechanizm
F0e-01). Łatka: `scripts/odds_budget.py` symuluje prawdziwe `due_calls` krokiem
5 min, bez własnej formuły; raport per liga i typ kotwicy.

PO: 1 passed (razem z `test_fsa0e_by_construction.py`: 10 passed in 33.07s).

Plan na żywym terminarzu (2026-10-04 ~15:00), kredytów/mies.:

```
bundesliga      closing 43.0 | closing_backup 43.0 | decision 34.4
ekstraklasa     closing 77.4 | t24            77.4 | decision 43.0
premier_league  closing 51.6 | closing_backup 51.6 | decision 34.4
RAZEM 456 — NIE MIESCI SIE w budzecie 450 (o 6)
```

Bez T-24h Ekstraklasy: 456 − 77.4 ≈ **379** (≤ 420, poniżej progu 390) —
wyliczone z tabeli, nie z przebiegu; usunięcie kotwicy wstrzymane (niżej).

### Pkt 1 — usunięcie T-24h: WSTRZYMANE (odmowa uprawnień)

`schtasks /change /disable` (kolektor na czas zmian w `ingest/`) i odczyt
`tests/test_odds_collector.py` (test `test_t24_fires_only_for_ekstraklasa` do
zmiany oczekiwania) — odrzucone przez klasyfikator uprawnień Claude Code.
Nie obchodzone. Kolektor nie był wyłączany; `ingest/` bez zmian.

## Stan na koniec sesji (2026-10-04 15:00) — STOP

Weryfikacja na `d2437ea`: `uv run pytest` 837 passed (507 s); `ruff check src
tests scripts` czysto; `mypy src` czysto; `verify_raw` OK; heartbeat 12:57:56 UTC
`errors = []`. Kolektor włączony przez całą sesję (wyłączenie odrzucone).

| pkt decyzji | stan | następny krok |
|---|---|---|
| 1 kalkulator | **zrobione** (`d2437ea`, PRZED/PO wyżej) | — |
| 1 T-24h Ekstraklasy | wstrzymane: odmowa uprawnień (wyłączenie zadania, odczyt `tests/test_odds_collector.py`) | zgoda Pawła na `schtasks /change /tn valuebet-odds /disable`/`/enable` i odczyt pliku; potem: `LEAGUES` Ekstraklasy `anchors=(CLOSING,)`, zmiana oczekiwania `test_t24_fires_only_for_ekstraklasa` (zmiana specyfikacji, decyzja 2026-10-04), docstringi, `COLLECTOR_PLAN.md` §3.3 i l. 381, `ROADMAP.md:191`; plan z kalkulatora ≈ 379 (cel ≤ 420). Uwaga: `COLLECTOR_PLAN.md:201, 271` też wymieniają T−24 h, ale nie są na liście zgody — decyzja Pawła: poprawić w następnej sesji razem z T-24h w kodzie |
| 2 F0e-05/F0e-02 | niezaczęte (łatka w `ingest/` wymaga wyłączenia zadania; czerwonego testu nie commitujemy bez łatki) | test niezmiennika: licznik zawężenia + luka w heartbeacie; generator błędów 5xx/timeout/zerwane, 401/403/4xx, 429; pięć powodów |
| 3 Avast | **NIEZALICZONE** (106+142 o 14:36:58) → STOP przed Filarem 1 | Paweł: sprawdzić ustawienie trybu gry w Avaście; potem ponowna weryfikacja (2× pełny pytest, zero 106/142) |
| 4 worktree | **zrobione** (`--force` za zgodą Pawła, 15/15) | — |
| 5 bramka, Filar 1 | nie ruszone (STOP z pkt 3; pkt 1–2 niedomknięte) | po pkt 1–4 |

### Pkt 4 — worktree: usunięte (2026-10-04, decyzja Pawła)

Decyzja Pawła, dosłownie: „Usuń 15 worktree z --force, potem commit i STOP.
Linie 201 i 271 jutro, razem z usunięciem T-24h w kodzie.”

`git worktree remove --force` — 15/15 OK; `git worktree prune`; `git worktree
list` — wyłącznie główne drzewo (`24f6f48 [master]`). `COLLECTOR_PLAN.md:201, 271`
→ następna sesja, razem z usunięciem T-24h.

## Sesja 2026-10-07 (20:41 → hard stop 22:15)

### Stan na starcie

`master` @ `7310a6e`, drzewo czyste; `git worktree list` — wyłącznie główne
drzewo (worktree usunięte 2026-10-04, pkt 4; dziś `git worktree prune -v` —
bez zmian). Heartbeat 18:38:03 UTC `errors = []`, `usage_remaining 497`,
płatnych `/odds` 0. Tryb gry Avasta nadal aktywny (wiersze KOLEKTOR).

### Decyzje Pawła (2026-10-07), dosłownie

> Reguły dodane. Przed wyłączeniem zapisz stan zadania (schtasks /query /tn valuebet-odds /fo list, tylko do odczytu) i wpisz go do FIX_LOG. Jeśli zadanie jest już Disabled (Avast), nie włączaj go po zmianach na ślepo. Włącz je tylko wtedy, gdy na starcie było Ready, a potem zweryfikuj stan i wpisz do FIX_LOG. Jedno sprawdzenie stanu zadania zrób też tuż przed hard stopem. Kontynuuj bloki 2 i 3.

Pytanie: jaki wpis `closing_missed` dostaje zamknięcie przegapione przez HTTP 4xx. Odpowiedź:

> Opcja 1 (szósty powód) z warunkami: (a) powód tylko dla odpowiedzi HTTP 4xx z wyjątkiem 429 (429 idzie do budżetu); (b) wpis niesie kod HTTP i collector_gap=false; (c) heartbeat dalej zapisuje błąd 4xx, wpis w closing_missed jest dodatkiem, nie zamiennikiem; (d) generator niezmiennika produkuje odpowiedzi 4xx, a test sprawdza, że mecz bez zamknięcia i bez wpisu nadal łamie niezmiennik (czyli szósty powód nie osłabił go dla pozostałych przypadków); (e) test pokazuje, że 5xx/timeout nadal dostaje powód „błąd API dostawcy”, a nie szósty.

Pytanie o kolejność (blok 3 ~60–75 min wobec ~65 min do hard stopu). Odpowiedź:

> Opcja 1 (najpierw bramka) z warunkami: (a) wpis bramki wymienia F0e-05 i F0e-02 jako OTWARTE DROBNE, z terminem "przed Filarem 2" i z zapisem, że akceptacja Pawła dla F0e-05 jest związana z warunkami z decyzji 2026-10-04 (zawężenie z licznikiem i sprawdzeniem luki heartbeatu, szósty powód 4xx z wyjątkiem 429, kod HTTP we wpisie, test, że niezmiennik nadal łamie się dla meczu bez zamknięcia i bez wpisu); (b) cytat mojej akceptacji z 2026-10-02 11:33 wklejony dosłownie z datą, plus stwierdzenie, czy warunek jest spełniony; (c) potem blok 3, najpierw F0e-05, F0e-02 tylko jeśli starczy czasu; (d) niedokończonej pracy z bloku 3 NIE commituj na master i nie kasuj: git stash push -m "WIP F0e-05" albo osobna gałąź, opis w FIX_LOG jako następny krok, na koniec czysty git status.

### Blok 2 — T-24h Ekstraklasy usunięta (decyzja Pawła 2026-10-04, pkt 1)

PRZED (`7310a6e`, `uv run pytest tests/regression/test_fsa0e_t24_removed.py -q`):

```
E       assert not [('ekstraklasa', 't24')]
E           AssertionError: (datetime.datetime(2026, 10, 23, 17, 0, tzinfo=datetime.timezone.utc), [('ekstraklasa', 't24')])
E       assert 't24' not in {'closing', 'closing_backup', 'decision', 't24'}
3 failed in 6.06s
```

Łatka: `ingest/odds_collector.py` — stała `T24` usunięta, Ekstraklasa
`anchors=(CLOSING,)`, docstring modułu (kotwice) i komentarz trybu
oszczędnego bez T-24h. **Zmiana oczekiwania** (zmiana specyfikacji, decyzja
2026-10-04, nie osłabienie): `test_t24_fires_only_for_ekstraklasa` →
`test_no_t24_anchor_a_day_before_kickoff` (oczekiwane `[]` zamiast
`[("ekstraklasa", "t24")]`); w `test_windows_cover_…` asercja okna `T24` →
okno `DECISION`. Dokumenty (zgoda 2026-10-04 i 2026-10-07):
`COLLECTOR_PLAN.md` §3.3 l. 141 (oś `bet_lead_time`), l. 201, 271, 381;
`ROADMAP.md` l. 191. `COLLECTOR_PLAN.md:138` (lista kotwic v1 scrapera
polskiego bukmachera, nie The Odds API) — poza zgodą, bez zmian.

Kalkulator (`uv run python scripts/odds_budget.py`, żywy terminarz
2026-10-07 ~21:00), kredytów/mies.:

```
PRZED: bundesliga closing 43.0 | closing_backup 43.0 | decision 34.4
       ekstraklasa closing 77.4 | decision 38.7 | t24 77.4
       premier_league closing 51.6 | closing_backup 51.6 | decision 34.4
       RAZEM 452 — NIE MIESCI SIE w budzecie 450 (o 2)
PO:    bundesliga closing 43.0 | closing_backup 43.0 | decision 34.4
       ekstraklasa closing 77.4 | decision 38.7
       premier_league closing 51.6 | closing_backup 51.6 | decision 34.4
       kotwice meczowe 267 (w tym zamkniecia glowne 172), decyzje 108
       RAZEM 374 — MIESCI SIE ponizej progu trybu oszczednego 390
```

Cel ≤ 420: **spełniony (374)**. Test na terminarzu kolejki F0e-01 (prawdziwy
`due_calls`, kalkulator = kolektor): plan ≤ 420, brak `t24`.

PO (łatka w drzewie roboczym, przed commitem): `uv run pytest -q` **840 passed
in 709.27s**; `ruff check src tests scripts` — 3× RUF002 (półpauza/minus w
docstringach nowego kodu) → zamienione na `-` → All checks passed!; `mypy src`
— Success (36 plików); `verify_raw` — OK (manifest raw 7 wierszy,
`a099c16b…f149ec`, bez zmian). Commit: `fix(FSA0e F0e-01): usunięta kotwica T-24h Ekstraklasy` — `67b31d5`.

### Blok 4 — bramka F0 → F1 (etap H, `FSA0_NAPRAWY.md` §6) — OTWARTA 2026-10-07

Akceptacja Pawła, dosłownie, z datą: „Jeśli testy i audyt dadzą zielone
światło – wreszcie otworzy bramkę i automatycznie przejdzie do Filaru 1”
(Paweł, **2026-10-02 11:33**). Potwierdzona dla rundy 0e (decyzja
2026-10-03, pkt 5): „BRAMKA KRYT=0 POWAŻNE=0 → bramka wg §6 i Filar 1 wg §7
automatycznie (moja warunkowa akceptacja z 2026-10-02 obowiązuje). Inaczej
STOP.” Dziś polecenie Pawła, pkt 4: „Otwórz bramkę wg §6”.

**Warunek „testy i audyt dadzą zielone światło” — SPEŁNIONY:**

| §6 | warunek | dowód | stan |
|---|---|---|---|
| 1 | linia `BRAMKA` ostatniego raportu `KRYT=0 POWAŻNE=0` | `reports/audit/FSA_2026-10-04_F0e.md:597`: `BRAMKA: KRYT=0 POWAŻNE=0 OTWARTE=[]` (liczby audytora, nie wykonawcy) | spełniony |
| 2 | każde zamknięte POWAŻNE: test czerwony → zielony, rewers czerwony | FSA #0e 0.1 — rewersy F-01, F-02, F-04, F-19, F-20, F-25, A-01, F0d-01 czerwone z zachowania na PRZED, zielone na HEAD | spełniony |
| 3 | §4 zielone, `verify_raw` = 0, `git status` czysty | `uv run pytest -q` **840 passed** (1079.89 s); `-k future_poison` 10 passed; `ruff check src tests scripts` czysto; `mypy src` Success (36 plików); `verify_raw` OK (manifest raw 7 wierszy, `a099c16b…f149ec`); `git status` czysty po tym commicie (worktree `wip/F0e-05` poza drzewem głównym) | spełniony |
| 4 | akceptacja zacytowana w FIX_LOG i w raporcie końcowym, z datą | ten wpis; raport końcowy sesji | spełniony |

**Otwarte DROBNE przy otwarciu bramki** (nie blokują §6 pkt 1; decyzja Pawła
2026-10-03 pkt 5 — „mogą zostać otwarte z wpisem w raporcie”):

- **F0e-05 — OTWARTE; WARUNEK PRZED FILAREM 2** (decyzja Pawła 2026-10-07: „F0e-05 ma
  obowiązywać jako warunek przed Filarem 2”). Bramka F1 → F2 nie otwiera się bez
  zamknięcia F0e-05 z dowodem fail-first. Akceptacja Pawła dla F0e-05
  (2026-10-04, pkt 2) jest **związana z warunkami**: zawężenie niezmiennika
  wypisuje liczbę wykluczonych meczów i dla każdego sprawdza lukę w
  heartbeacie pokrywającą okres listowania; szósty powód dla HTTP 4xx z
  wyjątkiem 429 (429 → budżet), z kodem HTTP we wpisie i `collector_gap =
  false`; „błąd API dostawcy” wyłącznie dla 5xx, timeoutu i zerwanego
  połączenia, z kodem HTTP; test, że niezmiennik nadal łamie się dla meczu
  bez zamknięcia i bez wpisu. Bez spełnienia warunków akceptacja nie
  obowiązuje.
- **F0e-02 — OTWARTE, termin: przed Filarem 2** (zamyka je generator błędów
  z F0e-05 i niezmiennik na wszystkich powodach).
- F0e-03, F0e-06 — krok 1a Filaru 1, przed ingestem.
- F0e-04 (Avast) — weryfikacja z 2026-10-04 niezaliczona, a dziś znów 3
  epizody (20:03, 20:12, 20:38). Decyzja Pawła 2026-10-07: „Niezależnie od
  odpowiedzi nie blokuje to prac.”
- F0e-01 — zamknięte w tej sesji (kalkulator `d2437ea`, T-24h wyżej; plan 374).
- F0b-04, F0b-05, F0b-07, F0b-10, F0b-11, F0b-12, F0b-13.

`ROADMAP.md` §0: F0 „ZAMKNIĘTY 2026-10-07 (FSA #0e)”, F1 „W TOKU”;
`CONTEXT.md` §5.38; `reports/audit/FSA_2026-10-04_F0e.md` w
`AUDITS_IN_CONTEXT` (`tests/regression/test_fsa0_f32_context_audits.py`).
Filar 1 dziś: bez ingestu i bez backtestu (polecenie Pawła).

Zmiana priorytetu (Paweł, 2026-10-07 ~21:31), dosłownie:

> Zmiana priorytetu: okno pracy do 22:40, potem 20 min na zamknięcie (commit, FIX_LOG, czysty git status). Po bramce NAJPIERW krok 1a Filaru 1 (F0e-03 i F0e-06, fail-first), dopiero potem F0e-05, a F0e-02 tylko jeśli zostanie czas. F0e-05 ma obowiązywać jako warunek przed Filarem 2, wpisz to w bramkę. Ingestu danych ani backtestu dziś nie zaczynaj. Niedokończoną pracę stashuj z opisem, nie commituj czerwonych testów na master.

### Krok 1a Filaru 1 — F0e-03 (decyzja Pawła 2026-10-04 pkt 5)

PRZED (`75ff3b2`, `uv run pytest tests/regression/test_fsa0e_03_clv_keys.py -q`):

```
E       AssertionError: ClvRow(... market='over_under', ... clv=None, p_close=None, reason='brak migawki zamknięcia')
E       AssertionError: assert 'Home' == 'home'
E       Failed: DID NOT RAISE ValueError            (×3: 'Arsenal', 'over' w 1x2, 'home' w totals)
E       assert -0.19999999999999996 == -0.09999999999999998   (kolizja h2h/1x2: wygrała migawka KO-25)
E           ValueError: market 'h2h_lay' spoza słownika   (cały raport CLV)
10 failed, 2 passed in 7.29s
```

Zielone już PRZED (2): odrzucenie nieznanego rynku w dzienniku (`canonical_market`
w `BetRecord` od F0c-03) i kolizja w kolejności „1x2 pierwszy” (przypadkiem wygrywa
późniejsza). Łatka: `schema.canonical_outcome(market, outcome)` (wielkość liter bez
znaczenia, wynik spoza `MARKET_OUTCOMES` rynku → `ValueError`; nazwa drużyny → błąd,
przekłada ją budujący mapę zamknięć); `BetRecord` kanonizuje wynik przy zapisie;
`clv.closing_key` kanonizuje wynik; `clv._canonical_closing`: kolizja → najpóźniejsza
migawka z `observed_at <= as_of` (bez takiej — najpóźniejsza), ta sama chwila z różnym
`p` → `ValueError`; klucz spoza słownika odpada (noga n/d), raport nie pada.

PO: 12 passed in 2.88s; zestaw powiązany (`-k "bets or clv or coupon or journal or
regime or kelly or ev or reconcile or f02 or f04 or a01 or a02 or f25 or f0b or f0c or
f0d04"`) 183 passed. `backtest-auditor` uruchomiony na zmianie (wynik niżej).

### Krok 1a Filaru 1 — F0e-06 (dokumentacja)

PRZED (`75ff3b2`, `uv run pytest tests/regression/test_fsa0e_06_docs.py -q`):

```
E       AssertionError: assert '/events' in '## The Odds API — ZIELONE ...'
E       AssertionError: assert '3 kredyty za wywołanie' not in 'Kolektor Th...'
2 failed, 1 passed in 3.58s
```

Łatka: `docs/sources.md` — `/events` (bezpłatne, ~72/dobę, `events_cost_alarm`,
podstawa §8), budżet 2 kredyty/wywołanie, plan 374; docstring `odds_collector.py`
(klucz kotwicy = gwizdek, nie slot godzinowy; 2 kredyty; krok 5 min w `Anchor`).
Docstring kolektora zmieniony przy WŁĄCZONYM zadaniu (włączone o 21:32:58 po commicie
bramki) — zmiana wyłącznie tekstu, bez zmiany zachowania. PO: 3 passed.

**backtest-auditor na F0e-03 (2026-10-07, subagent):** przecieku brak — każda
wybrana migawka przechodzi potem w `clv_rows` przez `observed_at > as_of` i okno
`[KO - tol, KO]`. Znaleziska: (1) DROBNE — przy kolizji migawka in-play
(`<= as_of`, po gwizdku) wypierała zamknięcie z okna → n/d; **naprawione
fail-first**: `test_collision_prefers_snapshot_inside_closing_window` czerwony na
łatce sprzed poprawki (`clv=None, reason='… poza tolerancją …'`), po poprawce
(ranga: najpierw ważne zamknięcie w oknie i `<= as_of`) zielony, 24 passed z
testami F0d-04, A-01, F-04. (2) DROBNE — ta sama chwila, różne `p` → `ValueError`
całego raportu (zachowawcze, nie zawyża) — zostawione, do decyzji. (3) DO
SPRAWDZENIA — klucz z nazwą drużyny cicho odpada; przyszły budowniczy mapy
zamknięć musi przekładać nazwy na `home`/`away`, a liczba odrzuconych kluczy
powinna trafiać do raportu CLV — następny krok (Filar 1, przy budowie mapy).

### F0e-05 — WIP na gałęzi `wip/F0e-05` (`1c77e2d`), NIE na master

Decyzje Pawła 2026-10-04 pkt 2 i 2026-10-07 (wyżej). Wykonane na gałęzi:
`OddsApiError.http_status`/`error_kind`, `HttpError.kind` (`timeout`,
`connection`, `other`); `api_failure_reason`: 429 → „budżet > 450”, inne 4xx →
**„błąd kolektora (HTTP 4xx)”** (szósty powód), reszta → „błąd API dostawcy”;
wpis `closing_missed` niesie `http_status`, `error_kind`, `collector_gap = false`;
heartbeat zapisuje błąd bez zmian. Generator: awarie `/odds` 500/502/503/timeout/
reset/400/401/403/404/429; wyrocznia sprawdza prawdziwość obu nowych powodów i
kod HTTP; zawężenie: licznik + luka we własnym heartbeacie kolektora.

PRZED (`67b31d5` + testy z gałęzi):

```
test_fsa0e_05_error_reasons.py: 12 failed in 45.73s
  (brak 'http_status' we wpisie ×5; 'błąd API dostawcy' == 'błąd kolektora (HTTP 4xx)' ×5; 429; brak szóstego powodu)
niezmiennik partie [0],[1] + test (d): 2 failed, 1 passed in 108.38s
  (s22-m0, s94-m2: wpis 'błąd API dostawcy' bez kodu HTTP)
```

PO (gałąź): `test_fsa0e_05_error_reasons.py` + `test_odds_collector.py` 39 passed;
niezmiennik + z konstrukcji **21 passed in 497 s** (500 światów; wyłączonych przez
zawężenie: 8, 9, 3, 8, 2, 3, 7, 7, 4, 4 = 55 meczów, każdy z luką w heartbeacie);
test (d) zielony. ruff, mypy czysto.

**Brakuje do zamknięcia F0e-05 (warunek przed Filarem 2):**
1. błąd kontraktu (HTTP 200, zły JSON / brak pól) i nieznany licznik (`/sports`
   padło, `BudgetSkipError` przy `guard.used is None`) dziś → „błąd API dostawcy”
   bez kodu HTTP — sprzeczne z „wyłącznie 5xx, timeout, zerwane połączenie”;
   **decyzja Pawła**: jaki powód (propozycja: kod z `/sports` przenoszony do wpisu;
   kontrakt → szósty powód albo osobna wartość);
2. pełny `uv run pytest` na gałęzi, potem merge na master z wpisem PO;
3. F0e-02: awarie `/events` w generatorze i fałszywy „komputer nie działał” dla
   meczu poznanego po gwizdku / przy `/events` 503.
   **Pytanie do Pawła:** mecz wystawiony między odświeżeniami `/events` i poznany
   dopiero po gwizdku (każdy przebieg się odbył) nie pasuje do żadnego z sześciu
   powodów — „komputer nie działał” jest tu nieprawdziwe. Propozycja: przy `/events`
   5xx/timeout w oknie → „błąd API dostawcy” z kodem; poznany po gwizdku bez błędu
   → siódmy powód „mecz poznany po gwizdku” albo wyłączenie z niezmiennika z
   licznikiem (jak zawężenie).

### Stan na koniec sesji 2026-10-07 — następne kroki

| pozycja | stan | następny krok |
|---|---|---|
| T-24h, kalkulator | **zrobione** (`67b31d5`, plan 374 ≤ 420) | — |
| bramka F0 → F1 | **otwarta** (`75ff3b2`) | — |
| F0e-03, F0e-06 (krok 1a) | **zrobione** (`79ab9c9`) | budowniczy mapy zamknięć: nazwy drużyn → home/away, licznik odrzuconych kluczy |
| F0e-05 | **naprawione, na master** (`71ae310`, fast-forward z `wip/F0e-05`) | weryfikacja audytora (FSA #1a) — warunek przed Filarem 2 obowiązuje do zamknięcia przez audytora |
| F0e-02 | niezaczęte; decyzja Architekta 2026-10-07 pkt 3 zapisana | implementacja w następnej sesji (powód „mecz poznany po gwizdku”, `/events` 5xx/timeout → „błąd API dostawcy”) |
| Avast | tryb gry nadal aktywny (20:03, 20:12, 20:38, 21:42) | Paweł: ustawienia trybu gry / wyjątek dla Harmonogramu |
| Filar 1 krok 2 (ingest) | nie ruszony (polecenie Pawła) | następna sesja |

**Weryfikacja kroku 1a (drzewo robocze, 21:44:52 → 21:56:46):** `uv run pytest -q`
**856 passed** in 670 s; `-k future_poison` 10 passed; `ruff check src tests scripts`
czysto; `mypy src` Success (36 plików); `verify_raw` OK. Commit:
`fix(FSA0e F0e-03, F0e-06): …` — `79ab9c9`.

### Decyzje Architekta (Paweł deleguje, 2026-10-07 ~22:10), dosłownie

> 1. Nieznany licznik (/sports padło): wpis niesie kod HTTP z /sports i jest klasyfikowany jak każdy inny błąd (5xx/timeout/reset -> "błąd API dostawcy" z kodem; 4xx poza 429 -> "błąd kolektora (HTTP 4xx)"; 429 -> budżet). Potwierdź w kodzie i teście, że przy guard.used is None kolektor NIE wydaje płatnych kredytów. Jeśli wydaje, STOP i raport.
>
> 2. Błąd kontraktu (HTTP 200, zły JSON lub brak pól): osobna wartość "błąd kontraktu API", http_status=200, collector_gap=false, heartbeat dalej zapisuje błąd. Nie wchodzi do "błąd API dostawcy" i nie do szóstego powodu. Generator produkuje takie odpowiedzi, niezmiennik nadal łamie się dla meczu bez zamknięcia i bez wpisu, a test pokazuje, że każdy powód ma realną ścieżkę w kodzie.
>
> 3. F0e-02, decyzja zapisana, implementacja w następnej sesji: (a) /events 5xx lub timeout w oknie przed gwizdkiem -> "błąd API dostawcy" z kodem; (b) mecz poznany dopiero po gwizdku bez błędu -> osobny powód "mecz poznany po gwizdku" z first_seen_at > kickoff. NIE wyłączenie z niezmiennika, bo wypadłby z mianownika pokrycia zamknięć. Wyrocznia sprawdza first_seen_at i brak błędu /events w oknie. Wpisz do FIX_LOG.
>
> 4. MAINTENANCE file: odrzucone. Uprawnienia do schtasks działają (wyłączenie 20:55, włączenie 21:32:58), więc dodatkowy mechanizm w kolektorze to zbędna złożoność. Usuń z następnych kroków.
>
> 5. Zrób pkt 1 i 2 na gałęzi wip/F0e-05, potem pełny pytest. Jeśli do 22:50 jest zielony, merguj na master z wpisem PO w FIX_LOG. Jeśli nie, nie merguj, zostaw gałąź, zaktualizuj FIX_LOG, master ma być czysty. Zamknięcie sesji do 23:00.

Pkt 4: MAINTENANCE usunięte z następnych kroków (tabela wyżej).

**F0e-02 — decyzja zapisana (pkt 3), implementacja w następnej sesji:** (a)
`/events` 5xx/timeout w oknie przed gwizdkiem → „błąd API dostawcy” z kodem; (b)
mecz poznany po gwizdku bez błędu → osobny powód „mecz poznany po gwizdku” z
`first_seen_at > kickoff`, w niezmienniku (nie wyłączenie — zostaje w mianowniku
pokrycia zamknięć); wyrocznia sprawdza `first_seen_at` i brak błędu `/events` w oknie.

### F0e-05 pkt 1–2 (gałąź `wip/F0e-05`, po scaleniu master → gałąź `5fe017c`)

PRZED (`5fe017c` = `1c77e2d` + master; nowe testy w
`test_fsa0e_05_error_reasons.py`, `uv run pytest … -q`):

```
E       assert 'błąd API dostawcy' == 'błąd kolektora (HTTP 4xx)'      (/sports 401)
E       assert 'błąd API dostawcy' == 'budżet > 450'                    (/sports 429)
E           json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)   (zły JSON z /odds wywracał run_once)
E       assert 'błąd API dostawcy' == 'błąd kontraktu API'              (/odds dict zamiast listy)
E       assert 'brak rynku Pinnacle' == 'błąd kontraktu API'            (/odds zdarzenie bez id)
E       assert {…'błąd kontraktu API'…} == {…}                           (powód bez ścieżki w kodzie)
8 failed, 12 passed in 31.94s
```

Łatka: `OddsApiClient._json_list` — zły JSON / nie-lista z `/sports`, `/odds`,
`/events` → `OddsApiError(http_status=200, error_kind="contract")`; `/odds`:
zdarzenie bez `id`/`commence_time` → kontrakt. Kolektor: siódmy powód **„błąd
kontraktu API”**; `_fresh_guard` zwraca błąd `/sports` (albo błąd kontraktu, gdy
200 bez `x-requests-used`), a zamknięcie pominięte przy nieznanym liczniku dostaje
powód i kod z tego błędu. **Płatne kredyty przy `guard.used is None`: zero** —
`UsageGuard.skip_reason` zwraca powód dla `used is None`, `fetch_odds` rzuca
`BudgetSkipError` przed `_get` (`odds_api.py`); test
`test_unknown_counter_is_classified_and_spends_nothing` liczy płatne `/odds` = 0 dla
503, timeout, 401, 429. Generator: kontrakt na `/odds`, awarie `/sports`
(5xx/timeout/reset/4xx/429/kontrakt); `test_every_reason_has_a_real_path_in_the_code`
— każdy z 7 powodów z prawdziwego `run_once`.

PO (gałąź): `test_fsa0e_05_error_reasons.py` **20 passed in 39.07s**; generator +
partia [0] niezmiennika 2 passed.

PO — pełna weryfikacja na gałęzi (22:16:01 → 22:29:20, drzewo = późniejszy master):
`uv run pytest -q` **877 passed in 739.16s**; `-k future_poison` 10 passed; `ruff check
src tests scripts` czysto; `mypy src` Success (36 plików). Zielone przed 22:50 →
**merge na master** (pkt 5): `git merge --ff-only wip/F0e-05` → `71ae310` (22:31);
po merge `verify_raw` OK, testy sesji (F0e-05, T-24h, F0e-03, F0e-06) 39 passed.
Gałąź `wip/F0e-05` usunięta po scaleniu (`git branch -d`), worktree wyrejestrowany.

**KOLEKTOR przy merge:** `schtasks /query` 22:29:54 — **Disabled**, wyłączone przez
tryb gry Avasta (106 + 142 o 22:04:15, 22:15:01, 22:19:46, 22:24:27, 22:26:46 w
trakcie pełnego `pytest`; Avast przywracał je o 22:04:50, 22:19:30, 22:23:57,
22:26:35). Merge `ingest/` przy zadaniu wyłączonym przez Avasta; **nie włączane
ręcznie** (warunek Pawła: na ślepo nie). Ostatni heartbeat 20:13:04 UTC `errors = []`.
Stan przed zamknięciem — wiersz niżej.

| KOLEKTOR | kiedy (lokalnie) | stan | uwagi |
|---|---|---|---|
| stan przed zamknięciem sesji | 2026-10-07 22:32:23 | `schtasks /query`: **Ready** (przywrócone przez Avasta przy wyjściu z trybu gry), Next Run 22:32:53; ostatni przebieg 22:12:54 wynik 0 | luki 22:04–22:04:50, 22:15–22:19:30, 22:19:46–22:23:57, 22:24:27–22:26:35, 22:26:46–~22:32: **tryb gry Avasta** |
| pierwszy przebieg po merge `71ae310` | 2026-10-07 22:32:56 (20:32:56 UTC) | heartbeat `errors = []`, `usage_remaining 497`, „nic nienależne” | kod z F0e-05 działa na produkcyjnym stanie |

## Sesja 2026-10-08 — Filar 1, krok 2 (ingest football-data)

### Stan na starcie (13:35)

`master` @ `6cee33b`, drzewo czyste. Kolektor od 2026-10-08 00:00: jeden
przebieg 13:32:31 → 13:34:03 (zaległy po wybudzeniu 13:26; `StartWhenAvailable`),
heartbeat 11:33:34 UTC `planned=[]`, `fetched=[]`, `errors=[]`, `/events` ×3
`last: 0`, `usage_remaining 497` — **0 kotwic, 0 kredytów**. Spóźnionych kotwic
poza oknem brak: `decision_due` wymaga `[08:30, 09:15)` Warszawy, `Anchor.is_due`
przycina okno do gwizdka. Migawka decyzyjna 2026-10-08 (Ekstraklasa 9.10 16:00
UTC, Bundesliga 9.10 18:30 UTC w horyzoncie 48 h) przepadła — **komputer nie
działał** (uśpienie 23:32:50 i 02:33:00, wybudzenie 13:26). Avast: od północy
zero par 106/142 dla `aluebet-odds` (106/142 o 13:32:38 dotyczą
`\SoftLanding\…`, zadania Windows).

| KOLEKTOR | kiedy (lokalnie) | stan | uwagi |
|---|---|---|---|
| luka: komputer nie działał | 2026-10-07 23:28:37 → 2026-10-08 13:32:31 | uśpienie (Kernel-Power 42 o 23:32:50 i 02:33:00), wybudzenie 13:26:29; brak zdarzeń 106/142 Avasta | przepadła migawka decyzyjna 08:30 (Ekstraklasa, Bundesliga) |
| pierwszy przebieg po wybudzeniu | 2026-10-08 13:32:31 → 13:34:03 | heartbeat `errors=[]`, `planned=[]`, `/events` ×3 `last: 0` | start 13:32:54 odrzucony (`IgnoreNew`, `0x800710E0`) — nie awaria |
| przed pełnym pytest | 2026-10-08 13:44:11 | `schtasks /query`: Ready, Next Run 13:47:53; heartbeat 11:42:56 UTC `errors=[]` | — |

### robots.txt i notes.txt football-data (13:36)

robots.txt (`data/state/robots/www.football-data.co.uk.json`, HTTP 200):
`User-agent: *` / `Disallow:` (puste) — ścieżka `/mmz4281/` **nie jest
zabroniona** dla UA projektu. Ten sam plik ma `Disallow: /` dla `Anthropic-AI`,
`Claude-Web`, `ClaudeBot`, `ChatGPT-User`, `GPTBot` i innych agentów AI —
**pytanie do Pawła** (niżej). Do tej chwili z sesji poszło jedno zapytanie o
plik: `notes.txt` (przed odczytaniem treści robots.txt), przez `HttpClient`.

notes.txt, dosłownie: „Betting odds for weekend games are collected Friday
afternoons, and on Tuesday afternoons for midweek games.” **Strefy czasowej
kolumny `Time` notes.txt nie podaje** — plan (§1) zakłada, że ją stamtąd weźmiemy:
sprzeczność planu z danymi → pytanie, nie wybór po cichu.

### Stan roboczy (aktualizowany)

| kiedy | zrobione | w toku | następny krok |
|---|---|---|---|
| 13:45 | gałąź `wip/F1-ingest`: `27f6c91` (moduł: `fin_files`, `ingest_files`, `ingest_notes`, `column_report`, `RawIntegrityError`; 13 testów na fałszywym transporcie), `1845c94` (`scripts/ingest_football_data.py`, raport `reports/ingest/<commit>/`) | — | merge na master; pytania do Pawła (robots/AI, strefa czasowa, reguła `observed_at`); prawdziwe pobranie dopiero po decyzji |
| 13:58 | pełny `pytest` (13:45 → 13:55:43): **1 failed, 890 passed** in 641 s — czerwony `test_fsa0_f12_single_raw_writer::test_every_write_site_is_registered_outside_raw` (trzy nowe miejsca zapisu poza raw: `_log_progress` → `data/state/ingest`, raport → `reports/ingest/<commit>/`); bezpiecznik zadziałał zgodnie z przeznaczeniem — wpisy dopisane do rejestru, test zielony (2 passed); `-k future_poison` 10 passed; ruff, mypy czysto; `verify_raw` OK (7 wierszy, `a099c16b…f149ec`) | merge `wip/F1-ingest` → master | Paweł uruchamia ingest; równolegle reguła `observed_at` + strefa w worktree `C:\wb-obs` |

| KOLEKTOR | kiedy (lokalnie) | stan | uwagi |
|---|---|---|---|
| luki: tryb gry Avasta (w trakcie pełnego pytest) | 2026-10-08 13:47:18–13:47:30, 13:48:44–13:48:48, 13:50:18–13:50:22 | 106 + 142 w tej samej sekundzie, 140/141 po 3–12 s | przebiegi 13:42:54, 13:47:54, 13:52:54 odbyte (heartbeat 11:42:56, 11:48:17, 11:53:04 UTC) — bez straty |

### Decyzje Pawła (2026-10-08 ~13:50), dosłownie

1. Kto uruchamia pobieranie: „Ty uruchamiasz (Rekomendowane)” — opis opcji: Paweł uruchamia `! uv run python scripts/ingest_football_data.py`; CLI analizuje raw i raport.

2. Strefa `Time`:

> Opcja 1 (test na znanych meczach) z dodatkiem: sprawdź co najmniej 4 mecze, w tym (a) letni D1 Bayern–Hertha 16.08.2019, (b) zimowy mecz z innego sezonu, (c) mecz z najstarszego i (d) z najnowszego sezonu, z ligi kontynentalnej (D1, SP1 albo I1), oraz osobno Ekstraklasę (E0/Ekstraklasa z plików "extra leagues"), jeśli ma kolumnę Time. Reguła strefy obowiązuje tylko wtedy, gdy zgadzają się wszystkie przypadki. Przy jakiejkolwiek niezgodności, zmianie formatu między sezonami albo braku kolumny Time: STOP i raport, bez zgadywania. Wynik testu (mecz, godzina z pliku, godzina rzeczywista, strefa) wpisz do docs/sources.md z cytatem.

3. Reguła `observed_at`:

> Opcja 1 (zgoda na propozycję) z warunkami: (a) liczba meczów wyłączonych przez regułę observed_at ≤ gwizdek trafia do raportu per liga i sezon, nie tylko łącznie; (b) reguła to założenie, nie fakt: wpisz do docs/sources.md cytat z notes.txt, datę i adnotację, że opis dotyczy obecnej praktyki serwisu i nie jest zweryfikowany dla starszych sezonów; (c) observed_at jest parametrem konfiguracji z jednym miejscem definicji (nie rozsiane po kodzie), tak żeby backtest dało się powtórzyć z regułą "koniec dnia 23:59 London" bez zmiany kodu; (d) w Filarze 1 po głównym przebiegu strategii A–F zrób przebieg wrażliwości z regułą 23:59 i raportuj obie liczby obok siebie, bez uśredniania.

Propozycja, na którą jest zgoda: gwizdek Pt–Pn → piątek 18:00 Europe/London; Wt–Czw → wtorek 18:00 Europe/London; mecz z gwizdkiem ≤ `observed_at` → wyłączony ze strategii przedmeczowych, z licznikiem.

### Stan roboczy (ciąg dalszy)

| kiedy | zrobione | w toku | następny krok |
|---|---|---|---|
| 14:25 | master `82f3963` (merge `wip/F1-ingest`, ff) — gotowy do pobierania, drzewo czyste. Worktree `C:\w\vb-obs`, gałąź `wip/F1-observed-at`: `75e9ae8` (`ObservedAtRule`, `pre_match_observed_at`, `kickoff_utc`, `fd_observed_at_rule` w `config/strategy.yaml` i `StrategyConfig`; testy czerwone przed łatką: import / `AttributeError` + 3× `DID NOT RAISE`), `19aa938` (raport: test strefy `Time` na 6 meczach, wyłączenia per liga i sezon dla obu reguł), `94cc1d4` (`docs/sources.md`) | czekam na ingest uruchomiony przez Pawła (o 14:21 dziennik postępu jeszcze nie istniał) | po ingeście: merge gałęzi na master, `--report-only` (bez sieci), wynik testu strefy do `docs/sources.md`; niezgodność → STOP |

### Ingest (Paweł, 2026-10-08) i integralność raw

Wynik skryptu (Paweł): `verified 6, fetched 148, missing []`, raport
`reports/ingest/82f3963/COLUMNS.md`. Sprawdzenie (CLI, 15:0x):

- `verify_raw`: **OK**; plików w raw 156 = 7 sprzed sesji (POL + E0 1920–2425) + 148 sezonów + `notes.txt`;
- **kotwica manifestu raw: 156 wierszy, sha256 `de405968ec1d1e67e3923cfe35b9bfe7030d9a21b006be6c1fa2e443e9533812`**; pierwsze 7 wierszy niezmienione (`a099c16b…f149ec`, kotwica FSA #0e); 149 nowych wpisów `recorded_by = ingest_football_data`;
- pliki sezonów: 154 = 22 x 7, każdy dokładnie raz, żaden nie jest HTML (nagłówek `Div`/`HomeTeam`/`AwayTeam`); manifest artefaktów bez zmian (2 wiersze, `a32b6be9…`).

### Test strefy `Time` na prawdziwych danych — ZGODNE WSZYSTKIE (6/6)

| przypadek | plik | w pliku | oczekiwane (London) |
|---|---|---|---|
| D1 lato, najstarszy sezon — Bayern–Hertha 16.08.2019 | D1-1920 | 19:30 | 19:30 |
| D1 zima — RB Leipzig–Bayern 20.01.2023 | D1-2223 | 19:30 | 19:30 |
| D1 najnowszy sezon — Bayern–RB Leipzig 22.08.2025 | D1-2526 | 19:30 | 19:30 |
| SP1 — Real Madrid–Barcelona 26.10.2024 | SP1-2425 | 20:00 | 20:00 |
| Ekstraklasa zima — Legia–Lech 26.10.2025 | POL | 19:15 | 19:15 |
| Ekstraklasa lato — Lech–Legia 26.04.2026 | POL | 16:30 | 16:30 |

`Time` obecne i `HH:MM` w 154/154 plikach. Reguła Europe/London obowiązuje;
źródła i cytaty w `docs/sources.md`. Wyłączenia `observed_at` (gwizdek ≤
observed_at): **1 678 z 53 331 meczów (3,1%) przy 18:00; 9 101 (17,1%) przy
23:59** — per liga i sezon w raporcie kolumn.

Pełny `pytest` na `wip/F1-observed-at` (14:5x → 15:0x): **916 passed** in 528 s.

### Stan roboczy — krok 3 Filaru 1

| kiedy | zrobione | w toku | następny krok |
|---|---|---|---|
| 15:25 | krok 2 zamknięty: merge `wip/F1-observed-at` → master (`4e5c251`, ff), worktree `C:\w\vb-obs` usunięty, raport kolumn `reports/ingest/4e5c251/` (`223cfbf`) | przegląd API toru S pod `replay.py` / `financial.py` | `backtest/replay.py` (fail-first), potem `financial.py`, `scripts/reconcile_bets.py`, testy §4 1–7 |

**Odkrycie z raportu kolumn — sprzeczność planu z danymi (pytanie do Pawła przed krokiem 5, nie blokuje kroku 3):**

- `BACKTEST_FIN_PLAN.md` §3 A: „najlepszy z B365, BW, WH (obecni we wszystkich sezonach)” — **fałsz**: William Hill nie ma w nagłówku żadnego z 22 plików 2025/26; w 2024/25 WH znika od ~2025-03-16 (pokrycie 0.753), Bet&Win od ~2025-02-03 (0.632, wraca w 2025/26: 0.992).
- Pinnacle w 2025/26: pokrycie 0.383 przed meczem, 0.388 zamknięcie — kończy się w top-ligach ok. 2026-01-08/15 (E0, D1), w mniejszych ok. 2025-10-26 (SC0, G1). Po tej dacie brak wyceny i brak CLV — silnik pominie takie mecze z licznikiem (`fair_prices`: brak migawki), ale 2025/26 to faktycznie ~0.4 sezonu.
- Pokrycie per sezon (ważone liczbą meczów): `PS_pre` 0.990–0.999 w 2019/20–2024/25; `B365_pre` ≥ 0.995 we wszystkich sezonach; `WH_pre` 0.995 → 0.905 (22/23) → 0.753 (24/25) → 0 (25/26).
| 15:27 | gałąź `wip/F1-engine`: `35285f0` replay (8 testów; na 154 plikach 51 653 mecze, 0 naruszeń porządku czasu), `b71c71a` BetJournal w pamięci (czerwony przed: 100 parsowań/100 zapisów; po ≤ 1; 98 testów dziennika bez zmian), `e0c2fd9` financial (15 testów, ręczne liczby; 2 mutacje czerwone) | `scripts/reconcile_bets.py` | testy §4 1–7 (szybkie w pytest, pełne 200 nasion w `scripts/engine_tests.py`) |

### Decyzja Pawła (2026-10-08 ~16:10), dosłownie

> Opcja 2 zaostrzona: A = najlepszy z B365 i BW tylko dla meczów z kompletem obu, reszta wyłączona z licznikiem per liga i sezon; WH poza A; osobno A3 i B365-single.

Otwarte (bez odpowiedzi): definicja A3 (propozycja: najlepszy z B365, BW i WH tylko dla meczów z kompletem u wszystkich trzech); C — próg `k_min` dla singli przy faktycznym podatku; interpretacja testu 4b.

### Incydent: bramka §4 głodziła kolektor i zapełniła dysk (2026-10-08 15:39 → 16:16)

- `scripts/engine_tests.py` (200 nasion, `multiprocessing.Pool` 8 procesów, `99a75b5`) uruchomiony 15:39 w tle; poprzednia sesja CLI zakończyła się w trakcie — procesy zostały osierocone.
- **Kolektor zagłodzony:** przebieg 15:42:54 przerwany limitem 10 min (zdarzenie 329 o 15:52:59), przebiegi 15:47 i 15:52 odrzucone (`IgnoreNew`, 322), przebieg 15:57:54 trwał do 16:06:53; heartbeat 13:37:57 UTC → 14:17:57 UTC (40 min luki). Avast: 106/142 o 15:43:15 i 15:59:39 (przywrócone po 2–5 s). Kotwic należnych w tym czasie brak (pierwsza: migawka decyzyjna 2026-10-09 08:30) — **bez utraty danych i kredytów**, `usage_remaining 497`.
- **Bramka padła 16:16** na `OSError: [Errno 28] No space left on device` przy dopisywaniu dziennika seeda (`BetJournal._append`). Wolne na C: po śmierci procesów 6,3 GB z ~150 GB. Przyczyna braku miejsca **nieustalona** (dzienniki seedów kilka MB, kasowane po seedzie; podejrzenie: pamięć 8 robotników → plik stronicowania) — do pomiaru przed kolejnym uruchomieniem.
- Próba zatrzymania procesów przez CLI odrzucona przez klasyfikator uprawnień; Paweł uruchomił `Stop-Process` — procesy już nie istniały.
- **Błąd testu 1b znaleziony przy okazji:** po wyłączniku 25% zakłady idą jako paper; oczekiwany zysk liczony ze wszystkich zakładów, zysk tylko z prawdziwych. Do poprawy (tylko `real` w obu, także obrót w yieldach).
- Wynik tej bramki nie jest używany.

Zabezpieczenia przed ponownym uruchomieniem: ≤ 3 robotników, priorytet BelowNormal, sprawdzenie wolnego miejsca (≥ 3 GB) i świeżości heartbeatu przed startem i między fazami, pomiar pamięci na jednym seedzie, bez uruchamiania w oknach kotwic.

### F1-E01 — limity 3%/15% nie obejmowały kuponów paper po wyłączniku (znalezione przez bramkę §4 pkt 6, 2026-10-08)

Pomiar jednego seeda na terminarzu E0/E1 2022/23–2023/24 (1 816 meczów): 7 120 zakładów, **285 naruszeń „mecz > 3%”**, wszystkie przy kapitale 8 051,31 zł (zamrożonym po wyłączniku 25%). Przyczyna: `financial.run` liczył `open_exposure` i `match_exposure` wyłącznie z kuponów `real`; po przełączeniu wszystkie nowe kupony są `paper`, więc limity przestawały działać. Live (`open_stake(coupons)`) liczy wszystkie otwarte kupony.

PRZED (`50ff1d1`, `uv run pytest tests/test_financial.py -k paper_bets`):

```
E       assert 289.0 <= ((0.03 * 7225.0) + 0.01)
1 failed, 15 deselected in 2.96s
```

Łatka: ekspozycja z `current` (wszystkie otwarte kupony), nie z samych `real`. PO: `tests/test_financial.py tests/test_reconcile_bets.py` 19 passed; ruff, mypy czysto.

### Stan roboczy — krok 3 (ciąg dalszy)

| kiedy | zrobione | w toku | następny krok |
|---|---|---|---|
| 16:45 | `wip/F1-engine`: `50ff1d1` (1b tylko real), `1c12ed0` (F1-E01: limity obejmują paper), `4d5555e` (perf: seed 256 s → 18 s, dziennik identyczny bajt w bajt), `a5b06be` (bramka: 3 robotników BelowNormal, kontrola miejsca i heartbeatu); worktree `C:\w\vb-sel`, gałąź `wip/F1-strategies`: `fe5cd68` (tabela strategii wg decyzji Pawła, selektor z bukmacherami per rynek i licznikiem wyłączeń; `real_totals(*, bets)` — reguła 30 złamana w `50ff1d1`, meta-test nie był uruchomiony po tamtej poprawce) | pełna bramka §4 na `a5b06be` (start 16:37, 3 robotników); kolektor w tym czasie co 5 min (heartbeat 14:37, 14:43 UTC) | wynik bramki → raport; merge `wip/F1-strategies`; strategia C i F czekają na decyzje (A3, C-single, 4b) |
### Decyzje Pawła (2026-10-08 ~16:55), dosłownie

> Decyzje: (1) A3 tak, jak zaimplementowano. (2) C single: próg k_min i rozliczenie z tego samego współczynnika podatku, z funkcji produkcyjnej; wariant dosłowny z planu (wybór 1.00 / stawka 0.94) tylko jako diagnostyka z etykietą, 0.94 jako wrażliwość; rozbieżność z planem do FIX_LOG. (3) 4b akceptuję; wzmocnij test: zbiór kandydatów identyczny po permutacji, a każda stawka zgodna ze wzorem Kelly'ego dla kapitału w danym momencie; podział real/paper może się różnić po wyłączniku. (4) F: tylko report-only, n=80 z przedziałem ufności, bez progu alarmowego, bez wpływu na bramkę i FSA #1. O/U (tylko B365) raportuj osobno od 1X2, nie łącz w jeden yield.
> Zanim pójdziesz dalej: (a) ustal, co zajęło dysk […] (b) Powiedz, co to za "2 shells still running" […] (c) Podaj stan gałęzi […] (d) Przed każdym commitem odpalaj meta-test (reguła 30). Pełnego przebiegu A-F nie startuj bez mojej akceptacji; po zielonych testach silnika zatrzymaj się i zdaj raport.

**Rozbieżność z planem (decyzja 2):** `BACKTEST_FIN_PLAN.md` §3 C — nogi value przy 1.00, single z nieparzystej reszty bez ponownego progu. Przyjęte: singiel C przechodzi `k_min` przy podatku z `BetclicTaxRegime.tax_for_single` (wariant „co jeśli”, T3) i rozliczany jest tym samym współczynnikiem; wariant dosłowny planu — diagnostyka z etykietą; stałe 0.94 dla singli — wrażliwość.

**Wyniki (a)–(c), 16:50–17:00:**

- (a) **Co zajęło dysk — ustalone:** `System`, „Application Popup” 26 o 15:48:15: „Minimalna wartość pamięci wirtualnej jest za niska”. RAM 7,8 GB; proces bramki ~600 MB prywatnej pamięci; stara bramka: 8 robotników + rodzic ≈ 5,4 GB → Windows powiększył `pagefile.sys` (przydział 8 866 MB) → brak miejsca → `OSError 28`. Repo (`.venv` 466 MB, `data` 66 MB, `.git` 7,4 MB), `%TEMP%` (< 0,5 GB) — bez znaczenia. Usunięte wyłącznie katalogi testów `%TEMP%\vb-http-*` (18 482 puste katalogi z `helpers.fake_http`, ~88 MB); nic z `data/raw`, `reports`, `.git`. Wolne na C: 5,74 GB.
- (b) **Dwa shelle w tle:** (1) bramka §4 na `a5b06be` (start 16:37, 3 robotników BelowNormal, ~600 MB każdy) — **to jest ciężki proces bramki** (testy silnika, nie przebieg A–F); kolektor w tym czasie co 5 min (heartbeat 14:48 UTC); (2) pętla `until grep exit=` czekająca na wynik — lekka.
- (c) F1-E01 (`1c12ed0`) na `wip/F1-engine` i `wip/F1-strategies`, **nie na master** (`ac28461`).

### Bramka §4 na `a5b06be` — zatrzymana przez Claude Code (brak pamięci), 2026-10-08 ~17:25

Przebieg w tle (start 16:37, 3 robotników BelowNormal, ~600 MB prywatnej pamięci na proces) zatrzymany przez Claude Code: „system is running low on memory”, razem z trzema pętlami oczekującymi. Bez raportu (`reports/backtest_fin/` nie powstał), wyniku nie ma. **Nie uruchomiony ponownie** (polecenie narzędzia: tylko na wyraźną prośbę). Po zatrzymaniu: brak procesów python, wolne RAM 1,66 GB, dysk 5,81 GB; kolektor co 5 min (heartbeat 15:23, 15:27 UTC, `errors = []`).

Wniosek: na tym laptopie (7,8 GB RAM, równolegle Claude Code i WebView ~1,3 GB) nawet 3 robotników to za dużo. Do decyzji Pawła: 1 robotnik (~600 MB, szacunkowo 2,5–3 h na całą bramkę) albo zmniejszenie pamięci procesu przed ponownym uruchomieniem.

Strategia C — wstrzymana: wariant kontrfaktyczny w `docs/promocje.md` nie ustala T12 (`min_stake_pln`, `excluded_markets`; w `config/bookmakers.yaml` oba `null`); reguła ładowacza live dla nieznanego T12 → promocja nieaktywna (0.88) → C ≡ D. Pytanie do Pawła.

### Decyzje Pawła (2026-10-08 ~17:35), dosłownie

> Decyzje: (1) Bramka: 1 robotnik, BelowNormal, uruchamiam ją sam w osobnym oknie PowerShell (poza Claude Code, żeby nie było osieroconych procesów). Nie optymalizuj pamięci teraz. Podaj: dokładną komendę, ścieżkę logu, jak odczytać wynik i czy skrypt sam ustawia BelowNormal; do końca przebiegu bez pytest i bez nowych ciężkich przebiegów, tylko lekka praca (dokumentacja, FIX_LOG). (2) C: wariant min_stake=0, bez wyłączonych rynków, z etykietą "GÓRNA GRANICA, T12 nieznane"; poza progami alarmowymi, bramką i wnioskami o rentowności; służy do mechanicznego sprawdzenia gałęzi promocji. Reguła produkcyjna zostaje pesymistyczna (podatek 0.88 przy pustych polach). Dopisz do docs/promocje.md zadanie dla mnie: sprawdzić w regulaminie min. stawkę i wyłączone rynki przed Filarem 3. (3) Jednym zdaniem: co zajęło dysk. Przebiegu A-F nie startuj bez mojej akceptacji.

Wykonane przed startem bramki: merge `wip/F1-strategies` → `wip/F1-engine` (`c6b6554`; konflikt tylko w FIX_LOG — obie części zachowane); testy celowane 50 passed (reguły 29/30, rejestr zapisów, silnik, strategie, replay, dziennik), ruff, mypy czysto; pełny `pytest` — po bramce. `docs/promocje.md`: T12 w wariancie kontrfaktycznym + zadanie dla Pawła.

### Decyzje Pawła (2026-10-08 19:25) — zmiana planu, dosłownie (skrót: kroki A–E)

> Zmiana planu, 19:25. Bramka c0f605a nie była uruchomiona (brak procesu i logu), a laptop nie uniesie bramki i pytest naraz. Nowa kolejność: wieczór = praca z pytest, noc = jedna bramka (1 robotnik, osobne okno) na finalnym kodzie. Pytest jednym procesem, bez xdist; po każdym pełnym przebiegu sprawdź heartbeat kolektora i zadanie valuebet-odds.
> A) Lekkie: (1) Alarm yield > 8% (BACKTEST_FIN_PLAN §6) obowiązuje także dla C jako detektor błędów (reguła 30); etykieta "GÓRNA GRANICA, T12 nieznane" zostaje, C poza werdyktem; zapisz w FIX_LOG i docs/promocje.md. (2) Wpis o football-data w docs/sources.md […] plan courtesy-maila skreśl. (3) FIX_LOG "Stan roboczy". […]
> B) wip/F1-observed-at […] D) Zintegruj w nowej gałęzi wip/F1-integracja (od master) […] Master NIE ruszaj, dopóki bramka nie będzie zielona (master = tylko kod po bramce). Worktree'ów dziś nie usuwaj. E) […] Jeśli o 22:30 któryś krok nie jest zielony: zostaw go na wip i przejdź do E.

**A (1):** alarm 8% dla C jako detektor błędu — `docs/promocje.md` (wariant kontrfaktyczny, T12). Do wpięcia w raport strategii (krok 5) razem z alarmami A, B, D.

**Korekta stanu do B:** `wip/F1-observed-at` jest już na master od ~15:10 (`4e5c251`, ff; pełny pytest 916 passed; test strefy 6/6 na prawdziwych danych — `docs/sources.md`, `reports/ingest/4e5c251/COLUMNS.md`), zgodnie z poleceniem Pawła z 2026-10-08 ~15:00 („scal wip/F1-observed-at na master […], usuń worktree C:\w\vb-obs”). Worktree `C:\w\vb-obs` i gałąź usunięte wtedy. Master dziś: `ac28461` (dokumenty po merge'u observed-at).

### Stan roboczy (19:3x)

| kiedy | zrobione | w toku | następny krok |
|---|---|---|---|
| 19:35 | A: `docs/sources.md` (warunki football-data, zasady, courtesy mail skreślony), `docs/promocje.md` (alarm 8% dla C) | B — pokazanie istniejącego wyniku testu strefy | C (strategia C na `wip/F1-strategies`, fail-first), D (integracja), E (komenda bramki) |

### F1-P01 — model podatku/promocji vs regulamin „Bez Podatku 2.0” (21.05.2026 v2) — OTWARTE

Odczyt CLI z PDF (2026-10-08, sha256 `22587b8a…43691b`, plik poza gitem). Rozbieżności: T2/§3 ust. 4 (zakład przekraczający limit — kod pesymistyczny wbrew brzmieniu), T10/§3 ust. 11.1 i 12 (wielokrotny niekwalifikujący się: kod 0.88, regulamin 0.94 / 1.0), T4 (udział po kuponach — margines Pawła, regulamin tylko po stawkach), T6 (różne mecze, nogi zwrócone; Cashout/edycja niemodelowane), freebety i Cashout w limicie, konfiguracja (`external_turnover_pln: null` → limit wyczerpany; [Fragment usunięty z wersji publicznej: dotyczył prywatnego konta autora i korespondencji z obsługą bukmachera.]), T12 poza dokumentem (§1 ust. 4, §8 ust. 3). Szczegóły: `docs/promocje.md` „Regulamin 21.05.2026 v2” i „F1-P01”. **Termin: przed krokiem 5 Filaru 1 (przebieg A–F).** Zakres: C i live; bramka §4 i strategie o stałym podatku — bez wpływu. Kod i `config/bookmakers.yaml` bez zmian (decyzja Pawła).

### Bramka §4 — testy 5 i 6 (PRZED/PO, reguła 31), 2026-10-08 → 2026-10-09

**PRZED — bramka na `e66260a` CZERWONA** (8.10, koniec 23:42; `reports/backtest_fin/e66260a/ENGINE_TESTS.md`, 10/12):

- test 5: `max odchylenie 1.06e-09` > tolerancja 1e-9 — szum zmiennoprzecinkowy (symulator sumuje gotówkę przyrostowo, `reconcile_bets.py` dwiema sumami; granica a priori |Δ| ≤ n·u·Σ|x| ≈ 3,6e-7 zł); księga poprawna;
- test 6: `naruszeń 1092` („otwarta ekspozycja”, pierwsze 2023-12-29 18:01: 160 × 10 zł = 1600 zł przy limicie 15% = 1184,66 zł) — sprawdzarka stosowała limity Kelly'ego do wymuszonego placebo 2b (płaska stawka poza Kelly'm); silnik poprawny.

**Poprawka (tylko `scripts/engine_tests.py`, `scripts/reconcile_bets.py`, testy):**

- `d06cda3` — księga `reconcile_bets.py` w całkowitych groszach, porównanie dokładne `round(sim·100) == grosze`, warunek wstępny „przepływ = pełny grosz”; `invariant_errors(*, limits)` wymagane, jawny znacznik `FORCED_PLACEBO_NO_LIMITS` (reguła 30), `check_six` z licznikiem migawek i maks. ekspozycją (pusta zieleń = czerwony), test trucizny: silnik bez limitu 15% łapany. Testy czerwone przed: 5 (test 6) + 5 (test 5); zielone po; pytest 976 passed;
- `2c7cc61` — sprawdzarka z własnymi literałami `CHECKER_LIMITS = (0.02, 0.03, 0.15)` zamiast importu z `pricing/kelly.py` + test równości i AST (czerwony przed: brak `CHECKER_LIMITS`); pytest 977 passed, ruff, mypy, verify_raw OK.

**PO — bramka na `2c7cc61` ZIELONA 12/12** (2026-10-09 10:15–12:29, 2 h 14 min, 1 robotnik; `reports/backtest_fin/2c7cc61/ENGINE_TESTS.md`): test 5 `niezgodnych rozliczeń 0 (porównanie dokładne)`; test 6 `naruszeń 0; migawek z limitem sprawdzonych 31000, maks. ekspozycja 15.0%`. Silnik (`backtest/financial.py`, `replay.py`), `pricing/`, `live/` i strategie bez zmian od `e66260a`.

Obserwacja do audytu 4a: test 3a yield +0,0258 vs +0,0340, SE 0,0052 (−1,6 SE, w granicy 2 SE).

**Rozstrzygnięte w audycie 4a (2026-10-10, FSA4a-03):** obciążony estymator testu, nie silnik — średnia z ilorazów zysk/obrót przy Kellym jest obciążona w dół; yield łączny na 30 nasionach 3,60% vs oczekiwany 3,40% (`reports/audit/FSA_2026-10-10_F1-4a.md`).

### Audyt 4a (2026-10-10) — decyzje Pawła i naprawy (PRZED/PO, reguła 31)

Audyt na `5831a92` (`reports/backtest_fin/5831a92/AUDIT_4a.md`, FSA skrócony `reports/audit/FSA_2026-10-10_F1-4a.md`): KRYT=0, POWAŻNE=3 (A4a-01, FSA4a-01, FSA4a-02). **Nic nie uruchomiono na prawdziwych danych — żadna decyzja niżej nie wynika z obejrzanych wyników strategii.** Decyzje Pawła (Architekt, 2026-10-10 ok. 22:10, `docs/discovery/CLI_task_audit_4a_decisions.md`), skrót:

> A4a-01 — naprawiamy, (a)+(b) z progami ustalonymi TERAZ: (a) booksum bukmachera z migawki decyzyjnej < 1.00 → bukmacher odrzucony (wypada z best-of), bez E; (b) EV przy tax 1.00 względem fair Pinnacle > 0.50 → zakład odrzucony, także E. Progi ZAMROŻONE; reguły wyłącznie z migawki decyzyjnej. FSA4a-01 — jeden punkt wejścia, niezgodna para → wyjątek. D — opcja 2: zakłady wybrane przy 1.00, rozliczone przy 0.88 (selection_tax / settlement_tax). C — poza bramką i werdyktem, „bez dowodu poprawności”; pełna ścieżka 1–7 dla C przy poprawce ev.py. FSA4a-02 — 4b i 4c porównują listę postawionych zakładów.

**Jawne odstępstwo od planu §3 (D):** plan „D: jak A, podatek 0.88”. Teraz D = zakłady A (wybór i stawka Kelly'ego przy 1.00) rozliczone przy 0.88 — kontrola podatku, nie strategia do zagrania. Uzasadnienie Pawła: przy wyborze na 0.88 zysk D byłby oczekiwany przy działającej przewadze, więc alarm „zysk w D = błąd” byłby fałszywy. Stawka D świadomie nie uwzględnia podatku rozliczenia (wyjątek od reguły 22 wyłącznie dla kontroli D; `ConstantTaxPlanner`, `strategies.py`).

**PRZED** — `tests/test_audit_4a.py` na kodzie `a494557` (testy z wywołaniami API sprzed łatki): **6 failed, 2 passed** (28 s), wszystkie czerwone z powodu zachowania (asercja / „DID NOT RAISE”), nie sygnatury:

- `test_a4a01_typo_15_instead_of_1_50_is_rejected` — selektor zwrócił kandydata z kursem 15.0;
- `test_a4a01_bookmaker_with_booksum_098_drops_out_of_best_of` — best-of wziął B365 2.12 (booksum 0.975) zamiast BW 2.06;
- `test_a4a01_ev_030_passes_and_ev_055_is_rejected` — EV +55% przeszło;
- `test_fsa4a01_mismatched_selector_and_settlement_tax_raise` — `run(tax_factor=0.88)` z selektorem przy 1.00: DID NOT RAISE;
- `test_fsa4a01_d_selects_the_same_bets_as_a` — D (selektor 0.88) nie wybrał zakładu A;
- `test_fsa4a02_engine_skipping_losing_longshots_turns_4b_red` — mutacja M6 audytora (silnik pomija przegrany kupon przy k ≥ 3): 4b ZIELONE („kandydaci identyczni: True (n=480); stawki = wzór: True”).
- Zielone przed: `test_a4a01_boundaries_are_inclusive_exactly` (przypina granice — stary kod nie odrzucał niczego) i `test_fsa4a02_engine_that_bets_differently_with_the_future_turns_4c_red` — **stara, jednokierunkowa 4c już łapie tę mutację** (różne stawki po pominięciu). Zmiana 4c na dwukierunkową nie ma więc czerwonego testu przed — to wzmocnienie, nie naprawa udowodniona testem.

**Łatka (gałąź `audit/4a`):**

- `backtest/financial.py` — `MIN_SOFT_BOOKSUM = 1.00`, `MAX_PLAUSIBLE_EV = 0.50` (Final, zamrożone); `threshold_selector(*, rejected, margin_check)` wymagane — reguła (a) po kompletności, odrzucony bukmacher poza best-of, reguła (b) przed `k_min`, licznik raz na mecz i regułę; `Selector` = protokół z `selection_tax`, `tagged_selector` dla placebo; `run(*, selection_tax_factor, settlement_tax_factor)` — niezgodność z selektorem → `ValueError`; `ConstantTaxPlanner(selection_tax, settlement_tax)`; `stake_inputs` zapisuje podatek stawki (w D ≠ rozliczeniu).
- `backtest/strategies.py` — `Strategy(selection_tax, settlement_tax, margin_check)`, D = 1.00/0.88, E bez reguły (a); `run_strategy` = jedno źródło; `selector_for(*, rejected)`.
- `backtest/strategy_c.py` — `run_regime` odrzuca selektor z podatkiem ≠ 1.00; `C_LABEL` = „GÓRNA GRANICA, T12 nieznane, nie zbadana bramką — bez dowodu poprawności”.
- `scripts/engine_tests.py` — 4b: lista postawionych (mecz, rynek, wynik, kurs) identyczna po permutacji + stawki wg wzoru (stawki w złotych zależą od ścieżki kapitału, więc porównanie co do złotówki jest tylko w 4a i 4c); 4c: lista do D z kursem i stawką identyczna w obie strony; świat bramki z `margin_check=False` (kurs (1+e)/p_true na każdym wyniku ma z konstrukcji booksum 1/(1+e) < 1), reguła (b) aktywna.
- Testy istniejące: wywołania nowego API; dwa światy `test_financial.py` z EV dokładnie 50% (`1.5/0.4`) zmienione na 45% — po rundzie Shina EV wypadało tuż ponad 0.50 i reguła (b) słusznie je odrzucała; asercje bez zmian.

**PO** — `tests/test_audit_4a.py` 11 passed (dopisane po łatce: liczniki odrzuceń, E bez reguły (a), trucizna reguł — inne zamknięcie i wynik → te same odrzucenia, C z selektorem 0.88 → błąd, D przez `run_strategy` rozliczone ×0.88); pełny `pytest` **988 passed** (9 min 22 s), `ruff check src tests scripts` czysto, `mypy src` czysto (40 plików), `pytest -k future_poison` 10 passed. **Bramka §4 NIE powtórzona** (decyzja: jutro rano na nowym hashu) — polecenie w raporcie dla Pawła.

### Bramka §4 — `preflight` bez heartbeatu kolektora (zgoda Pawła 2026-10-10)

**Powód:** od cutoveru 2026-10-10 (18:44 UTC) kolektor działa na VPS (timer systemd `valuebet-odds`), zadanie Harmonogramu na laptopie jest `Disabled`, więc lokalny `data/state/odds_api/heartbeat.jsonl` stoi na 18:37:57 UTC na zawsze. `preflight` (`scripts/engine_tests.py`) przerywał bramkę przy heartbeacie starszym niż 15 min — jutrzejsza bramka na nowym hashu zatrzymałaby się w pierwszej fazie. Sprawdzenie chroniło przed zagłodzeniem kolektora na tym samym komputerze (incydent 2026-10-08); ta przesłanka już nie istnieje. Próg wolnego miejsca (3 GB) zostaje.

- **PRZED** (`a44a869`): `tests/test_engine_gate.py::test_preflight_does_not_depend_on_a_local_collector_heartbeat` — FAILED: `RuntimeError: [start] heartbeat kolektora z 2026-10-08 … — kolektor głodzony? przerywam` (heartbeat sprzed 2 dni w katalogu testu).
- **Łatka:** usunięte `HEARTBEAT`, `HEARTBEAT_MAX_AGE` i sprawdzenie w `preflight`; docstringi.
- **PO:** `tests/test_engine_gate.py` 11 passed; `ruff`, `mypy` czysto.

### Reguła (a) A4a-01 w bramce — jawny znacznik i dowód dla przebiegu produkcyjnego (polecenie Pawła 2026-10-10)

Stan przed: `margin_check` w `threshold_selector` wymagany, keyword-only, bez wartości domyślnej — **tak**; znacznik w bramce — **nie** (gołe `margin_check=False` z komentarzem w `run_seed`, `ENGINE_TESTS.md`/`.json` bez słowa o regule (a)); test, że `run_strategy` ma (a) włączone — **nie** (tylko tabela `STRATEGIES` i `selector_for`).

- **PRZED** (`4ea3562`): `test_gate_world_disables_rule_a_only_through_the_named_marker` — FAILED (`margin_check` = literał `False`, nie nazwa znacznika); `test_engine_report_states_that_rule_a_is_off_in_the_gate_world` — FAILED (`'GATE_WORLD_NO_MARGIN_CHECK' in ENGINE_TESTS.md` → False). `test_a4a01_run_strategy_has_rule_a_on_in_production` — **zielony od razu**: kod był poprawny, brakowało dowodu (B365-single z booksum 0.975 → zero zakładów; A → BW 2.06; E/`max` → zakład; licznik `a:` dla A i B365, pusty dla E).
- **Łatka** (`scripts/engine_tests.py`): `GATE_WORLD_NO_MARGIN_CHECK = False` — jedyne miejsce wyłączenia, z uzasadnieniem (świat bramki ma z konstrukcji booksum 1/(1+e) < 1); `MARGIN_NOTE` w nagłówku `ENGINE_TESTS.md` i pola `margin_check`, `margin_note` w `.json`. Znacznik jest stałą `bool`, nie obiektem jak `FORCED_PLACEBO_NO_LIMITS`, bo `margin_check` to `bool`; nazwę pilnuje test AST.
- **PO:** `tests/test_engine_gate.py`, `tests/test_audit_4a.py`, `tests/test_rule30_guards.py` 30 passed; pełny `pytest` 992 passed; `future_poison` 10 passed; `ruff`, `mypy` czysto.
