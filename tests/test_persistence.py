"""F13 — SQLite persistence of all actions (db.py), using tmp_path.

`test_game_sink_receives_every_mutation` is the one test that must survive
any future refactor of either game.py or db.py (see SPEC.md §5): it proves
game.py can drive persistence through nothing but the `sink` callable, with
no import of db.py inside game.py.
"""

import sqlite3

import pytest

from db import EventStore
from game import Game, LogEntry


def test_event_store_creates_db_file_and_schema(tmp_path) -> None:
    path = tmp_path / "events.db"
    store = EventStore(path)

    assert path.exists()
    tables = {
        row[0]
        for row in sqlite3.connect(path).execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert "events" in tables
    store.close()


def test_append_persists_row_with_expected_columns(tmp_path) -> None:
    store = EventStore(tmp_path / "events.db")
    entry = LogEntry(
        round=2, phase="Action", text="Ana scored 1 VP", kind="note", player="Ana"
    )

    store.append(entry)

    row = store._conn.execute(
        "SELECT round, phase, player, kind, payload FROM events"
    ).fetchone()
    assert row == (2, "Action", "Ana", "note", "{}")
    store.close()


def test_append_survives_reopen(tmp_path) -> None:
    path = tmp_path / "events.db"
    store = EventStore(path)
    store.append(LogEntry(round=1, phase="Strategy", text="hello", kind="note"))
    store.close()

    reopened = EventStore(path)
    rows = reopened._conn.execute("SELECT kind FROM events").fetchall()
    assert rows == [("note",)]
    reopened.close()


def test_phase_totals_sums_phase_span_events_by_phase() -> None:
    store = EventStore.in_memory()
    store.append(
        LogEntry(
            round=1,
            phase="Strategy",
            text="x",
            kind="phase_span",
            payload={"duration": 30.0},
        )
    )
    store.append(
        LogEntry(
            round=1,
            phase="Action",
            text="x",
            kind="phase_span",
            payload={"duration": 10.0},
        )
    )
    store.append(
        LogEntry(
            round=2,
            phase="Action",
            text="x",
            kind="phase_span",
            payload={"duration": 20.0},
        )
    )
    store.append(
        LogEntry(round=1, phase="Action", text="x", kind="note")
    )  # not a phase_span

    totals = store.phase_totals()

    assert totals == {"Strategy": 30.0, "Action": 30.0}
    store.close()


def test_phase_totals_can_be_scoped_to_a_round() -> None:
    store = EventStore.in_memory()
    store.append(
        LogEntry(
            round=1,
            phase="Action",
            text="x",
            kind="phase_span",
            payload={"duration": 10.0},
        )
    )
    store.append(
        LogEntry(
            round=2,
            phase="Action",
            text="x",
            kind="phase_span",
            payload={"duration": 20.0},
        )
    )

    assert store.phase_totals(round=1) == {"Action": 10.0}
    store.close()


def test_player_totals_sums_turn_span_events_by_player() -> None:
    store = EventStore.in_memory()
    store.append(
        LogEntry(
            round=1,
            phase="Action",
            text="x",
            kind="turn_span",
            player="Ana",
            payload={"duration": 15.0},
        )
    )
    store.append(
        LogEntry(
            round=1,
            phase="Action",
            text="x",
            kind="turn_span",
            player="Ana",
            payload={"duration": 5.0},
        )
    )
    store.append(
        LogEntry(
            round=1,
            phase="Action",
            text="x",
            kind="turn_span",
            player="Bo",
            payload={"duration": 8.0},
        )
    )

    totals = store.player_totals()

    assert totals == {"Ana": 20.0, "Bo": 8.0}
    store.close()


def test_append_failure_does_not_raise(tmp_path) -> None:
    store = EventStore(tmp_path / "events.db")
    store.close()  # break the connection so the next append() fails internally

    store.append(
        LogEntry(round=1, phase="Strategy", text="should not raise", kind="note")
    )


def test_game_sink_receives_every_mutation() -> None:
    game = Game()
    events: list[LogEntry] = []
    game.sink = events.append

    game.add_player("Ana", "The Arborec", "Green")
    p = game.players[0]
    game.claim_seat(p, "device-a")
    game.score(p, 3, "device-a")
    game.assign_card(p, 1, "device-a")
    game.pass_speaker(p, "device-a")
    game.toggle_pass(p, "device-a")
    game.pause()
    game.resume()

    kinds = [e.kind for e in events]
    assert kinds == [
        "note",  # add_player
        "claim_seat",
        "note",  # score
        "note",  # assign_card
        "note",  # pass_speaker
        "note",  # toggle_pass
        "pause",
        "resume",
    ]
