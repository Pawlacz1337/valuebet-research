# KROK 4 — Dixon-Coles, rynki pochodne, Kelly symultaniczny

Plan wykonawczy. Czytaj razem z `CLAUDE.md` (reguły) i `CONTEXT.md` §5
(historia błędów).

**Warunek wejścia:** audyt z kroku 3 zamknięty, `ROADMAP.md` odhaczony.
Nie zaczynaj bez tego.

---

## 0. Dlaczego to jeden krok, a nie trzy

Dixon-Coles produkuje **pełną macierz łączną** `P(gole_gosp=i, gole_gość=j)`.
Rynki pochodne to sumy różnych komórek **tej samej** macierzy — koszt
krańcowy kilkudziesięciu linii.

Ale rynki pochodne natychmiast tworzą **skorelowane zakłady**: Over 2.5 i
AH −0.5 w jednym meczu wynikają z tych samych λ, μ. Jeśli model
przeszacowuje gole, mylisz się na obu naraz. Klasyczny Kelly per zakład
nie ma o tym pojęcia.

Dlatego Kelly symultaniczny nie jest ulepszeniem — jest **warunkiem
bezpieczeństwa** dla rynków pochodnych. Wdrażamy razem.

---

## 1. `models/dixon_coles.py`

### 1.1 Specyfikacja

Parametry: `α_i` (siła ataku), `β_i` (słabość obrony) dla każdej drużyny,
`γ` (atut własnego boiska), `ρ` (korekta niskich wyników).

Dla meczu gospodarz `i` — gość `j`:

```
λ = α_i · β_j · γ        (oczekiwane gole gospodarza)
μ = α_j · β_i            (oczekiwane gole gościa)
```

Korekta Dixona-Colesa, dotyczy wyłącznie czterech najniższych wyników:

```
τ(0,0) = 1 − λ·μ·ρ
τ(0,1) = 1 + λ·ρ
τ(1,0) = 1 + μ·ρ
τ(1,1) = 1 − ρ
τ(x,y) = 1                dla pozostałych
```

Log-wiarygodność z wygaszaniem czasowym:

```
ℓ = Σ_k φ(t_k) · [ log τ(x_k, y_k, λ_k, μ_k, ρ)
                 + log Poisson(x_k; λ_k)
                 + log Poisson(y_k; μ_k) ]

φ(t) = exp(−ξ · t)        t = dni przed datą odniesienia
```

### 1.2 Identyfikowalność — NIE POMIJAĆ

Wiarygodność jest niezmiennicza względem `α → c·α`, `β → β/c` (bo `λ`
zależy od iloczynu). Bez ograniczenia model jest nieidentyfikowalny, a
hesjan osobliwy wzdłuż tego kierunku — L-BFGS będzie się wlókł albo
zwróci losową wartość z grzbietu.

Ograniczenie: `Σ log α_i = 0`, egzekwowane **wewnątrz funkcji celu**
przez odjęcie średniej. Różniczkowalne, nie wymaga solvera z warunkami.

### 1.3 Ograniczenia na ρ

`τ` musi być dodatnie dla każdego meczu:

```
ρ < 1/(λ·μ)        ρ < 1
ρ > −1/λ           ρ > −1/μ
```

W praktyce ogranicz `ρ ∈ (−0.2, 0.2)` — bezpieczne dla typowych
`λ, μ ∈ (0.3, 3.0)`. Waliduj po dopasowaniu, że wszystkie `τ > 0`, i
podnieś wyjątek, jeśli nie.

### 1.4 Optymalizacja

- Parametryzacja w log-przestrzeni: `[log α_1..n, log β_1..n, log γ, ρ]`
  — utrzymuje dodatniość bez ograniczeń w solverze.
- `scipy.optimize.minimize`, metoda `L-BFGS-B`, `ρ` z bounds.
- Punkt startowy: `log α = log β = 0`, `log γ = 0.3` (γ ≈ 1.35),
  `ρ = −0.05`.
- Podaj gradient analityczny albo zaakceptuj różniczkowanie numeryczne —
  przy 38 parametrach i 4000 meczach numeryczne wystarczy, ale zmierz czas.
- `result.success == False` → **podnieś wyjątek**, nie zwracaj wyniku.

### 1.5 Strojenie ξ — pułapka leakage

`ξ` jest hiperparametrem. Dopasuj go **walk-forward wewnątrz okna
treningowego**, nigdy na zbiorze testowym (reguła 10).

