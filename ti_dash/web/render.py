import time

import htpy
from datastar_py.attributes import attribute_generator as d

from ti_dash.domain.game import Game
from ti_dash.web.components import _on_click, player_card

DATASTAR_SRC = (
    "https://cdn.jsdelivr.net/gh/starfederation/datastar@v1.0.0/bundles/datastar.js"
)


def _active_ends_at_ms(game: Game) -> int:
    clock = game.active_clock()
    if clock is None or clock.remaining() is None:
        return 0
    return int((time.time() + clock.remaining()) * 1000)


def timer_fragment(game: Game) -> str:
    running = game.active_clock() is not None
    # Signals are declared as a single `data-signals` JSON object (endsAt is
    # camelCase so it survives verbatim into the JS signal namespace), and the
    # countdown is derived client-side from the ticking global `now` signal.
    node = htpy.div(
        dict(
            d.signals(
                endsAt=_active_ends_at_ms(game),
                running=running,
                paused=game.paused,
            )
        ),
        dict(
            d.text("$running ? Math.round(($endsAt - $now)/1000) + 's' : '--'")
        ),
        id="active-timer",
    )[""]
    return str(node)


def players_fragment(game: Game) -> str:
    return str(htpy.div(id="players")[[player_card(game, p) for p in game.players]])


def phasebar_fragment(game: Game) -> str:
    active = game.players[game.active].name if game.active is not None else "—"
    gate = (
        htpy.button(_on_click("@post('/action/advance')"), class_="gate")[
            "Start next phase"
        ]
        if game.awaiting_admin
        else ""
    )
    pause_label = "Resume" if game.paused else "Pause"
    return str(
        htpy.div(id="phasebar")[
            htpy.span[f"Round {game.round}"],
            htpy.span[f"Phase: {game.phase}"],
            htpy.span[f"Active: {active}"],
            htpy.span[f"Paused: {game.paused}"],
            htpy.button(_on_click("@post('/action/toggle_pause')"), class_="pause")[
                pause_label
            ],
            gate,
        ]
    )


def full_page(game: Game, *, is_admin: bool) -> str:
    head = htpy.head[
        htpy.meta(charset="utf-8"),
        htpy.meta(name="viewport", content="width=device-width, initial-scale=1"),
        htpy.link(rel="stylesheet", href="/app.css"),
        htpy.script(type="module", src=DATASTAR_SRC),
        htpy.title["TI4 Dashboard"],
    ]
    # `now` is a client-side ms clock ticked every second (data-on-interval
    # defaults to 1s). `data-init` runs once when Datastar initializes this
    # element, opening the SSE stream that patches the three empty divs below.
    shell = htpy.body(
        dict(d.init("@get('/events')")),
        dict(d.signals(now="Date.now()")),
        dict(d.on_interval("$now = Date.now()")),
    )[
        htpy.h1["TI4 Dashboard"],
        htpy.div(id="phasebar")[""],
        htpy.div(id="active-timer")[""],
        htpy.div(id="players")[""],
    ]
    return str(htpy.html[head, shell])
