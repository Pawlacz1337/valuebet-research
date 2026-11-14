# KROK 4 — aneks: stacking DC + Elo i spójna macierz wyników

Zastępuje §2 („bramka jakościowa") z `STEP4_PLAN.md`. Czytaj razem z
`CLAUDE.md`, `ROADMAP.md` i `CONTEXT.md` §5.

---

## 0. Co się zmieniło i dlaczego

Stan: DC zaimplementowane poprawnie, ale na 1X2 przegrywa z Elo:
`LL(DC) = 1.0555`, `LL(Elo) = 1.0542`. Mieszanka 50/50 daje `1.0526`.
DC przeszacowuje remisy: w koszyku `P(X) ∈ [0.30, 0.35]` przewiduje 31.1%,
realizacja 23.9% (3.3 SE).

**Pierwotna bramka była źle postawiona.** `STEP4_PLAN.md` §2 mówiła: „jeśli
DC nie bije Elo, to jest błąd w implementacji". To było za mocne z dwóch
powodów:

1. Porównywała model skalibrowany (Elo + ordered logit, 3 parametry na
   trainie) z nieskalibrowanym (surowa macierz DC). Jabłka z gruszkami.
2. Mierzyła DC na rynku, na którym go najmniej potrzebujemy. **Elo w ogóle
   nie wycenia Over/Under ani handicapów.** Po to jest DC.

Ten dokument stawia bramkę na nowo i rozwiązuje konflikt między kalibracją
1X2 a rynkami pochodnymi.

---

## 1. Najpierw: czy impas jest w ogóle istotny

Różnice, o których rozmawiamy, to ~0.0013–0.0016 log loss. Audyt pokazał,
że przy 11 klastrach sezonowych CI luki Elo−rynek ma szerokość ~0.017.

**Zanim zbudujesz cokolwiek, policz:**

```
d_m = LL_A(m) − LL_B(m)        dla każdego meczu m, na TYCH SAMYCH meczach
Δ   = mean(d)
CI  = bootstrap klastrowy po sezonach (ten sam co w metrics.py)
```

dla par: `DC − Elo`, `blend50 − Elo`, `blend50 − DC`.

**Różnica sparowana, nie dwa osobne CI.** Oba modele widzą ten sam szum
meczowy, więc wariancja różnicy jest wielokrotnie mniejsza niż wariancja
każdego z osobna. Porównywanie dwóch przedziałów „na oko" jest błędem.

Jeśli CI dla `DC − Elo` zawiera zero — **na 1X2 modele są
nierozróżnialne**, a decyzja o architekturze wynika z tego, co każdy z nich
umie wycenić, a nie z 0.0013.

Natomiast błąd kalibracji remisów (3.3 SE) jest **istotny niezależnie od
tego**. Jego naprawa jest uzasadniona kalibracją, nie bramką LL.

---

## 2. Lockbox — od teraz

Zbiór OOS (3319 meczów) był oglądany co najmniej trzy razy: Elo, DC,
mieszanka. Każda decyzja podjęta po obejrzeniu wyników zamienia go po
trochu w zbiór walidacyjny. Diagnoza remisów też powstała na nim.

**Deklarujemy lockbox:**

| Zbiór | Sezony | Rola |
|---|---|---|
| deweloperski | 2015/16 – 2024/25 | wszystkie decyzje, diagnostyka, strojenie |
| **lockbox** | **2025/26, 2026/27** | **jedna ewaluacja, na samym końcu kroku 4** |

Od tej chwili nie oglądamy wyników per sezon dla lockboxa podczas
podejmowania decyzji. Zapisz to w `ROADMAP.md`.

Lockbox jest mały (~390 meczów), więc jego CI będzie szerokie. Jego zadaniem
nie jest precyzyjna estymacja — jest wykrycie grubego przeuczenia. Jeśli
ostateczny model na lockboxie wypadnie wyraźnie gorzej niż na zbiorze
deweloperskim, to jest sygnał, że decyzje zostały dopasowane do danych.

---

## 3. Diagnoza przyczyny nadmiaru remisów — napraw u źródła, jeśli się da

Nadmiar remisów może mieć trzy różne przyczyny i **każda ma inną naprawę.**
Nie kalibruj objawu, dopóki nie wiesz, która działa.

### 3.1 Mechanizm

Mechanizm ilustracyjny (nie Twoje dane — zmierz na swoich):

```
λ=1.60 μ=0.90 ρ= 0.00   P(X)=0.250   prawdziwe siły
λ=1.35 μ=1.15 ρ= 0.00   P(X)=0.268   siły skompresowane      +1.8 pp
λ=1.35 μ=1.15 ρ=-0.13   P(X)=0.302   kompresja + ujemne ρ    +3.4 pp
```

Dwa niezależne źródła nadmiaru remisów: **kompresja sił** (λ i μ za blisko
siebie) i **ujemne ρ** (korekta τ zawyża 0-0 i 1-1).

### 3.2 Hipoteza nr 1 — prior zawyża beniaminków

Prior gaussowski na drużyny bez historii ściąga je do **średniej ligowej**.
Ale beniaminkowie są systematycznie **słabsi** od średniej ligowej. Prior
zawyża ich siłę → zawęża różnicę sił w ich meczach → podbija remisy i
zaniża ich porażki.

**Test:** rozdziel reliability diagram remisów na mecze, w których co
najmniej jedna drużyna ma < 10 meczów historii w oknie treningowym, i
resztę. Jeśli nadmiar koncentruje się w pierwszej grupie — to jest to.

**Naprawa u źródła:** średnia prioru dla drużyny bez historii = średnia
parametrów **historycznych beniaminków** w oknie treningowym (nie średnia
ligowa). Alternatywnie: rating Elo przeniesiony do przestrzeni log-λ.
Parametr estymowany z danych treningowych, nie strojony pod OOS.

### 3.3 Hipoteza nr 2 — ρ zbyt ujemne

**Test:** tabela kalibracji niskich wyników na zbiorze deweloperskim.

```
dla (i, j) w {0..3} × {0..3}:
    przewidziane = mean_m P_m[i, j]
    zrealizowane = mean_m 𝟙[wynik_m == (i, j)]
    z = (zrealizowane − przewidziane) / SE
```

Jeśli DC przeszacowuje 0-0 i 1-1, a niedoszacowuje 1-0 i 0-1 — ρ jest zbyt
ujemne. Raportuj też `ρ` dopasowane w każdym sezonie walk-forward.

**Tej tabeli potrzebujesz i tak** — to jest dokładnie ta informacja, od
której zależy jakość Over/Under.

**Naprawa:** nie strój ρ ręcznie pod częstość remisów. ρ dotyka tylko
czterech komórek i przesuwa 1-0/0-1 w przeciwną stronę — to toporna
dźwignia. Jeśli MLE ρ jest patologiczne, szukaj przyczyny (wagi czasowe,
prior, obcięcie), nie nadpisuj wyniku.

### 3.4 Hipoteza nr 3 — ξ

Zbyt małe ξ uśrednia siły po długim okresie → kompresja. Sprawdź wybrane ξ
per sezon (strojenie walk-forward było w `STEP4_PLAN.md` §1.5).

### 3.5 Reguła dotycząca strojenia

Diagnoza na zbiorze deweloperskim jest w porządku. **Wybór wartości gałki
przez maksymalizację wyniku OOS — nie.** Każda zmiana musi być albo
strukturalna i uzasadniona teorią (średnia prioru dla beniaminków), albo
wybrana walidacją wewnętrzną w oknie treningowym.

---

## 4. Architektura: kalibrujemy 1X2, macierz rzutujemy na wynik

### 4.1 Dlaczego nie „kalibruj 1X2 osobno, rynki licz z surowej macierzy"

Bo to wycenia **to samo zdarzenie na dwa sposoby**:

```
AH −0.5 gospodarz  ≡  zwycięstwo gospodarza
AH +0.5 gospodarz  ≡  1X
AH  0.0            ≡  1 / (1 + 2)  po odrzuceniu remisu
```

Zmierzone na przykładzie: surowa macierz daje `AH −0.5 = 0.3831`, a
skalibrowane 1X2 daje `P(1) = 0.4181`. **Różnica 3.5 pp dla tej samej
imprezy** — więcej niż jakakolwiek przewaga, której szukamy. System
zgłaszałby value na „1" i nie zgłaszał go na „AH −0.5" jednocześnie.
Arbitraż przeciwko samemu sobie.

### 4.2 Rozwiązanie: projekcja minimum-KL

Szukamy macierzy `P'` najbliższej `P` (w sensie dywergencji KL), która ma
zadane marginesy 1X2 `q = (q₁, q_X, q₂)`:

```
min  Σ P'[i,j] · log(P'[i,j] / P[i,j])
przy Σ_{i>j} P' = q₁,   Σ_{i=j} P' = q_X,   Σ_{i<j} P' = q₂
```

Z mnożników Lagrange'a rozwiązanie ma postać zamkniętą — **każdy region
skalowany przez stałą**:

```
P'[i,j] = P[i,j] · q₁ / p₁     dla i > j
P'[i,j] = P[i,j] · q_X / p_X   dla i = j
P'[i,j] = P[i,j] · q₂ / p₂     dla i < j
```

gdzie `p` to surowe 1X2 z `P`.

Własności (zweryfikowane numerycznie):
- 1X2 z `P'` dokładnie równe `q`
- `Σ P' = 1`
- **proporcje wyników wewnątrz regionu zachowane** — kształt rozkładu goli
  w zwycięstwach gospodarza się nie zmienia, zmienia się tylko łączna masa
- AH −0.5 z `P'` == `q₁`. Spójność z definicji.
- KL mniejsza niż dla alternatyw (np. zbicia tylko 0-0 i 1-1)

### 4.3 Kod referencyjny — `pricing/projection.py`

```python
def project_to_1x2(
    matrix: NDArray[np.float64], target: NDArray[np.float64]
) -> NDArray[np.float64]:
    """Projekcja minimum-KL macierzy wyników na zadane marginesy 1X2.

    Każdy z trzech regionów (i>j, i=j, i<j) skalowany przez stałą.
    To jest jedyne rozwiązanie minimalizujące KL(P'||P) przy tych
    ograniczeniach — nie heurystyka.
    """
    if not np.isclose(matrix.sum(), 1.0, atol=1e-9):
        raise ValueError("macierz musi sumować się do 1")
    if target.shape != (3,) or not np.isclose(target.sum(), 1.0, atol=1e-9):
        raise ValueError("target musi być wektorem 1X2 sumującym się do 1")
    if np.any(target <= 0):
        raise ValueError("target nie może mieć zer — log loss eksploduje")

    i, j = np.indices(matrix.shape)
    regions = (i > j, i == j, i < j)
    current = np.array([matrix[r].sum() for r in regions])
    if np.any(current <= 0):
        raise ValueError(f"pusty region w macierzy: {current}")

    projected = matrix.copy()
    for region, want, have in zip(regions, target, current, strict=True):
        projected[region] *= want / have
    return projected
```

### 4.4 Pełny przepływ

```
DC ─────────▶ P (surowa macierz) ─▶ p_DC (1X2)
                    │                   │
Elo + ordinal ──────┼─────────────▶ p_Elo (1X2)
                    │                   │
                    │                   ▼
                    │        meta-model (§5) ─▶ q  (docelowe 1X2)
                    │                   │
                    ▼                   ▼
            project_to_1x2(P, q) ─▶ P'  (macierz spójna)
                                        │
                        ┌───────┬───────┼───────┬───────┐
                        ▼       ▼       ▼       ▼       ▼
                       1X2     AH      O/U    BTTS   dokładny wynik
```

**Jedno źródło prawdy dla wyceny: `P'`.** Żaden rynek nie jest liczony z
`P` ani bezpośrednio z `q`.

### 4.5 Uwaga o Over/Under — to nie jest neutralne

Projekcja przesuwa O/U. Na przykładzie ze zbiciem remisu o 7 pp:

```
Over 2.5   0.4433 → 0.4692   (+2.59 pp)
Over 1.5   0.7191 → 0.7246   (+0.56 pp)
```

Kierunek jest sensowny (DC przeszacowuje niskie remisy, więc zbicie remisów
zwiększa szansę na więcej goli), ale **wielkość 2.6 pp jest większa niż
typowa przewaga**. To musi zostać zmierzone, nie założone:

- reliability diagram O/U 2.5 **na `P` i na `P'`** — który jest lepiej
  skalibrowany?
- jeśli `P'` jest gorsze dla O/U, projekcja naprawiła 1X2 kosztem totali

W takim przypadku rozszerzeniem jest **IPF** (iterative proportional
fitting): naprzemienne skalowanie regionów 1X2 i regionów over/under do ich
skalibrowanych celów, aż do zbieżności. Zbiega do macierzy minimum-KL
spełniającej oba zestawy ograniczeń — dalej jedna spójna macierz. **Nie
teraz.** Najpierw zmierz, czy jest potrzebne. Wymaga osobnego modelu
kalibracji O/U, czyli kolejnych parametrów i kolejnej okazji do przeuczenia.

---

## 5. Stacking — jak łączyć DC i Elo bez przeuczenia

### 5.1 Poziomy, od najprostszego

**Poziom 0 — ustalone z góry, zero parametrów.** Dwa warianty, oba
raportuj jako baseline:

```
arytmetyczny:  q = ½·p_DC + ½·p_Elo
geometryczny:  q ∝ sqrt(p_DC · p_Elo),  renormalizowane
```

Mieszanka arytmetyczna dwóch skalibrowanych prognoz jest systematycznie
**niedopewna** (spłaszcza w stronę środka) — to znana własność puli
liniowej. Geometryczna tego nie ma.

**Poziom 2 — log-liniowa pula z wyrazem wolnym. Wariant główny.**

```
s_k = a · log p_DC(k) + b · log p_Elo(k) + c_k      k ∈ {1, X, 2},  c₂ = 0
q(k) = exp(s_k) / Σ_j exp(s_j)
```

Cztery parametry: `a, b, c₁, c_X`.

- `a = b = ½, c = 0` → dokładnie pula geometryczna 50/50. **To jest prior.**
- `a + b > 1` → wyostrzenie (model za mało pewny siebie), `< 1` → spłaszczenie
- `c_X` bezpośrednio koryguje stronniczość remisów — dokładnie ten błąd,
  który zdiagnozowałeś

Funkcja celu z regularyzacją L2 w stronę prioru:

```
L(a,b,c) = −Σ_m log q_m(y_m) + λ · [ (a−½)² + (b−½)² + c₁² + c_X² ]
```

`λ` ustal z góry (np. `λ = 5` przy sumie log loss po ~600+ meczach — słabe,
działa głównie jako stabilizator w pierwszych sezonach). **Nie strój λ na
wyniku OOS.**

`p_DC` i `p_Elo` są silnie skorelowane, więc `a` i `b` osobno będą słabo
zidentyfikowane. To nie przeszkadza w predykcji; regularyzacja to
stabilizuje. Nie interpretuj pojedynczych wag.

`p_DC` bierzemy z **surowej** macierzy `P`, bez osobnej kalibracji DC.
Jedna warstwa kalibracji (meta-model), nie dwie nałożone na siebie.

### 5.2 Walk-forward zagnieżdżony — tu się ludzie przewracają

Klasyczny przeciek w stackingu: meta-model uczy się na predykcjach modeli
bazowych **na ich własnym zbiorze treningowym**. Tam modele bazowe są
przeuczone i zbyt pewne siebie, więc meta-model uczy się im nadmiernie ufać.

**Meta-model wolno trenować wyłącznie na predykcjach OOS modeli bazowych.**

Dobra wiadomość: masz je już zapisane. Walk-forward z kroku 3 i ewaluacja
DC wyprodukowały dla każdego sezonu `s` predykcje z modeli dopasowanych na
sezonach `< s`. Wystarczy je ponownie użyć:

```
dla każdego sezonu testowego S:
    meta_train = { (p_DC(m), p_Elo(m), y(m)) : m ∈ sezon s, s < S,
                   s ≥ pierwszy_sezon_OOS }
    jeśli |meta_train| < 500:
        q_S = poziom 0 (geometryczny)           # burn-in meta-modelu
    w przeciwnym razie:
        θ_S = fit_meta(meta_train)
        q_S = meta(p_DC(S), p_Elo(S); θ_S)
```

Dlaczego to jest szczelne: każda predykcja bazowa dla sezonu `s` pochodzi z
modelu dopasowanego na sezonach `< s`. Meta-model dla `S` widzi tylko
sezony `< S` i ich znane wyniki. Nic z `S` ani z przyszłości.

**Warunek konieczny:** hiperparametry modeli bazowych (ξ w DC, K w Elo)
również muszą być dobrane walk-forward. Jeśli ξ zostało dobrane na całym
zbiorze, predykcje bazowe nie są naprawdę OOS i cała konstrukcja przecieka.
Zweryfikuj przed startem.

Burn-in meta-modelu kosztuje ~2 sezony z ewaluacji. To jest cena poprawności.

### 5.3 Dlaczego to nie przeuczy

Cztery parametry na ~2500 meczów. Przeuczenie w tej skali wymagałoby
aktywnego wysiłku. Prawdziwe ryzyko przeuczenia leży gdzie indziej:

- **w liczbie wypróbowanych wariantów**, nie w parametrach modelu —
  każdy wypróbowany i odrzucony wariant to decyzja podjęta na danych
- **w oglądaniu zbioru testowego między iteracjami** — stąd lockbox (§2)

Reguła: **poziom 2 jest zadeklarowany z góry jako wariant główny.** Poziom 0
raportujemy jako baseline. Nie wybieramy „najlepszego z kilku" po wyniku
testowym. Jeśli poziom 2 nie jest lepszy od poziomu 0 — raportujemy to
uczciwie i używamy poziomu 0.

---

## 6. Nowa bramka jakościowa

Wszystko liczone na **zbiorze deweloperskim**, różnice sparowane, CI
klastrowe po sezonach.

**G1 — spójność (testy jednostkowe, muszą przejść):**
- `AH −0.5` z `P'` == `q₁` z dokładnością 1e-12
- `AH +0.5` z `P'` == `q₁ + q_X`
- suma każdego rynku == 1

**G2 — 1X2 nie gorsze od Elo:**
- `Δ(q − Elo)` punktowo ≤ 0, a CI nie wskazuje na istotne pogorszenie.
  Stacking zawiera Elo — jeśli jest gorszy, to jest błąd.

**G3 — kalibracja remisów naprawiona:**
- żaden koszyk reliability diagramu `P(X)` z `|z| > 3`
- raportuj koszyk `[0.30, 0.35]` jawnie, przed i po

**G4 — Over/Under skalibrowane (to jest właściwy cel kroku 4):**
- reliability diagram O/U 2.5 na `P'`, żaden koszyk z `|z| > 3`
- kalibracja Coxa: regresja logistyczna `y_over ~ logit(p_over)`,
  nachylenie w CI zawierającym 1, wyraz wolny w CI zawierającym 0
- porównanie z tym samym na `P` — który lepszy?

**G5 — rynek, jeśli dane pozwalają:**
- sprawdź, czy `POL.csv` z football-data ma kursy O/U 2.5 lub AH (główne
  ligi mają `P>2.5`, `P<2.5`, `PAHH`, `PAHA`; pliki „extra" mogą ich nie
  mieć). Jeśli są — luka LL O/U do rynku po Shinie. Jeśli nie — zapisz to
  jako kolejny argument za pollerem kursów.

**Dopiero po G1–G4:** jednorazowa ewaluacja na lockboxie, raportowana
obok wyników deweloperskich.

---

## 7. Testy — minimum

**Projekcja**
- `test_projection_hits_target_exactly`
- `test_projection_preserves_within_region_ratios`
- `test_projection_sums_to_one`
- `test_projection_is_identity_when_target_equals_current`
- `test_projection_min_kl_vs_alternative` — KL projekcji < KL zbicia tylko
  0-0/1-1 (dowód, że to nie heurystyka)
- `test_ah_minus_half_equals_home_win_after_projection`
- `test_ah_zero_equals_draw_no_bet_after_projection`
- `test_projection_rejects_zero_target_and_empty_region`

**Meta-model**
- `test_meta_prior_equals_geometric_pool` — przy `λ → ∞` wynik == pula
  geometryczna 50/50
- `test_meta_outputs_sum_to_one`
- `test_meta_recovers_draw_bias` — dane syntetyczne z celowo zawyżonymi
  remisami w `p_DC`; meta-model musi dać `c_X < 0`

**Zagnieżdżony walk-forward — test trucizny dla stackingu**
- `test_meta_never_sees_current_or_future_season` — wstrzyknij absurdalne
  wyniki do sezonu `S` i późniejszych; `θ_S` nie może się zmienić
- `test_meta_burn_in_uses_level0`

**Diagnostyka**
- `test_low_score_calibration_table_shape` — tabela 4×4 z SE

---

## 8. Kolejność wykonania

1. **Lockbox** — zapisz w `ROADMAP.md`, od teraz nie oglądaj.
2. **Sparowane CI** dla `DC−Elo`, `blend−Elo`, `blend−DC` na zbiorze
   deweloperskim (§1). Raportuj, zanim zaczniesz cokolwiek budować.
3. **Diagnoza remisów** (§3): tabela 4×4 niskich wyników, reliability
   remisów z podziałem na beniaminków, ρ i ξ per sezon.
4. **Naprawa u źródła**, jeśli diagnoza jest jednoznaczna (najpewniej:
   średnia prioru dla beniaminków). Przelicz DC, powtórz punkt 2.
5. `pricing/projection.py` + testy (§4, §7).
6. `models/ensemble.py` — poziom 0 i 2, zagnieżdżony walk-forward + testy.
7. **Bramka G1–G4** (§6).
8. Jednorazowo: **lockbox**.
9. `backtest-auditor` na `models/`, `pricing/`, `backtest/`. Stacking to
   nowa powierzchnia na przeciek — szczególnie §5.2.
10. Wpisy do `CONTEXT.md` §5: pułapka spójności (§4.1), pułapka stackingu
    (§5.2), przyczyna nadmiaru remisów, jeśli ustalona.
11. Powrót do `STEP4_PLAN.md` od §3 (rynki) — **wszystkie rynki liczone z
    `P'`, nie z `P`.**

---

## 9. Czego nie robić

- ❌ Nie licz żadnego rynku z surowej `P` po wprowadzeniu kalibracji 1X2.
- ❌ Nie strój ρ ręcznie pod częstość remisów.
- ❌ Nie trenuj meta-modelu na predykcjach in-sample modeli bazowych.
- ❌ Nie wybieraj wariantu meta-modelu po wyniku testowym.
- ❌ Nie strój λ regularyzacji na OOS.
- ❌ Nie oglądaj lockboxa przed końcem kroku 4.
- ❌ Nie porównuj dwóch modeli przez dwa osobne CI — tylko różnica sparowana.
- ❌ Nie dokładaj IPF z ograniczeniem O/U, dopóki nie zmierzysz, że
  projekcja 1X2 psuje totale.

---

## 10. Decyzje po diagnozie (2026-09-30, wieczór)

Poprzednia wersja tej sekcji nie trafiła na dysk (cichy błąd zapisu po
stronie mostu). Ta wersja ją zastępuje i uwzględnia raport CLI z 20:31.

### 10.0 Stan faktyczny

- **DC jest przeuczany co dzień meczowy**, nie raz na sezon: ~130 dopasowań
  na sezon, ~2.3 meczu na dopasowanie, odcięcie `kickoff < min(kickoff)`
  w grupie. Szczelne. Hipoteza „zamrożonego DC" — **obalona**.
- **Poziom goli jest w porządku.** Cała próba dev: `+0.040 [−0.021, +0.093]`,
  nieistotne. Znak skacze między sezonami.
- **Prawdziwy problem to nachylenie, nie poziom:**
  ```
  dolny kwartyl λ+μ    n=736   +0.233  [+0.161, +0.307]  ISTOTNE
  górny kwartyl λ+μ    n=736   −0.127  [−0.204, −0.055]  ISTOTNE
  koszyk P(X) ≥ 0.30   n=275   +0.314  [+0.141, +0.467]  ISTOTNE
  ```
  Tam, gdzie model przewiduje mało goli, pada ich więcej, a tam, gdzie
  dużo — mniej. Predykcje sumy goli są zbyt rozstrzelone. Wysokie `P(X)` to
  ten sam dolny kwartyl oglądany z innej strony — jedno zjawisko, nie dwa.
- **Wybór `prior_sd` skacze między krańcami siatki** (0.25 ×5, 2.00 ×4,
  0.50 ×1). Kryterium jest wzdłuż tej osi prawie płaskie. Wyjaśnienie w 10.2.

### 10.1 Jensen: NIE dodajemy `+σ²/2`

Przy wyśrodkowanym priorze poziom (`mean(log β)`, `log γ`) jest wolny, a kara
niezmiennicza względem wspólnego przesunięcia. Równanie score:
`Σ w·(λ + μ) = Σ w·(y_h + y_a)` — łączna liczba goli na treningu jest
dopasowana dokładnie, niezależnie od siły ściągania. Symulacja:

```
sd kary   mean(log β)   przewidziane   obserwowane
0.05      −0.028        2.294          2.294
0.15      −0.056        2.294          2.294
0.50      −0.080        2.294          2.294
```

Pomiar CLI to potwierdza: poziom jest w szumie. `+σ²/2` przesunęłoby
wszystko w górę o stałą — nie naprawiłoby nachylenia i pogorszyło górny
kwartyl, już przestrzelony o 0.127.

Korekta `τ` też nie jest źródłem: zachowuje rozkłady brzegowe dokładnie
(w wierszach/kolumnach 0 i 1 człony z `ρ` znoszą się), więc
`E[gole] = λ, μ` niezależnie od `ρ`.

### 10.2 Diagnoza: jedna gałka ściągania na dwa wymiary o różnej zmienności

Obróć parametryzację. Dla każdej drużyny:

```
s_i = (log α_i − log β_i) / 2      siła (kto wygrywa)
o_i = (log α_i + log β_i) / 2      otwartość (ile goli w jej meczach)
```

Wtedy dla meczu `i` (dom) – `j` (wyjazd):

```
log λ + log μ = 2·(o_i + o_j) + 2c + g      ← suma goli: TYLKO otwartość
log λ − log μ = 2·(s_i − s_j) + g           ← różnica: TYLKO siła
```

Obecna kara ściąga `log α` i `log β` z tym samym `sd`. To jest dokładnie
równoważne ściąganiu `s` i `o` z **tym samym** `sd`.

Ale drużyny w lidze różnią się **siłą** dużo, a **otwartością** mało.
Jedno `sd` dobrane pod siłę prawie nie ściąga otwartości → oszacowania `ô`
są zdominowane przez szum → przewidywana suma goli jest za bardzo
rozstrzelona → **nachylenie < 1, z dokładnie tym wzorem znaków, który
zmierzyłeś.**

Zmniejszenie wspólnego `sd` naprawia sumy, ale nadmiernie ściąga siłę →
gorsze 1X2 i **wracają zawyżone remisy**. Stąd płaskie i niestabilne
kryterium: jedna gałka, dwa sprzeczne cele — zysk w jednym wymiarze
zjada strata w drugim.

Symulacja (prawda: `sd(siła)=0.30`, `sd(otwartość)=0.06`, 30 replikacji
× 918 meczów testowych):

```
model                           nachyl.  dolny Q  górny Q  LL 1X2   P(X) pred / real
wspólne sd=0.50                 0.796    +0.137   −0.099   0.9162   0.217 / 0.214
wspólne sd=0.25                 0.863    +0.107   −0.058   0.9167   0.220 / 0.214
wspólne sd=0.10                 1.307    −0.054   +0.121   0.9336   0.232 / 0.214  ← 1X2 i remisy się psują
osobne  sd_s=0.35  sd_o=0.10    0.920    +0.054   −0.018   0.9161   0.216 / 0.214
osobne  sd_s=0.35  sd_o=0.06    1.035    −0.013   +0.031   0.9160   0.215 / 0.214  ← wszystko naraz
```

Wspólne `sd=0.50` odtwarza Twój wzorzec (+0.137 / −0.099 vs Twoje
+0.233 / −0.127). Osobne ściąganie naprawia sumy **bez** kosztu na 1X2
i jest odporne na błędne oszacowanie `sd_o` (1.7× za duże nadal daje 0.92).

### 10.3 Naprawa: osobne ściąganie siły i otwartości

**Parametryzacja** `(s_i, o_i, c, g)`, `s` i `o` centrowane:

```
log λ = o_i + s_i + o_j − s_j + c + g
log μ = o_j + s_j + o_i − s_i + c
kara  = Σ s_i² / (2·sd_s²)  +  Σ (o_i − mean o)² / (2·sd_o²)
```

`c` i `g` wolne, **bez kary** — nie wprowadzaj z powrotem błędu
przypiętego poziomu. `ρ` i `τ` bez zmian. To ta sama rodzina modeli co
dotąd, tylko obrócona — zmienia się wyłącznie struktura kary.

**Wybór `sd_s`, `sd_o` — empirical Bayes zamiast siatki.** Siatka wybierana
na jednym sezonie walidacyjnym jest za mało czuła (10.0). Na każdym oknie
treningowym:

1. dopasuj ze słabym priorem (`sd = 2.0` dla obu)
2. błędy standardowe `ŝ`, `ô` z odwrotności hesjanu ujemnej
   log-wiarygodności (dla Poissona z log-linkiem analitycznie: `Xᵀ W X`,
   `W = diag(λ)`); użyj `np.linalg.pinv`, bo centrowanie zostawia kierunek
   zerowy
3. `τ_s² = max(var(ŝ) − mean(SE_s²), 0.01²)`, analogicznie `τ_o²`
4. dopasuj ponownie z `sd_s = τ_s`, `sd_o = τ_o`

Wszystko z danych treningowych okna → szczelne dla walk-forward.
**Dopisz test trucizny:** zatrucie sezonu testowego nie zmienia `τ_s, τ_o`.

Raportuj `τ_s, τ_o` per sezon. Jeśli `τ_o` ląduje na podłodze, to jest
ustalenie samo w sobie: w Ekstraklasie drużyny praktycznie nie różnią się
otwartością, a przewidywana suma goli powinna być niemal stała.

**Plan B, jeśli EB okaże się kłopotliwe:** siatka 2D `sd_s × sd_o`, ale
kryterium = log-wiarygodność zsumowana po **wszystkich** sezonach
walidacyjnych przed `S`, nie tylko po ostatnim.

`ξ` ląduje na 0–0.001, czyli praktycznie bez wygaszania. Odnotuj, nie
ruszaj teraz — wrócimy po 10.3.

**Weryfikacja** (te same metryki, które już liczysz):
- nachylenie regresji zrealizowana-na-przewidzianą sumę goli: CI zawiera 1
- dolny i górny kwartyl `λ+μ`: nieistotne
- koszyk `P(X) ≥ 0.30`: nieistotny
- kalibracja remisów nadal `|z| < 2` wszędzie
- 1X2: sparowane `Δ(nowe DC − obecne DC)` nie gorsze

### 10.4 Beniaminkowie — ODŁOŻONE

Przy przeuczaniu co dzień prior działa tylko przez pierwsze 2–3 kolejki
beniaminka. Podgrupa ma `n = 138` na 10 sezonów, różnica goli
`+0.150 [−0.040, +0.330]` — nieistotna.

Argument, że filtr EV preferencyjnie wybiera błędy modelu, pozostaje
prawdziwy, ale ekspozycja jest mała, a obciążenie nieustalone. Wracamy do
tego tylko wtedy, gdy po 10.3 i ensemblu podgrupa wyjdzie istotnie.
Opcjonalnie i tanio: w Elo nowa drużyna startuje ze średniego ratingu
spadkowiczów z poprzedniego sezonu. Nie blokuje niczego.

### 10.5 Ensemble — TAK, po 10.3

Po naprawie priora mieszanki nadal istotnie biją oba modele, więc modele
wnoszą komplementarną informację. Po 10.3 DC się zmieni — **przelicz
sparowane testy** zanim zbudujesz meta-model. Poziom 2 pozostaje
zadeklarowanym wariantem głównym (§5).

Nachylenie sumy goli to dokładnie ta wielkość, od której zależy O/U. Bramka
G4 (§6) dostaje konkretny cel: nachylenie w CI zawierającym 1.

### 10.6 Kolejność

1. **10.3** — reparametryzacja `(s, o)`, EB dla `sd_s, sd_o`, testy
   (w tym trucizna dla EB). Jeden commit.
2. Diagnostyka od nowa: nachylenie, kwartyle, koszyk `P(X) ≥ 0.30`,
   kalibracja remisów, sparowane 1X2 vs obecne DC.
3. Sparowane testy DC / Elo / mieszanki.
4. §8 punkty 5–11: projekcja, poziom 2, G1–G4, lockbox, audyt.

Do `CONTEXT.md` §5 dopisz:
- prior wyśrodkowany na 0 przypinał poziom goli (2.65 → 2.22)
- `+σ²/2` przy wolnym poziomie liczy Jensena podwójnie; problemem było
  nachylenie, nie poziom
- `τ` zachowuje rozkłady brzegowe — nie ruszaj `ρ`, szukając błędu goli
- jedno `sd` dla siły i otwartości → nachylenie sumy goli < 1; osobne
  ściąganie w parametryzacji `(s, o)`
- wybór hiperparametru na jednym sezonie walidacyjnym jest za mało czuły
  (skoki po krańcach siatki)

---

## 11. Po reparametryzacji (s, o) i EB (2026-09-30, 21:09)

### 11.0 Stan (commit fb9ec10, pytest 342/342)

- `τ_s ≈ 0.13–0.14`, `τ_o` na podłodze 0.01 w 5 z 10 sezonów (wszystkie
  wczesne okna), 0.034–0.051 w pozostałych. Stosunek `τ_s/τ_o` 2.7–13.7 —
  hipoteza §10.2 potwierdzona z danych.
- **2019/20 zdegenerowany:** wybrane `ξ = 0.008` (pół-okres 87 dni) →
  mała efektywna próba → oba `τ` na podłodze → model prawie stały →
  LL tego sezonu 1.0243 → 1.0525.
- Kwartyle `λ+μ` i poziom goli: nieistotne. Kalibracja remisów: `|z| < 2`
  we wszystkich ocenialnych koszykach.
- Nachylenie sumy goli `1.21 [0.31, 1.80]` — CI zawiera 1, ale przy
  `r ≈ 0.07` regresja nie ma dźwigni. **Kryterium bez mocy.**
- Sparowane 1X2: nowe DC − stare DC `+0.0026 [−0.0038, +0.0097]`
  nieistotne; cały wzrost robi 2019/20 (+0.0282 w tym sezonie).

### 11.1 Kompresja sum goli jest w większości prawidłowa — NIE cofamy jej

Obawa „model przewiduje 2.28–3.06 przy rzeczywistym sd = 1.63, więc nie ma
zdania" porównuje złe wielkości. **Rozrzut predykcji porównuje się z
rozrzutem PRAWDZIWEJ oczekiwanej sumy goli, nie zrealizowanej** — ta druga
to niemal w całości szum Poissona.

Z liczb raportu CLI (`cov = r · sd(pred) · sd(Y)`, `nachylenie = cov / var(pred)`):

```
PRZED   cov = 0.0254   nachylenie = 0.37   predykcje 2.7× za szerokie
PO      cov = 0.0100   nachylenie = 1.21   predykcje 1.2× za wąskie (nieistotne)
```

Dekompozycja wariancji dla Poissona, `var(Y) = E[T] + var(T)`:

```
var(Y) = 2.666   E[Y] = 2.647   →   var(T) ≈ 0.019   (SE ≈ 0.075)
sd prawdziwej oczekiwanej sumy goli:  ~0.14   (górna granica ~0.4)
przewidywalna część wariancji goli:   <1%     (najwyżej ~6%)
sufit korelacji predykcja–wynik:      ~0.08   (najwyżej ~0.25)    my: 0.067
```

Symulacja O/U 2.5 przeciw dobrze poinformowanemu, ale zaszumionemu bukowi
(marża 6%, próg EV 3%):

```
model                    sd P(over)  zakładów/1000   ROI
PRZED (nachyl. 0.37)       6.4 pp        377        −3.7% ±0.2
PO    (nachyl. 1.21)       2.2 pp        164        +0.1% ±0.4
PO rozciągnięte ×1.2       2.7 pp        156        +0.4% ±0.4
idealny (zna sygnał)       3.5 pp         36        +4.7% ±0.9
```

„Więcej zdania" = więcej zakładów, które tracą. Przewaga na totalach nie
bierze się z szerszych predykcji, tylko z **lepszej informacji niż buk**,
i przychodzi rzadko. **Nie luzujemy ściągania, żeby model „miał opinię".**

### 11.2 Poprawka A: wybór `ξ` — kryterium z wielu sezonów (Plan B)

Kryterium = suma log-wiarygodności goli po **wszystkich** sezonach
walidacyjnych przed `S`, każdy oceniany modelem dopasowanym wyłącznie na
sezonach wcześniejszych od niego. Nie ostatni sezon w pojedynkę. To ta sama
lekcja, co przy `prior_sd`: jeden sezon walidacyjny ma za mało sygnału.

Wydajność: `LL(V, ξ)` — log-wiarygodność goli sezonu `V` z walk-forwardu
(refit per kolejka) przy danym `ξ` — **nie zależy od `S`**. Policz ją raz
dla każdej pary (sezon, `ξ` z siatki), zcache'uj, a wybór dla `S` to
`argmax_ξ Σ_{V<S} LL(V, ξ)`. Bez przecieku: każde `LL(V, ξ)` powstało z
danych sprzed kolejnych kolejek `V`, a wszystkie `V` leżą przed `S`.

Oczekiwane: `ξ` się stabilizuje (8/10 sezonów i tak wybrało 0), 2019/20
przestaje się degenerować, sparowane 1X2 odzyskuje wartość punktową.
Rozszerz istniejący test trucizny wyboru hiperparametrów na nowe kryterium.

### 11.3 Poprawka B: estymator `τ` — marginalna wiarygodność zamiast momentów z podłogą

Dla `θ ∈ {s, o}` (centrowanych) przyjmij `θ̂_i ~ N(0, SE_i² + τ²)` i
maksymalizuj:

```
ℓ(τ) = −½ Σ_i [ log(SE_i² + τ²) + θ̂_i² / (SE_i² + τ²) ]  +  log τ
```

- Ważenie precyzją jest wbudowane: drużyny z krótką historią ważą mniej.
- `+ log τ` to prior gamma(2, λ→0) odsuwający od zera (Chung i in. 2013):
  poza okolicą zera praktycznie nie wpływa na wynik, a **nigdy nie zwraca 0**.
- `scipy.optimize.minimize_scalar(bounds=(1e-4, 1.0), method="bounded")`.
- **Usuń podłogę 0.01.**

Weryfikacja (4000 replikacji, 22 drużyny o heterogenicznych SE):

```
prawdziwe τ   momenty+podłoga: średnio / na podłodze   marg.lik+log τ: średnio / min
0.00          0.019 / 59%                                0.026 / 0.013
0.04          0.037 / 20%                                0.043 / 0.013
0.06          0.056 /  4%                                0.060 / 0.016
0.13          0.128 /  0%                                0.129 / 0.053
```

Przy wartościach, które mają znaczenie (0.04–0.13), nowy estymator jest
praktycznie nieobciążony i nigdy się nie zapada. Przy prawdziwym zerze daje
~0.026 — lekkie zawyżenie, nieszkodliwe przy tej skali.

**Bezpiecznik:** jeśli `τ_s < 0.05` → `raise` z diagnostyką. Zerowa
zmienność siły drużyn przeczy wszystkiemu, co wiemy (Elo pokazuje duże
różnice) — to jest awaria estymacji, nie ustalenie. Głośno, nie po cichu.

**Uwaga — pokusa przecieku.** CLI zaproponowało sprawdzenie, czy `τ_o`
z ostatnich okien (~0.05) nie jest bliższe prawdzie dla wczesnych. **Nie
wolno go użyć dla wcześniejszych sezonów** — to informacja z przyszłości.
Każde okno ma swój `τ` wyłącznie z własnych danych. Lepszy estymator jest
właściwą drogą, nie pożyczanie wartości z późniejszych okien.

Korekta `τ` DC pomijana w przybliżeniu Fishera ma znaczenie marginalne
(dotyka czterech komórek). Główne źródło problemu to nieważony estymator
momentów i obcięcie.

### 11.4 G4 — nowa definicja

Nachylenie liczone względem **wyniku** było złym wyborem przy `r ≈ 0.07` —
CI obejmuje prawie wszystko. Ten sam test da się jednak zrobić z mocą, jeśli
zamiast zrealizowanej liczby goli (szum Poissona, sd 1.63) użyć celu o
wielokrotnie mniejszym szumie: **sumy goli implikowanej z kursów 1X2
Pinnacle**, które już mamy dla sezonów dev.

Uzasadnienie (własność wieży): jeśli nasza predykcja jest skalibrowana przy
naszej informacji, a rynek na zamknięciu wie co najmniej tyle co my, to
`E[T_rynek | T_nasze] = T_nasze` — nachylenie regresji `T_rynek` na
`T_nasze` wynosi 1. Za szerokie predykcje dają nachylenie < 1, za wąskie > 1.
Szum w zmiennej objaśnianej nie obciąża nachylenia.

Weryfikacja symulacyjna (sd prawdziwej sumy ~0.14, słaby sygnał, szum Shina
0.004, 20–30 replikacji po 800 meczów, SE przeskalowane do n = 2944):

```
nasz model / warunek                    nachylenie   SE (iid)
skalibrowany                               1.00       ~0.015
za szeroki ×2.7  (jak „PRZED")             0.37       ~0.005
za wąski ×0.8                              1.25       ~0.018
szum Shina ×2                              0.99       ~0.022
ρ rynku −0.15, odwracamy z −0.08           0.93       ~0.014
ρ rynku  0.00, odwracamy z −0.08           1.11       ~0.013
```

Błąd standardowy ~20× mniejszy niż przy nachyleniu względem wyniku
(0.015 vs 0.33, oba iid). Niezgodność formy funkcyjnej (inne `ρ` u buka)
przesuwa nachylenie o ok. ±10% — stąd szeroki pas akceptacji.

**Bramka:**

- **(a)** reszty kwartyli `λ+μ` i poziom: nieistotne — **spełnione**
- **(b)** reliability `P(Over 2.5)` z macierzy, po koszykach: bramka
  `|z| < 3`; koszyki z `2 ≤ |z| < 3` raportowane, bez roli bramki
  (koszyki z < 5 klastrami: n/d). Korekta po raporcie z 21:56: próg
  `|z| < 2` przy 4–6 koszykach zatrzymywałby skalibrowany model w 17–25%
  przypadków (porównania wielokrotne); `|z| < 3` jak w G3 z §6.
- **(c)** nachylenie `T_rynek` na `T_nasze`, sezony dev, CI klastrowe po
  sezonach:
  - `T_rynek = λ_m + μ_m`, gdzie `(λ_m, μ_m)` rozwiązuje
    `P_DC(1; λ_m, μ_m, ρ) = q_1` i `P_DC(X; λ_m, μ_m, ρ) = q_X`;
    `q` = Shin z zamknięcia Pinnacle, `ρ` = `ρ` naszego modelu z tej
    kolejki, macierz z **tej samej** funkcji co w modelu
  - **zalicza:** wartość punktowa w `[0.8, 1.5]` **i** połowa szerokości
    CI `≤ 0.3`. Szerszy CI = test bez mocy → stop i raport, nie „zaliczone"
  - asymetria pasa jest celowa: za szeroko kosztuje dużo (fałszywe
    zakłady, −3.7% w §11.1), za wąsko mało (pominięte okazje)
  - kontrola odporności: powtórz z `ρ = 0`; różnica nachyleń > 0.15 → zgłoś
  - raportuj też `sd(T_rynek)`, `sd(T_nasze)`, korelację i liczbę meczów,
    których nie udało się odwrócić
- **(d)** to samo dla remisów: `q_X` rynku na nasze `P(X)` — raportowane,
  **bez** roli bramki (odpowiada na „63% predykcji w jednym koszyku")
- **(e)** czy `POL.csv` ma kursy O/U 2.5 — jeśli tak, dodatkowo `P(over)`
  rynku po Shinie na nasze; jeśli nie (dla „extra leagues" najpewniej nie),
  zapisz to — bezpośredni benchmark totali czeka na poller
- **(f)** nachylenie względem wyniku raportowane z CI, **bez** roli bramki

Zasady: kursy zamknięcia służą tu **wyłącznie diagnostyce** — nie są cechą,
ceną wejścia ani celem strojenia (reguły 7 i 19 nienaruszone). Wynik G4 nie
jest zaproszeniem do „dokalibrowania" DC — obowiązuje §11.5. Jeśli (c) nie
zalicza: stop i raport.

Implementacja: `backtest/market_benchmark.py`,
`implied_goal_rates(q1, qx, rho) -> tuple[float, float]` —
`scipy.optimize.least_squares` na `(log λ, log μ)`, stały start
`(log 1.4, log 1.1)`, tolerancje 1e-12; residuum > 1e-7 → `NaN` (nigdy
cicha liczba). Sprawdzone: siatka 168 przypadków `λ ∈ [0.4, 3.8]`,
`μ ∈ [0.3, 2.8]`, `ρ ∈ [−0.15, 0.05]` odtwarza się ze stałego startu z
błędem ~1e-10. Testy: round-trip na tej siatce; niespójne `q`
(`q_1 + q_X > 1`) → `NaN`.

### 11.5 Reguła stopu dla DC

Zbiór dev posłużył dziś do co najmniej sześciu rund decyzji (środek
prioru, reparametryzacja, EB, podłoga, `ξ`, …). Każda kolejna poprawka
dopasowuje strukturę modelu do tych konkretnych sezonów.

**Po 11.2 i 11.3 zamrażamy strukturę DC.** Żadnych kolejnych poprawek DC
przed ensemblem, projekcją i jednorazową ewaluacją lockboxa. Nowe pomysły
na DC trafiają na listę „po lockboxie". Beniaminkowie (§10.4): nadal
odłożone.

### 11.6 Kolejność

1. **11.2** i **11.3** — osobne commity, testy (w tym trucizna dla
   wielosezonowego wyboru `ξ` i nowego estymatora `τ`).
2. Diagnostyka: tabela `τ_s, τ_o, ξ` per sezon, `sd` przewidywanej sumy
   goli, nachylenie z CI, kwartyle, kalibracja remisów, sparowane 1X2
   (nowe DC vs obecne DC, vs Elo).
   Bootstrap klastrowy przy < 5 klastrach zwraca `NaN`, a raport pisze
   „n/d (k klastrów)" — nie liczbę. Koszyk `P(X) ≥ 0.30` w raporcie 21:09
   dał CI zerowej szerokości i z ≈ −9e14; to ma się nie dać wydrukować.
3. **G4** wg 11.4 — nowy moduł `backtest/market_benchmark.py` z testami,
   osobny commit.
4. Jeśli G4 przechodzi → **zamrożenie DC** → §8 punkty 5–11 (projekcja,
   poziom 2, G1–G4, lockbox, audyt).

Do `CONTEXT.md` §5 dopisz:
- rozrzut predykcji sumy goli porównuje się z rozrzutem prawdziwej
  oczekiwanej sumy (~0.14), nie zrealizowanej (1.63 — szum Poissona)
- szerokie predykcje totali = fałszywe sygnały na O/U (symulacja: −3.7%)
- nachylenie względem wyniku nie ma mocy przy `r ≈ 0.07`; kalibrację
  słabego sygnału testuje się względem celu z rynku (suma implikowana z
  1X2 Pinnacle, własność wieży) — SE ~20× mniejszy
- estymator momentów z podłogą zapada się w małych oknach; sprzężenie
  `ξ` × EB w 2019/20
- wybór hiperparametru na jednym sezonie walidacyjnym — ta sama pułapka
  po raz drugi

### 11.7 Ujednolicenie bramek (po raporcie z 21:56)

- **G4 z §6 jest w całości zastąpione przez §11.4.** Stosowane dwa razy:
  teraz na DC (`P`), a w §8 pkt 7 na `P'` po projekcji i stackingu.
  Kalibracja Coxa względem wyniku — raportowana, bez roli bramki (ten sam
  brak mocy co nachylenie).
- **G5 rozstrzygnięte:** `POL.csv` nie ma kursów O/U ani AH (30 kolumn,
  kursowe wyłącznie 1X2: PSC, MaxC, AvgC, BFEC, B365C). Bezpośredni benchmark
  totali możliwy tylko na danych zbieranych od teraz — `COLLECTOR_PLAN.md`
  (The Odds API: Pinnacle `totals` dla Ekstraklasy). Nie blokuje kroku 4.

### 11.8 Reguła decyzyjna po przebiegu diagnostycznym — spisana PRZED wynikiem

Stosuj mechanicznie, w tej kolejności. Pierwszy spełniony warunek „stop"
kończy procedurę.

1. Bezpiecznik `τ_s` odpalił → **stop**. Raport: okno, `ξ`, SE, liczba
   drużyn w oknie.
2. G4(c) bez mocy (połowa szerokości CI > 0.3) albo > 5% meczów z kursem
   Pinnacle, których nie udało się odwrócić → **stop**. Mecze bez kursu to
   osobna kategoria — policz je, ale nie wliczaj do tych 5%.
3. G4(c) poza `[0.8, 1.5]` → **stop** (< 0.8: za szeroko; > 1.5: za wąsko).
4. G4(b): koszyk `P(Over 2.5)` z `|z| ≥ 3` przy ≥ 5 klastrach → **stop**.
5. Nowe DC istotnie gorsze od fb9ec10 w sparowanym 1X2 (całe CI > 0) →
   **stop**.
6. Wszystko powyżej zielone → **DC zamknięte.** Zapisz w `ROADMAP.md` datę,
   commit i nachylenie G4(c) z CI.

Granice są twarde: 1.51 to „stop", nie „prawie zaliczone". Wynik tuż przy
granicy to powód do rozmowy, nie do przesunięcia granicy po fakcie.

Różnica nachyleń G4(c) dla `ρ` modelu i `ρ = 0` > 0.15 — raport, nie stop.

**Po zamknięciu DC:** priorytet ma kolektor (`COLLECTOR_PLAN.md`, Faza 1a),
bo dane, których nie zbieramy, przepadają, a model może poczekać bez straty.
§8 pkt 5–7 (projekcja, stacking, bramki) — po uruchomieniu Fazy 1a.

**Na przyszłość (infrastruktura, nie struktura DC):** wynik diagnostyki
zapisuj do pliku w trakcie przebiegu (`reports/diag_<commit>.json`), a cache
`LL(V, ξ)` na dysk z kluczem = hash commita + konfiguracja DC; inny commit →
cache unieważniony. Test: wynik z cache == wynik bez cache na małym
podzbiorze. Przebieg ubity razem z powłoką nie może kosztować kolejnych
kilkudziesięciu minut.

### 11.9 Poprawka C: drużyny bez informacji w oknie i SE bez `pinv` (2026-10-01)

**Zdarzenie.** Bezpiecznik `τ_s < 0.05` odpalił przy `ξ = 0.008`: w oknie
obejmującym 10 sezonów 12 z 30 drużyn miało wagi bliskie zera (ostatni mecz
w lidze lata temu), ich SE eksplodowało, macierz się zdegenerowała.
Bezpiecznik zrobił dokładnie to, do czego go postawiliśmy.

**Mechanizm — potwierdzony symulacją.** SE liczone z `pinv(XᵀWX)` bez
prioru. Drużyna bez meczów w ważonym oknie to kierunek o wartości własnej
~1e-7: `pinv` go odwraca (jest powyżej progu odcięcia) i zwraca wariancję
rzędu 1e7. Przy takim uwarunkowaniu błąd numeryczny wektorów własnych
rozlewa tę wariancję na wszystkie drużyny — SE **aktywnych** drużyn rośnie
z ~0.2 do ~6. Marginalna wiarygodność dostaje śmieci i ląduje na granicy
przedziału: u CLI w dole (bezpiecznik), w mojej symulacji w górze (1.0).
Kierunek zależy od szczegółów implementacji; mechanizm jest jeden.

Symulacja: 30 drużyn, 16 w sezonie, 3 spadki i 3 awanse rocznie, 10 sezonów,
cięcie po 10. kolejce ostatniego sezonu, 12 lig na wiersz. „Stara ścieżka" =
wszystkie drużyny + `pinv(XᵀWX)`. „Poprawka" = punkty 1–3 niżej.

```
ξ       prawdziwe   τ_s stara ścieżka   τ_s poprawka      SE(s) dobrze zmierzonych         cond XᵀWX*
        sd(s)       średnio / min       średnio / min     stara: mediana / poprawka: max   stara ścieżka
0.000   0.125       0.127 / 0.102       0.127 / 0.102     0.054 / 0.14                     1.6e2
0.002   0.115       0.110 / 0.064       0.093 / 0.050     0.108 / 0.32                     7.2e2
0.004   0.113       0.080 / 0.066       0.088 / 0.050     0.256 / 0.37                     1.1e4
0.008   0.100       1.000 / 1.000       0.110 / 0.068     6.1   / 0.39                     6.4e6
* bez dwóch dokładnych kierunków zerowych (wspólne przesunięcie s; o względem c)
```

Nawet maksymalne SE po poprawce jest przy `ξ = 0.008` piętnaście razy
mniejsze niż mediana na starej ścieżce.

Dwa wnioski poza samą naprawą:
1. Winowajcą jest `pinv` na macierzy bez prioru. Hesjan z priorem, rzutowany
   na kontrasty centrowane, liczy się poprawnie nawet z martwymi drużynami.
2. **Próg 0.05 był za ciasny.** Poprawny estymator przy prawdziwym τ ≈ 0.11
   i małej efektywnej próbie schodzi do 0.050 (wiersze 0.002 i 0.004).
   Prawdziwa sygnatura awarii jest numeryczna — łapiemy ją wprost.

**Poprawka.** To naprawa błędu numerycznego, nie kolejna runda modelowania:
§11.5 nie jest naruszone, reguła decyzyjna §11.8 zostaje bez zmian (poza
definicją bezpiecznika w pkt 4).

1. **Dwa progi informacji, ustalone z góry, nie strojone:**
   `n_eff,i = Σ_{m ∋ i, t_m < cięcie} exp(−ξ·(cięcie − t_m))`.
   - `n_eff,i ≥ 0.5` → drużyna wchodzi do dopasowania. Poniżej: brak
     informacji w oknie, mecze z jej udziałem wypadają z wiarygodności.
   - `n_eff,i ≥ 5` → drużyna wchodzi do estymacji `τ` (marginalna
     wiarygodność liczona tylko po dobrze zmierzonych).
   Raport wrażliwości dla progu `τ` = 3 i 10 — wyłącznie raport.
2. **Drużyna bez informacji w przewidywanej kolejce** (`n_eff < 0.5`, np.
   beniaminek po latach albo debiutant przed pierwszym meczem) → `s = 0`,
   `o = 0`, czyli średnia ligi — istniejący fallback. Policz takie mecze w
   raporcie. Beniaminkowie (§10.4): nadal odłożone.
3. **Bez `pinv`.** SE z odwrotności hesjanu **z priorem** przez Cholesky'ego,
   rzutowanej na kontrasty centrowane po zbiorze dopasowanym:
   `C·H⁻¹·Cᵀ`, `C = I − 11ᵀ/T`. Cholesky zawodzi głośno, gdy macierz nie jest
   dodatnio określona — o to chodzi. Cond `XᵀWX` raportuj w diagnostyce.
4. **Bezpieczniki — nowa definicja:**
   - numeryczny: dobrze zmierzona drużyna (`n_eff ≥ 5`) z SE(s) > 1.0
     (w symulacji poprawka daje maksymalnie 0.39, stara ścieżka 6.1);
   - statystyczny, ostatnia linia: `τ_s < 0.03` (było 0.05). Zmiana wynika z
     symulacji powyżej, nie z wyniku na dev.
5. **Siatka `ξ` a predykcja — dwie różne sytuacje:**
   - liczenie cache `LL(V, ξ)` dla kandydata: bezpiecznik → `LL(V, ξ) = −∞`
     (kandydat niedopuszczalny dla każdego `S > V`), wpis w logu z
     diagnostyką, przebieg trwa dalej. Zły kandydat to informacja, nie awaria;
   - dopasowanie z wybranym `ξ` (predykcja): bezpiecznik → `raise`, jak dotąd.
6. **Najpierw potwierdź**, gdzie odpalił bezpiecznik 2026-10-01: przy cache
   dla kandydata `ξ = 0.008` czy przy predykcji z wybranym `ξ`? Dla tego okna
   podaj: SE(s) aktywnych drużyn, cond, liczbę drużyn z `n_eff < 0.5` i `< 5`.
   Jeśli obraz jest inny niż opisany wyżej — stop i raport, zanim cokolwiek
   zmienisz.

**Testy:**
- regresja tego błędu: syntetyczna liga jak w symulacji, `ξ = 0.008`; stara
  ścieżka daje SE(s) aktywnych > 1, poprawka ≤ 0.5, a `τ_s` w [0.05, 0.25]
  przy prawdziwym 0.10;
- drużyna bez informacji w przewidywanej kolejce → fallback + licznik;
- siatka: kandydat zdegenerowany nie przerywa przebiegu i dostaje `−∞`;
  predykcja z `τ_s < 0.03` → wyjątek;
- Cholesky na macierzy nie-PD → wyjątek (żadnego cichego `pinv`);
- trucizna: progi `n_eff` w chwili `t` nie zależą od meczów po `t`.

Potem przebieg diagnostyczny od nowa → §11.8 mechanicznie.

### 11.10 Przebieg 313591a: DC zamknięte jako model 1X2 (2026-10-01, 17:40)

**Fakty** (`reports/diag_313591a.json`):
- Poprawka C działa: cond 50–1974, zero odrzuconych kandydatów `ξ`,
  `τ_s` 0.112–0.139, `τ_o` 0.020–0.039. 2019/20 wyleczony: LL 1.0277 (Elo 1.0335).
- 1X2: DC − Elo `+0.0001 [−0.0031, +0.0048]`; DC − fb9ec10
  `−0.0035 [−0.0091, +0.0006]`. Remisy: wszystkie ocenialne koszyki `|z| ≤ 2.01`.
- G4(c) totale, `ρ` modelu: nachylenie **2.21 [1.59, 2.73]**, r = 0.55,
  sd rynku 0.306 vs nasze 0.076.
- G4(c) totale, `ρ = 0`: nachylenie **1.75 [1.39, 2.15]**, sd rynku 0.257.
  Różnica nachyleń 0.46 > 0.15 — flaga odporności z §11.4.
- G4(d) remisy: `q_X` rynku na nasze `P(X)` — nachylenie **1.08 [0.94, 1.36]**,
  r = 0.61. W tym, co rynek wycenia wprost, jesteśmy skalibrowani.
- G4(b): `P(Over 2.5)` — poziom trafiony (0.489 vs 0.491), koszyki w normie,
  ale sd 0.019: prognoza prawie stała.
- G4(f) względem wyniku: 1.60 [0.76, 2.44] — bez mocy, kierunek ten sam.

**Wnioski:**
1. Reguła 2 zatrzymała przebieg słusznie, ale z niewłaściwego powodu. CI
   [1.59, 2.73] leży w całości poza pasem [0.8, 1.5] — to nie „brak mocy",
   tylko wyraźny wynik „za wąsko". Błąd w mojej definicji. **Poprawiona
   definicja:** brak mocy = CI obejmuje jednocześnie punkt w pasie i punkt
   poza nim. CI w całości poza pasem = niezaliczone (reguła 3).
2. **Kierunek jest pewny:** w obu wariantach `ρ` dolna granica CI > 1.38 —
   nasze totale są za mało rozproszone.
3. **Wielkość nie jest pewna:** 1.75 czy 2.21 zależy od `ρ` przyjętego przy
   odwracaniu. Instrument (suma goli wyprowadzona z 1X2) jest wrażliwy na formę
   funkcyjną, a remisy — które rynek wycenia wprost — wychodzą skalibrowane.
   Instrument trzeba zwalidować tam, gdzie rynek wycenia totale bezpośrednio.
4. **„Leczenie" przez strojenie odrzucone.** Podniesienie `τ_o` albo
   rozciągnięcie prognoz do rynku zaliczyłoby bramkę z definicji, ale nie
   dodałoby informacji — to dopasowanie modelu do bramki po obejrzeniu wyniku
   (§11.5). `τ_o` 0.02–0.04 to uczciwy wynik: z samych wyników prawie nie da
   się odróżnić „otwartości" drużyn. Totale skalibrowane do rynku bierzemy
   wprost z rynku — S1 zbiera totale Pinnacle.

**Decyzja — zawężamy roszczenie, nie przesuwamy bramki:**
- **DC zamknięte jako model 1X2.** Bezpieczniki zielone, remisy skalibrowane
  względem rynku, 1X2 na poziomie Elo. Totale, AH i kombinacje z naszej
  macierzy **nie** idą do wyceny.
- G4(c) zapisane jako **niezaliczone (za wąsko)**; wielkość — po walidacji
  instrumentu.
- **M2 startuje od razu**, niezależnie od walidacji.

**A. Walidacja instrumentu na Premier League (football-data, pliki głównych lig).**
Sezony z kursami zamknięcia Pinnacle 1X2 i O/U 2.5 — nazwy kolumn sprawdź w
nagłówku pliku (zamknięcie O/U najpewniej `PC>2.5` / `PC<2.5`); jeśli ich nie
ma — stop i raport. Nowy parser dla formatu głównych lig, osobny moduł;
ingest `POL.csv` bez zmian; dane do `data/raw/` z `ingested_at` i `source`.
Dla każdego meczu, w dwóch wariantach `ρ ∈ {0, mediana ρ z dopasowań DC
Ekstraklasy}`:
- `T_1x2` = `implied_goal_rates(q_1, q_X, ρ)` → λ + μ;
- `T_ou` = suma, przy której `P_DC(gole ≥ 3)` = `q_over` (Shin na rynku
  dwustronnym), ze stosunkiem λ/μ wziętym z odwrócenia 1X2.
Raport: sd(`T_1x2`), sd(`T_ou`), korelacja, nachylenie `T_ou` na `T_1x2`
(CI klastrowe po sezonach), liczba nieodwróconych.
**Kryterium (spisane przed wynikiem):** wariant jest ważny, jeśli
sd(`T_1x2`)/sd(`T_ou`) ∈ [0.8, 1.25] i korelacja ≥ 0.7.
- jest ważny wariant → nachylenie G4(c) Ekstraklasy z tego wariantu to
  zapisana wielkość kompresji;
- żaden nie jest ważny → G4(c) unieważnione jako instrument; każda wycena
  totali (BetBuilder, ROADMAP §4.3) bierze totale Pinnacle wprost, nigdy z
  samego 1X2.

**B. Rozkład na osie (Ekstraklasa, bez strojenia, z zapisanych λ, μ).**
Oś otwartości `A = log λ + log μ`, oś przewagi `B = log λ − log μ` — po
stronie modelu i po stronie rynku (z odwrócenia). Nachylenie `A_rynek` na
`A_nasze` i `B_rynek` na `B_nasze`, CI klastrowe, oba warianty `ρ`. Przy
kalibracji oba ≈ 1. Wynik służy tylko do raportu i listy „po v1.0": mówi, czy
za wąska jest otwartość, czy relacja przewaga → gole.

**C. M2 — test pokrywania, kryteria spisane przed wynikiem.**
Pula logarytmiczna Pinnacle po Shinie + DC (1X2), waga modelu dobierana
walk-forward wyłącznie na sezonach wcześniejszych; sparowana różnica log loss
(pula − sam Pinnacle), CI klastrowe po sezonach; Pinnacle jawnie jako cel
shrinkage (reguła 19). Lockbox nietknięty.
- górna granica CI < 0 → model wnosi informację ponad rynek; bramka G-M dla
  1X2 staje się możliwa;
- w przeciwnym razie → model zostaje w portfolio; jego rola pieniężna
  ogranicza się do kombinacji BetBuilder wycenianych z danych rynkowych.
Uczciwe oczekiwanie przed wynikiem: przy luce Elo − Pinnacle +0.0145 i DC ≈ Elo
waga modelu wyjdzie bliska zera.

**Po v1.0, nie teraz:** eksperymenty z otwartością — wspólny prior `(s, o)`
z korelacją, osobne wygaszanie dla `o`. Jeden, z góry zarejestrowany, i tylko
jeśli M2 pokaże wkład modelu.

**Git:** zero `git add -A` i `git add .` — wyłącznie jawne ścieżki. Przypadkowe
usunięcie pliku w commicie to typowy skutek ogólnego dodawania zmian.

### 11.11 Po M2: zakres domknięcia toru M (2026-10-01, wieczór)

**Wyniki (commity 6d0fa8c, 0208f64):**
- M2: pula − Pinnacle `+0.0015 [−0.0003, +0.0040]`; wagi modelu per sezon
  0–0.45 (mediana 0.14) — nie generalizują. Model nie wnosi informacji
  ponad rynek.
- Osie: przewaga `B` 1.21 [1.04, 1.38], r = 0.81 — prawie skalibrowana;
  otwartość `A` 3.06 [1.78, 3.95], r = 0.50, sd 0.036 vs 0.220 — tu siedzi
  cała kompresja.
- Instrument zwalidowany na Premier League (2269 meczów): oba warianty
  ważne; przy `ρ = −0.07` poziom trafiony co do tysięcznej (2.902 vs 2.902);
  instrument zawyża rozrzut o 12–21%, więc kompresja totali Ekstraklasy to
  ~1.8–2.2×.

**Konsekwencje dla §8:**
- **pkt 5 (projekcja) — skreślony.** Służyła spójnej wycenie totali i AH z
  naszej macierzy, a ta nie idzie do wyceny (§11.10, reguła 19a).
- **pkt 6–7 (stacking, G1–G4) — skreślone.** Skoro nawet pula z rynkiem nie
  wnosi informacji, stacking Elo + DC bez rynku nie ma po co powstawać.
- **pkt 8 (lockbox) — zostaje, w zawężonej formie.** Jednorazowa ocena
  zamrożonych modeli (Elo i DC z commita zapisanego w raporcie; zero zmian
  w `models/` i `features/` przed przebiegiem) na 2025/26 i 2026/27: luki
  log loss Elo − rynek, DC − rynek, DC − Elo, sparowane. Referencja:
  Pinnacle tam, gdzie jest, BFEC tam, gdzie nie — raportowane osobno
  (ROADMAP, Część II). CI: **klastry = kolejki**, bo dwa sezony to za mało
  klastrów sezonowych. W raporcie zastrzeżenie, że lockbox nie jest
  dziewiczy (ROADMAP, Część II, „Lockbox").
- **pkt 9 (audyt) — zostaje.** `backtest-auditor` na `models/`, `pricing/`,
  `backtest/` przed raportem.
- **pkt 10 (CONTEXT) — zrobione** (5.34–5.36).
- **pkt 11 (rynki z `P'`) — skreślony.** Wycena rynków wyłącznie z danych
  rynkowych: `TOR_S_PLAN.md`, ROADMAP §4.3.

Po lockboxie i audycie: raport portfolio (ROADMAP §6, M5). Krok 4 jest
wtedy zamknięty.
