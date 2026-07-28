"""F16 — TimerConfig and Game.update_config."""

import pytest

from game import Game


@pytest.fixture
def game() -> Game:
    return Game.demo()


def test_update_config_requires_admin(game: Game) -> None:
    with pytest.raises(PermissionError):
        game.update_config(False, turn_seconds=60.0)


def test_update_config_applies_all_given_fields(game: Game) -> None:
    game.update_config(True, turn_seconds=60.0, secondary_seconds=30.0, warn_at=(20.0,))

    assert game.config.turn_seconds == 60.0
    assert game.config.secondary_seconds == 30.0
    assert game.config.warn_at == (20.0,)


def test_update_config_rejects_unknown_field(game: Game) -> None:
    with pytest.raises(ValueError):
        game.update_config(True, not_a_real_field=1)


def test_update_config_logs_config_change(game: Game) -> None:
    game.update_config(True, turn_seconds=60.0)
    assert game.log[0].kind == "config_change"
    assert game.log[0].payload == {"turn_seconds": 60.0}
