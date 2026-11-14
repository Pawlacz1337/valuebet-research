# TOR_S_PLAN.md — wycena rynkowa, stawki, alerty, paper trading (S4–S6)

Spisane 2026-10-01 wieczorem, po M2: model nie wnosi informacji ponad
Pinnacle (pula − Pinnacle `+0.0015 [−0.0003, +0.0040]`). Pieniądze idą
wyłącznie torem S. Obowiązuje razem z `CLAUDE.md` (reguły 19, 19a, 20–23)
i `ROADMAP.md` §3–§7.

---

## 1. Przepływ

```
S1: migawki Pinnacle (The Odds API)
  → Shin → p uczciwe per wynik                      pricing/fair.py
  → tryb progowy: k_min per wynik                   pricing/ev.py
  → tryb z kursem: EV dla kursu podanego ręcznie    pricing/ev.py
  → stawka: Kelly z polityką ROADMAP §3.1           pricing/kelly.py
  → przegląd dnia: Telegram albo plik               live/digest.py
  → dziennik zakładów (paper i prawdziwe)           live/bets.py
  → CLV względem zamknięcia Pinnacle                backtest/clv.py
```

Kurs Betclica w tym przepływie podaje człowiek (tryb progowy,
`COLLECTOR_PLAN.md` §3.10). Gdy powstanie zgodny kolektor Betclica (S2–S3),
wchodzi w miejsce ręcznego wpisu — reszta się nie zmienia.

## 2. Migawka decyzyjna — korekta harmonogramu S1

Obecny harmonogram ma dla Premier League i Bundesligi wyłącznie zamknięcia,
czyli ~10 minut przed gwizdkiem. Na ręczną decyzję to za późno. Dodaj
**migawkę decyzyjną**: raz dziennie ok. 08:30 czasu warszawskiego dla każdej
ligi, która gra tego dnia lub następnego, 2 rynki (`h2h`, `totals`).
Przelicz budżet: całość ≤ 450 kredytów miesięcznie; jeśli się nie mieści —
najpierw rezygnujemy z `spreads` dla Ekstraklasy, nie z migawki decyzyjnej.

## 3. `pricing/fair.py` — p uczciwe

- wejście: najnowsza migawka Pinnacle sprzed chwili decyzji
  (`observed_at < t`); maksymalny wiek 6 h, ostrzeżenie powyżej 3 h;
  starsza → brak wyceny, nie stara cena;
- Shin osobno na każdym rynku: 1X2, każda linia totali, każda linia spreads;
  kompletność rynku przed Shinem (reguła 17);
- wyjście: `FairPrice(match_id, market, outcome, line, p, observed_at,
  source="pinnacle")`.

## 4. `pricing/ev.py` — EV i reżim podatkowy

- `ev = p · k · tax_factor − 1`; `k_min = (1 + θ) / (p · tax_factor)`,
  `θ = 0.02` z konfiguracji;
- `tax_factor` dla Betclica z klasy `BetclicTaxRegime`, liczonej z dziennika
  — **tylko zakłady prawdziwe**:
  - łączne stawki < 1000 zł → 1.00 dla wszystkiego;
  - potem: udział AKO w obrocie (po stawkach) z ostatnich 5000 zakładów, po
    12 miesiącach — z kroczących 12 miesięcy; ≥ 50% → 1.00; mniej → single
    0.94;
  - AKO kwalifikowany: ≥ 2 zdarzenia, każde z kursem ≥ 1.20;
  - „co jeśli": singiel, który zepchnąłby udział poniżej 50%, jest wyceniany
    na 0.94 — zanim zostanie zawarty;
  - źródło: regulamin „Bez Podatku 2.0" z 21.05.2026 v2;
- dublet: `EV = Π(p_i · k_i) · tax − 1`; zdarzenia z tego samego meczu →
  wyjątek;
- inni bukmacherzy: `tax_factor` z `config/bookmakers.yaml` z datami
  obowiązywania promocji; brak wpisu → 0.88.

## 5. `pricing/kelly.py` — stawki

