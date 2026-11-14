# CONTEXT.md — projekt `valuebet`

Dokument transferowy: sesja Claude (aplikacja desktopowa) → Claude Code (CLI).
Stan na 2026-09-21. Autor projektu: Paweł.

---

## 0. Jak czytać ten dokument

**Źródłem prawdy dla kodu jest repozytorium**, nie ten plik. Repo zawiera
`CLAUDE.md`, który ładuje się automatycznie, a każdy moduł ma obszerne
docstringi po polsku wyjaśniające *dlaczego*, a nie tylko *co*.

Ten dokument zawiera to, czego w repo nie ma:
- historię decyzji i odrzuconych podejść,
- ustalenia o rynku i dostępności danych z researchu,
- **historię błędów wraz z ich matematyką** (sekcja 5) — najważniejsza
  część, bo opisuje pułapki, w które już wpadliśmy,
- brief na krok 3.

Sekcja 5 jest na tyle precyzyjna, że pozwala odtworzyć każdy moduł od
zera, gdyby kod przepadł.

Odpowiadaj po polsku. Komentarze i docstringi po polsku, identyfikatory
po angielsku. Preferowana ocena: chłodna, inżynierska, bez optymistycznych
uogólnień. Jeśli coś jest złym pomysłem — powiedz to wprost i uzasadnij
liczbami.

---

## 1. Czym jest ten projekt i czym NIE jest

### Cel

System wyszukujący zakłady o dodatniej wartości oczekiwanej (+EV) na
polskim rynku bukmacherskim:

```
model probabilistyczny → detekcja błędnej wyceny → alert na Telegram
```

**Człowiek klika ręcznie.** Bot nigdy nie składa zakładu.

Podział wartości deklarowany przez Pawła: **80% portfolio** (demonstracja
Pythona, ML, statystyki, inżynierii danych), **20% zysk** do momentu
zlimitowania konta. Ta proporcja jest istotna dla priorytetów: poprawność
metodologiczna bije zysk.

### Co zostało odrzucone i dlaczego

**Latency arbitrage / HFT.** Punktem wyjścia był wiralowy post na X o
bocie zarabiającym rzekomo 78 tys. USD w 5 dni na Polymarket przez
porównywanie cen BTC z kursami. Paweł sam ustalił, że post to scam, a
model nie przenosi się na polski rynek: brak publicznego API, sztuczne
opóźnienia przy zakładach live (bet delay), szybkie limitowanie
wygrywających kont.

**Automatyczne składanie zakładów (clicker).** Regulaminy polskich
bukmacherów zakazują zautomatyzowanego dostępu do serwisu. Sankcją bywa
zamknięcie konta z zatrzymaniem środków — ryzykujesz nie tylko limitację,
ale saldo. Scraping kursów to szara strefa, klikanie botem to
jednoznaczne naruszenie. **Nie proponuj clickerów. Nie pisz kodu
logującego się na konto bukmachera.**

**Naiwne cechy kontekstowe.** Zmiana trenera i „motywacja końcówki
sezonu" zostały świadomie odrzucone. Efekt nowego trenera jest w
literaturze ekonometrycznej w dużej mierze regresją do średniej (trenera
zwalnia się po serii porażek, a seria i tak by się skończyła). Motywacja
dotyczy ~20 meczów rocznie w jednej lidze — to nie jest cecha, to
dopasowanie szumu.

### Matematyka, która definiuje cały projekt

Polski podatek obrotowy wynosi **12% od stawki** (nie od wygranej) i jest
potrącany z góry. Efektywnie mnoży kurs przez 0,88.

```
EV = p · k · tax − 1 > 0        gdzie tax ∈ {1.00, 0.94, 0.88}
k_min = 1 / (p · tax)
```

Przy standardowym podatku iloczyn `p · k` musi wynosić minimum **1,1364**,
czyli wymagana przewaga nad rynkiem to **13,6%**.

Przełożenie surowej przewagi `e` na yield netto:

```
yield_netto = tax · (1 + e) − 1
```

| Surowa przewaga | Yield @ 0.88 | Yield @ 0.94 | Yield @ 1.00 |
|---|---|---|---|
| 3% | **−9,4%** | −3,2% | +3,0% |
| 5% | **−7,6%** | −1,3% | +5,0% |
| 13,6% | 0% | +6,8% | +13,6% |

Realistyczny sufit value bettingu pre-match na świecie (bez podatku,
przeciwko soft-bookom, z Pinnacle jako referencją) to **2–5% ROI**;
bardzo dobrzy praktycy raportują ~5,5% yield.

**Wniosek: przy podatku 12% projekt jest matematycznie niemożliwy.**
Nie trudny — niemożliwy, i trzeba to mówić wprost zamiast szukać
obejścia. Cały projekt opiera się na promocjach „gra bez podatku"
(tax = 1,00).

### Konsekwencja dla Ciebie jako asystenta

Jeśli backtest pokaże yield powyżej **~8%**, domyślnym wyjaśnieniem jest
**błąd w kodzie, nie odkrycie**. Traktuj wysoki wynik jako objaw bugu i
szukaj go, zanim pogratulujesz. To nie jest ostrożność retoryczna — to
bezpośredni wniosek z tabeli powyżej.

---

## 2. Ustalenia o rynku i danych (research, wrzesień 2026)

### Podatki

- Podatek obrotowy **12% od stawki**, bez zmian w 2026. Jeden z
  najwyższych w Europie (Niemcy 5,3%, Francja 0% dla gracza, UK 0%).
- Dodatkowo **10% od wygranej powyżej 2280 PLN** z jednego kuponu. To
  obcina ogon rozkładu — istotne, jeśli model miałby grać kursy >11.
- Projekt podniesienia podatku od wygranych do 15% został zawetowany i
  nie wszedł w życie.

### Betclic „Gra Bez Podatku 2.0" (od 19–21 maja 2026)

Promocja została zmieniona w sposób, który uderza dokładnie w value
betting:

- Do **1000 PLN sumy stawek** — pełna gra bez podatku, wszystko.
- Po przekroczeniu — kupony **SOLO obciążone 6%**, chyba że **udział
  stawek** postawionych na kwalifikujące się AKO (min. 2 zdarzenia, kurs
  ≥1,20) wynosi co najmniej 50% (§3 ust. 5 regulaminu — cytat wstępny w
  `docs/promocje.md` T4; poprawione 2026-10-02, wcześniej błędnie „50%
  kuponów”). Wtedy powrót do 0% na wszystkim. Kod od 2026-10-11 (wariant B,
  F1-P01 pkt 3) liczy udział **wyłącznie po stawkach**, jak regulamin;
  wariant „po stawkach i po liczbie kuponów” (margines Pawła z 2026-10-02)
  zostaje tylko jako raport wrażliwości strategii C. Sformułowanie „50%
  kuponów” było sprzeczne z §3 ust. 5 — nieaktualne.
- Kupony AKO są bez podatku zawsze.
- Okres rozliczeniowy: 12 miesięcy kroczących lub 5000 ostatnich zakładów.

**Dlaczego to ma znaczenie:** value betting wymaga kuponów SOLO — każdy
zakład niezależny, stawkowany osobno według Kelly'ego. Promocja jest
zaprojektowana tak, żeby wypchnąć gracza w AKO, gdzie marże się mnożą.
To celowy mechanizm ochrony przed takimi graczami.

| Tryb | Wzór | Wymagana przewaga |
|---|---|---|
| Zwykły bukmacher | p·k·0,88 | 13,6% |
| Betclic SOLO bez ratio AKO | p·k·0,94 | 6,4% |
| Betclic z ratio AKO ≥50% | p·k | >0% + marża |

**DO ZWERYFIKOWANIA przez Pawła w oryginalnym regulaminie Betclic**, nie
na portalach afiliacyjnych: czy ratio liczy się po liczbie kuponów czy po
obrocie, czy jest minimalna stawka kwalifikująca, i czy regulamin ma
klauzulę o „nadużywaniu promocji". Jeśli ratio liczy się po liczbie
kuponów, utrzymanie go kosztuje tyle, ile strata na AKO-wypełniaczach o
minimalnej stawce — o rząd wielkości mniej niż 6% od pełnych stawek.

Wybór bukmachera jest **otwarty**. Betclic to przykład, nie decyzja.
Kryterium: najniższy efektywny podatek i najniższa marża na rynkach,
które model faktycznie wycenia.

### Dostępność danych — stan faktyczny

**FBref stracił licencję Opta w styczniu 2026.** Zaawansowane statystyki
(xG) nie są już aktualizowane. Dane historyczne zostały, nowe nie
przychodzą. To unieważnia standardową radę „weź xG z FBref przez
soccerdata".

- **Understat** — tylko top 5 lig + RPL. **Bez Polski.**
- **xG dla Ekstraklasy** — brak dobrego darmowego źródła.
- **xG dla 1. ligi i niżej** — nie istnieje. Proxy: strzały, strzały
  celne. To realna granica projektu, nie problem do obejścia.
- **Sofascore / FotMob** — mają xG dla szerokiego zbioru lig i składy
  ~1h przed meczem, przez wewnętrzne API. Formalnie scraping jest
  niezgodny z ich ToS. Decyzja należy do Pawła — nie udawaj, że to
  zwykłe publiczne API.
- **API-Football** (api-sports.io) — darmowy plan **100 zapytań/dobę**,
  endpointy `LineUps` i `Injuries`, pokrywa Ekstraklasę. Darmowy plan ma
  ograniczone dostępne sezony. Pod to jest napisany kolektor.
- **football-data.co.uk** — kursy zamknięcia, Polska w „extra leagues".
  Główne źródło dla kroku 3.
- **90minut.pl** — najlepsza baza polskiej piłki, także niższe ligi.
- **ClubElo** — darmowe API z ratingami, punkt odniesienia dla Elo.

### Klasy dostępności danych — fundament metodologiczny

| Klasa | Co to jest | Rekonstruowalne wstecz? | Gdzie używać |
|---|---|---|---|
| **A** | Elo, forma, dni odpoczynku, atut boiska | **tak, w pełni** | backtest na 10 sezonach |
| **B** | kontuzje, składy, zmiana trenera, wartości rynkowe | **NIE** | tylko okres zebrany samodzielnie |
| **C** | przewidywane składy, newsy przedmeczowe | nie istnieją | tylko live, nigdy w backteście |

**Kluczowe ustalenie:** historycznych danych o kontuzjach i składach z
poprawnym znacznikiem czasu obserwacji **nie da się zdobyć**.
Transfermarkt ma historię urazów, ale to rekonstrukcja retrospektywna:
daty końca korygowane po fakcie, drobne urazy pomijane, a to czy uraz
odnotowano koreluje z tym, jak ważny okazał się zawodnik. Użycie tego w
backteście to look-ahead bias, tylko dobrze ukryty.

**Historia kontuzji z Transfermarktu NIE JEST klasą B.** Jeśli pojawi się
pokusa „przecież mamy daty urazów" — odpowiedź brzmi nie.

Jedyne źródło wolne od tego problemu to archiwum budowane od teraz.
Stąd priorytet kolektora: **każdy dzień bez działającego kolektora to
dzień danych treningowych, których nigdy nie odzyskasz.**

Model produkcyjny to A+B. Model, który realnie zbacktestujesz na
sensownej próbie — przez najbliższy rok to samo A.

### Trzeźwe zastrzeżenie o wartości cech kadrowych

