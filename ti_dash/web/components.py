import htpy
from datastar_py.attributes import attribute_generator as d

from ti_dash.domain.game import Game
from ti_dash.domain.reference import STRATEGY_CARDS


def _on_click(expression: str) -> dict:
    """Datastar click handler, version-correct for the loaded datastar JS.

    Emitted via the datastar-py attribute generator so the attribute name
    matches the runtime (Datastar v1 uses the `data-on:click` colon form,
    not `data-on-click`).
    """
    return dict(d.on("click", expression))


def player_card(game: Game, p) -> htpy.Element:
    claimed = p.claim_token is not None
    action = "release_seat" if claimed else "claim_seat"
    return htpy.div(
        class_="player-card",
        data_seat=str(p.seat),
        style=f"border-left-color:{p.color}",
    )[
        htpy.span(class_="swatch", style=f"background:{p.color}")[""],
        htpy.span(class_="name")[p.name],
        htpy.span(class_="faction")[p.faction],
        htpy.span(class_="vp")[f"VP {p.vp}"],
        htpy.span(class_="card")[
            STRATEGY_CARDS[p.strategy_card] if p.strategy_card else "—"
        ],
        htpy.span(class_="passed")["passed" if p.passed else ""],
        htpy.button(
            _on_click(f"@post('/action/{action}?seat={p.seat}')"),
            class_="claim",
        )["Release" if claimed else "Claim"],
    ]
