"""Model Dixona-Colesa — dwa rozkłady Poissona z korektą niskich wyników.

Po co to istnieje
-----------------
Elo zna tylko wynik W/R/P. Dixon-Coles zna **liczbę goli**, czyli ściśle
więcej informacji, i produkuje pełną macierz łączną ``P(gole_gosp=i,
gole_gość=j)``. Z jednej estymacji wyceniamy 1X2, handicapy azjatyckie i
over/under — koszt krańcowy kolejnego rynku to suma innych komórek tej
samej macierzy (STEP4_PLAN §0).

Specyfikacja
------------
Dla meczu gospodarz ``i`` - gość ``j``::

    lambda = alpha_i * beta_j * gamma      (oczekiwane gole gospodarza)
    mu     = alpha_j * beta_i              (oczekiwane gole gościa)

``alpha`` to siła ataku, ``beta`` słabość obrony, ``gamma`` atut własnego
boiska. Korekta Dixona-Colesa dotyczy **wyłącznie** czterech najniższych
wyników — dwa niezależne Poissony za rzadko dają 0:0 i 1:1::

    tau(0,0) = 1 - lambda*mu*rho
    tau(0,1) = 1 + lambda*rho
    tau(1,0) = 1 + mu*rho
    tau(1,1) = 1 - rho
    tau(x,y) = 1                           dla pozostałych

Log-wiarygodność z wygaszaniem czasowym ``phi(t) = exp(-xi*t)``, gdzie
``t`` to dni przed datą odniesienia. Pół-okres = ``ln(2)/xi``; dla
``xi = 0.003`` to ~231 dni.

Identyfikowalność — NIE USUWAJ CENTROWANIA
-------------------------------------------
Wiarygodność jest niezmiennicza względem ``alpha -> c*alpha``,
``beta -> beta/c``, bo ``lambda`` i ``mu`` zależą tylko od iloczynów.
Bez ograniczenia hesjan jest osobliwy wzdłuż tego kierunku, a L-BFGS-B
albo wlecze się po grzbiecie, albo zwraca losowy punkt z grzbietu —
dwa przebiegi z różnych startów dają różne ``alpha`` przy tych samych
``lambda``.

Ograniczenie ``sum(log alpha_i) = 0`` jest egzekwowane **wewnątrz funkcji
celu** przez odjęcie średniej. Jest różniczkowalne (gradient przechodzi
przez rzutowanie ``I - 11^T/n``), więc nie wymaga solvera z warunkami.
``gamma`` jest identyfikowalne osobno, bo wchodzi tylko do ``lambda``.

Gradient analityczny, nie numeryczny
-------------------------------------
Walk-forward z przefitowaniem przed każdą kolejką to setki dopasowań.
Przy ~38 parametrach różniczkowanie numeryczne kosztuje 39 ewaluacji
funkcji celu na jeden krok gradientu. Gradient analityczny jest tu nie
optymalizacją, tylko warunkiem wykonalności — i ma test porównujący go
z ``scipy.optimize.check_grad``.

Granica czasowa
---------------
``reference_date`` jest **twardą granicą odcięcia**: mecz z ``kickoff_utc``
późniejszym niż ona podnosi wyjątek. Wagi czasowe liczone względem daty
z przyszłości to look-ahead bias wprowadzony bocznymi drzwiami — wagi
same w sobie są informacją o tym, gdzie kończy się historia.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.linalg import LinAlgError, cho_factor, cho_solve
from scipy.optimize import minimize, minimize_scalar
from scipy.special import gammaln
from scipy.stats import poisson

__all__ = [
    "DEFAULT_PRIOR",
    "MAX_GOALS_DEFAULT",
    "MAX_STANDARD_ERROR",
    "MIN_EFFECTIVE_FOR_FIT",
    "MIN_EFFECTIVE_FOR_TAU",
    "MIN_TAU_STRENGTH",
    "RHO_BOUND",
    "DegenerateSpreadError",
    "DixonColesParams",
    "EmpiricalBayesResult",
    "NumericalInstabilityError",
    "PriorScales",
    "empirical_bayes_scales",
    "fit_dixon_coles",
    "log_likelihood",
    "matrix_from_rates",
    "probabilities_1x2",
    "score_matrix",
]

log = logging.getLogger(__name__)

#: Obcięcie macierzy wyników.
#:
#: STEP4_PLAN §1.7 proponuje 10 i jednocześnie wymaga, żeby masa poza
#: obcięciem była < 1e-6. Te dwie rzeczy są sprzeczne dla realnych meczów:
#: przy lambda = 1.5 obcięcie na 10 daje 6.1e-07 (zgodnie z planem), ale
#: przy lambda = 2.5 już 6.2e-05, a przy 3.5 aż 1.0e-03. Mocny gospodarz
#: przeciwko słabemu gościowi to w Ekstraklasie lambda ~ 2.5-3.0, więc
#: warunek łamałby się regularnie.
#:
#: Wiążący jest próg, nie liczba: 15 daje < 1e-6 dla lambda do ~3.5, a
#: macierz 16x16 zamiast 11x11 kosztuje tyle, co nic.
MAX_GOALS_DEFAULT = 15

#: rho musi spełniać tau > 0 dla każdego meczu (STEP4_PLAN §1.3):
#: rho < 1/(lambda*mu), rho > -1/lambda, rho > -1/mu. Dla typowych
#: lambda, mu w (0.3, 3.0) przedział (-0.2, 0.2) jest bezpieczny.
RHO_BOUND = 0.2

#: Masa poza obcięciem powyżej tej wartości oznacza, że macierz nie jest
#: rozkładem i renormalizacja zaczyna kłamać.
TRUNCATION_TOLERANCE = 1e-6

#: Progi informacji, ustalone z góry i NIE strojone (STEP4_ENSEMBLE §11.9).
#:
#: n_eff drużyny to ważona liczba jej meczów w oknie. Poniżej 0.5 drużyna
#: nie wchodzi do dopasowania; poniżej 5 nie wchodzi do estymacji tau.
#: Rozdzielenie jest konieczne: do samego dopasowania wystarczy odrobina
#: informacji, do oszacowania ROZRZUTU między drużynami — nie.
MIN_EFFECTIVE_FOR_FIT = 0.5
MIN_EFFECTIVE_FOR_TAU = 5.0

#: Bezpiecznik numeryczny. Dobrze zmierzona drużyna (n_eff >= 5) z SE(s)
#: powyżej tej wartości oznacza rozlanie wariancji po macierzy, nie
#: niepewność. Symulacja §11.9: poprawka daje maksymalnie 0.39, stara
#: ścieżka 6.1; zmierzone na dev przed poprawką: 9.02.
MAX_STANDARD_ERROR = 1.0

#: Mniej drużyn niż tyle nie pozwala oszacować rozrzutu między drużynami.
_MIN_TEAMS_FOR_TAU = 6

#: Zakres poszukiwania tau w marginalnej wiarygodności. Podłogi NIE MA —
#: człon ``+ log tau`` odsuwa estymator od zera bez obcinania (§11.3).
_TAU_BOUNDS = (1e-4, 1.0)

#: Bezpiecznik statystyczny, OSTATNIA linia obrony. tau_s poniżej tej
#: wartości znaczy „drużyny nie różnią się siłą", co przeczy temu, co
#: pokazuje Elo.
#:
#: 0.03, nie 0.05 jak pierwotnie: symulacja §11.9 pokazała, że POPRAWNY
#: estymator przy prawdziwym tau ~ 0.11 i małej efektywnej próbie schodzi
#: do 0.050, więc stary próg karał poprawne oszacowania. Prawdziwa
#: sygnatura awarii jest numeryczna i łapie ją ``MAX_STANDARD_ERROR``.
MIN_TAU_STRENGTH = 0.03

#: Podłoga na tau w funkcji celu. Solver bywa w trakcie iteracji w
#: obszarze tau <= 0 (duże lambda przy ujemnym rho); zamiast zwracać inf,
#: które psuje line search, dajemy bardzo złą, ale skończoną wartość.
_TAU_FLOOR = 1e-8

_REQUIRED_COLUMNS = frozenset(
    {"kickoff_utc", "home_team_id", "away_team_id", "home_goals", "away_goals"}
)


@dataclass(frozen=True)
class DixonColesParams:
    """Dopasowane parametry. Niemutowalne — ``fit_dixon_coles`` zwraca nowy obiekt.

    Attributes
    ----------
    attack, defence:
        Siła ataku i słabość obrony per ``team_id``. Skala ustalona przez
        ``sum(log attack) = 0``, czyli średnia geometryczna ataku = 1.
        Drużyna nieznana modelowi dostaje **średnią ligową** (dla ataku
        1.0 z ograniczenia, dla obrony ``league_defence``), jeśli
        wywołanie na to pozwala — odpowiednik startowych 1500 punktów
        w Elo.
    home_advantage:
        ``gamma``, mnożnik oczekiwanych goli gospodarza.
    rho:
        Korekta niskich wyników. Ujemna w typowej lidze.
    xi:
        Użyte tempo wygaszania (1/dzień). 0 = brak wygaszania.
    prior:
        Użyte skale ściągania (siła, otwartość).
    reference_date:
        Granica odcięcia, względem której liczono wagi czasowe. Nie ma
        jej w specyfikacji ze STEP4_PLAN, ale bez niej nie da się po
        fakcie sprawdzić, czy dopasowanie nie widziało przyszłości.
    converged:
        Zawsze ``True`` w zwróconym obiekcie — brak zbieżności podnosi
        wyjątek (STEP4_PLAN §1.4). Pole zostaje dla serializacji i dla
        czytelności rekordu.
    """

    attack: dict[str, float]
    defence: dict[str, float]
    home_advantage: float
    rho: float
    xi: float
    prior: PriorScales
    n_fit: int
    converged: bool
    reference_date: pd.Timestamp | None = field(default=None)

    @property
    def teams(self) -> frozenset[str]:
        return frozenset(self.attack)

    def rates(
        self, home_team_id: str, away_team_id: str, *, allow_unknown_teams: bool = False
    ) -> tuple[float, float]:
        """``(lambda, mu)`` dla pary drużyn — oczekiwane gole gospodarza i gościa."""
        a_home, d_home = self._team(home_team_id, allow_unknown_teams)
        a_away, d_away = self._team(away_team_id, allow_unknown_teams)
        return a_home * d_away * self.home_advantage, a_away * d_home

    @property
    def league_attack(self) -> float:
        """Średnia geometryczna ataku. Zawsze 1.0 — pinuje to ograniczenie."""
        if not self.attack:
            return 1.0
        return float(np.exp(np.log(np.fromiter(self.attack.values(), float)).mean()))

    @property
    def league_defence(self) -> float:
        """Średnia geometryczna obrony. **Nie jest 1.0.**

        Ograniczenie identyfikowalności centruje tylko ``log alpha``;
        ``log beta`` unosi poziom bramkowy ligi i w Ekstraklasie wychodzi
        stabilnie ~1.10. To jest właściwa wartość domyślna dla drużyny
        bez historii — 1.0 dawałoby jej obronę o ~10% lepszą od ligowej
        i zaniżało oczekiwane gole w jej meczach.
        """
        if not self.defence:
            return 1.0
        return float(np.exp(np.log(np.fromiter(self.defence.values(), float)).mean()))

    def _team(self, team_id: str, allow_unknown: bool) -> tuple[float, float]:
        if team_id in self.attack:
            return self.attack[team_id], self.defence[team_id]
        if not allow_unknown:
            raise KeyError(
                f"drużyna {team_id!r} nie występuje w dopasowaniu; "
                "użyj allow_unknown_teams=True, jeśli świadomie chcesz "
                "przypisać jej średnią ligową"
            )
        # Średnia LIGOWA w obu wymiarach, nie jedynka. Dla ataku to i tak
        # 1.0, dla obrony nie — patrz ``league_defence``. Ta sama pułapka
        # co w środku prioru; poprawienie tylko jednego miejsca zostawia
        # błąd dla drużyn, które nie rozegrały jeszcze ani jednego meczu.
        return self.league_attack, self.league_defence


def _validate_matches(matches: pd.DataFrame) -> None:
    missing = _REQUIRED_COLUMNS - set(matches.columns)
    if missing:
        raise ValueError(f"fit_dixon_coles: brak kolumn {sorted(missing)}")
    if matches.empty:
        raise ValueError("fit_dixon_coles: pusty zbiór meczów")
    kickoff = matches["kickoff_utc"]
    if not isinstance(kickoff.dtype, pd.DatetimeTZDtype):
        raise ValueError(  # noqa: TRY004 - kontrakt danych, nie typ argumentu
            "kickoff_utc musi być timezone-aware (reguła 2); naiwny datetime "
            "to najczęstszy nośnik look-ahead bias"
        )
    goals = matches[["home_goals", "away_goals"]]
    if goals.isna().to_numpy().any():
        raise ValueError(
            "fit_dixon_coles: mecz bez wyniku nie niesie wiarygodności — "
            "odfiltruj je JAWNIE przed wywołaniem"
        )
    values = goals.to_numpy(dtype=np.float64)
    if (values < 0).any() or not np.allclose(values, np.rint(values)):
        raise ValueError("gole muszą być nieujemnymi liczbami całkowitymi")


def _time_weights(
    kickoff: pd.Series, reference_date: pd.Timestamp, xi: float
) -> NDArray[np.float64]:
    """``exp(-xi * dni_przed_odniesieniem)``. Mecz po granicy = wyjątek."""
    days = (reference_date - kickoff).dt.total_seconds().to_numpy() / 86400.0
    if (days < 0).any():
        n_future = int((days < 0).sum())
        raise ValueError(
            f"{n_future} meczów ma kickoff_utc po reference_date "
            f"({reference_date!r}) — dopasowanie widziałoby przyszłość"
        )
    return np.asarray(np.exp(-xi * days), dtype=np.float64)


def _tau(
    home_goals: NDArray[np.int64],
    away_goals: NDArray[np.int64],
    lam: NDArray[np.float64],
    mu: NDArray[np.float64],
    rho: float,
) -> NDArray[np.float64]:
    """Korekta niskich wyników. Wektorowo, dla całego zbioru naraz."""
    tau = np.ones_like(lam)
    m00 = (home_goals == 0) & (away_goals == 0)
    m01 = (home_goals == 0) & (away_goals == 1)
    m10 = (home_goals == 1) & (away_goals == 0)
    m11 = (home_goals == 1) & (away_goals == 1)
    tau[m00] = 1.0 - lam[m00] * mu[m00] * rho
    tau[m01] = 1.0 + lam[m01] * rho
    tau[m10] = 1.0 + mu[m10] * rho
    tau[m11] = 1.0 - rho
    return tau


@dataclass(frozen=True)
class PriorScales:
    """Siła ściągania osobno dla siły i dla otwartości (STEP4_ENSEMBLE §10.3).

    ``None`` w którymkolwiek polu oznacza brak kary w tym wymiarze — czyste
    MLE, dopuszczalne tylko tam, gdzie każda drużyna ma dużo meczów.
    """

    strength: float | None
    openness: float | None

    def __post_init__(self) -> None:
        for name, value in (("strength", self.strength), ("openness", self.openness)):
            if value is not None and value <= 0.0:
                raise ValueError(f"{name} musi być dodatnie albo None, jest {value}")

    @classmethod
    def uniform(cls, sd: float | None) -> PriorScales:
        """Jedno ``sd`` na oba wymiary — stary, wadliwy wariant. Do testów."""
        return cls(strength=sd, openness=sd)


#: Domyślne skale ściągania. Osobne dla siły i otwartości — patrz
#: ``PriorScales`` i STEP4_ENSEMBLE §10.2.
#:
#: Prior NIE jest ozdobą bayesowską, tylko warunkiem istnienia estymatora.
#: Wiarygodność DC jest nieograniczona dla drużyny, która nie strzeliła
#: gola: alpha -> 0 podnosi ją monotonicznie. Drużyna z dwoma meczami 0:0
#: dostawała log alpha = -12 i macierz zapadającą się na 0:0
#: (P(remis) = 0.999996) — kosztowało to +0.034 log lossu.
#:
#: Dwie osobne skale, bo drużyny różnią się SIŁĄ dużo, a OTWARTOŚCIĄ mało.
#: Jedno wspólne sd dobrane pod siłę prawie nie ściąga otwartości, przez co
#: przewidywana suma goli jest za bardzo rozstrzelona i nachylenie regresji
#: zrealizowana-na-przewidzianą spada poniżej 1. Zmierzone na Ekstraklasie:
#: dolny kwartyl lambda+mu +0.233 [+0.161, +0.307], górny -0.127
#: [-0.204, -0.055] — przeciwne znaki, czyli błąd rozrzutu, nie poziomu.
#:
#: W produkcji te wartości przychodzą z ``empirical_bayes_scales`` liczonego
#: na oknie treningowym, nie z tej stałej.
DEFAULT_PRIOR = PriorScales(strength=0.35, openness=0.06)

#: Prior używany w pierwszym przebiegu empirical Bayes — na tyle słaby, żeby
#: nie narzucać wyniku, na tyle obecny, żeby drużyna bez gola nie uciekła.
_EB_WEAK_PRIOR = PriorScales(strength=2.0, openness=2.0)

@dataclass(frozen=True)
class _FitData:
    """Zdekodowane wejście solvera. Wszystko już jako indeksy i tablice."""

    teams: tuple[str, ...]
    home_idx: NDArray[np.int64]
    away_idx: NDArray[np.int64]
    home_goals: NDArray[np.int64]
    away_goals: NDArray[np.int64]
    weights: NDArray[np.float64]
    log_factorial: NDArray[np.float64]
    prior: PriorScales = PriorScales(None, None)
    #: n_eff po drużynach POZOSTAWIONYCH w oknie.
    effective_matches: NDArray[np.float64] = field(
        default_factory=lambda: np.empty(0, dtype=np.float64)
    )
    n_dropped_teams: int = 0
    n_dropped_matches: int = 0

    @property
    def n_teams(self) -> int:
        return len(self.teams)

    @property
    def n_matches(self) -> int:
        return len(self.home_idx)


def _prepare(
    matches: pd.DataFrame,
    reference_date: pd.Timestamp,
    xi: float,
    prior: PriorScales | None = None,
    *,
    min_effective_matches: float = MIN_EFFECTIVE_FOR_FIT,
) -> _FitData:
    """Dekoduje wejście i **odrzuca drużyny bez informacji w oknie**.

    Drużyna z ``n_eff < min_effective_matches`` nie wnosi wiarygodności, a
    wnosi wolny parametr i kierunek prawie zerowy w macierzy informacji.
    Przy ``xi = 0.008`` na oknie dekady było takich 11 z 30 i to one
    zdegenerowały całą estymację (STEP4_ENSEMBLE §11.9).

    Mecze z udziałem odrzuconej drużyny wypadają z wiarygodności. W
    predykcji taka drużyna dostaje średnią ligową przez istniejący
    fallback ``allow_unknown_teams``.
    """
    weights_all = _time_weights(matches["kickoff_utc"], reference_date, xi)
    all_teams = tuple(
        sorted(
            set(matches["home_team_id"].astype(str))
            | set(matches["away_team_id"].astype(str))
        )
    )
    first_index = {team: i for i, team in enumerate(all_teams)}
    home_all = np.array(
        [first_index[t] for t in matches["home_team_id"].astype(str)], dtype=np.int64
    )
    away_all = np.array(
        [first_index[t] for t in matches["away_team_id"].astype(str)], dtype=np.int64
    )
    n_eff_all = _effective_counts(home_all, away_all, weights_all, len(all_teams))

    keep_team = n_eff_all >= min_effective_matches
    keep_match = keep_team[home_all] & keep_team[away_all]
    if not keep_match.any():
        raise ValueError(
            f"po odrzuceniu drużyn z n_eff < {min_effective_matches} nie został "
            f"żaden mecz (xi={xi}, drużyn={len(all_teams)})"
        )

    teams = tuple(t for t, ok in zip(all_teams, keep_team, strict=True) if ok)
    index = {team: i for i, team in enumerate(teams)}
    kept = matches.loc[keep_match]
    home_goals = kept["home_goals"].to_numpy(dtype=np.int64)
    away_goals = kept["away_goals"].to_numpy(dtype=np.int64)
    weights = weights_all[keep_match]
    home_idx = np.array(
        [index[t] for t in kept["home_team_id"].astype(str)], dtype=np.int64
    )
    away_idx = np.array(
        [index[t] for t in kept["away_team_id"].astype(str)], dtype=np.int64
    )
    return _FitData(
        teams=teams,
        home_idx=home_idx,
        away_idx=away_idx,
        home_goals=home_goals,
        away_goals=away_goals,
        weights=weights,
        # Stała względem parametrów — liczona raz, nie w każdej ewaluacji.
        log_factorial=np.asarray(
            gammaln(home_goals + 1.0) + gammaln(away_goals + 1.0), dtype=np.float64
        ),
        prior=prior if prior is not None else PriorScales(None, None),
        effective_matches=_effective_counts(home_idx, away_idx, weights, len(teams)),
        n_dropped_teams=int((~keep_team).sum()),
        n_dropped_matches=int((~keep_match).sum()),
    )


def _unpack(
    theta: NDArray[np.float64], n_teams: int
) -> tuple[NDArray[np.float64], NDArray[np.float64], float, float, float]:
    """``theta -> (siła, otwartość, poziom c, atut g, rho)``, s i o wycentrowane."""
    strength = theta[:n_teams]
    openness = theta[n_teams : 2 * n_teams]
    return (
        np.asarray(strength - strength.mean(), dtype=np.float64),
        np.asarray(openness - openness.mean(), dtype=np.float64),
        float(theta[2 * n_teams]),
        float(theta[2 * n_teams + 1]),
        float(theta[2 * n_teams + 2]),
    )


def _negative_loglik_and_grad(
    theta: NDArray[np.float64], data: _FitData
) -> tuple[float, NDArray[np.float64]]:
    """Wartość i gradient ujemnej ważonej log-wiarygodności z karą.

    Parametryzacja ``(s, o)`` zamiast ``(log alpha, log beta)`` — patrz
    docstring modułu. Pochodne liczone względem ``log lambda`` i ``log mu``,
    potem łańcuch przez stałe współczynniki +-1.
    """
    n_teams = data.n_teams
    strength, openness, level, home_adv, rho = _unpack(theta, n_teams)

    s_home = strength[data.home_idx]
    s_away = strength[data.away_idx]
    o_sum = openness[data.home_idx] + openness[data.away_idx]
    log_lam = s_home - s_away + o_sum + level + home_adv
    log_mu = s_away - s_home + o_sum + level
    lam = np.exp(log_lam)
    mu = np.exp(log_mu)

    tau = _tau(data.home_goals, data.away_goals, lam, mu, rho)
    valid = tau > _TAU_FLOOR
    safe_tau = np.where(valid, tau, _TAU_FLOOR)

    loglik_terms = (
        np.log(safe_tau)
        + data.home_goals * log_lam
        - lam
        + data.away_goals * log_mu
        - mu
        - data.log_factorial
    )
    value = -float(np.dot(data.weights, loglik_terms))

    m00 = (data.home_goals == 0) & (data.away_goals == 0)
    m01 = (data.home_goals == 0) & (data.away_goals == 1)
    m10 = (data.home_goals == 1) & (data.away_goals == 0)
    m11 = (data.home_goals == 1) & (data.away_goals == 1)

    d_tau_dloglam = np.zeros_like(lam)
    d_tau_dlogmu = np.zeros_like(lam)
    d_tau_drho = np.zeros_like(lam)
    d_tau_dloglam[m00] = -lam[m00] * mu[m00] * rho
    d_tau_dlogmu[m00] = -lam[m00] * mu[m00] * rho
    d_tau_drho[m00] = -lam[m00] * mu[m00]
    d_tau_dloglam[m01] = lam[m01] * rho
    d_tau_drho[m01] = lam[m01]
    d_tau_dlogmu[m10] = mu[m10] * rho
    d_tau_drho[m10] = mu[m10]
    d_tau_drho[m11] = -1.0
    inv_tau = np.where(valid, 1.0 / safe_tau, 0.0)

    d_loglam = data.weights * ((data.home_goals - lam) + d_tau_dloglam * inv_tau)
    d_logmu = data.weights * ((data.away_goals - mu) + d_tau_dlogmu * inv_tau)
    grad_rho = float(np.dot(data.weights, d_tau_drho * inv_tau))

    # log lambda = +s_home - s_away + o_home + o_away + c + g
    # log mu     = -s_home + s_away + o_home + o_away + c
    d_strength = d_loglam - d_logmu
    d_openness = d_loglam + d_logmu
    grad_strength = np.bincount(
        data.home_idx, weights=d_strength, minlength=n_teams
    ) - np.bincount(data.away_idx, weights=d_strength, minlength=n_teams)
    grad_openness = np.bincount(
        data.home_idx, weights=d_openness, minlength=n_teams
    ) + np.bincount(data.away_idx, weights=d_openness, minlength=n_teams)
    grad_level = float(d_openness.sum())
    grad_home_adv = float(d_loglam.sum())
    # Rzutowanie I - 11^T/n: s i o są centrowane w ``_unpack``, więc funkcja
    # celu jest niezmiennicza wzdłuż kierunku samych jedynek i prawdziwy
    # gradient musi mieć tam zero. Bez tych dwóch linii gradient niesie
    # fikcyjną składową stałą, a ``check_grad`` pokazuje rozjazd rzędu 70.
    grad_strength = grad_strength - grad_strength.mean()
    grad_openness = grad_openness - grad_openness.mean()

    grad = np.concatenate(
        [
            grad_strength,
            grad_openness,
            np.array([grad_level, grad_home_adv, grad_rho]),
        ]
    )
    negative_grad = -grad

    # Kara. Oba wektory są już wycentrowane, więc odchylenie od średniej to
    # sama wartość. Rzutowanie I - 11^T/n przechodzi przez centrowanie i dla
    # wektora o zerowej sumie jest tożsamością — zostawiamy je jawnie, żeby
    # nie zależeć od tej tożsamości przy ewentualnej zmianie centrowania.
    if data.prior.strength is not None:
        variance = data.prior.strength**2
        value += 0.5 * float(np.sum(strength**2)) / variance
        penalty = strength / variance
        negative_grad[:n_teams] += penalty - penalty.mean()
    if data.prior.openness is not None:
        variance = data.prior.openness**2
        value += 0.5 * float(np.sum(openness**2)) / variance
        penalty = openness / variance
        negative_grad[n_teams : 2 * n_teams] += penalty - penalty.mean()

    return value, np.asarray(negative_grad, dtype=np.float64)


def _start_vector(data: _FitData) -> NDArray[np.float64]:
    """Zerowe s i o, a poziom i atut boiska wprost ze średnich w danych."""
    total = float(data.weights.sum())
    mean_home = max(float(np.dot(data.weights, data.home_goals) / total), 0.05)
    mean_away = max(float(np.dot(data.weights, data.away_goals) / total), 0.05)
    return np.concatenate(
        [
            np.zeros(2 * data.n_teams),
            np.array([np.log(mean_away), np.log(mean_home / mean_away), -0.05]),
        ]
    )


def fit_dixon_coles(
    matches: pd.DataFrame,
    *,
    xi: float = 0.003,
    prior: PriorScales | None = None,
    reference_date: pd.Timestamp | None = None,
    max_iter: int = 500,
    start: NDArray[np.float64] | None = None,
    min_effective_matches: float = MIN_EFFECTIVE_FOR_FIT,
) -> DixonColesParams:
    """Maksimum ważonej wiarygodności z karą. Deterministyczne.

    Parameters
    ----------
    matches:
        ``kickoff_utc`` (tz-aware), ``home_team_id``, ``away_team_id``,
        ``home_goals``, ``away_goals``. Mecze bez wyniku podnoszą wyjątek —
        odfiltruj je jawnie.
    xi:
        Tempo wygaszania czasowego (1/dzień). ``0`` = wszystkie mecze
        ważą tak samo. **Hiperparametr** strojony walk-forward wewnątrz
        okna treningowego (reguła 10), nigdy na teście.
    prior:
        Siła ściągania osobno dla siły i otwartości. ``None`` = domyślne
        ``DEFAULT_PRIOR``. Wartość dobiera się z danych treningowych przez
        ``empirical_bayes_scales``, nie z siatki.
    reference_date:
        Granica odcięcia dla wag czasowych. Domyślnie ``max(kickoff_utc)``.
        Mecz późniejszy niż granica podnosi wyjątek.
    max_iter:
        Limit iteracji L-BFGS-B.
    start:
        Punkt startowy ``[s (n), o (n), c, g, rho]``. Domyślnie s = o = 0,
        a ``c`` i ``g`` ze średnich w danych. Kolejność drużyn =
        posortowane ``team_id``.
    min_effective_matches:
        Próg ``n_eff``, poniżej którego drużyna wypada z dopasowania
        (§11.9 pkt 1). ``0.0`` odtwarza zachowanie sprzed poprawki C i
        służy **wyłącznie** testowi regresji — w produkcji zostawia
        martwe drużyny jako wolne parametry i degeneruje macierz.

    Raises
    ------
    RuntimeError
        Gdy solver nie zbiegł albo dopasowanie daje ``tau <= 0``.
    """
    if xi < 0.0:
        raise ValueError(f"xi musi być nieujemne, jest {xi}")
    _validate_matches(matches)

    if reference_date is None:
        reference_date = pd.Timestamp(matches["kickoff_utc"].max())
    data = _prepare(
        matches,
        reference_date,
        xi,
        prior if prior is not None else DEFAULT_PRIOR,
        min_effective_matches=min_effective_matches,
    )
    if data.n_teams < 2:
        raise ValueError(f"za mało drużyn: {data.n_teams}")

    n_teams = data.n_teams
    if start is None:
        start = _start_vector(data)
    elif start.shape != (2 * n_teams + 3,):
        raise ValueError(
            f"start ma kształt {start.shape}, oczekiwano {(2 * n_teams + 3,)}"
        )
    bounds: list[tuple[float | None, float | None]] = [(None, None)] * (2 * n_teams + 2)
    bounds.append((-RHO_BOUND, RHO_BOUND))

    result = minimize(
        _negative_loglik_and_grad,
        start,
        args=(data,),
        jac=True,
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxiter": max_iter},
    )
    if not result.success:
        raise RuntimeError(f"Dixon-Coles nie zbiegł: {result.message}")

    strength, openness, level, home_adv, rho = _unpack(
        np.asarray(result.x, dtype=np.float64), n_teams
    )
    # Powrót do (alpha, beta, gamma). Poziom ``c`` wpuszczamy w całości do
    # bety, żeby zachować niezmiennik sum(log alpha) = 0 — to ta sama
    # niezmienniczość alpha -> c*alpha, beta -> beta/c, więc lambda i mu
    # się nie zmieniają.
    params = DixonColesParams(
        attack=dict(zip(data.teams, np.exp(openness + strength).tolist(), strict=True)),
        defence=dict(
            zip(data.teams, np.exp(openness - strength + level).tolist(), strict=True)
        ),
        home_advantage=float(np.exp(home_adv)),
        rho=rho,
        xi=xi,
        prior=data.prior,
        n_fit=data.n_matches,
        converged=True,
        reference_date=reference_date,
    )
    _assert_tau_positive(params, data)
    return params


class NumericalInstabilityError(RuntimeError):
    """Estymacja rozsypała się numerycznie. Sufiks ``Error`` wymaga ruff N818.

    Osobny typ od zwykłego ``RuntimeError``, bo budowa cache ``LL(V, xi)``
    traktuje go inaczej niż predykcja: dla kandydata z siatki to informacja
    („ten ``xi`` jest niedopuszczalny"), dla wybranego ``xi`` — awaria.
    """


class DegenerateSpreadError(NumericalInstabilityError):
    """``tau_s`` poniżej progu — ostatnia linia obrony (§11.9 pkt 4)."""


@dataclass(frozen=True)
class EmpiricalBayesResult:
    """Wynik empirical Bayes dla skal ściągania (STEP4_ENSEMBLE §10.3)."""

    scales: PriorScales
    #: Surowa wariancja oszacowań między drużynami.
    var_strength: float
    var_openness: float
    #: Średni kwadrat błędu standardowego — część wariancji, która jest szumem.
    noise_strength: float
    noise_openness: float
    n_teams: int
    n_well_measured: int = 0
    n_dropped_teams: int = 0
    n_dropped_matches: int = 0
    condition_number: float = float("nan")
    max_se_strength: float = float("nan")
    #: tau_s przy alternatywnych progach n_eff — wyłącznie raport.
    tau_strength_sensitivity: dict[float, float] = field(default_factory=dict)

    @property
    def openness_is_negligible(self) -> bool:
        """Czy rozrzut otwartości jest praktycznie zerowy.

        Estymator z marginalnej wiarygodności nie ma podłogi, więc nie ma
        też „osiadania". Próg jest umowny i służy wyłącznie raportowaniu:
        drużyny praktycznie nie różnią się otwartością, więc przewidywana
        suma goli powinna być niemal stała.
        """
        return self.scales.openness is not None and self.scales.openness < 0.02


def _effective_counts(
    home_idx: NDArray[np.int64],
    away_idx: NDArray[np.int64],
    weights: NDArray[np.float64],
    n_teams: int,
) -> NDArray[np.float64]:
    """``n_eff_i`` — ile ważonych meczów drużyny jest w oknie (§11.9 pkt 1).

    ``n_eff_i = suma po meczach z udziałem i, sprzed cięcia, z exp(-xi*wiek)``.
    Przy ``xi = 0`` to po prostu liczba meczów; przy silnym wygaszaniu
    drużyna, która ostatni raz grała lata temu, ma ``n_eff`` rzędu 1e-8.
    """
    counts = np.bincount(home_idx, weights=weights, minlength=n_teams)
    counts += np.bincount(away_idx, weights=weights, minlength=n_teams)
    return np.asarray(counts, dtype=np.float64)


def _hessian_with_prior(
    data: _FitData, params: DixonColesParams
) -> NDArray[np.float64]:
    """``X^T W X`` plus precyzja prioru. **Dodatnio określona, więc Cholesky.**

    Bloki ``s`` i ``o`` dostają ``1/sd^2`` na przekątnej. To nie jest
    kosmetyka — to jedyny powód, dla którego macierz w ogóle jest
    odwracalna. ``X^T W X`` ma dokładnie dwa kierunki zerowe (wspólne
    przesunięcie ``s``; ``o`` względem ``c``), a prior je domyka.

    Dlaczego nie ``pinv`` na macierzy bez prioru — patrz
    ``empirical_bayes_scales``. Krótko: drużyna bez meczów w ważonym oknie
    daje kierunek o wartości własnej ~1e-10, ``pinv`` go odwraca i rozlewa
    wariancję 1e10 po wszystkich drużynach.
    """
    information = _fisher_information(data, params)
    t = data.n_teams
    precision = np.zeros(2 * t + 2, dtype=np.float64)
    if data.prior.strength is not None:
        precision[:t] = 1.0 / data.prior.strength**2
    if data.prior.openness is not None:
        precision[t : 2 * t] = 1.0 / data.prior.openness**2
    return np.asarray(information + np.diag(precision), dtype=np.float64)


def _standard_errors(
    data: _FitData, params: DixonColesParams
) -> tuple[NDArray[np.float64], NDArray[np.float64], float]:
    """``(SE_s, SE_o, cond)`` z hesjanu z priorem, bez ``pinv``.

    Kowariancja z Cholesky'ego, potem rzut na kontrasty centrowane
    ``C = I - 11^T/T`` osobno dla bloku ``s`` i ``o``. Rzut jest po
    odwróceniu, nie przed: prior wnosi wariancję wzdłuż kierunku samych
    jedynek, która jest artefaktem parametryzacji, a nie niepewnością
    czegokolwiek, co raportujemy.

    Cholesky zawodzi **głośno**, gdy macierz nie jest dodatnio określona.
    O to chodzi — cicha pseudoodwrotność jest dokładnie tym, co zepsuło
    przebieg z 2026-10-01.
    """
    hessian = _hessian_with_prior(data, params)
    # Uwarunkowanie liczone BEZ dwóch dokładnych kierunków zerowych
    # (wspólne przesunięcie s; o względem c). Branie po prostu najmniejszej
    # dodatniej wartości własnej daje bzdurę: te dwa kierunki wychodzą
    # numerycznie jako ±1e-16, więc cond skakał do 1e16 także wtedy, gdy
    # macierz była zdrowa.
    eigenvalues = np.linalg.eigvalsh(_fisher_information(data, params))
    cond = (
        float(eigenvalues[-1] / eigenvalues[2])
        if eigenvalues.size > 2 and eigenvalues[2] > 0
        else float("inf")
    )
    try:
        factor = cho_factor(hessian, lower=True)
    except LinAlgError as exc:
        raise NumericalInstabilityError(
            "hesjan z priorem nie jest dodatnio określony — Cholesky zawiódł. "
            "NIE schodzimy na pseudoodwrotność: to ona zamieniła martwe "
            f"drużyny w SE rzędu 1e2. cond(X^T W X) = {cond:.3e}"
        ) from exc
    covariance = cho_solve(factor, np.eye(hessian.shape[0]))

    t = data.n_teams
    contrast = np.eye(t) - np.ones((t, t)) / t

    def project(block: NDArray[np.float64]) -> NDArray[np.float64]:
        return np.asarray(
            np.sqrt(np.clip(np.diag(contrast @ block @ contrast.T), 0.0, None)),
            dtype=np.float64,
        )

    return project(covariance[:t, :t]), project(covariance[t : 2 * t, t : 2 * t]), cond


def _fisher_information(
    data: _FitData, params: DixonColesParams
) -> NDArray[np.float64]:
    """``X^T W X`` dla Poissona z log-linkiem, w parametryzacji ``(s, o, c, g)``.

    Każdy mecz daje dwie obserwacje (gole gospodarza o intensywności lambda
    i gościa o intensywności mu), więc macierz planu ma ``2n`` wierszy::

        log lambda:  s[dom] = +1, s[gość] = -1, o[dom] = o[gość] = +1, c = 1, g = 1
        log mu:      s[dom] = -1, s[gość] = +1, o[dom] = o[gość] = +1, c = 1, g = 0

    Korekta ``tau`` dotyka czterech komórek i jest tu pominięta — to
    przybliżenie, którego STEP4_ENSEMBLE §10.3 jawnie oczekuje.
    """
    n, t = data.n_matches, data.n_teams
    attack = np.array([params.attack[k] for k in data.teams], dtype=np.float64)
    defence = np.array([params.defence[k] for k in data.teams], dtype=np.float64)
    lam = attack[data.home_idx] * defence[data.away_idx] * params.home_advantage
    mu = attack[data.away_idx] * defence[data.home_idx]

    design = np.zeros((2 * n, 2 * t + 2), dtype=np.float64)
    rows = np.arange(n)
    design[rows, data.home_idx] += 1.0
    design[rows, data.away_idx] -= 1.0
    design[n + rows, data.home_idx] -= 1.0
    design[n + rows, data.away_idx] += 1.0
    design[rows, t + data.home_idx] += 1.0
    design[rows, t + data.away_idx] += 1.0
    design[n + rows, t + data.home_idx] += 1.0
    design[n + rows, t + data.away_idx] += 1.0
    design[:, 2 * t] = 1.0
    design[rows, 2 * t + 1] = 1.0

    weight = np.concatenate([data.weights * lam, data.weights * mu])
    return np.asarray(design.T @ (design * weight[:, None]), dtype=np.float64)


def _marginal_likelihood_tau(
    estimates: NDArray[np.float64], standard_errors: NDArray[np.float64]
) -> float:
    """Estymator ``tau`` z marginalnej wiarygodności (STEP4_ENSEMBLE §11.3).

    Model: ``theta_i ~ N(0, SE_i^2 + tau^2)``. Maksymalizujemy::

        l(tau) = -0.5 * sum_i [ log(SE_i^2 + tau^2) + theta_i^2 / (SE_i^2 + tau^2) ]
                 + log tau

    Dlaczego nie metoda momentów ``max(var - mean(SE^2), podloga)``:

    - momenty ważą wszystkie drużyny tak samo, a drużyna z krótką historią
      ma wielokrotnie większy ``SE`` i powinna ważyć mniej;
    - różnica ``var - mean(SE^2)`` bywa ujemna i wymaga podłogi, a podłoga
      zapada się w małych oknach. Zmierzone na Ekstraklasie: ``tau_o`` na
      podłodze w 5 z 10 sezonów, a w 2019/20 również ``tau_s``, co
      zdegenerowało cały sezon.

    Człon ``+ log tau`` to prior gamma(2, lambda -> 0) w duchu Chunga i in.
    (2013): odsuwa od zera, poza jego okolicą praktycznie nie wpływa na
    wynik, a gwarantuje, że estymator **nigdy nie zwróci zera**. Dzięki temu
    podłoga jest niepotrzebna.
    """
    variance = np.asarray(standard_errors, dtype=np.float64) ** 2
    squared = np.asarray(estimates, dtype=np.float64) ** 2

    def negative_loglik(tau: float) -> float:
        total = variance + tau**2
        return float(0.5 * np.sum(np.log(total) + squared / total) - np.log(tau))

    result = minimize_scalar(
        negative_loglik, bounds=_TAU_BOUNDS, method="bounded",
        options={"xatol": 1e-10},
    )
    return float(result.x)


def empirical_bayes_scales(
    matches: pd.DataFrame,
    *,
    xi: float = 0.003,
    reference_date: pd.Timestamp | None = None,
    max_iter: int = 500,
) -> EmpiricalBayesResult:
    """Skale ściągania z danych, metodą momentów (STEP4_ENSEMBLE §10.3).

    Rozrzut oszacowań między drużynami to suma rozrzutu prawdziwego i szumu
    estymacji::

        var(s_hat) = tau_s^2 + mean(SE_s^2)   =>   tau_s^2 = var(s_hat) - mean(SE_s^2)

    Stąd cztery kroki: dopasuj ze słabym priorem, policz błędy standardowe
    z odwrotności informacji Fishera, odejmij szum, dopasuj ponownie.

    Dlaczego to, a nie siatka: siatka wybierana na jednym sezonie
    walidacyjnym jest wzdłuż osi ściągania prawie płaska i skacze po
    krańcach (zmierzone: 0.25 pięć razy, 2.00 cztery razy). Empirical Bayes
    korzysta z wszystkich drużyn w oknie treningowym naraz.

    **Liczone wyłącznie z okna treningowego**, więc szczelne dla
    walk-forward. Test trucizny pilnuje, że zatrucie sezonu testowego
    niczego tu nie zmienia.
    """
    if reference_date is None:
        reference_date = pd.Timestamp(matches["kickoff_utc"].max())
    weak = fit_dixon_coles(
        matches,
        xi=xi,
        prior=_EB_WEAK_PRIOR,
        reference_date=reference_date,
        max_iter=max_iter,
    )
    data = _prepare(matches, reference_date, xi, _EB_WEAK_PRIOR)
    t = data.n_teams

    log_attack = np.log(np.array([weak.attack[k] for k in data.teams]))
    log_defence = np.log(np.array([weak.defence[k] for k in data.teams]))
    strength = (log_attack - log_defence) / 2.0
    openness = (log_attack + log_defence) / 2.0
    strength -= strength.mean()
    openness -= openness.mean()

    se_strength, se_openness, condition = _standard_errors(data, weak)

    # Bezpiecznik numeryczny PRZED statystycznym. Rozlana wariancja daje
    # tau albo przy zerze, albo przy jedynce — kierunek zależy od
    # szczegółów, więc łapiemy przyczynę, nie skutek.
    well_measured = data.effective_matches >= MIN_EFFECTIVE_FOR_TAU
    if well_measured.any():
        worst = float(se_strength[well_measured].max())
        if worst > MAX_STANDARD_ERROR:
            raise NumericalInstabilityError(
                f"SE(s) dobrze zmierzonej drużyny = {worst:.3f} > "
                f"{MAX_STANDARD_ERROR} przy n_eff >= {MIN_EFFECTIVE_FOR_TAU}. "
                f"To rozlana wariancja, nie niepewność (xi={xi}, "
                f"drużyn w dopasowaniu={t}, odrzuconych={data.n_dropped_teams}, "
                f"cond(X^T W X)={condition:.3e})."
            )
    if int(well_measured.sum()) < _MIN_TEAMS_FOR_TAU:
        raise NumericalInstabilityError(
            f"tylko {int(well_measured.sum())} drużyn z n_eff >= "
            f"{MIN_EFFECTIVE_FOR_TAU} — za mało, żeby oszacować rozrzut "
            f"(xi={xi}, drużyn w dopasowaniu={t})"
        )

    # tau liczone WYŁĄCZNIE po dobrze zmierzonych (§11.9 pkt 1).
    tau_strength = _marginal_likelihood_tau(
        strength[well_measured], se_strength[well_measured]
    )
    tau_openness = _marginal_likelihood_tau(
        openness[well_measured], se_openness[well_measured]
    )
    if tau_strength < MIN_TAU_STRENGTH:
        raise DegenerateSpreadError(
            f"tau_s = {tau_strength:.4f} < {MIN_TAU_STRENGTH} — zerowa zmienność "
            f"siły drużyn przeczy wszystkiemu, co wiemy o lidze "
            f"(drużyn dobrze zmierzonych={int(well_measured.sum())}, "
            f"n_matches={data.n_matches}, xi={xi}, "
            f"var(s)={float(np.var(strength[well_measured], ddof=1)):.5f}, "
            f"cond(X^T W X)={condition:.3e}). "
            "To jest awaria estymacji, nie ustalenie."
        )

    # Wrażliwość progu — WYŁĄCZNIE raport, nie wpływa na wynik (§11.9 pkt 1).
    sensitivity = {}
    for alt in (3.0, 10.0):
        mask = data.effective_matches >= alt
        sensitivity[alt] = (
            _marginal_likelihood_tau(strength[mask], se_strength[mask])
            if int(mask.sum()) >= _MIN_TEAMS_FOR_TAU
            else float("nan")
        )

    return EmpiricalBayesResult(
        scales=PriorScales(strength=tau_strength, openness=tau_openness),
        var_strength=float(np.var(strength[well_measured], ddof=1)),
        var_openness=float(np.var(openness[well_measured], ddof=1)),
        noise_strength=float(np.mean(se_strength[well_measured] ** 2)),
        noise_openness=float(np.mean(se_openness[well_measured] ** 2)),
        n_teams=t,
        n_well_measured=int(well_measured.sum()),
        n_dropped_teams=data.n_dropped_teams,
        n_dropped_matches=data.n_dropped_matches,
        condition_number=condition,
        max_se_strength=float(se_strength[well_measured].max()),
        tau_strength_sensitivity=sensitivity,
    )


def _assert_tau_positive(params: DixonColesParams, data: _FitData) -> None:
    """Kontrola z STEP4_PLAN §1.3 — tau <= 0 to ujemne prawdopodobieństwo."""
    attack = np.array([params.attack[t] for t in data.teams], dtype=np.float64)
    defence = np.array([params.defence[t] for t in data.teams], dtype=np.float64)
    lam = attack[data.home_idx] * defence[data.away_idx] * params.home_advantage
    mu = attack[data.away_idx] * defence[data.home_idx]
    tau = _tau(data.home_goals, data.away_goals, lam, mu, params.rho)
    if (tau <= 0.0).any():
        n_bad = int((tau <= 0.0).sum())
        raise RuntimeError(
            f"dopasowanie daje tau <= 0 dla {n_bad} meczów (rho={params.rho:.4f}) — "
            "macierz wyników miałaby ujemne komórki"
        )


def log_likelihood(
    params: DixonColesParams,
    matches: pd.DataFrame,
    *,
    allow_unknown_teams: bool = False,
) -> float:
    """Log-wiarygodność goli pod zadanymi parametrami, **bez** wag czasowych.

    Służy do wyboru ``xi`` na sezonie walidacyjnym (STEP4_PLAN §1.5).
    Wagi są narzędziem dopasowania, nie oceny: na zbiorze walidacyjnym
    interesuje nas czysty fit predykcyjny, a nie to, jak bardzo model
    ceni ostatnie mecze.
    """
    _validate_matches(matches)
    home_goals = matches["home_goals"].to_numpy(dtype=np.int64)
    away_goals = matches["away_goals"].to_numpy(dtype=np.int64)
    rates = [
        params.rates(h, a, allow_unknown_teams=allow_unknown_teams)
        for h, a in zip(
            matches["home_team_id"].astype(str),
            matches["away_team_id"].astype(str),
            strict=True,
        )
    ]
    lam = np.array([r[0] for r in rates], dtype=np.float64)
    mu = np.array([r[1] for r in rates], dtype=np.float64)
    tau = _tau(home_goals, away_goals, lam, mu, params.rho)
    if (tau <= 0.0).any():
        raise RuntimeError("log_likelihood: tau <= 0 — parametry niezgodne z danymi")
    terms = (
        np.log(tau)
        + home_goals * np.log(lam)
        - lam
        + away_goals * np.log(mu)
        - mu
        - gammaln(home_goals + 1.0)
        - gammaln(away_goals + 1.0)
    )
    return float(terms.sum())


def score_matrix(
    params: DixonColesParams,
    home_team_id: str,
    away_team_id: str,
    *,
    max_goals: int = MAX_GOALS_DEFAULT,
    allow_unknown_teams: bool = False,
) -> NDArray[np.float64]:
    """Macierz ``(max_goals+1, max_goals+1)`` sumująca się do 1.

    ``P[i, j] = tau(i, j) * Poisson(i; lambda) * Poisson(j; mu)``, po czym
    renormalizacja.

    UWAGA — STEP4_PLAN §1.7 podaje błędne uzasadnienie
    ---------------------------------------------------
    Plan twierdzi, że „korekta tau psuje normalizację o rząd 1e-3".
    **Nie psuje.** Suma poprawek jest tożsamościowo zerowa::

        rho * exp(-lambda-mu) * [ -lambda*mu + lambda*mu + mu*lambda - lambda*mu ] = 0

    bo ``P(0,0) = e^-l e^-m``, ``P(0,1) = e^-l * m e^-m``,
    ``P(1,0) = l e^-l * e^-m``, ``P(1,1) = l e^-l * m e^-m``. Zweryfikowane
    numerycznie: odchyłka rzędu 1e-16 przy dowolnym ``rho``. Dixon i Coles
    tak właśnie skonstruowali ``tau`` — to poprawna perturbacja, nie
    przybliżenie.

    Cała odchyłka pochodzi z **obcięcia** macierzy i dlatego lekarstwem
    jest odpowiednio duże ``max_goals``, a nie renormalizacja.
    Renormalizacja zostaje jako zabezpieczenie numeryczne, ale rozmazuje
    brakujący ogon **proporcjonalnie po wszystkich komórkach**, podczas
    gdy brakuje go wyłącznie w wynikach wysokich. Dla 1X2 to bez
    znaczenia, dla Over 3.5 i wyżej to systematyczne zaniżenie — czyli
    dokładnie ten rynek, o którego kalibracji ostrzega STEP4_PLAN §8.
    """
    if max_goals < 1:
        raise ValueError(f"max_goals musi być dodatnie, jest {max_goals}")
    lam, mu = params.rates(
        home_team_id, away_team_id, allow_unknown_teams=allow_unknown_teams
    )
    return matrix_from_rates(lam, mu, params.rho, max_goals=max_goals)


def matrix_from_rates(
    lam: float, mu: float, rho: float, *, max_goals: int = MAX_GOALS_DEFAULT
) -> NDArray[np.float64]:
    """Macierz wyników wprost z ``(lambda, mu, rho)``, bez obiektu parametrów.

    Wydzielone, żeby odwracanie kursów rynkowych w
    ``backtest/market_benchmark.py`` używało **tej samej** funkcji co model.
    Gdyby benchmark miał własną kopię wzoru, porównywalibyśmy nasz model z
    lekko innym modelem i nie wiedzieli o tym.
    """
    grid = np.arange(max_goals + 1)
    pmf_home = np.asarray(poisson.pmf(grid, lam), dtype=np.float64)
    pmf_away = np.asarray(poisson.pmf(grid, mu), dtype=np.float64)

    outside = 1.0 - float(poisson.cdf(max_goals, lam) * poisson.cdf(max_goals, mu))
    if outside > TRUNCATION_TOLERANCE:
        log.warning(
            "masa poza obcięciem %.2e > %.0e dla lambda=%.3f mu=%.3f — "
            "zwiększ max_goals",
            outside,
            TRUNCATION_TOLERANCE,
            lam,
            mu,
        )

    matrix = np.outer(pmf_home, pmf_away)
    matrix[0, 0] *= 1.0 - lam * mu * rho
    matrix[0, 1] *= 1.0 + lam * rho
    matrix[1, 0] *= 1.0 + mu * rho
    matrix[1, 1] *= 1.0 - rho
    if (matrix < 0.0).any():
        raise RuntimeError(
            f"ujemna komórka macierzy dla lambda={lam:.3f} mu={mu:.3f} "
            f"rho={rho:.4f} — naruszone ograniczenie tau > 0"
        )
    return np.asarray(matrix / matrix.sum(), dtype=np.float64)


def probabilities_1x2(
    params: DixonColesParams,
    home_team_id: str,
    away_team_id: str,
    *,
    max_goals: int = MAX_GOALS_DEFAULT,
    allow_unknown_teams: bool = False,
) -> NDArray[np.float64]:
    """``(P(1), P(X), P(2))`` z macierzy wyników — konwencja jak w ``metrics``.

    Wersja ogólna (dowolny rynek z macierzy) zamieszka w
    ``pricing/markets.py``; tu jest tyle, ile potrzebuje bramka jakościowa
    ze STEP4_PLAN §2, i jest testem odniesienia dla tamtej.
    """
    matrix = score_matrix(
        params,
        home_team_id,
        away_team_id,
        max_goals=max_goals,
        allow_unknown_teams=allow_unknown_teams,
    )
    draw = float(np.trace(matrix))
    home = float(np.tril(matrix, -1).sum())
    away = float(np.triu(matrix, 1).sum())
    return np.array([home, draw, away], dtype=np.float64)
