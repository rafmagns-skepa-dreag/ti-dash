import htpy

from ti_dash.domain.game import Game
from ti_dash.domain.reference import STRATEGY_CARDS


def player_card(game: Game, p) -> htpy.Element:
    claimed = p.claim_token is not None
    return htpy.div(class_="player-card", data_seat=str(p.seat))[
        htpy.span(class_="swatch", style=f"background:{p.color}")[""],
        htpy.span(class_="name")[p.name],
        htpy.span(class_="faction")[p.faction],
        htpy.span(class_="vp")[f"VP {p.vp}"],
        htpy.span(class_="card")[
            STRATEGY_CARDS[p.strategy_card] if p.strategy_card else "—"
        ],
        htpy.span(class_="passed")["passed" if p.passed else ""],
        htpy.button(
            class_="claim",
            data_on_click=(
                f"@post('/action/release_seat?seat={p.seat}')" if claimed
                else f"@post('/action/claim_seat?seat={p.seat}')"
            ),
        )["Release" if claimed else "Claim"],
    ]
