"""Shared pytest fixtures for the ti-dash test suite."""

import pytest


@pytest.fixture
def fake_clock(monkeypatch):
    """Controllable replacement for time.monotonic() across game.py.

    Real time.sleep() in tests is slow and flaky under load; this lets tests
    drive Clock/Game timing deterministically via `fake_clock(5.0)` instead.
    """
    state = {"t": 0.0}
    monkeypatch.setattr("game.time.monotonic", lambda: state["t"])

    def advance(seconds: float) -> None:
        state["t"] += seconds

    return advance