Potwierdzone składy wychodzą godzinę przed meczem. Rynek je widzi i
wycenia: Pinnacle rusza linię w kilkadziesiąt sekund, soft book kopiuje w
kilka minut. Przewaga z kontuzji istnieje tylko w oknie między tym, kiedy
Ty wiesz, a kiedy wie rynek — pre-match to okno jest bliskie zeru tam,
gdzie rynek patrzy.

Czyli: cechy kadrowe mają największą wartość dokładnie tam, gdzie dane są
najtrudniejsze do zdobycia. To nie przypadek, to ten sam argument o
efektywności rynku z innej strony.

### Priorytetyzacja cech

| Cecha | Wpływ na log loss | Koszt | Werdykt |
|---|---|---|---|
| Elo / siła drużyny | duży | niski | fundament, najpierw |
| Atut własnego boiska | duży | trywialny | must-have |
| Beniaminek / spadkowicz | średni w Ekstraklasie | niski | tak |
| Rolling strzały, SOT | średni | niski | proxy za xG |
| Rolling xG | średni-duży | wysoki (brak źródła) | tylko jeśli zdobędziesz |
| Dni odpoczynku, kongestia | mały ale realny | niski | tak, tanie |
| Dostępność składu | potencjalnie średni | bardzo wysoki | dopiero po baseline |
| Zmiana trenera | ≈ 0 | średni | **pomiń** |
| Motywacja / stawka meczu | ≈ 0, ryzyko overfitu | wysoki | **pomiń** |

### Twarde ograniczenie próby

Ekstraklasa to 18 drużyn × 34 kolejki = **306 meczów na sezon**.
Dziesięć sezonów ≈ **3060 obserwacji**.

Przy 30 cechach i 3000 wierszy, w dziedzinie o tak fatalnym stosunku
sygnału do szumu jak piłka, przeuczysz się niezależnie od tego, jak
ostrożny będziesz z leakage.

**Realny budżet: 8–15 cech, silna regularyzacja, pooling hierarchiczny.**

Dixon-Coles jest w lepszej sytuacji niż GBM: ~36 parametrów na 6120
obserwacji goli, co jest zdrowe. To argument, żeby baseline był
parametryczny, a GBM dokładać dopiero gdy baseline bije zamknięcie.

### Wielkość próby potrzebna do wnioskowania

Przy średnim kursie 2,0 odchylenie standardowe zysku na jednostkę stawki
≈ 1,0. Żeby odróżnić yield 3% od zera na poziomie 95%:

```
n ≈ (1.96 / 0.03)² ≈ 4 300 zakładów
```

Przy kursie 4,0 to już ~12 800. **Backtest na 400 meczach nie mówi nic.**
Każdy raport z backtestu musi podawać `n` i przedział ufności.

---

## 3. Reguły nienaruszalne

Pełna treść jest w `CLAUDE.md` w katalogu głównym repo i ładuje się
automatycznie. Streszczenie dla orientacji — **w razie rozbieżności
obowiązuje `CLAUDE.md`**:

**Look-ahead bias (reguły 1–7).** Cechy wyłącznie z danych sprzed meczu.
Wszystkie znaczniki czasu tz-aware UTC. Zakaz statystyk liczonych na
pełnym zbiorze. `rolling`/`expanding` zawsze z `shift(1)` lub
`closed="left"`. Stan przed kolejką, nie końcowy. Kurs zamknięcia tylko
do CLV, nigdy jako cena wejścia.

**Backtest (8–11).** Wyłącznie walk-forward. Kalibracja na zbiorze
rozłącznym z treningiem. Hiperparametry nigdy na teście. Każdy raport
podaje `n` i przedział ufności.

**Dane (12–15).** `data/raw/` niemodyfikowalne. Parquet. Każdy zbiór ma
`ingested_at` i `source`. Nazwy drużyn wyłącznie przez `team_mapping`.

**Wycena (16–20).** Marża wyłącznie metodą Shina. Shin wymaga
kompletnego rynku. Prawdopodobieństwa skalibrowane. Kurs rynkowy nie
może być cechą. `tax_factor` zawsze jawny parametr.

**Stawkowanie (21–23).** Kelly ułamkowy (0.25), z podatkiem, limit 2%
bankrolla.

**Metryki (24–26).** Log loss → reliability diagram → CLV vs zamknięcie
Pinnacle po Shinie → yield. **Accuracy zabroniona.** CLV nadrzędne.

---

## 4. Co jest zbudowane — stan zweryfikowany

### Weryfikacja na docelowej maszynie (Windows, 2026-09-21)

```
uv 0.12.17 (x86_64-pc-windows-msvc)
CPython 3.13.15
64 pakietów zainstalowanych

pytest:  199 passed in 123.95s
ruff:    All checks passed!
mypy:    Success: no issues found in 13 source files
```

Podział testów: `test_shin` 59, `test_team_mapping` 41,
`test_features_base` 30, `test_schema` 27, `test_elo` 23,
`test_snapshots` 19.

**Uwaga wydajnościowa:** ta sama sucha przechodzi w ~1,5 s na Linuksie i
~124 s na tym Windowsie. Przyczyną jest najpewniej skanowanie w locie
przez antywirusa przy zapisach parquet w `test_snapshots` i tworzeniu
katalogów `tmp_path`. To nie jest błąd, ale przy iteracji w kroku 3
będzie bolało. Dwie opcje: wykluczyć folder projektu i `.venv` ze
skanowania, albo używać `uv run pytest tests/test_X.py` zamiast pełnej
suity podczas pracy nad jednym modułem. Pełną suitę i tak trzeba
przepuścić przed uznaniem zadania za skończone.

### Struktura

```
<user>\Desktop\value-bet\
├── CLAUDE.md                    26 reguł nienaruszalnych
├── CONTEXT.md                   ten dokument
├── README.md                    instrukcja + cron dla kolektora
├── .env.example                 szablon konfiguracji
├── .gitignore
├── pyproject.toml  uv.lock      uv, ruff, mypy strict, pytest
├── raport.log                   log weryfikacji (można usunąć)
├── .claude/agents/backtest-auditor.md
├── data/
│   ├── team_aliases.yaml        21 klubów Ekstraklasy i 1. ligi
│   ├── raw/        .gitkeep     NIEMODYFIKOWALNE
│   ├── interim/    .gitkeep
│   └── processed/  .gitkeep
├── logs/           .gitkeep
├── src/valuebet/
│   ├── schema.py                [GOTOWE]
│   ├── ingest/snapshots.py      [GOTOWE]
│   ├── ingest/team_mapping.py   [GOTOWE]
│   ├── features/base.py         [GOTOWE]
│   ├── features/elo.py          [GOTOWE]
│   ├── pricing/shin.py          [GOTOWE]
│   ├── models/                  (pusty)
│   ├── backtest/                (pusty)
│   └── live/                    (pusty)
└── tests/                       6 plików, 199 testów
```

### API modułów

**`schema.py`** — modele Pydantic v2, wszystkie `frozen=True`,
`extra="forbid"`.

- `UtcDatetime` — typ annotowany, odrzuca naiwny `datetime`.
- `utcnow()` — jedyne dopuszczalne źródło „teraz". Nigdy `datetime.now()`.
- `make_match_id(competition, kickoff_utc, home_team_id, away_team_id)` —
  deterministyczne SHA1[:16]; klucz to **data** (nie pełny timestamp)
  plus obie drużyny.
- `Match` — `match_id, sport, competition, season, kickoff_utc,
  home_team_id, away_team_id, status, home_goals?, away_goals?, stats,
  extra, ingested_at, source`. Pole `extra: dict[str, Any]` to miejsce na
  przyszłe cechy bez migracji schematu.
- `Selection` — `match_id, market, outcome, line?`. Waliduje, że wynik
  należy do rynku i że `line` jest podany dla AH/OU (i tylko tam).
- `OddsSnapshot` — `..., odds, observed_at, tax_factor, max_stake?,
  is_live, ...`; property `effective_odds = odds * tax_factor`.
- `MARKET_OUTCOMES` — mapa rynek → komplet wyników, do walidacji
  kompletności przed Shinem.
- `selection_key` — `{match_id}:{market}:{outcome}@{line}`, identyczny w
  `Selection` i `OddsSnapshot`.

**`ingest/snapshots.py`** — kolektor klasy B.

- `CollectorSettings.from_env()`
- `RequestBudget` — licznik zapytań na dobę UTC, **trwały między
  procesami** (`data/raw/snapshots/_state/budget.json`).
- `SnapshotWriter.write(kind, records, observed_at, source, context)` —
  append-only parquet, partycje `date=YYYY-MM-DD`.
- `ApiFootballClient` — transport wstrzykiwalny (testy przez
  `httpx.MockTransport`, zero sieci).
- `collect_once(settings, transport=None, now=None)`
- `read_snapshots(root, kind)`
- `main()` — `python -m valuebet.ingest.snapshots`

**`ingest/team_mapping.py`**

- `normalise_name(name)`
- `AliasStore.from_yaml/.to_yaml/.add_alias/.add_team/.lookup`
- `TeamResolver.resolve(name) -> str | None` — **nigdy nie zgaduje**
- `TeamResolver.resolve_strict(name) -> str`
- `TeamResolver.suggest(name, limit)` — do **ręcznego** zatwierdzenia
- `TeamResolver.report_unresolved()`
- `TeamResolver.coverage()`

**`features/base.py`**

- `build_timeline(matches)` — szeroki → długi
- `build_keys(matches, bet_lead_time)` — dodaje `asof_utc`
- `rolling_prior(timeline, column, window, min_periods)`
- `rolling_prior_sum(...)`
- `PointInTimeStore(tables)` / `.asof_join(keys, table, by, columns,
  suffix, tolerance)`
- `FeatureBuilder` (Protocol) + `compose(*builders)`

**`features/elo.py`**

- `EloConfig(initial=1500, k=20, home_advantage=65,
  goal_diff_scaling=True, season_carry=0.75)`
- `compute_elo(matches, config=None, initial_ratings=None) -> EloRatings`
- `EloRatings.features` — `match_id, home_elo_before, away_elo_before,
  elo_diff, elo_expected_home`
- `EloRatings.final`, `.history()`, `expected_score(a, b)`

**`pricing/shin.py`**

- `shin_probabilities(odds, ...) -> ShinResult`
- `ShinResult`: `probabilities, z, booksum, iterations, converged`,
  property `overround`, `fair_odds`
- `implied_probabilities`, `booksum`, `overround`
- `shin_forward(probabilities, z, margin)` — model odwrotny, do testów
  round-trip i Monte Carlo

---

## 5. Decyzje techniczne i historia błędów — NIE ZMIENIAJ TEGO

Najważniejsza sekcja. Każdy punkt opisuje błąd, który został już
popełniony i naprawiony, albo pułapkę przy „upraszczaniu". Jeśli
zobaczysz kod, który wygląda na nadmiarowy — sprawdź tutaj, zanim go
uprościsz.

### 5.1 Shin: solver Brenta, NIE iteracja punktu stałego

Kanoniczna iteracja z literatury (Jullien & Salanié):

```
z_{n+1} = ( Σᵢ sqrt(z_n² + 4(1−z_n)·πᵢ²/P) − 2 ) / (n − 2)
```

