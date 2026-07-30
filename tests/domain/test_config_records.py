from ti_dash.domain.config import TimerConfig
from ti_dash.domain.models import TurnRecord
from ti_dash.domain.reference import Context, Phase


def test_config_defaults_and_budget_lookup():
    c = TimerConfig()
    assert c.vp_goal == 10
    assert c.budget_for(Context.ACTION) == c.action_seconds
    assert c.budget_for(Context.AGENDA_VOTE) == c.agenda_vote_seconds


def test_turn_record_fields():
    r = TurnRecord(
        sequence=1,
        round=2,
        turn=3,
        phase=Phase.Action,
        context=Context.ACTION,
        player_name="Ana",
        seat=0,
        duration_seconds=42.5,
        over_budget=False,
        ended_at=123.0,
    )
    assert r.sequence == 1 and r.player_name == "Ana" and r.over_budget is False
