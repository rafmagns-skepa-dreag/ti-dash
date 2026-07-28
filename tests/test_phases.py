"""F6 (auto-advance Action -> Status), F14 (phase spans), F15 (turn spans)."""

import pytest

from game import Game


@pytest.fixture
def game() -> Game:
    return Game.demo()


# --- F6: auto-advance Action -> Status when all pass ------------------------------


def test_last_player_passing_advances_to_status_phase(game: Game, fake_clock) -> None:
    game.set_phase("Action")
    for p in game.players:
        p.passed = True

    game.next_turn()

    assert game.phase == "Status"
    assert game.active is None


def test_passing_during_non_action_phase_does_not_advance(game: Game, fake_clock) -> None:
    assert game.phase == "Strategy"
    game.toggle_pass(game.players[0])
    assert game.phase == "Strategy"


def test_all_pass_then_new_round_resets_passed_flags(game: Game, fake_clock) -> None:
    game.set_phase("Action")
    for p in game.players:
        p.passed = True
    game.next_turn()
    assert game.phase == "Status"

    game.set_phase("Agenda")
    game.new_round()

    assert game.phase == "Strategy"
    for p in game.players:
        assert p.passed is False


# --- F14: time spent per phase, end of game -----------------------------------------


def test_set_phase_emits_phase_span_for_outgoing_phase(game: Game, fake_clock) -> None:
    game.set_phase("Action")
    fake_clock(30.0)

    events: list = []
    game.sink = events.append
    game.set_phase("Status")

    spans = [e for e in events if e.kind == "phase_span"]
    assert len(spans) == 1
    assert spans[0].payload["duration"] == 30.0
    assert "Action" in spans[0].text


def test_set_phase_does_not_emit_span_on_first_call(fake_clock) -> None:
    game = Game()
    events: list = []
    game.sink = events.append

    game.set_phase("Action")

    assert all(e.kind != "phase_span" for e in events)


def test_phase_clock_restarts_on_every_phase_change(game: Game, fake_clock) -> None:
    game.set_phase("Action")
    fake_clock(10.0)
    game.set_phase("Status")

    assert game.phase_clock.elapsed() == 0.0
    assert game.phase_clock.running


# --- F15: time spent per player, end of game ----------------------------------------


def test_end_turn_emits_turn_span_with_player_name(game: Game, fake_clock) -> None:
    p = game.players[0]
    game.start_turn(p)
    fake_clock(20.0)

    events: list = []
    game.sink = events.append
    game.end_turn()

    spans = [e for e in events if e.kind == "turn_span"]
    assert len(spans) == 1
    assert spans[0].player == p.name
    assert spans[0].payload["duration"] == 20.0
    assert spans[0].silent is True


def test_end_turn_with_no_active_player_emits_nothing(game: Game) -> None:
    events: list = []
    game.sink = events.append

    game.end_turn()

    assert events == []
