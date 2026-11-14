# Harmonogram kolektora kursów (Windows Task Scheduler)

Kolektor nie ma własnego demona. Task Scheduler odpala go **co 5 minut**
(od 2026-10-02, FSA #0 F-13; wcześniej co 15),
a kolektor sam sprawdza, czy któraś kotwica jest należna. Zwykle nie jest
i proces kończy się w sekundę.

Odwrotny układ — harmonogram wiedzący o terminarzu Ekstraklasy — wymagałby
przepisywania zadania po każdej kolejce i psułby się przy każdym
przełożonym meczu.

## Zadanie

Utwórz zadanie (PowerShell, jako Twój użytkownik, **nie** SYSTEM — klucz
API jest w `.env` w katalogu projektu):

```powershell
$akcja = New-ScheduledTaskAction `
    -Execute "<user>\Desktop\value-bet\.venv\Scripts\python.exe" `
    -Argument "scripts\collect_odds.py" `
    -WorkingDirectory "<user>\Desktop\value-bet"

$wyzwalacz = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 5)

$ustawienia = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "valuebet-odds" `
    -Action $akcja -Trigger $wyzwalacz -Settings $ustawienia
```

Dlaczego te opcje, a nie inne:

- **`-StartWhenAvailable`** — „uruchom jak najszybciej po pominiętym
  starcie". Bez tego przespany start przepada bezpowrotnie, a przegapionego
  zamknięcia nie da się nadrobić.
- **`-WakeToRun`** — budzi komputer. Na laptopach z Modern Standby bywa
  zawodne; właśnie dlatego istnieje heartbeat (niżej).
- **`-MultipleInstances IgnoreNew`** — gdy poprzedni przebieg jeszcze
  trwa, nowy jest pomijany. Dwa równoległe kolektory biłyby się o ten sam
  plik stanu.
- **`-ExecutionTimeLimit 10 min`** — zawieszone zapytanie ma zostać ubite,
  a nie blokować kolejne przebiegi.

## Pierwsze uruchomienie

```powershell
uv run python scripts\collect_odds.py --refresh
```

