from ti_dash.domain.game import Game
from ti_dash.persistence.serialize import game_from_dict, game_to_dict


def build():
    g = Game()
    a = g.add_player("Ana", "The Nomad", "Red")
    a.vp = 4
    a.strategy_card = 3
    g.claim_seat(a, "d0")
    b = g.add_player("Bo", "The Winnu", "Blue")
    b.passed = True
    g.speaker_seat_number = 1
    g.round = 5
    g.phase = "Action"
    g.active = 0
    g._sequence = 7
    g.action_clock.start()  # live timer — must NOT survive
    return g


def test_roundtrip_preserves_durable_state():
    g = build()
    g2 = game_from_dict(game_to_dict(g))
    assert [
        (p.name, p.vp, p.strategy_card, p.passed, p.seat, p.claim_token)
        for p in g2.players
    ] == [
        ("Ana", 4, 3, False, 0, "d0"),
        ("Bo", 0, None, True, 1, None),
    ]
    assert (g2.speaker_seat_number, g2.round, g2.phase, g2.active) == (
        1,
        5,
        "Action",
        0,
    )
    assert g2._sequence == 7


def test_roundtrip_discards_live_clocks():
    g = build()
    g2 = game_from_dict(game_to_dict(g))
    assert g2.action_clock.running is False
    assert g2.action_clock.elapsed() == 0.0


def test_config_survives_roundtrip():
    g = build()
    g.config.action_seconds = 240.0
    g.config.admin_password = "secret"
    g2 = game_from_dict(game_to_dict(g))
    assert g2.config.action_seconds == 240.0
    assert g2.config.admin_password == "secret"
