# Nota do `reports/instrument_validation.json` (2026-10-02, FSA #0 F-23, W.10)

Plik zostaje bez zmian — jest zapisem tego, co pokazano 2026-10-01. Czytać z
dwiema poprawkami:

1. `valid` / `any_valid: true` stoi na kryterium bez mocy
   (`sd_ratio ∈ [0.8, 1.25]` i korelacja ≥ 0.7). Oba przedziały ufności
   nachylenia `T_ou ~ T_1x2` (`[0.8081, 0.8600]`, `[0.7535, 0.7969]`)
   **wykluczają 1** — instrument jest obciążony skalą o ~16–22%.
2. `n_clusters = 6` jest poniżej progu wiarygodności 8 (ten sam próg co
   `clv.MIN_CLUSTERS_RELIABLE`), więc i ten przedział formalnie nie daje
   werdyktu.

Bieżący raport: `reports/instrument_validation_<commit>.json` — pola
`reliable` i `verdict` liczone z liczb (`scripts/validate_instrument.py`,
`instrument_verdict`), etykieta przez `frozen_commit()`.
