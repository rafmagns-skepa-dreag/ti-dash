"""T0 — regression tests for game.py behavior as it exists today.

These tests intentionally pin down *current* behavior before any refactor
(see SPEC.md §0 / §7). No production code changes accompany this file: if a
later PR changes game.py's shape (e.g. the Clock refactor in F2/F12), these
tests should still pass unmodified, or the change needs to be re-justified.
"""

import pytest

from game import PHASES, STRATEGY_CARDS, Game


@pytest.fixture
def game() -> Game:
    return Game.demo()


# --- Game.demo() -----------------------------------------------------------


def test_demo_creates_expected_players(game: Game) -> None:
    names = [p.name for p in game.players]
    assert names == ["Ana", "Bo", "Cass", "Dev"]
    assert game.players[0].faction == "The Emirates of Hacan"
    assert game.players[0].color == "Yellow"


def test_demo_clears_log_and_starts_at_round_one(game: Game) -> None:
    assert game.log == []
    assert game.round == 1
    assert game.phase == "Strategy"
    assert game.active is None


# --- add_player -------------------------------------------------------------


def test_add_player_appends_player_with_defaults() -> None:
    g = Game()
    g.add_player("Eve", "The Winnu", "Purple")

    assert len(g.players) == 1
    p = g.players[0]
    assert p.name == "Eve"
    assert p.faction == "The Winnu"
    assert p.color == "Purple"
    assert p.vp == 0
    assert p.trade_goods == 0
    assert p.strategy_card is None
    assert p.passed is False
    assert p.banked == 0.0


def test_add_player_logs_join_message() -> None:
    g = Game()
    g.add_player("Eve", "The Winnu", "Purple")

    assert len(g.log) == 1
    assert "Eve joined as The Winnu" in g.log[0]


# --- score -------------------------------------------------------------------


def test_score_increases_vp(game: Game) -> None:
    p = game.players[0]
    game.score(p, 3)
    assert p.vp == 3


def test_score_decreases_vp(game: Game) -> None:
    p = game.players[0]
    game.score(p, 5)
    game.score(p, -2)
    assert p.vp == 3


def test_score_clamps_at_zero(game: Game) -> None:
    p = game.players[0]
    game.score(p, -100)
    assert p.vp == 0


def test_score_clamps_at_vp_goal(game: Game) -> None:
    p = game.players[0]
    game.score(p, 1000)
    assert p.vp == game.vp_goal


def test_score_logs_scored_and_lost_verbs(game: Game) -> None:
    p = game.players[0]
    game.score(p, 2)
    assert "scored 2 VP" in game.log[0]
    game.score(p, -1)
    assert "lost 1 VP" in game.log[0]


# --- assign_card --------------------------------------------------------------


def test_assign_card_sets_players_card(game: Game) -> None:
    p = game.players[0]
    game.assign_card(p, 3)
    assert p.strategy_card == 3


def test_assign_card_logs_card_name(game: Game) -> None:
    p = game.players[0]
    game.assign_card(p, 3)
    assert f"took 3 · {STRATEGY_CARDS[3]}" in game.log[0]


def test_assign_card_steals_from_another_player(game: Game) -> None:
    p1, p2 = game.players[0], game.players[1]
    game.assign_card(p1, 5)
    game.assign_card(p2, 5)

    assert p2.strategy_card == 5
    assert p1.strategy_card is None


def test_assign_card_none_clears_without_take_note(game: Game) -> None:
    p = game.players[0]
    game.assign_card(p, 3)
    log_len_before = len(game.log)
    game.assign_card(p, None)

    assert p.strategy_card is None
    # No new "took" note is logged for clearing a card.
    assert len(game.log) == log_len_before


# --- pass_speaker --------------------------------------------------------------


def test_pass_speaker_updates_speaker_index(game: Game) -> None:
    target = game.players[2]
    game.pass_speaker(target)
    assert game.speaker == 2
    assert game.players[game.speaker] is target


def test_pass_speaker_logs_message(game: Game) -> None:
    target = game.players[1]
    game.pass_speaker(target)
    assert "Bo is now Speaker" in game.log[0]


# --- start_turn / end_turn / elapsed --------------------------------------------


def test_start_turn_sets_active_player(game: Game, fake_clock) -> None:
    p = game.players[0]
    game.start_turn(p)
    assert game.active == 0
    assert game.turn_started == 0.0


def test_elapsed_accumulates_while_active(game: Game, fake_clock) -> None:
    p = game.players[0]
    game.start_turn(p)
    fake_clock(12.0)
    assert game.elapsed(p) == 12.0


def test_only_active_players_clock_runs(game: Game, fake_clock) -> None:
    p1, p2 = game.players[0], game.players[1]
    game.start_turn(p1)
    fake_clock(30.0)

    assert game.elapsed(p1) == 30.0
    assert game.elapsed(p2) == 0.0