Procedura: siatka `ξ ∈ {0, 0.001, 0.002, 0.003, 0.005, 0.008}`, dla
każdego sezonu testowego `S` wybierz `ξ` maksymalizujące
log-wiarygodność na ostatnim sezonie okna treningowego (walidacja
wewnętrzna), potem dopasuj na pełnym oknie i predykuj `S`.

Pół-okres = `ln(2)/ξ`. Dla `ξ = 0.003` to ~231 dni.

### 1.6 API

```python
@dataclass(frozen=True)
class DixonColesParams:
    attack: dict[str, float]
    defence: dict[str, float]
    home_advantage: float
    rho: float
    xi: float
    n_fit: int
    converged: bool

def fit_dixon_coles(
    matches: pd.DataFrame,
    *,
    xi: float = 0.003,
    reference_date: pd.Timestamp | None = None,
    max_iter: int = 500,
) -> DixonColesParams: ...

def score_matrix(
    params: DixonColesParams,
    home_team_id: str,
    away_team_id: str,
    *,
    max_goals: int = 10,
) -> NDArray[np.float64]: ...   # (max_goals+1, max_goals+1), sumuje się do 1
```

`reference_date` domyślnie = max `kickoff_utc` w `matches`. **Dla
predykcji przyszłego meczu ustaw ją na `asof_utc` tego meczu**, nie na
datę meczu — inaczej wagi czasowe widzą przyszłość.

### 1.7 Macierz wyników

```python
P[i, j] = τ(i, j, λ, μ, ρ) · pois.pmf(i, λ) · pois.pmf(j, μ)
P /= P.sum()
```

**Renormalizacja jest obowiązkowa** — korekta `τ` psuje normalizację o
rząd 1e-3. Bez tego prawdopodobieństwa rynków nie sumują się do 1 i EV
jest systematycznie przesunięte.

`max_goals = 10` wystarczy: `P(gole > 10)` przy `λ ≈ 1.5` to rząd 1e-7.
Waliduj, że masa poza obcięciem jest < 1e-6, i ostrzegaj powyżej.

---

## 2. Bramka jakościowa — ZASTĄPIONA

**Ta sekcja jest nieaktualna. Obowiązuje `STEP4_ENSEMBLE.md`.**

Pierwotna wersja mówiła: „DC musi pobić Elo na 1X2, inaczej jest błąd w
implementacji". To było za mocne. Porównywała model skalibrowany (Elo +
ordered logit) z nieskalibrowanym (surowa macierz DC) i mierzyła DC na
rynku, na którym najmniej go potrzebujemy — Elo nie wycenia O/U ani AH
w ogóle.

Nowa bramka (G1–G4), architektura stackingu i projekcja macierzy na
skalibrowane 1X2: `STEP4_ENSEMBLE.md` §4–§6.

**Konsekwencja dla reszty tego planu: wszystkie rynki z §3 liczone są z
macierzy po projekcji `P'`, nie z surowej `P`.**

---

## 3. `pricing/markets.py` — wycena z macierzy

### 3.1 Konwencja zwrotu

Dla zakładu o kursie `k` i stawce 1 jednostki definiujemy **mnożnik
zwrotu** `R` (ile dostajesz z powrotem, nie zysk):

| Rozstrzygnięcie | R |
|---|---|
| pełna wygrana | `k` |
| pół wygranej | `1 + (k − 1)/2` |
| zwrot (push) | `1` |
| pół przegranej | `0.5` |
| pełna przegrana | `0` |

```
EV = Σ P(rozstrzygnięcie) · R(rozstrzygnięcie) − 1
```

Ta jedna konwencja obsługuje wszystkie rynki włącznie z ćwiartkami.
Nie rób osobnych wzorów per rynek.

### 3.2 1X2

```
P(1) = Σ_{i>j} P[i,j]
P(X) = Σ_{i=j} P[i,j]
P(2) = Σ_{i<j} P[i,j]
```

### 3.3 Over/Under linia L

```
total = i + j
L połówkowe (2.5):   over = Σ_{total > L},  under = reszta,  brak pusha
L całkowite (3.0):   over = Σ_{total > L},  push = Σ_{total = L},
                     under = Σ_{total < L}
```

### 3.4 Handicap azjatycki h (dla gospodarza)

```
margines = i − j + h
margines > 0  →  wygrana
margines = 0  →  push
margines < 0  →  przegrana
```

