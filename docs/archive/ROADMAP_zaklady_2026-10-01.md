# ARCHIWUM — plan zakładów (ROADMAP, Część I z 2026-10-01, 12:58)

Zawieszony 2026-10-01 decyzją o modelu biznesowym — patrz `ROADMAP.md`,
Część I. Zachowany bez zmian jako zapis rozumowania: silniki S i M, bramki
etapowe, rękawy A i B, ekonomia zakładów, rytm audytów. Wraca wyłącznie
świadomą decyzją Pawła.

---

**Aktualizacja 2026-10-01.** Część I jest nowa: wizja, stan, droga do
pierwszego zakładu, bramki, rękawy A i B, ekonomia, audyty, granice.
Część II to historia kroków 3–4 z decyzjami — bez zmian merytorycznych
poza miejscami oznaczonymi datą.

Zasada bez zmian: kolejność jest zależnością, nie preferencją. Nic nie
skaluje się bez zaliczonej bramki z §4.

---

# CZĘŚĆ I — WIZJA I PLAN

## 1. Wizja w jednym akapicie

Projekt ma dwa silniki. **Silnik S** („kurs ostry vs kurs miękki") ma
zarabiać: bierze uczciwe prawdopodobieństwo z Pinnacle (The Odds API, po
Shinie) i szuka polskiego kursu bez podatku, który je przebija. **Silnik M**
(Elo, Dixon-Coles, ensemble) to badania i portfolio — musi dopiero
udowodnić, że wnosi cokolwiek ponad Pinnacle. Proporcja z założeń zostaje:
80% portfolio, 20% zysk do czasu limitów. Budżet zerowy. Człowiek klika.

Dlaczego S przed M — liczba, nie opinia: luka Elo − Pinnacle wynosi
**+0.0145 log loss [+0.0062, +0.0229]** (krok 3). Tam, gdzie nasz model i
Pinnacle się różnią, częściej myli się model. „Value" liczone z modelu
przeciw polskiemu kursowi byłoby w większości błędem modelu.

## 2. Gdzie jesteśmy (2026-10-01)

| obszar | stan |
|---|---|
| Kroki 1–3 | **zamknięte** — Shin, schema, Elo, walk-forward, audyt bez przecieków |
| Krok 4 — DC | **zatrzymany na bezpieczniku** `τ_s`; poprawka C w `STEP4_ENSEMBLE.md` §11.9 |
| Lockbox (2025/26, 2026/27) | zamknięty, nietknięty |
| Kolektor | Faza 0: The Odds API zweryfikowane na żywo, klucz w `.env`; `docs/sources.md` gotowy; `docs/discovery/` pusty; regulaminy STS, Fortuny, Superbetu niesprawdzone |
| Produkt: alerty, zakłady | **zero** |
| Wydane złotówki | zero |

## 3. Droga do pierwszego prawdziwego zakładu

### Silnik S — najkrótsza droga (Ekstraklasa)

| # | krok | stan |
|---|---|---|
| S1 | The Odds API na żywo (`COLLECTOR_PLAN.md` Faza 1c) — migawki Pinnacle zaczynają się zbierać | klient gotowy, do uruchomienia |
| S2 | Zgodna ścieżka odczytu kursów bukmachera głównego albo tryb `k_min` (`COLLECTOR_PLAN.md` §2 pkt 2a, §3.10) | czeka na discovery Betclica |
| S3 | Faza 1a — surowe kursy bukmachera na żywo (tylko przy zgodnej ścieżce; w trybie `k_min` odpada) | — |
| S4 | Faza 1b — parser i kanonizacja: The Odds API zawsze, bukmacher jeśli S3; łączenie meczów | — |
| S5 | `pricing/ev.py` + `pricing/kelly.py`: EV względem Pinnacle po Shinie, mechanika Bez Podatku 2.0 (§7), dublety value | — |
| S6 | Alerty Telegram + dziennik zakładów (ręczny wpis kursu, stawki, godziny) | — |
| S7 | Paper trading: ≥ 4 kolejki i ≥ 50 alertów | — |
| S8 | Bramka G-S (§4) → pierwszy prawdziwy zakład, minimalne stawki | — |

**Pięć–sześć kroków inżynieryjnych (S1–S6), realnie 6–9 sesji CLI, potem co
najmniej cztery tygodnie paper tradingu.** Pierwszy prawdziwy zakład —
najwcześniej pod koniec listopada.

„Zyskownej rekomendacji" nie da się zobaczyć z góry. Pojedynczy alert jest
+EV według wyceny. Czy przewaga jest prawdziwa, rozstrzyga CLV po
dziesiątkach zakładów; wynik finansowy — dopiero po tysiącach (§7).

Silnik S nie łamie reguły 19. Pinnacle jest tu **wyceniaczem**, nie cechą
modelu: osobna strategia, osobne raporty, zero mieszania z modelem bez
jawnego shrinkage. **Przed S5:** dopisać to rozróżnienie do `CLAUDE.md`.

### Silnik M — dłuższa droga

| # | krok |
|---|---|
| M1 | Poprawka C (§11.9) → przebieg diagnostyczny → §11.8 → DC zamknięte |
| M2 | Projekcja, stacking poziomu 2, bramki G1–G4 (`STEP4_ENSEMBLE.md` §8 pkt 5–7) |
| M3 | Lockbox — jednorazowo; `backtest-auditor` |
| M4 | **Test pokrywania:** czy pula logarytmiczna Pinnacle + nasz model bije samego Pinnacle'a na dev (sparowane, CI klastrowe po sezonach)? |
| M5 | Rynki z `P'` (`STEP4_PLAN.md` §3) — dla rynków bez linii ostrej albo gdy M4 pokazał wkład |
| M6 | Inferencja na żywo: codzienny refit, predykcje na nadchodzącą kolejkę |

M4 rozstrzyga los silnika M na 1X2. Jeśli model nie wnosi nic ponad
Pinnacle, zostają mu: rynki pochodne, w których polscy bukmacherzy wyceniają
niespójnie, I liga (brak linii ostrej) i portfolio. To nie porażka — to
najczęstszy uczciwy wynik w tej branży.

## 4. Bramki etapowe

Nic nie przechodzi dalej bez zaliczonej bramki. Granice twarde, spisane
przed wynikiem.

| bramka | warunek przejścia | skutek |
|---|---|---|
| **G-S** paper → pieniądze | ≥ 50 alertów i ≥ 4 kolejki; średnie CLV vs zamknięcie Pinnacle > 0, dolna granica CI > 0 (klastry = kolejki); ≥ 70% alertów z kursem wciąż dostępnym przy kliknięciu | pierwszy prawdziwy zakład: ćwierć Kelly, limit 2% |
| **G-R** utrzymanie | co 100 zakładów: CLV wciąż > 0; obsunięcie < 25% kapitału | grasz dalej; inaczej powrót do paper |
| **G-A2** skalowanie | G-S zaliczone + 200 zakładów z CLV > 0 + kolektor stabilny 4 tygodnie + kredyty The Odds API pozwalają | jedna nowa liga, nie pięć |
| **G-M** pieniądze dla modelu | M4: wkład modelu ponad Pinnacle istotny | model wchodzi do wyceny, jawnie jako shrinkage |
| **G-B** rękaw B | G-A2 zaliczone | tylko B0 z §6 |

**Reguła zabicia:** silnik, rękaw albo liga, które dwa razy nie zaliczą
bramki, idą do archiwum. Kod zostaje w historii gita, nie w utrzymaniu.

## 5. Rękaw A — skalowanie piłki (Premier League, La Liga, Bundesliga, Serie A)

**Architektura: tak, pod trzema warunkami** (`COLLECTOR_PLAN.md` §3.11):
rejestr lig w konfiguracji, strony meczów tylko z prescreenu, twardy sufit
kredytów The Odds API (przy pięciu ligach: same zamknięcia, dwa rynki).

Gotowe na wiele lig: `match_id` zawiera rozgrywki, `TeamResolver` nie zgaduje
i odrzuca niejednoznaczne aliasy, Shin i EV nie zależą od ligi, walk-forward
działa per liga. Do zrobienia: parser plików głównych lig z football-data
(inny układ kolumn niż `POL.csv`), aliasy ~100 drużyn w polskich wariantach
nazw („Bayern Monachium", „Inter Mediolan").

Dwa plusy, o których łatwo zapomnieć:
- pliki głównych lig mają historyczne kursy O/U 2.5 i AH (Pinnacle, Max,
  Avg) — tego brakuje nam dla Ekstraklasy;
- **każda nowa liga to świeży zbiór testowy** dla modelu dopracowanego na
  Ekstraklasie — model nie widział jej ani razu.

**Ekonomia jest słabsza niż architektura.** Pięć największych lig to
najefektywniejsze rynki świata; model z samych wyników nie pobije tam
Pinnacle'a. Silnik S może działać, ale polskie kursy na Premier League
trzymają się linii ostrej ciaśniej niż na Ekstraklasie, a większa liczba
zakładów przyspiesza limity. Skalujemy po jednej lidze, po bramce G-A2,
zaczynając od ligi, w której kolektor zmierzy najwięcej rozbieżności.

## 6. Rękaw B — rynki predykcyjne i zakłady specjalne

**Najpierw prawo, bo ono wycina większość pomysłu** (stan na 2026-10-01; to
nie jest porada prawna):

| platforma | status dla rezydenta PL | w projekcie |
|---|---|---|
| Polymarket | w rejestrze domen zakazanych od 8.01.2025; VPN nie zmienia statusu prawnego gry | **nie** |
| Betfair Exchange, Smarkets | bez polskiej licencji | **nie** |
| licencjonowani polscy bukmacherzy | legalne; STS i Betfan mają m.in. wybory 2027, wybory lokalne, wybory zagraniczne | **tak** |

Udział w grze u nielicencjonowanego operatora to art. 107 § 2 KKS: grzywna
do 120 stawek dziennych i obligatoryjny przepadek wygranej. Zysk z takiej
gry może przepaść w całości — matematyka EV nie ma tu znaczenia.

**To nie jest naturalne przedłużenie naszych algorytmów.** Modele golowe nie
przenoszą się na wybory, pogodę ani makro. Przenosi się infrastruktura:
Shin (działa dla rynków wielowynikowych), EV z podatkiem, Kelly, kolektor,
alerty, rygor audytów. Estymacja prawdopodobieństwa to osobna dziedzina dla
każdego typu zdarzenia — dla wyborów: agregacja sondaży.

Ekonomia legalnej części: 12% podatku (próg `p·k ≥ 1.136`), niskie limity na
zakładach specjalnych, kilka rynków w roku. Oczekiwany wkład ≈ 0.

**Plan fazowy, po bramce G-B:**
- **B0** (tydzień): inwentaryzacja ofert specjalnych u licencjonowanych
  bukmacherów — rynki, marże, limity, czy obejmuje je jakakolwiek promocja
  bez podatku.
- **B1** (portfolio, bez pieniędzy): bayesowska agregacja sondaży przed
  wyborami parlamentarnymi 2027 — kalibracja, porównanie z kursami polskich
  bukmacherów. Jako materiał portfolio mocniejszy niż większość zakładów.
- **B2** (pieniądze): tylko jeśli konkretny rynek pokaże EV powyżej progu po
  podatku — z bramką na wzór G-S.

## 7. Ekonomia — realne oczekiwania

### Mechanika bukmachera głównego: Betclic „Bez Podatku 2.0"

Regulamin promocji z 21.05.2026 v2, obowiązuje do odwołania:
- pierwsze **1000 zł łącznych stawek** — wszystkie zakłady bez podatku;
- potem: jeśli udział AKO w obrocie (liczony po stawkach, z ostatnich 5000
  zakładów, po roku krocząco z 12 miesięcy) wynosi **≥ 50%** — wszystko bez
  podatku; jeśli mniej — **single ze współczynnikiem 0.94**;
- AKO = co najmniej 2 zdarzenia, każde z kursem ≥ 1.20.

Skutek: po pierwszych 1000 zł single value wymagają przewagi > 6.4%, chyba
że co najmniej połowa obrotu idzie w AKO. Naturalna forma gry to **dublety z
dwóch nóg value** z różnych meczów: EV = (1+e₁)(1+e₂) − 1, zero podatku,
wyższa wariancja. Moduł EV (S5) śledzi udział AKO z dziennika zakładów i
wycenia single na 0.94, gdy udział spadłby poniżej 50%.

### Ile to daje

Przy ćwierć Kelly miesięczny zwrot z kapitału to w przybliżeniu
`0.25 · n · e² / (k − 1)` (n — zakłady w miesiącu, e — przewaga, k — kurs).
Zwrot rośnie z **kwadratem** przewagi, bo stawka Kelly'ego sama jest
proporcjonalna do przewagi. Mała przewaga daje bardzo mały zwrot.

Scenariusze (kurs ~2.0, ćwierć Kelly, przewaga prawdziwa — optymistycznie
zakładamy, że model jej nie przeszacowuje):

| scenariusz | zakładów/mies. | zwrot/mies. | ~rocznie | P(strata po 12 mies.) | zł/mies. przy 2 tys. / 10 tys. |
|---|---|---|---|---|---|
| Ekstraklasa, single, e = 2.5% | 8 | 0.12% | 1.5% | 40% | 2.5 / 12.5 |
| Ekstraklasa, dublety, e = 2.5% na nogę | 4 | 0.09% | 1.0% | 42% | 1.7 / 8.5 |
| + 4 ligi, single, e = 2.2% | 28 | 0.34% | 4.1% | 34% | 6.8 / 33.9 |
| + 4 ligi, dublety | 14 | 0.23% | 2.8% | 37% | 4.6 / 23.1 |
| optymistyczny: 40 nóg, e = 3% | 40 | 0.90% | 10.8% | 26% | 18 / 90 |

Częstość okazji (n) jest dziś **nieznana** — to pierwsza liczba, którą
zmierzy paper trading. Tabela skaluje się liniowo z n.

Limity polskich kont ograniczają **łączny** zysk, nie miesięczny. Konto
ograniczone po 300 zakładach (e = 2.5%) daje oczekiwanie 4.7% kapitału
(94 zł przy 2 tys., 469 zł przy 10 tys.), z 33% szansą, że akurat na tym
koncie wyjdziesz na minus.

Ile zakładów do rozstrzygnięcia, czy przewaga istnieje: z wyniku finansowego
~4 300 (e = 3%) do ~9 600 (e = 2%); z CLV — dziesiątki. Dlatego CLV jest
metryką nadrzędną (reguła 26).

Rękaw B: oczekiwany wkład ≈ 0 (§6).

**Wniosek:** przy darmowych danych, kapitale studenckim i limitach to jest
1–4% rocznie na kapitale w wariancie realistycznym i ~10% w optymistycznym —
od kilku do kilkudziesięciu złotych miesięcznie. Projekt może się sam
sfinansować (wydatki: zero), ale nie jest źródłem dochodu. Jego wartość to
portfolio, więc proporcja 80/20 z założeń jest trafna.

## 8. Rytm audytów (QA)

Każdy audyt kończy się wpisem w `reports/qa/RRRR-MM-DD.md`: liczby, werdykt,
decyzje. Liczby ma generować jeden skrypt (`valuebet.qa`, do zbudowania razem
z S6), nie ręczne klikanie. Do tego czasu audyt tygodniowy robi CLI na
prośbę, według tej tabeli.

| rytm | co sprawdzamy | wyzwalacz działania |
|---|---|---|
| każdy commit | pytest, ruff, mypy strict; `future_poison` przy `features/`, `backtest/`; `backtest-auditor` po zmianach w `models/`, `pricing/`, `backtest/` | czerwone = brak merge |
| co tydzień, po kolejce | **kolektor i zgodność:** pokrycie kotwic (zamknięcie ≥ 95%), luki heartbeatu, odrzucenia parsera, pokrycie aliasów; zapytania per host vs limity i `Crawl-delay`; **diff robots.txt każdego hosta** (zmiana → źródło wstrzymane do przeglądu); kredyty The Odds API vs plan | przekroczony limit lub zmieniony robots.txt = źródło stoi |
| co 2 kolejki (paper i na żywo) | **degradacja przewagi (model decay):** kroczące CLV z ostatnich 50 zakładów lub alertów, z CI; liczba okazji na kolejkę i średnie EV (trend); odsetek alertów z kursem dostępnym przy kliknięciu; dla silnika M: log loss na żywo vs oczekiwanie z dev, kalibracja | górna granica CI kroczącego CLV < 0 → stop pieniędzy, powrót do paper; liczba okazji spada o połowę przez 4 kolejki → przegląd |
| co miesiąc | **budżet i zakres:** lista usług zewnętrznych i ich planów (wszystko darmowe?); każdy moduł w `src/` ma pozycję w ROADMAP; przyrost linii kodu i liczby modułów vs poprzedni miesiąc; nowe zależności z uzasadnieniem | wydatek bez decyzji w ROADMAP = cofnięcie; przyrost `src/` > 30% bez zaliczonej bramki = przegląd zakresu |
| co kwartał | **architektura i regulaminy:** ponowne sprawdzenie regulaminów i robots.txt (`docs/sources.md`); martwy kod i zbędne abstrakcje; pełny przebieg `backtest-auditor`; przegląd bramek i reguły zabicia | źródło z werdyktem starszym niż kwartał = wstrzymane |

Twarde reguły przeciw rozrostowi:
1. Nowy rękaw, liga albo rynek — dopiero po zaliczonej bramce bieżącego.
2. Abstrakcja dopiero przy trzecim konkretnym użyciu.
3. Nowa zależność — tylko z uzasadnieniem w opisie commita.
4. Moduł bez pozycji w ROADMAP nie powstaje.
5. Reguła zabicia z §4.

## 9. Granice (stałe)

- Bot nigdy nie składa zakładu. Człowiek klika.
- **robots.txt obowiązuje per host, łącznie z `Crawl-delay`.** Decyzja z
  2026-10-01, po propozycji obejścia. Powody:
  1. konto u bukmachera głównego to główne aktywo projektu — bez promocji
     bez podatku matematyka się nie spina; regulamin Betclica przewiduje
     blokadę konta i wstrzymanie wypłat (np. pkt 5.6), a bukmacher szukający
     pretekstu nie potrzebuje argumentu prawnego;
  2. portfolio: publiczne repo z botem, który celowo ignoruje robots.txt, to
     czerwona flaga dla każdego, kto je czyta; `docs/sources.md` z werdyktami
     to zielona;
  3. zbędność: robots.txt działa per host, `Crawl-delay` Fortuny (20 s) przy
     naszych ~60–150 zapytaniach na dobę nic nie kosztuje, a gdy zgodnej
     ścieżki nie ma — jest tryb `k_min` (`COLLECTOR_PLAN.md` §3.10).
- Bez obchodzenia anty-botów, bez proxy, bez rotacji IP.
- Tylko licencjonowani polscy operatorzy. Bez VPN i bez platform z rejestru
  domen zakazanych.
- Budżet zerowy. Każdy wydatek — tylko z wpisem w ROADMAP i uzasadnieniem.
- Lockbox oglądany raz.

---

