# FIX_LOG_F1 — naprawy w Filarze 1 (wariant B, od 2026-10-11)

Specyfikacja: `docs/discovery/CLI_task_wariant_B.md` (poza gitem) i
`BACKTEST_FIN_PLAN.md` — „Zmiany 2026-10-11”. Ten plik to **twierdzenia
wykonawcy do sprawdzenia**, nie dowód (`docs/FULL_SYSTEM_AUDIT.md`).

Każdy wiersz: test regresji, wynik na kodzie PRZED łatką (czerwony z
właściwego powodu, reguła 31), commit naprawy i wynik PO. Testy uruchamiane
w worktree `value-bet-B` (gałąź `fix/F1-P01-C`) równolegle do bramki §4 na
`17a0759` — wyłącznie celowane (`pytest -q <pliki>`), zgodnie z
`CLI_task_wariant_B_rownolegle.md`.

## Tabela

| id | test | PRZED (commit, wynik) | PO (commit, wynik) | stan |
|---|---|---|---|---|
| F1-P01 pkt 1 (§3 ust. 4) | `tests/test_betclic_regime.py::test_f1p01_pkt1_any_remaining_limit_frees_the_whole_bet` | 78bb13c: FAILED — `assert 0.94 == 1.0` (900 zł obrotu + singiel 100 zł) | db4a3d9: 6 passed (`-k f1p01`), 356 passed w plikach reżimu, C, audytu 4a, regresji | naprawione |
| F1-P01 pkt 1, granica | `…::test_f1p01_pkt1_exhausted_limit_is_not_free` | 78bb13c: passed (limit wyczerpany dokładnie — zachowanie bez zmian, test pilnuje granicy) | db4a3d9: passed | — |
| F1-P01 pkt 2 (§3 ust. 11.1, 12) | `…::test_f1p01_pkt2_non_qualifying_multi_follows_the_share` | 78bb13c: FAILED — `assert 0.88 == 0.94` (wielokrotny z nogą 1.15 przy udziale 0) | db4a3d9: 6 passed (`-k f1p01`), 356 passed w plikach reżimu, C, audytu 4a, regresji | naprawione |
| F1-P01 pkt 3 (§3 ust. 5) | `…::test_f1p01_pkt3_share_by_stakes_only` | 78bb13c: FAILED — `assert 0.94 == 1.0` (po stawkach 99,8%, po kuponach 17%) | db4a3d9: 6 passed (`-k f1p01`), 356 passed w plikach reżimu, C, audytu 4a, regresji | naprawione |

Polecenie PRZED: `uv run pytest -q tests/test_betclic_regime.py -k f1p01 --tb=line`
→ `3 failed, 1 passed, 21 deselected in 1.93s`.

### Testy zmienione, bo opisywały zachowanie sprzed decyzji 2026-10-11

Nie osłabienie asercji (reguła 31) — zmiana oczekiwanej wartości zgodnie z
regulaminem; każdy nadal odróżnia ścieżkę niebezpieczną:

- `test_betclic_regime.py`: `test_t2_*` (próg osiągnięty stawką → teraz 1.00;
  test pilnuje limitu wyczerpanego przed zakładem), `test_t3_*` i
  `test_t4_*` (warunek po kuponach — teraz jawnie w wariancie wrażliwości
  `SHARE_BY_STAKES_AND_COUPONS`), `test_t8_t9_t10_tax_levels` (T10: 0.94 przy
  udziale < 50%, 1.00 w limicie), etykieta `BETCLIC_READING`.
- `test_tor_s.py::test_ako_share_is_by_turnover_not_by_count`: historia
  podniesiona z 520 do 1020 zł, żeby limit był wyczerpany przed kandydatem
  (inaczej pkt 1 daje 1.00 niezależnie od udziału).
- `regression/test_fsa0_f25_betclic_regime.py`: (a) w wariancie wrażliwości;
  (b), (d) 0.94 zamiast 0.88 — nadal „nie AKO” (AKO = 1.00).
- `RegimeConfig.share_basis` wymagane (reguła 30): dopisane w konstruktorach
  testowych; nowy test `test_f1p01_pkt3_share_basis_is_required`
  (pominięcie → `TypeError`), wartość spoza dziedziny → `ValueError`.

## Bramka §4 na 17a0759 — przerwana (2026-10-11)

Bramka 17a0759 przerwana bezpiecznikiem dysku 2026-10-11 14:44 w 2b
(seed 17), zastąpiona bramką wariantu B. Traceback:
`RuntimeError: [seed 17] wolne miejsce 2.04 GB < 3 GB`
(`docs/discovery/gate_error.txt`, poza gitem). Nie błąd silnika — spadek
miejsca przez równoległy worktree (.venv, cache) i plik wymiany. Decyzja
Pawła (dopisek 2, 14:55): 17a0759 nie jest powtarzana; nowa bramka na hashu
wariantu B obejmuje A i C. Bramka dostaje postęp, wyniki cząstkowe i
`--resume` (krok 2.5).

## 2.3 — kapitał live, kapitał backtestu, minimalna stawka (decyzja Pawła 2026-10-11)

