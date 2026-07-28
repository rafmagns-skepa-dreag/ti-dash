"""F9 — seat claim / unclaim / admin override."""

import pytest

from game import Game


@pytest.fixture
def game() -> Game:
    return Game.demo()


# --- claim / unclaim -----------------------------------------------------------


def test_claim_seat_sets_token(game: Game) -> None:
    p = game.players[0]
    game.claim_seat(p, "device-a")
    assert p.claim_token == "device-a"


def test_claim_seat_twice_same_device_is_idempotent(game: Game) -> None:
    p = game.players[0]
    game.claim_seat(p, "device-a")
    game.claim_seat(p, "device-a")
    assert p.claim_token == "device-a"


def test_claim_seat_by_second_device_raises(game: Game) -> None:
    p = game.players[0]
    game.claim_seat(p, "device-a")
    with pytest.raises(PermissionError):
        game.claim_seat(p, "device-b")


def test_unclaim_seat_requires_owning_device_or_admin(game: Game) -> None:
    p = game.players[0]
    game.claim_seat(p, "device-a")

    with pytest.raises(PermissionError):
        game.unclaim_seat(p, "device-b")

    game.unclaim_seat(p, "device-b", is_admin=True)
    assert p.claim_token is None

    game.claim_seat(p, "device-a")
    game.unclaim_seat(p, "device-a")
    assert p.claim_token is None


# --- authorize -------------------------------------------------------------------


def test_authorize_allows_owning_device(game: Game) -> None:
    p = game.players[0]
    game.claim_seat(p, "device-a")
    game.authorize(p, "device-a")  # must not raise


def test_authorize_allows_admin_for_any_player(game: Game) -> None:
    p = game.players[0]
    game.claim_seat(p, "device-a")
    game.authorize(p, "someone-else", is_admin=True)  # must not raise


def test_authorize_rejects_other_device(game: Game) -> None:
    p = game.players[0]
    game.claim_seat(p, "device-a")
    with pytest.raises(PermissionError):
        game.authorize(p, "device-b")


def test_authorize_allows_unclaimed_seat_with_no_identity(game: Game) -> None:
    """Backward-compat default: an unclaimed seat + no device_id passed
    reproduces pre-F9 behavior (anyone could act), matching T0's baseline
    tests which call mutators without any identity argument."""
    p = game.players[0]
    game.authorize(p)  # must not raise


# --- score is authorization-guarded (F9 applied to an existing mutator) -------------


def test_score_raises_without_authorization(game: Game) -> None:
    p = game.players[0]
    game.claim_seat(p, "device-a")
    with pytest.raises(PermissionError):
        game.score(p, 1, "device-b")


def test_score_allows_owning_device(game: Game) -> None:
    p = game.players[0]
    game.claim_seat(p, "device-a")
    game.score(p, 1, "device-a")
    assert p.vp == 1


def test_score_allows_admin_regardless_of_claim(game: Game) -> None:
    p = game.players[0]
    game.claim_seat(p, "device-a")
    game.score(p, 1, "device-b", is_admin=True)
    assert p.vp == 1


# --- pass_speaker: admin-or-current-speaker -----------------------------------------


def test_pass_speaker_requires_admin_or_current_speaker(game: Game) -> None:
    speaker = game.players[game.speaker]
    game.claim_seat(speaker, "speaker-device")
    target = game.players[1]

    with pytest.raises(PermissionError):
        game.pass_speaker(target, "someone-else", is_admin=False)

    game.pass_speaker(target, "speaker-device", is_admin=False)
    assert game.speaker == game.players.index(target)


def test_pass_speaker_allows_admin(game: Game) -> None:
    game.pass_speaker(game.players[2], "irrelevant-device", is_admin=True)
    assert game.speaker == 2


# --- adjust_counter (this PR's addition covering F9's "counters in player_card") ----


def test_adjust_counter_requires_authorization(game: Game) -> None:
    p = game.players[0]
    game.claim_seat(p, "device-a")
    with pytest.raises(PermissionError):
        game.adjust_counter(p, "trade_goods", 1, "device-b")


def test_adjust_counter_allows_owning_device(game: Game) -> None:
    p = game.players[0]
    game.claim_seat(p, "device-a")
    game.adjust_counter(p, "trade_goods", 3, "device-a")
    assert p.trade_goods == 3


def test_adjust_counter_clamps_at_zero(game: Game) -> None:
    p = game.players[0]
    game.adjust_counter(p, "fleet", -100)
    assert p.fleet == 0


def test_adjust_counter_rejects_unknown_counter(game: Game) -> None:
    p = game.players[0]
    with pytest.raises(ValueError):
        game.adjust_counter(p, "not_a_real_counter", 1)