**Nie działa.** Dwa powody:
1. Nie zbiega dla małych `z` (testy padały dla z ∈ {0.01, 0.03}).
2. Ma zero w mianowniku dla `n = 2`, czyli dla rynku dwustronnego —
   tenis, handicapy azjatyckie, over/under. Połowa tego, co projekt chce
   grać.

Rozwiązanie: **`scipy.optimize.brentq`** na `g(z) = Σ pᵢ(z) − 1`, na
przedziale `[0, 1−1e-12]`.

Bracketing gwarantowany:
- `g(0) = sqrt(P) − 1 > 0` dla książki z marżą
- `g(1⁻) = Σπᵢ²/P − 1 < 0`

Działa jednolicie dla każdego `n`. Nie zastępuj tego iteracją, nawet
jeśli literatura tak podaje.

### 5.2 Shin: granica przy z → 0 to NIE normalizacja proporcjonalna

Błąd koncepcyjny, który wyglądał niewinnie i psuł cały moduł po cichu.

```
lim(z→0) [ sqrt(z² + 4(1−z)·πᵢ²/P) − z ] / [ 2(1−z) ]
       = sqrt(4·πᵢ²/P) / 2
       = πᵢ / sqrt(P)          ← NIE πᵢ/P
```

Suma dąży do `sqrt(P)`, nie do 1. To nie jest błąd — to właśnie jest
funkcja celu, której pierwiastka szukamy.

**Wstawienie tam `πᵢ/P` zeruje `g` w punkcie 0**, solver zwraca `z = 0`
dla **każdej** książki, i cały moduł degeneruje się do metody, którą miał
zastąpić — bez żadnego sygnału błędu.

```python
_Z_EPS = 1e-10

def _apply_shin(pi, bsum, z):
    if z < _Z_EPS:
        return np.asarray(pi / np.sqrt(bsum), dtype=np.float64)   # ← sqrt!
    root = np.sqrt(z * z + 4.0 * (1.0 - z) * (pi**2) / bsum)
    return np.asarray((root - z) / (2.0 * (1.0 - z)), dtype=np.float64)
```

### 5.3 Shin: wzory referencyjne

Model prosty:

```
πᵢ = 1/kᵢ ,  P = Σπᵢ  (booksum)
pᵢ = ( sqrt(z² + 4(1−z)·πᵢ²/P) − z ) / ( 2(1−z) )
z dobrane tak, aby Σpᵢ = 1
```

Model odwrotny (`shin_forward`, do testów round-trip):

```
πᵢ = sqrt(P) · sqrt( pᵢ·((1−z)·pᵢ + z) )
sqrt(P) = Σᵢ sqrt( pᵢ·((1−z)·pᵢ + z) )
kᵢ = 1/πᵢ
```

Test round-trip (generujemy kursy z prawdziwych `p` i `z`, sprawdzamy
odzyskanie) jest najważniejszym testem w `test_shin.py` — dowodzi
poprawności matematycznej, a nie tylko tego, że liczby sumują się do 1.

### 5.4 Shin: dlaczego nie normalizacja proporcjonalna

Metoda proporcjonalna `(1/k)/Σ(1/k)` zakłada równomierny rozkład marży.
Empirycznie nieprawda — marża jest przeciążona na longshotach
(favourite-longshot bias). Skutek: systematyczne **zawyżanie**
prawdopodobieństwa outsiderów, czyli fałszywe +EV dokładnie tam, gdzie
wariancja jest największa.

Zmierzone na `[1.80, 3.60, 4.50]` (marża 5,56%, z=0,0279):

| | faworyt | remis | longshot |
|---|---|---|---|
| Shin | 0,5343 | 0,2602 | **0,2055** |
| proporcjonalna | 0,5263 | 0,2632 | **0,2105** |

Pół punktu procentowego na longshocie = **2,3 pp różnicy w EV**
(−5,26% vs −7,53%). Przy progu detekcji 2% to strumień fałszywych
sygnałów.

### 5.5 `ł` NIE jest literą z diakrytykiem

`unicodedata.normalize("NFKD", "ł")` zwraca `"ł"` — bez zmian. Polskie
`ł` to osobny znak alfabetu, kreska jest częścią glifu, nie znakiem
łączącym. Filtrowanie po `unicodedata.combining()` jej nie usuwa.

Skutek: `normalise_name("Łódź")` dawało `"łodz"`, co nie dopasowuje się
do `"lodz"`. **Cicho psuło Łódź, Wrocław, Zagłębie, Płock, Łęczna** —
sporą część Ekstraklasy, bez żadnego błędu, tylko z mniejszą liczbą
meczów w zbiorze.

```python
_LETTER_MAP = str.maketrans({
    "ł": "l", "Ł": "L",
    "đ": "d", "Đ": "D",
    "ø": "o", "Ø": "O",
    "æ": "ae", "Æ": "AE",
    "œ": "oe", "Œ": "OE",
    "ß": "ss",
    "þ": "th", "Þ": "TH",
    "ð": "d", "Ð": "D",
    "ı": "i", "İ": "I",   # noqa: RUF001 - tureckie i bez kropki, celowo
})

def normalise_name(name: str) -> str:
    mapped = name.translate(_LETTER_MAP)          # ← NAJPIERW mapa
    nfkd = unicodedata.normalize("NFKD", mapped)  # ← potem NFKD
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = _PUNCT.sub(" ", ascii_only.lower())
    raw_tokens = [t for t in _SPACES.split(cleaned) if t]
    tokens = [
        t for t in raw_tokens
        # Pojedyncze litery to resztki po formach prawnych ("S.A." -> "s","a").
        # Cyfry zostawiamy — bywają częścią nazwy (np. rok założenia).
        if t not in _NOISE_TOKENS and not (len(t) == 1 and t.isalpha())
    ]
    if not tokens:
        tokens = raw_tokens   # nazwa z samego szumu — nie generuj pustego klucza
    return " ".join(tokens)
```

`_NOISE_TOKENS`: `fc, sc, ac, afc, cf, fk, sk, ks, mks, gks, lks, zks,
rks, wks, ts, kks, oks, sa, spa, sad, klub, sportowy, miejski, gminny,
stowarzyszenie, team, club`.

**`ruch`, `stal`, `zaglebie`, `gornik` NIE mogą tam trafić** — to
prawdziwe nazwy klubów, nie szum organizacyjny.

### 5.6 `coverage()` musi liczyć trafienia, nie tylko chybienia

Pierwsza wersja liczyła wyłącznie `_misses` i zwracała `1.0` albo `0.0`,
nigdy nic pomiędzy — bezużyteczna jako metryka.

```python
def __init__(self, store, *, suggestion_cutoff=70.0):
    self._misses: Counter[str] = Counter()
    self._hits = 0                                   # ← wymagane

def resolve(self, name):
    hit = self.store.lookup(name)
    if hit is None:
        self._misses[name] += 1
    else:
        self._hits += 1                              # ← wymagane
    return hit

def coverage(self) -> float:
    total = self._hits + sum(self._misses.values())
    return 1.0 if total == 0 else self._hits / total
```

**To jest metryka jakości danych, pilnuj jej po każdym nowym źródle.**
Spadek z 1,00 na 0,97 to trzy procent meczów, które znikną bez żadnego
komunikatu — i znikną w sposób skorelowany z tym, które drużyny mają
nietypowe nazwy, czyli zwykle mniejsze i słabsze. To survivorship bias
wprowadzony literówką.

### 5.7 Fuzzy matching NIGDY nie zatwierdza automatycznie

`rapidfuzz` służy **wyłącznie** do generowania sugestii do ręcznego
zatwierdzenia. `resolve()` zwraca `None`, gdy nie ma pewnego trafienia.

Dowód liczbowy — zapytanie o samą nazwę klubu bez miasta daje
**identyczny score dla dwóch różnych klubów**:

```
"Ruch"    → ruch-chorzow: 90.0 , ruch-radzionkow: 90.0
"Gornik"  → gornik-zabrze: 90.0, gornik-leczna:   90.0
"Stal"    → stal-mielec:   90.0, stal-rzeszow:    90.0
"Wisla"   → wisla-krakow:  90.0, wisla-plock:     90.0
```

Automatyczna akceptacja wybrałaby jeden arbitralnie — kolejnością
słownika — i nikt by tego nie zauważył przez pół roku. Te pary są
rozpisane w komentarzu w `data/team_aliases.yaml`.

Workflow przy nowym źródle:
1. `resolver.resolve_many(names)`
2. `resolver.report_unresolved()` — **przejrzyj CAŁOŚĆ przed dalszą pracą**
3. Dopisz aliasy do YAML **ręcznie**
4. Sprawdź `resolver.coverage()`

### 5.8 `shift(1)` idzie PRZED `rolling()`

Najczęstszy pojedynczy błąd w tego typu kodzie. Okno bez przesunięcia
zawiera bieżący mecz — czyli wynik, który próbujesz przewidzieć.

```python
def rolling_prior(timeline, column, *, window, min_periods=1):
    _validate_timeline(timeline, column)   # m.in. sprawdza sortowanie!
    return timeline.groupby("team_id", sort=False)[column].transform(
        lambda s: s.shift(1).rolling(window, min_periods=min_periods).mean()
    )
```

Dwie rzeczy, których nie wolno „uprościć":
- **Walidacja sortowania.** Niesortowany `rolling` cicho miesza przyszłość
  z przeszłością i nic tego nie sygnalizuje.
- **NaN przy niedostatecznej historii zostaje NaN.** Nie wypełniaj
  średnią globalną — to statystyka z pełnego zbioru, czyli przeciek.

### 5.9 Format długi jest konieczny, nie kosmetyczny

Średnia krocząca musi być liczona wzdłuż sekwencji meczów **jednej
drużyny**. W formacie szerokim kolejne mecze tej samej drużyny leżą raz w
`home_*`, raz w `away_*` — każda próba rollingu tam kończy się przeciekiem
albo bzdurą. Stąd `build_timeline`.

Sortowanie jest trójstopniowe i stabilne:
`["kickoff_utc", "match_id", "is_home"]` z `kind="mergesort"`. Bez
deterministycznej kolejności dwa przebiegi na tych samych danych dają
różne wyniki i backtest przestaje być odtwarzalny.

### 5.10 `allow_exact_matches=False` w `merge_asof`

To NIE jest detal. Daje ostre `<` zamiast `<=`: fakt zaobserwowany
**dokładnie** w momencie odcięcia jest odrzucany.

Przy źródłach podających samą datę (bez godziny) równe znaczniki są
nagminne, a `<=` wpuszcza wtedy do cechy informację z tej samej chwili co
zakład.

```python
merged = pd.merge_asof(
    keys.sort_values("asof_utc", kind="mergesort"),
    facts.sort_values("observed_at", kind="mergesort"),
    left_on="asof_utc",
    right_on="observed_at",
    by=by_cols,
    direction="backward",
    allow_exact_matches=False,        # ← ostre <, nie <=
    tolerance=pd.Timedelta(tolerance) if tolerance is not None else None,
)
```

**Zawsze podawaj `tolerance`.** Bez niej `merge_asof` chętnie podstawi
kontuzję sprzed pół roku jako informację o dzisiejszym składzie.

### 5.11 `asof_utc`, nie `kickoff_utc`

```
asof_utc = kickoff_utc − bet_lead_time
```

Nie gwizdek. Stawiając 24h przed meczem nie masz potwierdzonych składów —
model wytrenowany na składach jest wtedy bezużyteczny w produkcji.

