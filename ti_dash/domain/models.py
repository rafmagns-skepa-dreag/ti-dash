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
        if self.faction is Faction.NAALU:
            return 0
        return self.strategy_card.value if self.strategy_card is not None else 99

    def to_dict(self):
        return {
            "name": self.name,
            "faction": self.faction.value,
            "color": self.color.name,
            "seat": self.seat,
            "vp": self.vp,
            "strategy_card": self.strategy_card.name if self.strategy_card else None,
            "passed": self.passed,
            "claim_token": self.claim_token,
        }

    @staticmethod
    def from_dict(
        name: str,
        faction: str,
        color: str,
        seat: int,
        vp: int,
        strategy_card: str | None,
        passed: bool,
        claim_token: str | None,
    ):
        parsed_faction = Faction(faction)
        parsed_color = Color[color]
        parsed_card = StrategyCard[strategy_card] if strategy_card is not None else None
        return Player(
            name,
            parsed_faction,
            parsed_color,
            seat,
            vp,
            parsed_card,
            passed,
            claim_token,
        )


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
