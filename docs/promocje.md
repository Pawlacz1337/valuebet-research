# promocje.md — regulaminy promocji „bez podatku”

Jedyne źródło stałych reżimu podatkowego (`CLAUDE.md` reguła 20). Każda
stała w `pricing/ev.py` ma tu wiersz: **cytat z paragrafu** albo **jawny
wariant pesymistyczny**. Przegląd co kwartał (`docs/FULL_SYSTEM_AUDIT.md`
§5) i przed każdym przejściem między Filarami.

Założone 2026-10-02 po FSA #0 (F-25).

---

## Betclic — „Bez Podatku 2.0”

- **Dokument:** `https://dam.begmedia.com/rox/images/Global/COMMON/TnC/PL/Bez_Podatku_2.0_T_Cs_21.05.2026_v2.pdf`
  (wersja 21.05.2026 v2).
- **Odczyt wstępny:** 2026-10-02, Architekt, przez narzędzie, które
  streszcza dokument. Fragmenty w cudzysłowie poniżej są **cytatami
  wstępnymi** — mogą różnić się od oryginału szykiem albo słowem.
- **Weryfikacja słowo w słowo:** [ ] — CLI czyta PDF bezpośrednio (kopia w
  `data/raw/tc/betclic/`, hash w manifeście), podmienia cytaty na dosłowne,
  wpisuje datę i commit.
  **Stan 2026-10-02: NIEZWERYFIKOWANE.** `scripts/fetch_betclic_tc.py`
  (przez `net/http.py`): `https://dam.begmedia.com/robots.txt` → HTTP 403 —
  robots.txt niedostępny, więc nie wiadomo, czy wolno; PDF **nie został
  pobrany** (FSA0_NAPRAWY §3 F-25b). Prośba do Pawła: pobrać PDF ręcznie do
  `data/raw/tc/betclic/` i dopisać go do manifestu
  (`uv run python scripts/verify_raw.py --adopt-orphan tc/betclic/<plik>`).
  Do tego czasu `promo_verified_on: null` → ładowacz live traktuje promocję
  jako nieaktywną (0.88), a strategia C w backteście jest oznaczana „na
  niezweryfikowanym regulaminie”. Każda rozbieżność z odczytem wstępnym → wpis w
  `reports/audit/FIX_LOG_F0.md` i w raporcie dla Pawła.
- **Decyzja Pawła, 2026-10-02:** kod liczy wariant **najmniej korzystny dla
  gracza** tam, gdzie regulamin czegoś nie rozstrzyga, oraz w punkcie T4
  (patrz niżej). Powrót przy optymalizacji. Do tego czasu weryfikacja
  słowo w słowo **nie zmienia kodu** — tylko ten dokument.

### Parametry