`bet_lead_time` jest **osią eksperymentu**, nie stałą. Zbuduj dwa zestawy
cech (24h i 1h) i porównaj CLV — to empirycznie odpowie, czy dane o
składach są u wybranego bukmachera cokolwiek warte.

Wyliczany w jednym miejscu (`build_keys`), żeby zmiana horyzontu była
zmianą parametru, a nie polowaniem po kodzie.

### 5.12 Elo musi być pętlowy

Elo jest rekurencyjny: rating przed meczem N+1 zależy od wyniku meczu N.
Każda próba wektoryzacji kończy się jednym z dwóch błędów:

- `groupby().shift()` na gotowych ratingach — ratingi trzeba najpierw
  skądś wziąć, a biorą się z przyszłości;
- `cumsum` po zmianach ratingu — ignoruje to, że zmiana zależy od
  ratingu przeciwnika w **tamtym** momencie, nie dzisiejszego.

Pętla przy 50 tys. meczów wykonuje się w sekundy. Optymalizacja nie ma tu
uzasadnienia, a ryzyko ma.

W kodzie jest linia oddzielająca odczyt od aktualizacji:

```python
        # --- ZAPIS CECHY. Wszystko poniżej tej linii to już przyszłość. ---
        out_home.append(home_rating)
        out_away.append(away_rating)
```

**Nie przenoś niczego nad tę linię.**

Własności do zachowania:
- Mecze bez wyniku dostają cechę, ale **nie aktualizują ratingów** — tą
  samą funkcją liczysz cechy dla nadchodzącej kolejki.
- Carry-over międzysezonowy **przed** odczytem cechy, więc pierwszy mecz
  sezonu ma już ściągnięty rating.
- Gra o sumie zerowej: `ratings[home] += delta`, `ratings[away] -= delta`.
- `initial_ratings` pozwala wznowić bez przeliczania całej historii.
- Sortowanie `["kickoff_utc", "match_id"]`, `kind="mergesort"` —
  przetasowane wejście musi dać identyczny wynik.

### 5.13 Kolejność zbierania w kolektorze jest celowa

`kontuzje → terminarz → składy`

Kontuzje kosztują 1 zapytanie na ligę i są potrzebne codziennie. Składy
kosztują 1 zapytanie na mecz i mają sens tylko w wąskim oknie (domyślnie
180 min) przed gwizdkiem. Przy wyczerpaniu budżetu składy giną pierwsze —
są najdroższe i najłatwiej je nadrobić następnego dnia. Kontuzji nie
nadrobisz.

### 5.14 Surowy payload trafia do bazy w całości

Każdy rekord zapisywany jako JSON w kolumnie `payload`, obok wyciągniętych
kolumn. Dziś nie wiesz, których pól będziesz potrzebować za rok, a
**ponownie pobrać przeszłości się nie da**. Parsowanie jest odwracalne,
utrata danych nie.

### 5.15 Brak klucza API to twardy błąd, nie cichy pusty przebieg

`collect_once()` podnosi `RuntimeError`, jeśli `VB_API_FOOTBALL_KEY` jest
pusty. Kolektor, który po awarii konfiguracji grzecznie nic nie robi, to
najgorszy tryb awarii w tym projekcie — dowiadujesz się po trzech
miesiącach, patrząc na pusty katalog.

Podobnie: API-Football zwraca **HTTP 200 z niepustym polem `errors`** przy
problemach z kluczem lub limitem. Klient sprawdza to jawnie.

### 5.16 Test trucizny — i test testu

Cztery testy, wszystkie muszą przechodzić:

```
test_future_poison_sequential_facts     (features/base)
test_future_poison_exogenous_facts      (features/base)
test_future_poison_elo                  (features/elo)
test_future_poison_detects_a_real_leak  (kontrola samego testu)
```

Wzorzec:

```python
def test_future_poison_sequential_facts():
    """Absurdalny mecz w przyszłości nie może zmienić ŻADNEJ przeszłej cechy."""
    baseline = _build_all(matches, store)

    poisoned_matches = pd.concat([matches, pd.DataFrame({
        "match_id": ["POISON"],
        "kickoff_utc": [T0 + timedelta(days=99)],
        "home_team_id": ["A"], "away_team_id": ["B"],
        "home_goals": [99.0], "away_goals": [99.0],
    })], ignore_index=True)

    after = _build_all(poisoned_matches, store)
    after = after[after["match_id"] != "POISON"].reset_index(drop=True)

    pd.testing.assert_frame_equal(baseline, after)
```

**`test_future_poison_detects_a_real_leak` jest ważniejszy, niż wygląda.**
Bierze celowo dziurawy pipeline (`rolling()` bez `shift(1)`) i sprawdza,
że test trucizny go wywala. Bez niego nie wiesz, czy trzy pierwsze
cokolwiek sprawdzają, czy zawsze przechodzą. **Test, który nigdy nie może
zawieść, jest gorszy niż brak testu** — daje fałszywą pewność.

**Dopisujesz nową cechę → dopisz ją do `_build_all` w
`tests/test_features_base.py`.** Test chroni tylko cechy obecne w
pipeline testowym.

### 5.17 Deterministyczne `match_id`

Klucz: `slug(competition) | data (nie pełny timestamp) | home_id |
away_id`, SHA1 obcięty do 16 znaków.

**Data, nie godzina** — źródła podają godziny różniące się o kilka minut i
bywają korygowane. Jedna para drużyn gra najwyżej raz dziennie.

Świadomy kompromis: przesunięcie meczu na inny dzień zmienia ID i tworzy
duplikat. Wolimy widoczny duplikat niż cichy merge dwóch różnych spotkań.

### 5.18 Drobiazgi, które wyglądają na nadmiarowe, a nie są

- `# noqa: TRY004` przy `raise ValueError` po sprawdzeniu dtype — ruff
  zakłada, że `isinstance`-check implikuje `TypeError`. Tu sprawdzamy
  **dtype kolumny DataFrame**, a nie typ argumentu; to błąd kontraktu
  danych, czyli `ValueError`. Nie zmieniaj na `TypeError`.
- `BudgetExhaustedError` — sufiks `Error` wymagany przez ruff N818.
- Ruff ma włączoną regułę **`DTZ`** celowo — wyłapuje naiwny `datetime`,
  jeden z częstszych wektorów look-ahead bias. Nie wyłączaj jej.
- `filterwarnings = ["error"]` w pytest — ostrzeżenia są błędami.
- `pandas-stubs` i `types-PyYAML` w grupie dev, bo `mypy --strict` ich
  wymaga.
- Uwaga środowiskowa: na Windowsie `uv sync` zaciągnął `tzdata` jako
  zależność przechodnią. Nie usuwaj go — bez niego `zoneinfo` nie ma bazy
  stref i konwersja `Europe/London` w kroku 3 padnie.

### 5.19 CI z bootstrapu iid przy danych panelowych — cena 31% szerokości

Znalezione w audycie kroku 3 (2026-09-30, `AUDIT_REPORT.md`). Kod był
poprawny w tym, w czym zwykle jest błędny — bootstrap BYŁ sparowany
(`diff = ll_elo - ll_market` liczone przed losowaniem). Błąd siedział
piętro wyżej: losowaliśmy **pojedyncze mecze**, jakby były niezależne.

Nie są. Mecze jednego sezonu dzielą to samo dopasowanie ordinal logit
(jedno na sezon), ten sam reżim ratingów i ten sam skład ligi. To dane
panelowe, a nie próba iid.

Rozrzut luki Elo do Pinnacle po sezonach:

```
2015/16 +0.0021   2018/19 +0.0189   2021/22 +0.0225   2024/25 +0.0193
2016/17 +0.0319   2019/20 +0.0129   2022/23 +0.0378   2025/26 +0.0091
2017/18 -0.0045   2020/21 +0.0085   2023/24 -0.0037
```

Od −0,0045 do +0,0378 przy CI iid o szerokości 0,0127. Przedział był
węższy niż rozrzut, który miał opisywać.

**Cena buga — liczby przed i po:**

| | przed (iid) | po (klastrowy po sezonach) |
|---|---|---|
| Elo − Pinnacle (n=3055) | +0,0145 **[+0,0082, +0,0209]** | +0,0145 **[+0,0062, +0,0229]** |
| Elo − BFEC (n=656) | +0,0121 [−0,0006, +0,0245] | +0,0121 [−0,0001, +0,0232], **oznaczone jako niewiarygodne (3 sezony)** |
| elo − stała (n=3319) | −0,0200 [−0,0271, −0,0132] | −0,0200 [−0,0273, −0,0125] |

**Wartości punktowe nie drgnęły.** Zmieniła się wyłącznie deklarowana
pewność: CI luki do Pinnacle jest **31% szersze**. Wniosek merytoryczny
przeżywa — rynek nadal lepszy, luka nadal w strefie 0,01–0,03, przedział
nadal nie zawiera zera. To jest bug, który nie psuje wniosku, tylko
uczciwość jego uzasadnienia.

**Dlaczego to trzeba było naprawić mimo to.** W kroku 3 porównujemy
log loss i błąd kosztuje 31% szerokości przedziału. W kroku 5+ ta sama
funkcja policzy CI **yieldu**, gdzie zakłady grupują się w kolejki i dni,
a decyzją nie jest „ciekawe", tylko „stawiam pieniądze". Reguła 11 mówi,
że rozróżnienie 3% od zera wymaga ~4300 zakładów — ten rachunek zakłada
niezależność. Przy klastrowaniu po kolejkach wymagane `n` rośnie, a zbyt
wąskie CI każe uwierzyć w przewagę, której nie ma.

**Zasada, nie łatka:** `paired_bootstrap_diff(groups=...)` jest
obowiązkowy dla każdej liczby raportowanej na zewnątrz. Wariant iid
zostaje wyłącznie tam, gdzie nie ma po czym klastrować (porównanie
wewnątrz jednego sezonu) i raport ma to wtedy **napisać**, a nie
przemilczeć. `BootstrapDiff.reliable` jest `False` poniżej 8 klastrów —
kwantyle z trzech sezonów to trzy liczby, nie przedział.

### 5.20 Dwie referencje na różnych meczach to nie dwa pomiary tej samej rzeczy

Ten sam audyt. ROADMAP raportował obok siebie: Elo − Pinnacle = +0,0145
i Elo − BFEC = +0,0121. Zestawienie zapraszało do wniosku „exchange
łatwiej pobić o 0,0024".

Wniosek jest fałszywy. Pinnacle pokrywa 3055 meczów, BFEC 656, **wspólnych
jest 418**. 2637 meczów ma tylko Pinnacle, 238 tylko BFEC — to w większości
różne mecze z różnych lat. Różnica 0,0024 mierzyła głównie podzbiór.

Na wspólnych 418 meczach:

```
Elo − pinnacle  +0.0166      Elo − betfair_exchange  +0.0159
różnica luk     +0.0006
LL(pinnacle) − LL(bfec) = -0.0006  [-0.0064, +0.0015]   NIEistotna
```

Mimo booksumu 1,0415 vs 1,0096 i z = 0,0209 vs 0,0048 — czyli **zupełnie
innej struktury marży** — obie referencje wyceniają nierozróżnialnie
dobrze. Cała różnica 0,0024 z ROADMAP to artefakt podzbioru, nie
właściwość źródła.

