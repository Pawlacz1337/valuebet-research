"""Walk-forward baseline Elo vs rynek — pierwsza uczciwa diagnoza projektu.

Co to liczy
-----------
Dla każdego sezonu testowego ``S``:

1. Elo idzie chronologicznie po CAŁEJ historii (``compute_elo``). To nie
   jest przeciek: rating przed meczem ``t`` zależy wyłącznie od meczów
   sprzed ``t``, niezależnie od tego, ile meczów jest po nim.
2. Ordered logit (Elo → 1X2) dopasowany **tylko na sezonach < S**, potem
   zastosowany do ``S``. To jedyna dopasowywana rzecz i jest dopasowana
   poza zbiorem testowym (reguły 8-10).
3. Baseline „stała" = częstości 1X2 z sezonów < S.
4. Rynek = zamknięcie po Shinie, osobno dla każdego bukmachera
   referencyjnego. Porównanie parowane — te same mecze, dwa modele.

Metryki w kolejności z reguły 24: log loss, reliability diagram. **CLV
nie jest tu liczone** — football-data nie ma kursów sprzed zamknięcia,
więc nie ma ceny wejścia, względem której CLV miałoby sens. Luka w log
loss między Elo a zamknięciem jest najbliższym uczciwym proxy tego, czy
model wie coś, czego rynek nie wie. CLV pojawi się, gdy poller zbierze
własne snapshoty kursów przedmeczowych.

Czego się spodziewać
--------------------
Elo NIE pobije zamknięcia. Wartość diagnostyczna jest w wielkości luki
(CONTEXT.md §6): <0,01 → Elo zaskakująco dobre, dokładamy cechy; >0,03 →
model ratingowy nie wystarcza, potrzebny model golowy. Jeśli Elo pobije
rynek — to bug, nie odkrycie. Szukaj przecieku przed raportowaniem.

Dwie referencje, dwie luki
--------------------------
Pinnacle (2012/13-2024/25) i Betfair Exchange (od 2024/25) są raportowane
**osobno** i nigdy nie są sklejane w jedną liczbę — exchange ma inną
strukturę marży i innych graczy niż book (ROADMAP.md, krok 3).

Osobno znaczy też: **nie zestawiaj ich obok siebie jako dwóch pomiarów
tej samej rzeczy.** Pinnacle pokrywa 3055 meczów, BFEC 656, wspólnych
jest 418 — to w większości różne mecze z różnych lat. Różnica między
luką +0,0145 a +0,0121 jest wtedy w pierwszej kolejności różnicą
podzbioru, nie różnicą źródeł. Dlatego raport liczy dodatkowo
``reference_overlaps``: obie luki na **tych samych** meczach, gdzie
porównanie ma sens. Czytaj tamtą sekcję, zanim wyciągniesz wniosek
„exchange łatwiej pobić".

Przedziały ufności
------------------
Liczby pooled dostają CI z bootstrapu **klastrowego po sezonach**
(``metrics.paired_bootstrap_diff(groups=...)``). Mecze w sezonie dzielą
jedno dopasowanie ordinal logit i jeden reżim ratingów — bootstrap iid
po meczach zwraca CI za wąskie o ~30%. Luki per sezon mają z konieczności
CI iid (jeden sezon = jeden klaster) i są przez to optymistyczne;
w raporcie są oznaczone.
"""

from __future__ import annotations

import argparse
import itertools
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from valuebet.backtest.lockbox import assert_no_lockbox, split_dev_lockbox
from valuebet.backtest.metrics import (
    BootstrapDiff,
    constant_probabilities,
    log_loss_per_match,
    market_probabilities,
    paired_bootstrap_diff,
    reliability_table,
)
from valuebet.features.elo import EloConfig, compute_elo
from valuebet.models.elo_ordinal import OrdinalElo, outcome_index

__all__ = [
    "BaselineReport",
    "EloSanity",
    "MarketGap",
    "ReferenceOverlap",
    "SeasonResult",
    "format_report",
    "main",
    "run_elo_baseline",
]

log = logging.getLogger(__name__)

DEFAULT_REFERENCES: tuple[str, ...] = ("pinnacle", "betfair_exchange")
_PROB_COLS = ["p_home", "p_draw", "p_away"]


