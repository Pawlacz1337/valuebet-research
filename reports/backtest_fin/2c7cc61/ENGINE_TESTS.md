# Testy silnika (§4) — commit `2c7cc61`

Nasion: §4.1 200 (BRAMKA); 2b, 3a: 50; 2a, 3b: 3; robotników 1; mecze świata: 1816 (E0-2223, E0-2324, E1-2223, E1-2324).

**WYNIK: ZIELONE**

| test | wynik | szczegóły |
|---|---|---|
| 1a znana odpowiedź: CLV każdego zakładu = e | OK | max |CLV - e| = 9.50e-13 (tolerancja 1e-07); zakładów 610415 |
| 1b znana odpowiedź: zysk - Σ stawka·e ≈ 0 | OK | średnia +198.80 zł, SE 245.46, nasion 200 |
| 2a placebo: zero zakładów przy θ = 0.02 | OK | zakładów 0 |
| 2b placebo wymuszone: yield -5% ± 2 SE | OK | yield -0.0499, SE 0.0009, nasion 50 |
| 3a podatek 0.94, e = 0.10: yield 3.4% ± 2 SE | OK | yield +0.0258 vs +0.0340, SE 0.0052 |
| 3b podatek 0.94, e = 0.025: zero zakładów | OK | zakładów 0 |
| 4a trucizna: losowe zamknięcia → te same zakłady i stawki, inne CLV | OK | zakłady/stawki identyczne: True; CLV inne: True |
| 4b trucizna: spermutowane wyniki → ten sam zbiór kandydatów, stawki wg wzoru Kelly'ego, inny P&L | OK | kandydaci identyczni: True (n=90800); stawki = wzór: True; P&L inny: True |
| 4c trucizna: mecze po dniu D usunięte → decyzje do D identyczne | OK | dzień D = 2023-05-26 |
| 5 podwójne księgowanie: symulator == reconcile w groszach | OK | niezgodnych rozliczeń 0 (porównanie dokładne, bez tolerancji) |
| 6 niezmienniki: limity, kapitał ≥ 0, porządek czasu, podatek | OK | naruszeń 0; migawek z limitem sprawdzonych 31000, maks. ekspozycja 15.0% |
| 7 jedna ścieżka kodu: szpiedzy wywołani, nazwy = funkcje live | OK | tożsamość: {'fair_prices': True, 'min_odds': True, 'KellyPolicy': True, 'BetJournal': True, 'open_stake': True, 'clv_rows': True}; wywołania: {'fair_prices': 4, 'min_odds': 300, 'KellyPolicy': 300, 'BetJournal': 121, 'open_stake': 300, 'clv_rows': 5} |
