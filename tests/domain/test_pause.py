from ti_dash.domain.reference import Context
import time

import pytest

from ti_dash.domain.game import Game


def test_pause_stops_running_clock_and_banks(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    g = Game()
    g.action_clock.start()
    t[0] = 30.0
    g.pause()
    assert g.paused is True
    assert g.action_clock.running is False
    assert g.action_clock.elapsed() == 30.0
    t[0] = 100.0  # paused time must not count
    assert g.action_clock.elapsed() == 30.0


def test_resume_restarts_the_paused_clock(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    g = Game()
    g.action_clock.start()
    t[0] = 30.0
    g.pause()
    t[0] = 100.0
    g.resume()
    assert g.paused is False
    assert g.action_clock.running is True
    t[0] = 110.0
    assert g.action_clock.elapsed() == 40.0


def test_check_not_paused_raises():
    g = Game()
    g.paused = True
    with pytest.raises(RuntimeError):
        g._check_not_paused()


def test_record_appends_and_flags_over_budget():
    g = Game()
    g.config.action_seconds = 60.0
    g._record(Context.ACTION, player=None, turn=1, duration=75.0)
    r = g.pending_records[0]
    assert r.sequence == 1 and r.context == Context.ACTION
    assert r.over_budget is True and r.duration_seconds == 75.0


def test_pause_stops_all_running_clocks_and_resume_restarts_them(monkeypatch):
    """FIX 3: pause must stop ALL running clocks (not just active_clock), resume restarts all"""
    t = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    g = Game()

    # Start both action_clock and secondary_clock
    g.action_clock.start()
    g.secondary_clock.start()
    t[0] = 30.0

    # Pause should stop BOTH clocks
    g.pause()
    assert g.paused is True
    assert g.action_clock.running is False
    assert g.secondary_clock.running is False
    assert g.action_clock.elapsed() == 30.0
    assert g.secondary_clock.elapsed() == 30.0

    # Advance time during pause - neither should count
    t[0] = 100.0
    assert g.action_clock.elapsed() == 30.0
    assert g.secondary_clock.elapsed() == 30.0

    # Resume should restart BOTH clocks
    g.resume()
    assert g.paused is False
    assert g.action_clock.running is True
    assert g.secondary_clock.running is True

    # Both should continue counting
    t[0] = 110.0
    assert g.action_clock.elapsed() == 40.0
    assert g.secondary_clock.elapsed() == 40.0


def test_resume_starts_strategy_pick_when_not_yet_started():
    """resume() on a fresh/not-started Strategy phase kicks off the pick clock,
    since there's nothing captured in _resume_clocks to fall back on."""
    g = Game()
    g.add_player("Ana", "F", "Red")
    g.start_strategy_phase()
    assert g.paused is True
    assert g.strategy_pick_started is False

    g.resume()

    assert g.paused is False
    assert g.strategy_pick_started is True
    assert g.strategy_pick_clock.running is True


def test_resume_does_not_restart_strategy_pick_once_already_started():
    g = Game()
    g.add_player("Ana", "F", "Red")
    g.start_strategy_phase()
    g.begin_strategy_pick()
    g.pause()
    g.resume()
    assert g.strategy_pick_clock.running is True
