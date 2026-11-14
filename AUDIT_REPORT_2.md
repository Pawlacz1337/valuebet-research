# AUDIT_REPORT_2 — audyt adwersaryjny toru S i modeli

Data: 2026-10-01
Audytor: subagent `backtest-auditor` (adwersaryjny)
Commit bazowy: patrz `git rev-parse HEAD` w momencie audytu (master, po 4b98818)

## Zakres

- `src/valuebet/models/` — dixon_coles.py, elo_ordinal.py
- `src/valuebet/pricing/` — fair.py, ev.py, kelly.py, shin.py
- `src/valuebet/backtest/` — clv.py, market_benchmark.py, dixon_coles_baseline.py,
  elo_baseline.py, lockbox.py, metrics.py
- Pomocniczo: live/bets.py, live/digest.py, features/, tests/, scripts/

## Lista kontrolna (statusy aktualizowane przyrostowo)

- [x] 0. Rekonesans: struktura, CONTEXT.md, reguły 19/19a/21 w zmienionej formie
- [x] 1. pricing/fair.py — szczelność czasowa migawek, kompletność rynku, strefy czasowe
- [x] 2. pricing/ev.py — reżim podatkowy Betclica, udział AKO, okno 5000/12mc, paper
- [x] 3. pricing/kelly.py — bramka G-K, limity 2/3/15%, korekta CLV, wyłącznik obsunięcia
- [x] 4. backtest/clv.py — brak zamknięcia, tolerancja 30 min, klastrowanie ISO
- [x] A. Sygnatury leakage w całym zakresie
- [x] B. metrics.py i market_benchmark.py — n, CI, bootstrap klastrowy, accuracy
- [x] C. shin.py — n=2, allow_underround, zgodność z CONTEXT §5.1-5.4
- [x] D. dixon_coles_baseline.py — rozdział siatka/predykcja, cache LL(V, xi)
- [x] E. Reguła 19a — macierz DC a totale/handicapy/kombinacje
- [x] PYTANIE 1 — szczelność czasowa wyceny toru S
- [x] PYTANIE 2 — reguła 19 po wyjątku dla toru S
- [x] PYTANIE 3 — ochrona lockboxa
- [x] PYTANIE 4 — bezpieczniki numeryczne dixon_coles.py
- [x] Tabela znalezisk, ocena wiarygodności raportów

---
## 0. Rekonesans — stan faktyczny

- HEAD audytu: `4b98818` (master). Testy: `uv run pytest` = **528 passed**, 159 s.
- Moduły toru S (`pricing/fair.py`, `pricing/ev.py`, `pricing/kelly.py`,
  `backtest/clv.py`, `live/bets.py`, `live/digest.py`) powstały w `4b98818`
  i **nie mają ani jednego wywołania poza `tests/test_tor_s.py`**.
  Sprawdzone grepem: `MarketQuote`, `fair_prices`, `build_digest`,
  `BetclicTaxRegime`, `PlacedBet`, `KellyPolicy`, `BetJournal`, `clv_rows`,
  `clv_report` — wszystkie wyłącznie w testach.
  **Konsekwencja dla całego audytu:** żadna liczba w `reports/` nie
  przeszła przez tor S, więc znaleziska z sekcji 1-4 nie unieważniają
  istniejących raportów — są długiem, który zapala się w chwili
  podłączenia. Klasyfikuję je po skutku, jaki wywołają po podłączeniu.
- Reguły w zmienionej formie potwierdzone w `CLAUDE.md:86-105`: wyjątek
  toru S do reguły 19, nowa reguła 19a (DC nie wycenia totali/handicapów/
  kombinacji), reguła 21 rozszerzona o „0.5 wyłącznie po bramce G-K,
  sprawdzanej kodem, nie flagą".
- Dane: `data/interim/football_data/matches.parquet` = 4151 meczów,
  15 sezonów (2012/13-2026/27), `kickoff_utc` = `datetime64[us, UTC]`
  (tz-aware). `closing_odds`: pinnacle 3887, betfair_exchange 656,
  bet365 343, market_avg/max 4151.

---

## 1. `pricing/fair.py` — wycena z migawek Pinnacle

### [KRYTYCZNE po podłączeniu] src/valuebet/pricing/fair.py:50 i :144-154
**Co:** walidacja kompletności rynku jest wykonywana **tylko** dla trzech
dosłownych nazw rynku; każda inna nazwa przechodzi bez żadnej kontroli
liczby wyników.

```python
MARKET_SIZE = {"1x2": 3, "totals": 2, "spreads": 2}
...
expected = MARKET_SIZE.get(quote.market)
if expected is not None and len(quote.odds) != expected:
    ...  # pomiń
```