| # | parametr | regulamin (wstępnie) | status | w kodzie (`pricing/ev.py`) |
|---|---|---|---|---|
| T1 | okres akcji | §2 ust. 1: „od dnia 21.05.2026 r. do odwołania” | cytat wstępny | zakład przed 21.05.2026 → 0.88; w live: weryfikacja regulaminu starsza niż 92 dni → 0.88 i ostrzeżenie w przeglądzie dnia |
| T2 | kwota bez podatku | §3 ust. 3: do chwili, gdy „łączna suma stawek Zakładów zawartych przez Użytkownika od chwili rozpoczęcia Akcji Specjalnej osiągnie kwotę 1,000 PLN” | cytat wstępny; czy liczone od startu akcji, czy od przystąpienia — **niejasne** | obrót liczony od 21.05.2026 (wcześniejsza z dwóch dat → próg wyczerpuje się szybciej); **od 2026-10-11 (F1-P01 pkt 1, §3 ust. 4):** 1.00 dla każdego kuponu (singiel i wielokrotny), gdy obrót prawdziwy + obrót spoza dziennika (`external_turnover_pln`) **przed** zakładem < 1000 — „cały taki Zakład … niezależnie od wysokości stawki”; do 2026-10-10: obrót + stawka < 1000, zakład przekraczający próg w całości poza zwolnieniem; brak `external_turnover_pln` → próg uznany za wykorzystany. Obrót spoza dziennika wchodzi też do mianownika udziału (T4) jako nie-AKO: `external_turnover_pln` do udziału po stawkach, `external_coupons` do udziału po kuponach; brak `external_coupons` → warunek udziału uznany za niespełniony |
| T3 | moment oceny | §3 ust. 4: „Jeżeli przed zawarciem Zakładu Użytkownikowi pozostaje do wykorzystania jakakolwiek kwota…” | cytat wstępny; czy kandydat liczy się do udziału — **nie określono** | ocena w chwili decyzji, z historii ≤ tej chwili (reguła 1); kandydat **wliczony** do udziału („co jeśli”); kandydaci z jednej migawki rozpatrywani po kolei, każdy widzi poprzednich, w ustalonej kolejności: **najpierw single, potem kupony wielokrotne** (wielokrotne podnoszą udział AKO, więc odwrotna kolejność byłaby optymistyczna), w obrębie grupy: single wg EV malejąco, potem `match_id` (plan §3); kolejność realnego klikania zależy od Pawła i nie jest modelowana; wrażliwość na kolejność niewyliczana (decyzja 2026-10-11, AB-4) |
| T4 | podstawa udziału | §3 ust. 5: „procentowy udział stawek postawionych na kwalifikujące się Zakłady wielokrotne” | cytat wstępny — **po stawkach** | **od 2026-10-11 (F1-P01 pkt 3, wariant B):** udział **wyłącznie po stawkach** (`share_basis = "stakes"`, regulamin). Wariant „po stawkach **i** po kuponach” (margines Pawła z 2026-10-02) — `share_basis = "stakes_and_coupons"`, wymagany jawnie, **tylko raport wrażliwości** C. `CONTEXT.md` §2 poprawiony 2026-10-11 |
| T5 | próg | §3 ust. 12: „co najmniej 50%” | cytat wstępny | ≥ 0.50 |
| T6 | AKO kwalifikowany | §3 ust. 9: „co najmniej dwóch zdarzeń objętych Ofertą, o kursie równym lub wyższym 1.20 każdy” | cytat wstępny; nogi z jednego meczu i nogi zwrócone — **nie określono** | ≥ 2 nogi z **różnych** meczów, każda ≥ 1.20; noga zwrócona się nie liczy; < 2 ważne nogi → kupon nie jest AKO |
| T7 | okno | §3 ust. 8: „ostatnich 5000 (pięć tysięcy) Zakładów zawartych przez Użytkownika od dnia przystąpienia do Oferty, z tym że po upływie 12 miesięcy od tego dnia uwzględnia się wyłącznie Zakłady zawarte w okresie ostatnich 12 miesięcy” | cytat wstępny | kupony, nie nogi; najpierw odcięcie 12 miesięcy **kalendarzowych** (nie 360 dni — F-08), gdy minęło 12 miesięcy od `join_date`; potem ostatnie 5000. Brak `join_date` → warunek udziału uznany za niespełniony (single 0.94) **Dzień przystąpienia do Oferty (2026-10-11):** dzień, od którego oferta została uruchomiona na koncie użytkownika — NIE dzień pierwszego zakładu; konto założone przed startem oferty → dzień udostępnienia oferty (21.05.2026), konto założone później → dzień aktywacji = dzień rejestracji profilu; czyli `join_date = max(data rejestracji konta, 21.05.2026)`. **Potwierdzone przez obsługę klienta Betclic (2026-10-11), nie tekstem regulaminu** — Bez Podatku 2.0 §3 ust. 8 używa pojęcia „dnia przystąpienia do Oferty”, ale go nie definiuje; Regulamin zakładów (v3) i Szczegółowe zasady (v8.0) też nie. Wariant kontrfaktyczny C: `join_date` = początek symulacji (zgodne — „konto sprzed startu oferty”) |
| T8 | singiel bez warunku | §3 ust. 11.1: „…ze Wskaźnikiem 0.94 (6%)” | cytat wstępny | 0.94 |
| T9 | AKO przy udziale < 50% | §3 ust. 11.2 i 12: kwalifikujący się AKO — wskaźnik 1.0 | cytat wstępny | 1.00 |
| T10 | zakład wielokrotny niekwalifikujący się | §3 ust. 11.1: „dla Zakładów pojedynczych oraz Zakładów wielokrotnych, które nie spełniają warunków określonych w ust. 9 […] Wskaźnikiem 0.94 (6%)”; ust. 12: przy udziale ≥ 50% „wszystkie […] Zakłady pojedyncze oraz wielokrotne kwalifikują się do Oferty” | dosłownie z PDF (2026-10-08) | **od 2026-10-11 (F1-P01 pkt 2):** jak singiel — 1.00 przy limicie niewyczerpanym albo udziale ≥ 50%, inaczej 0.94; do 2026-10-10: 0.88 (pesymistycznie) |
| T11 | zakłady paper | nie dotyczy — u bukmachera nie istnieją | — | poza obrotem i poza udziałem |
| T12 | nadużycia promocji, minimalna stawka, wyłączone rynki, wypłata | Szczegółowe zasady zakładów (v8.0, 20.08.2026) pkt 3.1: „Można zawrzeć jedynie zakład o minimalnym kursie 1,14. Minimalna stawka każdego zakładu wynosi 0,50 zł.”; Bez Podatku 2.0 §3 ust. 2.1: nie wlicza się „zakładów systemowych, zawartych na sporty wirtualne oraz na symulowane gry w karty” | **ZAMKNIĘTE 2026-10-09** (odczyt CLI z PDF): min. stawka 0,50 zł, min. kurs 1,14; wyłączone z promocji wyłącznie: systemowe, sporty wirtualne, symulowane gry karciane — rynków piłkarskich (1X2, O/U) nie wyłącza nic | warunek, który wyłącza zakład z oferty (minimalna stawka, rynek, liczba nóg, kurs) → ten zakład 0.88; klauzule o nadużyciach → ryzyko konta, wpis tutaj |
| T13 | podatek od wygranej (ustawowy, nie promocja) | `CONTEXT.md` §2: 10% od wygranej powyżej 2280 zł z jednego kuponu | do potwierdzenia w przepisach | osobny czynnik `winnings_factor` ∈ {1.00, 0.90}, **nie** mieszany z `tax_factor` (reguła 20); wypłata kuponu `stawka · k · tax` > 2280 zł → 0.90 na **całej** wypłacie (pesymistycznie); EV = `p · k · tax · w − 1`, Kelly na kursie `k · tax · w`; `w` liczone z wypłaty przy wyliczonej stawce, jedno przeliczenie, stawka nie rośnie |
| T14 | okno rozliczenia zakładów (udziału) | §3 ust. 8: „Udział, o którym mowa w ust. 5, oblicza się z uwzględnieniem ostatnich 5000 (pięć tysięcy) Zakładów zawartych przez Użytkownika od dnia przystąpienia do Oferty, z tym że po upływie 12 miesięcy od tego dnia uwzględnia się wyłącznie Zakłady zawarte w okresie ostatnich 12 miesięcy, liczonym na zasadzie kroczącej.” [Fragment usunięty z wersji publicznej: dotyczył prywatnego konta autora i korespondencji z obsługą bukmachera.] | dosłownie z PDF (2026-10-08); okno dotyczy **wyłącznie udziału AKO** (ust. 5, warunek ≥ 50% z ust. 11–12), **nie limitu 1000 zł** (ust. 3: „od chwili rozpoczęcia Akcji Specjalnej”, bez okna); czy po 12 miesiącach limit 5000 dalej obowiązuje — regulamin („z tym że … wyłącznie”) sugeruje, że okno 12 miesięcy ZASTĘPUJE limit 5000, nie nakłada się na niego — **niejednoznaczne** | `BetclicTaxRegime.window()`: kupony od `join_date`; po 12 miesiącach kalendarzowych od `join_date` odcięcie 12 miesięcy wstecz od `now`; **zawsze** ostatnie 5000 (część wspólna obu warunków — patrz F1-P02 pkt 2); limit 1000 zł (T2) bez okna — zgodnie z ust. 3; `external_turnover_pln` w mianowniku udziału stale, bez wypadania z okna (F1-P02 pkt 1) |

