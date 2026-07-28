"""Clock primitive (F2/F12) plus turn/secondary/status/agenda clocks (F5/F7/F8)."""

import pytest

from game import Clock, Game, TimerConfig


@pytest.fixture
def game() -> Game:
    return Game.demo()


# --- Clock (F2) ---------------------------------------------------------------


def test_clock_remaining_none_without_duration() -> None:
    clock = Clock()
    clock.start()
    assert clock.remaining() is None


def test_clock_remaining_counts_down(fake_clock) -> None:
    clock = Clock(duration=100.0)
    clock.start()
    fake_clock(30.0)
    assert clock.remaining() == 70.0


def test_clock_remaining_goes_negative_past_expiry(fake_clock) -> None:
    clock = Clock(duration=10.0)
    clock.start()
    fake_clock(15.0)
    assert clock.remaining() == -5.0


def test_clock_stop_start_preserves_banked_time(fake_clock) -> None:
    clock = Clock(duration=100.0)
    clock.start()
    fake_clock(10.0)
    clock.stop()
    assert clock.banked == 10.0
    assert not clock.running

    fake_clock(999.0)  # time passing while stopped must not count
    assert clock.elapsed() == 10.0

    clock.start()
    fake_clock(5.0)
    assert clock.elapsed() == 15.0


def test_clock_reset_clears_banked_and_stops(fake_clock) -> None:
    clock = Clock(duration=100.0)
    clock.start()
    fake_clock(10.0)
    clock.stop()

    clock.reset(50.0)

    assert clock.banked == 0.0
    assert clock.started_at is None
    assert not clock.running
    assert clock.duration == 50.0
    assert clock.elapsed() == 0.0


def test_clock_start_is_a_noop_when_already_running(fake_clock) -> None:
    clock = Clock()
    clock.start()
    started_at = clock.started_at
    fake_clock(5.0)
    clock.start()
    assert clock.started_at == started_at


def test_bare_clock_defaults_to_stopped_zero_banked_no_duration() -> None:
    clock = Clock()
    assert clock.duration is None
    assert clock.banked == 0.0
    assert clock.started_at is None
    assert not clock.running


# --- F12: turn clock is per-turn ------------------------------------------------


def test_start_turn_always_resets_duration_to_current_config(
    game: Game, fake_clock
) -> None:
    game.config.turn_seconds = 42.0
    game.start_turn(game.players[0])
    assert game.players[0].turn_clock.duration == 42.0
    assert game.players[0].turn_clock.remaining() == 42.0


def test_changing_config_mid_turn_does_not_resize_running_clock(
    game: Game, fake_clock
) -> None:
    game.config.turn_seconds = 100.0
    game.start_turn(game.players[0])

    game.config.turn_seconds = 999.0

    assert game.players[0].turn_clock.duration == 100.0


# --- F5: secondary strategy action timer ----------------------------------------


def test_start_secondary_creates_running_clock_with_configured_duration(
    game: Game,
) -> None:
    game.config.secondary_seconds = 45.0
    game.start_secondary()

    assert game.secondary_clock is not None
    assert game.secondary_clock.duration == 45.0
    assert game.secondary_clock.running


def test_clear_secondary_resets_to_none(game: Game) -> None:
    game.start_secondary()
    game.clear_secondary()
    assert game.secondary_clock is None


def test_secondary_clock_independent_of_turn_clock(game: Game, fake_clock) -> None:
    game.start_turn(game.players[0])
    fake_clock(5.0)

    game.start_secondary()

    assert game.players[0].turn_clock.running
    assert game.players[0].turn_clock.elapsed() == 5.0
    assert game.secondary_clock.elapsed() == 0.0


# --- F7: status phase timer per person -------------------------------------------


def test_start_status_clock_creates_and_starts_per_player(game: Game) -> None:
    game.config.status_phase_seconds = 33.0
    p = game.players[0]

    game.start_status_clock(p)

    clock = game.status_clocks[p.name]
    assert clock.duration == 33.0
    assert clock.running


def test_stop_status_clock_bank_time(game: Game, fake_clock) -> None:
    p = game.players[0]
    game.start_status_clock(p)
    fake_clock(20.0)

    game.stop_status_clock(p)

    clock = game.status_clocks[p.name]
    assert not clock.running
    assert clock.banked == 20.0


def test_status_clocks_cleared_on_new_round(game: Game) -> None:
    game.start_status_clock(game.players[0])
    game.new_round()
    assert game.status_clocks == {}


def test_status_clock_independent_per_player(game: Game, fake_clock) -> None:
    ana, bo = game.players[0], game.players[1]
    game.start_status_clock(ana)
    fake_clock(10.0)
    game.start_status_clock(bo)

    assert game.status_clocks[ana.name].elapsed() == 10.0
    assert game.status_clocks[bo.name].elapsed() == 0.0


# --- F8: agenda phase timers --------------------------------------------------------


def test_start_agenda_reveal_creates_running_clock(game: Game) -> None:
    game.config.agenda_reveal_seconds = 15.0
    game.start_agenda_reveal()

    assert game.agenda_clock is not None
    assert game.agenda_clock.duration == 15.0
    assert game.agenda_clock.running


def test_start_agenda_vote_reuses_per_player_clock_slot(game: Game) -> None:
    game.config.agenda_vote_seconds = 77.0
    p = game.players[0]

    game.start_agenda_vote(p)

    assert p.name in game.status_clocks
    clock = game.status_clocks[p.name]
    assert clock.duration == 77.0
    assert clock.running


def test_agenda_clocks_cleared_on_new_round(game: Game) -> None:
    game.start_agenda_reveal()
    game.start_agenda_vote(game.players[0])

    game.new_round()

    assert game.agenda_clock is None
    assert game.status_clocks == {}
