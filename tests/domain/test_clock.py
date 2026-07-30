import time

from ti_dash.domain.clock import Clock


def test_new_clock_is_stopped_and_empty():
    c = Clock()
    assert c.running is False
    assert c.elapsed() == 0.0
    assert c.remaining() is None  # no duration => stopwatch


def test_elapsed_advances_while_running(monkeypatch):
    t = [100.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    c = Clock()
    c.start()
    t[0] = 105.0
    assert c.elapsed() == 5.0
    assert c.running is True


def test_stop_banks_running_time_and_resume_continues(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    c = Clock()
    c.start()  # started_at=0
    t[0] = 90.0
    c.stop()  # banked=90
    assert c.running is False
    assert c.elapsed() == 90.0
    t[0] = 200.0  # time passes while stopped; must not count
    assert c.elapsed() == 90.0
    c.start()  # resume at 200
    t[0] = 210.0
    assert c.elapsed() == 100.0  # 90 banked + 10 live


def test_start_is_noop_if_already_running(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    c = Clock()
    c.start()
    t[0] = 5.0
    c.start()  # must not reset started_at
    t[0] = 10.0
    assert c.elapsed() == 10.0


def test_remaining_goes_negative_past_budget(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    c = Clock(duration=60.0)
    c.start()
    t[0] = 100.0
    assert c.remaining() == -40.0


def test_reset_clears_bank_and_sets_duration(monkeypatch):
    t = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    c = Clock(duration=60.0)
    c.start()
    t[0] = 30.0
    c.reset(120.0)
    assert c.banked == 0.0
    assert c.running is False
    assert c.duration == 120.0
    assert c.remaining() == 120.0