### Regulamin 21.05.2026 v2 — odczyt CLI z PDF (2026-10-08)

Plik dostarczony przez Pawła: `docs/discovery/Bez_Podatku_2.0_T_Cs_21.05.2026_v2.pdf`
(poza gitem — `docs/discovery/` w `.gitignore`), sha256
`22587b8ae7742ab01967cd043141f5d7477241fdff97108a44d36a34ba43691b`, 3 strony,
§1–§8. Cytaty niżej — **dosłownie z PDF** (CLI, 2026-10-08). Tabela T1–T13
wyżej zostaje jako stan sprzed odczytu; rozbieżności — F1-P01 niżej.
`promo_verified_on` w `config/bookmakers.yaml` **bez zmian** (decyzja Pawła:
pola uzupełniamy przed Filarem 3).

| temat | regulamin, dosłownie | uwaga |
|---|---|---|
| Zakłady objęte (§3 ust. 2) | „nie wlicza się zakładów systemowych, zawartych na sporty wirtualne oraz na symulowane gry w karty”; „wlicza się zakłady pojedyncze oraz wielokrotne”; „…zawarte przy wykorzystaniu freebetów”; „…przedmeczowe oraz zakłady zawarte na żywo” | — |
| limit (§3 ust. 3) | „Do momentu, w którym łączna suma stawek Zakładów zawartych przez Użytkownika od chwili rozpoczęcia Akcji Specjalnej osiągnie kwotę 1,000 PLN (tysiąc złotych), zawarte przez Użytkownika Zakłady będą automatycznie kwalifikowały się do Oferty.” | liczony **od startu akcji** (21.05.2026), nie od przystąpienia — T2 rozstrzygnięte |
| zakład przekraczający limit (§3 ust. 4) | „Jeżeli przed zawarciem Zakładu Użytkownikowi pozostaje do wykorzystania jakakolwiek kwota w ramach limitu, o którym mowa w ust. 3, cały taki Zakład uznaje się za kwalifikujący się do Oferty, niezależnie od wysokości stawki.” | niejednoznaczne: czy „Zakład” w ust. 3–4 obejmuje zakłady wyłączone z ust. 2 (systemowe) i jak liczyć stawkę freebetu |
| co wlicza się do limitu (§3 ust. 6) | „wlicza się Zakłady rozliczone przy wykorzystaniu funkcji Cashout i jednocześnie nie wlicza się Zakładów, które zostały anulowane” | — |
| udział AKO (§3 ust. 5, 7) | „procentowego udziału stawek postawionych na kwalifikujące się Zakłady wielokrotne w łącznej wartości wszystkich stawek postawionych przez Użytkownika na Zakłady”; mianownik: z Cashout, bez anulowanych | **po stawkach**; regulamin nie zna udziału po liczbie kuponów |
| okno (§3 ust. 8) | „ostatnich 5000 (pięć tysięcy) Zakładów zawartych przez Użytkownika od dnia przystąpienia do Oferty, z tym że po upływie 12 miesięcy od tego dnia uwzględnia się wyłącznie Zakłady zawarte w okresie ostatnich 12 miesięcy, liczonym na zasadzie kroczącej” | „dzień przystąpienia” niezdefiniowany w dokumencie |
| AKO kwalifikowany (§3 ust. 9–10) | „co najmniej dwóch zdarzeń objętych Ofertą, o kursie równym lub wyższym 1.20 każdy, z wyłączeniem Zakładów rozliczonych przy wykorzystaniu funkcji Cashout oraz Zakładów, które zostały anulowane”; ust. 10: zakłady edytowane do warunków AKO „nie będą wliczane do udziału” | „zdarzeń”, nie „meczów”; o nogach zwróconych — nic |
| udział < 50% (§3 ust. 11) | 11.1: single i wielokrotne niespełniające ust. 9–10 — „ze Wskaźnikiem 0.94 (6%)”; 11.2: kwalifikujące się wielokrotne — „ze Wskaźnikiem 1.0” | — |
| udział ≥ 50% (§3 ust. 12) | „wszystkie zawarte przez Użytkownika Zakłady pojedyncze oraz wielokrotne kwalifikują się do Oferty” | moment pomiaru udziału (przed / z kandydatem) — **nie określono** |
| podatek od wygranej (§3 ust. 13) | „Wygrane, których łączna wartość przekracza określony prawem limit, podlegają opodatkowaniu…” | kwoty progu brak — T13 z przepisów |
| T12: min. stawka, wyłączone rynki | **brak w dokumencie**. §1 ust. 4 odsyła do Regulaminu Ogólnego „Freebet”, Regulaminu urządzania zakładów i Komunikatów (`https://www.betclic.pl/termsandconditions`); §8 ust. 3: przy konflikcie rozstrzyga Regulamin | rozstrzygnięte 2026-10-09 w dokumentach z §1 ust. 4 — sekcja „T12 i Regulamin zakładów” niżej |
| nadużycia (§4 ust. 1, 3) | wykluczenie / anulowanie wygranych przy działaniach „sprzecznych z prawem, dobrymi obyczajami […]”; „zabrania się stosowania jakichkolwiek środków mających na celu obejście zasad Akcji Specjalnej” | [Fragment usunięty z wersji publicznej: dotyczył prywatnego konta autora i korespondencji z obsługą bukmachera.] |