**Konsekwencja projektowa:** liczba bez zakresu, na którym powstała, jest
niepełna. `MarketGap` niesie `seasons`, a `run_elo_baseline` liczy
`reference_overlaps` — obie luki na przecięciu, plus parowaną różnicę
samych referencji. Zestawianie luk pooled między sobą jest błędem
niezależnie od tego, jak kuszące.

**To nie unieważnia decyzji z ROADMAP o osobnym raportowaniu.** Exchange
ma inną strukturę marży i innych graczy, więc nadal nie sklejamy ich w
jedną liczbę. Nowa wiedza jest węższa: na meczach, gdzie mamy oba źródła,
nie mierzą nic różnego, więc przejście Pinnacle → BFEC w 2024/25 **nie
wprowadza skoku poziomu referencji**. To dobra wiadomość dla ciągłości
szeregu, a nie zgoda na uśrednianie.

---

### 5.21 Prior wyśrodkowany na zerze przypinał poziom bramkowy

Ograniczenie identyfikowalności w Dixonie-Colesie centruje **tylko**
`log alpha`. `log beta` nie jest niczym centrowane, bo musi unieść poziom
bramkowy ligi — zmierzona średnia w Ekstraklasie to stabilnie `+0.10`,
czyli `beta ≈ 1.10`, nie 1.

Kara liczona jako `Σ (log beta)²` ściągała więc każdą słabo określoną
drużynę do obrony **o 10% lepszej od ligowej**. Para średnich drużyn
dostawała `lambda+mu = 2.31` zamiast rzeczywistych 2.63, a przy zaniżonej
liczbie goli Poisson mechanicznie podbija remis.

Skutek na zbiorze deweloperskim: w koszyku `P(X) ≥ 0.30` model przewidywał
30.9% remisów przy realizacji 22.2% (`z = −3.45`), mimo że **faktycznych
goli padało tam tyle samo co wszędzie indziej**. Podgrupa z beniaminkiem:
`z = −5.04`.

Kara liczy się od **średniej**, nie od zera. Zero nie jest środkiem
rozkładu `log beta` i nigdy nim nie było. Ta sama pułapka siedziała drugi
raz w wartości domyślnej dla drużyny nieznanej modelowi — poprawienie
tylko kary zostawiłoby ją dla drużyn z zerem meczów.

### 5.22 Wiarygodność DC jest nieograniczona dla drużyny bez gola

`alpha -> 0` podnosi log-wiarygodność monotonicznie, jeśli drużyna nie
strzeliła ani jednego gola. Sandecja Nowy Sącz miała przed meczem z Legią
(2017/18) dokładnie dwa mecze, oba 0:0 — solver zatrzymał się na
`log alpha = −12`, `log beta = −14.6`, `lambda = 1.5e−06`, a macierz
wyników zapadła się na komórkę 0:0 dając `P(remis) = 0.999996`.

Dziesięć takich predykcji wnosiło **+0.0342** do średniego log lossu na
3319 meczach, czyli więcej niż cała przewaga Elo nad bukmacherem.

Prior nie jest tu ozdobą bayesowską, tylko **warunkiem istnienia
estymatora**. Czyste MLE wolno puszczać wyłącznie tam, gdzie każda drużyna
ma dużo meczów — na przykład w teście odzyskiwania parametrów.

### 5.23 `tau` zachowuje rozkłady brzegowe — nie szukaj w `rho` błędu goli

Dwie rzeczy, które wyglądają na winne, a nie są.

**Korekta `tau` nie psuje normalizacji.** Suma poprawek jest tożsamościowo
zerowa: `rho·e^(−λ−μ)·[−λμ + λμ + μλ − λμ] = 0`. Zweryfikowane numerycznie,
odchyłka rzędu 1e-16 przy dowolnym `rho`. Dixon i Coles tak właśnie
skonstruowali `tau`. Cała odchyłka od 1 pochodzi z **obcięcia macierzy**,
więc lekarstwem jest większe `max_goals`, nie renormalizacja. STEP4_PLAN
§1.7 podaje w tym miejscu błędne uzasadnienie.

Konsekwencja: `tau` zachowuje też `E[gole] = lambda, mu` niezależnie od
`rho`. **Szukając błędu w liczbie goli, nie ruszaj `rho`** — to nie ta
dźwignia. Tabela kalibracji niskich wyników 4×4 na zbiorze deweloperskim
nie pokazała ani jednej komórki z `|z| > 3`.

**`max_goals = 10` ze STEP4_PLAN jest sprzeczne z progiem 1e-6 z tego
samego paragrafu.** Przy `lambda = 1.5` daje 6.1e-07, ale przy 2.5 już
6.2e-05, a przy 3.5 aż 1.0e-03. Mocny gospodarz w Ekstraklasie to
`lambda ≈ 2.5–3.0`. Wiążący jest próg, nie liczba — domyślne 15.

### 5.24 Rozrzut predykcji sumy goli porównuje się z prawdą, nie z wynikiem

Najłatwiejszy do popełnienia błąd interpretacyjny w całym kroku 4.

„Model przewiduje 2.28–3.06 gola przy rzeczywistym `sd = 1.63`, więc nie
ma zdania" **porównuje złe wielkości**. Zrealizowana suma goli to w
przeważającej części szum Poissona. Dekompozycja `var(Y) = E[T] + var(T)`
daje `var(T) ≈ 0.019`, czyli `sd` prawdziwej oczekiwanej sumy goli rzędu
**0.14** (górna granica ~0.4). Przewidywalna część wariancji goli to
poniżej 1%, a sufit korelacji predykcja–wynik ~0.08.

Nasze `r = 0.067` leży więc praktycznie na suficie. Wąskie predykcje nie
są wadą modelu, tylko własnością ligi.

**Szersze predykcje totali to więcej fałszywych sygnałów, nie więcej
przewagi.** Symulacja przeciw dobrze poinformowanemu bukowi (STEP4_ENSEMBLE
§11.1): nachylenie 0.37 daje 377 zakładów na 1000 meczów i ROI −3.7%;
nachylenie 1.21 daje 164 zakłady i +0.1%. Przewaga na totalach bierze się
z **lepszej informacji niż buk**, a nie z szerszego rozkładu.

Nie luzuj ściągania, żeby model „miał opinię".

### 5.25 Jedno `sd` na dwa wymiary o różnej zmienności psuje nachylenie

Obróć parametryzację: `s_i = (log α_i − log β_i)/2` (siła, decyduje o tym
kto wygrywa), `o_i = (log α_i + log β_i)/2` (otwartość, decyduje o sumie
goli). Wtedy `log λ + log μ` zależy **wyłącznie** od otwartości, a
`log λ − log μ` **wyłącznie** od siły.

Wspólne `sd` dla `log alpha` i `log beta` to dokładnie wspólne `sd` dla `s`
i `o`. Ale drużyny różnią się siłą dużo, a otwartością mało — zmierzone
`tau_s/tau_o` w Ekstraklasie to 2.7–13.7. Jedno `sd` dobrane pod siłę
prawie nie ściąga otwartości, więc przewidywana suma goli jest za
rozstrzelona.

Objaw diagnostyczny: **przeciwne znaki na krańcach**. Dolny kwartyl `λ+μ`
`+0.233 [+0.161, +0.307]`, górny `−0.127 [−0.204, −0.055]`. To jest błąd
rozrzutu, nie poziomu — i nie naprawia go żadna korekta stałej.

Osobne skale ściągania dla `s` i `o` naprawiają sumy bez kosztu na 1X2.

### 5.26 `+σ²/2` przy wolnym poziomie liczy Jensena podwójnie

Kusząca, błędna odpowiedź na „model zaniża gole". Przy priorze
wyśrodkowanym na średniej poziom (`mean(log β)`, `log γ`) jest wolny, a
kara niezmiennicza względem wspólnego przesunięcia. Równanie score daje
`Σ w·(λ+μ) = Σ w·(y_h + y_a)` — łączna liczba goli na treningu jest
dopasowana **dokładnie**, niezależnie od siły ściągania.

Poziom był w porządku od początku: całe dev `+0.040 [−0.021, +0.093]`,
nieistotne. `+σ²/2` przesunęłoby wszystko o stałą, nie naprawiło
nachylenia i pogorszyło górny kwartyl, już przestrzelony o 0.127.

**Zanim dodasz korektę poziomu, sprawdź, czy problemem jest poziom czy
nachylenie.** Przeciwne znaki na krańcach oznaczają nachylenie.

### 5.27 Nachylenie wobec wyniku nie ma mocy — testuj wobec celu z rynku

Przy `r ≈ 0.07` regresja zrealizowanej sumy goli na przewidywanej daje
przedział `[0.31, 1.80]`. Taki przedział zawiera jedynkę, bo zawiera
prawie wszystko. **Kryterium spełnione pusto to nie kryterium.**

Ten sam test z mocą: celem jest suma goli implikowana z kursów 1X2
Pinnacle na zamknięciu. Z własności wieży, jeśli nasza predykcja jest
skalibrowana przy naszej informacji, a rynek wie co najmniej tyle co my,
to `E[T_rynek | T_nasze] = T_nasze`, czyli nachylenie wynosi 1. Szum w
zmiennej objaśnianej nie obciąża nachylenia, więc wolno użyć celu, który
sam jest oszacowaniem. Błąd standardowy wychodzi **~20× mniejszy**.

Kursy zamknięcia służą tu **wyłącznie diagnostyce** — nie są cechą modelu,
ceną wejścia ani celem strojenia (reguły 7 i 19 nienaruszone).
`backtest/market_benchmark.py`.

### 5.28 Estymator momentów z podłogą zapada się w małych oknach

`tau² = max(var(θ̂) − mean(SE²), podłoga²)` ma dwie wady: waży wszystkie
drużyny tak samo, choć drużyna z krótką historią ma wielokrotnie większy
`SE`, i wymaga podłogi, bo różnica bywa ujemna.

Skutek: `tau_o` na podłodze w 5 z 10 sezonów. W 2019/20 **również `tau_s`**,
przez co model stał się prawie stały — `sd(P(1)) = 0.038` wobec mediany
0.096, a log loss tego sezonu wzrósł z 1.0243 na 1.0525.

Zamiast tego: maksimum marginalnej wiarygodności przy
`θ̂_i ~ N(0, SE_i² + tau²)` z członem `+ log tau` (prior gamma(2, λ→0),
Chung i in. 2013). Ważenie precyzją jest wbudowane, a człon logarytmiczny
gwarantuje dodatniość bez obcinania. **Podłoga znika.**

Bezpiecznik: `tau_s < 0.05` podnosi wyjątek. Zerowa zmienność siły drużyn
przeczy temu, co pokazuje Elo — to awaria estymacji, nie ustalenie, i ma
być głośna.

**Uwaga o przecieku:** kuszące „weź `tau_o` z późniejszych okien, tam
wychodzi sensowniej" jest informacją z przyszłości. Każde okno ma swoje
`tau` wyłącznie z własnych danych. Lepszy estymator, nie pożyczanie.

### 5.29 Wybór hiperparametru na jednym sezonie walidacyjnym — dwa razy ta sama pułapka

Najpierw przy `prior_sd`: wybór skakał po krańcach siatki (0.25 pięć razy,
2.00 cztery razy), bo kryterium było wzdłuż tej osi prawie płaskie i
decydował szum jednego sezonu.