| zmiana | test | PRZED | PO |
|---|---|---|---|
| `config/live.yaml` `bankroll_pln: 1000`, `config.load_live` | `test_config.py::test_live_bankroll_*`, `test_bad_live_config_*` | f9fa69f: ImportError (`LIVE_PATH`, `load_live`) | zielone |
| backtest 10 000 zł (`strategy.yaml` `backtest_start_capital_pln`, `engine_tests.START`) | `test_backtest_capital_stays_10000_*` | f9fa69f: ImportError | zielone |
| min. stawka 0,50 zł we wszystkich strategiach; `kelly.meets_min_stake`; `simulate/run/run_strategy/run_regime(min_stake_pln=…)` wymagane; licznik `SKIP_BELOW_MIN_STAKE` | `test_financial.py::test_stake_below_min_stake_*`, `test_min_stake_check_*`, `test_run_requires_*` | f9fa69f: TypeError (`min_stake_pln`), ImportError | zielone |
| T12 w `bookmakers.yaml` (`0.50`, `[]`), reszta `null` | `test_min_stake_is_050_*` | f9fa69f: AttributeError | zielone |
| C: etykieta „kontrfaktyczny reżim Betclica…”, `min_stake_pln = 0.50` | `test_strategy_c.py::test_counterfactual_*` | f9fa69f: asercja 0.0 ≠ 0.50 | zielone |

PRZED łącznie: `32 failed, 19 passed` (`test_config`, `test_financial`,
`test_strategy_c`); PO: `83 passed` (te + reconcile, strategies, audit_4a,
reguły 29 i 30).

## 2.2 + 2.5 — bramka §4 obejmuje C; postęp, wyniki cząstkowe, --resume, PAPER (2026-10-11)

Nowa funkcjonalność bramki, nie naprawa znaleziska — testy pisane razem z
kodem, każdy sprawdza też ścieżkę niebezpieczną (reguła 30):

| element | test (pytest, świat syntetyczny) | ścieżka niebezpieczna |
|---|---|---|
| testy 1–7 C w `gate` | `test_gate_covers_every_point_of_section_four` (1a-C…6-C, 7 ze szpiegami C) | — |
| niezależny checker reżimu (`RefRegime`, literały) | `test_reference_regime_catches_an_engine_that_ignores_the_share` | silnik dający 1.00 każdemu singlowi → `tax_errors` niepuste |
| 3c-C przejścia reżimu | `test_regime_transitions_are_green_and_catch_a_wrong_threshold` | próg 0.51 → czerwony |
| reconcile niezależny od wyceny | `test_reconcile_is_independent_of_pricing` (AST: brak importu `valuebet`) | — |
| wyniki cząstkowe + `--resume` | `test_interrupted_and_resumed_gate_gives_the_same_report` | przerwanie po 7 przebiegach → wznowienie daje identyczne checki |
| odmowa wznowienia | `test_resume_refuses_other_commit_seeds_or_params_and_needs_the_flag` | inny commit / liczba nasion / parametry / brak flagi → odmowa |
| PAPER raz na przebieg | `test_financial.py::test_paper_message_is_logged_once_per_run_with_a_counter` | wyniki identyczne przy DEBUG i ERROR |
| preflight 8 GB, komunikat 3 GB z `--resume` | `test_preflight_start_requires_eight_gigabytes_and_mid_run_message_mentions_resume` | 7 GB → odmowa startu |
| `--raw-root` tylko odczyt | `test_gate_reads_raw_only_through_the_given_root` | brak plików → błąd, katalog nie powstaje |

Pomiar na terminarzu bramki (1 nasiono, 1 proces, maszyna bez bramki):
A `full` 68 s; C `c120` 157 s (4503 kupony, 4382 dublety, 0 błędów podatku);
C `solo` e = 0.10: 16 s (571 singli po 0.94); wymuszone placebo C na `c120`:
562 s (8665 singli) — dlatego 2b-C liczone na świecie `solo` (w placebo
dublety nie powstają w żadnym świecie: EV dubletu 0.95² − 1 < θ; ta sama
ścieżka kodu, ~16 s/nasiono).

## 2.4 — runner kroku 5 `scripts/run_backtest_fin.py` (2026-10-11)

Nie uruchamiany na prawdziwych danych. Przebiegi zamrożone w `run_specs`
(główne θ = 0.02: A, A3, B365, B-BW, B-WH, C, D, E, F; wrażliwość θ ∈ {0.01,
0.03, 0.05}, C po stawkach i kuponach, kapitał 1000 zł dla A i C, wariant bez
wyłącznika dla A i C). Werdykt w trzech częściach, rekomendacja dla Filaru 2,
alarmy §6 (zysk D, yield > 8% w agregacie i grupach A/A3/B/C/D/F) i
niezgodność z `reconcile_bets.py` → kod wyjścia 2, raport bez wniosków.
Tabela per liga dla A i C (reguła wyboru lig do Filaru 2 — hipoteza).

Testy (`tests/test_run_backtest_fin.py`, świat syntetyczny): znana odpowiedź
(CLV każdego zakładu A = e, D = e·0.88), alarm D przy wymuszonym zysku,
zapis wyłącznie do katalogu raportu (`RawStore.write_raw` zablokowany,
`data/bets/bets.csv` nietknięty), szpiedzy funkcji produkcyjnych
(`simulate`, `fair_prices`, `KellyPolicy.from_journal`,
`BetclicTaxRegime.tax_for_multi`), plan przebiegów, werdykt §6, ścieżka bez
alarmu. Reguła 29: `backtest/strategies.py` i `backtest/strategy_c.py`
podłączone (zdjęte z `PENDING_WIRING`; ROADMAP §2, CLAUDE.md „Układ”).

