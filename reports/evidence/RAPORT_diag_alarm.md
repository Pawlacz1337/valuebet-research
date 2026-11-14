# Diagnoza alarmu 4599dca (2026-10-18) — liczby i kryteria, bez werdyktu
**Krok 0.** HEAD 4599dca; `git status --short` = tylko `?? reports/backtest_fin/4599dca/`; wolne C: 13.69 GB, D: 35.56 GB; python: brak procesów; strategie: 38 katalogów + RAPORT.json + RAPORT.md.
**Krok 1.** Kopia → `D:\vb-backup\backtest_4599dca_2026-10-18\` (strategie\ + 2 logi): 80/80 plików, 38/38 nazw katalogów identycznych (θ, ł, ą), sha256 i rozmiar zgodne, 0 niezgodności → kopia 100%. Manifest `out_B\manifest_backtest_4599dca.txt`, sha256 = `91138208C8D2140B02EF385632C1610FCFB216CF4E36C72883EEEB6285CD3F38`.
**Kontrola rekonstrukcji:** dla 7 przebiegów n, obrót i zysk z dziennika = RAPORT.md co do grosza; średnie CLV (funkcje silnika) A/A3/C = +0.0197/+0.0265/+0.0376 = RAPORT. Wszystkie kupony real, 0 void, 0 otwartych.
**K2** (oczekiwany z p_fair_at_bet; z = (zr−ocz)/√var; CI = bootstrap klastrowy po tyg. ISO najwcześniejszego gwizdka, ziarno 20261018, 10 000 prób, statystyka (zr−ocz)/obrót):

| przebieg | n | obrót | yield ocz. | yield zr. | z | CI 95% (zr−ocz)/obrót | kl. | kryterium |
|---|---|---|---|---|---|---|---|---|
| A | 2628 | 184845.74 | +6.18% | +7.24% | +0.27 | [−5.29%, +7.63%] | 261 | zgodne z losowością |
| A3 | 3146 | 388329.91 | +6.76% | +9.64% | +0.80 | [−3.86%, +9.73%] | 253 | zgodne z losowością |
| B365 | 2461 | 124663.78 | +6.10% | +3.70% | −0.61 | [−9.04%, +4.25%] | 273 | zgodne z losowością |
| B-BW | 446 | 34964.22 | +6.80% | +18.77% | +1.51 | [−2.73%, +26.48%] | 179 | zgodne z losowością |
| B-WH | 1041 | 106541.44 | +8.03% | +11.44% | +0.63 | [−7.32%, +14.08%] | 224 | zgodne z losowością |
| C | 1424 | 37574.00 | +10.93% | +16.11% | +0.50 | [−13.22%, +24.86%] | 259 | zgodne z losowością |
| E | 8559 | 1498734.79 | +5.61% | +3.55% | −1.07 | [−5.36%, +1.25%] | 293 | zgodne z losowością |

Wzór oczekiwanego zysku bez T13 (zgodnie z zadaniem); kupony z brutto > 2280 zł (T13 ×0.90 w zrealizowanym): A3 3, E 27, pozostałe 0. **K2b:** brak — dziennik nie ma pola p z zamknięcia ani kursu zamknięcia (kolumny: bets.py `BetRecord`); nie liczone.
**K3.** Top 10 zysków / zysk całkowity: A 7520.51/13377.58 = 56.2% (yield bez nich +3.22%); A3 14526.76/37437.61 = 38.8% (+5.97%); C 6629.95/6054.47 = 109.5% (−1.57%).
Koszyki kursu kuponu — n / obrót / yield / śr. CLV:

| kurs | A | A3 | C |
|---|---|---|---|
| <2.0 | 177 / 29834 / +20.4% / +0.0259 | 246 / 72178 / +13.7% / +0.0343 | 19 / 2647 / +27.8% / +0.0432 |
| 2.0–3.0 | 219 / 27912 / +14.6% / +0.0424 | 429 / 98746 / +8.7% / +0.0511 | 21 / 1387 / −34.0% / +0.0509 |
| 3.0–5.0 | 1628 / 103575 / +6.7% / +0.0195 | 1727 / 174556 / +11.1% / +0.0244 | 167 / 7391 / +22.3% / +0.0249 |
| ≥5.0 | 604 / 23525 / −15.9% / +0.0103 | 744 / 42850 / −0.6% / +0.0146 | 1217 / 26148 / +15.8% / +0.0390 |

Sezony (wg `placed_at`, cięcie 1 lipca UTC) — n / obrót / yield / śr. CLV:

| sezon | A | A3 | C |
|---|---|---|---|
| 2019/20 | 622 / 24084 / +4.0% / +0.0260 | 693 / 30998 / +6.2% / +0.0252 | 323 / 5664 / −12.5% / +0.0501 |
| 2020/21 | 451 / 21844 / +4.5% / +0.0290 | 553 / 34517 / +7.0% / +0.0275 | 259 / 5399 / −1.7% / +0.0559 |
| 2021/22 | 527 / 38675 / +18.4% / +0.0136 | 679 / 78744 / +19.9% / +0.0303 | 278 / 7637 / +53.2% / +0.0252 |
| 2022/23 | 377 / 32447 / +13.9% / +0.0259 | 483 / 87004 / +15.0% / +0.0273 | 205 / 6033 / +43.7% / +0.0481 |
| 2023/24 | 355 / 35349 / +1.1% / +0.0107 | 438 / 88875 / −0.0% / +0.0193 | 193 / 6266 / +10.8% / +0.0190 |
| 2024/25 | 186 / 16631 / +0.4% / +0.0097 | 279 / 58008 / +9.2% / +0.0282 | 106 / 3312 / −7.3% / +0.0174 |
| 2025/26 | 110 / 15816 / −4.3% / +0.0002 | 21 / 10184 / −9.3% / +0.0335 | 60 / 3263 / −8.7% / +0.0079 |

**K4** (bez wywołań valuebet; ziarno 20261018: 60 losowych A + 20 największych zysków A (1 wspólny) + 20 kuponów C (17 dubletów) = 100 kuponów, 117 nóg). Mecz po sha1(liga|data UTC|gosp.|gość)[:16]; wynik z FTR (zgodny z FTHG/FTAG), O/U z FTHG+FTAG; kurs: A — kolumna bukmachera z dziennika, C — max(B365, BW z booksum ≥ 1.00), O/U B365; p — Shin na PSH/PSD/PSA lub P>2.5/P<2.5 (silnik: `fair.py:236` → `shin.py` Brent na Σp=1 + renormalizacja; tu własna bisekcja, ten sam wzór); wypłata porównana z dziennikiem (A) i przyrostem gotówki w equity.csv (A, C). **Niezgodności: 0** → kryterium spełnione.
**K5 (a)** Decyzja: `replay.py:74-86` (pre: PSH/D/A, B365H.., BWH.., WHH.., MaxH.., P>2.5/P<2.5, B365>2.5.., Max>2.5..; zamknięcie …C… osobno), `replay.py:207` (decision ← kolumny pre), `financial.py:558` (Pinnacle z `m.decision`), `financial.py:322` (miękki z `match.decision`). Zamknięcia: tylko `replay.py:208` → `financial.py:261-273` `closing_map` → CLV (`financial.py:577` `clv_rows`/`clv_report` z `as_of=t` dla stawki/wyłącznika; `run_backtest_fin.py:362` raport); F: `replay.py:257` PSC/B365C jako decyzja (tylko raport). Brak innych użyć `.closing` w src/scripts.
**(b)** `friday_tuesday_1800_london` (`football_data_main.py:447-507`): mecz pt–pn → observed_at = piątek 18:00 London tego weekendu, wt–czw → wtorek 18:00 London; gwizdek ≤ observed_at → mecz wypada; decyzja = observed_at + 1 min (`replay.py:65`). Założenie: football-data zbiera kursy przedmeczowe „Friday afternoons / Tuesday afternoons” (notes.txt), koniec popołudnia = 18:00; niezweryfikowane dla starszych sezonów (docstring `ObservedAtRule`).
**(c)** A: 2628 zakładów, decyzja ≥ gwizdek: **0**, bez znanego gwizdka: **0**, snapshot ≥ placed_at: 0; wyprzedzenie min 0.48 h / mediana 22.4 h / max 75.2 h. To samo 0/0 w A3, B365, B-BW, B-WH, C, E → kryterium spełnione.
**K7** klucz (match_id, rynek, wynik, linia), |∩|/|mniejszy|: A–A3 0.914, A–B365 0.938, A–B-BW 0.987, A–B-WH 0.207, A3–B365 0.863, A3–B-BW 0.843, A3–B-WH 0.917, B365–B-BW 0.269, B365–B-WH 0.182, B-BW–B-WH 0.164. C: 2612/2636 nóg (99.1%) występuje jako zakład A.
**STOP-y: brak.** Odstępstwa: skrypt manifestu poszedł w priorytecie Normal (PS 5.1 nie ma `-PriorityClass`), diagnostyka w BelowNormal; pierwszy przebieg diag_alarm.py nie widział 6 plików E0 w starym formacie nazwy (`E0-1920-…Z.csv`) — poprawione wyszukiwanie pliku, przebieg powtórzony, liczby wyżej z drugiego. Pliki: `diag_alarm.py`, `diag_alarm_out.json`, `make_manifest_4599dca.py`.
