# BACKTEST_FIN_PLAN.md — Filar 1: historyczny backtest finansowy

Spisane 2026-10-01, 22:50, na żądanie Pawła: zanim cokolwiek pójdzie na
żywo, silnik wyceny (fair → EV → Kelly → dziennik → CLV) przechodzi przez
historię. Obowiązuje z `CLAUDE.md` (reguły 27–31) i `ROADMAP.md` §0.

**Zmiany 2026-10-02, po FSA #0, przed jakimkolwiek wynikiem:** §1 (lockbox,
sieć, manifest), §3 (bramka G-K tylko raportowana; podatek od wygranej;
strategia C wg `docs/promocje.md` i jej konstrukcja), §4 pkt 2 (placebo
przez wstrzyknięcie), §6 (definicja alarmu), §7 (kroki 1 i 4a). Żadna nie
wynika z obejrzanych liczb — backtest jeszcze nie istnieje.

**Zmiany 2026-10-10 po audycie 4a, przed jakimkolwiek wynikiem** (decyzje
Pawła, `docs/discovery/CLI_task_audit_4a_decisions.md`; audyt:
`reports/backtest_fin/5831a92/AUDIT_4a.md`; nic nie uruchomiono na
prawdziwych danych — żadna decyzja nie wynika z wyniku strategii):

- §3, wszystkie strategie — **wiarygodność kursu** (A4a-01), progi zamrożone
  teraz: (a) kwotowanie bukmachera z booksum < 1.00 w migawce decyzyjnej
  wypada z best-of dla meczu i rynku (bez E — kolumna `Max` to nie
  kwotowanie jednego bukmachera); (b) zakład z EV przy podatku 1.00 względem
  fair Pinnacle > 0.50 — odrzucony (także E). Tylko migawka decyzyjna; licznik
  odrzuceń per liga / sezon / reguła w raporcie, flaga > 0.5% meczów ligi.
- §3, **D — jawne odstępstwo**: D = zakłady A (wybór i stawka przy 1.00)
  **rozliczone** przy 0.88; kontrola podatku, nie strategia do zagrania.
  Plan mówił „jak A przy 0.88” — przy wyborze na 0.88 zysk D byłby
  oczekiwany przy działającej przewadze, a alarm „zysk w D” fałszywy.
- §3 — **jedno źródło podatku** (FSA4a-01): `Strategy.selection_tax` /
  `settlement_tax`, przebieg przez `strategies.run_strategy`; niezgodny
  selektor i podatek wyboru → wyjątek.
- §3/§6, **C — poza bramką §4 i poza werdyktem**: „GÓRNA GRANICA, nie
  zbadana bramką”; liczby C w raporcie z etykietą „bez dowodu poprawności”;
  alarm 8% zostaje jako detektor błędu. Pełna ścieżka testów 1–7 dla C — przy
  poprawce `pricing/ev.py` (F1-P01, warunek startu Filaru 2). **Werdykt
  Filaru 1 opiera się wyłącznie na A.**
- §4 pkt 4 — trucizny 4b i 4c porównują **listy postawionych zakładów**
  (FSA4a-02): 4b — (mecz, rynek, wynik, kurs) identyczne po permutacji
  wyników, stawki wg wzoru Kelly'ego dla kapitału w danej chwili; 4c — lista
  do dnia D z kursem i stawką identyczna w obie strony.

**Zmiany 2026-10-11 (wariant B, decyzja Pawła, przed jakimkolwiek wynikiem)**
(`docs/discovery/CLI_task_wariant_B.md`, `CLI_task_wariant_B_rownolegle.md`,
odpowiedzi Pawła w czacie 2026-10-11; nic nie uruchomiono na prawdziwych
danych — żadna zmiana nie wynika z wyniku strategii). Zastępują punkt
„C — poza bramką §4 i poza werdyktem” z 2026-10-10.