> [Fragment usunięty z wersji publicznej: dotyczył prywatnego konta autora i korespondencji z obsługą bukmachera.]

### F1-P01 — rozbieżności modelu z regulaminem (pkt 1–3 W NAPRAWIE W FILARZE 1 — wariant B, decyzja Pawła 2026-10-11; wcześniej: zamknięte dla F1, otwarte dla F2, decyzja 2026-10-10)

1. **T2 / §3 ust. 4:** kod daje 1.00 tylko, gdy `obrót + stawka < 1000`
   („zakład przekraczający próg w całości poza zwolnieniem”); regulamin:
   wystarczy, że **przed** zakładem zostaje „jakakolwiek kwota” — cały zakład
   kwalifikuje się „niezależnie od wysokości stawki”. Kod sprzeczny z
   brzmieniem (bardziej pesymistyczny).
2. **T10 / §3 ust. 11.1 i 12:** kod — wielokrotny niekwalifikujący się → 0.88;
   regulamin — 0.94 przy udziale < 50%, oferta (1.0) przy ≥ 50%.
3. **T4 / §3 ust. 5:** kod wymaga udziału po stawkach **i** po kuponach;
   regulamin zna tylko po stawkach (warunek po kuponach to margines Pawła z
   2026-10-02 — do potwierdzenia, czy zostaje).
