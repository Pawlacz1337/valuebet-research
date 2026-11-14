# Audyt 4a — kod kroku 3 przed pierwszym przebiegiem strategii (BACKTEST_FIN_PLAN §7)

- Commit: `5831a92` (gałąź `audit/4a`); `git diff --stat 2c7cc61 5831a92 -- src scripts` pusty —
  kod silnika i bramki identyczny z bramką §4 ZIELONĄ na `2c7cc61`.
- Data: 2026-10-10. Zlecenie: `docs/discovery/CLI_task_audit_4a.md`.
- Wykonawcy: subagent `backtest-auditor` (pkt a–h) i subagent `full-system-auditor` — FSA skrócony,
  sekcje 3 „Przecieki” i 4 „Poprawność finansowa” (`docs/FULL_SYSTEM_AUDIT.md`, „Kiedy” pkt 4);
  pełny raport FSA: `reports/audit/FSA_2026-10-10_F1-4a.md`. Każde POWAŻNE sprawdzone przez CLI
  przed wpisem (kolumna „weryfikacja CLI”).
- **Nic nie zostało uruchomione na prawdziwych danych** (zakaz zlecenia): reprodukcje wyłącznie na
  światach syntetycznych (`tests/helpers/fin_world.py`, `scripts/engine_tests.synthetic_truth`),
  mutacje w kopii `git archive` poza repo. Żadnych liczb strategii A–F.
- Stan bazowy na `5831a92`: `uv run pytest` 977 passed (11 min 49 s); `ruff check src tests` czysto;
  `mypy src` czysto (40 plików); `pytest -k future_poison` 10 passed.

## Ustalenia

Duplikaty scalone pod jednym ID (w nawiasie ID u drugiego audytora).

