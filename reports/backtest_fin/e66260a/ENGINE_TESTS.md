# Testy silnika (§4) — commit `e66260a`

Nasion: §4.1 200 (BRAMKA); 2b, 3a: 50; 2a, 3b: 3; robotników 1; mecze świata: 1816 (E0-2223, E0-2324, E1-2223, E1-2324).

**WYNIK: CZERWONE — STOP**

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
| 5 podwójne księgowanie: |symulator - reconcile| ≤ 1e-9 | CZERWONY | max odchylenie 1.06e-09 |
| 6 niezmienniki: limity, kapitał ≥ 0, porządek czasu, podatek | CZERWONY | naruszeń 1092; pierwsze: ['2023-12-29 18:01:00+00:00: otwarta ekspozycja 1600.00', '2024-03-01 18:01:00+00:00: otwarta ekspozycja 1100.00', '2024-03-08 18:01:00+00:00: otwarta ekspozycja 1100.00'] |
| 7 jedna ścieżka kodu: szpiedzy wywołani, nazwy = funkcje live | OK | tożsamość: {'fair_prices': True, 'min_odds': True, 'KellyPolicy': True, 'BetJournal': True, 'open_stake': True, 'clv_rows': True}; wywołania: {'fair_prices': 4, 'min_odds': 300, 'KellyPolicy': 300, 'BetJournal': 121, 'open_stake': 300, 'clv_rows': 5} |