Linie ćwiartkowe dzielą stawkę na pół:

```
h = −0.25  →  połowa na 0.0, połowa na −0.5
h = −0.75  →  połowa na −0.5, połowa na −1.0
```

Zaimplementuj to jako **dekompozycję**, nie jako osobny wzór: funkcja
`split_handicap(h) -> list[tuple[float, float]]` zwracająca pary
(linia, waga). Dla linii pełnych i połówkowych zwraca jeden element o
wadze 1.0. Wtedy reszta kodu nie musi wiedzieć o ćwiartkach.

### 3.5 BTTS

```
P(tak) = Σ_{i≥1, j≥1} P[i,j]
P(nie) = 1 − P(tak)
```

### 3.6 PUŁAPKA: push pod polskim podatkiem

To jest nieoczywista interakcja i kosztuje realne pieniądze.

Przy podatku obrotowym płacisz 1 jednostkę, do gry idzie `tax`. Przy
zwrocie dostajesz z powrotem **`tax`, nie 1** — podatek nie jest
zwracany.

```
R_wygrana = tax · k
R_push    = tax          ← STRATA 12% przy tax = 0.88
R_przegrana = 0
```

**Push jest przegraną 12%, nie zdarzeniem neutralnym.** Handicapy z
wysokim prawdopodobieństwem pusha (linie całkowite: 0.0, −1.0, +1.0,
O/U 2.0, 3.0) są pod podatkiem znacznie gorsze, niż wyglądają.

Przy `tax = 1.00` (promocja bez podatku) push jest neutralny. To kolejny
argument, dlaczego cały projekt stoi na promocji.

Konsekwencja projektowa: **`tax_factor` musi wchodzić do wyceny per
rozstrzygnięcie, nie jako mnożnik EV na końcu.** Jeśli policzysz
`EV_bez_podatku · tax`, dostaniesz złą liczbę dla rynków z pushem.

---

## 4. `pricing/kelly.py`

### 4.1 Kelly z pushem

Wzór zamknięty `f* = (p·k − 1)/(k − 1)` działa tylko dla zakładów
dwustanowych. Przy pushu maksymalizuj numerycznie:

```
maksymalizuj  E[log(1 − f + f·R)]  względem f ∈ [0, 1)
```

`scipy.optimize.minimize_scalar` z `bounds=(0, 0.99)`, metoda `bounded`.
Tanie i dokładne. Sprawdź w teście, że dla zakładu bez pusha wynik
pokrywa się ze wzorem zamkniętym z dokładnością 1e-9.

Potem: `f_ułamkowy = 0.25 · f*`, twardy limit `min(f, 0.02)` (reguły 21–23).

### 4.2 Symultaniczny, poziom 1 — naiwne skalowanie

Dwa poziomy grupowania, bo korelacja nie jest jednorodna:

```python
CAP_MECZ  = 0.02   # wszystkie zakłady na jeden mecz
CAP_OKNO  = 0.06   # wszystkie zakłady rozstrzygające się w tym samym oknie

def scale_group(fractions: dict[str, float], cap: float) -> dict[str, float]:
    total = sum(fractions.values())
    if total <= cap:
        return dict(fractions)
    factor = cap / total
    return {key: value * factor for key, value in fractions.items()}
```

Kolejność: najpierw skaluj w obrębie meczu, potem w obrębie okna.
Skalowanie okna działa na już przeskalowanych ułamkach meczowych.

Okno = mecze, których `kickoff_utc` mieści się w tym samym przedziale
(domyślnie: ta sama doba UTC). Funkcja grupująca ma być parametrem, nie
stałą — przy innych ligach okna będą inne.

**Ograniczenie poziomu 1, świadome:** traktuje zakłady w jednym meczu tak
samo jak zakłady w różnych meczach tego dnia, choć te pierwsze są dużo
silniej skorelowane. Dlatego `CAP_MECZ` jest wyraźnie ciaśniejszy.
Poziom 2 (pełna optymalizacja na łącznej macierzy DC) rozwiąże to
poprawnie — nie teraz.

---

## 5. `backtest/simulate.py`

Symulacja pełnego portfela zakładów.

Wymagania wynikające z reguł:
- Stawki liczone z bankrolla **przed** rozliczeniem okna, nie po (reg. 24)
- `tax_factor` per rozstrzygnięcie, nie jako mnożnik na końcu (§3.6)
- Rozliczenie chronologiczne (reg. 26)
- Raport z `n`, yieldem, przedziałem ufności, maksymalnym obsunięciem
- Yield raportowany **osobno per rynek** — 1X2, AH, O/U