Potem, po przejściu na empirical Bayes, ta sama wada została na osi `ξ` i
zdegenerowała 2019/20: pojedynczy sezon walidacyjny wybrał `ξ = 0.008`
(pół-okres 87 dni), efektywna próba zmalała, EB uznał że drużyny się nie
różnią, oba `tau` spadły na podłogę.

Kryterium to suma log-wiarygodności po **wszystkich** sezonach
walidacyjnych przed `S`, każdy oceniany walk-forwardem z przefitowaniem
przed dniem meczowym. `LL(V, ξ)` nie zależy od `S`, więc liczy się raz i
cache'uje — inaczej ten sam walk-forward szedłby dla każdego `S` osobno.

**Jeden sezon walidacyjny nie wystarcza. Jeśli zobaczysz wybór skaczący
po krańcach siatki, to nie jest sygnał — to szum.**

### 5.30 Lockbox i reguła stopu dla DC

Zbiór OOS z kroku 3 posłużył w ciągu jednego dnia do co najmniej sześciu
rund decyzji: środek prioru, reparametryzacja `(s, o)`, empirical Bayes,
podłoga, wybór `ξ`, benchmark rynkowy. Każda kolejna poprawka dopasowuje
strukturę modelu do tych konkretnych sezonów — nie przez przeciek w
kodzie, tylko przez przeciek przez głowę autora.

Stąd dwie rzeczy:

- **Lockbox** (`backtest/lockbox.py`): 2025/26 i 2026/27 odłożone,
  jedna ewaluacja na końcu kroku 4. Egzekwowane `assert_no_lockbox()`
  przy każdej liczbie wpływającej na decyzję. Zadeklarowany **po** tym,
  jak log loss obu sezonów pojawił się w raportach — więc nie jest
  dziewiczy i końcowy wynik trzeba czytać z tą poprawką.
- **Zamrożenie struktury DC** po §11.2 i §11.3. Nowe pomysły na DC idą na
  listę „po lockboxie". Beniaminkowie (`tau` prioru pod drużyny bez
  historii) — świadomie odłożone, podgrupa `n = 138` i różnica goli
  `+0.150 [−0.040, +0.330]`, nieistotna.

---

### 5.31 `pinv` na macierzy z kierunkami prawie zerowymi rozlewa wariancję

Najdroższy błąd numeryczny w projekcie: zabił dwa przebiegi diagnostyczne
po kilkadziesiąt minut każdy i wyglądał jak wynik merytoryczny.

**Sytuacja.** Błędy standardowe parametrów drużyn liczone z
`pinv(XᵀWX)`, bez prioru, po **wszystkich** drużynach w oknie. Przy
wygaszaniu czasowym `ξ = 0.008` na oknie dekady drużyna, która ostatni raz
grała lata temu, ma `n_eff` rzędu 1e-8 — jej kierunek ma wartość własną
~1e-10.

**Mechanizm.** `pinv` odcina tylko to, co leży pod progiem `rcond`.
Kierunek o wartości własnej 1e-10 jest **powyżej** progu, więc zostaje
odwrócony w wariancję rzędu 1e10. Przy takim uwarunkowaniu błąd numeryczny
wektorów własnych rozlewa tę wariancję na **wszystkie** drużyny.

Sygnatura jest nie do pomylenia: SE wszystkich 18 aktywnych drużyn wyszło
9.0229–9.0239. Praktycznie identyczne liczby dla drużyn o bardzo różnej
liczbie meczów to nie niepewność — to jedna wartość rozmazana po macierzy.

```
xi      n_eff<0.5   cond XᵀWX*   SE(s) aktywnych: mediana
0.000        0        1.79e+02          0.048
0.002        4        2.00e+04          0.176
0.004        8        9.79e+06          3.800
0.008       11        3.72e+12          9.024
* bez dwóch dokładnych kierunków zerowych (wspólne przesunięcie s; o względem c)
```

**Naprawa — trzy rzeczy razem, żadna nie wystarcza osobno:**

1. **Dwa progi `n_eff`, ustalone z góry.** `≥ 0.5` wejście do dopasowania
   (mecze drużyny poniżej progu wypadają z wiarygodności), `≥ 5` wejście do
   estymacji `τ`. Martwa drużyna nie wnosi informacji, a wnosi wolny
   parametr i kierunek prawie zerowy.
2. **Koniec z `pinv`.** SE z odwrotności hesjanu **z priorem** przez
   Cholesky'ego, rzutowanej na kontrasty centrowane `C·H⁻¹·Cᵀ`. Prior
   domyka dwa kierunki zerowe, więc macierz jest dodatnio określona.
   Cholesky zawodzi **głośno** — i o to chodzi. Cicha pseudoodwrotność
   jest dokładnie tym, co zepsuło przebieg.
3. **Rzut po odwróceniu, nie przed.** Prior wnosi wariancję wzdłuż
   kierunku samych jedynek, która jest artefaktem parametryzacji, nie
   niepewnością czegokolwiek, co raportujemy.

Efekt na oknie, które wywaliło przebieg (`ξ = 0.008`): SE(s) max
9.02 → 0.181, cond 3.7e12 → 3.8e2, `τ_s` 0.0001 → 0.1395.

**Przy okazji — dwie pułapki w samym mierzeniu:**

- `numpy.linalg.pinv` z **domyślnym** `rcond` (~1e-15·λ_max) nie odcina
  nawet dokładnych kierunków zerowych z centrowania: zmierzone wartości
  własne 5.9e-13 przy maksimum 1.2e+04 dawały ujemną diagonalę kowariancji
  rzędu −4e+09, a po `clip` do zera — ciche zero, które udaje „brak szumu"
  i zawyża `τ`. Jawny `rcond` jest konieczny, ale **niewystarczający**:
  przy `ξ = 0.008` kierunki martwych drużyn leżą nad każdym sensownym
  progiem.
- Uwarunkowanie liczy się **bez** dwóch dokładnych kierunków zerowych.
  Branie po prostu najmniejszej dodatniej wartości własnej daje `cond`
  rzędu 1e16 także dla zdrowej macierzy, bo te kierunki wychodzą
  numerycznie jako ±1e-16.

**Czego się z tego nauczyć ogólnie:** estymator, który w zdegenerowanym
przypadku zwraca liczbę z granicy przedziału poszukiwań (u nas `τ` na
dolnym krańcu, w symulacji autora planu na górnym), prawie zawsze dostaje
na wejściu śmieci. Kierunek zapaści zależy od szczegółów implementacji,
więc **bezpiecznik stawia się na przyczynie, nie na skutku**: progiem jest
SE dobrze zmierzonej drużyny, nie sama wartość `τ`.

### 5.32 Bezpiecznik w siatce to co innego niż bezpiecznik w predykcji

Ta sama kontrola, dwa różne znaczenia — i pomylenie ich kosztowało
przebieg.

Po wprowadzeniu wielosezonowego wyboru `ξ` (§5.29) cache musi policzyć
`LL(V, ξ)` dla **każdego** `ξ` z siatki na **każdym** oknie. Wcześniej
`ξ = 0.008` było oceniane rzadko i degenerowało się cicho; teraz
zdegenerowana kombinacja jest odwiedzana systematycznie.

Bezpiecznik, który przerywa cały przebieg, zamienił wtedy **informację o
złym kandydacie** w awarię:

- **kandydat z siatki** — zdegenerowany `ξ` dostaje `LL(V, ξ) = −∞`, wpis
  w logu z diagnostyką, przebieg trwa. Kandydat niedopuszczalny dla
  jednego okna jest niedopuszczalny dla każdego `S > V`, więc `−∞`
  propaguje się samo. **Zły kandydat to wynik, nie wyjątek.**
- **dopasowanie z wybranym `ξ`** (predykcja) — bezpiecznik podnosi
  wyjątek, jak dotąd. Tutaj nie ma alternatywy do wyboru; model, którego
  nie da się dopasować, nie ma czym przewidywać.

Odrzucenie **wszystkich** kandydatów to z kolei błąd, nie wybór — wtedy
też wyjątek.

Reguła ogólna: zanim postawisz bezpiecznik, zapytaj, czy stoi na ścieżce
**wyboru** czy **wykonania**. Na ścieżce wyboru awaria jednego wariantu
jest daną. Na ścieżce wykonania jest awarią.

### 5.33 Po poprawce C przestrzeliliśmy w drugą stronę

Zapis stanu na 2026-10-01, żeby nie szukać tego od nowa.

Pierwotny problem: predykcje sumy goli **za szerokie**, nachylenie wobec
celu rynkowego 0.37. Po reparametryzacji `(s, o)` i empirical Bayes:
nachylenie **2.21** `[1.59, 2.73]`, czyli predykcje są teraz za **wąskie**
ponad dwukrotnie.

```
sd(T_nasze)  = 0.0757     sd(T_rynek po Shinie) = 0.3060
r(T_nasze, T_rynek) = 0.546      r(T_nasze, wynik) = 0.074
```

Dwie rzeczy warte zapamiętania:

1. **Cel rynkowy ma moc, wynik nie ma.** `r = 0.55` wobec `r = 0.07`,
   połowa szerokości CI 0.57 wobec 0.84 przy n = 2944. Konstrukcja z §11.4
   (własność wieży, suma goli implikowana z 1X2 Pinnacle) działa dokładnie
   tak, jak miała.
2. **`sd(T_rynek) = 0.31` uściśla szacunek z §5.24.** Dekompozycja
   wariancji dawała `sd` prawdziwej oczekiwanej sumy goli ~0.14 z górną
   granicą ~0.4. Rynek plasuje się w tym przedziale, blisko górnego
   krańca. Nasze 0.076 jest **poniżej** niego, więc kompresja poszła za
   daleko — ale uzasadnienie z §5.24 pozostaje w mocy: luzowanie ściągania
   „żeby model miał opinię" to nie ta droga. Drogą jest lepsza informacja.

Kontrola odporności: nachylenie przy `ρ = 0` wynosi 1.75 wobec 2.21 przy
`ρ` modelu, czyli różnica **0.46** — znacznie powyżej progu 0.15 z §11.4.
Forma funkcyjna `ρ` ma na ten pomiar realny wpływ i interpretując
nachylenie co do drugiego miejsca po przecinku trzeba o tym pamiętać.

---

### 5.34 „Brak mocy" to nie to samo co „wynik poza pasem"

Błąd w mojej własnej regule decyzyjnej, złapany dopiero przy stosowaniu jej
do danych. Wart zapamiętania, bo łatwo go powtórzyć przy każdej bramce z
pasem akceptacji.

Pierwsza wersja §11.8 mówiła: „połowa szerokości CI > 0.3 → brak mocy →
stop". Przebieg `313591a` dał nachylenie **2.21 [1.59, 2.73]**, czyli
połowę szerokości 0.57 — formalnie „brak mocy". Ale CI **w całości leży
poza pasem** `[0.8, 1.5]`. To nie jest pomiar, który niczego nie
rozstrzyga; to pomiar, który rozstrzyga jednoznacznie, tylko na „nie".

**Poprawna definicja:** brak mocy = przedział obejmuje jednocześnie punkt
w pasie i punkt poza nim. Wtedy nie wiadomo, po której stronie jesteśmy.
Przedział w całości poza pasem to **wynik niezaliczony**, nie brak mocy —
i do raportu wchodzi jako „za wąsko", a nie jako „nie dało się zmierzyć".