@dataclass(frozen=True)
class MarketGap:
    """Luka Elo - rynek w log loss na wspólnych meczach. Dodatnia = rynek lepszy.

    ``seasons`` jest częścią wyniku, nie ozdobą: dwie luki policzone na
    różnych zakresach sezonów nie są porównywalne, a bez tej krotki nie
    widać, że zakresy się różnią.
    """

    bookmaker: str
    n: int
    seasons: tuple[str, ...]
    log_loss_elo: float
    log_loss_market: float
    diff: BootstrapDiff


@dataclass(frozen=True)
class ReferenceOverlap:
    """Dwie referencje na **tych samych** meczach — jedyne uczciwe porównanie.

    ``gap_a`` i ``gap_b`` to luki Elo do każdej z referencji, policzone na
    przecięciu. ``market_diff`` to parowana różnica log lossów samych
    referencji (A - B); ujemna = A lepiej wycenia. Jeśli ``market_diff``
    nie odróżnia się od zera, a luki pooled się różnią, różnica pooled
    jest artefaktem podzbioru.
    """

    bookmaker_a: str
    bookmaker_b: str
    n: int
    seasons: tuple[str, ...]
    gap_a: MarketGap
    gap_b: MarketGap
    market_diff: BootstrapDiff


@dataclass(frozen=True)
class SeasonResult:
    season: str
    n: int
    n_train: int
    log_loss_constant: float
    log_loss_elo: float
    ordinal: OrdinalElo
    gaps: tuple[MarketGap, ...]


@dataclass(frozen=True)
class EloSanity:
    """Kontrole z CONTEXT.md §6, zadanie 3.

    ``sum_final ≈ expected_sum`` obowiązuje tylko przy ``season_carry=1.0``.
    Przy carry < 1 w lidze otwartej suma dryfuje w dół: drużyny, które
    spadły, zamrażają swoje (zwykle ujemne) odchylenie od 1500, a te, które
    zostały, mają dodatnie odchylenie ściągane co sezon. Zweryfikowane na
    Ekstraklasie 2012-2026: carry=1.0 daje sumę co do grosza, carry=0.75
    daje -933 na 34 drużyny. To mechanika, nie bug.
    """

    n_teams: int
    sum_final: float
    expected_sum: float
    top: tuple[tuple[str, float], ...]
    bottom: tuple[tuple[str, float], ...]
    max_abs_step: float
    n_matches_without_result: int


@dataclass
class BaselineReport:
    seasons: list[SeasonResult]
    #: Wszystkie predykcje out-of-sample: match_id, season, outcome,
    #: ll_constant, ll_elo, p_home, p_draw, p_away, elo_expected_home.
    predictions: pd.DataFrame
    pooled_gaps: tuple[MarketGap, ...]
    #: Luki policzone na przecięciu par referencji — jedyne miejsce, gdzie
    #: wolno je ze sobą zestawiać. Puste, jeśli referencji jest mniej niż dwie
    #: albo nie mają wspólnych meczów.
    reference_overlaps: tuple[ReferenceOverlap, ...]
    reliability_expected_score: pd.DataFrame
    reliability_home: pd.DataFrame
    reliability_draw: pd.DataFrame
    reliability_away: pd.DataFrame
    sanity: EloSanity
    config: EloConfig = field(default_factory=EloConfig)

    @property
    def n(self) -> int:
        return len(self.predictions)

    @property
    def pooled_log_loss_constant(self) -> float:
        return float(self.predictions["ll_constant"].mean())

    @property
    def pooled_log_loss_elo(self) -> float:
        return float(self.predictions["ll_elo"].mean())


def _sanity(
    ratings_final: dict[str, float],
    history: pd.DataFrame,
    config: EloConfig,
    n_without_result: int,
) -> EloSanity:
    ranked = sorted(ratings_final.items(), key=lambda kv: kv[1], reverse=True)
    if history.empty:
        max_step = 0.0
    else:
        ordered = history.sort_values(["team_id", "kickoff_utc"], kind="mergesort")
        steps = ordered.groupby("team_id", sort=False)["rating_after"].diff().abs()
        max_step = float(steps.max()) if steps.notna().any() else 0.0
    n_teams = len(ratings_final)
    return EloSanity(
        n_teams=n_teams,
        sum_final=float(sum(ratings_final.values())),
        expected_sum=config.initial * n_teams,
        top=tuple((t, round(r, 1)) for t, r in ranked[:8]),
        bottom=tuple((t, round(r, 1)) for t, r in ranked[-5:]),
        max_abs_step=max_step,
        n_matches_without_result=n_without_result,
    )


