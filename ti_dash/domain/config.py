from dataclasses import dataclass

from ti_dash.domain.reference import BUDGET_FIELDS, Context


@dataclass
class TimerConfig:
    strategy_pick_seconds: float = 60.0
    action_seconds: float = 180.0
    secondary_seconds: float = 60.0
    status_seconds: float = 120.0
    agenda_window_seconds: float = 60.0
    agenda_vote_seconds: float = 90.0
    vp_goal: int = 10

    def budget_for(self, context: Context) -> float:
        return getattr(self, BUDGET_FIELDS[context])