4. **T6 / §3 ust. 9:** kod wymaga nóg z **różnych meczów** i pomija nogi
   zwrócone; regulamin mówi o „zdarzeniach” i o tym nic nie mówi; regulamin
   wyłącza Cashout, anulowane i edytowane (ust. 10) — kod tego nie modeluje
   (projekt nie używa Cashout ani edycji).
5. **T2 / §3 ust. 2.3, 6:** freebety i Cashout wchodzą do limitu i
   mianownika — dziennik ich nie zna (dotyczy obrotu spoza dziennika).
6. **Konfiguracja vs aplikacja:** `external_turnover_pln: null` → model
   zakłada wyczerpany limit. [Fragment usunięty z wersji publicznej: dotyczył prywatnego konta autora i korespondencji z obsługą bukmachera.]
7. **T12:** ~~brak w tym dokumencie~~ — **zamknięte 2026-10-09** (sekcja niżej):
   min. stawka 0,50 zł, min. kurs 1,14, wyłączenia promocji tylko systemowe,
   wirtualne i karciane. `config/bookmakers.yaml` (`min_stake_pln`,
   `excluded_markets`) **nadal puste** — uzupełnienie przed Filarem 3
   (decyzja Pawła); do tego czasu ładowacz live: promocja nieaktywna (0.88).
   **2026-10-11 (wariant B):** `min_stake_pln: 0.50`, `excluded_markets: []`
   wpisane do `config/bookmakers.yaml`; pozostałe pola (`promo_verified_on`,
   `join_date`, `external_*`) nadal `null` — ładowacz live zostaje
   pesymistyczny (0.88 do czasu `promo_verified_on`).

Zakres skutków: strategia C (`backtest/strategy_c.py`, `BetclicTaxRegime`)
i tryb live; strategie A, A3, B, D, E i bramka §4 używają stałego podatku.

~~**Zakres naprawy F1-P01 (stan 2026-10-09):** wyłącznie kod reżimu w
`backtest/strategy_c.py` i testy C, gałąź `fix/F1-P01`, `pricing/ev.py` bez
zmian.~~ Zakres błędny co do miejsca kodu (CLI, 2026-10-10): reżim
(`BetclicTaxRegime`, `ako_shares`, `share_condition_met`, `tax_for_coupon`,
`qualifies_as_ako`) jest w `src/valuebet/pricing/ev.py:181-410`, który importuje
bramka §4 (`engine_tests` → `backtest/financial.py`, `live/bets.py` →
`pricing/ev.py`). Przesłonięcie reżimu w `strategy_c.py` łamałoby regułę 28,
a zmiana `ev.py` unieważniłaby bramkę §4 na `2c7cc61`. Gałąź `fix/F1-P01`
nie powstała.

**Decyzja Pawła 2026-10-11 (wariant B, `docs/discovery/CLI_task_wariant_B.md`,
przed jakimkolwiek wynikiem strategii):** werdykt Filaru 1 nie opiera się
wyłącznie na A — porównujemy A, B i C. Dlatego **teraz**, w Filarze 1:
naprawa pkt 1, 2, 3 w `pricing/ev.py` (czerwony test najpierw), bramka §4
obejmująca strategię C (testy 1–7), potem oficjalny przebieg A–F. Pkt 4–7
bez zmian (decyzje niżej). Udział po stawkach i po kuponach zostaje wyłącznie
jako wariant wrażliwości C. Poniższa decyzja z 2026-10-10 — **zastąpiona** w
części dotyczącej pkt 1–3 i bramki.

**Decyzja Pawła 2026-10-10 (`docs/discovery/CLI_task_F1P01_decision.md`):**

- **Filar 1 — ZAMKNIĘTE, kod bez zmian.** Pkt 3 (udział po stawkach **i**
  po kuponach) zostaje: kod jest ostrzejszy od §3 ust. 5, więc daje
  współczynnik podatku **nie wyższy** niż regulamin — kierunek konserwatywny
  dla werdyktu Filaru 1. Pkt 1 i 6 nie zmieniają C (konfiguracja
  kontrfaktyczna: limit 1000 zł wyczerpany). Pkt 2 nie zmienia C
  (`RegimePlanner.groups` tworzy wyłącznie kwalifikujące się dublety: różne
  mecze, nogi ≥ 1.20). Pkt 4 — wariant pesymistyczny zostaje (decyzja
  2026-10-02; różne mecze wspiera Szczegółowe zasady pkt 2.2). Pkt 5 —
  bez zmian (projekt nie używa freebetów ani Cashout). Bramka §4 na
  `2c7cc61` zostaje ważna.