def _market_log_loss(joined: pd.DataFrame, suffix: str) -> NDArray[np.float64]:
    cols = [f"{c}{suffix}" for c in _PROB_COLS]
    return log_loss_per_match(joined[cols].to_numpy(), joined["outcome"].to_numpy())


def _market_gap(
    bookmaker: str,
    predictions: pd.DataFrame,
    market: pd.DataFrame,
    *,
    seed: int,
    clustered: bool,
) -> MarketGap | None:
    """Parowane porównanie na przecięciu meczów. None, jeśli przecięcie puste.

    ``clustered`` włącza bootstrap po sezonach. Dla luk pooled zawsze True —
    inaczej CI jest za wąskie (docstring modułu). Dla pojedynczego sezonu
    nie ma po czym klastrować, więc False.

    Mecze bez kursu tej referencji wypadają przez ``how="inner"``. To nie
    jest cicha strata: ``n`` i ``seasons`` w wyniku pokazują dokładnie, na
    czym liczba powstała, a ``MarketGap`` bez tych pól nie istnieje.
    """
    joined = predictions.merge(
        market, on="match_id", how="inner", suffixes=("", "_mkt")
    )
    if joined.empty:
        return None
    ll_market = _market_log_loss(joined, "_mkt")
    ll_elo = joined["ll_elo"].to_numpy()
    groups = joined["season"].to_numpy() if clustered else None
    return MarketGap(
        bookmaker=bookmaker,
        n=len(joined),
        seasons=tuple(sorted(pd.unique(joined["season"]).tolist())),
        log_loss_elo=float(ll_elo.mean()),
        log_loss_market=float(ll_market.mean()),
        diff=paired_bootstrap_diff(ll_elo, ll_market, groups=groups, seed=seed),
    )


def _reference_overlap(
    bookmaker_a: str,
    bookmaker_b: str,
    predictions: pd.DataFrame,
    markets: dict[str, pd.DataFrame],
    *,
    seed: int,
) -> ReferenceOverlap | None:
    """Obie referencje ograniczone do meczów, dla których są OBIE.

    Bez tego zestawienie dwóch luk pooled porównuje głównie podzbiory
    (ROADMAP krok 3: n=3055 vs n=656, wspólnych 418).
    """
    # Jawne przemianowanie zamiast suffixes= — przy dwóch kolejnych mergach
    # tych samych trzech kolumn pandas potrafi wyprodukować duplikaty nazw.
    def _tagged(bookmaker: str, tag: str) -> pd.DataFrame:
        return markets[bookmaker][["match_id", *_PROB_COLS]].rename(
            columns={c: f"{c}_{tag}" for c in _PROB_COLS}
        )

    both = predictions.merge(
        _tagged(bookmaker_a, "a"), on="match_id", how="inner", validate="one_to_one"
    ).merge(
        _tagged(bookmaker_b, "b"), on="match_id", how="inner", validate="one_to_one"
    )
    if both.empty:
        return None

    common = predictions[predictions["match_id"].isin(both["match_id"])]
    gap_a = _market_gap(
        bookmaker_a, common, markets[bookmaker_a], seed=seed, clustered=True
    )
    gap_b = _market_gap(
        bookmaker_b, common, markets[bookmaker_b], seed=seed, clustered=True
    )
    if gap_a is None or gap_b is None:  # pragma: no cover - both niepuste
        return None

    ll_a = _market_log_loss(both, "_a")
    ll_b = _market_log_loss(both, "_b")
    return ReferenceOverlap(
        bookmaker_a=bookmaker_a,
        bookmaker_b=bookmaker_b,
        n=len(both),
        seasons=tuple(sorted(pd.unique(both["season"]).tolist())),
        gap_a=gap_a,
        gap_b=gap_b,
        market_diff=paired_bootstrap_diff(
            ll_a, ll_b, groups=both["season"].to_numpy(), seed=seed
        ),
    )


