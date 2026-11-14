# ARCHIWUM — decyzja o modelu biznesowym (ROADMAP, Część I z 2026-10-01, 13:29)

Zastąpiona 2026-10-01 o 14:07 modelem hybrydowym — patrz `ROADMAP.md`,
Część I. Ocena czterech ścieżek (§2–§3) nadal obowiązuje: wszystkie
odrzucone. Ścieżka C (§4) weszła do modelu hybrydowego jako tor M.

---

**Aktualizacja 2026-10-01, 13:29 — decyzja o modelu biznesowym.** Kryterium
Pawła: ścieżka do 30–50% rocznie przy rozsądnym ryzyku albo zamknięcie
projektu. Część I ocenia cztery zaproponowane ścieżki i rekomenduje model,
który ma sens ekonomiczny. Poprzedni plan zakładów (silniki S i M, rękawy
A i B, bramki, ekonomia, audyty) jest zawieszony i zarchiwizowany bez zmian
w `docs/archive/ROADMAP_zaklady_2026-10-01.md`. Część II — historia kroków
3–4 — bez zmian.

---

# CZĘŚĆ I — DECYZJA O MODELU BIZNESOWYM

## 1. Werdykt

**Żadna z czterech ścieżek nie daje 30–50% rocznie przy rozsądnym ryzyku
dla rezydenta Polski.** Dwie są nielegalne (1 i 4), jedna łamie regulaminy
bukmacherów i podstawową regułę projektu (3), jedna działa tylko wtedy, gdy
sprzedaje się coś, czego nie da się udowodnić (2). To nie jest problem
architektury, tylko trzech ograniczeń, których żadna architektura nie
zdejmuje (§3).

Model, który ma sens ekonomiczny: **monetyzacja kompetencji, nie zakładów**
(§4). Decyzja należy do Pawła: ścieżka C albo zamknięcie bez kasowania (§5).

## 2. Ocena czterech ścieżek

| ścieżka | prawo (rezydent PL) | przewaga | werdykt |
|---|---|---|---|
| 1. Brokerzy azjatyccy (BetInAsia, Sportmarket) | operatorzy bez polskiej licencji → art. 107 § 2 KKS: grzywna do 120 stawek dziennych, obligatoryjny przepadek wygranej | **ujemna** — to rynek ceny Pinnacle, a nasz model przegrywa z Pinnacle o 0.0145 log loss | **nie** |
| 2. Sygnały / SaaS (kanał VIP) | legalne jako usługa informacyjna, jeśli nie przyjmujemy stawek; wymaga działalności gospodarczej; reklama zakładów ograniczona (art. 29 i 29b UGH); bez obietnic zarobku | nieudowodniona — zero historii | **nie w zakładanej skali** (§2.2) |
| 3. Live / HFT / niszowe ligi z botem | bot stawiający łamie regulaminy (Betclic pkt 5.6: blokada konta, wstrzymanie wypłat) i regułę nr 1 projektu | **ujemna** — opóźnienie zakładu, wyższa marża live, dane wolniejsze niż oficjalne feedy bukmachera; nisze to mikrolimity i ryzyko ustawek | **nie** |
| 4. Krypto (SX Bet) | brak polskiej licencji → ten sam art. 107 § 2 KKS co przy Polymarkecie; brak KYC nie zmienia prawa | niska marża nic nie daje bez przewagi nad ceną uczciwą — a tej nie mamy | **nie** |

### 2.1 Brokerzy: dlaczego „zwycięzcy są mile widziani"

Bo prawie nikt tam nie wygrywa — to najostrzejsza cena na świecie. Brak
limitów przy ujemnej przewadze oznacza brak limitu strat. To, że broker
przyjmuje rejestrację z Polski (Sportmarket z licencją Isle of Man nie
blokuje Polski), nie czyni gry legalną w kraju gracza — zastrzegają to
nawet recenzje brokerów.

### 2.2 Sygnały: rachunek, który nie wychodzi

Uczciwy produkt kosztuje mniej, niż subskrybent na nim zarabia. Subskrybent
przy ~28 zakładach miesięcznie po 50 zł i przewadze 2.2% zarabia w
oczekiwaniu ~31 zł. Przy abonamencie 150 zł traci ~120 zł miesięcznie —
**nawet jeśli przewaga jest prawdziwa.** Do tego:
- 100 osób na tym samym kursie = kurs cięty po kilku zakładach, konta
  subskrybentów limitowane szybciej niż nasze;
- zero historii — sprzedawalibyśmy nadzieję;
- branża typerska zarabia na marketingu, nie na przewadze. Tej wersji nie
  projektujemy.

Wersja uczciwa (cena poniżej oczekiwanego zysku klienta, po miesiącach
udokumentowanych wyników) to kilka–kilkanaście złotych od osoby. Daleko od
15 000 zł miesięcznie.

### 2.3 Live i niszowe ligi: więcej obrotu przy ujemnej przewadze

Obrót mnoży przewagę, nie tworzy jej. Przy przewadze ujemnej (live: bet
delay, wyższa marża, wolniejsze dane; nisze: mikrolimity) więcej zakładów to
szybsza strata. Darmowych danych live nie ma bez scrapingu zakazanego
regulaminami, a automat stawiający jest zakazany wprost.

### 2.4 Krypto: „bez KYC" to ryzyko, nie zaleta

SX Bet nie wymienia Polski wśród krajów zakazanych, ale nie ma polskiej
licencji, więc dla rezydenta PL to ta sama sytuacja co Polymarket. Wypłata
do złotówek przechodzi przez giełdę z weryfikacją tożsamości. Niska marża
oznacza cenę bliską uczciwej — a my nie mamy przewagi nad ceną uczciwą.

