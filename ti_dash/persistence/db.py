import json
import time

import aiosqlite

from ti_dash.domain.game import Game
from ti_dash.domain.records import TurnRecord
from ti_dash.persistence.serialize import game_from_dict, game_to_dict

_SCHEMA = """
CREATE TABLE IF NOT EXISTS game_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    snapshot TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS turn_records (
    sequence INTEGER PRIMARY KEY,
    round INTEGER, turn INTEGER, phase TEXT, context TEXT,
    player_name TEXT, seat INTEGER, duration_seconds REAL,
    over_budget INTEGER, ended_at REAL
);
"""


class Database:
    def __init__(self, path: str) -> None:
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self._path)
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()

    async def save_snapshot(self, game: Game) -> None:
        payload = json.dumps(game_to_dict(game))
        await self._conn.execute(
            "INSERT INTO game_state (id, snapshot, updated_at) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET snapshot=excluded.snapshot, "
            "updated_at=excluded.updated_at",
            (payload, time.time()),
        )
        await self._conn.commit()

    async def load_snapshot(self) -> Game | None:
        async with self._conn.execute(
            "SELECT snapshot FROM game_state WHERE id=1"
        ) as cur:
            row = await cur.fetchone()
        return game_from_dict(json.loads(row[0])) if row else None

    async def append_records(self, records: list[TurnRecord]) -> None:
        await self._conn.executemany(
            "INSERT INTO turn_records (sequence, round, turn, phase, context, "
            "player_name, seat, duration_seconds, over_budget, ended_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    r.sequence,
                    r.round,
                    r.turn,
                    r.phase,
                    r.context,
                    r.player_name,
                    r.seat,
                    r.duration_seconds,
                    int(r.over_budget),
                    r.ended_at,
                )
                for r in records
            ],
        )
        await self._conn.commit()

    async def load_records(self) -> list[TurnRecord]:
        async with self._conn.execute(
            "SELECT sequence, round, turn, phase, context, player_name, seat, "
            "duration_seconds, over_budget, ended_at FROM turn_records ORDER BY sequence"
        ) as cur:
            rows = await cur.fetchall()
        return [
            TurnRecord(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], bool(r[8]), r[9])
            for r in rows
        ]

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