- **Pomiar kierunku (CLI, 2026-10-10, skrypt poza repo, kod `f80e05d`):**
  świat bramki §4 (`scripts/engine_tests.build_world`: terminarz E0+E1
  2022/23–2023/24, e = +2,5%, θ = 0,02), strategia C w konfiguracji
  kontrfaktycznej, `single_mode = production`, nasiona 0–4. Na każdym
  postawionym kuponie i przy każdej wycenie singla przez reżim liczony
  równolegle podatek wg regulaminu (udział ≥ 50% tylko po wartości stawek),
  na tej samej historii; dodatkowo pełny drugi przebieg z warunkiem tylko po
  stawkach. Wynik: **22 229 kuponów** (21 631 dubletów po 1.00, 598 singli po
  1.00), **74 wyceny singla po 0.94** (w obu wariantach 0.94) — **0 kuponów
  z innym współczynnikiem**, **0 przypadków kod > regulamin**; drugi
  przebieg identyczny co do kuponu i złotówki. **Zastrzeżenie:** w tym
  świecie ~97% kuponów to dublety (każdy wynik jest value), więc udział AKO
  jest wysoki w obu miarach i pomiar **nie rozróżnia** wariantów — to
  potwierdzenie kierunku, nie oszacowanie skutku. Skutek na danych
  rzeczywistych pokaże licznik w raporcie A–F (`ROADMAP.md` §2).
- **Filar 2 — OTWARTE, warunek startu** (paper i alerty pokażą EV liczone
  tym reżimem, Paweł będzie na nich działał). Naprawa w
  `src/valuebet/pricing/ev.py:181-410`, razem: pkt 1 (§3 ust. 4: „jakakolwiek
  kwota” przed zakładem → cały zakład w ofercie), pkt 2 (§3 ust. 11.1 i 12:
  wielokrotny niekwalifikujący się 0.94 / 1.0 zamiast 0.88), pkt 3 (udział
  tylko po stawkach, §3 ust. 5). Czerwony test najpierw (reguła 31), potem
  **powtórzona bramka §4 na nowym hashu** (zielona) i FSA przed przejściem do
  Filaru 2 (reguła 27). **Ta bramka obejmuje też strategię C — pełna ścieżka
  testów 1–7** (decyzja Pawła 2026-10-10 po audycie 4a, FSA4a-02: do tego
  czasu C jest poza bramką i poza werdyktem, „GÓRNA GRANICA, nie zbadana
  bramką”, liczby z etykietą „bez dowodu poprawności”).

### F1-P02 — okno udziału AKO (T14) vs kod (OTWARTE, 2026-10-11; decyzja Architekta/Pawła)

**ZAMKNIĘTE decyzją Architekta 2026-10-11:** §3 ust. 8 „z tym że” = po 12
miesiącach oba warunki (5000 i 12 miesięcy), kod bez zmian, rozbieżność
mianownika (pkt 1) zostaje jako wariant pesymistyczny — zapis i cytat:
`reports/audit/FIX_LOG_F1.md`, sekcja F1-P02. Treść niżej — stan badania
sprzed decyzji.

Badanie samym czytaniem kodu i liczb z testów — bez uruchamiania strategii na
prawdziwych danych, bez zmian kodu.

**(a) Mechanizm:** okno 5000 / 12 miesięcy dotyczy wyłącznie udziału AKO
(§3 ust. 8 → „Udział, o którym mowa w ust. 5”). Limit 1000 zł (ust. 3)
liczy się „od chwili rozpoczęcia Akcji Specjalnej” — bez okna.

**(b) Kod NIE liczy udziału skumulowanie.** `pricing/ev.py`
`BetclicTaxRegime.window()` (używane przez `ako_shares` →
`share_condition_met` → `tax_for_coupon`; `RegimePlanner` i `strategy_c` idą
przez tę samą funkcję) bierze kupony od `join_date`, po upływie 12 miesięcy
kalendarzowych od `join_date` tylko z ostatnich 12 miesięcy przed `now`, i
zawsze najwyżej 5000 ostatnich. Bramka sprawdza to niezależnym checkerem
(`scripts/engine_tests.py` `RefRegime`, test 3d-C; mutacja okna 12 → 3
miesiące jest wykrywana). Rozbieżności z brzmieniem, które zostają:

