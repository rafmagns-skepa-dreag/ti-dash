from dataclasses import asdict, fields

from ti_dash.domain.config import TimerConfig
from ti_dash.domain.game import Game
from ti_dash.domain.models import Player

_PLAYER_KEYS = (
    "name",
    "faction",
    "color",
    "seat",
    "vp",
    "strategy_card",
    "passed",
    "claim_token",
)
_GAME_KEYS = (
    "speaker_seat_number",
    "round",
    "vp_goal",
    "phase",
    "awaiting_admin",
    "active",
    "paused",
    "agenda_enabled_this_round",
)


def game_to_dict(game: Game) -> dict:
    return game.to_dict()
    return {
        "config": asdict(game.config),
        "sequence": game._sequence,
    }


def game_from_dict(data: dict) -> Game:
    return Game.from_dict(data)
    g = Game(players=[Player.from_dict(**pd) for pd in data["players"]])
    for k in _GAME_KEYS:
        setattr(g, k, data[k])
    valid = {f.name for f in fields(TimerConfig)}
    g.config = TimerConfig(**{k: v for k, v in data["config"].items() if k in valid})
    g._sequence = data["sequence"]
    return g