Uwaga z testu: na świecie syntetycznym ~150 kuponów yield C wyszedł +11,6%
(oczekiwane ~5%, dublety o kursach ~4–5) i alarm 8% zadziałał — to szum
małej próby, alarm działa zgodnie z §6 (detektor, nie werdykt).

## Dopisek 3 (2026-10-11 16:10) — katalog tymczasowy na D:, progi miejsca

`engine_tests.py`: katalog tymczasowy z TEMP/TMP wypisany na starcie;
preflight ≥ 6 GB na dysku repo i ≥ 10 GB na dysku katalogu tymczasowego;
bezpiecznik w trakcie < 3 GB na którymkolwiek → stop z komunikatem o
`--resume` (niczego nie kasuje); linie postępu z wolnym miejscem obu dysków.
Test: `test_preflight_checks_repo_and_temp_disks_and_mid_run_message_mentions_resume`
(6/10 GB przechodzi; 5,9 GB repo, 9,9 GB tmp, 2,9 GB w trakcie na każdym
z dysków → odmowa). Praca CLI w worktree z `UV_CACHE_DIR=D:/uv-cache`
(w poleceniach, bez zmiennej użytkownika). Pliku wymiany nie ruszano.

## Audyt `backtest-auditor` na `master..fix/F1-P01-C` (2026-10-11): KRYT=0, POWAŻNE=3, DROBNE=7

| id | znalezisko | test regresji | PRZED (850888e) | PO | stan |
|---|---|---|---|---|---|
| AB-1 POWAŻNE | bramka nie sprawdza reżimu C w paśmie udziału ~50% (c120: udział wysoki, solo: 0); okno 12 mies./5000 i kolejność kandydatów bez kontroli | `test_band_world_catches_regime_mutations[AKO_SHARE_THRESHOLD-0.45]`, `[AKO_WINDOW_MONTHS-3]`, `test_band_world_puts_coupons_near_the_share_threshold` | AttributeError (`band_truth` — świata pasma nie było); po dodaniu świata mutacja okna NIE wykryta — tolerancja „cykl pesymistyczny” ukrywała 6 błędów w dół | 3d-C: świat `band` (migawki 1 mecz / 4 mecze, e = 0.10), single i po 1.00, i po 0.94, 60 kuponów w paśmie; tolerancja cyklu tylko gdy checker przy stawce liczonej przy 1.00 daje 0.94 (DROBNE 8); obie mutacje wykryte | naprawione |
| AB-2 POWAŻNE | `--resume` nie wiąże wyników z danymi (inne `--raw-root` → raport z dwóch światów) | `test_resume_refuses_results_from_another_world` | DID NOT RAISE | `world_digest` (sha256 terminarza) w każdym pliku cząstkowym i w ENGINE_TESTS.json; inny świat → `ResumeRefusedError` | naprawione |
| AB-3 POWAŻNE | `RunSpec.main` z domyślnym `False`, alarm yieldu z białej listy nazw (reguła 30) | `test_run_spec_flags_are_required_and_alarm_follows_the_flag` | stary kod: `RunSpec(...)` bez `main` przechodzi; `alarms()` dla nowej strategii z yieldem 20% → `[]` | `main` i `alarm` wymagane, keyword-only; alarm z flagi; alarm yieldu także na przebiegach wrażliwości (DROBNE 10); alarm D po strategii, nie nazwie | naprawione |
| AB-6 DROBNE | min. stawka C z dwóch źródeł | `test_strategy_c.py::test_run_regime_refuses_two_different_minimum_stakes` | DID NOT RAISE | `ValueError` przy rozjeździe | naprawione |
| AB-8 DROBNE | tolerancja checkera ukrywa błędy w dół | jak AB-1 | jw. | jw. | naprawione |
| AB-10 DROBNE | wrażliwość bez alarmu yieldu | jak AB-3 | — | alarm także na wrażliwości | naprawione |
| AB-4 DROBNE | T3: `promocje.md` mówi (kickoff, mecz, rynek, wynik), kod sortuje single po EV (plan §3) | — | — | — | **do decyzji Pawła** (który dokument obowiązuje) |
| AB-5 DROBNE | CLV kuponu: plan `Π(k·p_close) − 1`, kod `· tax` (ostrzejszy) | — | — | — | **do decyzji Pawła** (dokumentacja przed werdyktem C) |
| AB-7 DROBNE | PAPER na DEBUG w `kelly.py` (live nie zobaczy); kolejne wejścia w PAPER | — | — | — | otwarte: wejście jedno na przebieg (PAPER nie wraca do real, ROADMAP §2); ostrzeżenie live — przy podłączaniu `digest.py` (Filar 2) |
| AB-9 DROBNE | w C stawka < 0,50 zł odpada jako „poza progiem po podatku” (0.88), nie `SKIP_BELOW_MIN_STAKE`; próg 0,50 może dać fałszywą czerwień 4b | — | — | — | **zamknięte** — naprawa `8d63a12` (2026-10-12, sekcja „Naprawa 4b-C i AB-9”); bramka `27ae469`: 24/25, a jedyna czerwień 4b-C (remis zaokrąglenia, nie AB-9) zamknięta rerunem 4b-C na `737a111` (2026-10-15) |

