from ti_dash.domain.game import Game
from ti_dash.domain.models import Player
from ti_dash.domain.reference import Color, Faction, StrategyCard
from ti_dash.web import render


def create_game() -> Game:
    return Game(
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


def demo_running():
    g = Game(
        players=[
            Player("Ana", Faction.F, Color.RED, 0),
            Player("Bo", Faction.F, Color.BLUE, 1),
            Player("Cass", Faction.F, Color.GREEN, 2),
            Player("Dev", Faction.F, Color.YELLOW, 3),
        ]
    )
    for player in g.players:
        g.claim_seat(player, f"d{player.seat}")
    cards(
        g,
        {
            "Ana": StrategyCard.Warfare,
            "Bo": StrategyCard.Leadership,
            "Cass": StrategyCard.Politics,
            "Dev": StrategyCard.Imperial,
        },
    )

    for i, p in enumerate(g.players):
        p.strategy_card = StrategyCard(i + 1)
    g.start_action_phase()
    return g


def test_timer_fragment_has_id_and_signals():
    g = create_game()
    g.start_action_phase()
    html = render.timer_fragment(g)
    assert 'id="active-timer"' in html
    # Single data-signals JSON object; endsAt is referenced verbatim by the
    # countdown expression (must match the declared signal name).
    assert "data-signals=" in html
    assert "endsAt" in html
    assert "$endsAt" in html and "$now" in html
    assert "data-text=" in html


def test_players_fragment_lists_all_players():
    g = create_game()
    html = render.players_fragment(g)
    for name in ("Ana", "Bo", "Cass", "Dev"):
        assert name in html
    assert 'id="players"' in html


def test_phasebar_shows_round_and_phase():
    g = create_game()
    html = render.phasebar_fragment(g)
    assert "Strategy" in html
    assert 'id="phasebar"' in html
    # Datastar v1 event handler uses the colon form, not data-on-click.
    assert "data-on:click" in html
    assert "data-on-click" not in html


def test_players_fragment_buttons_use_datastar_colon_form():
    html = render.players_fragment(create_game())
    assert "data-on:click" in html
    assert "data-on-click" not in html


def test_full_page_loads_datastar_and_embeds_fragments():
    g = create_game()
    html = str(render.full_page(g, is_admin=False))
    assert html.startswith("<!doctype html>")
    assert "&lt;!doctype" not in html
    assert html.lower().count("<!doctype") == 1
    assert "datastar" in html.lower()
    assert 'id="players"' in html and 'id="phasebar"' in html
    # The SSE stream is opened via data-init (runs on element load); a plain
    # data-on-load never fires on <body> and would leave the page empty.
    assert "data-init=" in html
    assert "data-on-load" not in html
    assert "data-on-interval" in html
