from ti_dash.domain.models import Player
from ti_dash.domain.game import Game


def make_game():
    g = Game()
    g.players = [
        Player(name="Ana", faction="F", color="Red", seat=0),
        Player(name="Bo", faction="F", color="Blue", seat=1),
        Player(name="Cass", faction="F", color="Green", seat=2),
        Player(name="Dev", faction="F", color="Yellow", seat=3),
    ]
    return g


def test_initiative_defaults_last_when_no_card():
    p = Player(name="X", faction="F", color="Red", seat=0)
    assert p.initiative == 99
    p.strategy_card = 4
    assert p.initiative == 4


def test_seating_order_rotates_to_speaker():
    g = make_game()
    g.speaker = 2  # Cass is Speaker
    assert [p.name for p in g.seating_order()] == ["Cass", "Dev", "Ana", "Bo"]


def test_initiative_order_by_card_number():
    g = make_game()
    g.players[0].strategy_card = 6   # Ana
    g.players[1].strategy_card = 1   # Bo
    g.players[2].strategy_card = 3   # Cass
    g.players[3].strategy_card = None
    assert [p.name for p in g.initiative_order()] == ["Bo", "Cass", "Ana", "Dev"]


def test_demo_builds_four_players_round_one_strategy():
    g = Game.demo()
    assert len(g.players) == 4
    assert g.round == 1 and g.phase == "Strategy"
