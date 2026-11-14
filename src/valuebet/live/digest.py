"""Przegląd dnia — progi kursowe dla człowieka (TOR_S_PLAN §6).

Tryb progowy: nie mówimy „stawiaj", mówimy „od tego kursu warto". Człowiek
porównuje próg z tablicą u bukmachera i klika sam — bot nigdy nie składa
zakładu (``CLAUDE.md``, „Granice projektu").

Bez tokena Telegrama digest **zapisuje się do pliku**, nie znika. Brak
kanału nie może oznaczać braku przeglądu dnia; pierwsze tygodnie i tak
będą czytane z pliku.

Żadnych sekretów w treści
-------------------------
Treść idzie na zewnątrz — do Telegrama albo do pliku w ``reports/``, który
kiedyś może trafić do repo. Token i chat id nigdy nie trafiają do tekstu.
Telegram Bot API przyjmuje token **w ścieżce URL** (``/bot<token>/``), więc
inaczej się nie da — dlatego zapytanie idzie przez ``net/http.py``, który
redaguje ``/bot…/`` w logach, wyjątkach i ``repr``, a przy odrzuceniu
logujemy wyłącznie kod HTTP, bez treści odpowiedzi (FSA #0 F-27).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from valuebet.net.http import HttpClient, HttpError
from valuebet.pricing.ev import min_odds
from valuebet.pricing.fair import STALE_WARNING_AGE, FairPrice

__all__ = ["DIGEST_DIR", "DigestLine", "build_digest", "send_digest"]

log = logging.getLogger(__name__)

_HTTP_OK = 200

DIGEST_DIR = Path("reports/digest")
#: Horyzont przeglądu: mecze w najbliższych 36 h.
HORIZON = timedelta(hours=36)


@dataclass(frozen=True)
class DigestLine:
    match_id: str
    label: str
    kickoff: datetime
    league: str
    rows: tuple[tuple[str, float, float], ...]
    snapshot_age: timedelta

    @property
    def is_stale(self) -> bool:
        return self.snapshot_age > STALE_WARNING_AGE


def build_digest(
    prices: Iterable[FairPrice],
    *,
    kickoffs: dict[str, datetime],
    labels: dict[str, str],
    leagues: dict[str, str],
    decision_time: datetime,
    tax_factor: float,
    mode: str,
    edge_threshold: float,
    winnings_factor: float,
    horizon: timedelta = HORIZON,
) -> str:
    """Tekst przeglądu. Jedna sekcja na ligę, tabela progów per mecz."""
    if decision_time.tzinfo is None:
        raise ValueError("decision_time musi być timezone-aware (reguła 2)")

    by_match: dict[str, list[FairPrice]] = {}
    for price in prices:
        kickoff = kickoffs.get(price.match_id)
        if kickoff is None:
            continue
        if not (decision_time <= kickoff <= decision_time + horizon):
            continue
        by_match.setdefault(price.match_id, []).append(price)

    lines: list[DigestLine] = []
    for match_id, group in by_match.items():
        rows = tuple(
            (
                _outcome_label(p),
                p.p,
                min_odds(
                    p.p,
                    tax_factor=tax_factor,
                    winnings_factor=winnings_factor,
                    edge_threshold=edge_threshold,
                ),
            )
            for p in sorted(group, key=_sort_key)
        )
        newest = max(p.observed_at for p in group)
        lines.append(
            DigestLine(
                match_id=match_id,
                label=labels.get(match_id, match_id),
                kickoff=kickoffs[match_id],
                league=leagues.get(match_id, "nieznana"),
                rows=rows,
                snapshot_age=decision_time - newest,
            )
        )

    return _render(lines, decision_time=decision_time, tax_factor=tax_factor, mode=mode)


def _outcome_label(price: FairPrice) -> str:
    if price.line is None:
        return price.outcome
    return f"{price.outcome} {price.line:g}"


#: Kolejność rynków w przeglądzie — nazwy kanoniczne i z The Odds API
#: (``h2h`` = 1X2; FSA #0 F-18: słownik bez ``h2h`` spychał 1X2 na koniec).
MARKET_ORDER: tuple[str, ...] = ("h2h", "1x2", "totals", "over_under", "spreads", "asian_handicap")


def _sort_key(price: FairPrice) -> tuple[int, float, str]:
    rank = MARKET_ORDER.index(price.market) if price.market in MARKET_ORDER else len(MARKET_ORDER)
    return (rank, price.line or 0.0, price.outcome)


def _render(
    lines: Sequence[DigestLine],
    *,
    decision_time: datetime,
    tax_factor: float,
    mode: str,
) -> str:
    out: list[str] = []
    stale = [line for line in lines if line.is_stale]
    out.append(f"PRZEGLAD DNIA  {decision_time:%Y-%m-%d %H:%M} UTC")
    out.append(f"tryb: {mode.upper()}   tax_factor: {tax_factor:.2f}")
    out.append("progi k_min: od tego kursu warto. Klikasz sam.")
    if stale:
        out.append(
            f"UWAGA: {len(stale)} meczow z migawka starsza niz "
            f"{STALE_WARNING_AGE} — progi moga byc nieaktualne"
        )
    if not lines:
        out.append("")
        out.append("Brak meczow w horyzoncie albo brak wycenialnych migawek.")
        return "\n".join(out)

    for league in sorted({line.league for line in lines}):
        out.append("")
        out.append(f"=== {league} ===")
        for line in sorted(
            (x for x in lines if x.league == league), key=lambda x: x.kickoff
        ):
            age_hours = line.snapshot_age.total_seconds() / 3600.0
            flag = "  [STARA MIGAWKA]" if line.is_stale else ""
            out.append(
                f"{line.kickoff:%a %d.%m %H:%M} UTC  {line.label}"
                f"   (migawka {age_hours:.1f} h){flag}"
            )
            for outcome, p, threshold in line.rows:
                out.append(f"    {outcome:<14} p={p:.4f}   k_min={threshold:.3f}")
    return "\n".join(out)


def send_digest(text: str, *, now: datetime, http: HttpClient) -> Path | None:
    """Telegram, jeśli jest token; inaczej plik. Zwraca ścieżkę pliku albo ``None``.

    Brak tokena to **nie błąd** — digest ma być dostępny od pierwszego dnia,
    a kanał można dołożyć później.
    """
    if now.tzinfo is None:
        raise ValueError("now musi być timezone-aware (reguła 2)")
    token = os.environ.get("VB_TELEGRAM_TOKEN")
    chat_id = os.environ.get("VB_TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            response = http.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json_body={"chat_id": chat_id, "text": text},
            )
            if response.status_code == _HTTP_OK:
                return None
            # Komunikat bez treści odpowiedzi: Telegram odbija w niej token.
            log.error("Telegram odrzucił wiadomość: HTTP %s", response.status_code)
        except HttpError:
            # HttpError jest zredagowany (token w ścieżce /bot…/ wycięty).
            log.exception("nie udało się wysłać przez Telegram — zapisuję do pliku")

    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    path = DIGEST_DIR / f"{now:%Y-%m-%d_%H%M}.txt"
    path.write_text(text, encoding="utf-8")
    log.info("digest zapisany do %s", path)
    return path
