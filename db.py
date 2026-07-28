"""SQLite persistence for ti-dash session events.

stdlib `sqlite3` only, no NiceGUI import — `game.py` stays ignorant of this
module entirely; the two are connected only through the `Game.sink` callable
(see `game.Game.note`). This module is the only place allowed to touch disk.
"""

import json
import sqlite3
import sys
from pathlib import Path

from game import LogEntry

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       REAL    NOT NULL,
    round    INTEGER NOT NULL,
    phase    TEXT    NOT NULL,
    player   TEXT,
    kind     TEXT    NOT NULL,
    payload  TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
"""


class EventStore:
    """Append-only event log backing the F13/F14/F15 audit + report features."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    @classmethod
    def in_memory(cls) -> EventStore:
        """Fast schema/query unit tests that don't need on-disk durability."""
        return cls(":memory:")

    def append(self, entry: LogEntry) -> None:
        """Persist one LogEntry as an INSERT.

        Must never raise into game.py's mutation path — a full disk or a
        closed connection shouldn't crash the dashboard mid-game. Failures
        are logged to stderr instead, keeping game.py fully unaware.
        """
        try:
            self._conn.execute(
                "INSERT INTO events (ts, round, phase, player, kind, payload) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    entry.ts,
                    entry.round,
                    entry.phase,
                    entry.player,
                    entry.kind,
                    json.dumps(entry.payload),
                ),
            )
            self._conn.commit()
        except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
            print(f"EventStore.append failed: {exc}", file=sys.stderr)

    def phase_totals(self, round: int | None = None) -> dict[str, float]:
        """F14 — sums duration of `phase_span` events grouped by phase."""
        query = "SELECT phase, payload FROM events WHERE kind = 'phase_span'"
        params: tuple = ()
        if round is not None:
            query += " AND round = ?"
            params = (round,)
        totals: dict[str, float] = {}
        for phase, payload in self._conn.execute(query, params):
            duration = json.loads(payload).get("duration", 0.0) if payload else 0.0
            totals[phase] = totals.get(phase, 0.0) + duration
        return totals

    def player_totals(self) -> dict[str, float]:
        """F15 — sums duration of `turn_span` events grouped by player."""
        totals: dict[str, float] = {}
        query = "SELECT player, payload FROM events WHERE kind = 'turn_span'"
        for player, payload in self._conn.execute(query):
            if player is None:
                continue
            duration = json.loads(payload).get("duration", 0.0) if payload else 0.0
            totals[player] = totals.get(player, 0.0) + duration
        return totals

    def close(self) -> None:
        self._conn.close()