**Naruszona reguła:** 17 („Shin wymaga kompletnego rynku. Waliduj
kompletność **przed** wywołaniem"). Docstring modułu obiecuje dokładnie
to, czego kod nie robi: „Shin osobno na każdym rynku, po walidacji
kompletności (reguła 17)".

**Mechanizm — i dlaczego to nie jest teoretyczne:** cały własny ingest
nazywa rynek 1X2 **`h2h`**, nie `1x2`:
`ingest/odds_api.py:130` → `markets = ("h2h", "totals", "spreads")`,
`ingest/odds_collector.py:135` → `DECISION_MARKETS = ("h2h", "totals")`.
Czyli najbardziej naturalne podłączenie kolektora do `fair_prices`
(przepisanie `market` z klucza The Odds API) **wyłącza walidację rynku
1X2 w całości**. Zmierzone:

```
market="h2h", outcomes=("1","X","2","X"), odds=(1.20, 6.50, 13.0, 6.50)
  -> fair_prices zwraca 4 wyceny, booksum=1.2179, suma p = 1.0
market="1x2", te same 2 z 3 wyników -> 0 wycen (poprawnie pominięte)
```

Drugi, gorszy wariant: rynek, który wcale nie jest rozkładem. Podwójna
szansa pod nazwą `double_chance`:

```
odds=(1.28, 1.30, 2.10) -> booksum 2.0267
  1X  p=0.4145  k_min(tax=1.00)=2.461
  12  p=0.4044  k_min(tax=1.00)=2.522
  X2  p=0.1811  k_min(tax=1.00)=5.631
```

`p(1X)=0.41` przy kursie rynkowym 1.28 to nie wycena, to artefakt
normalizacji booksumu 2.03 do jedynki. Progi `k_min` 2.46 / 5.63 trafiłyby
do przeglądu dnia jako „od tego kursu warto".

**Kierunek i rząd wielkości:** jednostronny, w górę. Shin dzieli przez
booksum, więc każdy rynek o booksumie > 1 z innego powodu niż marża
(nakładające się wyniki, zduplikowany wynik, dwie linie w jednym quote)
produkuje `p` zawyżone w proporcji do nadmiaru booksumu. Dla podwójnej
szansy to współczynnik ~2. Dla 1X2 z powtórzonym remisem ~1.15. Każda
wartość `p` zawyżona o `x%` przesuwa EV o `x%` stawki — czyli
wielokrotność całej szukanej przewagi (2-5%).

**Jak sprawdzić:** test, który podaje `fair_prices` rynek o nazwie
nieobecnej w `MARKET_SIZE` i oczekuje wyjątku, nie wyceny. Dziś
`tests/test_tor_s.py:78` sprawdza wyłącznie ścieżkę `market="1x2"`, więc
dziura jest poza zasięgiem testów.

### [POWAŻNE] src/valuebet/pricing/fair.py:166 — underround wychodzi jako wyjątek z całej pętli
**Co:** `shin_probabilities` przy booksumie < 1 podnosi `ValueError`, a
`fair_prices` **nie łapie go**. Jeden zepsuty rynek w migawce przerywa
wycenę wszystkich pozostałych meczów.

**Mechanizm:** to komplementarna połowa znaleziska wyżej. Dla realnych
kursów Pinnacle 1X2 (overround 2-6%) usunięcie dowolnego wyniku daje
booksum < 1, więc typowy niekompletny rynek pod nieznaną nazwą nie
zawyża cicho — **wysadza przebieg**. Zmierzone: `market="1X2"`
(wielka litera), `odds=(1.20, 6.50)` → `ValueError: booksum = 0.987179 < 1`
propagowany z `fair_prices`.

**Kierunek:** nie zawyża yieldu; zabiera przegląd dnia w całości.
Deklarowany kontrakt funkcji („Rynki niekompletne (...) są **pomijane z
ostrzeżeniem**, nie wyceniane na siłę") jest złamany.

### [DROBNE] src/valuebet/pricing/fair.py:57-71 — `line` nie wchodzi do walidacji kompletności
`MARKET_SIZE["totals"] = 2` sprawdza wyłącznie **liczbę** kursów. Quote z
`Over 2.5` i `Under 3.5` przechodzi jako kompletny rynek dwustronny;
booksum takiej pary nie ma interpretacji marży. `MarketQuote` ma jedno
pole `line` na cały rynek, więc struktura danych nie pozwala tego wykryć
po fakcie.

### [CZYSTO] granica czasowa migawki
- `fair.py:109-110` — naiwny `decision_time` podnosi wyjątek (reguła 2).
- `fair.py:114-115` — naiwny `observed_at` podnosi wyjątek.
- `fair.py:117` — `quote.observed_at >= decision_time` → `continue`.
  Nierówność **nieostra**, czyli migawka równa chwili decyzji też jest
  odrzucana. To jest poprawny kierunek.
- `fair.py:127` — `age > max_age` → brak wyceny. Brak dziury na strefach,
  bo oba znaczniki są wymuszone tz-aware, a arytmetyka `datetime`
  tz-aware jest w UTC niezależnie od `tzinfo`.

### [DO SPRAWDZENIA] `fair_prices` nie zna `kickoff_utc`
Funkcja nie przyjmuje godziny rozpoczęcia meczu, więc nie ma jak sprawdzić
`decision_time < kickoff`. Przy odtwarzaniu historycznym (backtest na
zebranych migawkach) wystarczy podać `decision_time` późniejszy niż
gwizdek, żeby wyceniać z migawek in-play — a te są o rząd lepsze.
Filtr `decision_time <= kickoff` istnieje dopiero w `digest.py:76`, czyli
o jedną warstwę za późno i tylko dla jednego konsumenta. Rozstrzygnęłoby:
przebieg historyczny z `decision_time = kickoff + 1h` — dziś przejdzie bez
jednego ostrzeżenia.

---
## 2. `pricing/ev.py` — reżim podatkowy Betclica

### [KRYTYCZNE po podłączeniu] src/valuebet/pricing/ev.py:98-103 — okno AKO nie ma górnej granicy

Kod:

    def _window(self) -> list[PlacedBet]:
        real = [b for b in self.bets if b.is_real]
        if self.now is not None:
            cutoff = self.now - timedelta(days=AKO_WINDOW_MONTHS * 30)
            real = [b for b in real if b.placed_at >= cutoff]
        return sorted(real, key=lambda b: b.placed_at)[-AKO_WINDOW_BETS:]

**Co:** okno jest obcięte **tylko od dołu**. Brak warunku
`b.placed_at <= self.now`, mimo że `now` jest podane.

**Naruszona reguła:** 1 (cecha dla czasu t liczona wyłącznie z danych
dostępnych przed t) oraz 20 pośrednio, bo to `tax_factor` jest tą cechą.

**Mechanizm:** `tax_factor` jest funkcją dziennika. Każde przeliczenie
historyczne — rekonstrukcja EV dla zakładu z marca na dzienniku czytanym
w czerwcu, backtest toru S na zapisanych migawkach, raport "jak by
wyszło" — podaje do `BetclicTaxRegime` **cały** dziennik. Zakłady
postawione PO chwili decyzji wchodzą wtedy do licznika i mianownika
udziału AKO.

**Dowód liczbowy** (now = 2026-06-01; 10 singli po 100 zł sprzed decyzji,
10 AKO po 200 zł PO decyzji):

    udzial AKO bez przyszlosci: 0.000  -> tax_for_single(100) = 0.94
    udzial AKO z przyszloscia : 0.667  -> tax_for_single(100) = 1.00

**Kierunek i skala:** jednostronnie w górę, **6 punktów procentowych na
stawce** (0.94 -> 1.00). Przy progu opłacalności p*k >= 1/tax to różnica
między "zakład jest -EV" i "zakład jest +EV". Więcej niż cała przewaga,
której szuka projekt.

**Jak sprawdzić:** test, w którym `bets` zawiera wpis z `placed_at > now`,
a `ako_share` ma wyjść identyczne jak bez tego wpisu. Dziś brak takiego
testu — `tests/test_tor_s.py` wszędzie ustawia `placed_at = T0 = now`.

### [POWAŻNE] ev.py:106-107 wobec :98-103 — okno stosowane niespójnie

    @property
    def real_turnover(self) -> float:
        return sum(b.stake for b in self.bets if b.is_real)   # BEZ okna

`real_turnover` (próg 1000 zł) liczy **cały dziennik od zawsze**, a
`ako_share` liczy okno 5000 zakładów / 12 miesięcy. Odpowiedź na pytanie
ze zlecenia (czy okno jest stosowane spójnie): **nie**.

**Dowód liczbowy:** 900 zł sprzed 500 dni + 50 zł sprzed dnia, now dzisiaj:

    real_turnover (bez okna) = 950    obrot w oknie = 50
    below_turnover_limit = True       tax_for_single(10) = 1.00

Dwie definicje tej samej wielkości w jednym obiekcie. Kierunek zależy od
tego, która interpretacja regulaminu jest prawdziwa, więc nie da się
nazwać go konserwatywnym — i to właśnie dyskwalifikuje: błąd o nieznanym
znaku w parametrze, który wprost mnoży EV.

### [POWAŻNE] ev.py:69-88 wobec live/bets.py:141-171 — wiersze rozliczeniowe

`BetJournal.settle()` dopisuje **nowy wiersz** z tym samym `stake` i tym
samym `mode="real"` (bets.py:153-165). `BetJournal.real_turnover` poprawnie
filtruje (bets.py:170: `if r.mode == "real" and not r.settled`), ale
`BetclicTaxRegime.real_turnover` **nie ma pola `settled` w ogóle** —
`PlacedBet` go nie posiada. Każde zbudowanie `PlacedBet` z
`BetJournal.read()` bez jawnego odfiltrowania rozliczeń podwaja obrót.
Dwie sprzeczne definicje obrotu rzeczywistego w dwóch modułach, które mają
się ze sobą składać.

Dodatkowo `settle()` ustawia `placed_at = datetime.now(UTC)`, więc wiersze
rozliczeniowe zajmują miejsca w oknie `[-AKO_WINDOW_BETS:]` sortowanym po
`placed_at` i wypychają z niego prawdziwe zakłady.

### [POWAŻNE] ev.py:77 — `mode` domyślnie "real"

Odpowiedź na pytanie, czy zakłady paper są wyłączone ze wszystkich trzech
ścieżek: **tak, ale tylko jeśli wołający pamięta o `mode="paper"`**.
Domyślna wartość jest po niebezpiecznej stronie — pominięte `mode=` liczy
zakład papierowy jako prawdziwy. Docstring modułu opisuje dokładnie ten
skutek ("Wliczanie go dawałoby fałszywe 1.00"), a kod ustawia domyślnie
wariant, który go wywołuje. Zweryfikowane:
`PlacedBet(placed_at=T, stake=100.0, leg_odds=(2.0,)).is_real` zwraca True.
Samo filtrowanie `is_real` jest poprawne w obu ścieżkach (`_window`,
`real_turnover`) i w `tax_for_single`.

### [DROBNE] ev.py:61 i :101 — "12 miesięcy" to 360 dni

`AKO_WINDOW_MONTHS * 30 = 360` dni, pięć dni krócej niż rok. Kierunek:
wypadają najstarsze zakłady, więc jeśli stare są AKO, udział spada, czyli
konserwatywnie. Rząd wielkości pomijalny, ale to arbitralna rozbieżność z
regulaminem w miejscu, które sam docstring nazywa "do weryfikacji w
oryginale" (CONTEXT §2).

### [DROBNE] ev.py:84-88 — `qualifies_as_ako` nie wymaga różnych meczów

`double_ev` (ev.py:220-225) słusznie odrzuca dwie nogi z tego samego meczu
jako skorelowane, a `qualifies_as_ako` tej kontroli nie ma: kupon z dwóch
zdarzeń tego samego meczu kwalifikuje się jako AKO i zwraca `tax = 1.00`.
Niespójność w obrębie jednego modułu.

### [DO SPRAWDZENIA] src/valuebet/schema.py:309 — 0.88 zaszyte jako domyślna wartość

    tax_factor: float = Field(default=0.88, gt=0.0, le=1.0)

Reguła 20: "Nigdy nie zaszywaj 0.88 w kodzie — to parametr konfiguracji".
Formalnie naruszone w modelu danych. Kierunek bezpieczny (podatek ustawowy
to najostrożniejszy wariant), ale domyślna wartość liczbowa w schemacie
oznacza, że brak `tax_factor` w migawce nie zostanie zauważony. Nie
sprawdziłem, czy jakakolwiek ścieżka produkcyjna polega na tym defaulcie.

### [CZYSTO] wariant "co jeśli" i reguła 20 w `ev()`

- `tax_for_single` (ev.py:128-140) liczy udział **po** hipotetycznym
  dodaniu stawki: `total = suma(okno) + stake`, licznik AKO bez zmiany. To
  poprawny kierunek rozcieńczenia — singiel może sam zepchnąć się na 0.94
  i kod to łapie. Potwierdzone testami test_tor_s.py:204-215.
- `ev()` (ev.py:175-178) wymusza `tax_factor in {1.00, 0.94, 0.88}` i
  podnosi wyjątek poza tym zbiorem. Reguła 20 spełniona, nic nie jest
  zaszyte w samym wzorze.
- `double_ev` zakłada niezależność i jawnie blokuje nogi z tego samego
  meczu.

---

## 3. `pricing/kelly.py` — stawkowanie

### [POWAŻNE] kelly.py:100-124 — bramka G-K jest polem, nie obliczeniem

    @dataclass(frozen=True)
    class KellyPolicy:
        bankroll: float
        peak_bankroll: float
        n_real_bets: int = 0
        clv_ci_low: float | None = None

**Co:** `gk_passed` czyta dwa **pola przekazane przez wołającego**.
Docstring modułu twierdzi: "KellyPolicy liczy warunek z dziennika i nie da
się jej poprosić o 0.5 bez spełnienia warunku". Kod tego nie robi — nie ma
w nim dziennika, nie importuje `BetJournal` ani `clv_report`.

**Naruszona reguła:** 21 w nowej formie ("0.5 wyłącznie po bramce G-K,
sprawdzanej **kodem, nie flagą**"). Dziś to dwie flagi:
`KellyPolicy(bankroll=X, peak_bankroll=X, n_real_bets=150, clv_ci_low=1e-9)`
daje `c = 0.5`. Odpowiedź wprost: **c=0.5 da się uzyskać bez spełnionej
bramki, trywialnie — wystarczy podać liczby**.

**Kierunek i skala:** `c` wprost mnoży stawkę, więc błędne przejście bramki
podwaja ekspozycję. Nie zawyża raportowanego yieldu (yield liczy się na
stawkę), ale podwaja wariancję i ryzyko ruiny — dokładnie to, przed czym
reguła 21 ma chronić.

### [POWAŻNE] wzmacniacz: clv.py:184 + market_benchmark.py:61 wobec metrics.py:59

`clv_report` uznaje CI za policzalne od `MIN_CLUSTERS = 5` klastrów (import
z `market_benchmark`), a `metrics.py` ma własny, **inny** próg
`_MIN_GROUPS = 8` i wystawia `BootstrapDiff.reliable` właśnie po to, żeby
oznaczyć CI z garstki klastrów jako nieinformacyjne. `ClvReport` nie ma
odpowiednika `reliable`. Skutek złożony z poprzednim znaleziskiem: CI
średniego CLV zbudowane z **pięciu tygodni ISO** wystarczy, żeby
`beats_closing` dało True, a stąd `gk_passed` i `c = 0.5`. Pięć klastrów to
5^5 = 3125 możliwych prób i kwantyle 2.5/97.5% z kilkunastu kombinacji.

### [DO SPRAWDZENIA] kelly.py:126-135 — wyłącznik przy peak_bankroll = 0

    @property
    def drawdown(self) -> float:
        if self.peak_bankroll <= 0.0:
            return 0.0

Odpowiedź wprost: **przy peak_bankroll = 0 wyłącznik nie działa** —
`drawdown = 0`, `switched_to_paper = False`, `mode = "real"`. Nie ma
walidacji `peak_bankroll >= bankroll` ani wyjątku na `peak_bankroll <= 0`.
Wołający, który zapomni utrzymywać szczyt (zostawi 0 albo ustawi
`peak = bankroll` przy każdym wywołaniu), dostaje bezpiecznik, który nigdy
się nie zapala, i nie zobaczy ostrzeżenia. Dziś brak jakiegokolwiek
wołającego, więc z kodu nie da się rozstrzygnąć, czy szczyt będzie
utrzymywany.

### [DROBNE] kelly.py:59-77 — `kelly_fraction` nie waliduje `tax_factor`

`ev()` wymusza zbiór {1.00, 0.94, 0.88}; `kelly_fraction` przyjmuje dowolną
liczbę bez kontroli i bez komunikatu. Dwa moduły wyceny trzymają regułę 20
na dwóch różnych poziomach rygoru. Wzór sam jest poprawny (reguła 22, na
kursie efektywnym `odds * tax_factor`).

### [DROBNE] kelly.py:151-155 — kod i docstring się rozchodzą

Docstring: "Dopóki nie ma bramki G-K, współczynnik wynosi 1". Kod stosuje
`clv_to_ev_ratio` zawsze, gdy nie jest None, niezależnie od `gk_passed`.
Kierunek bezpieczny (tylko zmniejsza), ale kontrakt nieprawdziwy.

### [CZYSTO] korekta CLV, limity, kolejność

- `shrink = min(1.0, max(0.0, self.clv_to_ev_ratio))` — korekta **nigdy nie
  zwiększa** stawki. Odpowiedź wprost: nie, nie może. Potwierdzone testem
  test_tor_s.py:299 (clv_to_ev_ratio=5.0).
- Limity składają się poprawnie i każdy tylko obcina: 2% na zakład
  (reguła 23), potem `max(0, 3% - match_exposure)`, potem
  `max(0, 15% - open_exposure)`. Żaden nie może podnieść `fraction`.
- `kelly_fraction` zwraca 0.0 dla EV <= 0 i dla `k*tax <= 1`, zamiast
  liczby ujemnej.
- `c` jest dodatkowo domknięte `min(value, _MAX_C)` — nigdy powyżej 0.5
  (reguła 21, druga połowa).

---

## 4. `backtest/clv.py` — CLV wobec zamknięcia Pinnacle

### [CZYSTO] brak migawki zamknięcia nigdy nie staje się zerem

Odpowiedź wprost: **nie, nie może**. Trzy miejsca pilnują tego spójnie:

- `ClvRow.clv: float | None` z komentarzem "None = brak migawki zamknięcia.
  NIE zero" (clv.py:52-53);
- `clv_rows` zwraca wiersz z `clv=None` i tekstowym `reason` w obu
  przypadkach braku (clv.py:81-93 brak wpisu lub brak gwizdka;
  clv.py:96-111 migawka poza tolerancją);
- `clv_report` filtruje `usable = [r for r in rows if r.clv is not None]`,
  raportuje `n_missing` osobno i przy pustym `usable` zwraca
  `mean=None, ci=None` z notatką (clv.py:170-180).

Przeszukałem moduł pod kątem `or 0`, `fillna`, `np.nan_to_num` — nie ma.

### [CZYSTO] tolerancja 30 minut jest jednostronna

    if not (kickoff - tolerance <= observed_at <= kickoff):

Migawka **musi** leżeć w oknie przed gwizdkiem; migawka po gwizdku jest
odrzucana z `reason`. Odpowiedź wprost: tak, tolerancja jest jednostronna i
w poprawną stronę (reguła 7 — kurs zamknięcia tylko do CLV, i tylko
sprzed gwizdka).

### [CZYSTO] klastrowanie po tygodniu ISO nie skleja sezonów

`_cluster` (clv.py:127-129) zwraca `f"{iso.year}-W{iso.week:02d}"` z
`kickoff.isocalendar()`. **Rok ISO jest w kluczu**, więc ten sam numer
tygodnia z dwóch lat to dwa różne klastry. Dodatkowo `run_lockbox.py:86-96`
używa własnego `_round_cluster`, który prefiksuje klucz jeszcze sezonem
(`season + "-W" + iso.year + "." + iso.week`), czyli jest nawet
drobniejszy. Jedyny efekt uboczny: mecze z różnych lig w tym samym
tygodniu wpadają do jednego klastra — to zmniejsza liczbę klastrów i
**poszerza** CI, czyli konserwatywnie.

### [POWAŻNE] clv.py:181-209 — średnia CLV jest warunkowana na sprawnym kolektorze

**Co:** `mean`, `ci_low`, `ci_high` i `beats_closing` liczą się wyłącznie na
zakładach, które **mają** migawkę zamknięcia. `n_missing` jest raportowane,
ale nie ma żadnego progu ani bramki: `beats_closing` może zwrócić True na
mocno przetrzebionym podzbiorze.

**Naruszona reguła:** 11 (liczba bez n i CI nic nie znaczy — tu n jest, ale
nie jest podane, z jakiej populacji) i duch reguły 26 (CLV jest metryką
nadrzędną, więc nie wolno jej liczyć na próbce wybranej mechanizmem
skorelowanym z tym, co mierzy).

**Mechanizm:** docstring tego samego modułu nazywa problem wprost —
"migawek brakuje najczęściej tam, gdzie coś się działo — mecz przełożony,
rynek zamknięty wcześniej, awaria kolektora w dniu meczowym". Dokładnie te
sytuacje korelują z dużym ruchem kursu, czyli z ekstremalnym CLV w obie
strony. Kod wyciąga z tego poprawny wniosek dla **pojedynczego wiersza**
(None, nie zero), a potem i tak raportuje średnią po pozostałych, nie
flagując, ile ich wypadło.

**Skala, zmierzona na realnych danych:** zamknięcie Pinnacle istnieje dla
3887 z 4151 meczów łącznie (93.6%), ale w lockboxie tylko dla **112 z 375**
(29.9%), i to wyłącznie z sezonu 2025/26 (raport `lockbox_3433f2c.json`,
`gaps.pinnacle.n = 112`, `seasons = ["2025/26"]`). Czyli najświeższy okres
— ten, na którym ma działać tor S — ma najgorsze pokrycie referencji.
Przy takim pokryciu `n_missing` nie jest przypisem, tylko główną liczbą.

**Jak sprawdzić:** porównać rozkład `|CLV|` na meczach z zamknięciem wobec
rozkładu ruchu kursu (kurs ostatniej migawki / kurs decyzyjny) na meczach
bez zamknięcia. Jeśli ten drugi ma grubszy ogon, selekcja jest
potwierdzona. Dane do tego są w migawkach kolektora.

### [DROBNE] clv.py:58-124 — brak kontroli `placed_at < kickoff`

`clv_rows` nie sprawdza, czy zakład był postawiony przed gwizdkiem, ani czy
migawka zamknięcia jest późniejsza niż `placed_at`. Zakład zapisany po
gwizdku (in-play, albo literówka w dzienniku) dostanie policzone CLV.
`BetRecord.__post_init__` pilnuje tylko relacji
`snapshot_observed_at < placed_at`, nie relacji do gwizdka — bo nie zna
`kickoff_utc`. Dziura w łańcuchu, a nie w jednym module.

### [DROBNE] clv.py:112 — `tax_factor_applied` w definicji CLV

    value = bet.odds_taken * bet.tax_factor_applied * p_close - 1.0

To nie jest CLV z reguły 24/26 ("CLV vs zamknięcie Pinnacle po Shinie"),
tylko przewaga **po podatku** wobec zamknięcia. Przy `tax = 0.88` liczba
wychodzi okolo -12% nawet dla idealnej ceny, więc `beats_closing` jest
wtedy nieosiągalne, a razem z nim bramka G-K (kelly.py:120-124). Kierunek
konserwatywny, ale konsekwencja jest realna: pod podatkiem ustawowym
`c = 0.5` nie odblokuje się nigdy, a raportowana liczba nie jest
porównywalna z CLV z literatury.

### [DROBNE] clv.py:163-209 — jedna liczba na wszystkie rynki i ligi

`ClvRow` niesie `market` i `league`, a `clv_report` je ignoruje: 1X2,
totale i spready z różnych lig lądują w jednej średniej i jednym CI.
Rynek dwustronny i trójstronny mają inną strukturę marży, więc mieszanie
ich zaciera to, co CLV ma pokazać.

### [DROBNE] clv.py:73 — filtr rozliczeń po polu tekstowym

`if bet.settled: continue` działa na `settled: str = ""`, więc polega na
pustym stringu jako "nie rozliczony". Działa, ale zależy od konwencji
zapisu w CSV, nie od typu.

---

## A. Sygnatury leakage w całym zakresie

Przeszukałem `src/valuebet/{models,pricing,backtest,features,live}` i
`scripts/` pod każdy wzorzec z listy. Wynik:

### A.1 `groupby().transform()` — [CZYSTO, jedno użycie, poprawne]

Jedyne wystąpienia: `features/base.py:206` i `:222`.

    return timeline.groupby("team_id", sort=False)[column].transform(
        lambda s: s.shift(1).rolling(window, min_periods=min_periods).mean()
    )

`shift(1)` jest **przed** `rolling()` (reguła 4, mechanizm z CLAUDE.md
"Fakty sekwencyjne"). Dodatkowo `base.py:176-181` wymusza sortowanie osi
po `kickoff_utc` i podnosi wyjątek, gdy nie jest rosnąca, oraz wymusza
tz-aware (`_require_utc`). Nie ma ani jednego `transform` z agregatem
liczonym na pełnym zbiorze.

### A.2 `rolling()` / `expanding()` bez `shift` — [CZYSTO]

Jedyne `rolling()` w kodzie produkcyjnym to dwa powyższe. Słowo
"expanding" występuje wyłącznie w docstringu
`dixon_coles_baseline.py:23` jako opis okna walk-forward (okno jest
rozszerzane filtrem `kickoff_utc < cutoff`, nie metodą pandas).

### A.3 `.mean()` / `.std()` / `fillna()` przed podziałem — [CZYSTO]

Wszystkie `.mean()` w `backtest/` liczą **metryki po predykcji**
(`ll_dc.mean()`, `ll_elo.mean()`, `values.mean()`), nie statystyki
normalizacyjne. Nie ma żadnego skalowania ani imputacji cech, bo DC i Elo
nie mają warstwy preprocessingu — to jedna z zalet tej architektury i
warto, żeby tak zostało.

Dwa `fillna(0)` w `dixon_coles_baseline.py:199-200` dotyczą kolumn
`history_home` / `history_away`, które docstring jawnie opisuje jako
**diagnostykę**, nie cechę; liczone są z `history`, czyli z ramki już
obciętej do `kickoff_utc < cutoff`.

`constant_probabilities` (`metrics.py:91-101`) liczy częstości 1X2
**z trainu** i powiela je na test — poprawnie, z komentarzem wyjaśniającym,
dlaczego z testu byłoby przeciekiem.

### A.4 `train_test_split` / `KFold` — [CZYSTO]

Zero wystąpień w `src/` i `scripts/`. Jedyne losowe przetasowanie w całym
repo to `tests/test_elo.py:140` (`sample(frac=1.0, random_state=7)`) i jest
to **test odporności**: sprawdza, że `compute_elo` daje ten sam wynik na
przetasowanym wejściu, czyli że sortuje samo. Podział jest wyłącznie
walk-forward po sezonach (reguła 8) w obu baseline'ach i w `run_m2.py`.

### A.5 Naiwny `datetime` (reguła 2) — [CZYSTO]

`uv run ruff check --select DTZ src scripts` -> **All checks passed**.
Pełne `uv run ruff check src tests scripts` -> **All checks passed**.
Wymuszenia w kodzie:

- `dixon_coles.py:258-263` — `kickoff_utc` musi mieć `DatetimeTZDtype`,
  inaczej wyjątek z powołaniem na regułę 2;
- `features/base.py` `_require_utc`;
- `fair.py:109`, `fair.py:114`, `digest.py:69`, `bets.py:62` — wyjątek na
  naiwny znacznik.

Zweryfikowane na danych: `matches.parquet.kickoff_utc` ma dtype
`datetime64[us, UTC]`.

### A.6 Odcięcie po dacie zamiast po godzinie — [CZYSTO, i to konserwatywnie]

`dixon_coles_baseline.py:262-266`:

    for _day, group in test.groupby(test["kickoff_utc"].dt.floor("D"), ...):
        cutoff = pd.Timestamp(group["kickoff_utc"].min())
        history = frame[frame["kickoff_utc"] < cutoff]

Grupowanie po dniu, ale **odcięcie po pierwszym gwizdku tego dnia**, z
nierównością ostrą. Mecz grany wcześniej tego samego dnia NIE wchodzi do
dopasowania dla meczu późniejszego. To jest ostrożniejsze niż reguła 2
wymaga. Zmierzone: 56.5% meczów (2345 z 4151) ma wcześniejszy mecz tego
samego dnia, więc gdyby odcięcie było po dacie, przeciek dotyczyłby
większości zbioru. Nie dotyczy.

Dodatkowo `dixon_coles.py:275-286` (`_time_weights`) podnosi wyjątek, gdy
jakikolwiek mecz ma `kickoff_utc > reference_date` — drugi, niezależny
bezpiecznik na tej samej ścieżce. Uwaga: nierówność jest `days < 0`, więc
mecz **dokładnie** w `reference_date` przeszedłby; w praktyce nieosiągalne,
bo `history` jest już obcięte ostrym `<`.

### A.7 Strefa źródłowa football-data a granica dnia — [CZYSTO, zmierzone]

`ingest/football_data.py:146` lokalizuje `Date + Time` jako
`Europe/London`. Dla POL.csv to założenie jest dyskusyjne (możliwa
rozbieżność 1 h wobec czasu polskiego), ale **nie może wpłynąć na
odcięcie**: rozkład godzin UTC w zbiorze to 10:00-19:00, zero meczów po
22:00 UTC, więc przesunięcie o godzinę nie przenosi żadnego meczu przez
granicę dnia UTC i nie zmienia grupowania `floor("D")`.

### A.8 `merge` po samym ID bez warunku czasowego — [CZYSTO w zakresie]

Wszystkie mergowania w `backtest/` i `scripts/` łączą **predykcje z
metrykami/referencjami po `match_id`**, czyli dwie wielkości przypisane do
tego samego meczu, już po tym, jak predykcja została policzona z danych
sprzed gwizdka. Kursy zamknięcia dołączane są po `match_id` — i to jest
poprawne, bo służą wyłącznie jako referencja po fakcie (reguła 7). Nigdzie
nie ma `merge` po `team_id` bez warunku czasowego, który wciągnąłby stan
późniejszy. `merge_asof` nie jest w tym zakresie używane (brak
`PointInTimeStore` — klasa B jeszcze nie jest podłączona).

### A.9 Elo: stan przed meczem — [CZYSTO, z dowodem]

`features/elo.py:191-193` ma jawną granicę ("ZAPIS CECHY. Wszystko poniżej
tej linii to już przyszłość") i rzeczywiście zapisuje `home_rating` /
`away_rating` **przed** aktualizacją (`:221-222`). Carry-over sezonowy jest
zastosowany przed odczytem cechy (`:180-189`), czyli pierwszy mecz sezonu
ma już ściągnięty rating — poprawnie.

Sprawdziłem podejrzenie, że przy 532 meczach o **identycznym**
`kickoff_utc` (12.8% zbioru) remis w kolejności `["kickoff_utc",
"match_id"]` wpuszcza wynik meczu równoległego do cechy meczu późniejszego
po match_id. **Nie wpuszcza**: aktualizacja Elo jest o sumie zerowej i
dotyka wyłącznie dwóch drużyn biorących udział w meczu, a żadna drużyna
nie gra dwóch meczów tego samego dnia — zmierzone na danych: liczba par
(dzień, drużyna) z więcej niż jednym meczem = **0**. Cecha meczu zależy
więc tylko od wcześniejszych meczów jego własnych dwóch drużyn, które
musiały się rozpocząć wcześniej. Brak przecieku i brak asymetrii wobec
konserwatywnego odcięcia DC.

---

## B. `metrics.py` i `market_benchmark.py` — n, CI, bootstrap klastrowy

### B.1 Accuracy — [CZYSTO]

Reguła 25 nienaruszona. `grep -i "accuracy|argmax|hit_rate|trafien"` po
`src/` i `scripts/` daje wyłącznie: docstring `metrics.py:3` deklarujący,
że accuracy nie istnieje w module, `argmax_xi` w docstringu `select_xi`
(wybór hiperparametru, nie metryka jakości) i trafienia harmonogramu w
kolektorze. **Nigdzie nie liczy się odsetka trafionych wyników.**

### B.2 Bootstrap klastrowy — [CZYSTO w implementacji]

`paired_bootstrap_diff` (metrics.py:140-202) robi dokładnie to, co obiecuje:
przy podanym `groups` losuje **całe klastry ze zwracaniem** i liczy średnią
jako `sum(sumy)/sum(liczności)` (estymator ilorazowy), a nie średnią ze
średnich sezonowych. To jest poprawny estymator dla raportowanej statystyki
punktowej. Deterministyczny `seed`. Parowanie po meczach jest wymuszone
kształtem (`x.shape != z.shape` -> wyjątek).

`clustered_slope` (market_benchmark.py:232-279) analogicznie: losuje klastry
i refituje `polyfit` na konkatenacji.

`clv_report` (clv.py:195-201) używa tej samej konstrukcji ilorazowej.

### B.3 Dwa różne progi liczby klastrów — [POWAŻNE]

- `metrics.py:59` -> `_MIN_GROUPS = 8`, wystawione jako
  `BootstrapDiff.reliable`, **nie blokuje** liczenia, tylko oznacza;
- `market_benchmark.py:61` -> `MIN_CLUSTERS = 5`, **blokuje** (CI = NaN
  poniżej progu).

Ten sam projekt ma więc dwie niezgodne odpowiedzi na pytanie "od ilu
klastrów wolno wydrukować CI", a `clv.py` i `run_lockbox.py` importują
**ten słabszy** (5). W przedziale 5-7 klastrów CI jest drukowane jako
liczba, mimo że `metrics.py` uznałby je za nieinformacyjne. Skutek
praktyczny opisałem w sekcji 3: to jest droga do `c = 0.5` przez bramkę
G-K opartą na pięciu tygodniach.

Gdzie `reliable` jest w ogóle konsultowane: tylko
`dixon_coles_baseline.py:581` i `elo_baseline.py:507-509` (formatowanie
raportu tekstowego). **`run_lockbox.py` i `run_m2.py` go nie czytają** —
w JSON nie ma ani jednego pola `reliable`. Dla tych konkretnych raportów to
nieszkodliwe, bo liczby klastrów są wysokie (lockbox: 44 i 42, pinnacle 14;
m2: 10 sezonów), ale to szczęście, nie bezpiecznik.

### B.4 Czy każda raportowana liczba ma n i CI (reguła 11) — [DROBNE]

- Różnice (to, na czym stoją wnioski) mają n, CI i `significant`:
  `dc_minus_elo`, `elo_minus_market`, `dc_minus_market`,
  `pool_minus_market`, `slope_T_ou_on_T_1x2`. Tu jest w porządku.
- Wartości **bezwzględne** log lossu są gołymi liczbami bez CI:
  `report["ll"]["dc"] = 1.0627`, `per_season[].ll_dc`, `ll_pool`,
  `ll_market`, `ll_model`. Bronić się da (porównania są parowane, a CI
  różnicy jest tym, co ma znaczenie), ale `per_season` z n=69 dla 2026/27
  to liczba, którą łatwo przeczytać jako ustalenie — a 69 meczów to szum.
- `reliability_table` podaje `n` i `se_observed` per koszyk. Dobrze.
- Żaden z raportów nie zawiera yieldu ani liczby zakładów, bo tor S nie
  został jeszcze uruchomiony — reguła 11 w swojej właściwej treści nie ma
  dziś czego dotyczyć.

### B.5 `market_probabilities` — [CZYSTO]

- wymaga jednego bukmachera na wywołanie i podnosi wyjątek na powtórzonym
  `match_id` (metrics.py:267-270) — to pilnuje kompletności rynku na
  poziomie struktury (reguła 17);
- `shin_probabilities` dostaje trzy kursy 1X2 naraz, nigdy podzbiór;
- mecze bez zbieżności są **pomijane** i policzone w
  `.attrs["not_converged"]`, nie wypełniane niczym;
- NaN w kursach podniósłby wyjątek w `implied_probabilities`. Zweryfikowane
  na danych: w `closing_odds.parquet` zero NaN w `odds_home/draw/away` i
  zero przypadków booksum < 1 u Pinnacle'a, więc ścieżka awaryjna nie jest
  dziś używana.

### B.6 `instrument_validation.json` — [POWAŻNE: kryterium przechodzi, mocniejsza statystyka odrzuca]

To nie jest leakage, ale jest to zawyżona ocena instrumentu i wpływa na
regułę 19a. W tym samym pliku, dla obu wariantów rho:

    rho_zero   : sd_ratio 1.119  r 0.936  slope 0.8364  CI [0.8081, 0.8600]
    rho_median : sd_ratio 1.211  r 0.940  slope 0.7766  CI [0.7535, 0.7969]
    criterion  : "sd_ratio in [0.8, 1.25] AND correlation >= 0.7"  -> valid: true

Kryterium (spisane przed wynikiem, więc uczciwe) patrzy na `sd_ratio` i `r`.
Ale `market_benchmark.py:15-27` sam argumentuje, że **nachylenie** jest tą
statystyką, która ma moc ("własność wieży": jeśli oba odczyty mierzą to
samo, nachylenie = 1). Nachylenie wychodzi 0.78-0.84, a jego CI
**wyklucza 1.0** z dużym marginesem. Czyli: suma goli wyprowadzona z 1X2
jest systematycznie o ~16-22% **za szeroka** względem odczytu z rynku
totali, i to jest zmierzone z CI o półszerokości 0.02.

Dodatkowo `sd_ratio = 1.211` dla wariantu z rho z Ekstraklasy leży 0.04 od
progu odrzucenia 1.25, a `mean_T_1x2 = 2.6156` vs `mean_T_ou = 2.9016` dla
`rho_zero` to rozjazd 0.29 gola w **poziomie**, nie w rozrzucie — przy
`rho_median` poziomy się zgadzają (2.9019 vs 2.9016), co pokazuje, że rho
jest dopasowywane do poziomu, a nie walidowane.

**Konsekwencja:** `any_valid: true` jest formalnie prawdziwe wobec
zadeklarowanego kryterium, ale instrument jest obciążony i każda liczba
"suma goli z 1X2" dziedziczy to obciążenie. Reguła 19a wymaga dla totali
λ, μ dopasowanych do Pinnacle 1X2 **i** totali — ten raport jest dowodem,
dlaczego to "i" jest konieczne, a nie potwierdzeniem, że 1X2 wystarcza.

---

## C. `pricing/shin.py`

### C.1 Zgodność z CONTEXT §5.1-5.4 — [CZYSTO, zgodność dosłowna]

- §5.1 (solver Brenta, nie iteracja punktu stałego): `_solve_z` używa
  `brentq` na `g(z) = sum(p_i(z)) - 1`, przedział `[0, 1-1e-12]`, z
  komentarzem wyjaśniającym, dlaczego nie iteracja. Zgodne.
- §5.2 (granica z -> 0 to `pi/sqrt(P)`, NIE `pi/P`): `_apply_shin:245-246`
  ma dokładnie `pi / np.sqrt(bsum)` przy `z < _Z_EPS = 1e-10`, z pełnym
  wyprowadzeniem w docstringu. To jest ten jeden warunek, którego złamanie
  degeneruje moduł bez żadnego sygnału — jest poprawny.
- §5.3 (wzory referencyjne, `shin_forward`): wzory zgodne znak po znaku,
  w tym `sqrt(P) = sum sqrt(p*((1-z)*p + z))`.
- §5.4 (dlaczego nie proporcjonalna): docstring modułu powtarza argument i
  liczby; nie ma w kodzie produkcyjnym żadnej ścieżki `(1/k)/sum(1/k)`
  **poza** opisaną niżej.

### C.2 Zachowanie dla n = 2 — [CZYSTO, zweryfikowane liczbowo]

Rynki dwustronne są teraz używane realnie: `fair.py:50`
(`"totals": 2, "spreads": 2`) i `validate_instrument.py:84-86` (O/U 2.5).
Sprawdziłem cztery reprezentatywne książki:

    (1.90, 1.98)  booksum 1.0314  z=0.0314  shin [0.510633, 0.489367]
    (1.05, 15.0)  booksum 1.0190  z=0.0203  shin [0.942857, 0.057143]
    (1.33, 3.50)  booksum 1.0376  z=0.0380  shin [0.733083, 0.266917]
    (2.05, 1.85)  booksum 1.0283  z=0.0283  shin [0.473632, 0.526368]

Wszystkie `converged=True`, `z` w oczekiwanym zakresie 0.02-0.04, suma = 1.
Różnica wobec proporcjonalnej idzie w **poprawną stronę**: dla (1.05, 15.0)
proporcjonalna daje longshotowi 0.0654, Shin 0.0571 — czyli Shin obniża
outsidera o 0.83 pp, dokładnie tak, jak opisuje §5.4. Bracketing dla n=2
jest matematycznie gwarantowany, bo `g(1-) = sum(pi^2)/P - 1 < 0` zachodzi
zawsze, gdy każde `pi < 1` (czyli każdy kurs > 1), a to jest wymuszone w
`implied_probabilities:104-107`.

Test losowy: 20000 trójstronnych książek z booksumem > 1 i kursami z
`U(1.01, 50)` — **zero** przypadków `converged=False`. Ścieżka awaryjna jest
nieosiągalna dla poprawnej książki z marżą.

### C.3 [POWAŻNE — latentne] shin.py:217-221 — ścieżka braku zbieżności zwraca normalizację proporcjonalną

    g_hi = g(hi)
    if g_lo * g_hi > 0.0:
        # ... schodzimy na proporcjonalną i sygnalizujemy brak zbieżności.
        return 0.0, 0, False

Po tym `shin_probabilities` i tak liczy `probs = _apply_shin(pi, bsum, 0.0)`
czyli `pi/sqrt(P)`, a potem `probs / probs.sum()` -> **`pi/P`, dokładnie
normalizacja proporcjonalna**, i zwraca ją w `ShinResult.probabilities`.

Zweryfikowane na ścieżce `allow_underround=True`, `[2.5, 3.0, 4.0]`:

    booksum = 0.9833  z = 0.0000  converged = False
    zwrocone p     = [0.40678, 0.338983, 0.254237]
    proporcjonalna = [0.40678, 0.338983, 0.254237]   identyczne: True

**Naruszona reguła:** 16 ("Normalizacja proporcjonalna jest **zabroniona** w
kodzie produkcyjnym"). Funkcja nie podnosi wyjątku, tylko zwraca zakazaną
liczbę opakowaną we flagę. Jedyną ochroną jest dyscyplina wołającego.

Stan dyscypliny — policzyłem wszystkie trzy wywołania w kodzie poza
testami, każde sprawdza `converged`:

- `fair.py:167` -> `if not result.converged: ... continue`
- `metrics.py:278` -> `if not result.converged: not_converged += 1; continue`
- `validate_instrument.py:87-88` -> `three.probabilities if three.converged
  else [np.nan]*3`

Czyli **dziś nic tej liczby nie zużywa**. Klasyfikuję jako POWAŻNE-latentne,
nie KRYTYCZNE: kierunek po realizacji jest znany i jednostronny (zawyżenie
longshotów, fałszywe +EV na wysokich kursach — zmierzone w CONTEXT §5.4 jako
2.3 pp EV na kursie 4.50), a wystarczy jedno nowe wywołanie bez sprawdzenia
flagi, żeby się zapaliło. Dodatkowo `allow_underround=True` jest jedynym
realnym sposobem dojścia tu dla książki z marżą, a jego docstring zachęca:
"Użyj allow_underround=True, jeśli świadomie podajesz zagregowane kursy z
wielu bukmacherów" — i w tym właśnie scenariuszu dostaniesz proporcjonalną.

### C.4 [DROBNE] shin.py:226 — `iterations` zwraca `max_iter`, nie liczbę iteracji

    z = float(brentq(g, lo, hi, xtol=tol, rtol=..., maxiter=max_iter))
    return z, max_iter, True

`ShinResult.iterations` to zawsze 200 po udanym brentq. Pole jest
udokumentowane jako "liczba iteracji do zbieżności" i jest nieprawdziwe.
Nie ma skutku liczbowego, ale gdyby ktoś diagnozował zbieżność po tym polu,
nie dowie się niczego.

### C.5 [DROBNE] shin.py:165-172 — booksum == 1 zwraca `pi` bez zmian

Przy `abs(bsum - 1) < 1e-12` funkcja zwraca surowe `pi` jako
prawdopodobieństwa z `z = 0` i `converged = True`. To jest poprawne
matematycznie (brak marży = brak czego usuwać), ale jest też jedyny
przypadek, w którym `converged = True` idzie w parze z wynikiem
nierozróżnialnym od proporcjonalnego. Dla realnej książki nieosiągalne.

---

## D. `backtest/dixon_coles_baseline.py`

### D.1 Rozdział siatka/predykcja (§11.9 pkt 5) — [CZYSTO, kierunek bezpieczny]

    try:
        scales = _scales_for_window(frame, before, xi, max_iter=max_iter)
        run = _walk_forward_season(frame, season, xi, scales, ...)
    except NumericalInstabilityError as exc:
        cache[season, xi] = -math.inf
        log.warning("kandydat xi=%.4f odrzucony dla walidacji %s: %s", ...)
        continue

Pytanie, czy `except` zjada wyjątek, którego nie powinien. Prześledziłem
wszystkie `raise` w `models/dixon_coles.py` (linie 255, 257, 260, 266, 272,
282, 323, 421, 633, 646, 652, 668, 811, 959, 967, 981, 1026, 1060, 1108,
1146):

- `NumericalInstabilityError` i jej podklasa `DegenerateSpreadError`
  podnoszone są **wyłącznie** z `_standard_errors` (:811) i
  `empirical_bayes_scales` (:959, :967, :981) — czyli tylko z gałęzi
  `_scales_for_window`;
- `fit_dixon_coles`, `log_likelihood`, `score_matrix`,
  `probabilities_1x2` podnoszą `RuntimeError` / `ValueError`, które **nie
  są** łapane i lecą w górę (brak zbieżności :668, `tau <= 0` :1026/:1060,
  masa poza obcięciem :1146).

Czyli `_walk_forward_season` w praktyce nie może rzucić wyjątku z tej
rodziny i `except` obejmuje dokładnie to, co miał obejmować. Nawet gdyby
kiedyś zaczął — skutkiem byłoby `cache = -inf`, czyli **odrzucenie
kandydata**, nigdy zachowanie liczby. Kierunek błędu jest więc
konserwatywny. W ścieżce predykcji (`run_dixon_coles_baseline:447-454`)
`empirical_bayes_scales` jest wołane **poza** jakimkolwiek `try`, z
komentarzem "bezpiecznik ma tu podnieść wyjątek, nie zostać zjedzony" —
zgodnie z §11.9 pkt 5.

### D.2 Cache LL(V, xi) i sezony późniejsze niż V — [CZYSTO, z dowodem w kodzie i w testach]

Odpowiedź wprost: **nie, wpis dla V nie może zależeć od sezonu
późniejszego niż V.** Trzy niezależne ograniczenia:

1. `scales = _scales_for_window(frame, before, xi)` z
   `before = seasons[:index]`, a `_scales_for_window` filtruje
   `frame[frame["season"].isin(seasons_before)]` i ustawia
   `reference_date = max(kickoff_utc)` tego okna;
2. `_walk_forward_season(frame, V, ...)` fituje na
   `history = frame[frame["kickoff_utc"] < cutoff]`, gdzie `cutoff` to
   pierwszy gwizdek dnia meczowego w V — ostra nierówność, więc nic z V ani
   po V;
3. `select_xi` sumuje `cache[season, xi]` wyłącznie po
   `enumerate(seasons[:test_index])`, czyli V < S.

Potwierdzone istniejącymi testami, które realnie falsyfikują:
`tests/test_dixon_coles_baseline.py:166` (`test_future_poison_hyperparameter
_selection` — zatrucie `home_goals=99` we wszystkich sezonach od S w górę i
`assert clean_cache == dirty_cache`), `:203`
(`test_xi_cache_entry_does_not_depend_on_test_season` — cache z 4 i z 5
sezonów musi mieć identyczne wspólne wpisy), `:240`
(`test_future_poison_dixon_coles_walk_forward`).

### D.3 [DROBNE] pierwszy sezon testowy stoi na jednym sezonie walidacyjnym

`select_xi` dla `test_index = min_train_seasons = 3` daje
`used = [seasons[2]]`, czyli **jeden** sezon walidacyjny — a docstring tej
samej funkcji argumentuje, że "jeden sezon walidacyjny ma za mało sygnału"
i to właśnie pojedynczy sezon wybrał kiedyś `xi = 0.008` i zdegenerował
2019/20. Potwierdzone w `reports/diag_313591a.json`:
`2015/16 -> n_validation_seasons: 1`. Liczba jest raportowana, więc nie jest
ukryta, ale pierwszy sezon testowy ma słabszą gwarancję niż pozostałe.

### D.4 [DROBNE] `n_rejected_xi` liczy pary (V, xi), nie kandydatów

`run_dixon_coles_baseline:440-445` sumuje po `used x xi_grid`, więc jeden
beznadziejny `xi` odrzucony na pięciu sezonach walidacyjnych raportuje się
jako 5. W `diag_313591a.json` wszystkie wartości to 0, więc dziś bez
znaczenia.

### D.5 [DO SPRAWDZENIA] xi i tau dla 2026/27 wybrane z udziałem 2025/26, czyli drugiego sezonu lockboxa

Przy 15 sezonach w danych `select_xi` dla S = 2026/27 (`test_index = 14`)
używa `used = seasons[2:14]`, co zawiera **2025/26**, a
`empirical_bayes_scales` dla tego sezonu dostaje `train_seasons = seasons[:14]`,
też z 2025/26. Formalnie jest to poprawny walk-forward (V < S, brak
informacji z przyszłości) i reguła 8 jest spełniona. Ale oznacza, że dwa
sezony lockboxa nie są wobec siebie niezależne: konfiguracja użyta na
2026/27 została dobrana z udziałem pierwszego sezonu lockboxa. Przy
`n = 69` meczów dla 2026/27 (`lockbox_3433f2c.json`) ta liczba i tak nie
niesie informacji — `per_season.ll_dc = 1.0528` na 69 meczach to szum o
półszerokości rzędu 0.1.

---

## E. Reguła 19a — czy macierz DC wycenia totale, handicapy albo kombinacje

Odpowiedź wprost: **nie. Reguła 19a nie jest naruszona.** Nie ma ani jednego
miejsca, w którym macierz DC produkuje cenę, próg kursowy, EV albo stawkę
dla totalu, handicapu lub kombinacji.

Policzyłem wszystkie wywołania `matrix_from_rates` / `score_matrix` /
`over_probability` w `src/` i `scripts/`:

- `dixon_coles.py:1112` (`score_matrix`) i `:1167` (`probabilities_1x2`) —
  wyłącznie rynek 1X2;
- `market_benchmark.py:77` (`outcome_probabilities`) — 1X2;
- `market_benchmark.py:94` (`over_probability`) — P(suma > linia) z macierzy
  DC. Dwóch konsumentów, oba **diagnostyczne**:
  - `scripts/run_diagnostics.py:311` — tabela kalibracji P(over 2.5) wobec
    realizacji na zbiorze dev. To jest **pomiar**, który uzasadnił regułę
    19a, nie jej złamanie;
  - `market_benchmark.py:173` wewnątrz `implied_total_from_over`, czyli
    **odwrócenia ceny rynkowej** na implikowaną sumę goli. Kierunek jest
    odwrotny do wyceny: wejściem jest `q_over` z rynku Pinnacle, wyjściem
    `T`. Dodatkowo `ratio = lambda/mu` bierze się z odwrócenia 1X2, czyli to
    jest dokładnie konstrukcja "λ, μ dopasowane do kursów Pinnacle 1X2 **i**
    totali", którą reguła 19a nakazuje.
- Kombinacje: `pricing/ev.double_ev` liczy EV dubletu z `p` podanych per
  noga. Nie ma w repo żadnej ścieżki, która podałaby tam `p` z macierzy DC;
  jedynym producentem `p` w torze S jest `fair.py` (Shin na Pinnaclu).
  `pricing/markets.py` (ogólna wycena z macierzy) **nie istnieje** —
  docstring `probabilities_1x2` zapowiada go w przyszłości.
- `fair.py:50` obsługuje `totals` i `spreads` wyłącznie przez Shina na
  migawkach Pinnacle, bez udziału DC.

### [DO SPRAWDZENIA] `over_probability` jest jeden import od naruszenia

Funkcja jest publiczna (`market_benchmark.__all__`), ma sygnaturę
`(lam, mu, rho, line)` i nie ma żadnego oznaczenia "tylko diagnostyka" w
nazwie ani żadnego bezpiecznika. Reguła 19a jest dziś utrzymywana wyłącznie
tym, że nikt jej jeszcze nie zawołał z λ, μ z DC do wyceny. Dowód, jak mały
to margines, jest w `m2_313591a.json`: nachylenie osi otwartości
`A_openness.slope = 3.059` z CI [1.780, 3.954], `sd_ours = 0.0361` wobec
`sd_market = 0.2204` — czyli rozrzut przewidywanej otwartości DC jest
**sześć razy** węższy od rynkowego. Każdy total wyceniony z tej macierzy
byłby ściśnięty do średniej ligowej i produkował pozorne +EV na obu
stronach linii naprzemiennie.

---

## PYTANIE 1 — Czy wycena toru S jest szczelna czasowo?

### Odpowiedź: NIE. Są trzy ścieżki, którymi dane późniejsze niż decyzja wchodzą do wyceny lub stawki, i jedna, która jest szczelna.

**Ścieżka 1 (KRYTYCZNA) — `tax_factor` przez `BetclicTaxRegime._window`.**
`pricing/ev.py:98-103`. Okno nie ma górnej granicy czasowej, więc zakłady z
`placed_at > now` wchodzą do udziału AKO, a stąd do `tax_for_single` i
`tax_for_ako`, a stąd do `ev()`, `min_odds()` i `kelly_fraction()`.
Zmierzone: 0.94 -> 1.00, czyli 6 pp EV na stawce. To jest wycena z
przyszłości w dosłownym sensie: dziś nie wiem, ile AKO postawię w
listopadzie, a kod to wykorzystuje.

**Ścieżka 2 (POWAŻNA) — `clv_to_ev_ratio` i `clv_ci_low` do stawkowania.**
`pricing/kelly.py:105-107, 151-155`. CLV jest metryką PO fakcie i w
`backtest/clv.py` jest użyte poprawnie (p_close z zamknięcia, wyłącznie do
pomiaru). Ale `KellyPolicy` przyjmuje **agregat CLV** jako wejście do
wielkości stawki i do ułamka Kelly'ego. Nic w kodzie nie wymusza, by ten
agregat był policzony wyłącznie z zakładów **rozliczonych przed** chwilą
tej decyzji. `clv_report` nie przyjmuje żadnego `as_of` i liczy średnią po
wszystkim, co mu podasz. Najprostsze podłączenie — `clv_report(clv_rows(
journal.read(), ...))` raz na dzień i wstrzyknięcie wyniku do `KellyPolicy`
— daje stawkowanie zasilane CLV zakładów z przyszłości względem części
pozycji. Kierunek: `shrink` tylko zmniejsza stawkę, więc przeciek działa
jak selekcja po fakcie (mniejsze stawki tam, gdzie rynek się potem
poprawił), co **zawyża** symulowany yield.

**Ścieżka 3 (POWAŻNA) — brak granicy gwizdka w `fair_prices`.**
`pricing/fair.py:91-96` nie przyjmuje `kickoff_utc`, więc jedynym warunkiem
jest `observed_at < decision_time`. Przy odtwarzaniu historycznym
`decision_time` późniejszy niż gwizdek wycenia z migawek in-play i nie
zostawia żadnego ostrzeżenia. Reguła 2 mówi wprost: granicą odcięcia jest
godzina rozpoczęcia meczu. Ta granica jest sprawdzana dopiero w
`digest.py:76` i tylko tam.

**Ścieżka szczelna — dziennik.** `live/bets.py:64-71`:

    if (self.snapshot_observed_at is not None
            and self.snapshot_observed_at >= self.placed_at):
        raise ValueError("migawka nie jest sprzed zakładu — wycena z przyszłości")

To jest najmocniejszy bezpiecznik w całym torze S: relacja
`snapshot_observed_at < placed_at` jest wymuszona **w konstruktorze**, więc
nie da się zapisać wiersza z wyceną z przyszłości, także przy odczycie CSV
(`read()` buduje `BetRecord`, więc walidacja działa na wejściu). Brak
strefy w `placed_at` też podnosi wyjątek. Czego ten bezpiecznik nie
sprawdza: relacji do gwizdka (`BetRecord` nie zna `kickoff_utc`) ani
`tax_factor_applied` wobec reżimu obowiązującego w `placed_at`.

**CLV sam w sobie — czysto.** `p_close` z zamknięcia to dozwolone użycie
(reguła 7, reguła 24/26): tolerancja jednostronna przed gwizdkiem,
`clv=None` przy braku, bez wycieku do ceny wejścia. Wyciek nie jest w CLV,
jest w tym, że stawka czyta agregat CLV bez granicy czasowej.

---

## PYTANIE 2 — Czy reguła 19 jest nienaruszona po wyjątku dla toru S?

### Odpowiedź: TAK. Kurs rynkowy nigdzie nie jest cechą modelu.

Policzyłem wszystkie miejsca w `src/` i `scripts/`, które czytają kursy
zamknięcia, i do czego ich używają — **dziewięć**, żadne nie jest cechą:

| miejsce | co robi z kursem | status |
|---|---|---|
| `ingest/football_data.py:376-425` | buduje tabelę `closing_odds`, **celowo rozłączną** z ramką meczów (`ParseResult` docstring: "matches i closing_odds są celowo rozłączne") | produkcja danych |
| `backtest/metrics.py:252-296` | Shin na 1X2 jednego bukmachera -> `p_home/p_draw/p_away`, docstring: "WYŁĄCZNIE jako punkt odniesienia — nigdy jako cecha modelu" | referencja |
| `backtest/elo_baseline.py:380-397` | ten sam Shin, potem `_market_gap` (log loss Elo vs rynek) | referencja |
| `backtest/dixon_coles_baseline.py:512-524` | `_market_frames`, potem `_market_gap` dla DC | referencja |
| `backtest/clv.py:60` | `p_close` do CLV | metryka po fakcie |
| `backtest/market_benchmark.py` | odwrócenie 1X2/totali rynku na λ, μ, T | diagnostyka |
| `scripts/run_diagnostics.py:134` | referencja i benchmark G4 | diagnostyka |
| `scripts/run_lockbox.py:148, 192-198` | luki do rynku, osobno per referencja | referencja |
| `scripts/run_m2.py:76-82` | **shrinkage target** w puli logarytmicznej | jawny wyjątek reguły 19 |

**Modele są czyste — zweryfikowane grepem:** ani
`models/dixon_coles.py`, ani `models/elo_ordinal.py`, ani
`features/base.py`, ani `features/elo.py` nie zawierają słowa `closing`,
`odds`, `PSC` ani żadnego importu z `pricing/`. `fit_dixon_coles` przyjmuje
wyłącznie `kickoff_utc, home_team_id, away_team_id, home_goals, away_goals`
(`_REQUIRED_COLUMNS`, dixon_coles.py:157-159) i podnosi wyjątek na braku
tych kolumn — nie ma gdzie wsunąć kursu. `OrdinalElo.fit` przyjmuje
`(elo_diff, outcome)`. `compute_elo` przyjmuje tylko ramkę meczów.

**Pula logarytmiczna w `run_m2.py` — shrinkage target, zgodnie z regułą:**

    logs = weight * log(model) + (1 - weight) * log(market)

`weight` dla sezonu S jest dopasowywana **wyłącznie na sezonach
wcześniejszych** (`run_m2.py:101-112`), a pierwszy sezon dostaje `weight=0`
("brak sezonów wcześniejszych — nie ma na czym dobrać wagi. Zero znaczy sam
rynek, czyli najostrożniejszy wybór"). Rynek wchodzi jako drugi składnik
gotowej mieszanki, nie jako wejście do dopasowania DC — DC został dopasowany
wcześniej, bez dostępu do kursów. To jest dokładnie ten jeden wyjątek, który
reguła 19 dopuszcza, i jest oznaczony w docstringu modułu.

Werdykt M2 jest przy tym negatywny: `pool_minus_market.mean = +0.00149`,
CI [-0.00028, +0.00396], `significant: false` -> "model NIE wnosi informacji
ponad rynek". Czyli wyjątek dla toru S (wyceniaczem jest Pinnacle po
Shinie) jest uzasadniony pomiarem, nie wygodą.

**Jedna uwaga:** reguła 19 broni modelu, ale nie broni **progu**.
`digest.py:86` liczy `min_odds(p, tax_factor, edge_threshold)` z `p`
pochodzącego z Pinnacle'a, a człowiek porównuje ten próg z tablicą u
Betclica. To jest zamierzona konstrukcja toru S (arbitraż informacyjny
między bukmacherami), ale oznacza, że **cały tor S z definicji nie bije
Pinnacle'a** — bije tylko Betclica. CLV wobec zamknięcia Pinnacle będzie
więc dla toru S miarą jakości migawki, nie miarą przewagi, i reguła 26
("model, który nie bije zamknięcia, nie ma przewagi") nie przekłada się na
niego wprost. Warto to zapisać, zanim pojawi się raport z CLV ~0 i wniosek,
że tor S nie działa.

---

## PYTANIE 3 — Czy lockbox jest rzeczywiście chroniony?

### Odpowiedź: NIE w pełni. Liczbę decyzyjną na lockboxie da się policzyć bez wywołania bezpiecznika, na pięć sposobów. Żaden nie został faktycznie wykorzystany w istniejących raportach, ale żaden nie jest też zablokowany.

`assert_no_lockbox` jest wołane dokładnie **dwa razy** w całym repo:
`scripts/run_diagnostics.py:169` i `scripts/run_m2.py:75`. Obydwa poprawnie,
na ramce po `split_dev_lockbox` albo na wczytanym `dev_<commit>.parquet`.

### Dziura 1 (POWAŻNA) — baseline'y zwracają lockbox w wyniku, bez bramki

`run_elo_baseline(matches, closing)` i `run_dixon_coles_baseline(matches,
closing)` są wołane na **pełnej** ramce (run_diagnostics.py:137-139,
run_lockbox.py:151-153). Zwracany `report.predictions` zawiera wszystkie
sezony testowe, w tym 2025/26 i 2026/27, a `report.pooled_gaps` oraz
`report.pooled_log_loss` są policzone **na całości**, z lockboxem w środku.
Żadna z tych funkcji nie zna modułu `lockbox` i nie woła bezpiecznika.
Dowolny nowy skrypt, który wypisze
`run_dixon_coles_baseline(matches, closing).pooled_log_loss`, dostanie
liczbę skażoną lockboxem i nie zobaczy ostrzeżenia.

W istniejących raportach ta dziura nie została wykorzystana:
`run_diagnostics.py` nie zapisuje `pooled_gaps` ani `pooled_log_loss`
(sprawdzone — w `diag_313591a.json` nie ma pola z luką pooled), a wszystkie
publikowane liczby idą z ramki `dev` po bezpieczniku.

### Dziura 2 (POWAŻNA) — zduplikowana definicja lockboxa poza bezpiecznikiem

`scripts/run_diagnostics.py:155-157` filtruje sezony lockboxa **literałami**,
a nie stałą `LOCKBOX_SEASONS`:

    for s in dc.seasons
    if s.season not in ("2025/26", "2026/27")

Jeśli lista sezonów lockboxa się zmieni, ten filtr cicho przestanie się z
nią zgadzać i blok `seasons` w raporcie diagnostycznym zacznie publikować
sezon odłożony. Ta sama klasa błędu, przed którą broni reguła 15 (jedno
źródło prawdy), tylko dla sezonów zamiast nazw drużyn.

### Dziura 3 (POWAŻNA) — `validate_instrument.py` nie woła bezpiecznika w ogóle

`scripts/validate_instrument.py:36` ma `SEASONS = ("1920", ..., "2425")`.
Dziś lockboxa nie dotyka: to sezony Premier League do 2024/25. Ale
`parse_main_league` produkuje etykietę w **tym samym formacie** co
`LOCKBOX_SEASONS` (`football_data_main.py:92`, `_season_label("2526")` daje
`2025/26`), więc dopisanie jednego kodu sezonu wprowadziłoby sezon
odłożony do zbioru, na którym liczy się `valid: true/false` — liczba w
pełni decyzyjna, bo reguła 19a opiera się na tym raporcie. Bezpiecznik
zadziałałby, gdyby został zawołany. Nie jest.

### Dziura 4 (POWAŻNA) — nic nie liczy, ile razy lockbox był oglądany

Cała wartość lockboxa stoi na zdaniu z `lockbox.py:11-12`: dwa ostatnie
sezony są odłożone i oglądane **dokładnie raz**. W kodzie nie ma licznika,
pliku-blokady ani odmowy startu przy istniejącym raporcie.
`run_lockbox.py:126` zapisuje do `reports/lockbox_{commit}.json`, więc każdy
nowy commit daje nowy plik i ewaluację można powtarzać dowolnie wiele razy,
zbierając kolejne wyniki. Dokładnie ten zarzut, który `_assert_frozen`
stawia deklaratywnemu zamrożeniu, dotyczy tu samej liczby spojrzeń.

### Dziura 5 (POWAŻNA, dotyczy już wydanego raportu) — `_assert_frozen` nie obejmuje `backtest/`

`run_lockbox.py:59`: `FROZEN_DIRS = ("src/valuebet/models", "src/valuebet/features")`.
Cała logika walk-forward, wybór xi, cache LL(V, xi), Shin i metryki żyją w
`src/valuebet/backtest/` i `src/valuebet/pricing/` — **poza zamrożeniem**.

Mocniejszy dowód: `reports/lockbox_3433f2c.json` deklaruje
`commit_frozen: 3433f2c`, ale `git show --stat 3433f2c` pokazuje, że ten
commit dotknął wyłącznie `scripts/odds_budget.py`,
`ingest/odds_collector.py` i `tests/test_odds_collector.py`, a
`scripts/run_lockbox.py` **został dodany dopiero w 4b98818**. Raport powstał
więc z **niezacommitowanego** skryptu przy HEAD na 3433f2c, a `_commit()`
nadał mu etykietę sugerującą pełną odtwarzalność z tamtego commita. Z
3433f2c nie da się go odtworzyć, bo tam nie ma czym.

Okoliczność łagodząca jest realna: `src/valuebet/models/` nie zmieniał się
od `313591a`, a `features/` od `fb9ec10`, więc same **modele** przy tym
przebiegu faktycznie były zamrożone i `_assert_frozen` nie miał czego
wykryć. Log loss z lockboxa pochodzi z modeli z 313591a. Problem jest w
etykiecie i w zasięgu bezpiecznika, nie w tym, że model był grzebany
pomiędzy.

### Co jest chronione dobrze

- `split_dev_lockbox` wrzuca sezony spoza obu list do **deweloperskiego**,
  czyli nowy sezon w danych jest domyślnie materiałem roboczym, nie
  odłożonym. Właściwy kierunek domyślny.
- `assert_no_lockbox` sprawdza przecięcie zbiorów i podnosi `RuntimeError` z
  nazwą liczby (`what=`), więc komunikat jest użyteczny w diagnozie.
- `run_lockbox.py` niesie w JSON zastrzeżenie o niedziewiczości lockboxa i
  to zastrzeżenie jest prawdziwe oraz istotne przy czytaniu wyniku.
- `run_m2.py` czyta `dev_<commit>.parquet` i wywołuje bezpiecznik, zamiast
  liczyć od zera na pełnej ramce. Dobry wzorzec do powtórzenia.

---

## PYTANIE 4 — Czy bezpieczniki numeryczne w `dixon_coles.py` można obejść?

### Odpowiedź: NIE. Wszystkie cztery są na ścieżce bez obejścia, a Cholesky nie ma cichego fallbacku na pseudoodwrotność.

**Bezpiecznik 1 — `MIN_EFFECTIVE_FOR_FIT = 0.5` (próg n_eff dla dopasowania).**
Jest parametrem `fit_dixon_coles(min_effective_matches=...)` i `_prepare`.
Wszystkie wywołania z wartością inną niż domyślna:
`tests/test_dixon_coles.py:945` i `:953`, oba w
`test_regression_pinv_blew_up_standard_errors`, który **celowo** odtwarza
starą, złą ścieżkę. W `src/` i `scripts/` **zero** wywołań z tym argumentem.
Docstring (dixon_coles.py:621-625) jawnie ostrzega, że 0.0 służy wyłącznie
testowi regresji.

Rzecz najważniejsza: `empirical_bayes_scales`, czyli funkcja, w której żyją
pozostałe trzy bezpieczniki, **nie ma tego parametru w sygnaturze** i woła
`_prepare(matches, reference_date, xi, _EB_WEAK_PRIOR)` bez niego
(dixon_coles.py:940). Czyli nawet podanie 0.0 do `fit_dixon_coles` nie
przeniosłoby się na estymację tau — próg n_eff w estymacji rozrzutu jest
nieparametryzowalny z zewnątrz.

**Bezpiecznik 2 — `MIN_EFFECTIVE_FOR_TAU = 5.0`.** Stała modułowa, bez
parametru. `well_measured = data.effective_matches >= MIN_EFFECTIVE_FOR_TAU`
(dixon_coles.py:955), a tau liczone **wyłącznie** po tej maskce (:974-979).
Dodatkowo `_MIN_TEAMS_FOR_TAU = 6` podnosi wyjątek, gdy dobrze zmierzonych
drużyn jest mniej (:966-971). Analiza wrażliwości dla progów 3.0 i 10.0
(:991-999) jest **tylko raportem** — wynik nie wraca do `scales`, co kod
jawnie komentuje.

**Bezpiecznik 3 — `MAX_STANDARD_ERROR = 1.0` dla dobrze zmierzonej drużyny.**
dixon_coles.py:956-965, stała modułowa, bez parametru, sprawdzana **przed**
estymacją tau (komentarz: bezpiecznik numeryczny PRZED statystycznym).
Kolejność jest istotna i poprawna — rozlana wariancja wypycha tau albo do
zera, albo do jedynki, więc łapanie przyczyny przed skutkiem jest jedynym
sposobem, żeby komunikat był diagnostyczny.

**Bezpiecznik 4 — `MIN_TAU_STRENGTH = 0.03`.** dixon_coles.py:980-989, stała
modułowa, `DegenerateSpreadError` z pełną diagnostyką w komunikacie (liczba
dobrze zmierzonych drużyn, n_matches, xi, var(s), cond).

**Cholesky — brak cichego fallbacku, potwierdzone grepem.** Szukałem
`pinv`, `lstsq` i `np.linalg.inv` w całym `src/`: **zero trafień w kodzie**.
Są tylko trzy wzmianki w docstringach dixon_coles.py:766-794, wyjaśniające,
dlaczego pinv jest zakazany, i jedno użycie w
`tests/test_dixon_coles.py:955`, odtwarzające starą ścieżkę w teście
regresji. Jedyny `except LinAlgError` w `src/` to dixon_coles.py:810-815 i
**podnosi** `NumericalInstabilityError`, nie schodzi na nic:

    except LinAlgError as exc:
        raise NumericalInstabilityError(
            'hesjan z priorem nie jest dodatnio okreslony - Cholesky zawiodl. '
            'NIE schodzimy na pseudoodwrotnosc: ...'
        ) from exc

**Jedyna ścieżka, na której te wyjątki są łapane**, to `build_xi_cache`
(dixon_coles_baseline.py:327-340), i kierunek jest konserwatywny:
`cache[season, xi] = -math.inf`, czyli kandydat jest **odrzucany**, nigdy
przemilczany. W ścieżce predykcji z wybranym xi nie ma `try` (sekcja D.1).
`select_xi` dodatkowo podnosi `NumericalInstabilityError`, gdy wszystkie
kandydaty wyszły -inf (:374-378) — z komentarzem, że to awaria, nie wybór.

**Zmierzone na realnym przebiegu:** `diag_313591a.json` pokazuje
`n_rejected_xi: 0` i `n_dropped_teams: 0` dla każdego sezonu, a
`condition_number` w zakresie 50-126 (zdrowy). Bezpieczniki nie musiały więc
zadziałać na danych Ekstraklasy po poprawce C, co jest spójne z tym, że
poprawka naprawiła przyczynę (martwe drużyny jako wolne parametry), a nie
zamaskowała skutek.

---

## Tabela znalezisk według wagi

| waga | plik:linia | reguła | co | kierunek wpływu |
|---|---|---|---|---|
| KRYTYCZNE (po podłączeniu) | pricing/fair.py:50, 144-154 | 17 | walidacja kompletności rynku działa tylko dla nazw 1x2/totals/spreads; ingest nazywa 1X2 jako h2h | p zawyżone proporcjonalnie do nadmiaru booksumu; zmierzone x1.15 i x2.0 |
| KRYTYCZNE (po podłączeniu) | pricing/ev.py:98-103 | 1, 20 | okno AKO bez górnej granicy czasowej, zakłady z przyszłości podnoszą udział AKO | tax 0.94 na 1.00, czyli +6 pp EV na stawce; zmierzone |
| POWAŻNE | pricing/ev.py:106-107 | 1 | próg 1000 zł liczy cały dziennik, udział AKO liczy okno: dwie definicje obrotu | nieznany znak, skala do 6 pp EV |
| POWAŻNE | pricing/kelly.py:100-124 | 21 | bramka G-K to dwa pola od wołającego, nie obliczenie z dziennika | c=0.5 bez spełnienia bramki, podwojona ekspozycja |
| POWAŻNE | clv.py:184, market_benchmark.py:61, metrics.py:59 | 11 | dwa niezgodne progi liczby klastrów (5 i 8); CLV używa słabszego i nie ma pola reliable | CI za wąskie w zakresie 5-7 klastrów, odblokowuje c=0.5 |
| POWAŻNE | pricing/shin.py:217-221 | 16 | brak zbieżności i allow_underround zwracają normalizację proporcjonalną we flagze, nie wyjątek | zawyżenie longshotów, 2.3 pp EV wg CONTEXT 5.4; dziś nikt tego nie zużywa |
| POWAŻNE | pricing/ev.py:69-88, live/bets.py:141-171 | brak | PlacedBet nie zna settled, a settle() dopisuje wiersz z tym samym stake | podwojony obrót, dwie sprzeczne definicje |
| POWAŻNE | pricing/ev.py:77 | brak | mode domyślnie real, paper wchodzi do obrotu przy pominięciu argumentu | fałszywe 1.00 |
| POWAŻNE | pricing/fair.py:166 | brak | ValueError z Shina (underround) nie jest łapany i przerywa wycenę całej migawki | brak przeglądu dnia, złamany kontrakt funkcji |
| POWAŻNE | backtest/clv.py:181-209 | 11, 26 | średnia CLV i beats_closing tylko na zakładach z migawką zamknięcia, bez progu na n_missing | selekcja skorelowana z ruchem kursu; pokrycie Pinnacle w lockboxie 112/375 |
| POWAŻNE | scripts/run_lockbox.py:59 | 10 | zamrożenie obejmuje tylko models/ i features/; raport etykietowany commitem, w którym jego skryptu nie ma | etykieta nieodtwarzalna, modele faktycznie zamrożone |
| POWAŻNE | scripts/run_diagnostics.py:155-157 | 15 (duch) | druga definicja lockboxa literałami, poza assert_no_lockbox | ryzyko publikacji sezonu odłożonego po zmianie listy |
| POWAŻNE | scripts/validate_instrument.py | brak | brak assert_no_lockbox, mimo zgodnego formatu etykiety sezonu | liczba decyzyjna valid bez bramki |
| POWAŻNE | backtest/elo_baseline.py, dixon_coles_baseline.py | brak | pooled_gaps i pooled_log_loss liczone na pełnej ramce z lockboxem, bez bramki | nie zużyte w raportach, dostępne jednym wywołaniem |
| POWAŻNE | reports/instrument_validation.json | 19a | kryterium na sd_ratio i r przechodzi, a nachylenie 0.78-0.84 z CI wyklucza 1.0 | instrument obciążony o 16-22%, any_valid true jest mylące |
| DROBNE | pricing/fair.py:57-71 | 17 | line nie wchodzi do walidacji, Over 2.5 z Under 3.5 przejdzie | booksum bez interpretacji |
| DROBNE | pricing/kelly.py:126-135 | brak | przy peak_bankroll = 0 wyłącznik obsunięcia nie działa i nie ostrzega | brak przejścia w paper |
| DROBNE | pricing/kelly.py:59-77 | 20 | kelly_fraction nie waliduje tax_factor, w odróżnieniu od ev() | brak |
| DROBNE | pricing/ev.py:61 | brak | 12 miesięcy zaimplementowane jako 360 dni | konserwatywnie |
| DROBNE | pricing/ev.py:84-88 | brak | qualifies_as_ako nie wymaga różnych meczów, double_ev wymaga | niespójność |
| DROBNE | schema.py:309 | 20 | tax_factor z domyślną wartością 0.88 zaszytą w modelu danych | konserwatywnie |
| DROBNE | backtest/clv.py:112 | 24 | CLV zawiera tax_factor_applied, więc nie jest CLV z reguły 24 | pod podatkiem 0.88 bramka G-K nieosiągalna |
| DROBNE | backtest/clv.py:58-124 | 2 | brak kontroli placed_at < kickoff w łańcuchu dziennik-CLV | zakład in-play dostałby CLV |
| DROBNE | backtest/clv.py:163-209 | brak | jedna średnia i jedno CI na wszystkie rynki i ligi | zaciera sygnał |
| DROBNE | pricing/shin.py:226 | brak | ShinResult.iterations zwraca zawsze max_iter | tylko diagnostyka |
| DROBNE | dixon_coles_baseline.py:363-372 | 10 | pierwszy sezon testowy stoi na jednym sezonie walidacyjnym | słabsza gwarancja dla 2015/16 |
| DO SPRAWDZENIA | pricing/fair.py:91-96 | 2 | fair_prices nie zna kickoff_utc, nie wymusza decision_time < kickoff | wycena z migawek in-play przy odtwarzaniu historycznym |
| DO SPRAWDZENIA | backtest/market_benchmark.py:85-97 | 19a | over_probability to macierz DC na rynku totali; dziś wyłącznie diagnostyka, funkcja publiczna bez bezpiecznika | gdyby wyceniała: pozorne +EV po obu stronach linii, oś otwartości ściśnięta 6x |
| DO SPRAWDZENIA | dixon_coles_baseline.py:432-454 | 8 | xi i tau dla 2026/27 wybrane z udziałem 2025/26, pierwszego sezonu lockboxa | walk-forward poprawny, ale sezony lockboxa nie są niezależne |
| DO SPRAWDZENIA | scripts/run_lockbox.py | brak | nic nie liczy, ile razy lockbox był oglądany | jedno spojrzenie jest deklaracją |

---

## Co sprawdziłem i nie znalazłem nic

Pełna lista, żeby nie trzeba było powtarzać pracy:
`groupby().transform()` bez shift, `rolling`/`expanding` bez `closed="left"`
i bez `shift(1)`, statystyki normalizacyjne na pełnym zbiorze,
`fit_transform`, `train_test_split`, `KFold`, naiwny `datetime` (ruff DTZ
czysto na src i scripts), odcięcie po dacie zamiast po gwizdku, `merge` po ID
bez warunku czasowego, Elo z aktualizacją przed zapisem cechy, przeciek przez
mecze o identycznym `kickoff_utc` (532 takich meczów, zweryfikowane jako
nieszkodliwe), kurs rynkowy jako cecha modelu, accuracy jako metryka,
obejście bezpieczników numerycznych DC, `pinv` jako cichy fallback,
zależność cache LL(V, xi) od sezonu późniejszego niż V, macierz DC
wyceniająca totale, handicapy albo kombinacje.

Narzędzia: `uv run pytest` 528 passed, `uv run ruff check src tests scripts`
czysto, `uv run ruff check --select DTZ src scripts` czysto.

---

## Ocena wiarygodności trzech raportów

### reports/lockbox_3433f2c.json — wiarygodny co do treści, niewiarygodny co do etykiety

Liczby: n=375, n_clusters=44, ll_dc=1.0627, ll_elo=1.0654, dc_minus_elo mean
-0.0027 z CI [-0.0103, +0.0055], significant false. Metodologia poprawna:
walk-forward bez przecieku (potwierdzone testami trucizny i czytaniem kodu),
klaster to tydzień ISO w obrębie sezonu, bootstrap klastrowy, 44 klastry
(powyżej obu progów), CI podane, zastrzeżenie o niedziewiczości lockboxa
zawarte w pliku.

Trzy zastrzeżenia, w kolejności istotności:

1. `commit_frozen: 3433f2c` jest nieprawdziwe jako opis odtwarzalności —
   `scripts/run_lockbox.py` nie istniał w tym commicie (dodany w 4b98818).
   Modele były zamrożone (bez zmian od 313591a), więc liczby odpowiadają
   modelowi z 313591a, ale plik sugeruje coś, czego nie da się zweryfikować.
2. `gaps.pinnacle` ma n=112 i tylko sezon 2025/26, przy n=375 ogółem. Luka DC
   do Pinnacle (+0.0114, CI [-0.0101, +0.0351]) stoi na 30% lockboxa i 14
   klastrach. Raport słusznie oznacza significant false.
3. `per_season` dla 2026/27 to n=69. Przy typowym sd log lossu per mecz rzędu
   0.8 półszerokość CI jest rzędu 0.19, czyli dziesięciokrotnie większa niż
   raportowana różnica DC minus Elo. Ta liczba nie niesie informacji.

Wniosek: teza główna, czyli że DC i Elo są na lockboxie nierozróżnialne i oba
leżą blisko dev, jest wiarygodna. Liczby cząstkowe wymagają ostrożności, a
etykieta commita powinna zostać poprawiona.

---

### reports/m2_313591a.json — wiarygodny, najmocniejszy z trzech

n=2943, 10 sezonów, waga dobierana walk-forward per sezon, bootstrap
klastrowy po sezonach (10 klastrów, powyżej progu 8), CI podane,
`assert_no_lockbox` wywołane przed liczeniem. Reguła 19 nienaruszona, rynek
wchodzi wyłącznie jako shrinkage target i jest jawnie oznaczony.

`pool_minus_market`: mean +0.00149, CI [-0.00028, +0.00396], significant
false, czyli model nie wnosi informacji ponad rynek. Werdykt jest ostrożny w
poprawną stronę: punktowo pula jest gorsza od rynku, a CI obejmuje zero, więc
raport nie twierdzi nic mocniejszego, niż ma prawo. Wagi per sezon (0.0 do
0.45, mediana okolo 0.17) są z tym spójne.

Jedyne zastrzeżenie: liczby w bloku `axes` (A_openness slope 3.06, B_edge
slope 1.21) są policzone na tym samym zbiorze dev, który był już wielokrotnie
oglądany, i są wejściem do decyzji o regule 19a. To nie przeciek, tylko
zwykłe zużycie zbioru, ale raport nie ma mechanizmu, który by to sygnalizował.

### reports/instrument_validation.json — liczby wiarygodne, werdykt mylący

n=2269, 6 sezonów Premier League, n_shin_failed zero, n_not_inverted zero,
klastrowanie po sezonach, CI podane. Mechanika czysta: Shin na kompletnych
rynkach 1X2 (trzy kursy) i O/U 2.5 (dwa kursy), oba po sprawdzeniu
`converged`. Shin dla n=2 zweryfikowałem osobno i działa poprawnie. Lockboxa
to nie dotyczy, bo inna liga i sezony do 2024/25.

Ale `any_valid: true` opiera się na kryterium (sd_ratio w [0.8, 1.25] oraz
r >= 0.7), które pomija najmocniejszą statystykę w tym samym pliku:
nachylenie regresji T_ou na T_1x2 wynosi 0.8364 z CI [0.8081, 0.8600] dla
rho=0 i 0.7766 z CI [0.7535, 0.7969] dla rho=-0.0702. Oba CI wykluczają 1.0.
Zgodnie z własnością wieży, na którą powołuje się market_benchmark.py:15-27,
nachylenie 1.0 jest testem tego, czy oba odczyty mierzą to samo. Nie mierzą:
suma goli wyprowadzona z 1X2 jest o 16-22% za szeroka.

Dodatkowo sd_ratio 1.211 leży 0.04 od progu odrzucenia 1.25, a różnica
poziomów mean_T_1x2 wobec mean_T_ou to 0.29 gola dla rho=0 i praktycznie zero
dla rho=-0.0702, co pokazuje, że rho jest dopasowywane do poziomu, a nie
walidowane niezależnie.

Wniosek: kryterium było spisane przed wynikiem, więc jest uczciwe, ale
zostało dobrane bez mocy. `any_valid: true` należy czytać jako "instrument
mierzy coś skorelowanego z sumą goli, z obciążeniem skali około 20%", nie
jako "instrument jest ważny". To wzmacnia, a nie osłabia, regułę 19a.

---

## Zdanie końcowe

Istniejące raporty (lockbox_3433f2c.json, m2_313591a.json,
instrument_validation.json) **można traktować poważnie** — nie znalazłem w
ścieżce, która je wytworzyła, ani jednego przecieku z przyszłości, a ich
werdykty są ostrożne w poprawną stronę. Natomiast **tor S w obecnym kształcie
nie jest gotowy, żeby wyprodukować wiarygodną liczbę**: dwie ścieżki (okno
AKO bez górnej granicy czasowej oraz brak walidacji kompletności rynku dla
nazwy h2h) podniosłyby wycenę o więcej, niż wynosi cała szukana przewaga, i
obie zapalą się w chwili pierwszego podłączenia tych modułów do danych.