Weryfikacja po naprawach audytu: pełne `pytest` → 1034 passed, 2 failed
(`test_deterministic_points_are_green`: 3d-C czerwone na za małym świecie
fixture — 25 meczów w `band`, single tylko po 0.94, osłona przed pustą
zielenią zadziałała; `test_interrupted_and_resumed_*`: stary napis „wolne C:”
w asercji). Naprawa testów: fixture 30 tygodni zamiast 10, asercja na nowy
format postępu → `tests/test_engine_gate.py` 25 passed. `-k future_poison`:
10 passed. Świat `band` na prawdziwym terminarzu bramki (3 nasiona, przed
bramką): 280 meczów, single 1.00 / 0.94 ≈ 165 / 90, ~230 kuponów w paśmie
[0.40, 0.60], 0 błędów podatku. ruff, mypy strict — czysto.

## Decyzje Architekta do AB-4 i AB-5 (dopisek 4, 2026-10-11 17:20) — tylko dokumentacja

- **AB-4 (kolejność singli w T3):** obowiązuje plan §3 — single wg EV
  malejąco, potem `match_id`; to też polityka live (przegląd dnia sortowany po
  EV). `docs/promocje.md` T3 poprawiony: kolejność realnego klikania zależy od
  Pawła i nie jest modelowana; wrażliwość na kolejność niewyliczana. Kod bez zmian.
- **AB-5 (CLV kuponu):** obowiązuje kod — CLV kuponu = `Π_i (k_i · p_close_i) · tax − 1`
  (po podatku reżimu), jak CLV singla i test 1a. `BACKTEST_FIN_PLAN.md`
  („Zmiany 2026-10-11”) poprawiony z adnotacją „korekta 2026-10-11 17:20, PRZED
  jakimkolwiek wynikiem, zgodność z kodem (AB-5)”. Bez dodatkowego kodu ani
  raportu CLV przed podatkiem.
- **AB-7, AB-9:** otwarte — wpis w `ROADMAP.md` §2 („DROBNE po wariancie B”).

## F1-P02 — okno udziału AKO (T14) vs kod (OTWARTE, 2026-10-11, tylko dokumentacja)

[Fragment usunięty z wersji publicznej: dotyczył prywatnego konta autora i korespondencji z obsługą bukmachera.]
Okno 5000 / 12 miesięcy
dotyczy wyłącznie udziału AKO (§3 ust. 8 → ust. 5), nie limitu 1000 zł.
Kod NIE liczy udziału skumulowanie — `BetclicTaxRegime.window()` stosuje okno
(od `join_date`, po 12 miesiącach 12 miesięcy wstecz, ≤ 5000), bramka sprawdza
je niezależnym checkerem (3d-C). Zostają: (1) `external_turnover_pln` stale w
mianowniku (pesymistycznie; ~0,4 pkt proc. udziału w świecie bramki, kilka
pkt proc. w wariancie 1000 zł); (2) po 12 miesiącach kod stosuje 12 miesięcy
**i** ≤ 5000, regulamin i odpowiedź sugerują samo 12 miesięcy (różnica tylko
przy > 5000 kuponów w 12 miesiącach; w świecie bramki ~2250 — bez skutku);
(3) `join_date` live = null. Rząd wielkości dla prawdziwych danych nie do
oszacowania bez uruchomienia strategii. Szczegóły i propozycja:
`docs/promocje.md` F1-P02. Decyzja: Architekt/Paweł. Kod bez zmian.

**ZAMKNIĘTE decyzją Architekta 2026-10-11** (podjętą PRZED jakimkolwiek
wynikiem strategii; zapis po zielonej bramce §4, 2026-10-16). Regulamin Bez
Podatku 2.0 (21.05.2026 v2), §3 ust. 8, dosłownie: „Udział, o którym mowa w
ust. 5, oblicza się z uwzględnieniem ostatnich 5000 (pięć tysięcy) Zakładów
zawartych przez Użytkownika od dnia przystąpienia do Oferty, z tym że po
upływie 12 miesięcy od tego dnia uwzględnia się wyłącznie Zakłady zawarte w
okresie ostatnich 12 miesięcy, liczonym na zasadzie kroczącej.”

- Interpretacja: „z tym że” jest zastrzeżeniem do reguły 5000 zakładów — po
  12 miesiącach obowiązują **oba** warunki (ostatnie 5000 zakładów, z których
  liczą się tylko te z ostatnich 12 miesięcy). Tak robi
  `BetclicTaxRegime.window()`.
- Kod **bez zmian** (zgodny z literą regulaminu).
- Rozbieżność mianownika (pkt 1: `external_turnover_pln` stale w mianowniku)
  **zostaje** — kierunek pesymistyczny, konserwatywny.
- F1-P02 nie blokowało bramki §4.

## Naprawa 4b-C i AB-9 (2026-10-12) — reguła 31

