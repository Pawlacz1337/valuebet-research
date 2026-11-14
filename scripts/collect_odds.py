"""Punkt wejścia kolektora kursów — wołany przez Task Scheduler co 5 min.

Co przebieg: terminarz z bezpłatnego ``/events`` (gdy starszy niż 60 min),
potem kotwice należne teraz; zawsze linia heartbeatu. Konfigurację
harmonogramu opisuje ``docs/task_scheduler.md``.

Użycie::

    uv run python scripts/collect_odds.py            # zwykły przebieg
    uv run python scripts/collect_odds.py --refresh  # terminarz teraz (/events, bezpłatne)

``--refresh`` nie jest potrzebny do pracy — ``run_once`` sam odświeża
terminarz z ``/events``; flaga wymusza odświeżenie od razu (F0d-01).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import UTC, datetime

from dotenv import load_dotenv

from valuebet.ingest.odds_api import OddsApiClient, OddsApiError, OddsApiSettings
from valuebet.ingest.odds_collector import OddsCollector
from valuebet.net.http import HttpClient


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kolektor The Odds API")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="odśwież terminarz lig teraz z bezpłatnego /events",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # httpx loguje pełne URL-e na INFO, a klucz siedzi w query stringu.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    load_dotenv(dotenv_path=".env")

    settings = OddsApiSettings.from_env()
    try:
        http = HttpClient(clock=time.time, sleep=time.sleep)
        with OddsApiClient(http=http, settings=settings) as client:
            collector = OddsCollector(client=client)
            entry = (
                collector.refresh_events(now=datetime.now(UTC))
                if args.refresh
                else collector.run_once(now=datetime.now(UTC))
            )
    except OddsApiError:
        # Głośno, nie cicho: kolektor, który po awarii konfiguracji grzecznie
        # nic nie robi, to najgorszy tryb awarii w tym projekcie.
        logging.getLogger("collect_odds").exception("kolektor nie wystartował")
        return 2

    print(json.dumps(entry, ensure_ascii=False, default=str))
    return 1 if entry.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())