| ID | waga | plik:linia | scenariusz błędu | weryfikacja CLI | rekomendacja |
|---|---|---|---|---|---|
| **A4a-01** | **POWAŻNE** | `backtest/financial.py:236-264` (`threshold_selector`), `backtest/replay.py:142-158` (`_quote`) | Kurs miękki bez żadnej kontroli wiarygodności (odrzucany tylko kurs ≤ 1.0). Literówka w football-data (np. `B365H` 15.0 zamiast 1.50) → kandydat EV +875%, pierwszy w kolejce (EV malejąco), stawka z limitu 2%, rozliczenie po kursie 15; w rzeczywistości bukmacher unieważnia zakład z oczywistym błędem kursu. Jeden taki kupon przy ~5 000 przesuwa średnie CLV o ~+0,18 pkt proc. Pinnacle chroniony częściowo (booksum < 1 → Shin rzuca wyjątek, mecz poza wyceną). | Potwierdzone: `repro1.py` (fin_world, 10 meczów, jeden kurs 15.0) → 1 zakład, stawka 200,00 zł, EV 8,75, zysk +2 500 zł, CLV +8,75. Częstość w prawdziwych danych — **nieznana** (skan wymagałby oglądania danych decyzyjnych, poza zleceniem). | Reguła odrzucenia kursu zamrożona **przed** krokiem 5, liczona **wyłącznie z migawki decyzyjnej** (nigdy z zamknięcia ani wyniku), z licznikiem wykluczeń per liga/sezon; **decyzja Pawła** (zmienia strategię zamrożoną w §3). |
| **FSA4a-01** (A4a-03) | **POWAŻNE** | `backtest/strategies.py:34,62-72`, `backtest/financial.py:330-353` | Podatek strategii podawany dwa razy: `threshold_selector(tax_factor)` (próg `k_min`) i `run(tax_factor)` (dziennik, rozliczenie), bez sprawdzenia zgodności. Runner, który poda A `run(0.88)`, zaniży każdą wypłatę o 12% i da werdykt NIEPOTWIERDZONA/OBALONA bez alarmu. | Potwierdzone kodem (`run` waliduje tylko dziedzinę) i `exp/taxmismatch.py`: selektor 1.00 + `run(0.88)` → kasa 10 140,00; selektor 0.88 + `run(1.00)` → 10 280,00; oba przyjęte bez błędu. Dziś bez skutku — runnera nie ma. | Jedno źródło podatku strategii wiązane w kodzie (podatek w dzienniku == podatek selektora); test szpiegów i niezmiennik podatku na runnerze kroku 5. |
| **FSA4a-02** | **POWAŻNE** | `scripts/engine_tests.py:541-569` (4b, 4c), `:303-311` (`kelly_mismatches`) | Trucizny 4b/4c nie porównują **postawionych** zakładów: 4b — zbiór kandydatów selektora i wzór Kelly'ego tylko dla postawionych; 4c — porównanie jednokierunkowe (`:567`). Silnik pomijający kandydata zależnie od wyniku przechodzi 4a, 4b, 4c, 5, 6, 7. Strategia C nie ma żadnego testu bramki (`invariant_errors`, `kelly_mismatches` rzuciłyby `KeyError` na kuponie dwunożnym). | Potwierdzone kodem (`engine_tests.py:544-546`: `same_cand` z `r.candidates`, `kelly_mismatch` po `bets`). Mutacja audytora M6 (pomiń przegrany kupon przy k ≥ 3): szybka bramka 4a/4b/4c/5/6/7 zielone, czerwone tylko statystyczne 1b (+1 417 zł, SE 193), 2b, 3a; `test_deterministic_points_are_green` zielony. **Obecny kod takiego przecieku nie ma** — ustalenie dotyczy mocy bramki. | 4b: każdy kandydat, dla którego niezależny wzór daje stawkę ≥ 0,01 zł, jest postawiony (i odwrotnie) — wymaga logowania wejść stawki dla **każdego** kandydata w `simulate`; 4c dwukierunkowo; zakres bramki dla C — **decyzja Pawła**. |
| A4a-02 | DROBNE | `backtest/clv.py:262-269` | CLV = `Π(k·p_close)·tax − 1` bez `winnings_factor` (T13); kupon z wypłatą > 2 280 zł ma CLV zawyżone o ~10 pkt proc. | Kod. Przy 10 000 zł i Kellym ¼ wymaga kapitału rzędu 250 tys. zł (FSA4a-05). | Raport kroku 5: liczba kuponów z `w = 0.90`. |
| A4a-04 (FSA4a-07) | DROBNE | `backtest/financial.py:99-103`, `replay.py:107-108` | Selektor dostaje `ReplayMatch` z polem `closing`; dziś nieczytane (trucizna 4a zielona). | Kod: `threshold_selector` czyta tylko `decision`, `league`, `season`. | Widok meczu bez `closing` dla selektora/planisty. |
| A4a-05 (FSA4a-09) | DROBNE | `pricing/kelly.py:183-192`, `financial.py:412-418`, `:535-537` | Po wyłączniku 25% przebieg nie wraca do real (kapitał zamrożony); yield real liczony na prefiksie historii uciętym regułą zależną od wyników. | `repro3.py` (audytor). Kierunek nie zawyżający. | Już w ROADMAP §2: raport A–F z datą wyłącznika, real i paper osobno, wariant bez wyłącznika. |
| A4a-06 | DROBNE | `backtest/strategy_c.py:113-129` | EV dubletu ≈ e₁ + e₂ — yield C strukturalnie ~2× A; alarm > 8% w C może zadziałać bez błędu. | Rachunek. | Przy alarmie C porównać yield z `Σ stawka·EV` przebiegu. |
| A4a-07 | DROBNE / do sprawdzenia | `ingest/football_data_main.py:439` | Strefa `Time` = Europe/London sprawdzona na E0, D1, SP1, POL; brak przypadków dla T1, G1 (UTC+2/+3), P1, N1, B1, F1, I1, SC. Gdyby tam był czas lokalny, mecz piątkowy/wtorkowy mógłby przejść regułę `observed_at`. | Niepotwierdzone. | Po jednym przypadku letnim T1 i G1 w `docs/sources.md`. |
| FSA4a-03 | DROBNE | `scripts/engine_tests.py:522-527` | Test 3a: średnia z ilorazów zysk/obrót obciążona w dół przy Kellym; okno akceptacji [−0,22; +1,86] pkt proc. Wyjaśnia obserwację 2c7cc61 (−1,6 SE). | `exp/exp3a.py` (audytor): yield łączny 3,60% vs oczekiwany 3,40%, silnik nieobciążony. | 3a na różnicy zysk − Σ stawka·EV (jak 1b). |
| FSA4a-04 | DROBNE | `scripts/engine_tests.py:433` | Niezmiennik podatku sprawdza tylko dziedzinę {1.00, 0.94, 0.88}. | Kod. | Razem z FSA4a-01. |
| FSA4a-05 | DROBNE | świat bramki | T13 nigdy nie występuje w świecie bramki; łapią go tylko testy jednostkowe. | Mutacja M3 (audytor). | Raport: licznik `w = 0.90`. |
| FSA4a-06 | DROBNE | `scripts/engine_tests.py:272` | 1a nie sprawdza pokrycia CLV (`default=0.0`). | Kod. | Dopisać warunek pokrycia. |
| FSA4a-08 | DROBNE | `financial.py:283-285`, `strategy_c.py`, `docs/promocje.md` T3/T12 | C: single wyceniane w kolejności EV, promocje.md T3 — (kickoff, match_id, rynek, wynik); `min_stake_pln = 0` mimo T12 zamkniętego 2026-10-09 (0,50 zł). | Kod. C poza werdyktem („GÓRNA GRANICA”). | Do decyzji przy C. |
| FSA4a-10 | DROBNE | `CLAUDE.md` lista kontrolna | `pytest -k future_poison` nie dotyka backtestu finansowego (trucizny są w `test_engine_gate.py`). | 10 testów, żaden z `financial`/`replay`. | Dopisać do listy kontrolnej `tests/test_engine_gate.py`. |
| FSA4a-11 | DROBNE | `financial.py:180-192` | `closing_map` liczy Shina bez walidacji kompletności (reguła 17); replay daje tylko kompletne rynki, dziś bez skutku. | Kod. | Walidacja jak w `fair_prices`. |