| element | PRZED | PO |
|---|---|---|
| 4b-C | bramka `2624fff` CZERWONA tylko w 4b-C („kupony identyczne: False”, nasiona 1 i 2, pierwsza różnica na kuponie 2325); diagnoza `docs/discovery/out_B/diag_4bC.md`: klasa (A) — wyniki → kapitał → stawka < 0,50 zł → reżim 0.88 → grupa odrzucona, lista przesunięta o 1 | bramka `27ae469` (nowe kryterium ścieżki, BACKTEST_FIN_PLAN §4): 24/25 OK; 4b-C czerwone już nie z powodu #1 (lista kuponów), lecz przez remis zaokrąglenia na c0-004274 — 4b-C #2, sekcja niżej; po naprawie #2 rerun 4b-C na `737a111` (tryb `--only`) **ZIELONY**, niewyjaśnionych 0 — **zamknięte 2026-10-15** |
| AB-9 | odrzucenie przy stawce < 0,50 zł w C liczone jako „kupon poza progiem po podatku”, bez nazwanej przyczyny; testy `test_ab9_*` na `2624fff`: 2 failed (ImportError — brak `DROP_BELOW_MIN_STAKE`/`dropped_groups`) | `financial.py`: `RunResult.dropped_groups` (przyczyna z listy zamkniętej, kapitał, stawka, tryb), licznik C → `SKIP_BELOW_MIN_STAKE`; testy zielone |
| dowód „czysto obserwacyjnie” | odcisk PRZED (sha256: kupony, stawki, tryb, kapitał, P&L) na 17 przebiegach: early i c120-early × A, C × nasiona 1–3, c120 C nasiona 1–2, c120 C spermutowane nasiona 1–2, wymuszony (kapitał 100 zł) | odcisk PO identyczny bit w bit we wszystkich 17; odrzuceń ścieżką „stawka < 0,50 zł” (zewnętrzny szpieg) PRZED = PO = wpisy `STAWKA_PONIZEJ_MINIMUM`: 1 / 1 / 137; liczniki A bez zmian |
| rozmiar | — | `c120`, C, nasiono 1: 70 wpisów (STAWKA_ZERO); `RunResult` +9 KB, `SeedRun` z detalem +41 KB (bez detalu +0 B); szczyt RAM 213 → 212 MB; cała bramka ≈ +1,4 MB danych cząstkowych |
| czułość kryterium | — | `tests/test_gate_4bc.py`: planista zaglądający w wynik → wyjście różne w 17 z 45 grup (test czystości czerwony); przeciek → 21 niewyjaśnionych; fałszywa przyczyna → 21 × „STAWKA_PONIZEJ_MINIMUM niepotwierdzona” |
| uczciwy przebieg, świat `c120` (bramka), nasiona 1 i 2 | stare kryterium: CZERWONE | nowe 4b-C: ZIELONE, niewyjaśnionych 0; nasiono 1: PAPER 3476, STAWKA_PONIZEJ_MINIMUM 1, STAWKA_ZERO 50; nasiono 2: STAWKA_PONIZEJ_MINIMUM 1; audyt ścieżki (stawka = Kelly z księgi, tryb = obsunięcie z księgi): 0 błędów; odrzucenia potwierdzone 113/113 i 71/71 |

## Naprawa 4b-C #2 — remis zaokrąglenia (2026-10-15) — reguła 31

Diagnoza `docs/discovery/out_B/diag_4bC_2.md` (poza gitem): klasa A. Kupon
c0-004274 — wiąże limit 15% ekspozycji, surowa stawka dokładnie 5,825 zł;
silnik (`cash + open_real` = 15467.100000000042) → 5,83, checker z księgi
(15467.099999999997) → 5,82; Δ kapitału 4,5e-11 (kolejność sumowania floatów).
Decyzja Architekta: naprawa wyłącznie w `scripts/` i `tests/`; src/ i config/
bez zmian (`git diff 27ae469 -- src config` pusty przed i po commitach).

