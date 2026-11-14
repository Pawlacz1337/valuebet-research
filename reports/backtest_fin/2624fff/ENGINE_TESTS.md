# Testy silnika (§4) — commit `2624fff`

Nasion: §4.1 200 dla A i C (BRAMKA); 2b, 3a: 50; 2a, 3b: 3; trucizny 10; robotników 2; mecze świata: 1816 (E0-2223, E0-2324, E1-2223, E1-2324); światy: {'full': 1816, 'early': 918, 'c120': 1804, 'c120-early': 912, 'solo': 124, 'band': 280}.

Wznowienie (`--resume`): TAK — wczytano 221 wyników cząstkowych.

Kupony w trybie PAPER (wyłącznik 25%; komunikat logowany raz na przebieg): 1-A: 38366, 1-C: 26580, 3a-A: 10730, 4-base-A: 3632, 4a-A: 3632, 4b-A: 23020, 4b-C: 14383, 4c-A: 611.

Uwaga: reguła (a) A4a-01 WYŁĄCZONA w świecie bramki (`GATE_WORLD_NO_MARGIN_CHECK`): kurs miękki (1 + e)/p_true ma z konstrukcji booksum 1/(1 + e) < 1. Reguła (b) (EV > 0.50) włączona. Przebieg produkcyjny (`run_strategy`) ma (a) włączone — test `test_a4a01_run_strategy_has_rule_a_on_in_production`.

Strategia C (wariant B, decyzja Pawła 2026-10-11): `run_regime`, reżim wg regulaminu (udział po stawkach), konfiguracja kontrfaktyczna (limit 1000 zł wykorzystany, min. stawka 0.50 zł). Świat `c120` — kursy miękkie ≥ 1.20 (dublety możliwe); `solo` — jeden mecz na migawkę (dubletów brak, single 0.94). Podatek kuponów C sprawdza niezależny checker reżimu z literałów regulaminu (`RefRegime`).

**WYNIK: CZERWONE — STOP**

