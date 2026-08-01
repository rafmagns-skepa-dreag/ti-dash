import time

import htpy
from datastar_py.attributes import attribute_generator as d

from ti_dash.domain.game import Game
from ti_dash.domain.reference import Phase
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
        dict(d.text("$running ? Math.round(($endsAt - $now)/1000) + 's' : '--'")),
        dict(d.class_(overtime="$running && $endsAt - $now < 0")),
        id="active-timer",
    )[""]
    return str(node)


def players_fragment(game: Game) -> str:
    return str(
        htpy.div(id="players")[
            [player_card(game, p) for p in game.current_phase_ordering]
        ]
    )


def speaker_modal_fragment(game: Game) -> str:
    choices = [
        htpy.button(
            _on_click(
                f"@post('/action/set_speaker?seat={p.seat}'); "
                "$speakerModalOpen = false"
            ),
            class_="speaker-choice",
        )[f"{p.name} (Speaker)" if p.seat == game.speaker_seat_number else p.name]
        for p in game.players
    ]
    return str(
        htpy.div(
            dict(d.show("$speakerModalOpen")),
            id="speaker-modal",
            class_="modal-backdrop",
        )[
            htpy.div(class_="modal")[
                htpy.h2["Choose speaker"],
                htpy.div(class_="modal-list")[choices],
                htpy.button(
                    _on_click("$speakerModalOpen = false"), class_="modal-close"
                )["Cancel"],
            ]
        ]
    )


def admin_bar() -> htpy.Element:
    button = htpy.button(
        _on_click(
            "@post($isAdmin ? '/action/admin_logout' : '/action/admin_login')"
        ),
        dict(d.text("$isAdmin ? 'Admin: On' : 'Admin: Off'")),
        dict(d.class_({"is-on": "$isAdmin"})),
        class_="admin-toggle",
    )
    return htpy.div(id="admin-bar")[button]


def _phase_controls(game: Game) -> list:
    if game.awaiting_admin:
        return []
    match game.phase:
        case Phase.Status:
            return [
                htpy.button(
                    _on_click("@post('/action/end_status_phase')"), class_="gate"
                )["End status phase"]
            ]
        case Phase.Agenda:
            window_button = (
                htpy.button(
                    _on_click("@post('/action/close_agenda_window')"), class_="gate"
                )["Close agenda window"]
                if game.agenda_window_clock.running
                else htpy.button(
                    _on_click("@post('/action/open_agenda_window')"), class_="gate"
                )["Open agenda window"]
            )
            vote_button = (
                ""
                if game.agenda_vote_clock.running
                else htpy.button(
                    _on_click("@post('/action/begin_vote')"), class_="gate"
                )["Begin vote"]
            )
            return [
                window_button,
                vote_button,
                htpy.button(
                    _on_click("@post('/action/end_agenda_phase')"), class_="gate"
                )["End agenda phase"],
            ]
        case _:
            return []


def phasebar_fragment(game: Game) -> str:
    active = (
        game.current_phase_ordering[game.active].name
        if game.active is not None
        else "—"
    )
    gate = (
        htpy.button(_on_click("@post('/action/advance')"), class_="gate")[
            "Start next phase"
        ]
        if game.awaiting_admin
        else ""
    )
    agenda_label = "Disable agenda" if game.agenda_enabled_this_round else "Enable agenda"
    pause_label = "Resume" if game.paused else "Pause"
    return str(
        htpy.div(id="phasebar")[
            htpy.span[f"Round {game.round}"],
            htpy.span[f"Phase: {game.phase.name}"],
            htpy.span[f"Active: {active}"],
            htpy.span[f"Paused: {game.paused}"],
            htpy.button(_on_click("@post('/action/toggle_pause')"), class_="pause")[
                pause_label
            ],
            htpy.button(
                _on_click("@post('/action/toggle_agenda')"), class_="toggle-agenda"
            )[agenda_label],
            htpy.button(
                _on_click("$speakerModalOpen = true"), class_="change-speaker"
            )["Change speaker"],
            _phase_controls(game),
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
        dict(
            d.signals(
                now="Date.now()",
                speakerModalOpen=False,
                isAdmin=is_admin,
            )
        ),
        dict(d.on_interval("$now = Date.now()")),
    )[
        htpy.h1["TI4 Dashboard"],
        admin_bar(),
        htpy.div(id="phasebar")[""],
        htpy.div(id="active-timer")[""],
        htpy.div(id="players")[""],
        htpy.div(id="speaker-modal")[""],
    ]
    return str(htpy.html[head, shell])