| element | PRZED | PO |
|---|---|---|
| 4b-C #2 | bramka `27ae469`: 24/25, 4b-C CZERWONE — 1 niewyjaśniona: c0-004274 stawka 5.83 vs wzór z księgi 5.82 | `737a111`: reguła remisu (surowa stawka < 1e-6 zł od x.xx5 → którykolwiek z dwóch sąsiednich groszy; poza remisem równość) + twardy warunek |Δ kapitału| < 1e-6 dla każdego kuponu i wpisu odrzucenia (dotąd: kupony bez sprawdzenia wprost, wpisy 0,005 zł); rerun `--only 4b-C` na `737a111` (`reports/backtest_fin/737a111/ENGINE_TESTS_4bC.md`): **ZIELONE**, niewyjaśnionych 0; 20/20 przebiegów z audytem; kuponów 89 958, remisów 28, zaakceptowanych dzięki remisowi 1 (c0-004274), odrzuconych 0, max |Δ kapitału| 6,548e-11 |
| czerwone testy, krok 1 | `tests/test_gate_4bc_tie.py` na `27ae469`: 15 failed, 1 passed — m.in. `test_path_audit_accepts_the_other_grosz_at_a_tie` (AssertionError: „stawka … vs wzór z księgi …”), reszta AttributeError (brak `stake_verdict`, `kelly_expected_raw`) | 16 passed |
| czerwone testy, krok 3 (tryb częściowy) | `tests/test_engine_partial.py`: 6 failed (strażnik diffu src/config, `--only` tylko 4b-C, `--only` + `--resume` odmowa, osobny raport z nagłówkiem, zgodność przebiegów z pełną bramką) | 6 passed; testy dotknięte zmianą: 103 passed |
| zmienione definicje w `scripts/engine_tests.py` vs `27ae469` (AST) | — | **współdzielone:** `SeedRun` (+pole `path_stats`, domyślnie `()`), `run_seed` (+przekazanie statystyk `path_audit`); poza tym `path_audit` (zwraca 3. wartość `PathAuditStats`; `check_drop` z regułą remisu i progiem 1e-6), `check_4b_c` (statystyki w raporcie; zielone tylko przy audycie we wszystkich przebiegach), `main` (`--only`); nowe: `kelly_expected_raw`, `is_tie`, `stake_neighbours`, `stake_verdict`, `StakeVerdict`, `PathAuditStats`, `REF_TIE_PLN`, `REF_CAPITAL_TOL`, tryb częściowy (`PARTIAL_*`, `PartialRunRefusedError`, `src_config_diff`, `require_unchanged_src`, `gate_4bc_only`, `run_partial`, `main_partial`); `kelly_expected_stake` nietknięty (wspólny z 6-C) |
| dowód zakresu (AST) | — | `.path_stats` odczytywane WYŁĄCZNIE w `check_4b_c` (`scripts/engine_tests.py:1414`); pozostałe wystąpienia: definicja pola (`:354`), zapis w `run_seed` (`:436`, `:442`, `:464`). `check_4b_c` wołane przez `gate_c`, `gate_4bc_only` i `tests/test_gate_4bc.py` |
| dowód obojętności (bit w bit) | — | stary runner (`27ae469`) vs nowy na tym samym src/: early i c120-early × A, C × nasiona 1, 2 — **8/8 identycznych** (25 pól `SeedRun` poza `path_stats`; w C z audytem — `path_errors`, `dropped` = dwie pierwsze wartości `path_audit`). Przebieg dodatkowy c120-early, C, nasiono 1, wyniki spermutowane: jedyna różnica `path_errors` — stary `c1-001166: stawka 21.8 vs wzór z księgi 21.81`, nowy pusty (1 remis zaakceptowany, 0 odrzuconych, max |Δ kapitału| 3,5e-11). Interpretacja (Architekt 2026-10-15): **zamierzona zmiana oceny remisu**, drugi przypadek klasy A, nie skutek zmian w `SeedRun`/`run_seed` |
| lista remisów rerunu (diagnostyka poza repo, te same 20 przebiegów) | — | 28 remisów kuponów: 15 w 4-base-C, 13 w 4b-C; wszystkie |Δ kapitału| ≤ 4,6e-11; 27 ze stawką silnika = `round` checkera, 1 (4-base-C, nasiono 0, c0-004274: surowa 5.824999999999034, silnik 5.83, checker 5.82, Δ 4,5e-11) zaakceptowany dzięki remisowi. Wpisy odrzucenia przy remisie: STAWKA_ZERO z surową 0,00499999… zł (4b-C nasiona 0, 2, 5) — potwierdzone także bez reguły remisu (`round` = 0,00). Kontrola: remisy zapisane = `path_stats` w 20/20 przebiegach |