| test | wynik | szczegóły |
|---|---|---|
| 1a znana odpowiedź: CLV każdego zakładu = e | OK | max |CLV - e| = 9.50e-13 (tolerancja 1e-07); zakładów 610400 |
| 1b znana odpowiedź: zysk - Σ stawka·e ≈ 0 | OK | średnia +198.81 zł, SE 245.46, nasion 200 |
| 2a placebo: zero zakładów przy θ = 0.02 | OK | zakładów 0 |
| 2b placebo wymuszone: yield -5% ± 2 SE | OK | yield -0.0499, SE 0.0009, nasion 50 |
| 3a podatek 0.94, e = 0.10: yield 3.4% ± 2 SE | OK | yield +0.0258 vs +0.0340, SE 0.0052 |
| 3b podatek 0.94, e = 0.025: zero zakładów | OK | zakładów 0 |
| 4a trucizna: losowe zamknięcia → te same zakłady i stawki, inne CLV | OK | zakłady/stawki identyczne: True; CLV inne: True |
| 4b trucizna: spermutowane wyniki → ci sami kandydaci, te same postawione zakłady, stawki wg wzoru Kelly'ego, inny P&L | OK | kandydaci identyczni: True (n=90800); postawione identyczne: True (n=30520); stawki = wzór: True; P&L inny: True |
| 4c trucizna: mecze po dniu D usunięte → decyzje do D identyczne | OK | dzień D = 2023-05-26 |
| 5 podwójne księgowanie: symulator == reconcile w groszach | OK | niezgodnych rozliczeń 0 (porównanie dokładne, bez tolerancji) |
| 6 niezmienniki: limity, kapitał ≥ 0, porządek czasu, podatek | OK | naruszeń 0; migawek z limitem sprawdzonych 31000, maks. ekspozycja 15.0% |
| 1a-C znana odpowiedź: CLV kuponu = (1+e)^n·tax - 1 (dublet (1+e)^2 - 1) | OK | max |CLV - wzór| = 1.67e-12 (tolerancja 1e-07); kuponów 900428, dubletów 876397; świat c120: 1804 meczów |
| 1b-C znana odpowiedź: zysk - Σ stawka·EV kuponu (podatek reżimu, T13) ≈ 0 | OK | średnia +91.90 zł, SE 277.19, nasion 200 |
| 2a-C placebo: k = 0.95/p → zero kuponów | OK | kuponów 0 |
| 2b-C placebo wymuszone: yield = teoria Σ stawka·(0.95·tax - 1)/obrót ± 2 SE | OK | yield -0.1066 vs teoria -0.1070; różnica +0.0004, SE 0.0041, nasion 50; dubletów 0 (EV dubletu 0.95² - 1 < θ — planista nie łączy, single w trybie `literal`) |
| 3a-C podatek: udział AKO 0 (brak dubletów) → single 0.94, e = 0.10: yield 3.4% ± 2 SE | OK | yield +0.0342 vs +0.0340, SE 0.0028; wszystkie kupony single 0.94: True; świat solo: 124 meczów |
| 3b-C podatek 0.94, e = 0.025, brak dubletów: zero kuponów | OK | kuponów 0 |
| 3c-C przejścia reżimu (próg limitu 1000 zł, udział 0.50 / 0.4999, wielokrotny niekwalif.): silnik == checker == literał | OK | przypadków 9; niezgodnych 0 |
| 3d-C reżim w paśmie udziału ~50% (okno, kolejność kandydatów): podatek = niezależny checker | OK | kuponów z udziałem w [0.40, 0.60]: 2279; single 1.00 / 0.94: 1700 / 829; podatek ≠ checker: 0; świat band: 280 meczów |
| 4a-C trucizna: losowe zamknięcia → te same kupony (nogi, kursy, stawki), inne CLV | OK | kupony identyczne: True; CLV inne: True |
| 4b-C trucizna: spermutowane wyniki → ci sami kandydaci, te same kupony (nogi, kursy), stawki wg wzoru Kelly'ego, inny P&L | CZERWONY | kandydaci identyczni: True; kupony identyczne: False (n=44928); stawki = wzór: True; P&L inny: True; nasiono 1: pierwsza różnica na kuponie 2325: ('2023-08-11T17:01:00+00:00', (('0da61ecc94ebc6b7', '1x2', 'draw', 6.802987346326522), ('8466ef90ae036dcf', '1x2', 'away', 2.4536731496815403)), 0.0) vs ('2023-08-11T17:01:00+00:00', (('0da61ecc94ebc6b7', '1x2', 'away', 13.808506004216374), ('0433ad4c5f224beb', '1x2', 'away', 18.556306174125712)), 0.0); nasiono 2: pierwsza różnica na kuponie 2325: ('2 |
| 4c-C trucizna: mecze po dniu D usunięte → kupony do D identyczne (nogi, kursy, stawki) | OK | dzień D = 2023-05-26 |
| 5-C podwójne księgowanie kuponów wielonożnych: symulator == reconcile w groszach | OK | niezgodnych rozliczeń 0; dubletów w porównaniu 876397 (reconcile_bets.py nie importuje valuebet — test_reconcile_is_independent_of_pricing) |
| 6-C niezmienniki: limity (pełna stawka dubletu w obu meczach), nogi z różnych meczów ≥ 1.20, porządek czasu, podatek = niezależny checker reżimu | OK | naruszeń 0; migawek z limitem sprawdzonych 31000, maks. ekspozycja 15.0%; podatek ≠ checker: 0; single rozstrzygnięte pesymistycznie (cykl podatek↔stawka): 59; 1-C wg podatku: multi 1.00: 876397, single 1.00: 24031 |
| 7 jedna ścieżka kodu: szpiedzy wywołani (A i C: RegimePlanner, reżim pricing.ev), nazwy = funkcje live | OK | tożsamość: {'fair_prices': True, 'min_odds': True, 'KellyPolicy': True, 'BetJournal': True, 'open_stake': True, 'clv_rows': True, 'C: BetclicTaxRegime': True, 'C: simulate': True, 'C: min_odds': True}; wywołania: {'fair_prices': 28, 'min_odds': 700, 'KellyPolicy': 651, 'BetJournal': 366, 'open_stake': 552, 'clv_rows': 31, 'C: RegimePlanner.begin': 24, 'C: RegimePlanner.groups': 24, 'C: RegimePlanner.price': 252, 'C: RegimePlanner.placed': 245, 'C: BetclicTaxRegime.tax_for_single': 196, 'C: BetclicTaxRegime.tax_for_multi': 148, 'C: BetclicTaxRegime.share_condition_met': 196, 'C: BetclicTaxRegime.assume': 245} |
