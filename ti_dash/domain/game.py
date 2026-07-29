from dataclasses import dataclass, field

from ti_dash.domain.clock import Clock
from ti_dash.domain.config import TimerConfig
from ti_dash.domain.models import Player
from ti_dash.domain.records import TurnRecord


@dataclass
class Game:
    players: list[Player] = field(default_factory=list)
    speaker: int = 0
    round: int = 1
    vp_goal: int = 10
    phase: str = "Strategy"
    awaiting_admin: bool = False
    active: int | None = None
    paused: bool = False
    agenda_enabled_this_round: bool = False
    config: TimerConfig = field(default_factory=TimerConfig)
    pending_records: list[TurnRecord] = field(default_factory=list)

    strategy_pick_clock: Clock = field(default_factory=Clock)
    action_clock: Clock = field(default_factory=Clock)
    secondary_clock: Clock = field(default_factory=Clock)
    status_clock: Clock = field(default_factory=Clock)
    agenda_window_clock: Clock = field(default_factory=Clock)
    agenda_vote_clock: Clock = field(default_factory=Clock)

    _sequence: int = 0

    # -- orderings --------------------------------------------------------
    def seating_order(self) -> list[Player]:
        ordered = sorted(self.players, key=lambda p: p.seat)
        if not ordered:
            return ordered
        start = next(i for i, p in enumerate(ordered) if p.seat == self.speaker)
        return ordered[start:] + ordered[:start]

    def initiative_order(self) -> list[Player]:
        return sorted(self.players, key=lambda p: p.initiative)

    # -- construction -----------------------------------------------------
    @classmethod
    def demo(cls) -> "Game":
        g = cls()
        g.players = [
            Player(name="Ana", faction="The Emirates of Hacan", color="Yellow", seat=0),
            Player(name="Bo", faction="The Naalu Collective", color="Green", seat=1),
            Player(name="Cass", faction="The Nomad", color="Blue", seat=2),
            Player(name="Dev", faction="The Winnu", color="Purple", seat=3),
        ]
        return g