Różnica jest praktyczna, nie językowa. „Brak mocy" każe szukać mocniejszego
instrumentu albo większej próby. „Niezaliczone" każe zająć się modelem. To
dwie zupełnie inne listy zadań.

### 5.35 Suma goli wyprowadzona z 1X2 jest wrażliwa na `rho` — ale instrument działa

Suma goli implikowana z rynku 1X2 (`implied_goal_rates`) zależy od formy
funkcyjnej, bo odwracamy przez naszą własną macierz DC. Zmierzone na
Ekstraklasie: nachylenie G4(c) wynosi **2.21** przy `rho` modelu i **1.75**
przy `rho = 0`. Różnica 0.46, trzykrotnie powyżej progu odporności 0.15.

Stąd pytanie, czy instrument w ogóle mierzy to, co ma mierzyć. Ekstraklasa
nie pozwala tego sprawdzić — `POL.csv` nie ma kursów O/U. Premier League
pozwala: ma zamknięcie Pinnacle i dla 1X2 (`PSCH/PSCD/PSCA`), i dla totali
(`PC>2.5` / `PC<2.5`), czyli **dwa niezależne odczyty tej samej wielkości**.

Wynik na 2269 meczach, 6 sezonów (kryterium spisane przed pomiarem:
`sd(T_1x2)/sd(T_ou) ∈ [0.8, 1.25]` i korelacja `≥ 0.7`):

```
wariant        sd(T_1x2)  sd(T_ou)  stosunek  korelacja  nachylenie T_ou~T_1x2  ważny
rho = 0          0.451     0.403      1.119     0.936     0.836 [0.808, 0.860]  TAK
rho = -0.0702    0.488     0.403      1.211     0.940     0.777 [0.754, 0.797]  TAK
```

**Oba warianty ważne**, więc G4(c) jest ważnym instrumentem i jego wynik
stoi. Trzy rzeczy do zapamiętania:

1. **Poziom rozstrzyga między wariantami, choć kryterium tego nie robi.**
   Przy `rho = 0` średnia `T_1x2` to 2.616 wobec 2.902 z rynku totali —
   zaniżenie o 0.29 gola. Przy `rho` median Ekstraklasy: 2.9019 wobec
   2.9016, czyli trafienie co do trzeciego miejsca. Wariant z `rho` modelu
   jest lepiej wyspecyfikowany, mimo że kryterium ważności go nie
   wyróżnia.
2. **Instrument zawyża rozrzut o 12–21%** (`sd_ratio` 1.12–1.21,
   nachylenie `T_ou` na `T_1x2` poniżej 1). Zapisana wielkość kompresji
   Ekstraklasy to więc nachylenie 2.21, ale skorygowane o własne
   zawyżenie instrumentu wychodzi bliżej **1.8×**. Kierunek („za wąsko")
   jest pewny w obu wariantach i po korekcie; wielkość należy podawać z
   tym zastrzeżeniem.
3. **Korelacja 0.94 przy 2269 meczach** — instrument jest precyzyjny.
   Połowa szerokości CI nachylenia to 0.02–0.03, czyli o dwa rzędy lepiej
   niż cokolwiek mierzonego względem wyniku.

### 5.36 DC zamknięte jako model 1X2 — i tylko 1X2

Decyzja z 2026-10-01, przebieg `313591a`. Zawężamy roszczenie, nie
przesuwamy bramki.

**Co jest zamknięte i dlaczego wolno:**
- bezpieczniki zielone: cond 50–1974, zero odrzuconych kandydatów `ξ`,
  `τ_s` 0.112–0.139;
- 1X2 na poziomie Elo: DC − Elo `+0.0001 [−0.0031, +0.0048]`;
- remisy skalibrowane **względem rynku**: nachylenie `q_X` rynku na nasze
  `P(X)` to `1.08 [0.94, 1.36]`, `r = 0.61`. W tym, co rynek wycenia
  wprost, jesteśmy na miejscu.

**Czego NIE wolno z tej macierzy liczyć:** totali, handicapów azjatyckich
ani kombinacji. Nachylenie 2.21 (po korekcie ~1.8) znaczy, że prognoza
sumy goli jest za mało rozproszona, a `sd P(Over 2.5) = 0.019` — prognoza
praktycznie stała. Model nie ma zdania o totalach i udawanie, że ma,
produkowałoby fałszywe sygnały dokładnie tam, gdzie wariancja jest
największa.

**Dlaczego nie „podkręcamy" `τ_o`.** Podniesienie rozrzutu otwartości albo
rozciągnięcie prognoz do rynku zaliczyłoby bramkę z definicji i nie dodało
ani bitu informacji. To dopasowanie modelu do bramki po obejrzeniu wyniku.
`τ_o` 0.02–0.04 to **uczciwy wynik**: z samych wyników meczów prawie nie
da się odróżnić „otwartości" drużyn. Totale skalibrowane do rynku bierzemy
wprost z rynku — po to jest kolektor.

**Rozkład na osie** (§11.10 B) pokazuje, gdzie dokładnie siedzi kompresja:

```
oś                       nachylenie rynek~my (rho modelu)   r      sd my / sd rynku
A = log λ + log μ  (otwartość)   3.06 [1.78, 3.95]        0.50    0.036 / 0.220
B = log λ − log μ  (przewaga)    1.21 [1.04, 1.38]        0.81    0.293 / 0.440
```

Za wąska jest **otwartość**, nie relacja przewaga → gole. Oś przewagi jest
prawie skalibrowana (1.21) i dobrze skorelowana (0.81); oś otwartości jest
ściśnięta sześciokrotnie w `sd` i słabo skorelowana. To jest treść zdania
„DC jest modelem 1X2, nie modelem totali".

**M2 — model nie wnosi informacji ponad rynek.** Pula logarytmiczna
Pinnacle po Shinie + DC, waga dobierana walk-forward wyłącznie na
sezonach wcześniejszych (Pinnacle jawnie jako cel shrinkage, reguła 19):

```
LL puli 1.0395   LL samego Pinnacle 1.0380   LL samego DC 1.0529
pula − Pinnacle: +0.0015 [−0.0003, +0.0040]   górna granica > 0
waga modelu per sezon: mediana 0.138, max 0.453, dwa sezony 0.000
```

Kryterium z §11.10 C („górna granica CI < 0") **niespełnione**. Model
zostaje w portfolio; jego rola pieniężna ogranicza się do kombinacji
wycenianych z danych rynkowych. To był uczciwie zapowiedziany wynik —
przy luce Elo − Pinnacle +0.0145 i DC ≈ Elo niczego innego nie należało
oczekiwać.

### 5.37 Audyty toru S i FSA #0 — bezpiecznik, którego da się nie podać, nie istnieje

Audyty: `AUDIT_REPORT.md` (krok 3, 2026-09-30), `AUDIT_REPORT_2.md` (tor S,
2026-10-01, naprawy w `eac437c`: 2 KRYTYCZNE, 9 POWAŻNYCH) i FSA #0
(`reports/audit/FSA_2026-10-01_F0.md`: 0 KRYTYCZNYCH, 18 POWAŻNYCH, 14
DROBNYCH; naprawy 2026-10-02 według `docs/FSA0_NAPRAWY.md`, log
`reports/audit/FIX_LOG_F0.md`). Wnioski, które obowiązują przy każdym
nowym kodzie:

**(a) Opcjonalny bezpiecznik = brak bezpiecznika → reguła 30.** Naprawy z
`eac437c` dodały `as_of=None` (CLV), `kickoffs=None` (wycena) i publiczny
konstruktor `KellyPolicy` — każdy dało się pominąć, a pominięcie
otwierało look-ahead (CLV −1.0% → +9.5%) albo podwajało stawkę (c = ½
bez raportu CLV). Teraz parametr-bezpiecznik jest wymagany, keyword-only,
bez `None`; pilnuje `tests/test_rule30_guards.py`.

**(b) Zielony test ścieżki bezpiecznej nie jest dowodem → reguła 31.**
`half_kelly_requires_the_gk_gate_not_a_flag` i
`pricing_refuses_after_kickoff_when_given_kickoffs` były zielone przy
otwartej dziurze, bo testowały wyłącznie wariant z podanym argumentem.
Naprawa zaczyna się od testu ścieżki niebezpiecznej, czerwonego na starym
kodzie z powodu zachowania; dowodem jest rewers.

**(c) Komunikat commita nie zastępuje weryfikacji kodem.** Dwie deklaracje
z `eac437c` były nieprawdziwe: „`from_journal` to jedyna droga do c = 0.5”
(F-19) i „`validate_instrument` woła `assert_no_lockbox`” (F-21). Audyt
sprawdza kod, nie opis.

**(d) Druga implementacja tej samej logiki → reguła 28.**
`BetJournal.real_turnover` liczył obrót bez odcięcia czasowego obok
naprawionej wersji w `ev.py` — ten sam mechanizm co KRYT 1 (F-03). Jedna
funkcja, jedno miejsce (`ev.real_turnover`), a konsumenci pracują na
kuponach z `live.bets.coupons` (F-02: wiersze jako „single” dawały udział
AKO strukturalnie 0 i obrót AKO liczony N razy).

**(e) Regulamin Betclica — udział po stawkach (§3 ust. 5, cytat wstępny).**
`CONTEXT.md` §2 mówił „50% kuponów”; regulamin mówi o udziale stawek.
Decyzja Pawła 2026-10-02: kod liczy wariant najmniej korzystny dla gracza
(oba udziały ≥ 50%, okno 12 miesięcy kalendarzowych, AKO z różnych meczów,
wielokrotny niekwalifikujący się 0.88) — `docs/promocje.md`,
`BETCLIC_READING = "pesymistyczny-2026-10-02"`. Weryfikacja słowo w słowo
niewykonana: robots.txt hosta PDF zwraca 403.

**(f) A-01 i A-02 — dwie dziury znalezione w przeglądzie specyfikacji.**
A-01: zamknięcie kluczowane samym meczem dawało jedno `p_close` dla
wszystkich zakładów na mecz — test znanej odpowiedzi Filaru 1 by padł;
klucz to teraz `(match_id, market, outcome, line)`. A-02: podatek 10% od
wygranej powyżej 2280 zł nie był modelowany nigdzie; teraz osobny
`winnings_factor` ∈ {1.00, 0.90} w EV, progu, Kellym i rozliczeniu.

### 5.38 FSA #0b–#0e — naprawa zamyka scenę, sąsiednia ścieżka zostaje

Audyty powtórkowe wyjścia z Filaru 0: FSA #0b, #0c, #0d (2026-10-03) i
runda dodatkowa FSA #0e (`reports/audit/FSA_2026-10-04_F0e.md`, linia
`BRAMKA: KRYT=0 POWAŻNE=0`). Bramka F0 → F1 otwarta 2026-10-07 (wpis w
`reports/audit/FIX_LOG_F0.md`). Wnioski:

**(a) Test opisuje wynik, nie scenę.** Kolektor trzy rundy z rzędu
(F0b-01, F0c-02, F0d-01) potrafił zamilknąć, bo każda łatka zamykała
konkretny scenariusz audytora. Zamknęło to dopiero usunięcie przyczyny
(terminarz wyłącznie z bezpłatnego `/events`) i niezmiennik na 500
losowych światach: po gwizdku każdy mecz ma zamknięcie albo wpis
`closing_missed` z prawdziwym powodem. Niezmiennik musi wykrywać mutacje
(FSA #0e 0.6: 4/4).

**(b) Kalkulator to symulacja prawdziwego kodu, nie formuła obok niego.**
Własna formuła budżetu liczyła migawki decyzyjne tylko w dni z meczem —
plan ~456 wydrukowany jako 430 (F0e-01, reguła 28 w duchu). Teraz
`scripts/odds_budget.py` przechodzi prawdziwym `due_calls` co 5 min; po
usunięciu T-24h Ekstraklasy 374/mies.

**(c) Ten sam byt, inny napis.** Kanonizacja nazw rynku (F0d-04) nie
objęła wyniku (`Draw`/`draw`, nazwy drużyn) — F0e-03, przed ingestem
Filaru 1.

**(d) Odstępstwo od decyzji „do akceptacji” nie przechodzi przez bramkę
automatycznie** (F0e-05). Akceptacja Pawła z 2026-10-04 jest warunkowa
(zawężenie niezmiennika z licznikiem i luką heartbeatu, szósty powód dla
HTTP 4xx poza 429) — do wykonania przed Filarem 2.

**(e) Środowisko jest częścią systemu.** Tryb gry Avasta wyłącza zadanie
kolektora przy każdym obciążeniu CPU (F0e-04); luka widoczna w
heartbeacie, przyczyna w `docs/task_scheduler.md`.

---

## 6. KROK 3 — co masz zrobić

### Najpierw: zweryfikuj stan repo

```bash
uv run pytest -q          # oczekiwane: 199 passed
uv run ruff check src tests
uv run mypy src
```

Jeśli którykolwiek pada — **zatrzymaj się i zgłoś**, zanim cokolwiek
dopiszesz. Środowisko było zweryfikowane 2026-09-21 na tej maszynie i
było zielone.

### Zadanie 0 (po stronie Pawła — przypomnij mu)

Kolektor jest gotowy, ale **nic jeszcze nie zbiera**:
1. Klucz z `dashboard.api-football.com/register` → `.env`
   (skopiuj `.env.example` do `.env`)
2. **Zweryfikować ID lig** w `api-football.com/coverage` — w kodzie jest
   106 (Ekstraklasa) i 107 (1. liga) wpisane z pamięci, mogą być
   nieaktualne. Zły numer = cichy pusty przebieg.
3. Zadanie w Harmonogramie zadań Windows co 30 min (README ma wariant
   cronowy; na Windowsie użyj Task Scheduler)
4. Po dwóch dniach sprawdzić, czy archiwum rośnie

### Zadanie 1: `ingest/football_data.py`

Źródło: **football-data.co.uk**, sekcja „extra leagues", plik dla Polski
(`https://www.football-data.co.uk/new/POL.csv` — **zweryfikuj URL i
faktyczne nazwy kolumn, nie zakładaj**; format „extra" różni się od
głównych lig i bywa zmieniany).

Spodziewane kolumny: `Country, League, Season, Date, Time, Home, Away,
HG, AG, Res` plus kursy `PH/PD/PA` (Pinnacle), `MaxH/MaxD/MaxA`,
`AvgH/AvgD/AvgA`. **Sprawdź nagłówek pobranego pliku i dostosuj parser do
tego, co faktycznie jest.** Jeśli kolumny Pinnacle nie występują —
powiedz o tym, bo to zmienia plan CLV.

Wymagania:
- Zapis do `data/raw/football_data/` w parquet, z `ingested_at` i `source`
- **`data/raw/` jest niemodyfikowalne** — nie nadpisuj istniejących plików
- Transformacje do `data/interim/`
- `match_id` przez `schema.make_match_id`
- Nazwy drużyn przez `TeamResolver`, **nigdy fuzzy w miejscu wywołania**
- Wyjście zgodne z `schema.Match`

**PUŁAPKA CZASOWA — najważniejsza rzecz w tym zadaniu.**
football-data podaje `Date` i `Time` w **czasie lokalnym brytyjskim**, z
DST. Naiwna konwersja da przesunięcie o 1–2h, co przy regule
`asof_utc = kickoff − 2h` potrafi przerzucić mecz na drugą stronę granicy
odcięcia.

```python
naive = pd.to_datetime(df["Date"] + " " + df["Time"], format="%d/%m/%Y %H:%M")
kickoff_utc = (
    naive.dt.tz_localize("Europe/London", ambiguous="NaT", nonexistent="NaT")
         .dt.tz_convert("UTC")
)
```

Wiersze z `NaT` (godziny dwuznaczne przy zmianie czasu) **raportuj, nie
odrzucaj po cichu**. Wiersze bez `Time` — zdecyduj świadomie i
**udokumentuj decyzję w kodzie**; domyślnie odrzuć i policz, ile ich jest.

### Zadanie 2: raport pokrycia nazw

Przed jakimkolwiek modelowaniem:

```python
resolver.resolve_many(all_team_names)
print(f"coverage: {resolver.coverage():.2%}")
for u in resolver.report_unresolved():
    print(u.raw, u.occurrences, u.suggestions)
```

Uzupełnij `data/team_aliases.yaml` **ręcznie**, aż `coverage()` = 1.00
albo pozostałe nazwy będą świadomie odrzucone (np. drużyny z pucharów).
Dopiero potem dalej.

`team_aliases.yaml` ma dziś 21 klubów. Dziesięć sezonów Ekstraklasy to
znacznie więcej — dojdą spadkowicze i kluby, których już nie ma
(Podbeskidzie, Arka Gdynia, Bruk-Bet Termalica, Wisła Kraków po spadku,
Sandecja, Nieciecza...). **Drużyny, które zniknęły z ligi, MUSZĄ zostać w
zbiorze** — ich usunięcie to survivorship bias (punkt D22 listy audytora).

### Zadanie 3: pierwszy realny przebieg Elo

```python
result = compute_elo(matches, EloConfig())
```

na pełnej dostępnej historii Ekstraklasy, z kolumną `season`.

Sanity check:
- Czy `sum(final.values()) ≈ 1500 * n_teams`?
- Czy ranking końcowy przypomina rzeczywistą hierarchię?
- Czy `history()` nie ma skoków sugerujących błąd w danych?

### Zadanie 4: diagnostyka kalibracji — właściwy cel kroku 3

**To jest pierwsza uczciwa informacja o tym, czy projekt ma sens.**

Zbuduj `backtest/metrics.py` i policz:

**a) Reliability diagram.** Podziel `elo_expected_home` na 10 koszyków,
porównaj przewidywaną częstość z rzeczywistą. Jeśli Twoje „70%" wygrywa
62% czasu, model jest bezużyteczny niezależnie od reszty metryk.

**b) Log loss vs trzy baseline'y**, na tych samych meczach:

