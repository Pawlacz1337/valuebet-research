# Testy silnika (§4) — CZĘŚCIOWY — NIE BRAMKA; uzupełnia bramkę 27ae469 (24/25 OK, 4b-C czerwone: remis zaokrąglenia)

Commit: `737a111`; odniesienie: `27ae469`; tryb `--only 4b-C` (4-base-C + 4b-C, nasion 10, przebiegów 20); robotników 2; mecze świata: 1816; sha256 terminarza `b2818773f24aab96a9d93f5f2163797f79ac4f02b2deda0ff96dc3a058d11a9c`.

`git diff 27ae469..HEAD -- src config`: **PUSTY** (src/ i config/ bit-w-bit jak w bramce odniesienia).

**WYNIK 4b-C: ZIELONE** (to NIE jest bramka)

| test | wynik | szczegóły |
|---|---|---|
| 4b-C trucizna (kryterium ścieżki, 2026-10-12): spermutowane wyniki → ci sami kandydaci; każda różnica kuponów wyjaśniona stanem przebiegu (kapitał, PAPER, min. stawka) potwierdzonym z księgi; inny P&L | OK | kandydaci identyczni: True; stawki = wzór (silnik): True; P&L inny: True; nasiono 0: wyjaśnione — PAPER (tryb, obsunięcie z księgi): 0; nasiono 1: wyjaśnione — PAPER (tryb, obsunięcie z księgi): 3476, STAWKA_PONIZEJ_MINIMUM: 1, STAWKA_ZERO: 50; nasiono 2: wyjaśnione — PAPER (tryb, obsunięcie z księgi): 0, STAWKA_PONIZEJ_MINIMUM: 1; nasiono 3: wyjaśnione — PAPER (tryb, obsunięcie z księgi): 3048, STAWKA_PONIZEJ_MINIMUM: 1, STAWKA_ZERO: 21; nasiono 4: wyjaśnione — PAPER (tryb, obsunięcie z księgi): 1629; nasiono 5: wyjaśnione — PAPER (tryb, obsunięcie z księgi): 0, STAWKA_PONIZEJ_MINIMUM: 1; nasiono 6: wyjaśnione — PAPER (tryb, obsunięcie z księgi): 0; nasiono 7: wyjaśnione — PAPER (tryb, obsunięcie z księgi): 3370, STAWKA_PONIZEJ_MINIMUM: 1, STAWKA_ZERO: 45; nasiono 8: wyjaśnione — PAPER (tryb, obsunięcie z księgi): 667; nasiono 9: wyjaśnione — PAPER (tryb, obsunięcie z księgi): 2183, STAWKA_PONIZEJ_MINIMUM: 1; niewyjaśnionych: 0; audyt stawek z księgi (przebiegów 20/20): kuponów 89958, remisów 28, zaakceptowanych jako remis 1, odrzuconych 0, max |Δ kapitału| 6.548e-11 (próg 1e-06) |
