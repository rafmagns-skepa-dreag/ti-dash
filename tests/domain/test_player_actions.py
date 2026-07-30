import time

import pytest

from ti_dash.domain.game import Game


def test_score_clamps_between_zero_and_goal():
    g = Game()
    p = g.add_player("Ana", "F", "Red")
    g.claim_seat(p, "d1")
    g.score(p, 3, "d1")
    assert p.vp == 3
    g.score(p, 1000, "d1")
    assert p.vp == g.vp_goal
    g.score(p, -1000, "d1")
    assert p.vp == 0


def test_score_requires_authorization():
    g = Game()
    p = g.add_player("Ana", "F", "Red")
    g.claim_seat(p, "d1")
    with pytest.raises(PermissionError):
        g.score(p, 1, "d2")


def test_score_blocked_while_paused():
    g = Game()
    p = g.add_player("Ana", "F", "Red")
    g.claim_seat(p, "d1")
    g.paused = True
    with pytest.raises(RuntimeError):
        g.score(p, 1, "d1")


def test_pick_records_strategy_pick_and_steals(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    g = Game()
    a = g.add_player("Ana", "F", "Red")
    g.claim_seat(a, "d1")
    b = g.add_player("Bo", "F", "Blue")
    g.claim_seat(b, "d2")
    g.begin_strategy_pick(a)
    t[0] = 25.0
    g.pick_strategy_card(a, 5, "d1")
    assert a.strategy_card == 5
    rec = g.pending_records[-1]
    assert rec.context == "strategy_pick" and rec.player_name == "Ana"
    assert rec.duration_seconds == 25.0 and rec.turn is None
    # stealing
    g.begin_strategy_pick(b)
    g.pick_strategy_card(b, 5, "d2")
    assert b.strategy_card == 5 and a.strategy_card is None
