import time
import pytest
from ti_dash.domain.game import Game


def four_player_game():
    g = Game()
    for i, (n, c) in enumerate(
        [("Ana", "Red"), ("Bo", "Blue"), ("Cass", "Green"), ("Dev", "Yellow")]
    ):
        p = g.add_player(n, "F", c)
        g.claim_seat(p, f"d{i}")
    return g


def cards(g, mapping):
    for name, card in mapping.items():
        next(p for p in g.players if p.name == name).strategy_card = card


def test_start_action_phase_activates_lowest_initiative():
    g = four_player_game()
    cards(g, {"Ana": 6, "Bo": 1, "Cass": 3, "Dev": 8})
    g.start_action_phase()
    assert g.phase == "Action"
    assert g.players[g.active].name == "Bo"  # card 1
    assert g.action_clock.running is True


def test_end_turn_records_and_advances_in_initiative(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    g = four_player_game()
    cards(g, {"Ana": 6, "Bo": 1, "Cass": 3, "Dev": 8})
    g.start_action_phase()  # Bo active
    bo = g.players[g.active]
    t[0] = 40.0
    g.end_turn(bo, bo.claim_token)
    rec = g.pending_records[-1]
    assert rec.context == "action" and rec.player_name == "Bo" and rec.turn == 0
    assert g.players[g.active].name == "Cass"  # next by initiative


def test_pass_marks_passed_and_is_skipped():
    g = four_player_game()
    cards(g, {"Ana": 6, "Bo": 1, "Cass": 3, "Dev": 8})
    g.start_action_phase()  # Bo
    bo = g.players[g.active]
    g.pass_turn(bo, bo.claim_token)
    assert bo.passed is True
    assert g.players[g.active].name == "Cass"


def test_phase_gates_when_all_passed():
    g = four_player_game()
    cards(g, {"Ana": 6, "Bo": 1, "Cass": 3, "Dev": 8})
    g.start_action_phase()
    for _ in range(4):
        p = g.players[g.active]
        g.pass_turn(p, p.claim_token)
    assert g.active is None
    assert g.awaiting_admin is True
    assert g.action_clock.running is False


def test_secondary_window_records_for_active_player(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    g = four_player_game()
    cards(g, {"Ana": 6, "Bo": 1, "Cass": 3, "Dev": 8})
    g.start_action_phase()  # Bo active
    g.open_secondary()
    t[0] = 15.0
    g.close_secondary()
    rec = g.pending_records[-1]
    assert rec.context == "secondary" and rec.player_name == "Bo"
