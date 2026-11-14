# Audyt backtestu — raport przyrostowy

**Data:** 2026-09-30
**Audytor:** subagent `backtest-auditor` (adwersaryjny)
**Repo:** <user>\Desktop\value-bet (branch `master`)

## Zakres

Pliki objęte audytem:
- `src/valuebet/ingest/football_data.py`
- `src/valuebet/backtest/metrics.py`
- `src/valuebet/backtest/elo_baseline.py`
- `src/valuebet/pricing/shin.py`

Pomocniczo (tylko odczyt): `src/valuebet/models/elo_ordinal.py`,
`src/valuebet/features/elo.py`, `src/valuebet/schema.py`, `tests/`.

Reguły odniesienia: CLAUDE.md, punkty 1-26.

## Klasyfikacja

KRYTYCZNE / POWAŻNE / DROBNE / DO SPRAWDZENIA.

## Lista kontrolna sekcji

- [x] A. football_data.py — daty, strefy, ingested_at/source, raw, team_mapping, mecze bez wyniku
- [x] B. elo_baseline.py — mechanika walk-forward (poza ustalonymi punktami)
- [x] C. metrics.py — n i CI, sparowany bootstrap, accuracy, kolejnosc metryk
- [x] D. elo_ordinal.py — progi ordered logit: train czy pelny zbior
- [x] E. shin.py — solver, granica z->0, brak normalizacji proporcjonalnej, n=2, booksum<=1
- [x] F. Sygnatury leakage w calym zakresie
- [x] PYTANIE 1 — mecze bez kursu zamkniecia: ile, jak usuwane, czy selekcja losowa
- [x] PYTANIE 2 — przelaczenie referencji Pinnacle -> BFEC
- [x] PYTANIE 3 — wiersze NaT po tz_localize
- [x] PYTANIE 4 — kompletnosc rynku dla Shina
- [x] PODSUMOWANIE — tabela znalezisk + ocena wiarygodnosci liczb

---
## Sekcja A — `src/valuebet/ingest/football_data.py`

**Status: brak znalezisk krytycznych i poważnych. Jedno DROBNE, jedno DO SPRAWDZENIA.**

### Co sprawdzono (i wynik)

**Parsowanie dat i stref (reguła 2) — CZYSTO.**
`_to_kickoff_utc` (linie 321-325) robi `pd.to_datetime(..., format="%d/%m/%Y %H:%M")`
z **jawnym formatem** (brak zgadywania `dayfirst`), potem
`tz_localize("Europe/London", ambiguous="NaT", nonexistent="NaT")` i
`tz_convert("UTC")`. Kolumna `kickoff_utc` w interim ma dtype
`datetime64[us, UTC]` — tz-aware. Naiwnych `datetime` w module nie ma
(`utcnow()` z `schema`, `astimezone(UTC)` w `write_raw` i `parse_matches`).

Zweryfikowałem empirycznie, że `Europe/London` to **poprawna** strefa źródła,
a nie zgadnięcie. Test falsyfikujący: gdyby źródło zapisywało czas w UTC albo
w stałym offsecie, modalne godziny polskie różniłyby się o godzinę między
okresem GMT a BST. Nie różnią się:

```
GMT  (+0000): 18:00 x455, 20:30 x257, 17:30 x181, 15:30 x175, 15:00 x124
BST  (+0100): 18:00 x764, 20:30 x478, 17:30 x346, 15:30 x253, 15:00 x177
```

Identyczny profil godzin po obu stronach zmiany czasu — strefa źródła jest
zgodna z brytyjskim DST. 99.95% meczów ląduje na "okrągłej" godzinie polskiej
(:00/:15/:30/:45).

**Godzina, nie data, jest granicą odcięcia (reguła 2) — CZYSTO.**
Cały pipeline operuje na `kickoff_utc` (timestamp), nigdy na `Date`.
`compute_elo` sortuje po `["kickoff_utc", "match_id"]`, więc mecze z tego
samego dnia nie widzą się nawzajem. Rozpiętość godzin w danych: 11:15-20:00
czasu UK, czyli w ramach jednego dnia realnie do 9h różnicy — to ma znaczenie
i jest obsłużone.

**Reguła 14 (`ingested_at` + `source`) — CZYSTO.**
`write_raw` (208-211) dokłada `ingested_at`, `source`, `source_url`,
`content_sha256`, `row_number`. `matches` (570-571) i `closing_odds` (423-424)
też. Zweryfikowane na pliku interim — kolumny obecne.

**Reguła 12 (niemodyfikowalność raw) — CZYSTO.**
`write_raw` (213-219): nazwa `POL-{stamp}-{uuid4[:8]}.parquet`, jawny
`FileExistsError` przy kolizji, brak jakiejkolwiek ścieżki zapisu do istniejącego
pliku w raw. `load_raw_latest` tylko czyta. Nadpisywane jest wyłącznie
`data/interim/` (`write_interim`), co reguła 12 dopuszcza.

**Reguła 15 (nazwy drużyn) — CZYSTO.**
`_resolve_teams` woła `TeamResolver.resolve` po słowniku aliasów; jedyne
"obejście" to `SOURCE_NAME_OVERRIDES` (139-144) — jawny słownik 4 skrótów
specyficznych dla źródła, rozwijany PRZED resolverem. To słownik, nie fuzzy.
Nierozpoznana nazwa w `strict=True` podnosi `KeyError` zamiast po cichu
wyrzucać mecz. Na realnych danych: `rows_unresolved_team=0`, `coverage=1.0`.

**Mecze bez wyniku — CZYSTO i nieaktualne w praktyce.**
`HG`/`AG` puste => `status=SCHEDULED`, mecz **zostaje** w `matches`
(nie jest cicho wyrzucany). Połowa wyniku (HG bez AG) podnosi `ValueError`
(513-517). `_validate_results` (328-344) krzyżowo sprawdza `Res` vs `HG-AG`
i wywala się przy rozjeździe. Na realnych danych: 0 wierszy bez wyniku
(wszystkie 4151 mają HG/AG), `n_matches_without_result=0` w sanity check.

### Znaleziska

**[DROBNE] football_data.py:492** (reguła 2, obsługa brzegowa)
Co: `frame["Time"].str.strip()` zadziała tylko dopóki kolumna `Time` jest
dtype `object`. Jeśli football-data wypuści plik, w którym CAŁA kolumna `Time`
jest pusta, `read_csv(dtype=str)` da kolumnę `float64` NaN i `.str` rzuci
`AttributeError` zamiast policzyć `rows_without_time`.
Wpływ: zero na bieżący wynik (0 pustych `Time` w danych). Ryzyko przyszłego
twardego błędu, nie przecieku.

**[DO SPRAWDZENIA] football_data.py:224-233, warstwa raw ma tylko 1 snapshot**
Co: `data/raw/football_data/` zawiera dokładnie jeden plik
(`POL-20260921T133212Z-27bb0df3.parquet`). Serwis **nadpisuje** POL.csv i
koryguje wiersze wstecz (co docstring sam przyznaje, linie 8-10).
Dlaczego to istotne dla audytu: kursy zamknięcia i wyniki w tym snapshocie to
wersja PO wszystkich korektach źródła. Nie jest to look-ahead w sensie reguły 1
(kurs zamknięcia i tak jest poprzedzający wynik), ale oznacza, że nie da się
odtworzyć, co widzieliśmy w danym dniu — architektura append-only jeszcze
niczego nie chroni, bo nie ma z czym porównać.
Jak rozstrzygnąć: drugi snapshot za kilka tygodni + diff po `match_id`.

## Sekcja E — `src/valuebet/pricing/shin.py`

**Status: matematycznie zgodny z CONTEXT.md §5.1-5.4. Zero znalezisk krytycznych.
Dwa DROBNE, jedno DO SPRAWDZENIA.**

### Zgodność z CONTEXT.md §5.1-5.4 — CZYSTO

* **§5.1 solver Brenta, nie iteracja punktu stałego** — `_solve_z` (190-226)
  używa `scipy.optimize.brentq` na `g(z) = sum(p_i(z)) - 1`, przedział
  `[0, 1-1e-12]`. Iteracji Jullien-Salanié w kodzie nie ma.
  Zweryfikowane: `shin_probabilities([1.90, 2.10])` (n=2) zwraca
  `z=0.00251, converged=True` — czyli rynek dwustronny działa, co było
  głównym powodem odrzucenia iteracji.
* **§5.2 granica z -> 0 to `pi/sqrt(P)`, NIE `pi/P`** — `_apply_shin` linia 246:
  `pi / np.sqrt(bsum)`. Poprawnie. To jest ten jeden znak, który po cichu
  degeneruje cały moduł, i jest na miejscu.
* **§5.3 wzory referencyjne** — `_apply_shin` (247-248) i `shin_forward`
  (282-285) zgodne co do znaku i nawiasu ze wzorami z CONTEXT.
* **§5.4 / reguła 16: brak normalizacji proporcjonalnej** — w ścieżce
  produkcyjnej (booksum > 1) nie występuje. Kontrola liczbowa na przykładzie
  z CONTEXT `[1.80, 3.60, 4.50]`:
  Shin `[0.5343, 0.2602, 0.2055]` vs proporcjonalna `[0.5263, 0.2632, 0.2105]`
  — zgadza się co do czwartego miejsca z tabelą w CONTEXT §5.4.

### Zachowanie brzegowe (sprawdzone uruchomieniowo)

