# Proweniencja `reports/lockbox_3433f2c.json`

Spisane 2026-10-02 (FSA #0 F-24). Fakty z gita:

| fakt | wartość |
|---|---|
| etykieta w pliku | `3433f2c` |
| skrypt generujący | `scripts/run_lockbox.py` |
| skrypt w drzewie `3433f2c` | **nie** (`git cat-file -e 3433f2c:scripts/run_lockbox.py` → błąd) |
| skrypt dodany do gita | `4b98818 (2026-10-01 18:48)` |
| raport dodany do gita | `eac437c (2026-10-01 22:43)` |

**Teza jakościowa wiarygodna** (FSA #0, tabela „Które liczby w `reports/`”):
DC i Elo nierozróżnialne na lockboxie i oba blisko dev; `n = 375`,
`n_clusters = 44`, uczciwe zastrzeżenie o niedziewiczym lockboxie. **Żadna
decyzja nie zależy od cyfr** — tor M jest zamknięty (ROADMAP §1), lockbox
zużyty 2026-10-01 (`reports/lockbox_views.jsonl`), drugiego przebiegu nie
będzie (`run_lockbox.py` odmawia startu).

**Wniosek:** liczby z tego pliku są **nieodtwarzalne z deklarowanego commita**
— w jego drzewie nie ma skryptu, który je wyprodukował. Plik zostaje bez
zmian (jest dowodem tego, co pokazano), a etykieta `3433f2c` nie jest
proweniencją. Od 2026-10-02 każdy raport z etykietą commita powstaje przez
`valuebet.provenance.frozen_commit()` (odmowa przy brudnym drzewie) i niesie
pole `generated_by` (FSA #0 F-24).
