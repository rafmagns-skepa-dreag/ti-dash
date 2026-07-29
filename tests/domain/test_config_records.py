from ti_dash.domain.config import TimerConfig
from ti_dash.domain.records import TurnRecord


def test_config_defaults_and_budget_lookup():
    c = TimerConfig()
    assert c.vp_goal == 10
    assert c.budget_for("action") == c.action_seconds
    assert c.budget_for("agenda_vote") == c.agenda_vote_seconds


def test_budget_for_unknown_context_raises():
    import pytest
    with pytest.raises(KeyError):
        TimerConfig().budget_for("nope")


def test_turn_record_fields():
    r = TurnRecord(
        sequence=1, round=2, turn=3, phase="Action", context="action",
        player_name="Ana", seat=0, duration_seconds=42.5,
        over_budget=False, ended_at=123.0,
    )
    assert r.sequence == 1 and r.player_name == "Ana" and r.over_budget is False