1. **Obrót spoza dziennika** (`external_turnover_pln`) siedzi w mianowniku
   udziału na stałe — nie wypada z okna 12 miesięcy ani 5000. Kierunek:
   pesymistyczny (zaniża udział). Skala: w C kontrfaktycznym 1000 zł wobec
   sumy stawek w oknie; świat bramki (10 000 zł, ~2250 kuponów C na 12
   miesięcy, stawki rzędu 100 zł) → ~0,4 pkt proc. udziału; wariant
   „kapitał 1000 zł” (stawki ~10× mniejsze) → rzędu kilku pkt proc. — tam może
   zmienić stan reżimu przy udziale bliskim 50% (w stronę 0.94).
2. **Po 12 miesiącach kod stosuje oba warunki naraz** (12 miesięcy **i**
   ≤ 5000); brzmienie regulaminu sugeruje, że
   okno 12 miesięcy zastępuje limit 5000. Różnica wyłącznie, gdy w 12
   miesiącach jest > 5000 kuponów; kierunek niemonotoniczny (zależy od tego,
   czy starsze kupony w oknie są AKO).
3. `join_date` w live — brak wartości → warunek udziału niespełniony (T7,
   pesymistycznie); wartość poda Paweł (ROADMAP, przed Filarem 3).

**(c) Rząd wielkości (z istniejących liczb, bez uruchamiania):** świat
bramki — E0+E1, 2 sezony, 1804 mecze, każdy wynik value (górna granica
gęstości zakładów): C 4503 kupony, A 3052 zakłady na 2 sezony (pomiar
jednego nasiona, `FIX_LOG_F1.md` 2.2) → ~2250 kuponów C i ~1500 zakładów A
na 12 miesięcy: **okno 5000 w świecie bramki się nie wypełnia**, odcięcie 12
miesięcy działa od drugiego roku. Dla prawdziwych danych (22 ligi × 7
sezonów) liczby kuponów na 12 miesięcy **nie da się oszacować bez
uruchomienia strategii** — gęstość okazji jest nieznana; górna granica
proporcjonalna do liczby meczów (~8× świat bramki) to ~19 000 kuponów C na
12 miesięcy, przy której limit 5000 by wiązał i pkt 2 miałby znaczenie.
Czy okno 12 miesięcy może zmienić stan reżimu względem liczenia
skumulowanego: **tak** — świat pasma (test mutacji okna) pokazuje, że długość
okna zmienia podatek singli, gdy udział jest blisko 50%; kod okno stosuje.

**Propozycja (do decyzji):** pkt 1 — wliczać `external_turnover_pln` jako
kupon nie-AKO z datą startu akcji (wypada z okna jak inne) albo zostawić
jako jawny wariant pesymistyczny; pkt 2 — przyjąć lekturę „po 12 miesiącach
wyłącznie 12 miesięcy, bez limitu 5000” albo
zostawić część wspólną jako wariant pesymistyczny-niemonotoniczny. Każda
zmiana kodu zmienia hash, więc wymaga bramki na nowym hashu.

### T12 i Regulamin zakładów — odczyt CLI z PDF (2026-10-09)

Pliki dostarczone przez Pawła, poza gitem (`docs/discovery/`):
`Regulamin_zak_ad_w_wzajemnych_08.06.2026_v3.pdf` (22 s., zatwierdzony
decyzją z 13.05.2026 nr DRG2.6841.6.2026; sha256 `9b133809…cd1b2dd6`) i
`8.0.pdf` (Regulaminy, Komunikaty, Szczegółowe zasady zakładów, v8.0 z
20.08.2026, 90 s.; sha256 `09a9072c…04007200`).

| temat | dosłownie | wniosek |
|---|---|---|
| min. stawka i kurs | Szczegółowe zasady pkt 3.1: „Można zawrzeć jedynie zakład o minimalnym kursie 1,14. Minimalna stawka każdego zakładu wynosi 0,50 zł.” | T12: `min_stake_pln = 0.50`; noga < 1,14 nie istnieje w ofercie (AKO i tak wymaga ≥ 1,20) |
| wyłączenia promocji | Bez Podatku 2.0 §3 ust. 2.1: systemowe, sporty wirtualne, symulowane gry w karty | T12: `excluded_markets = []` dla rynków projektu |
| Cashout | Komunikat 03/2019 pkt 6: „Zakłady rozliczone dzięki Cashout nie są liczone do obrotu jakiejkolwiek z ofert promocyjnych.” | **sprzeczne** z Bez Podatku 2.0 §3 ust. 6–7 (Cashout wlicza się do limitu i mianownika); projekt Cashout nie używa — bez skutku dla kodu |
| AKO, zdarzenia powiązane | Szczegółowe zasady pkt 2.2: „zabronione jest zawieranie zakładów na powiązane zdarzenia” (poza MyCombi) | wspiera wymóg „różne mecze” w `qualifies_as_ako` |
| freebet | Regulamin Ogólny „Freebet” pkt 3.4: wskaźnik 0.88 dla zakładów z freebetu | freebety projekt pomija |
| automaty | [Fragment usunięty z wersji publicznej: dotyczył prywatnego konta autora i korespondencji z obsługą bukmachera.] | — |