| wejście | zachowanie |
|---|---|
| `[1.90, 2.10]` (n=2) | działa, `converged=True` |
| `[2.5, 3.0, 4.0]` (booksum 0.983) | `ValueError` — underround blokowany domyślnie |
| to samo z `allow_underround=True` | `converged=False`, **p = normalizacja proporcjonalna** |
| `[1.0, 3.0, 4.0]` | `ValueError` — kursy muszą być > 1.0 |
| `[0.5, 3.0, 4.0]` | `ValueError` |
| `[nan, 3, 4]` | `ValueError` — NaN/inf |
| `[2.0]` (1 wynik) | `ValueError` — min. 2 wyniki |
| `[1.80, 3.60]` (2 z 3 rynku 1X2) | `ValueError` (booksum 0.833 < 1) |

Bracketing jest faktycznie gwarantowany dla `P > 1`: `g(0) = sqrt(P) - 1 > 0`,
a `g(1^-) = sum(pi^2)/P <= max(pi) < 1`, więc `g(1^-) - 1 < 0`. Gałąź
"nie udało się zabracketować" jest osiągalna **wyłącznie** przy
`allow_underround=True` i `booksum < 1`.

### Znaleziska

**[DO SPRAWDZENIA] shin.py:174-179 + 217-221** (reguła 16)
Co: przy `allow_underround=True` i `booksum < 1` solver zwraca `z=0,
converged=False`, a `shin_probabilities` mimo to liczy `probs = pi/sqrt(P)`
i dzieli przez sumę (linia 179) — co jest **dokładnie** `(1/k)/sum(1/k)`,
czyli normalizacją proporcjonalną zakazaną regułą 16. Zweryfikowane
liczbowo: dla `[2.5, 3.0, 4.0]` wynik to `[0.4068, 0.3390, 0.2542]`,
`np.allclose` z proporcjonalną = True.
Dlaczego to nie jest dziś KRYTYCZNE: jedyny produkcyjny wołający
(`metrics.market_probabilities:201`) używa domyślnego
`allow_underround=False` i dodatkowo pomija wyniki z `converged=False`.
Ryzyko: to jest pułapka na przyszłość — kod zwraca `ShinResult` wyglądający
normalnie, z zakazanym rozkładem w środku, a jedyną obroną jest to, że
wołający sprawdzi `converged`. Kierunek błędu, gdyby ktoś to przeoczył:
zawyżenie prawdopodobieństwa longshotów => fałszywe +EV na wysokich kursach.
Jak sprawdzić: dowolny wołający, który zignoruje `converged`.

**[DROBNE] shin.py:226 i docstring 73-74**
Co: `_solve_z` zwraca `max_iter` jako liczbę iteracji, niezależnie od tego,
ile faktycznie zrobił Brent (`brentq` nie zwraca licznika bez
`full_output=True`). `ShinResult.iterations` jest udokumentowane jako
"liczba iteracji do zbieżności", a zawsze wynosi 200.
Wpływ: zero na wyniki, mylące przy diagnostyce.

**[DROBNE] shin.py:165-172**
Co: przy `abs(bsum - 1) < tol` zwracane są surowe `pi` bez renormalizacji,
więc `sum(p)` = `bsum`, a nie dokładnie 1 (odchyłka do 1e-12).
Wpływ: zero (`metrics._check_probs` toleruje 1e-6), ale niespójne z
resztą ścieżki, która renormalizuje.

### Marginesy na realnych danych (kontekst dla reguł 17/16)

Rozkład booksum w `closing_odds.parquet`:

| bukmacher | n | min | mediana | max | booksum < 1 |
|---|---|---|---|---|---|
| pinnacle | 3887 | 1.0102 | 1.0297 | 1.0730 | 0 |
| betfair_exchange | 656 | 1.0010 | 1.0097 | 1.0223 | 0 |
| bet365 | 343 | 1.0476 | 1.0907 | 1.1111 | 0 |
| market_avg | 4151 | 1.0584 | 1.0709 | 1.0999 | 0 |
| market_max | 4151 | 0.8666 | 1.0056 | 1.0645 | **1530** |

Wniosek: dwie referencje używane w backteście (`pinnacle`, `betfair_exchange`)
nigdy nie wpadają w underround, więc ścieżka proporcjonalna nie jest w tym
backteście wykonywana ani razu. `market_max` (nieużywany jako referencja) ma
underround w 37% wierszy — dodanie go do `DEFAULT_REFERENCES` wysadziłoby
przebieg nieprzechwyconym `ValueError` w `market_probabilities` (co jest
zachowaniem głośnym, czyli poprawnym).

## Sekcja B — `src/valuebet/backtest/elo_baseline.py` (mechanika walk-forward)

*(Zgodnie z zakresem pominięto dwa punkty uznane przez użytkownika za ustalone:
poprawność expanding window / `OrdinalElo.fit` na `seasons[:i]` oraz
arytmetykę 4151 − 832 = 3319.)*

**Status: mechanika czasowa czysta. Jedno POWAŻNE (szerokość CI), dwa DROBNE,
jedno DO SPRAWDZENIA (reguła 10).**

### Kolejność chronologiczna — CZYSTO

`frame.sort_values(["kickoff_utc", "match_id"], kind="mergesort")` (251-253),
a `compute_elo` robi identyczne sortowanie u siebie (`features/elo.py:159-161`).
Podziały `train`/`test` to maski boolowskie na już posortowanej ramce, więc
kolejność wewnątrz sezonu jest zachowana. Sort jest po **timestampie**, nie po
dacie — mecze z tego samego dnia (a rozpiętość godzin w danych to 11:15-20:00
UK, do 9h) nie widzą się nawzajem.

### Granice sezonów — CZYSTO, zweryfikowane liczbowo

`seasons = sorted(frame["season"].unique())` to sort **leksykograficzny**
etykiet `"YYYY/YY"`. Dla tego zbioru daje porządek chronologiczny (wszystkie
etykiety mają ten sam prefiks 4-cyfrowy). Sprawdziłem, że etykiety sezonów nie
nakładają się czasowo — dla każdej pary kolejnych sezonów
`min(kickoff | S+1) > max(kickoff | S)`:

```
2012/13  2012-08-17 .. 2013-06-02   2019/20  2019-07-19 .. 2020-07-19 (COVID)
2013/14  2013-07-19 .. 2014-06-01   2020/21  2020-08-21 .. 2021-05-16
...                                  2026/27  2026-07-24 .. 2026-09-15 (w toku)
```

Nawet wydłużony COVID-owy 2019/20 (koniec 19 lipca 2020) nie zachodzi na
2020/21 (start 21 sierpnia 2020). Czyli "train = sezony o mniejszej etykiecie"
jest równoważne "train = mecze wcześniejsze w czasie". Bez tej własności
podział po etykiecie byłby przeciekiem — tutaj nie jest.

### Stan Elo między foldami — CZYSTO

`compute_elo(matches, config)` (239) jest wołane **raz, na całej historii**,
przed podziałem. To wygląda podejrzanie i jest pierwszą rzeczą, którą
sprawdzałem — ale jest poprawne, bo Elo jest czysto rekurencyjne:
`features/elo.py:191` (`# --- ZAPIS CECHY ---`) emituje rating PRZED
aktualizacją, a aktualizacja używa wyłącznie wyniku bieżącego meczu. Żadna
wielkość nie jest agregatem po pełnym zbiorze:

* `config.initial = 1500` — stała, nie średnia zbioru;
* `season_carry` ściąga do `config.initial` (1500), **nie** do średniej
  ratingów w zbiorze — gdyby ściągało do średniej empirycznej, to byłby
  przeciek; nie ściąga;
* `compute_elo` jest wołane na `matches` PRZED odfiltrowaniem meczów bez
  wyniku (244-246), więc rating nie zależy od tego, które mecze wejdą do
  metryk;
* rating **przenosi się** przez granice foldów (nie ma resetu) — i tak być
  powinno, reset niszczyłby informację dostępną w momencie predykcji.

Kontrola pośrednia: maksymalny pojedynczy skok ratingu 57.5 pkt przy
`k=20, goal_diff_scaling=True` — wartość zgodna z `k * log1p(|gd|)` dla
różnicy 4-5 bramek. Brak skoków sugerujących nadpisanie stanu.

### Reguła 19 (kurs rynkowy jako cecha) — CZYSTO

`closing` wchodzi wyłącznie do `markets` (263-279) i jest łączone z
predykcjami dopiero w `_market_gap` (179-181), czyli PO wygenerowaniu
`probs_elo`. Jedyną cechą modelu jest `elo_diff`. `OrdinalElo.fit` dostaje
`train["elo_diff"]` i nic więcej. Kurs nie ma żadnej drogi do modelu.

### Znaleziska

**[POWAŻNE] elo_baseline.py:193 i 331-335** (reguła 11)
Co: przedział ufności luki liczony jest bootstrapem **iid po meczach**,
ignorującym strukturę sezonową, mimo że luka per sezon jest silnie
heterogeniczna: od −0.0045 (2017/18) i −0.0037 (2023/24) do +0.0378 (2022/23).
Mechanizm: bootstrap iid traktuje 3055 meczów jako 3055 niezależnych
obserwacji, podczas gdy efektywna liczba niezależnych jednostek jest bliższa
liczbie sezonów (11), bo dopasowanie `OrdinalElo` i warunki rynkowe są wspólne
w obrębie sezonu.
Dowód liczbowy (bootstrap blokowy po sezonach, 4000 replikacji, seed 0):

| referencja | n | luka | CI iid (w kodzie) | CI blokowe po sezonach |
|---|---|---|---|---|
| pinnacle | 3055 | +0.0145 | [+0.0082, +0.0209] szer. 0.0127 | **[+0.0062, +0.0229] szer. 0.0167** |
| betfair_exchange | 656 | +0.0121 | [−0.0006, +0.0245] szer. 0.0251 | [−0.0001, +0.0232] szer. 0.0233 |

