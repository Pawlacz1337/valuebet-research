"""Pomocnicy testów regresji FSA (``docs/FSA0_NAPRAWY.md`` §1).

Dwa zadania, oba po to, żeby test regresji był dowodem także na STARYM
kodzie (rewers):

- ``build`` woła konstruktor albo funkcję z odfiltrowanymi argumentami,
  których stara sygnatura nie zna. Bez tego test na starym kodzie padłby na
  ``TypeError`` sygnatury, zanim doszedłby do asercji o zachowaniu — a taki
  czerwony nie jest dowodem.
- ``assert_from_checkout`` sprawdza, że ``valuebet`` jest importowany z tego
  samego drzewa, w którym leży test. W rewersie test jest kopiowany do
  worktree starego commita; gdyby importował pakiet z głównego drzewa,
  czerwony i zielony mierzyłyby ten sam kod.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

__all__ = ["FakeClock", "accepts", "assert_from_checkout", "build", "fake_http"]


def accepts(target: Callable[..., Any], name: str) -> bool:
    """Czy ``target`` przyjmuje argument o tej nazwie."""
    try:
        params = inspect.signature(target).parameters
    except (TypeError, ValueError):
        return True
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return True
    return name in params


def build(target: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    """``target(*args, **kwargs)`` bez argumentów nieznanych staremu kodowi."""
    kept = {k: v for k, v in kwargs.items() if accepts(target, k)}
    return target(*args, **kept)


def assert_from_checkout(test_file: str) -> Path:
    """Pakiet ``valuebet`` musi leżeć w drzewie, z którego pochodzi test."""
    import valuebet

    root = Path(test_file).resolve().parents[2]
    package = Path(valuebet.__file__).resolve()
    if not package.is_relative_to(root):
        raise RuntimeError(
            f"valuebet importowany z {package}, a test leży w {root} — "
            "rewers mierzyłby nie ten kod"
        )
    return root


class FakeClock:
    """Zegar i usypianie dla ``HttpClient`` — sekundy płyną tylko przez ``sleep``."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.t = start
        self.slept = 0.0

    def __call__(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds
        self.slept += seconds


def fake_http(handler: Callable[..., Any], clock: FakeClock | None = None) -> Any:
    """``HttpClient`` na ``MockTransport`` z fałszywym zegarem i stanem w katalogu tymczasowym."""
    import tempfile

    import httpx

    from valuebet.net.http import HttpClient

    state = Path(tempfile.mkdtemp(prefix="vb-http-"))
    clock = clock or FakeClock()
    return HttpClient(
        clock=clock,
        sleep=clock.sleep,
        transport=httpx.MockTransport(handler),
        state_dir=state / "throttle",
        robots_dir=state / "robots",
    )