- reguła 22 na kursie efektywnym: `f* = (p·k·tax − 1) / (k·tax − 1)`,
  stawka `c · f*` od przewagi skorygowanej
  `e_użyte = e · min(1, CLV zrealizowane / EV przewidziane)` — do bramki
  G-K współczynnik = 1;
- `c = 0.25`; `c = 0.5` **tylko** gdy plik stanu potwierdza bramkę G-K
  (≥ 150 zakładów prawdziwych, średnie CLV z dolną granicą CI > 0) —
  liczone kodem z dziennika, nie ustawiane ręcznie;
- limity: 2% kapitału na zakład (reguła 23), 3% na mecz, 15% łącznej
  otwartej ekspozycji;
- dublet: Kelly na kursie dubletu;
- wyłącznik: obsunięcie 25% od szczytu kapitału → tryb paper; alerty
  oznaczone `PAPER`; wpis w raporcie.

## 6. `live/digest.py` — przegląd dnia (tryb progowy)

- rano po migawce decyzyjnej i ~2 h przed pierwszym meczem dnia, jeśli jest
  świeższa migawka;
- dla każdego meczu w najbliższych 36 h: p uczciwe i `k_min` dla 1, X, 2,
  powyżej i poniżej 2.5 (główna linia AH, jeśli jest);
- jedna wiadomość na ligę, tabela tekstowa: mecz, godzina, progi Betclica;
  nagłówek: tryb (PAPER/REAL), wiek migawki, ostrzeżenie > 3 h;
- kanał: Telegram (token i chat id w `.env`); bez tokena → plik
  `reports/digest/RRRR-MM-DD_HHMM.txt`. Żadnych sekretów w treści.

## 7. `live/bets.py` — dziennik zakładów

`data/bets/bets.csv`, tylko dopisywanie. Kolumny: `bet_id, placed_at (UTC),
mode (paper/real), bookmaker, coupon_id, match_id, market, outcome, line,
odds_taken, stake, tax_factor_applied, p_fair_at_bet, snapshot_observed_at,
price_available (tak/nie), notes`.

Wpis przez `uv run python -m valuebet.live.bets add …` z walidacją: mecz
istnieje w S1, kurs > 1, stawka w limitach z §5. Rozliczenie na start
ręczne (`settle`), automat — później.

`price_available` = czy kurs Betclica był ≥ `k_min` w chwili sprawdzenia.
To jest licznik do bramki G-S („≥ 70% alertów z kursem wciąż dostępnym").

## 8. `backtest/clv.py` — CLV

- `CLV = odds_taken · tax_factor_applied · p_close − 1`, gdzie `p_close` =
  Shin z ostatniej migawki zamknięcia Pinnacle ≤ gwizdek (tolerancja 30 min);
  bez niej → CLV n/d, liczone osobno, nigdy jako zero;
- raport: średnie CLV z CI (bootstrap klastrowy po kolejkach; < 5 klastrów →
  n/d), per liga, per rynek, paper i real osobno;
- to jest metryka bramek G-S i G-K.

## 9. Testy — minimum

- Shin na odpowiedziach z S1 (fixture'y z prawdziwych odpowiedzi, oczyszczone);
- reżim Betclica: próg 1000 zł, udział AKO po obrocie, „co jeśli" dla
  singla, AKO z nogą < 1.20 nie kwalifikuje, zakłady paper nie wchodzą do
  udziału;
- Kelly: limity 2/3/15%, `c = 0.5` niedostępne bez potwierdzonej G-K,
  wyłącznik 25%;
- `k_min` i EV — wartości policzone ręcznie;
- CLV: brak migawki zamknięcia → n/d, nie zero;
- digest bez tokena → plik; żaden sekret w treści;
- trucizna: wycena w chwili `t` używa wyłącznie migawek z `observed_at < t`.

## 10. Kolejność

1. Korekta harmonogramu S1 (§2) + przeliczenie kredytów.
2. `fair.py`, `ev.py`, `kelly.py` + testy.
3. Dziennik + `clv.py` + testy.
4. Digest + Telegram.
5. Paper trading od najbliższej kolejki, dla której S1 ma migawki.