> [Fragment usunięty z wersji publicznej: dotyczył prywatnego konta autora i korespondencji z obsługą bukmachera.]
Paweł: „nie narażamy się na konsekwencje” — przy odpowiedzi negatywnej albo
niejasnej Betclic nie jest bukmacherem projektu na prawdziwe pieniądze.

### Konfiguracja (live) — `config/bookmakers.yaml`

```yaml
betclic:
  promo: bez_podatku_2_0
  promo_valid_from: 2026-05-21
  promo_verified_on: null      # data weryfikacji słowo w słowo
  join_date: null              # dzień przystąpienia Pawła do oferty
  external_turnover_pln: null  # stawki u Betclica spoza dziennika od 21.05.2026
  external_coupons: null       # liczba kuponów spoza dziennika od 21.05.2026
```

Brak wartości rozstrzyga **ładowacz konfiguracji live** według tabeli (T1,
T2, T7), zanim powstanie reżim — sam reżim dostaje komplet pól, bez `None`.
Daty: północ Europe/Warsaw, przeliczona na UTC. Plik bez sekretów.

### Wariant kontrfaktyczny — backtest (`BACKTEST_FIN_PLAN.md` §3, C)

Historia z football-data jest sprzed 21.05.2026, więc T1 wyłączałby
promocję. Strategia C to z założenia pytanie „co by było, gdyby”: ta sama
ścieżka kodu, konfiguracja `promo_valid_from` = początek symulacji,
`join_date` = początek symulacji, `promo_verified_on` = początek symulacji
(świeżość T1 sprawdza tylko ładowacz live), `external_turnover_pln = 1000`
(próg wykorzystany), `external_coupons = 0`, raport z flagą
`counterfactual: true`. T13 obowiązuje w backteście bez zmian.

**T12 w wariancie kontrfaktycznym — od 2026-10-11 (wariant B):**
`min_stake_pln = 0.50`, `excluded_markets = []` (T12 zamknięte 2026-10-09);
etykieta C: „kontrfaktyczny reżim Betclica (promocja od początku symulacji,
limit 1000 zł wykorzystany), kursy zastępcze B365/BW”; C w bramce §4 (testy
1–7) i w werdykcie (`BACKTEST_FIN_PLAN.md`, zmiany 2026-10-11). Akapit niżej
— stan do 2026-10-10, **zastąpiony**.

**T12 w wariancie kontrfaktycznym — decyzja Pawła 2026-10-08:** regulamin
(T12) nie jest jeszcze sprawdzony, w `config/bookmakers.yaml`
`min_stake_pln` i `excluded_markets` są puste. Strategia C liczona z
`min_stake_pln = 0` i bez wyłączonych rynków, z etykietą **„GÓRNA GRANICA,
T12 nieznane”**: poza progami alarmowymi, poza bramką i bez wniosków o
rentowności — służy wyłącznie mechanicznemu sprawdzeniu gałęzi promocji w
kodzie. **Alarm yield > 8% (`BACKTEST_FIN_PLAN.md` §6) obowiązuje także dla C**
— jako detektor błędu, nie werdykt (decyzja Pawła 2026-10-08, 19:25): wartość
punktowa > 8% w agregacie albo grupie lig → stop i szukanie przyczyny. C
pozostaje poza werdyktem. Reguła produkcyjna (`load_betclic_regime_config`) zostaje
pesymistyczna: puste pola T12 → promocja nieaktywna, podatek 0.88.

**Zadanie dla Pawła (przed Filarem 3):** sprawdzić w regulaminie „Bez
Podatku 2.0” minimalną stawkę kwalifikującą i listę wyłączonych rynków,
zacytować paragrafy w tabeli wyżej (T12) i wpisać wartości do
`config/bookmakers.yaml`.

---

## Inni bukmacherzy

TOTALbet, Fortuna (AKO, BetBuilder), forBET, LVBET — warunki z serwisów
porównawczych (`ROADMAP.md` §4), regulaminy nieczytane. Do weryfikacji:
`tax_factor = 0.88` (`TOR_S_PLAN.md` §4: brak wpisu → 0.88).
