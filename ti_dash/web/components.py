import htpy
from datastar_py.attributes import attribute_generator as d

from ti_dash.domain.game import Game
from ti_dash.domain.reference import Phase, StrategyCard


def _on_click(expression: str) -> dict:
    """Datastar click handler, version-correct for the loaded datastar JS.

    Emitted via the datastar-py attribute generator so the attribute name
    matches the runtime (Datastar v1 uses the `data-on:click` colon form,
    not `data-on-click`).
    """
    return dict(d.on("click", expression))


def _on_submit(expression: str) -> dict:
    """Datastar submit handler with preventDefault, so forms don't navigate."""
    return dict(d.on("submit", expression).prevent)


def _card_picker(game: Game, p) -> htpy.Element | str:
    if game.phase != Phase.Strategy or game.paused:
        return ""
    taken = {pl.strategy_card for pl in game.players if pl.strategy_card is not None}
    if p.strategy_card is None:
        available = [c for c in StrategyCard if c not in taken]
        return htpy.div(class_="card-picker")[
            [
                htpy.button(
                    _on_click(
                        f"@post('/action/pick_card?seat={p.seat}&card={c.value}')"
                    ),
                    class_="pick-card",
                )[c.name]
                for c in available
            ]
        ]
    # Player already holds a card: only admin may reassign or clear it.
    reassignable = [c for c in StrategyCard if c not in taken or c is p.strategy_card]
    return htpy.div(dict(d.show("$isAdmin")), class_="card-picker admin-only")[
        [
            htpy.button(
                _on_click(f"@post('/action/pick_card?seat={p.seat}&card={c.value}')"),
                class_="pick-card",
            )[c.name]
            for c in reassignable
        ],
        htpy.button(
            _on_click(f"@post('/action/unset_card?seat={p.seat}')"),
            class_="unset-card",
        )["Unset"],
    ]


def _turn_controls(game: Game, p) -> htpy.Element | str:
    if game.phase != Phase.Action or game.paused or game.active is None:
        return ""
    if game.current_phase_ordering[game.active].seat != p.seat:
        return ""
    return htpy.div(class_="turn-controls")[
        htpy.button(
            _on_click(f"@post('/action/end_turn?seat={p.seat}')"),
            class_="end-turn",
        )["End Turn"],
        htpy.button(
            _on_click(f"@post('/action/pass_turn?seat={p.seat}')"),
            class_="pass-turn",
        )["Pass"],
    ]


def _status_controls(game: Game, p) -> htpy.Element | str:
    if game.phase != Phase.Status or game.paused or p.passed:
        return ""
    return htpy.div(class_="turn-controls")[
        htpy.button(
            _on_click(f"@post('/action/pass_status?seat={p.seat}')"),
            class_="pass-turn",
        )["Pass"],
    ]


def _vote_controls(game: Game, p) -> htpy.Element | str:
    if game.phase != Phase.Agenda or game.paused or not game.agenda_vote_clock.running:
        return ""
    if game.active is None or game.current_phase_ordering[game.active].seat != p.seat:
        return ""
    return htpy.div(class_="vote-controls")[
        htpy.button(
            _on_click(f"@post('/action/cast_vote?seat={p.seat}')"),
            class_="cast-vote",
        )["Cast Vote"]
    ]


def _admin_pass_toggle(game: Game, p) -> htpy.Element | str:
    if game.phase not in (Phase.Action, Phase.Status) or game.paused:
        return ""
    if p.passed:
        return htpy.button(
            _on_click(f"@post('/action/admin_unpass?seat={p.seat}')"),
            class_="admin-unpass",
        )["Un-pass"]
    return htpy.button(
        _on_click(f"@post('/action/admin_pass?seat={p.seat}')"),
        class_="admin-pass",
    )["Pass"]


def _admin_controls(game: Game, p) -> htpy.Element | str:
    toggle = _admin_pass_toggle(game, p)
    if not toggle:
        return ""
    return htpy.div(dict(d.show("$isAdmin")), class_="admin-controls")[toggle]


def _is_active(game: Game, p) -> bool:
    return (
        game.active is not None
        and game.current_phase_ordering[game.active].seat == p.seat
    )


def player_card(game: Game, p) -> htpy.Element:
    claimed = p.claim_token is not None
    action = "release_seat" if claimed else "claim_seat"
    classes = "player-card active-player" if _is_active(game, p) else "player-card"
    return htpy.div(
        class_=classes,
        data_seat=str(p.seat),
        style=f"border-left-color:{p.color}",
    )[
        htpy.span(class_="swatch", style=f"background:{p.color}")[""],
        htpy.span(class_="name")[p.name],
        htpy.span(class_="speaker-badge")[
            "SPEAKER" if p.seat == game.speaker_seat_number else ""
        ],
        htpy.span(class_="faction")[p.faction],
        htpy.span(class_="vp")[f"VP {p.vp}"],
        htpy.span(class_="card")[p.strategy_card.name if p.strategy_card else "—"],
        htpy.span(class_="passed")["passed" if p.passed else ""],
        htpy.button(
            _on_click(f"@post('/action/{action}?seat={p.seat}')"),
            class_="claim",
        )["Release" if claimed else "Claim"],
        _card_picker(game, p),
        _turn_controls(game, p),
        _status_controls(game, p),
        _vote_controls(game, p),
        _admin_controls(game, p),
    ]