Dowody poza gitem (`<user>\Desktop\value-bet\docs\discovery\out_B\`):
`equiv_proof.py`, `equiv_proof.out`, `equiv_detail.out`, `path_stats_ast.py`,
`path_stats_ast.out`, `tie_list.py`, `tie_list.out`, `tie_list.json`.
Pełna lista 28 remisów (nasiono, przebieg, kupon, surowa stawka, silnik,
checker, Δ kapitału) — `tie_list.out`.

Poza zakresem (decyzja Architekta, bez działania teraz): zaokrąglenie stawki
przy wiążącym limicie (`pricing/kelly.py:279,302`, remis w górę = ekspozycja
15,00003%) — DROBNE w `ROADMAP.md` §2, naprawa przed Filarem 3 + pełna bramka.

## F1-E02 — etykieta bukmachera w nogach dubletu C (2026-10-16) — reguła 31

Znalezione przez **oficjalny przebieg kroku 5** na `77abbb7` (start 16:38:34,
`--workers 0`): po 7/38 przebiegach (A, A3, B365, B-BW, B-WH, D, E), ok. 17:31:13,
przebieg C przerwał się wyjątkiem `ValueError: kupon C-000008: nogi różnią się
polem bookmaker` (`live/bets.py:267`, `_check_legs`). Stało się to **PRZED
jakimkolwiek wynikiem**: nie powstał RAPORT.json/.md ani werdykt, nikt nie widział
wyników strategii. Pliki przerwanego przebiegu zarchiwizowano bez otwierania (`D:\vb-backup\backtest_77abbb7_crash_2026-10-16\`,
15 plików / 10 987 789 B, sha256 zgodne) i usunięto z repo. Diagnoza:
`docs/discovery/out_B/RAPORT_diagnoza_crash_C.md` (poza gitem). To nie jest
strojenie: nie zmieniono żadnego parametru, a przebieg zostanie powtórzony w
całości na nowym commicie.

Przyczyna: `backtest/financial.py:337-344,365` — `Candidate.bookmaker` = bukmacher
z najlepszym kursem spośród `books[rynek]`; C bierze książki A
(`scripts/run_backtest_fin.py`, `STRATEGIES["A"].books`: 1X2 bet365/betandwin,
O/U bet365). `financial.py:655` przepisuje go na każdą nogę, a parowanie
(`backtest/strategy_c.py:127-143`) bukmachera nie widzi → dublet z nogą BW i nogą
B365. `_check_legs` (`live/bets.py:258-273`) słusznie wymaga jednego bukmachera na
kupon. Pole nie wpływa na żadną decyzję: `financial.py:655` to jedyny odczyt
`Candidate.bookmaker`, a `Coupon.bookmaker` nie czyta nikt (limity, reżim
Betclica, rozliczenie, CLV, `reconcile_bets.py`).

Luka testowa: wszystkie światy syntetyczne miały jednego miękkiego bukmachera
(`scripts/engine_tests.py:108` `SOFT="bet365"`, `test_strategy_c.py`,
`test_financial.py`, `test_engine_gate.py`, `test_gate_4bc.py`), a świat
`test_run_backtest_fin.py::_world` — czterech z IDENTYCZNYMI kursami (ścisłe `>`
→ zawsze bet365). Nie istniał żaden test dubletu z nogami od różnych bukmacherów.

Decyzja Architekta 2026-10-16: opcja (a) — jednolita etykieta wyłącznie w
`scripts/` (src/ i config/ bez zmian, `git diff 27ae469 -- src config` pusty
przed i po; bramka §4 `27ae469` + `737a111` obowiązuje). Opcja (b) (parowanie
tylko u jednego bukmachera) odrzucona — zmienia zamrożoną konstrukcję C. Opcja
(c) (etykieta z planisty w src/) — DROBNE w `ROADMAP.md` §2.

| element | PRZED | PO |
|---|---|---|
| test regresji `tests/test_run_backtest_fin.py::test_c_doubles_with_legs_from_different_books_get_one_label` (świat `_two_book_world`: B365 i BW o różnych kursach 1X2, na przemian po `match_id` w chwili decyzji) | `77abbb7`: **FAILED** — `ValueError: kupon C-000002: nogi różnią się polem bookmaker` (`live/bets.py:267`, przez `execute` → `run_regime` → `simulate:675` → `add_coupon`) | **passed** |
| naprawa `scripts/run_backtest_fin.py` | — | stała `C_BOOKMAKER = "betclic"`; w `execute` (gałąź C) selektor `threshold_selector` (argumenty bez zmian) owinięty przez `financial.tagged_selector` z `replace(c, bookmaker=C_BOOKMAKER)` i `selection_tax=best_of.selection_tax` (1.0); gałąź nie-C nietknięta |
| dowód obojętności dla decyzji (`docs/discovery/out_B/proof_c_label.py`, poza gitem): runner z `77abbb7` vs nowy, świat `_world` (jeden efektywny bukmacher), ten sam spec | — | C przy value 1.025, C i C@θ0.05 przy value 1.06: **3/3 OK** — dziennik 284/284, 286/286, 286/286 wierszy, wszystkie kolumny równe poza `bookmaker` (bet365 → betclic) i `ingested_at` (`datetime.now` w `execute`); equity.csv bajt w bajt; `n_coupons` 72/72, 74/74, 74/74; `skipped`, `dropped_groups`, `excluded`, `rejected`, `stake_inputs` równe; dubletów 70, 69, 69 |
| testy lekkie | — | `test_run_backtest_fin.py`, `test_strategy_c.py`, `test_financial.py`: 41 passed; ruff check czysto |
| mypy (`uv run mypy <plik>`) | skrypt 18, test 10 (wszystkie zastane: `import-untyped`/`import-not-found`) | skrypt 18, test 10 |
| `ruff format --check` | oba pliki „would be reformatted” na `77abbb7` (zastane) | bez nowych pozycji — nowe długie linie z `# fmt: skip`, jak w pliku |

## 2026-10-18 — Alarm przebiegu oficjalnego 4599dca: ZAMKNIĘTY (decyzja Pawła)

- Przebieg: commit 4599dca, 38/38, 2026-10-18 12:16:20–15:37:47, kod wyjścia 2. 41 linii alarmu „yield > 8%” (m.in. C agregat +16,11%, A3 agregat +9,64%, B-BW agregat +18,77%, B-WH agregat +11,44%, F +78,48%).
- Diagnoza: docs/discovery/out_B/RAPORT_diag_alarm.md (diag_alarm.py, ziarno 20261018). Rekonstrukcja z dzienników = RAPORT.md co do grosza (7 przebiegów). K2: |z| ≤ 2 we wszystkich 7 przebiegach (zgodne z losowością). K4: 0 niezgodności (100 kuponów, 117 nóg). K5: decyzja wyłącznie z kolumn przedmeczowych, 0 decyzji po gwizdku. K7: A–A3 91%, A–B-BW 99% wspólnych zakładów, 99,1% nóg C to zakłady A.
- Przyczyna alarmu: wariancja i koncentracja zysku, nie defekt. K3: 10 największych zysków = 56% zysku A (bez nich yield +3,2%), 39% A3 (+6,0%), 110% C (−1,6%). Yield oczekiwany przy decyzji (A +6,18%) > CLV (A +1,97%).
- Ograniczenia danych (analiza Architekta 2026-10-18, pliki football-data z data/raw): kursy Pinnacle znikają od XI 2025 — sezon 2025/26: 38% meczów z kursem przedmeczowym Pinnacle, 39% z zamknięciem, od II 2026 0%. Bwin brak w ok. 37% meczów 2024/25 (A wymaga kompletu → mecze wypadają). William Hill brak w całym 2025/26. Spadek liczby zakładów A (622 → 110 na sezon) jest w dużej części artefaktem pokrycia danych. Spadek CLV A po sezonach (ok. +2,6% w 2019–23 → ok. +1,0% w 2023–25) jest realny; 2025/26 niemiarodajny (n = 110, ok. 4 miesiące danych).
- Wynik mechaniczny §6 (θ = 0,02, 10 000 zł): A — CLV +1,97% [+1,52; +2,42], yield +7,24% → kryteria POTWIERDZONA spełnione. C — CLV +3,76% [+2,87; +4,64], yield +16,11% → kryteria spełnione. B-* tylko raport (CLV z dolną granicą CI > 0 we wszystkich trzech). D traci (yield −13,95%, wyłącznik 2020-01-31) — zgodnie z oczekiwaniem.
- Zastrzeżenia do werdyktu: koncentracja zysku C; malejące CLV; luka danych 2025/26; C zakłada kursy Betclica ≈ max(B365, BW) — niezweryfikowane (marża 1X2 Betclica z 11 ręcznych odczytów 11.10: 7,34%; Pinnacle w naszych migawkach: 4,4% PL, 5,0% Ekstraklasa).
- Werdykt formalny Filaru 1 (krok 6 planu): po FSA #1, zgodnie z kolejnością planu.
- Decyzja Pawła 2026-10-18: alarm zamknięty jako „wariancja i koncentracja, bez defektu”.

## 2026-11-13 — FSA #1 zaakceptowany, werdykt Filaru 1

FSA #1 zakończony 2026-11-13, BRAMKA KRYT=0 POWAŻNE=0, akceptacja Pawła 2026-11-13. WERDYKT FILARU 1: A — POTWIERDZONA w sensie §6 (CLV +1,97% [+1,52; +2,42]; odporne na metodę: potęgowa +1,52% [+1,05; +1,98]); zastrzeżenie audytu: wynik mechaniczny, nie dowód przewagi dziś (CLV 2025/26 ≈ 0, ceny zastępcze). C — §6 spełnione formalnie, wynik kruchy (CI yieldu [−1,17; +36,0], 10 wygranych = 110% zysku). D traci (kontrola podatku). Filar 1 ZAMKNIĘTY. Filar 2 i 3 nie są realizowane (decyzja 2026-10-18). Otwarte DROBNE: D01–D11 z FSA_2026-11-13_F1.md.

## 2026-11-13 — FSA1-D03 ZAMKNIĘTE 2026-11-13 — reguła 31

- Znalezisko: `tests/regression/test_fsa0_f12_single_raw_writer.py::test_every_write_site_is_registered_outside_raw` czerwony od `737a111` (FSA_2026-11-13_F1, DROBNE).
- Przyczyna: tryb `--only 4b-C` (`scripts/engine_tests.py::main_partial`, dodany w `737a111`) dodał dwa zapisy pliku — `(out / 'ENGINE_TESTS_4bC.json').write_text` i `(out / 'ENGINE_TESTS_4bC.md').write_text` — bez dopisania ich do rejestru `WRITERS_OUTSIDE_RAW`. Cel obu: `out = ROOT / "reports" / "backtest_fin" / commit`, czyli `reports/backtest_fin/<commit>/ENGINE_TESTS_4bC.{json,md}` — **poza `data/raw`**. Meta-test działał poprawnie (wykrył niezarejestrowane miejsce zapisu); brakowało przeglądu i wpisu.
- Naprawa: dwa wpisy w rejestrze `WRITERS_OUTSIDE_RAW` z celem zapisu. Bez zmian w `src/`, `config/` i `scripts/`; asercje testu bez zmian; bez `xfail`/`skip`/`noqa`.
- Decyzja Pawła 2026-11-13 (czat): „naprawić D03, bez xfail”.

| element | PRZED | PO |
|---|---|---|
| `test_every_write_site_is_registered_outside_raw` | `6ee399a` (master), pełny `uv run pytest`: **FAILED** — `AssertionError: zapis pliku poza rejestrem … ["scripts/engine_tests.py::main_partial::(out / 'ENGINE_TESTS_4bC.json').write_text", "scripts/engine_tests.py::main_partial::(out / 'ENGINE_TESTS_4bC.md').write_text"]`; 1 failed, 1082 passed | **passed** (plik: 2 passed — także `test_registry_has_no_stale_entries`) |
| pełny `uv run pytest` | 1 failed, 1082 passed | **1083 passed** (0 skipped) |
| `uv run ruff check src tests` / `uv run mypy src` | — | czysto / czysto (40 plików) |
