import time

from ti_dash.domain.game import Game
from ti_dash.domain.models import Player
from ti_dash.domain.reference import Color, Context, Faction, Phase, StrategyCard


def four_player_game() -> Game:
    g = Game(
        players=[
            Player("Ana", Faction.F, Color.RED, 0, strategy_card=StrategyCard.Warfare),
            Player(
                "Bo", Faction.F, Color.BLUE, 1, strategy_card=StrategyCard.Leadership
            ),
            Player(
                "Cass", Faction.F, Color.GREEN, 2, strategy_card=StrategyCard.Politics
            ),
            Player(
                "Dev", Faction.F, Color.YELLOW, 3, strategy_card=StrategyCard.Imperial
            ),
        ]
    )
    for player in g.players:
        g.claim_seat(player, f"d{player.seat}")
    return g


def test_start_action_phase_activates_lowest_initiative():
    g = four_player_game()
    g.start_action_phase()
    assert g.phase == Phase.Action
    assert g.active is not None
    assert g.current_phase_ordering[g.active].name == "Bo"  # card 1
    assert g.action_clock.running is True


def test_end_turn_records_and_advances_in_initiative(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    g = four_player_game()
    g.start_action_phase()  # Bo active
    assert g.active is not None
    bo = g.current_phase_ordering[g.active]
    t[0] = 40.0
    g.end_turn(bo, bo.claim_token)
    rec = g.pending_records[-1]
    assert rec.context == Context.ACTION and rec.player_name == "Bo" and rec.turn == 0
    assert g.current_phase_ordering[g.active].name == "Cass"  # next by initiative


def test_pass_marks_passed_and_is_skipped():
    g = four_player_game()
    g.start_action_phase()  # Bo
    assert g.active is not None
    bo = g.current_phase_ordering[g.active]
    g.pass_turn(bo, bo.claim_token)
    assert bo.passed is True
    assert g.current_phase_ordering[g.active].name == "Cass"


def test_phase_gates_when_all_passed():
    g = four_player_game()
    g.start_action_phase()
    assert g.active is not None
    for _ in range(4):
        p = g.current_phase_ordering[g.active]
        g.pass_turn(p, p.claim_token)
    assert g.active is None
    assert g.awaiting_admin is True
    assert g.action_clock.running is False


def test_secondary_window_records_for_active_player(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    g = four_player_game()
    g.start_action_phase()  # Bo active
    assert g.current_phase_ordering[g.active].name == "Bo"
    g.open_secondary()
    t[0] = 15.0
    g.close_secondary()
    rec = g.pending_records[-1]
    assert rec.context == Context.SECONDARY and rec.player_name == "Bo"