Wpływ: CI dla Pinnacle jest **o ~31% za wąskie**. Kierunek: zawyża pewność,
z jaką twierdzimy, że luka jest istotna. Wniosek jakościowy ("rynek lepszy")
przeżywa — blokowe CI nadal wyklucza zero — ale etykieta "istotna" przy
pojedynczych sezonach (2016/17, 2022/23, 2024/25) jest wyliczana tym samym
nieadekwatnym estymatorem na n≈300.

**[DO SPRAWDZENIA] elo_baseline.py:452-455 + features/elo.py:52-56** (reguła 10)
Co: hiperparametry Elo (`k`, `home_advantage`, `season_carry`,
`goal_diff_scaling`) **nie są strojone na żadnym foldzie walidacyjnym** —
są stałymi domyślnymi `EloConfig`, a CLI wystawia `--k` i `--home-advantage`
bezpośrednio przy przebiegu, który drukuje wynik testowy. Docstring
`features/elo.py:52-56` wręcz zachęca ("dostrój to na swoich danych"), nie
mówiąc gdzie.
Ryzyko: nic w kodzie nie odróżnia strojenia na trainie od strojenia na teście;
to jest jedna flaga od złamania reguły 10.
Dowód, że **dziś** reguła 10 najprawdopodobniej nie została złamana:
przeszedłem siatkę 30 kombinacji (k ∈ {10,16,20,24,32,40} × ha ∈ {40,55,65,75,90})
plus `season_carry` ∈ {0.5,0.75,0.9,1.0} × `goal_diff_scaling` ∈ {T,F}:

* luka do Pinnacle rośnie **monotonicznie** z `k`: 0.0132 (k=10) → 0.0174 (k=40);
* domyślne `k=20` daje 0.0145, czyli **nie jest** optimum — optimum to k=10
  (0.0132). Gdyby ktoś stroił patrząc na test, wybrałby k=10.
* `home_advantage` jest praktycznie **nieidentyfikowalny**: zmiana 40 → 90
  rusza lukę o 0.0002, bo ordered logit dopasowuje `theta` i absorbuje stałe
  przesunięcie `elo_diff`. Parametr wygląda na strojony, a nie robi nic.
Zakres manipulacji, gdyby ktoś stroił na teście: luka do Pinnacle dałaby się
ściągnąć z 0.0145 do 0.0132 (−9%), do BFEC z 0.0121 do 0.0082 (−32%).
Jak rozstrzygnąć definitywnie: historia zmian wartości domyślnych — pliki są
nietrackowane w gicie (`?? src/valuebet/backtest/elo_baseline.py`), więc
audyt z kodu tego nie rozstrzygnie.

**[DROBNE] elo_baseline.py:193, 316, 334**
Co: `seed=0` przekazywany do każdego wywołania `paired_bootstrap_diff`, więc
wszystkie CI (per sezon i pooled) używają tej samej macierzy indeksów
losowych. Dla parowanego bootstrapu to nie jest błąd (deterministyczność jest
celem), ale CI z różnych sezonów są ze sobą skorelowane przez wspólne losowanie
— nie wolno ich traktować jako niezależnych testów.

**[DROBNE] features/elo.py:180-187**
Co: carry-over międzysezonowy jest stosowany na podstawie
`last_season.get(team) not in (None, season)`, czyli **raz** przy powrocie
drużyny, niezależnie od tego, ile sezonów jej nie było. Drużyna wracająca po
trzech sezonach dostaje jedno ściągnięcie 25% zamiast trzech.
Wpływ: nieznaczny i **obojętny kierunkowo** dla luki do rynku (dotyczy
beniaminków, których rating i tak jest stary). Nie jest to look-ahead.

## Sekcja C — src/valuebet/backtest/metrics.py

**Status: bootstrap JEST sparowany (poprawnie). Reguła 25 czysta. Jedno
POWAŻNE (to samo zdarzenie co w sekcji B — struktura CI), trzy DROBNE.**

### Czy bootstrap jest sparowany — TAK, potwierdzone

`paired_bootstrap_diff` (metrics.py:99-126):

    diff = x - z                                # linia 114: parowanie PRZED losowaniem
    idx  = rng.integers(0, len(diff), size=(n_boot, len(diff)))
    means = diff[idx].mean(axis=1)              # resampling wektora różnic

Losowanie idzie po **wektorze różnic per mecz**, nie osobno po `a` i po `b`.
To jest poprawna konstrukcja dla sparowanych log lossów. Linie 110-111
wymuszają `x.shape == z.shape` i `ndim == 1`, więc nie da się przypadkiem
podać różnych zbiorów meczów. Warunek "te same mecze" jest egzekwowany
wcześniej, przez inner merge po `match_id` w `elo_baseline._market_gap`.

Waga tej decyzji jest duża: odchylenie standardowe samego log lossu per mecz
to ok. 0.6, a odchylenie **różnicy** Elo minus rynek jest o rząd mniejsze.
Niesparowany bootstrap dałby CI kilkukrotnie szersze i wniosek "NIEistotna"
dla obu luk. Czyli parowanie decyduje o treści raportu — i jest zrobione dobrze.

### Reguła 25 (accuracy) — CZYSTO

Grep po src/ i tests/ na accuracy oraz argmax daje jedno trafienie:
`tests/test_elo_baseline.py:221: assert "accuracy" not in text.lower()`.
Accuracy nie tylko nie istnieje, ale jest test pilnujący, żeby nie wróciła.

### Reguła 24 (kolejność metryk) — CZYSTO, z jawnym i uzasadnionym ubytkiem

`format_report` drukuje: sanity Elo, potem log loss (walk-forward, potem
pooled), potem reliability diagram. CLV **nie jest liczone** i jest to jawnie
uzasadnione (`elo_baseline.py:17-22`): football-data nie ma kursów sprzed
zamknięcia, więc nie ma ceny wejścia. To poprawna decyzja, nie ukryty brak —
reguła 7 zabrania użycia PSC* jako ceny wejścia, a bez ceny wejścia CLV nie
istnieje.

Symulowanego yieldu w repozytorium **nie ma w ogóle** — grep nie znajduje
yield, stake, kelly, bankroll ani tax_factor w kodzie produkcyjnym. To kluczowe
dla oceny końcowej: nie ma yieldu, który mógłby być zawyżony. Cały "backtest"
to diagnostyka log lossu.

### Baseline stałej — z TRAINU, potwierdzone

`constant_probabilities` (metrics.py:71-81) liczy
`np.bincount(y_train)/len(y_train)` i powiela na n meczów testu. Wołane
z `elo_baseline.py:295` z argumentem `train["outcome"]`, nie `test`.
Docstring wprost nazywa alternatywę przeciekiem. Czysto.

### Znaleziska

**[POWAŻNE] metrics.py:99-126** (reguła 11) — to samo zdarzenie co w sekcji B
Co: bootstrap jest sparowany, ale **iid po meczach**. Nie ma wariantu
blokowego po sezonach, mimo że jedynym konsumentem jest walk-forward, w którym
obserwacje w obrębie sezonu dzielą wspólne dopasowanie OrdinalElo i wspólne
warunki rynkowe.
Wpływ liczbowy: CI dla luki Pinnacle jest o ~31% za wąskie (iid szerokość
0.0127 vs blokowe 0.0167). Kierunek: **zawyża pewność** raportowanych wniosków,
nie samą lukę.

**[DROBNE] metrics.py:200-203** (reguła 17 / odporność)
Co: `market_probabilities` łapie tylko `converged=False`. ValueError
z `shin_probabilities` (underround, kurs <= 1.0, NaN) **nie jest łapany** i
przerywa cały przebieg.
Wpływ: zero na bieżący wynik — dla pinnacle i betfair_exchange minimalny
booksum to 1.0102 i 1.0010, żaden wiersz nie wpada w underround. Ale dodanie
market_max do referencji (1530 z 4151 wierszy ma booksum < 1) wysadzi przebieg.

**[DROBNE] metrics.py:219 + elo_baseline.py:273-278**
Co: licznik odrzuconych meczów jedzie przez `DataFrame.attrs`, które pandas
gubi przy większości operacji (merge, concat, groupby). Tu działa, bo odczyt
jest natychmiast po utworzeniu ramki, ale to kruchy kanał na liczbę, która
z definicji ma być widoczna. Na realnych danych: not_converged = 0 dla obu
referencji.

**[DROBNE] elo_baseline.py:366-373** (wielokrotne testowanie)
Co: raport drukuje etykietę "istotna/NIEistotna" dla 13 luk sezonowych i 2
pooled, każdą przy 95% i bez korekty na wielokrotne porównania. Pod hipotezą
zerową spodziewalibyśmy się ~0.65 fałszywego trafienia na 13 testów; raport
pokazuje 3 (2016/17, 2022/23, 2024/25), więc sygnał jest realny — ale etykieta
przy pojedynczym sezonie (n ok. 300) nie jest niezależnym wynikiem.

## Sekcja D — src/valuebet/models/elo_ordinal.py (zakres: dopasowanie progów)

**Status: CZYSTO. Brak znalezisk.**

Pytanie audytowe: czy progi ordered logit są dopasowywane na trainie, czy na
pełnym zbiorze. Odpowiedź: **na trainie**, bez ukrytych statystyk z całości.

* `OrdinalElo.fit` jest wołane wyłącznie w `elo_baseline.py:291-293`, z
  `train["elo_diff"]` i `train["outcome"]`, gdzie
  `train = frame[frame.season.isin(seasons[:i])]`. Zbiór testowy nie ma żadnej
  drogi do `fit`.