## Punkty a–h zlecenia

| | werdykt | dowód |
|---|---|---|
| a) wyciek z przyszłości | OK w kodzie; moc bramki — FSA4a-02 | `fair.py:153-182` (migawki `observed_at >= decision_time` odrzucone); wynik poza `ReplayMatch` (`replay.py:92-121`), dotykany tylko w `settle_until` (`financial.py:396-420`); rozliczenia `settled_at <= t` przed decyzjami (`repro2.py` R2, `reconcile_bets` `bisect_left`); CLV dla G-K `as_of = t` (`clv.py:202-219`, `test_regression_clv_as_of_excludes_unplayed_matches`); bramka 2c7cc61: 4a, niezmiennik kolejności czasów (test 6) |
| b) selekcja po wyniku | OK | `require_complete`/`excluded` czytają tylko `match.decision` (`financial.py:224-235`); mecz bez wyniku zostaje jako void (`replay.py:196-197`, `test_missing_result_is_kept_and_marked_void`); brak zamknięcia → licznik i CLV n/d, mecz zostaje (`replay.py:205-217`) |
| c) zamknięcie jako referencja CLV | OK | `closing_map` — Shin strict z `PSC*`/`PC>2.5`, klucz (mecz, rynek, wynik, linia) (`financial.py:180-192`, `clv.py:101-111`); decyzja tą samą metodą (`fair.py:236`); bramka 1a: \|CLV − e\| < 1e-7 |
| d) rozliczenie | OK | `leg_result` (`financial.py:163-177`), `test_leg_result` (8 przypadków); O/U 2.5 bez pusha; brak wyniku → void; dublety void/wygrana/przegrana (`repro2.py` R3) zgodne z `reconcile_bets` co do grosza; bramka 5 |
| e) kapitał, limity, wyłącznik | OK | kapitał = `cash + open_real` (`financial.py:447`); limity `kelly.py:232-244`, ekspozycja z paper (`test_limits_bind_paper_bets_after_the_drawdown_switch`); bramka 6: 0 naruszeń; mutacje M1, M5 czerwone |
| f) podatek | OK w kodzie; wiązanie — FSA4a-01 | `strategies.py:43-59` (A/A3/B/E 1.00, D 0.88); C: ten sam `tax` w `k_min` i rozliczeniu (`strategy_c.py:131-164`, `test_single_with_enough_edge_is_placed_and_settled_at_the_same_tax`); T13 jednym kodem (`ev.py:560-574`, `kelly.py:247-265`), niezależnie w `reconcile_bets._payout` |
| g) dublety C | OK; poza bramką — FSA4a-02 | różne mecze, nogi ≥ 1.20 (`strategy_c.py:118-122`); p = Πp, k = Πk (`financial.py:456-461`); pełna stawka do obu meczów (`bets.py:336-338`); `test_strategy_c.py` (10 testów); pomiar audytora 18 przebiegów: księga == symulator, 0 naruszeń |
| h) strefy czasu, `observed_at` | OK z uwagą A4a-07 | Europe/London → UTC (`football_data_main.py:467-482`), 6/6 przypadków (`docs/sources.md`); reguła piątek/wtorek 18:00 London, mecz z gwizdkiem ≤ `observed_at` wykluczony (`:485-507`, `test_football_data_observed_at.py`); wrażliwość 23:59 obowiązkowa (decyzja Pawła 2026-10-08, 3d) |

## Status

Naprawy **nie rozpoczęte**: A4a-01 i zakres FSA4a-02 dla C wymagają decyzji Pawła (zmiana strategii
zamrożonej w §3 / zakresu bramki), a każda zmiana `financial.py` wymaga powtórki bramki §4 (~2 h 15 min)
— jedna seria napraw i jedna bramka zamiast kilku.

BRAMKA 4a: KRYT=0 POWAŻNE=3 OTWARTE=[A4a-01, FSA4a-01, FSA4a-02]