def test_end_turn_banks_elapsed_time(game: Game, fake_clock) -> None:
    p = game.players[0]
    game.start_turn(p)
    fake_clock(45.0)
    game.end_turn()

    assert p.banked == 45.0
    assert game.active is None
    assert game.turn_started is None


def test_banked_time_accumulates_across_turns(game: Game, fake_clock) -> None:
    p = game.players[0]
    game.start_turn(p)
    fake_clock(10.0)
    game.end_turn()
    assert p.banked == 10.0

    game.start_turn(p)
    fake_clock(5.0)
    assert game.elapsed(p) == 15.0

    game.end_turn()
    assert p.banked == 15.0


def test_start_turn_ends_previous_active_players_turn(game: Game, fake_clock) -> None:
    p1, p2 = game.players[0], game.players[1]
    game.start_turn(p1)
    fake_clock(20.0)
    game.start_turn(p2)

    assert p1.banked == 20.0
    assert game.active == 1


# --- next_turn ------------------------------------------------------------------


def test_next_turn_starts_first_player_when_none_active(game: Game, fake_clock) -> None:
    game.next_turn()
    assert game.active == 0


def test_next_turn_advances_to_next_unpassed_in_initiative_order(
    game: Game, fake_clock
) -> None:
    game.start_turn(game.players[0])
    game.next_turn()
    assert game.active == 1


def test_next_turn_skips_passed_players(game: Game, fake_clock) -> None:
    game.players[1].passed = True
    game.start_turn(game.players[0])
    game.next_turn()
    assert game.active == 2


def test_next_turn_wraps_around(game: Game, fake_clock) -> None:
    game.start_turn(game.players[-1])
    game.next_turn()
    assert game.active == 0


def test_next_turn_ends_turn_when_everyone_passed(game: Game, fake_clock) -> None:
    for p in game.players:
        p.passed = True
    game.start_turn(game.players[0])
    fake_clock(7.0)

    game.next_turn()

    assert game.active is None
    assert game.turn_started is None
    assert game.players[0].banked == 7.0


# --- toggle_pass -----------------------------------------------------------------


def test_toggle_pass_flips_passed_flag(game: Game) -> None:
    p = game.players[0]
    game.toggle_pass(p)
    assert p.passed is True
    game.toggle_pass(p)
    assert p.passed is False


def test_toggle_pass_logs_passed_and_un_passed(game: Game) -> None:
    p = game.players[0]
    game.toggle_pass(p)
    assert "Ana passed" in game.log[0]
    game.toggle_pass(p)
    assert "Ana un-passed" in game.log[0]


def test_toggle_pass_auto_advances_off_the_passing_active_player(
    game: Game, fake_clock
) -> None:
    p0 = game.players[0]
    game.start_turn(p0)

    game.toggle_pass(p0)

    assert p0.passed is True
    assert game.active == 1


def test_toggle_pass_on_non_active_player_does_not_change_active(
    game: Game, fake_clock
) -> None:
    game.start_turn(game.players[0])
    game.toggle_pass(game.players[2])

    assert game.active == 0
    assert game.players[2].passed is True


# --- set_phase / advance_phase ------------------------------------------------


def test_set_phase_updates_phase_and_logs(game: Game) -> None:
    game.set_phase("Action")
    assert game.phase == "Action"
    assert "Action phase" in game.log[0]


def test_set_phase_ends_turn_when_leaving_action(game: Game, fake_clock) -> None:
    game.start_turn(game.players[0])
    fake_clock(5.0)

    game.set_phase("Status")

    assert game.active is None
    assert game.players[0].banked == 5.0


def test_set_phase_does_not_end_turn_when_entering_action(
    game: Game, fake_clock
) -> None:
    game.set_phase("Action")
    game.start_turn(game.players[0])
    game.set_phase("Action")
    assert game.active == 0


def test_advance_phase_cycles_strategy_to_action_and_starts_first_turn(
    game: Game, fake_clock
) -> None:
    assert game.phase == "Strategy"
    game.advance_phase()
    assert game.phase == "Action"
    assert game.active == 0


def test_advance_phase_from_agenda_starts_new_round(game: Game, fake_clock) -> None:
    game.set_phase("Agenda")
    assert game.round == 1

    game.advance_phase()

    assert game.round == 2
    assert game.phase == "Strategy"


# --- new_round --------------------------------------------------------------------


def test_new_round_clears_strategy_cards_and_passed_flags(
    game: Game, fake_clock
) -> None:
    for i, p in enumerate(game.players):
        game.assign_card(p, i + 1)
        p.passed = True
    game.start_turn(game.players[0])

    game.new_round()

    assert game.round == 2
    assert game.phase == "Strategy"
    assert game.active is None
    for p in game.players:
        assert p.strategy_card is None
        assert p.passed is False


def test_new_round_logs_message(game: Game) -> None:
    game.new_round()
    assert "New round begins" in game.log[0]
