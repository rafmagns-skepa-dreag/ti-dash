from dataclasses import dataclass


@dataclass
class TurnRecord:
    sequence: int
    round: int
    turn: int | None
    phase: str
    context: str
    player_name: str | None
    seat: int | None
    duration_seconds: float
    over_budget: bool
    ended_at: float
