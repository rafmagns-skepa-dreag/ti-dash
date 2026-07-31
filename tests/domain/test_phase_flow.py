import time

from ti_dash.domain.game import Game
from ti_dash.domain.reference import Context, Phase, StrategyCard


def game2() -> Game:
    g = Game()
    a = g.add_player("Ana", "F", "Red")
    g.claim_seat(a, "d0")
    b = g.add_player("Bo", "F", "Blue")
    g.claim_seat(b, "d1")
    return g


def test_status_phase_records_shared_segment(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    g = game2()
    g.start_status_phase()
    assert g.phase == Phase.Status and g.status_clock.running
    t[0] = 50.0
    g.end_status_phase()
    rec = g.pending_records[-1]
    assert rec.context == Context.STATUS and rec.player_name is None
    assert g.awaiting_admin is True


def test_agenda_window_and_vote_recorded(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    g = game2()
    g.start_agenda_phase()
    assert g.phase == Phase.Agenda
    g.open_agenda_window()
    t[0] = 10.0
    g.close_agenda_window()
    assert g.pending_records[-1].context == Context.AGENDA_WINDOW
    ana = g.players[0]
    g.begin_agenda_vote()
    t[0] = 30.0
    g.cast_agenda_vote(ana, "d0")
    rec = g.pending_records[-1]
    assert rec.context == Context.AGENDA_VOTE and rec.player_name == "Ana"


def test_new_round_resets_cards_passes_and_returns_to_strategy():
    g = game2()
    for p in g.players:
        p.strategy_card = StrategyCard.Construction
        p.passed = True
    g.round = 3
    g.enable_agenda_phase()
    g.new_round()
    assert g.round == 4
    assert all(p.strategy_card is None and not p.passed for p in g.players)
    assert g.phase == Phase.Strategy and g.active is None
    assert g.agenda_enabled_this_round is True
