"""Jednorazowe pobranie regulaminu „Bez Podatku 2.0” do raw (FSA0_NAPRAWY §3 F-25b).

Przez jedyny klient sieciowy: robots.txt hosta ``dam.begmedia.com`` jest
sprawdzany przed pobraniem — ścieżka zabroniona albo robots.txt niedostępny
→ nic nie jest pobierane, a regulamin trzeba pobrać ręcznie do
``data/raw/tc/betclic/`` (``docs/promocje.md``). Zapis do raw z manifestem.

Użycie::

    uv run python scripts/fetch_betclic_tc.py
"""

from __future__ import annotations

import sys
import time
from datetime import UTC, datetime

from valuebet.ingest.raw_store import RawStore
from valuebet.net.http import HttpClient, RobotsDisallowedError

URL = (
    "https://dam.begmedia.com/rox/images/Global/COMMON/TnC/PL/"
    "Bez_Podatku_2.0_T_Cs_21.05.2026_v2.pdf"
)
SUBDIR = "tc/betclic"
STEM = "Bez_Podatku_2.0_T_Cs_21.05.2026_v2"


def main() -> int:
    store = RawStore()
    existing = store.latest(SUBDIR, STEM, ".pdf")
    if existing is not None:
        print(f"już pobrany: {existing}")
        return 0
    with HttpClient(clock=time.time, sleep=time.sleep) as http:
        try:
            response = http.get(URL)
        except RobotsDisallowedError as exc:
            print(f"NIE POBIERAM: {exc}")
            return 3
    if response.status_code != 200:
        print(f"NIE POBRANO: HTTP {response.status_code}")
        return 4
    content = bytes(response.content)
    if not content.startswith(b"%PDF"):
        print("NIE ZAPISUJĘ: odpowiedź nie jest PDF-em")
        return 5
    path = store.write_raw(
        SUBDIR, STEM, ".pdf", content, now=datetime.now(UTC), recorded_by="fetch_betclic_tc"
    )
    print(f"zapisano {path} ({len(content)} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