* Skalowanie wejścia to `diff / 400.0` (elo_ordinal.py:90) — **stała zaszyta
  w kodzie**, a nie `diff.std()` czy `diff.mean()` policzone na pełnym zbiorze.
  To jest dokładnie to miejsce, w którym normalizacja dopasowana na całości
  byłaby złamaniem reguły 3. Nie jest.
* `predict_proba` (115-118) używa tej samej stałej 400.0 i parametrów
  z instancji — brak refitowania na teście.
* Punkt startowy optymalizacji `[1.0, -0.5, 0.0]` jest stały i niezależny od
  danych; `minimize(..., "L-BFGS-B")` deterministyczny, brak zbieżności
  podnosi wyjątek zamiast po cichu zwracać śmieci.
* `_unpack` wymusza `theta_high = theta_low + exp(gap)` — uporządkowanie progów
  bez ograniczeń w solverze. Nie dotyczy leakage, ale eliminuje degenerację.
* `outcome_index` (44-50) liczy wynik z goli tego samego meczu — to **etykieta**,
  nie cecha, i nie wchodzi do `predict_proba`. Jedynym wejściem predykcji jest
  `elo_diff`.

## Sekcja F — sygnatury leakage w całym zakresie

**Status: brak znalezisk. Poniżej co dokładnie sprawdzono.**

