"""F10 — pause button. F11 — admin resets a player's turn timer."""

import pytest

from game import Game


@pytest.fixture
def game() -> Game:
    return Game.demo()


# --- F10: pause ------------------------------------------------------------------


def test_pause_stops_active_turn_clock(game: Game, fake_clock) -> None:
    p = game.players[0]
    game.start_turn(p)
    fake_clock(10.0)

    game.pause()

    assert not p.turn_clock.running
    assert p.turn_clock.banked == 10.0
    assert game.paused is True


def test_resume_restarts_active_turn_clock_without_losing_banked_time(
    game: Game, fake_clock
) -> None:
    p = game.players[0]
    game.start_turn(p)
    fake_clock(10.0)
    game.pause()

    fake_clock(999.0)  # time passing while paused must not count
    game.resume()

    assert p.turn_clock.running
    assert p.turn_clock.elapsed() == 10.0
    fake_clock(5.0)
    assert p.turn_clock.elapsed() == 15.0


def test_pause_is_idempotent(game: Game, fake_clock) -> None:
    p = game.players[0]
    game.start_turn(p)
    fake_clock(10.0)
    game.pause()
    fake_clock(20.0)
    game.pause()  # second call should be a no-op

    assert p.turn_clock.banked == 10.0


def test_score_raises_while_paused(game: Game) -> None:
    p = game.players[0]
    game.pause()
    with pytest.raises(RuntimeError):
        game.score(p, 1)


def test_pause_and_resume_noop_when_already_in_that_state(game: Game) -> None:
    game.resume()  # not paused yet; must not raise or flip state
    assert game.paused is False

    game.pause()
    game.pause()
    assert game.paused is True


# --- F11: admin resets a player's turn timer -----------------------------------------


def test_reset_turn_clock_requires_admin(game: Game) -> None:
    p = game.players[0]
    with pytest.raises(PermissionError):
        game.reset_turn_clock(p, is_admin=False)


def test_reset_turn_clock_on_active_player_restarts_running(
    game: Game, fake_clock
) -> None:
    p = game.players[0]
    game.config.turn_seconds = 180.0
    game.start_turn(p)
    fake_clock(100.0)

    game.reset_turn_clock(p, is_admin=True)

    assert p.turn_clock.running
    assert p.turn_clock.remaining() == 180.0


def test_reset_turn_clock_on_inactive_player_stays_stopped(
    game: Game, fake_clock
) -> None:
    active, other = game.players[0], game.players[1]
    game.start_turn(active)
    fake_clock(10.0)

    game.reset_turn_clock(other, is_admin=True)

    assert not other.turn_clock.running
    assert other.turn_clock.remaining() == game.config.turn_seconds