- **Werdykt Filaru 1 ma trzy części** (§6):
  1. **Logika toru S** — strategia A, kryteria §6 bez zmian.
  2. **Reżim Betclica** — strategia C (`single_mode = production`), wszystkie
     ligi razem: POTWIERDZONA / NIEPOTWIERDZONA / OBALONA według tych samych
     kryteriów co A (średnie CLV z CI klastrowanym po tygodniach ISO, yield
     punktowy). CLV kuponu wielokrotnego = `Π_i (k_i · p_close_i) · tax − 1`,
     gdzie `p_close_i` to Shin z zamknięcia Pinnacle, a `tax` — podatek reżimu
     kuponu (CLV po podatku); singiel tak samo (`k · p_close · tax − 1`) —
     *korekta 2026-10-11 17:20, PRZED jakimkolwiek wynikiem, zgodność z kodem
     (AB-5)*.
  3. **Pojedynczy bukmacherzy** — B365, B-BW, B-WH: raport z CI, bez
     osobnego werdyktu.
- **Rekomendacja dla Filaru 2 (spisana przed wynikiem):** A i C POTWIERDZONE →
  Filar 2 na Betclicu w reżimie Bez Podatku 2.0 uzasadniony. A POTWIERDZONA,
  C nie → edge istnieje, ale reżim Betclica go nie przenosi: Filar 2 na
  Betclicu nieuzasadniony, decyzja Pawła o alternatywie jako osobny plan.
  A NIEPOTWIERDZONA / OBALONA → jak w §6.
- **Reżim produkcyjny = regulamin** (F1-P01 pkt 1–3 naprawione w
  `pricing/ev.py`): udział AKO wyłącznie po wartości stawek (§3 ust. 5), próg
  „co najmniej 50%” (T5, ≥ 0.50); przed zakładem zostaje jakakolwiek kwota
  limitu 1000 zł → cały zakład w ofercie (§3 ust. 4); wielokrotny
  niekwalifikujący się → 0.94 przy udziale < 50%, 1.00 przy ≥ 50% (§3 ust.
  11.1, 12). Wariant „po stawkach **i** po kuponach” (margines Pawła z
  2026-10-02) — **tylko raport wrażliwości** C.
- **Bramka §4 obejmuje C** — testy 1–7 dla C (szczegóły w
  `scripts/engine_tests.py` i `ENGINE_TESTS.md`), 200 nasion w teście 1 C
  (decyzja Pawła 2026-10-11).
- **Minimalna stawka 0,50 zł we wszystkich strategiach** (decyzja Pawła
  2026-10-11; Szczegółowe zasady Betclic pkt 3.1, T12): stawka Kelly'ego
  < 0,50 zł → zakład **pominięty** (nie zaokrąglany w górę), licznik pominięć
  w raporcie. Dotyczy też A, B, D, E i live.
- **Wariant informacyjny „kapitał 1000 zł”:** A i C z kapitałem 1000 zł
  (stały kapitał projektu na Filar 3, decyzja Pawła 2026-10-11); stawka
  < 0,50 zł → pominięta, licznik. Tylko raport. Przebieg główny — umowne
  10 000 zł bez zmian (§3).
- **Alarmy §6 bez zmian**; C podlega alarmowi yield > 8%.
- **Etykieta C:** zamiast „GÓRNA GRANICA, T12 nieznane” → „kontrfaktyczny
  reżim Betclica (promocja od początku symulacji, limit 1000 zł wykorzystany),
  kursy zastępcze B365/BW”. T12 w konfiguracji kontrfaktycznej:
  `min_stake_pln = 0.50`, `excluded_markets = []` (T12 zamknięte 2026-10-09).