| Model | Opis |
|---|---|
| stała | częstości bazowe 1X2 z trainu |
| Elo | `elo_expected_home`, rozbite na 1X2 |
| rynek | zamknięcie Pinnacle **po Shinie** |

Uwaga techniczna: Elo daje wynik w skali [0,1] (remis = 0,5), a nie
rozkład na trzy wyniki. Potrzebujesz mapowania Elo → (P(1), P(X), P(2)).
Najprostsze uczciwe podejście: regresja porządkowa albo dopasowanie
funkcji remisu `P(X) = f(|elo_diff|)` na trainie. **Dopasuj ją
walk-forward, nie na całym zbiorze.**

**c) CLV vs zamknięcie Pinnacle po Shinie.** Metryka nadrzędna.

### Czego się spodziewać — i co z tym zrobić

**Oczekiwany wynik: Elo NIE pobije rynku.** To jest prawidłowy rezultat,
nie porażka. Rynek to wypadkowa wszystkich pieniędzy, w tym syndykatów z
modelami lepszymi niż samo Elo.

Wartość diagnostyczna jest w **wielkości luki**:
- Luka mała (log loss gorszy o <0,01) → Elo zaskakująco dobre, warto
  dokładać cechy.
- Luka duża (>0,03) → sama forma i Elo nie wystarczą, potrzebny model
  golowy (Dixon-Coles) zamiast ratingowego.

**Raportuj bezwzględnie:** `n` meczów, przedział ufności, i jawnie
„model nie bije rynku o X" zamiast szukania pozytywnego sformułowania.

**Jeśli Elo pobije rynek — to jest bug, nie odkrycie.** Szukaj przecieku
przed raportowaniem. Najbardziej prawdopodobne przyczyny: kurs zamknięcia
jako wejście, brak walk-forward, mecze z trainu w teście.

### Na koniec kroku 3

```bash
uv run pytest -q
uv run pytest -k future_poison -v
uv run ruff check src tests
uv run mypy src
```

Plus uruchom subagenta `backtest-auditor` na `features/` i `backtest/`.

### Co przyjdzie po kroku 3

Nie zaczynaj bez zamknięcia kroku 3:
- `pricing/ev.py` + `pricing/kelly.py` (reguły 20–23)
- `models/dixon_coles.py` z time decay (ξ ≈ 0,003/dzień)
- `models/hierarchical.py` (PyMC) dla lig z małym samplem
- `backtest/walk_forward.py`
- `live/` — poller `httpx`, detektor value, alerty Telegram

---

## 7. Czego NIE robić — lista kontrolna

- ❌ Nie pisz clickera ani kodu logującego się na konto bukmachera.
- ❌ Nie używaj normalizacji proporcjonalnej `(1/k)/Σ(1/k)` w kodzie
  produkcyjnym.
- ❌ Nie zastępuj solvera Brenta iteracją punktu stałego (5.1).
- ❌ Nie „uprość" granicy `z → 0` do `πᵢ/P` (5.2).
- ❌ Nie usuwaj `_LETTER_MAP` ani nie przestawiaj jej po NFKD (5.5).
- ❌ Nie włączaj automatycznej akceptacji fuzzy matchingu (5.7).
- ❌ Nie wektoryzuj Elo (5.12).
- ❌ Nie używaj `train_test_split` ani `KFold` bez wariantu czasowego.
- ❌ Nie wypełniaj NaN w cechach średnią globalną.
- ❌ Nie dodawaj kursu rynkowego jako cechy modelu.
- ❌ Nie używaj kursu zamknięcia jako ceny wejścia (tylko do CLV).
- ❌ Nie raportuj yieldu bez `n` i przedziału ufności.
- ❌ Nie używaj `accuracy` jako metryki jakości modelu.
- ❌ Nie usuwaj drużyn, które zniknęły z ligi.
- ❌ Nie używaj historii kontuzji z Transfermarktu w backteście.
- ❌ Nie wyłączaj reguły `DTZ` w ruff.
- ❌ Nie używaj `pip` — projekt stoi na `uv`.

---

## 8. Jeśli kod przepadł

Sekcja 5 zawiera wszystkie wzory, krytyczne fragmenty i pułapki —
wystarczająco, żeby odtworzyć każdy moduł od zera. Kolejność:

1. `schema.py` (sekcja 4 + 5.17)
2. `pricing/shin.py` (5.1–5.4) — z testem round-trip
3. `ingest/team_mapping.py` (5.5–5.7)
4. `features/base.py` (5.8–5.11) — z testem trucizny (5.16)
5. `features/elo.py` (5.12)
6. `ingest/snapshots.py` (5.13–5.15)

Przy każdym module pisz testy **przed** uznaniem go za gotowy. Testy w
tym projekcie znalazły trzy realne błędy matematyczne, których żaden
przegląd kodu by nie wyłapał.
