import time

import htpy

from ti_dash.domain.game import Game
from ti_dash.web.components import player_card


def _active_ends_at_ms(game: Game) -> int:
    clock = game.active_clock()
    if clock is None or clock.remaining() is None:
        return 0
    return int((time.time() + clock.remaining()) * 1000)


def timer_fragment(game: Game) -> str:
    ends_at = _active_ends_at_ms(game)
    running = "true" if game.active_clock() is not None else "false"
    paused = "true" if game.paused else "false"
    node = htpy.div(
        id="active-timer",
        data_signals_ends_at=str(ends_at),
        data_signals_running=running,
        data_signals_paused=paused,
        # remaining seconds = (ends_at - now)/1000, formatted client-side
        data_text="$running ? Math.round(($ends_at - $now)/1000) + 's' : '--'",
    )[""]
    return str(node)


def players_fragment(game: Game) -> str:
    return str(htpy.div(id="players")[[player_card(game, p) for p in game.players]])


def phasebar_fragment(game: Game) -> str:
    active = game.players[game.active].name if game.active is not None else "—"
    gate = (
        htpy.button(class_="gate", data_on_click="@post('/action/advance')")["Start next phase"]
        if game.awaiting_admin else ""
    )
    pause_label = "Resume" if game.paused else "Pause"
    return str(htpy.div(id="phasebar")[
        htpy.span[f"Round {game.round}"],
        htpy.span[f"Phase: {game.phase}"],
        htpy.span[f"Active: {active}"],
        htpy.span[f"Paused: {game.paused}"],
        htpy.button(class_="pause", data_on_click="@post('/action/toggle_pause')")[pause_label],
        gate,
    ])


def full_page(game: Game, *, is_admin: bool) -> str:
    head = htpy.head[
        htpy.meta(charset="utf-8"),
        htpy.meta(name="viewport", content="width=device-width, initial-scale=1"),
        htpy.script(type="module", src="https://cdn.jsdelivr.net/gh/starfederation/datastar@v1.0.0/bundles/datastar.js"),
        htpy.title["TI4 Dashboard"],
    ]
    # `now` is a client-side ms clock ticked every second; the timer fragment
    # derives its countdown from `$ends_at - $now`. `data_on_load` opens the SSE
    # stream, which immediately patches the three empty divs below by id.
    shell = htpy.body(
        {"data-on-interval__duration.1s": "$now = Date.now()"},
        data_signals_now="Date.now()",
        data_on_load="@get('/events')",
    )[
        htpy.h1["TI4 Dashboard"],
        htpy.div(id="phasebar")[""],
        htpy.div(id="active-timer")[""],
        htpy.div(id="players")[""],
    ]
    return f"<!doctype html>\n{htpy.html[head, shell]}"
