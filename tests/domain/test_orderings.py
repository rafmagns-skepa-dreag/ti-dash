from ti_dash.domain.game import Game
from ti_dash.domain.models import Player
from ti_dash.domain.reference import Color, Faction, StrategyCard


def make_game() -> Game:
    return Game(
        players=[
            Player(name="Ana", faction=Faction.ARBOREC, color=Color.RED, seat=0),
            Player(name="Bo", faction=Faction.ARBOREC, color=Color.BLUE, seat=1),
            Player(name="Cass", faction=Faction.ARBOREC, color=Color.GREEN, seat=2),
            Player(name="Dev", faction=Faction.ARBOREC, color=Color.YELLOW, seat=3),
        ]
    )


def test_initiative_defaults_last_when_no_card():
    p = Player(name="X", faction=Faction.ARBOREC, color=Color.RED, seat=0)
    assert p.initiative == 99
    p.strategy_card = StrategyCard.Construction
    assert p.initiative == 4


def test_seating_order_rotates_to_speaker():
    g = make_game()
    g.speaker_seat_number = 2  # Cass is Speaker
    assert [p.name for p in g.speaker_order()] == ["Cass", "Dev", "Ana", "Bo"]


def test_initiative_order_by_card_number():
    g = make_game()
    g.players[0].strategy_card = StrategyCard.Warfare  # Ana
    g.players[1].strategy_card = StrategyCard.Leadership  # Bo
    g.players[2].strategy_card = StrategyCard.Politics  # Cass
    g.players[3].strategy_card = None
    assert [p.name for p in g.initiative_order()] == ["Bo", "Cass", "Ana", "Dev"]


def test_seating_order_falls_back_when_speaker_seat_absent():
    g = make_game()
    g.speaker_seat_number = 99  # No such seat
    assert [p.name for p in g.speaker_order()] == ["Ana", "Bo", "Cass", "Dev"]