| wzorzec | trafienia w zakresie | ocena |
|---|---|---|
| train_test_split, KFold, StratifiedKFold | 0 | czysto — podział wyłącznie po sezonach |
| fit_transform, StandardScaler, SimpleImputer | 0 | czysto — brak skalowania/imputacji w ogóle |
| fillna | 0 | czysto |
| groupby().transform() | 2 w features/base.py:206,222 (poza zakresem, sprawdzone) | czysto — `s.shift(1).rolling(...)`, shift PRZED rolling |
| rolling( / expanding( | jw. | czysto — jawny shift(1), zgodnie z regułą 4 |
| .mean() / .std() | 8 trafień, wszystkie na **metrykach po predykcji** oraz w reliability_table | czysto — żadna nie jest statystyką normalizacyjną cechy |
| datetime.now / utcnow | 2 w football_data.py:205,470, oba .astimezone(UTC) na ingested_at | czysto — znacznik ingestu, nie granica cechy |
| shift( | tylko features/base.py | czysto |
| .merge( | elo_baseline.py:178 (predykcje x rynek, PO predykcji) i :240 (mecze x cechy Elo, validate="one_to_one") | czysto — merge po match_id bez warunku czasowego jest tu bezpieczny, bo obie ramki są per-mecz i obie policzone point-in-time |
| accuracy / argmax | 0 w kodzie, 1 asercja zakazująca w teście | czysto (reguła 25) |
| kurs jako cecha (reguła 19) | 0 | czysto — jedyną cechą modelu jest elo_diff |

Osobno sprawdzone ręcznie, bo grep tego nie złapie:

* **Kolejność zapis-cechy / aktualizacja-ratingu** (features/elo.py:191-225):
  `out_home.append(home_rating)` poprzedza odczyt `row.home_goals`. Wynik meczu
  nie ma drogi do cechy tego samego meczu.
* **Carry-over międzysezonowy** stosowany PRZED odczytem cechy (178-189), więc
  pierwszy mecz sezonu ma już ściągnięty rating.
* **Mecze bez wyniku** nie aktualizują ratingów (continue, 198-200), więc
  nierozegrany mecz nie wnosi zera do historii.
* **Sortowanie przed operacjami sekwencyjnymi**: compute_elo sortuje po
  ["kickoff_utc", "match_id"] z kind="mergesort" niezależnie od kolejności
  wejścia. Niesortowany Elo byłby cichym przeciekiem — nie jest.

## PYTANIE 1 — Mecze bez kursu zamknięcia

### Gdzie dokładnie są usuwane

Są **dwa** miejsca, oba filtrem, żadne nie jest `dropna()`:

1. **`ingest/football_data.py:391-393`** (`_build_closing_odds`):

       odds = frame[cols].apply(pd.to_numeric, errors="coerce")
       complete = odds.notna().all(axis=1) & (odds > 1.0).all(axis=1)
       report.closing_incomplete[bookmaker] = int((~complete).sum())

   Mecz bez kompletnej trójki H/D/A nie trafia do `closing_odds.parquet` dla
   tego bukmachera. Jest **policzony** (`closing_incomplete`), a dla Pinnacle
   dodatkowo **per sezon** (`pinnacle_missing_by_season`) i logowany jako
   `warning`. To jest robota zrobiona dobrze.
   **Ważne: sam mecz NIE znika.** `matches.parquet` ma wszystkie 4151 wierszy
   niezależnie od kursów — brak kursu nie usuwa meczu z historii Elo.

2. **`backtest/elo_baseline.py:178-181`** (`_market_gap`):

       joined = predictions.merge(market, on="match_id", how="inner", ...)

   **Inner join** po `match_id`. Tu mecz bez kursu danego bukmachera wypada
   z porównania po cichu — jedyną informacją dla czytelnika jest `gap.n`
   w raporcie, którą trzeba samemu odjąć od pooled `n=3319`.

### Ile ich jest — liczbowo, na `data/raw/football_data/POL-20260921T133212Z-*.parquet`

Cały zbiór, 4151 meczów:

| bukmacher | kompletne | brak | 
|---|---|---|
| pinnacle (PSC*) | 3887 | **264** |
| betfair_exchange (BFEC*) | 656 | **3495** |
| bet365 (B365C*) | 343 | 3808 |
| market_max (MaxC*) | 4151 | 0 |
| market_avg (AvgC*) | 4151 | 0 |

Per sezon (brakujące):

| sezon | n | brak PSC | brak BFEC |
|---|---|---|---|
| 2012/13 | 240 | 0 | 240 |
| 2013/14 | 296 | 0 | 296 |
| 2014/15 | 296 | 0 | 296 |
| 2015/16 | 296 | **1** | 296 |
| 2016/17 | 296 | 0 | 296 |
| 2017/18 | 296 | 0 | 296 |
| 2018/19 | 296 | 0 | 296 |
| 2019/20 | 296 | 0 | 296 |
| 2020/21 | 240 | 0 | 240 |
| 2021/22 | 306 | 0 | 306 |
| 2022/23 | 306 | 0 | 306 |
| 2023/24 | 306 | 0 | 306 |
| 2024/25 | 306 | 0 | **0** |
| 2025/26 | 306 | **194** | **25** |
| 2026/27 | 69 | **69** | 0 |
| **razem** | **4151** | **264** | **3495** |

W samym zbiorze OOS (3319 meczów, sezony 2015/16-2026/27): Pinnacle brakuje
dla **264**, więc porównanie idzie na **3055**; BFEC brakuje dla **2663**,
porównanie idzie na **656**. Obie liczby zgadzają się z tym, co drukuje raport.

### Czy selekcja jest losowa — dwa testy

**Test 1 — rozkład wyników 1/X/2 w meczach usuniętych vs pozostałych
(chi-kwadrat):**

| porównanie | usunięte (1/X/2) | pozostałe (1/X/2) | chi2 | p |
|---|---|---|---|---|
| pinnacle, cały zbiór | 0.4242 / 0.2765 / 0.2992 | 0.4407 / 0.2704 / 0.2889 | 0.278 | **0.870** |
| pinnacle, tylko sezony z obecnym źródłem | 0.4154 / 0.2872 / 0.2974 | 0.4407 / 0.2704 / 0.2889 | 0.510 | **0.775** |
| bfec, cały zbiór | 0.4381 / 0.2718 / 0.2901 | 0.4482 / 0.2652 / 0.2866 | 0.241 | **0.887** |
| bfec, tylko sezony z obecnym źródłem | 0.4800 / 0.2000 / 0.3200 | 0.4482 / 0.2652 / 0.2866 | 0.538 | **0.764** |

Brak jakiejkolwiek różnicy rozkładu wyników. Hipoteza "kursu brakuje tam, gdzie
coś się działo" **nie znajduje potwierdzenia** po stronie wyniku meczu.

**Test 2 (mocniejszy) — czy usunięty podzbiór jest dla Elo trudniejszy czy
łatwiejszy?** Wykorzystałem to, że `market_avg` (AvgC*) jest kompletny dla
**wszystkich 4151** meczów, więc daje referencję rynkową także dla wierszy
usuniętych. Porównanie luki Elo − market_avg:

| bukmacher | zachowane | usunięte | test |
|---|---|---|---|
| pinnacle | +0.0149 (n=3055) | **+0.0086** (n=264) | t=0.60, **p=0.546** |
| betfair_exchange | +0.0110 (n=656) | **+0.0152** (n=2663) | t=−0.61, **p=0.543** |

Profil meczów usuniętych vs zachowanych (Pinnacle): p faworyta 0.471 vs 0.476,
LL rynku 1.067 vs 1.038, LL Elo 1.076 vs 1.052 — usunięte mecze są
**trudniejsze dla obu stron jednocześnie**, więc luka się nie zmienia.

**Kontrfaktyk liczbowy.** Luka Elo − market_avg (źródło dostępne dla
wszystkich 3319 meczów OOS):

| podzbiór | n | luka | 95% CI |
|---|---|---|---|
| **cały OOS** | 3319 | **+0.0144** | [+0.0085, +0.0202] |
| podzbiór Pinnacle | 3055 | +0.0149 | [+0.0089, +0.0210] |
| podzbiór BFEC | 656 | +0.0110 | [−0.0012, +0.0230] |

Czyli gdyby nie było żadnej selekcji, luka wyniosłaby +0.0144 zamiast +0.0149.
Efekt selekcji na raportowaną liczbę: **+0.0005 log lossu, czyli 3%**, i
w kierunku **zawyżania** luki Elo do rynku (tzn. na korzyść rynku, na
niekorzyść Elo) — dokładnie przeciwnie do kierunku, który byłby groźny.

### ODPOWIEDŹ

**Selekcja NIE jest losowa, ale nie jest też skorelowana z wynikiem meczu ani
z trudnością predykcji.** Jest w 100% wyjaśniona **dostępnością źródła w
czasie**: Pinnacle znika od 2025/26 (194+69 meczów, football-data przestało
publikować PSC dla Ekstraklasy), a BFEC istnieje dopiero od 2024/25. Jest to
selekcja **strukturalna i kalendarzowa**, nie wynikowa. Hipoteza "kursu brakuje
tam, gdzie coś się działo" jest **odrzucona** dwoma niezależnymi testami
(chi-kwadrat p=0.77-0.89; test różnicy luki p=0.54-0.55). Wpływ na raportowaną
liczbę +0.0145 to około +0.0005 (3%), w kierunku zawyżania luki, czyli
konserwatywnym. **Wynik z tego powodu nie jest spalony.**

Jedyne realne zastrzeżenie: odrzucenie w `_market_gap` jest **ciche** — raport
podaje `n` dla każdej luki, ale nigdzie nie mówi "z 3319 meczów OOS 264 nie ma
Pinnacle". Klasyfikacja: **DROBNE** (przejrzystość raportu, nie poprawność).

## PYTANIE 2 — Przełączenie referencji Pinnacle -> BFEC

ROADMAP raportuje: Elo − Pinnacle = **+0,0145** (n=3055) i
Elo − BFEC = **+0,012** (n=656). Pytanie: czy różnica 0,0024 jest realna, czy
to artefakt zmiany referencji.

### Sezony z OBOMA źródłami jednocześnie

`match_id` obecne równocześnie w `pinnacle` i `betfair_exchange`:
**418 meczów** — 2024/25 (306) i 2025/26 (112). Wszystkie w OOS.

### Porównanie obu źródeł na tym samym, wspólnym podzbiorze (n=418)

Prawdopodobieństwa po Shinie:

| | p_home | p_draw | p_away |
|---|---|---|---|
| pinnacle | 0.4389 | 0.2639 | 0.2972 |
| betfair_exchange | 0.4378 | 0.2657 | 0.2965 |
| **różnica (pin − bfec)** | **+0.0011** | **−0.0019** | **+0.0008** |
| MAE per mecz | 0.0086 | 0.0055 | 0.0077 |
| korelacja | **0.9944** | **0.9750** | **0.9945** |

Marża i parametr Shina (tu źródła faktycznie się różnią, zgodnie z
oczekiwaniem "exchange ma inną strukturę marży"):

| | booksum | z (Shin) |
|---|---|---|
| pinnacle | 1.0415 | 0.0209 |
| betfair_exchange | 1.0096 | 0.0048 |

Log loss na tych samych 418 meczach:

| | log loss |
|---|---|
| pinnacle | **1.0238** |
| betfair_exchange | **1.0245** |
| Elo | 1.0404 |

| wielkość | wartość | 95% CI (parowany bootstrap) |
|---|---|---|
| LL pinnacle − LL bfec | **−0.0006** | [−0.0039, +0.0028] |
| luka Elo − pinnacle (n=418) | **+0.0166** | [+0.0016, +0.0314] |
| luka Elo − bfec (n=418) | **+0.0159** | [+0.0008, +0.0310] |
| **różnica luk, sparowana** | **+0.0006** | **[−0.0028, +0.0039]** |

### Rozkład różnicy 0,0024 na składowe

Druga kontrola: luka do `market_avg` (jedyne źródło kompletne dla wszystkich
3319 meczów OOS), liczona na tych samych podzbiorach, na których liczone są
dwie raportowane luki:

| podzbiór | n | luka Elo − market_avg |
|---|---|---|
| podzbiór Pinnacle (2015/16-2025/26 cz.) | 3055 | **+0.0149** |
| podzbiór BFEC (2024/25-2026/27) | 656 | **+0.0110** |
| różnica wywołana **samym podzbiorem** | | **0.0039** |

Czyli sama zmiana podzbioru meczów — przy **niezmienionym** źródle
referencyjnym — daje różnicę 0,0039, podczas gdy zmiana źródła przy
niezmienionym podzbiorze daje 0,0006. Raportowana różnica to 0,0024, czyli
mieści się w całości w efekcie podzbioru.

### ODPOWIEDŹ

**Różnica 0,0145 vs 0,012 jest artefaktem zmiany podzbioru meczów, nie różnicą
między źródłami.** Liczba rozstrzygająca: na 418 meczach, gdzie oba źródła
istnieją, różnica luk wynosi **+0,0006 przy CI [−0,0028, +0,0039]** — zero
leży w środku przedziału, a sama różnica jest **cztery razy mniejsza** niż
raportowane 0,0024. Pinnacle i Betfair Exchange po Shinie dają praktycznie ten
sam rozkład (korelacja 0,975-0,994, MAE ≤ 0,0086, różnica log lossu −0,0006
[−0,0039, +0,0028]) mimo trzykrotnie różnej marży (booksum 1,0415 vs 1,0096)
i czterokrotnie różnego `z` (0,0209 vs 0,0048). Shin poprawnie zdejmuje różnicę
marży.

Konsekwencja praktyczna: ostrzeżenie w `elo_baseline.py:32-35` i w ROADMAP
("nigdy nie sklejamy w jedną liczbę, bo exchange ma inną strukturę marży") jest
**metodologicznie słuszne jako zasada**, ale na tych danych obie referencje są
wymienne — a to, co naprawdę różni obie raportowane liczby, to **różne okresy
i różne n**, i tego ROADMAP nie mówi. Raportowanie dwóch liczb obok siebie bez
adnotacji "to są rozłączne okresy" sugeruje porównywalność, której nie ma.
Klasyfikacja: **POWAŻNE (interpretacja raportu, nie kod)** — liczby są policzone
poprawnie, ale zestawione w sposób, który zaprasza do błędnego wniosku
"exchange jest łatwiejszy do pobicia".

## PYTANIE 3 — Wiersze NaT po tz_localize

### Wszystkie konwersje stref w zakresie

W całym audytowanym zakresie jest **jedno** miejsce konwersji stref:
`ingest/football_data.py:321-325`

    def _to_kickoff_utc(date, time):
        naive = pd.to_datetime(date + " " + time, format="%d/%m/%Y %H:%M")
        localized = naive.dt.tz_localize("Europe/London", ambiguous="NaT", nonexistent="NaT")
        return localized.dt.tz_convert("UTC")

Parametry: `ambiguous="NaT"`, `nonexistent="NaT"` — czyli godzina dwuznaczna
(jesienne cofnięcie zegara) i nieistniejąca (wiosenny skok) dają `NaT` zamiast
cichego przesunięcia. Poza tym w module są tylko `utcnow().astimezone(UTC)`
(linie 205, 470) na `ingested_at` — bez strefy źródłowej do zgadnięcia.
`pd.Timestamp(ingested_at)` zachowuje tz. `schema.Match` waliduje tz-aware.

### Ile wierszy kończy jako NaT — liczba na realnych danych

**Zero.** Na pełnym pliku (4151 wierszy):

| miara | wartość |
|---|---|
| `rows_in` | 4151 |
| `rows_without_time` (pusty `Time`) | **0** |
| `rows_ambiguous_dst` (NaT po tz_localize) | **0** |
| `rows_unknown_competition` | 0 |
| `rows_unresolved_team` | 0 |
| `rows_out` | **4151** |

Zero to nie przypadek, tylko konsekwencja danych: wszystkie godziny rozpoczęcia
mieszczą się w przedziale **11:15-20:00 czasu UK**, a brytyjskie okno zmiany
czasu to 01:00-02:00. Żaden mecz Ekstraklasy nie może w nie wpaść.

### Czy są POLICZONE I ZARAPORTOWANE — TAK

* `rows_without_time` — liczone w `parse_matches:493`, drukowane w
  `ParseReport.log_summary` (271-281).
* `rows_ambiguous_dst` — liczone w `:498` i dodatkowo logowane jako
  **`log.warning` z pełną listą odrzuconych meczów** (`Date, Time, Home, Away`),
  linie 499-507. To nie jest ciche `dropna()`.
* `ParseReport.rows_dropped` = `rows_in - rows_out` domyka bilans, więc żadne
  odrzucenie nie może się schować.
* Docstring modułu (52-59) jawnie dokumentuje decyzję "odrzucamy i liczymy"
  dla braku `Time` i uzasadnia, dlaczego wstawienie sztucznej godziny byłoby
  gorsze.

### Reguła 2: czy granicą odcięcia jest godzina, czy data

**Godzina.** Nigdzie w pipeline nie ma operacji na `Date` bez `Time`:
`compute_elo` sortuje po `["kickoff_utc", "match_id"]` (timestamp z minutą),
`elo_baseline` tak samo. Przy rozpiętości godzin 11:15-20:00 (do 9h w obrębie
jednego dnia) to ma realne znaczenie i jest zrobione poprawnie.

**Weryfikacja, że sama strefa źródłowa jest poprawna** (bo `ambiguous="NaT"`
nic nie da, jeśli strefa jest zgadnięta źle). Test falsyfikujący: gdyby źródło
podawało czas w UTC albo w stałym offsecie, modalne godziny polskie różniłyby
się o godzinę między okresem GMT a BST. Nie różnią się:

| okres | modalne godziny po konwersji na czas polski |
|---|---|
| GMT (+0000), zima | 18:00 x455, 20:30 x257, 17:30 x181, 15:30 x175 |
| BST (+0100), lato | 18:00 x764, 20:30 x478, 17:30 x346, 15:30 x253 |

Identyczny profil po obu stronach zmiany czasu. 99,95% meczów ląduje na
"okrągłej" minucie polskiej. `Europe/London` jest poprawną strefą źródła.

### Co się dzieje z meczami bez godziny

`parse_matches:492-494`: `has_time = Time.notna() & (Time.str.strip() != "")`,
wiersze bez godziny są **odrzucane i liczone** (`rows_without_time`). Na
bieżących danych: 0 takich wierszy, więc decyzja nie ma dziś żadnego wpływu na
próbę. Gdyby kiedyś miała, liczba jest w raporcie.

### ODPOWIEDŹ

**Zero wierszy kończy jako NaT (0 z 4151), zero wierszy nie ma godziny, i obie
liczby są policzone oraz zaraportowane — `rows_ambiguous_dst` dodatkowo
z `log.warning` zawierającym listę odrzuconych meczów. Nic nie jest filtrowane
po cichu.** Granicą odcięcia jest godzina rozpoczęcia (timestamp), nie data,
a strefa źródłowa `Europe/London` została zweryfikowana empirycznie, a nie
przyjęta na wiarę. Reguła 2 jest spełniona. **Brak znalezisk.**

Jedyne zastrzeżenie techniczne (już zgłoszone jako DROBNE w sekcji A):
`Time.str.strip()` w linii 492 rzuci `AttributeError`, a nie policzy zer,
gdyby kiedyś cała kolumna `Time` przyszła pusta i pandas nadał jej dtype
`float64`.

## PYTANIE 4 — Kompletność rynku dla Shina (reguła 17)

### Każde wywołanie `shin_probabilities` w repo

`grep -rn "shin_probabilities" --include=*.py .`:

| miejsce | kontekst |
|---|---|
| `src/valuebet/backtest/metrics.py:27` | import |
| **`src/valuebet/backtest/metrics.py:201`** | **jedyne wywołanie w kodzie produkcyjnym** |
| `src/valuebet/pricing/shin.py:121` | definicja |
| `src/valuebet/pricing/shin.py:257` | wzmianka w docstringu `shin_forward` |
| `tests/test_shin.py` — 11 wywołań | testy |

Czyli w całym kodzie produkcyjnym jest **dokładnie jedno** wywołanie.

### Czy przed wywołaniem jest walidacja kompletności — TAK, ale nie tam

Walidacja **nie leży** bezpośrednio przed wywołaniem w `metrics.py:201`.
`market_probabilities` sprawdza tylko obecność kolumn (187-190) i brak
duplikatów `match_id` (191-194), a potem woła Shina na każdej trójce.

Realna bramka kompletności stoi **wyżej, przy budowie danych**:
`ingest/football_data.py:391-393`

    odds = frame[cols].apply(pd.to_numeric, errors="coerce")
    complete = odds.notna().all(axis=1) & (odds > 1.0).all(axis=1)

Warunek `.all(axis=1)` na **wszystkich trzech** kolumnach H/D/A plus wymóg
`> 1.0`. Wiersz niekompletny nie trafia do `closing_odds.parquet` w ogóle, więc
Shin nigdy go nie zobaczy. Docstring funkcji powołuje się wprost na regułę 17.

### Czy sam `shin_probabilities` waliduje wejście — CZĘŚCIOWO, kompletności NIE

Waliduje (przez `implied_probabilities`, linie 95-108, zweryfikowane
uruchomieniowo):

| warunek | zachowanie |
|---|---|
| `ndim != 1` | `ValueError` |
| `size < 2` | `ValueError` ("potrzeba co najmniej 2 wyników") |
| NaN / inf | `ValueError` |
| kurs <= 1.0 | `ValueError` |
| booksum < 1 (bez `allow_underround`) | `ValueError` |

**Nie waliduje kompletności rynku i nie może** — funkcja nie wie, ilu wyników
oczekiwać (dla n=2 rynek dwustronny jest legalny). **Ufa wołającemu.**
Docstring mówi o tym wprost (133-137), ale to kontrakt, nie egzekucja.

Praktycznym, częściowym zabezpieczeniem jest gard underround: obcięcie rynku
1X2 zwykle zbija booksum poniżej 1 i podnosi wyjątek. **Ale nie zawsze.** Test
falsyfikujący:

| pełny rynek | booksum | po usunięciu wyniku "2" | efekt |
|---|---|---|---|
| [1.05, 15.0, 30.0] | 1.0524 | booksum 1.0190 | **PRZESZŁO**: p=[0.9429, 0.0571], z=0.0203 |
| [1.08, 11.0, 26.0] | 1.0553 | booksum 1.0168 | **PRZESZŁO**: p=[0.9175, 0.0825], z=0.0175 |
| [1.20, 6.5, 15.0] | 1.0538 | booksum 0.9872 | odrzucone (underround) |

Czyli przy dużym faworycie okrojony rynek 1X2 przechodzi przez Shina bez
sygnału błędu i produkuje bezsensowny rozkład dwuelementowy. To jest dokładnie
scenariusz, przed którym ostrzega reguła 17.

### Ile wierszy ma niekompletny rynek 1X2 na realnych danych i co się z nimi dzieje

Rozkład liczby obecnych, poprawnych (>1.0) kursów 1X2 per wiersz, po wszystkich
4151 meczach:

| bukmacher | 0 kursów | 1 kurs | 2 kursy | 3 kursy |
|---|---|---|---|---|
| pinnacle | 264 | 0 | **0** | 3887 |
| betfair_exchange | 3495 | 0 | **0** | 656 |
| bet365 | 3808 | 0 | **0** | 343 |
| market_max | 0 | 0 | 0 | 4151 |
| market_avg | 0 | 0 | 0 | 4151 |

**Częściowych rynków (1 lub 2 z 3) nie ma ani jednego.** Braki w
football-data są zawsze "wszystko albo nic" — cały blok kolumn bukmachera jest
pusty. Wiersze z 0 kursami są odfiltrowane w `_build_closing_odds`, policzone
w `report.closing_incomplete` i (dla Pinnacle) per sezon w
`pinnacle_missing_by_season` z ostrzeżeniem w logu.

Dodatkowo booksum wszystkich wierszy, które faktycznie trafiają do Shina
w tym backteście, mieści się w rozsądnym zakresie: pinnacle 1.0102-1.0730
(mediana 1.0297), betfair_exchange 1.0010-1.0223 (mediana 1.0097). Zero
wierszy w underround, zero wierszy z absurdalnym booksumem.

### ODPOWIEDŹ

**TAK — w tym backteście Shin dostaje wyłącznie kompletne rynki 1X2, i jest to
udowodnione liczbowo: 0 wierszy z 1 lub 2 kursami z 3 na 4151 meczów, dla
każdego z pięciu bukmacherów; booksum każdego wiersza podanego Shinowi mieści
się w [1.0010, 1.0730].** Reguła 17 jest w praktyce spełniona.

**ALE walidacja stoi w niewłaściwym miejscu.** Egzekwuje ją
`ingest/football_data.py:392`, czyli warstwa ingestu, a nie punkt wywołania
(`metrics.py:201`) ani sam `shin_probabilities`. Każda inna ścieżka do Shina —
inne źródło kursów, ręczna ramka, przyszły poller — omija tę bramkę, a sam
Shin przepuści okrojony rynek z faworytem bez żadnego sygnału (dowód wyżej:
[1.05, 15.0] daje `converged=True` i p=[0.9429, 0.0571]).
Klasyfikacja: **DO SPRAWDZENIA** dla dzisiejszego wyniku (wpływ zerowy),
**POWAŻNE jako dług** przy wejściu drugiego źródła kursów.

## TEST FALSYFIKUJĄCY — permutacja etykiet (test trucizny na całym pipeline)

Zamiast spekulować, puściłem cały walk-forward na danych z **globalnie
przepermutowanymi parami (home_goals, away_goals)** między meczami. Po takiej
permutacji wyniki są niezależne od drużyn, więc Elo staje się błądzeniem
losowym i **nie może** mieć żadnej przewagi nad baseline'em stałej. Jeżeli
gdziekolwiek w pipeline wynik meczu wyciekał do jego własnej predykcji,
przewaga by przetrwała.

| przebieg | LL stała | LL elo | elo − stała [95% CI] | luka pin | luka bfec |
|---|---|---|---|---|---|
| **oryginał** | 1.0742 | 1.0542 | **−0.0200** [−0.0271, −0.0132] | +0.0145 | +0.0121 |
| permutacja seed=1 | 1.0728 | 1.0730 | +0.0001 [−0.0005, +0.0008] | −0.0532 | −0.0350 |
| permutacja seed=2 | 1.0784 | 1.0786 | +0.0003 [+0.0000, +0.0005] | −0.0478 | −0.0430 |
| permutacja seed=3 | 1.0748 | 1.0751 | +0.0003 [−0.0002, +0.0007] | −0.0541 | −0.0559 |
| permutacja seed=7 | 1.0762 | 1.0764 | +0.0001 [−0.0005, +0.0008] | −0.0404 | −0.0202 |
| permutacja seed=11 | 1.0756 | 1.0756 | +0.0001 [−0.0006, +0.0008] | −0.0474 | −0.0174 |

**Interpretacja.** Przewaga Elo nad stałą spada z −0,0200 do +0,0001..+0,0003,
czyli do **dokładnie zera z dokładnością do szumu**, i to konsekwentnie po
stronie "Elo minimalnie gorsze" — tak, jak powinno być dla modelu bez
informacji, który dokłada wariancję estymacji. Gdyby wynik meczu przeciekał do
własnej predykcji (przez okno `rolling`, kolejność aktualizacji Elo, merge bez
warunku czasowego albo dopasowanie progów na teście), przewaga przetrwałaby
permutację. Nie przetrwała.

Kontrola zdrowego rozsądku w drugą stronę: luka do rynku odwraca się na
−0,02..−0,06, bo prawdziwe kursy zamknięcia z definicji nie potrafią
przewidzieć sfabrykowanych wyników, a stała i Elo-na-szumie nadal trafiają
w częstości bazowe. To jest dokładnie oczekiwane zachowanie i potwierdza, że
kursy nie mają żadnej drogi do modelu (reguła 19).

Dodatkowo: `uv run pytest` — **275 testów, wszystkie przechodzą**.

## PODSUMOWANIE

### Tabela wszystkich znalezisk (wg wagi)

| # | waga | plik:linia | reguła | co | kierunek wpływu | rząd wielkości |
|---|---|---|---|---|---|---|
| 1 | **POWAŻNE** | `metrics.py:99-126` (konsument: `elo_baseline.py:193, 331-335`) | 11 | Bootstrap parowany, ale **iid po meczach**; brak wariantu blokowego po sezonach mimo silnej heterogeniczności międzysezonowej (luka od −0.0045 do +0.0378) | zawyża **pewność**, nie samą lukę | CI za wąskie o **31%**: [+0.0082,+0.0209] zamiast [+0.0062,+0.0229] |
| 2 | **POWAŻNE** | ROADMAP.md krok 3 + `elo_baseline.py:32-35` | 11 | Dwie luki (+0,0145 i +0,012) zestawione obok siebie bez adnotacji, że są liczone na **rozłącznych okresach i różnych n** (3055 vs 656) | zaprasza do fałszywego wniosku "exchange łatwiejszy do pobicia" | cała różnica 0,0024 to efekt podzbioru; efekt źródła 0,0006 [−0,0028,+0,0039] |
| 3 | DO SPRAWDZENIA | `elo_baseline.py:452-455`, `features/elo.py:52-56` | 10 | Hiperparametry Elo nie mają foldu walidacyjnego; CLI wystawia je przy przebiegu drukującym wynik testowy | ryzyko, **nie stwierdzone naruszenie** | strojenie na teście dałoby 0,0132 zamiast 0,0145 (−9%) dla Pinnacle i 0,0082 zamiast 0,0121 (−32%) dla BFEC |
| 4 | DO SPRAWDZENIA | `shin.py:174-179, 217-221` | 16 | Przy `allow_underround=True` i booksum<1 zwracana jest **normalizacja proporcjonalna** opakowana w ShinResult z `converged=False` | zawyżałoby longshoty, fałszywe +EV | **zero dziś** (0 wierszy w underround dla obu referencji) |
| 5 | DO SPRAWDZENIA | `shin.py:121-153` vs `metrics.py:201` | 17 | Walidacja kompletności rynku stoi w ingeście, nie w punkcie wywołania; sam Shin przepuszcza okrojony rynek z faworytem | j.w. | **zero dziś** (0 rynków częściowych w danych) |
| 6 | DO SPRAWDZENIA | `football_data.py:224-233` | 12 | `data/raw/` ma jeden snapshot, a serwis koryguje wiersze wstecz | nieokreślony | nieoznaczalny bez drugiego snapshotu |
| 7 | DROBNE | `elo_baseline.py:178-181` | 11 | Inner join wycina mecze bez kursu **po cichu**; raport podaje tylko `gap.n` | przejrzystość | 0 na liczby |
| 8 | DROBNE | `elo_baseline.py:366-373` | — | 15 etykiet istotności przy 95% bez korekty na wielokrotne porównania | zawyża wrażenie istotności sezonowej | oczekiwane ~0,65 FP na 13 testów, obserwowane 3 |
| 9 | DROBNE | `metrics.py:200-203` | 17 | ValueError z Shina nie jest łapany; market_max (1530/4151 w underround) wysadziłby przebieg | zachowanie głośne = bezpieczne | 0 |
| 10 | DROBNE | `metrics.py:219`, `elo_baseline.py:273-278` | 11 | Licznik odrzuconych przez `DataFrame.attrs` — kruchy kanał | przejrzystość | not_converged=0 |
| 11 | DROBNE | `shin.py:226` | — | `ShinResult.iterations` zawsze 200, niezależnie od faktycznej liczby iteracji | mylące w diagnostyce | 0 |
| 12 | DROBNE | `shin.py:165-172` | — | Przy booksum≈1 brak renormalizacji, sum(p)=booksum (odchyłka 1e-12) | 0 | 0 |
| 13 | DROBNE | `football_data.py:492` | 2 | `Time.str.strip()` rzuci AttributeError zamiast policzyć zera przy pustej kolumnie Time | ryzyko przyszłego błędu | 0 |
| 14 | DROBNE | `features/elo.py:180-187` | — | Carry-over stosowany raz przy powrocie drużyny, niezależnie od liczby opuszczonych sezonów | obojętny kierunkowo | pomijalny |

**Znalezisk KRYTYCZNYCH: zero.** Nie znalazłem ani jednego miejsca, w którym
informacja z przyszłości trafia do predykcji.

### Odpowiedzi na cztery pytania — po jednym zdaniu

**PYTANIE 1.** Selekcja **nie jest losowa, ale jest kalendarzowa, nie wynikowa**
— braki to w 100% strukturalna niedostępność źródła (Pinnacle znika od 2025/26:
194+69 meczów; BFEC zaczyna się w 2024/25), rozkład 1/X/2 w meczach usuniętych
nie różni się od pozostałych (chi2 p=0,77-0,89), a luka Elo-rynek na meczach
usuniętych jest statystycznie taka sama jak na zachowanych (p=0,54-0,55), więc
efekt selekcji na raportowane +0,0145 wynosi około **+0,0005 (3%), i to
w kierunku konserwatywnym**.

**PYTANIE 2.** Różnica 0,0145 vs 0,012 jest **artefaktem zmiany podzbioru
meczów, nie różnicą między źródłami**: na 418 meczach, gdzie oba źródła
istnieją równocześnie, różnica luk wynosi **+0,0006 [−0,0028, +0,0039]**
(korelacja prawdopodobieństw po Shinie 0,975-0,994, MAE do 0,0086, różnica log
lossu −0,0006 mimo booksumu 1,0415 vs 1,0096), podczas gdy sama zmiana
podzbioru przy niezmienionym źródle referencyjnym daje 0,0039.

**PYTANIE 3.** **Zero** wierszy kończy jako NaT i zero nie ma godziny (0 z 4151),
obie liczby są policzone i zaraportowane (`rows_ambiguous_dst` dodatkowo
z `log.warning` z listą meczów), nic nie jest filtrowane po cichu, granicą
odcięcia jest timestamp a nie data, a strefa `Europe/London` została
zweryfikowana empirycznie (identyczny profil modalnych godzin polskich po obu
stronach zmiany czasu).

**PYTANIE 4.** **Tak** — Shin dostaje wyłącznie kompletne rynki, dowód:
0 wierszy z 1 lub 2 kursami z 3 na 4151 meczów i 5 bukmacherów (braki są
zawsze "wszystko albo nic"), booksum każdego wiersza podanego Shinowi w
przedziale [1,0010; 1,0730]; ale walidacja stoi w ingeście
(`football_data.py:392`), a nie w punkcie wywołania, i sam `shin_probabilities`
**nie waliduje kompletności** — okrojony rynek z dużym faworytem przechodzi
przez niego bez sygnału błędu.

### Ocena wiarygodności raportowanych liczb

| liczba | ocena |
|---|---|
| **n = 3319** (OOS) | **wiarygodna**. 4151 − 832 (trzy pierwsze sezony przy min_train_seasons=3), zreprodukowane co do meczu. Wszystkie 4151 meczów ma wynik i godzinę, 0 odrzuceń w ingeście. |
| **Elo − Pinnacle = +0,0145** | **wiarygodna co do wartości punktowej, z zastrzeżeniem do CI**. Zreprodukowana (n=3055). Kontrfaktyk bez selekcji: +0,0144. CI powinno być [+0,0062, +0,0229], a nie [+0,0082, +0,0209]. Wniosek "rynek lepszy, luka w strefie 0,01-0,03" przeżywa obie korekty. |
| **Elo − BFEC = +0,012** | **wiarygodna, ale nieporównywalna z powyższą**. Zreprodukowana (n=656). To nie jest druga, niezależna referencja — to ta sama luka zmierzona na innym, czterokrotnie mniejszym i późniejszym podzbiorze. Na wspólnych meczach obie referencje są nierozróżnialne. |

**Czy wyniki tego backtestu można traktować poważnie — TAK.** Nie znalazłem
przecieku informacji z przyszłości: Elo emituje rating przed aktualizacją,
ordered logit jest dopasowywany wyłącznie na sezonach wcześniejszych ze stałą
skalującą 400 zamiast statystyki ze zbioru, baseline stałej idzie z trainu,
sezony nie nakładają się czasowo, sortowanie jest po timestampie a nie po
dacie, kurs rynkowy nie ma żadnej drogi do modelu, a test trucizny (globalna
permutacja wyników) kasuje całą przewagę Elo z −0,0200 do +0,0001..+0,0003,
czyli do zera z dokładnością do szumu. Dwa zastrzeżenia, które trzeba dopisać
do raportu z kroku 3: **CI luki do Pinnacle jest o ~31% za wąskie** (bootstrap
iid zamiast blokowego po sezonach) oraz **dwie raportowane luki nie są
porównywalne**, bo dotyczą rozłącznych okresów — na wspólnym podzbiorze różnią
się o 0,0006 przy CI zawierającym zero. Ani jedno, ani drugie nie zmienia
wniosku merytorycznego: **rynek jest lepszy od Elo o około 0,014-0,015 log
lossu, czyli same ratingi nie wystarczą**. Najważniejszy kontekst dla
ostrożności wymaganej przez CLAUDE.md: **w tym repozytorium nie ma jeszcze
żadnego symulowanego yieldu ani stawkowania** — nie ma więc liczby, która
mogłaby być "zbyt dobra", i cała ocena dotyczy wyłącznie diagnostyki log lossu.


---

# ROZSTRZYGNIĘCIA — co naprawiono, co zostaje otwarte

**Data:** 2026-09-30. Sekcja dopisana po audycie, przez sesję prowadzącą.
Wszystkie liczby poniżej zweryfikowane niezależnie od audytora, na tych
samych danych (`data/interim/football_data/`).

## Weryfikacja znalezisk POWAŻNYCH przed naprawą

Obydwa potwierdzone własnym przebiegiem, nie przyjęte na słowo.

Luka Elo do Pinnacle per sezon — to jest dowód na korelację wewnątrz sezonu:

```
2015/16 +0.0021   2018/19 +0.0189   2021/22 +0.0225   2024/25 +0.0193
2016/17 +0.0319   2019/20 +0.0129   2022/23 +0.0378   2025/26 +0.0091
2017/18 -0.0045   2020/21 +0.0085   2023/24 -0.0037
```

Rozrzut −0,0045…+0,0378 przy CI iid o szerokości 0,0127 — bootstrap
losujący pojedyncze mecze nie mógł tego rozrzutu zobaczyć.

Przecięcie referencji: **418 meczów**, nie zero. Sformułowanie „rozłączne
okresy" z podsumowania audytu jest nieścisłe — zbiory się przecinają
(2024/25: 306, 2025/26: 112). Istotne jest co innego: 2637 meczów ma tylko
Pinnacle, 238 tylko BFEC, więc luki pooled stoją w większości na różnych
meczach i nie są porównywalne. Wniosek audytora zostaje, uzasadnienie
poprawione.

## NAPRAWIONE

### POWAŻNE 1 — bootstrap iid zamiast klastrowego (reguła 11)

`metrics.paired_bootstrap_diff` przyjmuje `groups=`. Podane — losuje
**całe sezony ze zwracaniem**, nie pojedyncze mecze. Średnia liczona jako
`suma/liczność` po wylosowanych klastrach, więc ważona liczebnością
(sezon 306-meczowy nie waży tyle co obcięty 69-meczowy).

`BootstrapDiff` niesie teraz `n_groups`, `is_clustered` i `reliable`.
`reliable` jest `False` dla klastrowego z mniej niż 8 klastrami — kwantyle
z trzech sezonów to nie przedział ufności, tylko trzy liczby. Raport
tekstowy drukuje rodzaj CI przy każdej liczbie; nie da się już przeczytać
CI, nie wiedząc, skąd pochodzi.

`elo_baseline`: luki pooled i `elo - stała` klastrują po sezonach, luki
per sezon zostają iid (jeden sezon = jeden klaster) i są w raporcie
opisane jako optymistyczne.

### POWAŻNE 2 — dwie luki zestawione bez adnotacji o podzbiorach (reguła 11)

`MarketGap` niesie `seasons` — zakres, na którym liczba powstała, jest
częścią liczby. Raport drukuje go pod każdą luką.

Nowy `ReferenceOverlap` + sekcja raportu **REFERENCJE NA WSPÓLNYM
PODZBIORZE**: obie luki policzone na przecięciu i parowana różnica log
lossów samych referencji. Gdy ta różnica nie odróżnia się od zera, raport
mówi to wprost zdaniem, a nie zostawia czytelnikowi.

### Przy okazji: `UnicodeEncodeError` w CLI

Znak `→` w raporcie wywalał `python -m valuebet.backtest.elo_baseline`
przy przekierowaniu do pliku (konsola Windows, cp1250). Podmieniony na
`->`. Nie znalezisko audytu — regresja wprowadzona tą naprawą, złapana
przy przeliczaniu.

### Testy

15 nowych, wszystkie w `tests/test_metrics.py` i `tests/test_elo_baseline.py`.
Najważniejszy: `test_clustered_bootstrap_is_wider_when_effect_is_between_groups`
— na danych z efektem grupowym CI klastrowe musi być ponad 2x szersze od iid.
Bez niego naprawa mogłaby zdegenerować się do iid i nikt by nie zauważył.
Dalej: ważenie liczebnością, flaga `reliable` przy 3 klastrach, zachowanie
wartości punktowej, determinizm, walidacja długości `groups`, oraz
`test_reference_overlap_detects_equally_good_references` (w syntetycznej
lidze obie referencje pochodzą z tego samego `shin_forward`, więc różnica
MUSI być nieistotna — inaczej sekcja nie wykrywa przypadku, dla którego
powstała).

`pytest` 290/290, `ruff` czysto, `mypy --strict` czysto, `-k future_poison` 5/5.

## DO SPRAWDZENIA — co konkretnie by to rozstrzygnęło

Nie naprawiane w tej sesji. Dla każdego: jedno wykonalne działanie, które
zamienia „nie wiadomo" w „wiadomo".

### DS-3. Hiperparametry Elo bez foldu walidacyjnego (reguła 10)

*Rozstrzyga:* dopisać do `run_elo_baseline` wewnętrzny fold — dla każdego
sezonu testowego `S` wybrać `k` maksymalizujące log loss na **ostatnim
sezonie okna treningowego**, potem dopasować na pełnym oknie i predykować
`S`. Jeśli tak wybrane `k` daje lukę w granicach szumu wokół dzisiejszych
+0,0145, reguła 10 nigdy nie była złamana i sprawa jest zamknięta na
piśmie. Jeśli daje istotnie mniej — dzisiejsze `k=20` jest strojone przez
historię sesji, nie przez dane, i wynik trzeba przepisać.

*Dlaczego to nie jest pilne:* siatka pokazała, że luka rośnie monotonicznie
z `k` (0,0132 przy k=10 → 0,0174 przy k=40), a `k=20` **nie jest** minimum.
Strojenie pod wynik wybrałoby k=10. To silna przesłanka, że nikt nie
stroił — ale przesłanka, nie dowód, bo pochodzi z tego samego zbioru
testowego. Dowodem jest dopiero fold walidacyjny.

*Uwaga osobna:* `home_advantage` jest nieidentyfikowalny obok ordered
logit — zmiana 40→90 rusza lukę o 0,0002, bo próg logitu absorbuje
przesunięcie. To nie jest hiperparametr do strojenia, tylko parametr
pozorny. Warto go wyjąć z `--home-advantage` w CLI albo opisać, żeby nikt
nie tracił na to czasu. **Konsekwencja dla kroku 4:** w Dixon-Coles `γ`
jest estymowane razem z `α, β` w jednej wiarygodności i tam ten problem
nie znika sam — patrz identyfikowalność, STEP4_PLAN §1.2.

### DS-4. `shin.py` zwraca normalizację proporcjonalną przy `allow_underround=True` (reguła 16)

*Rozstrzyga:* jedna decyzja projektowa, nie pomiar. Albo (a) ta ścieżka
podnosi wyjątek zamiast zwracać cokolwiek — wtedy reguła 16 jest
egzekwowana przez typ, nie przez dyscyplinę wołającego; albo (b) zwracany
obiekt dostaje pole `method: Literal["shin", "proportional"]`, a każdy
konsument ma obowiązek je sprawdzić. Dzisiejsze `converged=False` jest za
słabym sygnałem: `metrics.market_probabilities` je honoruje i pomija
wiersz, ale to zbieg okoliczności, nie kontrakt.

*Stan faktyczny dziś:* 0 wierszy w underround dla obu referencji, więc
wpływ na raportowane liczby jest zerowy. To pułapka na moment, w którym
pojawią się kursy agregowane albo exchange bez prowizji.

### DS-5. Walidacja kompletności rynku stoi w ingeście, nie przy wywołaniu (reguła 17)

*Rozstrzyga:* przenieść próg do `shin_probabilities` jako parametr
`expected_outcomes: int | None`. Wołający deklaruje, ilu wyników oczekuje
(3 dla 1X2, 2 dla O/U i AH), a funkcja odrzuca wejście o innej długości.
Dziś Shin nie może tego sprawdzić sam, bo nie wie, czego oczekiwać — i to
jest dokładnie ta informacja, której brakuje w sygnaturze.

*Test, który to domyka:* `[1.05, 15.0]` podane jako „1X2 bez remisu" musi
podnieść wyjątek. Dziś zwraca `converged=True` i `p=[0.9429, 0.0571]` —
liczbę, która wygląda poprawnie i jest bezsensowna.

*Wpływ na dziś:* zerowy. Rozkład liczby obecnych kursów 1X2 per wiersz to
`{0, 3}` dla każdego z 5 bukmacherów — ani jednego wiersza z 1 lub 2
kursami. Krok 4 otwiera rynki dwustronne i wtedy to przestaje być
teoretyczne.

### DS-6. `data/raw/` ma jeden snapshot, a źródło koryguje wiersze wstecz (reguła 12)

*Rozstrzyga:* pobrać football-data.co.uk drugi raz do `data/raw/` pod
nowym znacznikiem czasu i zdiffować z istniejącym po `match_id`. Liczba
zmienionych wierszy jest odpowiedzią. Zero — append-only wystarczy.
Niezero — trzeba wersjonować snapshoty i wiedzieć, na której wersji
powstała każda raportowana liczba, bo inaczej backtest przestaje być
odtwarzalny między pobraniami.

*Dlaczego to nie jest kosmetyka:* reguła 12 chroni przed nadpisaniem
**przez nas**. Przed cichą korektą **u źródła** nie chroni nic.
