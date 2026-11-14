"""Metryki jakości prawdopodobieństw — w kolejności z reguły 24.

Log loss → reliability diagram → CLV → yield. **Accuracy nie istnieje w
tym module** i nie wolno jej tu dopisać (reguła 25): model, który trafia
55% meczów z prawdopodobieństwem 0.70, jest gorszy od modelu, który
trafia 52% z prawdopodobieństwem 0.52. Value betting żyje z kalibracji.

Konwencja: macierz prawdopodobieństw ma kształt ``(n, 3)`` w kolejności
1 / X / 2, a wynik jest indeksem 0 / 1 / 2 — jak w
``models/elo_ordinal.py``.

Każda liczba raportowana z tego modułu ma iść z ``n`` i przedziałem
ufności (reguła 11). Różnice log loss między modelami liczymy **parowanym**
bootstrapem po meczach — te same mecze, dwa modele — bo wariancja między
meczami jest o rząd większa niż różnica między modelami i nieparowany
test niczego nie odróżni.

Parowanie to jednak za mało. Mecze w obrębie jednego sezonu **nie są
niezależne**: dzieli je ten sam ordinal logit (dopasowany raz na sezon),
ten sam reżim ratingów Elo i te same drużyny. Bootstrap losujący
pojedyncze mecze traktuje je jak niezależne i zwraca CI za wąskie.
Zmierzone na Ekstraklasie: luka Elo do Pinnacle waha się między sezonami
od -0,0045 do +0,0378, czyli o rząd więcej, niż szum iid dopuszcza; CI
klastrowy po sezonach jest 1,32 raza szerszy od iid.

Dlatego ``paired_bootstrap_diff`` przyjmuje ``groups`` i wtedy losuje
**całe sezony ze zwracaniem** (cluster bootstrap), a nie pojedyncze
mecze. Dla liczby raportowanej jako wynik projektu używaj wariantu
klastrowego. Wariant iid zostaje dla porównań wewnątrz jednego sezonu,
gdzie nie ma po czym klastrować — i tam trzeba pamiętać, że jest
optymistyczny.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

from valuebet.pricing.shin import ShinNotConvergedError, shin_probabilities

__all__ = [
    "BootstrapDiff",
    "constant_probabilities",
    "log_loss",
    "log_loss_per_match",
    "market_probabilities",
    "paired_bootstrap_diff",
    "reliability_table",
]

_EPS = 1e-15

#: Poniżej tylu klastrów kwantyle bootstrapu klastrowego pochodzą z garstki
#: kombinacji i same są szumem. Nie blokujemy liczenia — oznaczamy wynik
#: jako niewiarygodny (``BootstrapDiff.reliable``), żeby raport to pokazał.
_MIN_GROUPS = 8


def _check_probs(probs: ArrayLike) -> NDArray[np.float64]:
    p = np.asarray(probs, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] != 3:
        raise ValueError(f"oczekiwano macierzy (n, 3), jest {p.shape}")
    if np.isnan(p).any():
        raise ValueError(
            "prawdopodobieństwa zawierają NaN — wypełnij albo odfiltruj JAWNIE"
        )
    if (p < 0).any() or (p > 1).any():
        raise ValueError("prawdopodobieństwa poza [0, 1]")
    if not np.allclose(p.sum(axis=1), 1.0, atol=1e-6):
        raise ValueError("wiersze nie sumują się do 1 — to nie jest rozkład")
    return p


def log_loss_per_match(probs: ArrayLike, outcome: ArrayLike) -> NDArray[np.float64]:
    """-log p(wynik) dla każdego meczu. Do bootstrapu i do sumowania."""
    p = _check_probs(probs)
    y = np.asarray(outcome, dtype=np.int64)
    if y.shape != (p.shape[0],):
        raise ValueError("outcome musi mieć długość n")
    picked = np.clip(p[np.arange(len(y)), y], _EPS, 1.0)
    return np.asarray(-np.log(picked), dtype=np.float64)


def log_loss(probs: ArrayLike, outcome: ArrayLike) -> float:
    return float(log_loss_per_match(probs, outcome).mean())


def constant_probabilities(outcome_train: ArrayLike, n: int) -> NDArray[np.float64]:
    """Baseline „stała": częstości 1X2 z TRAINU, powielone na n meczów testu.

    Częstości liczone z testu byłyby przeciekiem — model widziałby
    rozkład wyników, które ma przewidzieć.
    """
    y = np.asarray(outcome_train, dtype=np.int64)
    if len(y) == 0:
        raise ValueError("pusty zbiór treningowy")
    freq = np.bincount(y, minlength=3).astype(np.float64) / len(y)
    return np.tile(freq, (n, 1))


@dataclass(frozen=True)
class BootstrapDiff:
    """Różnica średnich (a - b) z przedziałem ufności. Ujemna = a lepsze.

    ``n_groups is None`` oznacza bootstrap iid po meczach — **CI jest wtedy
    za wąskie**, jeśli obserwacje są skorelowane wewnątrz sezonu. Wariant
    klastrowy ma ``n_groups`` równe liczbie wylosowanych jednostek.
    """

    n: int
    mean_diff: float
    ci_low: float
    ci_high: float
    confidence: float
    n_groups: int | None = None

    @property
    def excludes_zero(self) -> bool:
        return self.ci_low > 0.0 or self.ci_high < 0.0

    @property
    def is_clustered(self) -> bool:
        return self.n_groups is not None

    @property
    def reliable(self) -> bool:
        """Czy CI wolno czytać dosłownie.

        Bootstrap iid jest zawsze „wiarygodny" w sensie technicznym, ale
        optymistyczny przy korelacji — to sygnalizuje ``is_clustered``.
        Bootstrap klastrowy z garstką klastrów daje kwantyle z kilkunastu
        możliwych kombinacji i nie niesie informacji.
        """
        return self.n_groups is None or self.n_groups >= _MIN_GROUPS


def paired_bootstrap_diff(
    a: ArrayLike,
    b: ArrayLike,
    *,
    groups: ArrayLike | None = None,
    n_boot: int = 4000,
    confidence: float = 0.95,
    seed: int = 0,
) -> BootstrapDiff:
    """Parowany bootstrap różnicy średnich per mecz. Deterministyczny (seed).

    Parameters
    ----------
    groups:
        Etykieta klastra per mecz (u nas: sezon). Podana — losujemy **całe
        klastry ze zwracaniem**, nie pojedyncze mecze. To jedyny wariant,
        którego wolno użyć do liczby raportowanej na zewnątrz: mecze w
        sezonie dzielą jedno dopasowanie modelu i nie są niezależne
        (patrz docstring modułu). Pominięta — bootstrap iid po meczach.

    Notes
    -----
    Przy losowaniu klastrów długość próby bootstrapowej się zmienia (sezony
    mają różne ``n``), więc średnią liczymy jako ``suma / liczność``, a nie
    jako średnią ze średnich sezonowych. Ważenie liczebnością jest zgodne
    ze statystyką punktową, którą raportujemy.
    """
    x = np.asarray(a, dtype=np.float64)
    z = np.asarray(b, dtype=np.float64)
    if x.shape != z.shape or x.ndim != 1:
        raise ValueError("a i b muszą być wektorami tej samej długości (te same mecze)")
    if len(x) == 0:
        raise ValueError("brak meczów do porównania")
    diff = x - z
    alpha = (1.0 - confidence) / 2.0
    rng = np.random.default_rng(seed)

    if groups is None:
        idx = rng.integers(0, len(diff), size=(n_boot, len(diff)))
        means = diff[idx].mean(axis=1)
        n_groups = None
    else:
        g = np.asarray(groups)
        if g.shape != diff.shape:
            raise ValueError("groups musi mieć tę samą długość co a i b")
        _, codes = np.unique(g, return_inverse=True)
        n_groups = int(codes.max()) + 1
        # Suma i liczność per klaster wystarczą — średnia z konkatenacji
        # wylosowanych klastrów to sum(sumy) / sum(liczności), dokładnie.
        sums = np.bincount(codes, weights=diff, minlength=n_groups)
        counts = np.bincount(codes, minlength=n_groups).astype(np.float64)
        pick = rng.integers(0, n_groups, size=(n_boot, n_groups))
        means = sums[pick].sum(axis=1) / counts[pick].sum(axis=1)

    lo, hi = np.quantile(means, [alpha, 1.0 - alpha])
    return BootstrapDiff(
        n=len(diff),
        mean_diff=float(diff.mean()),
        ci_low=float(lo),
        ci_high=float(hi),
        confidence=confidence,
        n_groups=n_groups,
    )


def reliability_table(
    predicted: ArrayLike,
    observed: ArrayLike,
    *,
    n_bins: int = 10,
) -> pd.DataFrame:
    """Reliability diagram w formie tabeli: koszyk → średnia predykcja vs realizacja.

    ``observed`` może być 0/1 (wynik binarny) albo 0/0.5/1 (wynik w skali
    Elo). Koszyki o równej szerokości na [0, 1]; puste są pomijane, a
    koszyki z małym ``n`` trzeba czytać z odpowiednią nieufnością — stąd
    kolumna ``n`` i błąd standardowy realizacji.
    """
    p = np.asarray(predicted, dtype=np.float64)
    y = np.asarray(observed, dtype=np.float64)
    if p.shape != y.shape or p.ndim != 1:
        raise ValueError("predicted i observed muszą być wektorami tej samej długości")
    if (p < 0).any() or (p > 1).any():
        raise ValueError("predicted poza [0, 1]")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    # Prawa krawędź ostatniego koszyka domknięta, żeby p = 1.0 nie wypadło.
    which = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, n_bins - 1)

    rows: list[dict[str, float | int]] = []
    for b in range(n_bins):
        mask = which == b
        n = int(mask.sum())
        if n == 0:
            continue
        obs = y[mask]
        rows.append(
            {
                "bin_low": float(edges[b]),
                "bin_high": float(edges[b + 1]),
                "n": n,
                "mean_predicted": float(p[mask].mean()),
                "mean_observed": float(obs.mean()),
                "se_observed": float(obs.std(ddof=1) / np.sqrt(n))
                if n > 1
                else float("nan"),
            }
        )
    table = pd.DataFrame(rows)
    table["gap"] = table["mean_observed"] - table["mean_predicted"]
    return table


def market_probabilities(closing: pd.DataFrame) -> pd.DataFrame:
    """Kursy zamknięcia 1X2 → prawdopodobieństwa po Shinie, per mecz.

    Wejście: ramka z ``match_id, odds_home, odds_draw, odds_away`` dla
    JEDNEGO bukmachera. Wyjście: ``match_id, p_home, p_draw, p_away, z,
    booksum``. Mecze, dla których solver nie zbiegł, są pomijane i liczone
    w atrybucie ``.attrs["not_converged"]`` — nie wypełniamy ich niczym.

    To jest jedyne dopuszczalne usuwanie marży (reguła 16). Wynik służy
    WYŁĄCZNIE jako punkt odniesienia — nigdy jako cecha modelu.
    """
    required = {"match_id", "odds_home", "odds_draw", "odds_away"}
    missing = required - set(closing.columns)
    if missing:
        raise ValueError(f"market_probabilities: brak kolumn {sorted(missing)}")
    if closing["match_id"].duplicated().any():
        raise ValueError(
            "market_probabilities: jeden bukmacher na wywołanie — match_id się powtarza"
        )

    rows: list[dict[str, float | str]] = []
    not_converged = 0
    ids = closing["match_id"].astype(str).to_numpy()
    odds = closing[["odds_home", "odds_draw", "odds_away"]].to_numpy(dtype=np.float64)
    for match_id, trio in zip(ids, odds, strict=True):
        try:
            result = shin_probabilities(trio, strict=True)
        except ShinNotConvergedError:
            not_converged += 1
            continue
        ph, pd_, pa = result.probabilities
        rows.append(
            {
                "match_id": str(match_id),
                "p_home": float(ph),
                "p_draw": float(pd_),
                "p_away": float(pa),
                "z": result.z,
                "booksum": result.booksum,
            }
        )
    out = pd.DataFrame(
        rows, columns=["match_id", "p_home", "p_draw", "p_away", "z", "booksum"]
    )
    out.attrs["not_converged"] = not_converged
    return out
