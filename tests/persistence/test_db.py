import pytest
from ti_dash.domain.game import Game
from ti_dash.domain.records import TurnRecord
from ti_dash.persistence.db import Database


@pytest.fixture
async def db(tmp_path):
    d = Database(str(tmp_path / "t.db"))
    await d.connect()
    yield d
    await d.close()


async def test_connect_creates_tables_and_empty_snapshot(db):
    assert await db.load_snapshot() is None
    assert await db.load_records() == []


async def test_save_and_load_snapshot(db):
    g = Game()
    g.add_player("Ana", "The Nomad", "Red")
    g.round = 4
    await db.save_snapshot(g)
    loaded = await db.load_snapshot()
    assert loaded.round == 4
    assert loaded.players[0].name == "Ana"


async def test_snapshot_is_single_row_upsert(db):
    g = Game(); g.round = 1
    await db.save_snapshot(g)
    g.round = 2
    await db.save_snapshot(g)
    loaded = await db.load_snapshot()
    assert loaded.round == 2


async def test_append_and_load_records(db):
    recs = [
        TurnRecord(1, 1, 0, "Action", "action", "Ana", 0, 30.0, False, 100.0),
        TurnRecord(2, 1, 1, "Action", "action", "Bo", 1, 200.0, True, 160.0),
    ]
    await db.append_records(recs)
    loaded = await db.load_records()
    assert [r.sequence for r in loaded] == [1, 2]
    assert loaded[1].over_budget is True


async def test_reconnect_keeps_records_and_snapshot(tmp_path):
    path = str(tmp_path / "t.db")
    d1 = Database(path); await d1.connect()
    g = Game(); g.round = 9; await d1.save_snapshot(g)
    await d1.append_records([TurnRecord(1, 9, 0, "Action", "action", "Ana", 0, 5.0, False, 1.0)])
    await d1.close()
    d2 = Database(path); await d2.connect()
    assert (await d2.load_snapshot()).round == 9
    assert len(await d2.load_records()) == 1
    await d2.close()
