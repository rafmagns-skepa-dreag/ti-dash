from dataclasses import dataclass

from ti_dash.domain.reference import Color, Context, Faction, Phase, StrategyCard


@dataclass
class Player:
    name: str
    faction: Faction
    color: Color
    seat: int
    vp: int = 0
    strategy_card: StrategyCard | None = None
    passed: bool = False
    claim_token: str | None = None

    @property
    def initiative(self) -> int:
        return self.strategy_card.value if self.strategy_card is not None else 99


@dataclass
class TurnRecord:
    sequence: int
    round: int
    turn: int | None
    phase: Phase
    context: Context
    player_name: str | None
    seat: int | None
    duration_seconds: float
    over_budget: bool
    ended_at: float
