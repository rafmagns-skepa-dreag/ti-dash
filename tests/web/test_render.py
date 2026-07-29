from ti_dash.domain.game import Game
from ti_dash.web import render


def demo_running():
    g = Game.demo()
    g.start_action_phase = g.start_action_phase  # ensure method exists
    for i, p in enumerate(g.players):
        p.strategy_card = i + 1
    g.start_action_phase()
    return g


def test_timer_fragment_has_id_and_signals():
    g = demo_running()
    html = render.timer_fragment(g)
    assert 'id="active-timer"' in html
    assert "data-signals" in html or "data-signals-ends-at" in html


def test_players_fragment_lists_all_players():
    g = Game.demo()
    html = render.players_fragment(g)
    for name in ("Ana", "Bo", "Cass", "Dev"):
        assert name in html
    assert 'id="players"' in html


def test_phasebar_shows_round_and_phase():
    g = Game.demo()
    html = render.phasebar_fragment(g)
    assert "Strategy" in html
    assert 'id="phasebar"' in html


def test_full_page_loads_datastar_and_embeds_fragments():
    g = Game.demo()
    html = str(render.full_page(g, is_admin=False))
    assert html.startswith("<!doctype html>")
    assert "&lt;!doctype" not in html
    assert "datastar" in html.lower()
    assert 'id="players"' in html and 'id="phasebar"' in html