Ten ostatni punkt jest diagnostyczny: jeśli cały zysk pochodzi z jednego
rynku, to albo tam jest prawdziwa nieefektywność, albo tam jest błąd w
logice rozliczeniowej. Obie hipotezy trzeba sprawdzić.

---

## 6. Testy — minimum

**Dixon-Coles**
- `test_recovers_known_parameters` — wygeneruj 5000 meczów z zadanych
  `α, β, γ, ρ`, dopasuj, sprawdź odzyskanie z tolerancją. **To jest
  odpowiednik testu round-trip z Shina — najważniejszy test modułu.**
- `test_matrix_sums_to_one`
- `test_matrix_1x2_matches_direct` — 1X2 z macierzy == wycena bezpośrednia
- `test_tau_positive_for_fitted_params`
- `test_identifiability_constraint_enforced` — dwa przebiegi z różnych
  punktów startowych dają te same `λ, μ`
- `test_truncation_mass_negligible`

**Rynki**
- `test_over_under_half_line_no_push`
- `test_over_under_integer_line_has_push`
- `test_handicap_zero_is_draw_no_bet`
- `test_quarter_handicap_splits_into_two` — dla każdej z ±0.25, ±0.75
- `test_quarter_handicap_ev_matches_manual` — policz ręcznie jeden
  przypadek i porównaj
- `test_market_probabilities_sum_to_one` — dla każdego rynku

**Podatek**
- `test_push_loses_tax` — przy `tax=0.88` push daje `R = 0.88`, nie 1.0
- `test_no_tax_push_neutral` — przy `tax=1.0` push daje `R = 1.0`
- `test_ev_with_push_differs_from_naive_scaling` — dowód, że
  `EV_bez_podatku · tax` daje inną (złą) liczbę

**Kelly**
- `test_kelly_no_push_matches_closed_form`
- `test_kelly_with_push_is_smaller`
- `test_fractional_and_cap_applied`

**Symultaniczny**
- `test_scaling_caps_match_total`
- `test_scaling_preserves_proportions`
- `test_no_scaling_below_cap`
- `test_window_scaling_applies_after_match_scaling`

**Trucizna**
- Dopisz nowe cechy DC do `_build_all` w `tests/test_features_base.py`
  (reguła z `CLAUDE.md`, sekcja „Zanim uznasz zadanie za skończone")

---

## 7. Kolejność wykonania

1. `models/dixon_coles.py` + testy odzyskiwania parametrów — **ZROBIONE**
2. **`STEP4_ENSEMBLE.md` w całości** — lockbox, sparowane CI, diagnoza
   remisów, projekcja, stacking, bramka G1–G4
3. `pricing/markets.py` + testy pushy i ćwiartek — **z macierzy `P'`**
4. `pricing/ev.py` — EV z `tax_factor` per rozstrzygnięcie
5. Kalibracja **osobno per rynek** na `P'`
6. `pricing/kelly.py` — z pushem, ułamkowy, limity
7. Skalowanie symultaniczne poziom 1
8. `backtest/simulate.py` + raport per rynek
9. `backtest-auditor` na całości
10. Aktualizacja `ROADMAP.md` i `CONTEXT.md` §5

---

## 8. Czego się spodziewać

**Kalibracja per rynek się rozjedzie.** Korekta `τ` dotyczy tylko
czterech najniższych wyników i jest strojona pod 1X2. Dla totali liczy
się ogon, a rzeczywisty rozkład goli jest lekko nadmiernie rozproszony
względem Poissona. Model dobrze skalibrowany na 1X2 bywa systematycznie
przestrzelony na Over 3.5. **To jest oczekiwane, nie bug** — ale musi być
zmierzone i udokumentowane, a nie odkryte na produkcji.

**DC prawdopodobnie nadal nie pobije rynku na 1X2.** Zamknięcie Pinnacle
zawiera informację, której nie masz (składy, kontuzje, pieniądze
syndykatów). Celem kroku 4 nie jest pobicie Pinnacle — celem jest
**zmniejszenie luki** i **otwarcie rynków, których polski bukmacher
wycenia gorzej niż 1X2**.

Jeśli DC nagle pobije rynek o dużo — szukaj błędu, zanim się ucieszysz
(`CLAUDE.md`, nagłówek o yieldzie powyżej 8%).
