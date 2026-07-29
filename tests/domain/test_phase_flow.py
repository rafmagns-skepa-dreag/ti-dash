import time
import pytest
from ti_dash.domain.game import Game


def game2():
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
    assert g.phase == "Status" and g.status_clock.running
    t[0] = 50.0
    g.end_status_phase()
    rec = g.pending_records[-1]
    assert rec.context == "status" and rec.player_name is None
    assert g.awaiting_admin is True


def test_agenda_window_and_vote_recorded(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    g = game2()
    g.start_agenda_phase()
    assert g.phase == "Agenda"
    g.open_agenda_window()
    t[0] = 10.0
    g.close_agenda_window()
    assert g.pending_records[-1].context == "agenda_window"
    ana = g.players[0]
    g.begin_agenda_vote(ana)
    t[0] = 30.0
    g.cast_agenda_vote(ana, "d0")
    rec = g.pending_records[-1]
    assert rec.context == "agenda_vote" and rec.player_name == "Ana"


def test_new_round_resets_cards_passes_and_returns_to_strategy():
    g = game2()
    for p in g.players:
        p.strategy_card = 4
        p.passed = True
    g.round = 3
    g.agenda_enabled_this_round = True
    g.new_round()
    assert g.round == 4
    assert all(p.strategy_card is None and not p.passed for p in g.players)
    assert g.phase == "Strategy" and g.active is None
    assert g.agenda_enabled_this_round is False