- **Wybór lig do zbierania na żywo w Filarze 2** (darmowy budżet API = 3 ligi),
  zapis przed wynikami:
  (a) Kwalifikowalność (poza backtestem): liga jest w The Odds API z Pinnacle,
  w ofercie Betclic i w próbce ręcznej Betclic (znana marża).
  (b) Ranking po DOLNEJ granicy CI 95% (klastry: tygodnie ISO) średniego CLV
  strategii A w danej lidze, 7 sezonów łącznie. NIE po zysku ani yield.
  (c) Próg: liga musi mieć ≥ 300 zakładów A w 7 sezonach; poniżej progu nie
  jest rankingowana.
  (d) Wybieramy 3 kwalifikowalne ligi z najwyższą dolną granicą; remis →
  więcej zakładów.
  (e) Wynik to HIPOTEZA wyboru (ranking bez korekty na wielokrotne
  porównania, 22 ligi), nie dowód. Potwierdza ją dopiero Filar 2 (CLV na
  żywo = dane spoza próby).
  Zapis 2026-10-16 (Paweł, przed wynikami; wariant A): reguła (a)–(d) stosowana
  dosłownie. Ekstraklasa nie wchodzi do rankingu (brak jej wśród 22 lig; POL.csv
  tylko zamknięcia → F, informacyjnie), nie ma miejsca zarezerwowanego; może
  wrócić przez Filar 4.
  Runner wypisuje tabelę per liga dla A i C: liczba zakładów, średnie CLV z
  CI 95% (klastry tygodni ISO), yield punktowy, zakładów na tydzień sezonu
  (średnio). Tabela tylko raportowa, bez wpływu na werdykt.

---

## 0. Co ten backtest może udowodnić, a czego nie

**Archiwum kursów polskich bukmacherów nie istnieje w żadnym darmowym,
legalnym źródle.** football-data ma Pinnacle, Bet365, Bet&Win, William Hill,
Interwetten, VC Bet, Betfair, 1xBet oraz średnią i maksimum rynku — żadnego
polskiego bukmachera. The Odds API nie ma polskich bukmacherów w żadnym
regionie. Archiwa typu OddsPortal mają regulaminy zakazujące pobierania
(`COLLECTOR_PLAN.md` §6). Polską historię możemy mieć tylko taką, jaką sami
zbierzemy od teraz (Filar 2).

Dlatego Filar 1 odpowiada na trzy pytania:

1. **Czy silnik liczy poprawnie?** Testy znanej odpowiedzi (§4) — twardy
   dowód, niezależny od rynku. To jest Twoje „101% pewności co do
   poprawności systemu".
2. **Czy logika toru S działa na prawdziwej historii?** Kurs miękkiego
   bukmachera kontra uczciwa cena Pinnacle w chwili decyzji, z prawdziwym
   zamknięciem i prawdziwymi wynikami — na bukmacherach zastępczych (UK/EU),
   22 ligi × 7 sezonów.
3. **Czy „strefa pośrednia" daje więcej okazji niż topowe ligi?**
   Porównanie grup lig — pierwotna teza projektu, pierwszy raz sprawdzalna.

Na co **nie** odpowiada: jak wyceniają polscy bukmacherzy, czy kurs był
dostępny w chwili kliknięcia, jak szybko przychodzą limity, jak działa bet
delay. To zostaje dla Filaru 2.

## 1. Dane

- **Źródło:** football-data, pliki głównych lig, sezony 2019/20–2025/26
  (od 2019/20 są kursy zamknięcia). Wszystkie ligi w tym formacie: Anglia
  E0–E3 i EC, Szkocja SC0–SC3, Niemcy D1–D2, Włochy I1–I2, Hiszpania
  SP1–SP2, Francja F1–F2, Holandia N1, Belgia B1, Portugalia P1, Turcja T1,
  Grecja G1. CLI potwierdza listę i kolumny w nagłówkach.
- **Kolumny** (sprawdzone na E0 2019/20 i 2024/25):
  - przed meczem: `PSH/PSD/PSA` (Pinnacle), `B365*`, `BW*`, `WH*`, wcześniej
    `IW*`, `VC*`, później `BF*`, `1XB*`, plus `Max*`, `Avg*`;
  - O/U 2.5 przed meczem: `B365>2.5`, `P>2.5`, `Max>2.5`, `Avg>2.5`;
  - zamknięcie: te same z „C" — `PSCH`, `B365CH`, `PC>2.5`, `B365C>2.5` itd.