### 2.5 Poza listą: promocje bukmacherów

Podwyższone kursy, freebety, gra bez podatku u licencjonowanych bukmacherów —
jedyne legalne +EV w mikroskali. Ale jednorazowe (oferty powitalne) albo
ograniczone stawką, ręczne, a regulaminy promocji zastrzegają prawo
wykluczenia uczestników. Nie spełnia kryterium powtarzalnych 30–50%.

## 3. Dlaczego żadna architektura tego nie zmienia

1. **Przewaga.** Model z samych wyników przegrywa z Pinnacle (+0.0145 log
   loss, CI [+0.0062, +0.0229]). Rynki bez limitów to dokładnie te, na
   których trzeba Pinnacle'a pobić.
2. **Prawo.** Dla rezydenta Polski legalni są wyłącznie licencjonowani
   polscy bukmacherzy: 12% podatku albo warunki promocji, plus limity.
3. **Skala.** Zwrot z kapitału rośnie z kwadratem przewagi, a kapitał jest
   mały. Nawet 50% rocznie od 2 000 zł to 1 000 zł rocznie, ~83 zł
   miesięcznie — mniej niż jedna dniówka juniora w analityce danych.

## 4. Rekomendacja: ścieżka C — monetyzacja kompetencji

Najlepszym nabywcą tego algorytmu nie jest subskrybent, tylko pracodawca.
Projekt pokazuje dokładnie to, czego szukają działy wyceny i ryzyka
bukmacherów, firmy danych sportowych i zespoły analityki ilościowej:
walk-forward bez przecieków, lockbox, CI klastrowe, Shin, Dixon-Coles z
empirycznym Bayesem, CLV, pipeline danych ze sprawdzoną zgodnością prawną.
Do tego ekonomia rynku — podatek, promocje, limity, prawo — rzadkie
połączenie u studenta zarządzania.

Rachunek: junior data scientist 9–12 tys. zł brutto miesięcznie; junior data
analyst w Warszawie średnio ~9.6 tys. zł brutto (lipiec 2026). **Jeden
miesiąc takiej pracy ≈ 9× optymistyczny roczny zysk z zakładów przy
kapitale 10 000 zł** (~1 080 zł rocznie, archiwum §7). Zero ryzyka kapitału.

### Plan C — time-box 6 tygodni (do 2026-11-12), potem zero nowych funkcji

| # | krok | po co |
|---|---|---|
| C1 | DC: poprawka `STEP4_ENSEMBLE.md` §11.9 → przebieg diagnostyczny → §11.8 → jednorazowy lockbox | czysty wynik badawczy |
| C2 | Test pokrywania: czy pula Pinnacle + nasz model przewiduje lepiej niż sam Pinnacle (dev, sparowane, CI klastrowe) | odpowiedź na pytanie badawcze; wynik pozytywny i negatywny są równie publikowalne |
| C3 | Tracker CLV na żywo z The Odds API — paper, zero pieniędzy | inżynieria produkcyjna: harmonogram, raw/interim, monitoring |
| C4 | Raport „Czy model z samych wyników bije Pinnacle w Ekstraklasie?" + README + tag `v1.0` | materiał portfolio |
| C5 | Aplikacje: działy tradingu, ryzyka i danych bukmacherów, firmy danych sportowych, analityka ilościowa | zwrot |

Przed upublicznieniem repo (C4): skan całej historii gita pod kątem sekretów;
`data/` poza repozytorium — dane z football-data i The Odds API nie są nasze
do redystrybucji. W repo tylko kod i skrypty pobierające.

**Zawieszone w ścieżce C:** scrapery polskich bukmacherów, alerty z
pieniędzmi, rękawy A i B, skalowanie. Wracają wyłącznie wtedy, gdy C2 da
wynik pozytywny i Paweł świadomie zdecyduje — z ekonomią z archiwum §7, nie
z życzeniami.

## 5. Jeśli nie C — zamknięcie bez kasowania

Jedna–dwie sesje: raport końcowy z tego, co już jest (krok 3: luka Elo −
Pinnacle z CI, metodologia bez przecieków, diagnostyka DC, ekonomia
zakładów w Polsce), README, tag `v0.9`, archiwum.

**Nie kasować repozytorium.** To jedyny składnik projektu z realnym zwrotem;
skasowanie zamienia dwa tygodnie pracy w zero.

## 6. Kontrola ścieżki C

- co tydzień: postęp vs time-box (C1–C5); każda nowa funkcja spoza tabeli →
  odrzucona albo wpisana jako „po v1.0";
- każdy commit: pytest, ruff, mypy strict, `future_poison`; `backtest-auditor`
  po zmianach w `models/`, `pricing/`, `backtest/`;
- budżet: zero złotych; The Odds API w planie darmowym, kredyty śledzone;
- 2026-11-12: niezależnie od stanu — tag i stop nowych funkcji.

## 7. Granice (stałe)

- Bot nigdy nie składa zakładu. Człowiek klika.
- Tylko licencjonowani polscy operatorzy. Bez VPN, bez brokerów, giełd i
  platform krypto bez polskiej licencji.
- robots.txt per host, łącznie z `Crawl-delay`. Bez obchodzenia anty-botów,
  bez proxy, bez rotacji IP.
- Bez sprzedaży sygnałów z obietnicą zarobku.
- Budżet zerowy. Lockbox oglądany raz.

---

