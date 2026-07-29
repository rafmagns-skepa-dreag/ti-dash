from dataclasses import dataclass


@dataclass
class Player:
    name: str
    faction: str
    color: str
    seat: int
    vp: int = 0
    strategy_card: int | None = None
    passed: bool = False
    claim_token: str | None = None

    @property
    def initiative(self) -> int:
        return self.strategy_card if self.strategy_card is not None else 99