`--refresh` pobiera terminarz trzech lig z **bezpłatnego** `/events`
(dokumentacja v4: „does not count against the usage quota”). Nie jest
potrzebny do pracy: każdy przebieg sam odświeża terminarz ligi, gdy ostatnie
udane odświeżenie jest starsze niż 60 min — bezwarunkowo, także w trybie
oszczędnym budżetu (decyzja Pawła 2026-10-03, FSA #0d F0d-01). Płatne
odpowiedzi `/odds` terminarza nie zasilają; płatnej sondy terminarza już nie
ma.

## Terminarz, zamknięcia, przegapione

- **Koszt `/events`** — każde wywołanie trafia do
  `data/state/odds_api/usage.jsonl` (`endpoint: "/events <liga>"`, pole
  `last`). `last > 0` → kolektor wyłącza `/events` (`events_cost_alarm` w
  `state.json`) i każdy heartbeat ma błąd, do decyzji człowieka.
- **Heartbeat** — `events_refreshed` (ligi odświeżone w tym przebiegu),
  `schedule_empty` (ligi bez żadnego przyszłego meczu w terminarzu —
  informacja, nie błąd: przerwa w lidze), `errors` (m.in. brak miejsca
  < 200 MB przed płatnym wywołaniem — wywołanie pominięte).
- **`closing_missed.jsonl`** — po gwizdku każdy mecz z terminarza bez
  zamknięcia z kompletem h2h Pinnacle dostaje jeden wpis z `reason`:
  `komputer nie działał`, `budżet > 450`, `brak rynku Pinnacle`,
  `brak miejsca / błąd zapisu`, `błąd API dostawcy`. `collector_gap: true`
  tylko dla „komputer nie działał” — to są luki kolektora; brak rynku
  Pinnacle raportujemy osobno.
- **Pokrycie zamknięć** (`odds_collector.closing_coverage`) — per mecz
  (identyfikator `/events`, aktualny gwizdek), mianownik wyłącznie z
  `/events`.

## Czy to działa — heartbeat

Każdy przebieg dopisuje linię do
`data/state/odds_api/heartbeat.jsonl`, **także gdy nic się nie
należało**. To jest cały sens pliku: bez niego luka w danych jest
nieodróżnialna od spokojnego dnia bez meczów.

Ile przebiegów w ostatniej dobie (krok 5 min — powinno być ~288):

```powershell
$od = (Get-Date).AddDays(-1).ToUniversalTime().ToString("yyyy-MM-dd")
(Get-Content data\state\odds_api\heartbeat.jsonl |
    Where-Object { $_ -match $od }).Count
```

Najdłuższa przerwa między przebiegami — to ona pokazuje, czy komputer spał:

```powershell
$czasy = Get-Content data\state\odds_api\heartbeat.jsonl |
    ForEach-Object { ([pscustomobject](ConvertFrom-Json $_)).at } |
    ForEach-Object { [datetime]$_ } | Sort-Object
$max = 0
for ($i = 1; $i -lt $czasy.Count; $i++) {
    $luka = ($czasy[$i] - $czasy[$i-1]).TotalMinutes
    if ($luka -gt $max) { $max = $luka }
}
"najdluzsza przerwa: $([math]::Round($max)) min"
```

Przerwa dłuższa niż ~20 minut w dniu meczowym znaczy, że komputer spał
albo zadanie nie wystartowało. To jest dana, nie usterka do zamiecenia —
`COLLECTOR_PLAN.md` §3.4.

## Kredyty

Licznik idzie z nagłówków odpowiedzi (`x-requests-remaining`), nie z pliku
lokalnego — lokalny rozjeżdża się po każdym nieudanym przebiegu. Ostatnia
znana wartość siedzi w `data/state/odds_api/state.json`:

```powershell
(Get-Content data\state\odds_api\state.json | ConvertFrom-Json).last_usage
```

Progi (FSA #0 F-15, liczone z `x-requests-used` odświeżanego bezpłatnym
`/sports` na początku przebiegu): `used + koszt > 450` → wywołanie pominięte
(`budget_skip` w heartbeacie); zapas `450 − used < 60` → wyłącznie zamknięcia
główne. Nagłówki po każdym wywołaniu: `data/state/odds_api/usage.jsonl`.

## Zatrzymanie

```powershell
Unregister-ScheduledTask -TaskName "valuebet-odds" -Confirm:$false
```


## Diagnoza luk z 2026-10-01/02 (FSA #0 F-13)

Bez zmian ustawień systemu, z trzech źródeł: `Get-ScheduledTaskInfo`
(`LastTaskResult = 0`, `NumberOfMissedRuns` rósł tylko w czasie celowego
wyłączenia zadania), XML zadania (`schtasks /query /tn valuebet-odds /xml`:
`StartWhenAvailable = true`, `WakeToRun = true`, bez warunku zasilania
sieciowego, `MultipleInstances = IgnoreNew`, `ExecutionTimeLimit = PT10M`) i
dziennika System (Kernel-Power, Power-Troubleshooter). Dziennik
`TaskScheduler/Operational` nie był włączany.

**Przyczyna:** komputer w **Modern Standby** — zdarzenia Kernel-Power 566
(przejścia sesji) w godzinach luk heartbeatu (19:42–21:48 czasu polskiego,
czyli luki 17:03–17:33 i 19:03–20:33 UTC), uśpienie 42/107, nocne uśpienie
00:03–08:40 i wyłączenie 09:09–11:29 (Kernel-General 13/12). W Modern
Standby `-WakeToRun` bywa ignorowane — to nie błąd zadania ani kolektora
(wszystkie przebiegi `errors = []`).

**Co zmienia kod (F-13):** krok 5 min (kredyty idą tylko przy należnej
kotwicy, przebieg bez kotwicy jest darmowy), zamknięcie główne w
`[KO − 7 min, KO)`, zapasowe w `[KO − 30, KO − 7)` dla Premier League i
Bundesligi (Ekstraklasa bez zapasowego i bez `spreads` — budżet 450,
`scripts/odds_budget.py`: 430 kredytów/mies.). Klucz kotwicy to gwizdek, nie
godzina. Przegapione zamknięcie główne → `data/state/odds_api/closing_missed.jsonl`;
tygodniowe pokrycie: `odds_collector.closing_coverage` (ROADMAP §8).

Na rzeczywistych czasach przebiegów z 2026-10-01 (14 przebiegów, 255
hipotetycznych gwizdków co minutę): stare okno 25 min łapało 76.5%, nowe
`[KO − 30, KO)` na tych samych przebiegach 82.4%. Resztę strat robi uśpiony
komputer — **ryzyko szczątkowe**: komputer wyłączony albo w Modern Standby w
porze meczu gubi zamknięcie bez względu na kod. Pokrycie ≥ 95% mierzy się w
Filarze 2 (bramki G-S i G-K go wymagają).

**Dla Pawła (ustawienia systemu, nie zmieniane przez CLI):** plan zasilania
— w dni meczowe wyłączyć usypianie przy zasilaniu sieciowym albo ustawić
dłuższy czas; „Zezwalaj na czasomierze wybudzenia” = Włącz (Opcje zasilania →
Zaawansowane → Uśpienie); rozważyć wyłączenie Modern Standby w porze meczów
(komputer nie zamknięty, nie hibernowany).

## Samoczynne wyłączenia zadania (2026-10-03/04, FSA #0e) — tryb gry Avasta

Objaw: zadanie przechodzi w `Disabled` bez udziału wykonawcy, zwykle tuż po
przebiegu, i po kilku sekundach–kilkudziesięciu minutach wraca do `Ready`.
W tym czasie przebiegi się nie odbywają (`NumberOfMissedRuns` rośnie, luka w
heartbeacie). Kod projektu nie dotyka Harmonogramu (grep `schtasks`,
`ScheduledTask`, `win32com`, `ctypes.windll` w `src/`, `tests/`, `scripts/` — 0).

**Przyczyna (udowodniona dziennikiem `TaskScheduler/Operational`, czytelnym od
2026-10-03 21:56:42):** program antywirusowy **Avast, tryb gry** („Gaming
mode”). Przy wejściu w ten tryb Avast w tej samej sekundzie:
(1) wyłącza (zdarzenie 142) **wszystkie** zadania spoza `\Microsoft\` —
Lenovo, McAfee, Edge, OneDrive, WD i `valuebet-odds`; (2) rejestruje zadanie
`\AVAST Software\Gaming mode Task Scheduler recovery` (106). Przy wyjściu
ponownie włącza te zadania (140) i usuwa swoje zadanie (141). Wszystkie 10
wyłączeń `valuebet-odds` od 21:56:42 pokrywają się co do sekundy z
utworzeniem zadania Avasta:

| wyłączone (142) | włączone (Avast 141) |
|---|---|
| 2026-10-03 22:03:08 | 22:03:10 |
| 22:05:09 | 22:09:04 |
| 22:13:20 | 22:16:07 |
| 22:48:04 | 22:48:07 |
| 22:50:25 | 22:50:27 |
| 22:51:02 | 22:51:34 |
| 22:57:26 | 23:19:38 |
| 23:19:45 | 23:26:28 (uśpienie 23:27) |
| 2026-10-04 12:56:55 | 12:59:26 |
| 13:09:01 | 13:13:58 (w trakcie pełnego `pytest`) |

Epizody sprzed 21:56:42 (F0b-06 14:28–14:43, 21:13, 21:19, 21:30, 21:33) mają
ten sam wzór, ale dziennik ich nie obejmuje — przypisanie wiarygodne, nie
udowodnione. Co włącza tryb gry, dziennik nie mówi (Avast nie loguje tego do
dzienników Windows dostępnych bez administratora); bisekcja z 2026-10-03
(wyłączenia w trakcie testów, „pod obciążeniem”) jest z tym zgodna.

Skutek: zadanie stoi, dopóki Avast nie wyjdzie z trybu gry — w nocy
2026-10-03 przez 22 min (22:57–23:19), potem do uśpienia. Zamknięcie meczu
wypadające w takim oknie przepada; kolektor zapisze je w `closing_missed` z
powodem „komputer nie działał” (luka w heartbeacie).

**Dla Pawła (ustawienia programu, nie zmieniane przez CLI):** w Avaście
wyłączyć tryb gry albo jego automatyczne włączanie, albo — jeśli Avast na to
pozwala — opcję wyłączania zaplanowanych zadań w tym trybie. Kontrola po
zmianie: w `TaskScheduler/Operational` brak nowych zdarzeń 106 z
`AVAST Software\Gaming mode Task Scheduler recovery`.
