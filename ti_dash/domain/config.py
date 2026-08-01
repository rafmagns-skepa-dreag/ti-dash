from dataclasses import dataclass

from ti_dash.domain.models import PlayerType
from ti_dash.domain.reference import BUDGET_FIELDS, Context


@dataclass
class TimerConfig:
    strategy_pick_seconds: float = 120
    action_seconds: float = 300
    secondary_seconds: float = 90
    status_seconds: float = 120.0
    agenda_window_seconds: float = 180.0
    agenda_vote_seconds: float = 90.0
    vp_goal: int = 10

    def budget_for(self, context: Context, player_type: PlayerType) -> float:
        t = getattr(self, BUDGET_FIELDS[context])
        if player_type is not PlayerType.DEFAULT and "action" in str(context).lower():
            t += 60
        return t
