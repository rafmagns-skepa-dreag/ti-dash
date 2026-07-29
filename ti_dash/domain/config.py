from dataclasses import dataclass

_BUDGET_FIELDS = {
    "strategy_pick": "strategy_pick_seconds",
    "action": "action_seconds",
    "secondary": "secondary_seconds",
    "status": "status_seconds",
    "agenda_window": "agenda_window_seconds",
    "agenda_vote": "agenda_vote_seconds",
}


@dataclass
class TimerConfig:
    strategy_pick_seconds: float = 60.0
    action_seconds: float = 180.0
    secondary_seconds: float = 60.0
    status_seconds: float = 120.0
    agenda_window_seconds: float = 60.0
    agenda_vote_seconds: float = 90.0
    vp_goal: int = 10
    admin_password: str = "password"

    def budget_for(self, context: str) -> float:
        return getattr(self, _BUDGET_FIELDS[context])
