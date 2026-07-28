"""F14/F15 — end-of-game reports (phase_totals / player_totals), driven
end-to-end through a real Game wired to an in-memory EventStore, the same
way main.py wires game.sink = store.append at startup.
"""

from db import EventStore
from game import Game


def test_multiple_turns_same_player_accumulate_in_report(fake_clock) -> None:
    game = Game()
    game.add_player("Ana", "The Arborec", "Green")
    game.add_player("Bo", "The Winnu", "Purple")
    store = EventStore.in_memory()
    game.sink = store.append
    ana = game.players[0]

    game.start_turn(ana)
    fake_clock(10.0)
    game.next_turn()  # ends Ana's turn, starts Bo's
    fake_clock(5.0)
    game.start_turn(ana)
    fake_clock(7.0)
    game.end_turn()

    totals = store.player_totals()

    assert totals["Ana"] == 17.0
    store.close()


def test_phase_totals_end_to_end_via_game_sink(fake_clock) -> None:
    game = Game()
    store = EventStore.in_memory()
    game.sink = store.append

    game.set_phase("Strategy")
    fake_clock(60.0)
    game.set_phase("Action")
    fake_clock(120.0)
    game.set_phase("Status")

    totals = store.phase_totals()

    assert totals["Strategy"] == 60.0
    assert totals["Action"] == 120.0
    store.close()