def run_elo_baseline(
    matches: pd.DataFrame,
    closing: pd.DataFrame,
    *,
    config: EloConfig | None = None,
    min_train_seasons: int = 3,
    references: tuple[str, ...] = DEFAULT_REFERENCES,
    seed: int = 0,
) -> BaselineReport:
    """Walk-forward po sezonach. Patrz docstring modułu.

    Parameters
    ----------
    matches:
        Ramka z ``ingest/football_data`` (kolumny ``schema.Match``).
        Mecze bez wyniku są pomijane w metrykach (nie da się ich ocenić),
        ale liczone w ``sanity``.
    closing:
        Tabela ``closing_odds`` — używana WYŁĄCZNIE jako referencja.
    min_train_seasons:
        Pierwszy sezon testowy ma co najmniej tyle pełnych sezonów przed
        sobą. Mniej = ordered logit dopasowany na kilkuset meczach i szum.
    """
    config = config or EloConfig()
    required = {
        "match_id",
        "season",
        "kickoff_utc",
        "home_team_id",
        "away_team_id",
        "home_goals",
        "away_goals",
    }
    missing = required - set(matches.columns)
    if missing:
        raise ValueError(f"run_elo_baseline: brak kolumn {sorted(missing)}")
    if matches["match_id"].duplicated().any():
        raise ValueError(
            "run_elo_baseline: powtórzone match_id — ten sam mecz nie może być dwa razy"
        )

    # Elo na całej historii — sekwencyjnie, stan SPRZED meczu.
    elo = compute_elo(matches, config)
    frame = matches.merge(
        elo.features, on="match_id", how="left", validate="one_to_one"
    )

    with_result = frame["home_goals"].notna() & frame["away_goals"].notna()
    n_without = int((~with_result).sum())
    frame = frame.loc[with_result].copy()
    frame["outcome"] = outcome_index(
        frame["home_goals"].to_numpy(dtype=np.float64),
        frame["away_goals"].to_numpy(dtype=np.float64),
    )
    frame = frame.sort_values(
        ["kickoff_utc", "match_id"], kind="mergesort"
    ).reset_index(drop=True)

    seasons = sorted(frame["season"].unique())
    if len(seasons) <= min_train_seasons:
        raise ValueError(
            f"za mało sezonów: {len(seasons)}, potrzeba > {min_train_seasons} "
            "(train + co najmniej jeden test)"
        )

    # Referencje rynkowe — Shin per bukmacher, tylko kompletne rynki.
    markets: dict[str, pd.DataFrame] = {}
    for bookmaker in references:
        subset = closing.loc[
            closing["bookmaker"] == bookmaker,
            ["match_id", "odds_home", "odds_draw", "odds_away"],
        ]
        if subset.empty:
            log.warning("brak kursów zamknięcia dla referencji %r", bookmaker)
            continue
        probs = market_probabilities(subset)
        if probs.attrs.get("not_converged"):
            log.warning(
                "%s: Shin nie zbiegł dla %d meczów — pominięte",
                bookmaker,
                probs.attrs["not_converged"],
            )
        markets[bookmaker] = probs

    season_results: list[SeasonResult] = []
    prediction_parts: list[pd.DataFrame] = []

    for i, test_season in enumerate(seasons):
        if i < min_train_seasons:
            continue
        train_seasons = seasons[:i]
        train = frame[frame["season"].isin(train_seasons)]
        test = frame[frame["season"] == test_season]

        ordinal = OrdinalElo.fit(
            train["elo_diff"].to_numpy(), train["outcome"].to_numpy()
        )
        probs_elo = ordinal.predict_proba(test["elo_diff"].to_numpy())
        probs_const = constant_probabilities(train["outcome"].to_numpy(), len(test))
        y = test["outcome"].to_numpy()

        preds = pd.DataFrame(
            {
                "match_id": test["match_id"].to_numpy(),
                "season": test_season,
                "outcome": y,
                "ll_constant": log_loss_per_match(probs_const, y),
                "ll_elo": log_loss_per_match(probs_elo, y),
                "p_home": probs_elo[:, 0],
                "p_draw": probs_elo[:, 1],
                "p_away": probs_elo[:, 2],
                "elo_expected_home": test["elo_expected_home"].to_numpy(),
            }
        )
        prediction_parts.append(preds)

        # Per sezon: jeden klaster, więc bootstrap iid. CI jest tu
        # optymistyczne i raport to oznacza.
        gaps = tuple(
            gap
            for bookmaker, market in markets.items()
            if (
                gap := _market_gap(
                    bookmaker, preds, market, seed=seed, clustered=False
                )
            )
            is not None
        )
        season_results.append(
            SeasonResult(
                season=test_season,
                n=len(test),
                n_train=len(train),
                log_loss_constant=float(preds["ll_constant"].mean()),
                log_loss_elo=float(preds["ll_elo"].mean()),
                ordinal=ordinal,
                gaps=gaps,
            )
        )

    predictions = pd.concat(prediction_parts, ignore_index=True)
    pooled_gaps = tuple(
        gap
        for bookmaker, market in markets.items()
        if (
            gap := _market_gap(
                bookmaker, predictions, market, seed=seed, clustered=True
            )
        )
        is not None
    )
    names = list(markets)
    reference_overlaps = tuple(
        overlap
        for a, b in itertools.combinations(names, 2)
        if (overlap := _reference_overlap(a, b, predictions, markets, seed=seed))
        is not None
    )

    y_all = predictions["outcome"].to_numpy()
    realized_score = np.where(y_all == 0, 1.0, np.where(y_all == 1, 0.5, 0.0))

    return BaselineReport(
        seasons=season_results,
        predictions=predictions,
        pooled_gaps=pooled_gaps,
        reference_overlaps=reference_overlaps,
        reliability_expected_score=reliability_table(
            predictions["elo_expected_home"], realized_score
        ),
        reliability_home=reliability_table(
            predictions["p_home"], (y_all == 0).astype(float)
        ),
        reliability_draw=reliability_table(
            predictions["p_draw"], (y_all == 1).astype(float)
        ),
        reliability_away=reliability_table(
            predictions["p_away"], (y_all == 2).astype(float)
        ),
        sanity=_sanity(elo.final, elo.history(), config, n_without),
        config=config,
    )


