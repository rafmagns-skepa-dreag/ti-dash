import time

from ti_dash.domain.game import Game
from ti_dash.domain.reference import Context, Phase, StrategyCard


def game2() -> Game:
    g = Game()
    a = g.add_player("Ana", "F", "Red")
    g.claim_seat(a, "d0")
    b = g.add_player("Bo", "F", "Blue")
    g.claim_seat(b, "d1")
    g.paused = False
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


def test_pass_status_ends_phase_once_everyone_passed(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    g = game2()
    g.start_status_phase()
    ana, bo = g.players[0], g.players[1]
    g.pass_status(ana, "d0")
    assert ana.passed is True
    assert g.awaiting_admin is False
    assert g.status_clock.running
    t[0] = 20.0
    g.pass_status(bo, "d1")
    assert bo.passed is True
    assert g.awaiting_admin is True
    rec = g.pending_records[-1]
    assert rec.context == Context.STATUS and rec.player_name is None


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
    ana, bo = g.players[0], g.players[1]
    g.begin_agenda_vote()
    # voting starts with the player after the speaker; the speaker goes last
    assert g.current_phase_ordering[g.active] is bo
    t[0] = 30.0
    g.cast_agenda_vote(bo, "d1")
    rec = g.pending_records[-1]
    assert rec.context == Context.AGENDA_VOTE and rec.player_name == "Bo"
    assert g.current_phase_ordering[g.active] is ana
    t[0] = 40.0
    g.cast_agenda_vote(ana, "d0")
    rec = g.pending_records[-1]
    assert rec.context == Context.AGENDA_VOTE and rec.player_name == "Ana"
    assert g.active is None


def test_agenda_vote_out_of_order_rejected():
    g = game2()
    g.start_agenda_phase()
    g.begin_agenda_vote()
    ana = g.players[0]
    try:
        g.cast_agenda_vote(ana, "d0")
        assert False, "expected PermissionError"
    except PermissionError:
        pass


def test_only_one_agenda_timer_runs_at_a_time():
    g = game2()
    g.start_agenda_phase()
    g.open_agenda_window()
    assert g.agenda_window_clock.running
    g.begin_agenda_vote()
    assert g.agenda_vote_clock.running and not g.agenda_window_clock.running
    g.open_agenda_window()
    assert g.agenda_window_clock.running and not g.agenda_vote_clock.running


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
    assert g.strategy_pick_started is False
