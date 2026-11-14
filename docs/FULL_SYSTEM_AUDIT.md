# FULL_SYSTEM_AUDIT — protokół audytu generalnego

Obowiązuje od 2026-10-01 (`CLAUDE.md`, reguła 27). Powód: audyt toru S z
2026-10-01 (`AUDIT_REPORT_2.md`) znalazł dwa błędy KRYTYCZNE w modułach,
które przeszły wszystkie testy — w tym okno AKO sięgające w przyszłość,
warte 6 pkt proc. stawki.

---

## Kiedy

1. Po zamknięciu każdego Filaru (`ROADMAP.md` §0).
2. Przed każdym przejściem między Filarami.
3. Przed pierwszym zakładem za prawdziwe pieniądze i przed każdą zmianą
   ułamka Kelly'ego (bramka G-K).
4. Wersja skrócona (sekcje 3–4) — po każdej zmianie w `pricing/`,
   `backtest/financial.py`, `backtest/replay.py`, `live/`.

## Kto i jak

- Subagent `full-system-auditor`, **bez kontekstu implementacji**,
  adwersarialnie: zakłada, że błąd istnieje, i szuka dowodu.
- Każde znalezisko: plik i linia, reprodukcja (test albo skrypt), klasa:
  - **KRYTYCZNE** — zmienia decyzję o pieniądzach albo wynik backtestu;
  - **POWAŻNE** — może zmienić w innych danych albo po podłączeniu;
  - **DROBNE** — jakość, czytelność, dokumentacja.
- Znalezisko potwierdzone kodem **przed** naprawą (jak KRYT 1 i 2 z
  2026-10-01). Naprawa = test regresji, który failuje przed i przechodzi po
  (`CLAUDE.md` reguła 31), z wpisem w `reports/audit/FIX_LOG_<filar>.md`.
- Raport: `reports/audit/FSA_RRRR-MM-DD_<filar>.md`; podsumowanie w
  `CONTEXT.md` §5.
- **Bramka:** zero otwartych KRYTYCZNYCH i POWAŻNYCH + akceptacja Pawła w
  czacie → przejście dozwolone. DROBNE mogą zostać, z wpisem w raporcie.
  Akceptacja udzielona z góry, warunkowo, jest ważna — raport cytuje ją
  dosłownie z datą i stwierdza, czy warunek jest spełniony.

## Audyt powtórkowy — weryfikacja napraw

Gdy poprzedni FSA zostawił otwarte znaleziska, następny zaczyna od nich:

1. Każde poprzednie znalezisko dostaje status: **ZAMKNIĘTE** (z dowodem),
   **OTWARTE** albo **PRZEKLASYFIKOWANE** (z uzasadnieniem: co się zmieniło,
   że ryzyko spadło — nie „bo tak napisano w FIX_LOG").
2. **Rewers.** Dla każdego zamkniętego POWAŻNEGO i KRYTYCZNEGO: test
   regresji z HEAD uruchomiony na kodzie sprzed **tej** naprawy (procedura
   w `docs/FSA0_NAPRAWY.md` §1: własny worktree, własne `uv sync`,
   sprawdzenie `valuebet.__file__`) musi być **czerwony z powodu
   zachowania** (asercja, „DID NOT RAISE”), a na HEAD zielony. Test zielony
   na starym kodzie albo czerwony tylko przez `TypeError` sygnatury =
   naprawa nieudowodniona = znalezisko OTWARTE.
3. `FIX_LOG` to zbiór twierdzeń do sprawdzenia, nie dowód.
4. Potem pełny przegląd wszystkich sekcji w poszukiwaniu **nowych**
   znalezisk — naprawy same bywają źródłem błędów.

## Sekcje — wszystkie, w tej kolejności

### 1. Stan repozytorium
- `uv run pytest`, `ruff check`, `mypy --strict` — czysto.
- Pokrycie kodu dla `pricing/`, `backtest/`, `live/` — raport liczbowy;
  cel ≥ 90% linii w `pricing/`.
- `git status` czysty; `.env` nieśledzony; skan całej historii gita pod
  kątem sekretów (bez wypisywania wartości).
- Moduły bez wywołań poza testami → lista „niepodłączone" (reguła 29).
- Meta-testy reguł: `tests/test_rule29_wiring.py`,
  `tests/test_rule30_guards.py` zielone; lista nazw parametrów-bezpieczników
  w tym drugim nie skurczyła się od poprzedniego FSA.

### 2. Dane
- `data/raw/` niezmienione: sumy kontrolne plików vs manifest z chwili
  pobrania (reguła 12) — `scripts/verify_raw.py` zwraca 0. Do raportu
  wpisz kotwicę: liczbę wierszy manifestu i sha256 tych wierszy — następny
  FSA sprawdza, że ten prefiks się nie zmienił. Każde
  `--adopt-orphan` od poprzedniego FSA — wymień i oceń.
- Kompletność kolumn, odrzucone wiersze z powodami, pokrycie aliasów.
- Kolektor S1: luki w heartbeat, migawki per liga, zużyte kredyty.

### 3. Przecieki
- Zakres przy wyjściu z F0: istniejące moduły i skrypty; trucizny
  backtestu finansowego (niżej) są zakresem F1.
- Wszystkie testy `future_poison`.
- Trucizny backtestu finansowego (`BACKTEST_FIN_PLAN.md` §4 pkt 4).
- Okna liczone z historii (udział AKO, CLV, bramka G-K, wyłącznik) — czy
  mają **obie** granice czasowe.
- Pełna lista kontrolna `backtest-auditor`.

### 4. Poprawność finansowa
- Zakres zależy od Filaru. Przy wyjściu z F0: istniejące moduły toru S
  (wartości policzone ręcznie, ścieżki niebezpieczne, reżim podatkowy wobec
  `docs/promocje.md`). Od F1: pełne testy poniżej.
- Testy znanej odpowiedzi, placebo i podatku
  (`BACKTEST_FIN_PLAN.md` §4 pkt 1–3).
- Podwójne księgowanie: kapitał z symulatora == `reconcile_bets.py`.
- Niezmienniki: limity stawek, kapitał ≥ 0, kolejność czasów, `tax_factor`
  zgodny z regulaminem promocji w danej chwili.
- Wyłącznik 25% i bramka G-K zadziałały na danych testowych.

### 5. Zgodność
- Regulaminy i robots.txt: daty w `docs/sources.md` i `docs/promocje.md`
  nie starsze niż kwartał. Każda stała reżimu podatkowego w kodzie ma w
  `docs/promocje.md` cytat z paragrafu albo jawny wariant pesymistyczny.
- Tempo zapytań per host vs limity i `Crawl-delay`.
- Bot nie składa zakładów — przegląd kodu `live/`.

### 6. Budżet i zakres
- Wydatki: zero; lista usług zewnętrznych i ich planów.
- Każdy moduł ma pozycję w ROADMAP; przyrost kodu od poprzedniego FSA.

### 7. Dokumentacja
- `CLAUDE.md`, `ROADMAP.md`, `CONTEXT.md` zgodne ze stanem kodu.
- Każda reguła z `CLAUDE.md` ma test albo jest oznaczona jako proceduralna.

## Ostatnia linia raportu

Dokładnie: `BRAMKA: KRYT=<n> POWAŻNE=<m> OTWARTE=[<id>, …]`. Otwarte = każdy
status inny niż ZAMKNIĘTE albo PRZEKLASYFIKOWANE na DROBNE. Tę linię czyta
bramka; raportu audytora nikt poza nim nie edytuje.