# ---------------------------------------------------------------------------
# Raport tekstowy
# ---------------------------------------------------------------------------


def _fmt_ci(d: BootstrapDiff) -> str:
    """CI z jawnym rodzajem bootstrapu — bez tego czytelnik nie wie, co czyta."""
    sig = "istotna" if d.excludes_zero else "NIEistotna"
    if not d.is_clustered:
        kind = "CI iid, optymistyczne"
    elif not d.reliable:
        kind = f"CI klastrowe, tylko {d.n_groups} sezony — NIEWIARYGODNE"
    else:
        kind = f"CI klastrowe po {d.n_groups} sezonach"
    return f"[{d.ci_low:+.4f}, {d.ci_high:+.4f}] ({sig}; {kind})"


def _fmt_gap(gap: MarketGap) -> str:
    return (
        f"    {gap.bookmaker:<17} n={gap.n:<5} LL elo={gap.log_loss_elo:.4f} "
        f"LL rynek={gap.log_loss_market:.4f}  luka={gap.diff.mean_diff:+.4f} "
        f"{_fmt_ci(gap.diff)}"
    )


def _fmt_overlap(ov: ReferenceOverlap) -> str:
    lines = [
        f"  {ov.bookmaker_a} vs {ov.bookmaker_b} na wspólnych meczach: "
        f"n={ov.n} ({ov.seasons[0]}-{ov.seasons[-1]})",
        _fmt_gap(ov.gap_a),
        _fmt_gap(ov.gap_b),
    ]
    d = ov.market_diff
    lines.append(
        f"    różnica luk (na tych samych meczach): "
        f"{ov.gap_a.diff.mean_diff - ov.gap_b.diff.mean_diff:+.4f}"
    )
    lines.append(
        f"    LL({ov.bookmaker_a}) - LL({ov.bookmaker_b}) = {d.mean_diff:+.4f} "
        f"{_fmt_ci(d)}"
    )
    if not d.excludes_zero:
        lines.append(
            "    -> referencje wyceniają nierozróżnialnie dobrze. Każda różnica"
        )
        lines.append(
            "      między lukami pooled jest artefaktem podzbioru, nie źródła."
        )
    return "\n".join(lines)


def _fmt_reliability(table: pd.DataFrame) -> str:
    lines = ["    koszyk        n    pred    obs     gap    se"]
    for r in table.itertuples(index=False):
        lines.append(
            f"    [{r.bin_low:.1f},{r.bin_high:.1f})  {r.n:>5}  {r.mean_predicted:.3f}  "
            f"{r.mean_observed:.3f}  {r.gap:+.3f}  {r.se_observed:.3f}"
        )
    return "\n".join(lines)