- **Moment kursów sprzed meczu:** według notatek football-data — piątek po
  południu dla meczów weekendowych, wtorek dla środka tygodnia. CLI
  potwierdza w `notes.txt` i zapisuje regułę `observed_at`, **konserwatywnie**
  (najpóźniejszy możliwy moment zbierania). Strefa czasowa godzin meczów —
  też z `notes.txt`; test na kilku meczach o znanej godzinie.
- **Ekstraklasa (`POL.csv`):** wyłącznie zamknięcia → osobny wariant F (§3),
  tylko informacyjnie.
- Ingest przez `ingest/football_data_main.py`, rozszerzony na wszystkie
  ligi; `data/raw/` niemodyfikowalne; `ingested_at` i `source` (reguła 14).
  Koszt: zero.
- Pobieranie wyłącznie przez `valuebet/net/http.py` (≥ 10 s między
  zapytaniami do hosta, robots.txt) i zapis do raw z manifestem sum
  kontrolnych (FSA #0 F-12, F-26). ~150 plików ≈ pół godziny — to jest
  cena zgodności, nie błąd. Pliki już pobrane nie są pobierane drugi raz.
- **Lockbox nie dotyczy Filaru 1.** Lockbox to zbiór toru M (Ekstraklasa,
  2025/26–2026/27), zużyty 2026-10-01 (`ROADMAP.md`, część II). Tutaj nic
  nie jest strojone (§3, §8), więc sezon 2025/26 wchodzi normalnie, a kod
  Filaru 1 nie woła `assert_no_lockbox`.

## 2. Architektura — jedna ścieżka kodu (reguła 28)

```
football-data (raw)
  → backtest/replay.py      wiersz meczu → dwie migawki w formacie S1
                            (decyzyjna i zamknięcia) + wynik, dostępny
                            dopiero po gwizdku
  → backtest/financial.py   pętla zdarzeń po czasie:
       decyzja:     pricing/fair.py → pricing/ev.py → pricing/kelly.py
                    → live/bets.py (dziennik TEGO przebiegu)
       rozliczenie: wynik po gwizdku → kapitał → wyłącznik, bramka G-K
       metryka:     backtest/clv.py
  → reports/backtest_fin/<commit>/<strategia>/  bets.csv, equity.csv, PNG
  → scripts/reconcile_bets.py   niezależne podwójne księgowanie
```

- Backtest woła **te same funkcje** co tryb live. Żadnej kopii logiki.
- Dziennik backtestu to osobny plik per przebieg — nigdy `data/bets/bets.csv`.
- `reconcile_bets.py` (~50 linii) nie importuje modułów wyceny: liczy kapitał
  wprost z `stake`, `odds_taken`, `tax_factor_applied` i wyniku.
- Kapitał do stawki = kapitał w chwili decyzji (gotówka + otwarte stawki po
  koszcie); limit 15% otwartej ekspozycji działa na tej podstawie.

## 3. Strategie — zamrożone przed wynikiem

Wspólne dla wszystkich: `θ = 0.02`; Kelly ¼ z reguły 22 na kursie
efektywnym; limity 2% / 3% / 15%; kapitał startowy 10 000 zł (umowny);
wyłącznik 25%; bramka G-K liczona kodem, jak w live, i **raportowana**
(od którego zakładu by się otworzyła), ale `c` zostaje ¼ przez cały
przebieg — c = ½ jest zablokowane do Filaru 3 (`CLAUDE.md` reguła 21,
FSA #0 F-06/F-19); podatek od wygranej (`docs/promocje.md` T13) we
wszystkich strategiach — jest ustawowy; rynki 1X2 i O/U 2.5; kilka wyników
z jednego meczu dozwolone w limicie meczu.

| | strategia | kursy | podatek | rola |
|---|---|---|---|---|
| **A** | **główna** | najlepszy z B365, BW, WH (obecni we wszystkich sezonach) | 1.00 | proxy trzech kont bez podatku |
| B | jeden bukmacher | B365, BW, WH — każdy osobno | 1.00 | proxy jednego konta |
| C | reżim Betclica | jak A | `BetclicTaxRegime` wg regulaminu (udział AKO po stawkach; od 2026-10-11 — wcześniej wariant pesymistyczny po stawkach **i** po kuponach, teraz tylko wrażliwość); kontrfaktycznie od początku symulacji, próg 1000 zł uznany za wykorzystany; dublety z nóg value z różnych meczów tej samej migawki | test reżimu w działaniu |
| D | kontrola podatku | jak A | 0.88 | **musi tracić** — zysk = alarm błędu |
| E | górna granica | `Max` | 1.00 | nieosiągalna (najlepszy z dziesiątek notowań) — tylko porównanie |
| F | Ekstraklasa | `B365C` vs `PSC`, zamknięcie vs zamknięcie | 1.00 | informacyjnie: na zamknięciu nie da się zagrać po kursie zamknięcia |

- O/U 2.5: jedynym miękkim bukmacherem w plikach jest B365 — w A, B i C
  O/U idzie wyłącznie przez B365.
- **Konstrukcja C** (zamrożona): nogi value z jednej migawki decyzyjnej
  (EV ≥ θ przy 1.00), posortowane po EV malejąco, potem po `match_id`,
  łączone zachłannie w pary z **różnych** meczów, każda noga ≥ 1.20; dublet
  wchodzi, gdy jego EV (`Π(p_i·k_i) · 1.00 − 1`) ≥ θ; nieparzysta reszta i
  nogi bez pary → single. Noga nie występuje jednocześnie w dublecie i w
  singlu. Stawka dubletu: Kelly ¼ na kursie `Π k_i` przy `p = Π p_i`, limit
  2%; ekspozycja meczowa: **pełna** stawka dubletu doliczona do każdego z
  dwóch meczów. Podatek wyceniany w kolejności z `docs/promocje.md` T3:
  najpierw single, potem dublety.
- Wrażliwość — tylko raport, nie wybór: `θ ∈ {0.01, 0.03, 0.05}`.
- Grupy lig: najwyższe (E0, D1, I1, SP1, F1) vs „strefa pośrednia"
  (wszystkie pozostałe).
- **Zakaz strojenia:** żaden parametr nie zmienia się po obejrzeniu wyników.

## 4. Testy poprawności silnika — twarda bramka

Uruchamiane **przed** pierwszym przebiegiem strategii. Czerwone → stop i
raport, bez oglądania wyników strategii.

1. **Znana odpowiedź.** Syntetyczny świat na prawdziwym terminarzu (podzbiór:
   E0 i E1, sezony 2022/23–2023/24, ~1 300 meczów): `p_true` = Shin z
   zamknięcia Pinnacle; kursy Pinnacle w obu migawkach odtworzone z `p_true`
   przez `shin_forward` (marża ~2.5%), więc Shin zwraca dokładnie `p_true`;
   wyniki losowane z `p_true`; kurs miękki = `(1 + e) / p_true`, `e = 0.025`.
   200 nasion; Shin liczony raz na mecz i współdzielony. Zaliczone, gdy:
   - CLV każdego zakładu = `e` z dokładnością Shina;
   - średnia z nasion (zysk zrealizowany − Σ stawka·e) mieści się w ±2 SE od 0.
2. **Placebo.** Kurs = `0.95 / p_true` → zero zakładów przy `θ = 0.02`;
   zakłady wymuszone → yield −5% ± 2 SE. Wymuszenie przez wstrzyknięcie:
   `financial.run(*, selector, staker, …)` — oba parametry wymagane; test
   podaje selektor „każdy wynik” i stawkę płaską, przebieg produkcyjny —
   selektor progu `k_min` z `pricing/ev.py` i stawkowanie z
   `pricing/kelly.py` (pilnuje tego test szpiegów, pkt 7). `θ` zostaje
   walidowane jako ≥ 0 — ujemny próg nie istnieje.
3. **Podatek.** `e = 0.10` przy podatku 0.94 → yield `1.10 · 0.94 − 1 = 3.4%`
   ± 2 SE; `e = 0.025` przy 0.94 → zero zakładów.
4. **Trucizna** (klasa błędu KRYT 2):
   - kolumny zamknięcia zastąpione losowymi → zbiór zakładów i stawki
     identyczne, zmienia się tylko CLV;
   - wyniki spermutowane → decyzje identyczne, zmienia się tylko P&L;
   - mecze po dniu D usunięte → wszystkie decyzje do dnia D identyczne.

   **Zmiana kryterium 4b dla strategii zależnych od ścieżki (2026-10-12).**
   *Co było:* dla C — lista postawionych kuponów (chwila, nogi, kursy)
   identyczna po permutacji wyników, jak dla A (FSA4a-02). *Co jest:* (i)
   kandydaci identyczni; (ii) kupony wspólne obu przebiegów — nogi i kursy z
   klucza, stawka = wzór Kelly'ego z kapitału i ekspozycji odtworzonych z
   księgi TEGO przebiegu, podatek = niezależny checker reżimu; (iii) kupon
   tylko w jednym przebiegu — w drugim wpis odrzucenia
   (`RunResult.dropped_groups`) z przyczyną z listy zamkniętej, potwierdzoną
   niezależnym przeliczeniem z księgi (np. stawka < 0,50 zł); (iv) różnica
   trybu PAPER — tryby obu przebiegów zgodne z obsunięciem 25% z księgi; (v)
   każda inna różnica = czerwony; (vi) inny P&L. *Dlaczego:* w C stawka
   zależy od kapitału, kapitał od wyników przeszłych rozliczeń, a stawka
   < 0,50 zł daje w reżimie 0.88 (T12) i odrzucenie grupy — prawowita
   zależność od ścieżki, nie przeciek (diagnoza:
   `docs/discovery/out_B/diag_4bC.md`, poza gitem). Zmiana po CZERWONYM 4b-C
   na świecie SYNTETYCZNYM bramki `2624fff`, przed jakimkolwiek wynikiem
   strategii na prawdziwych danych. Nowe kryterium wykrywa przeciek (planista
   pomijający grupy, których noga przegrywa) i fałszywe wyjaśnienie (przyczyna
   „stawka poniżej minimum” przy stawce z księgi ≥ 0,50 zł) —
   `tests/test_gate_4bc.py`. **4b-A bez zmian.**

   *Dopisek 2026-10-15 — remis zaokrąglenia i twardy warunek kapitału.*
   Do punktu (ii) i do wpisów odrzucenia z (iii): (a) **remis** — gdy surowa
   stawka z księgi (pełna precyzja, przed zaokrągleniem) leży bliżej niż
   1e-6 zł od x.xx5, stawka silnika może być którymkolwiek z dwóch
   sąsiednich groszy; poza remisem dokładna równość z `round(stawka, 2)`
   (żadnej ogólnej tolerancji 0,01 zł); (b) **twardy warunek kapitału** —
   |kapitał z księgi − kapitał silnika| < 1e-6 zł dla każdego kuponu i
   wpisu odrzucenia (dotąd: kupony bez sprawdzenia wprost, wpisy 0,005 zł);
   naruszenie = czerwony (klasa B, inny stan przebiegu). Raport 4b-C podaje
   kupony sprawdzone, remisy, zaakceptowane dzięki remisowi, odrzucone i
   max |Δ kapitału|. *Źródło:* bramka `27ae469` — 4b-C czerwone na jednej
   pozycji, kupon c0-004274: wiąże limit 15% ekspozycji, stawka dokładnie
   5,825 zł, silnik 5,83 vs checker 5,82, kapitały różne o 4,5e-11
   (kolejność sumowania floatów); diagnoza klasa A
   (`docs/discovery/out_B/diag_4bC_2.md`, poza gitem). Zmiana **przed**
   jakimkolwiek wynikiem strategii na prawdziwych danych; src/ i config/ bez
   zmian (zmiana wyłącznie w audycie `scripts/engine_tests.py`).
5. **Podwójne księgowanie.** Kapitał z symulatora == kapitał z
   `reconcile_bets.py` po każdym rozliczeniu (tolerancja 1e-9).
6. **Niezmienniki.** Stawka ≤ limity; kapitał ≥ 0;
   `observed_at < decision_at < kickoff < settled_at`; `tax_factor` zgodny z
   reżimem w danej chwili.
7. **Jedna ścieżka kodu.** Test podmienia funkcje modułów live na szpiegi i
   sprawdza, że backtest woła właśnie je.

## 5. Metryki i raport

Per strategia, grupa lig i rynek: liczba zakładów, obrót, zysk, yield z CI
(klastry = tygodnie ISO), CLV z CI, ROC roczny z procentem składanym,
maksymalne obsunięcie i najdłuższy czas pod kreską, okazje na 100 meczów,
krzywa kapitału (PNG), rozkład kapitału końcowego z bootstrapu po
tygodniach. Każda liczba z `n` i CI (reguła 11).

Raport: `reports/backtest_fin/<commit>/RAPORT.md` + JSON + PNG.

## 6. Werdykt — spisany przed wynikiem

- **Silnik:** §4 w całości zielone — warunek konieczny wszystkiego dalej.
- **Logika toru S** — strategia A, wszystkie ligi razem:
  - **POTWIERDZONA:** średnie CLV > 0 z dolną granicą CI > 0 **i** yield > 0
    (wartość punktowa) → Filar 2 uzasadniony;
  - **NIEPOTWIERDZONA:** CI CLV obejmuje 0 → brak dowodu nawet na
    bukmacherach zastępczych → zgodnie z zasadą Pawła nie idziemy na rynek;
    projekt zostaje portfolio;
  - **OBALONA:** górna granica CI CLV < 0 → tor S zamknięty.
- **Reżim Betclica** — strategia C, te same kryteria (zmiany 2026-10-11:
  trzy części werdyktu, rekomendacja dla Filaru 2). **Pojedynczy
  bukmacherzy** (B365, B-BW, B-WH) — raport z CI, bez werdyktu.
- **ROC** — raportowany z CI i zestawiony z celem 10–15% (ROADMAP §3).
  Informacja, nie bramka: przy kilku tysiącach zakładów przedział yieldu ma
  szerokość rzędu ±2–3 pkt proc., więc twardym dowodem jest CLV.
- **Alarmy przerywające:** zysk (wartość punktowa) w strategii D; yield
  (wartość punktowa) > 8% w agregacie którejkolwiek strategii A, B (każdy
  bukmacher), C, D, F — wszystkie ligi razem albo grupa lig z §3. Strategia
  E (`Max`) i pojedyncze ligi czy rynki nie uruchamiają alarmu — tam
  raport. Oba alarmy → stop i szukanie przyczyny przed jakimkolwiek
  wnioskiem (CLAUDE.md — domyślnie błąd).
- **Strefa pośrednia:** różnica CLV i okazji między grupami lig — wejście do
  wyboru lig w Filarze 4.

## 7. Kolejność

1. FSA #0 — zrobione 2026-10-01: 0 KRYTYCZNYCH, 18 POWAŻNYCH →
   naprawy wg `docs/FSA0_NAPRAWY.md` → FSA #0b → bramka F0 → F1.
2. Ingest wszystkich lig + raport kolumn i reguły `observed_at`.
3. `replay.py` + `financial.py` + `reconcile_bets.py`.
4. Testy z §4 → bramka.
   4a. `backtest-auditor` + skrócony FSA (sekcje 3–4) na kodzie z kroku 3,
   **przed** pierwszym przebiegiem strategii — błąd znaleziony po
   obejrzeniu wyników kosztuje świeżość wyniku.
5. Jeden przebieg strategii A–F + wrażliwość → raport.
6. FSA #1 → werdykt → decyzja Pawła o Filarze 2.

## 8. Czego nie robimy

- Nie stroimy parametrów po wyniku; wrażliwość tylko raportujemy.
- Nie używamy modelu DC/Elo do decyzji (M2: brak wkładu ponad rynek).
- `Max` nie służy do decyzji — tylko jako górna granica.
- Handicapy azjatyckie — po Filarze 1, jeśli A wyjdzie POTWIERDZONA.
