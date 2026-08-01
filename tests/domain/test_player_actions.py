import time

import pytest

from ti_dash.domain.game import Game
from ti_dash.domain.reference import Context, StrategyCard


def test_score_clamps_between_zero_and_goal():
    g = Game()
    p = g.add_player("Ana", "F", "Red")
    g.claim_seat(p, "d1")
    g.paused = False
    g.score(p, 3, "d1")
    assert p.vp == 3
    g.score(p, 1000, "d1")
    assert p.vp == g.vp_goal
    g.score(p, -1000, "d1")
    assert p.vp == 0


def test_set_speaker_updates_seat_number_and_order():
    g = Game()
    ana = g.add_player("Ana", "F", "Red")
    g.claim_seat(ana, "d1")
    bo = g.add_player("Bo", "F", "Blue")
    g.claim_seat(bo, "d2")
    g.set_speaker(bo)
    assert g.speaker_seat_number == bo.seat
    assert g.speaker_order()[0] is bo


def test_score_requires_authorization():
    g = Game()
    p = g.add_player("Ana", "F", "Red")
    g.claim_seat(p, "d1")
    g.paused = False
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
    g.paused = False
    g.begin_strategy_pick()
    t[0] = 25.0
    g.pick_strategy_card(a, StrategyCard.Trade, "d1")
    assert a.strategy_card == StrategyCard.Trade
    rec = g.pending_records[-1]
    assert rec.context == Context.STRATEGY_PICK and rec.player_name == "Ana"
    assert rec.duration_seconds == 25.0 and rec.turn is None
    # stealing
    g.begin_strategy_pick()
    g.pick_strategy_card(b, StrategyCard.Trade, "d2")
    assert b.strategy_card == StrategyCard.Trade and a.strategy_card is None


def test_awaiting_admin_set_once_all_players_have_picked():
    g = Game()
    a = g.add_player("Ana", "F", "Red")
    g.claim_seat(a, "d1")
    b = g.add_player("Bo", "F", "Blue")
    g.claim_seat(b, "d2")
    g.paused = False

    g.begin_strategy_pick()
    g.pick_strategy_card(a, StrategyCard.Trade, "d1")
    assert g.awaiting_admin is False

    g.begin_strategy_pick()
    g.pick_strategy_card(b, StrategyCard.Warfare, "d2")
    assert g.awaiting_admin is True