def format_report(report: BaselineReport) -> str:
    s = report.sanity
    out: list[str] = []
    out.append("=== ELO — sanity check ===")
    out.append(
        f"  drużyn: {s.n_teams}; suma ratingów {s.sum_final:.1f} vs oczekiwane {s.expected_sum:.1f} "
        f"(różnica {s.sum_final - s.expected_sum:+.1f})"
    )
    out.append(f"  największy pojedynczy skok ratingu: {s.max_abs_step:.1f} pkt")
    out.append(
        f"  meczów bez wyniku (pominięte w metrykach): {s.n_matches_without_result}"
    )
    out.append("  góra tabeli Elo: " + ", ".join(f"{t} {r}" for t, r in s.top))
    out.append("  dół tabeli Elo:  " + ", ".join(f"{t} {r}" for t, r in s.bottom))
    out.append("")
    out.append(
        f"=== WALK-FORWARD (Elo {report.config.k=}, {report.config.home_advantage=}) ==="
    )
    out.append("  sezon     n_train  n     LL stała  LL elo    luki do rynku")
    for r in report.seasons:
        out.append(
            f"  {r.season:<9} {r.n_train:<8} {r.n:<5} {r.log_loss_constant:.4f}    {r.log_loss_elo:.4f}"
        )
        for gap in r.gaps:
            out.append(_fmt_gap(gap))
    out.append("")
    out.append(f"=== POOLED out-of-sample: n={report.n} ===")
    out.append(
        f"  LL stała = {report.pooled_log_loss_constant:.4f}   LL elo = {report.pooled_log_loss_elo:.4f}"
    )
    const_vs_elo = paired_bootstrap_diff(
        report.predictions["ll_elo"],
        report.predictions["ll_constant"],
        groups=report.predictions["season"].to_numpy(),
    )
    out.append(
        f"  elo - stała = {const_vs_elo.mean_diff:+.4f} {_fmt_ci(const_vs_elo)}"
    )
    out.append(
        "  luki do rynku (dodatnia = rynek lepszy; raportowane OSOBNO, nie sumować):"
    )
    for gap in report.pooled_gaps:
        out.append(_fmt_gap(gap))
        out.append(
            f"      zakres: {gap.seasons[0]}-{gap.seasons[-1]} "
            f"({len(gap.seasons)} sezonów)"
        )
    out.append("")
    if report.reference_overlaps:
        out.append("=== REFERENCJE NA WSPÓLNYM PODZBIORZE ===")
        out.append(
            "  Luk pooled powyżej NIE WOLNO porównywać między sobą — stoją na"
        )
        out.append("  różnych meczach. Porównywalne są dopiero te:")
        for overlap in report.reference_overlaps:
            out.append(_fmt_overlap(overlap))
        out.append("")
    out.append("=== RELIABILITY: elo_expected_home vs realizacja (1 / 0.5 / 0) ===")
    out.append(_fmt_reliability(report.reliability_expected_score))
    out.append("=== RELIABILITY: P(1) po ordered logit vs zwycięstwo gospodarza ===")
    out.append(_fmt_reliability(report.reliability_home))
    out.append("=== RELIABILITY: P(X) vs remis ===")
    out.append(_fmt_reliability(report.reliability_draw))
    out.append("=== RELIABILITY: P(2) vs zwycięstwo gościa ===")
    out.append(_fmt_reliability(report.reliability_away))
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Walk-forward baseline Elo vs rynek")
    parser.add_argument(
        "--matches",
        type=Path,
        default=Path("data/interim/football_data/matches.parquet"),
    )
    parser.add_argument(
        "--closing",
        type=Path,
        default=Path("data/interim/football_data/closing_odds.parquet"),
    )
    parser.add_argument("--min-train-seasons", type=int, default=3)
    parser.add_argument("--k", type=float, default=EloConfig.k)
    parser.add_argument(
        "--home-advantage", type=float, default=EloConfig.home_advantage
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    matches = pd.read_parquet(args.matches)
    closing = pd.read_parquet(args.closing)
    # Lockbox (FSA #0 W.8): raport CLI nie pokazuje sezonów odłożonych.
    matches, _ = split_dev_lockbox(matches)
    assert_no_lockbox(matches, what="elo_baseline CLI")
    report = run_elo_baseline(
        matches,
        closing,
        config=EloConfig(k=args.k, home_advantage=args.home_advantage),
        min_train_seasons=args.min_train_seasons,
    )
    print(format_report(report))  # raport CLI, nie log produkcyjny
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
