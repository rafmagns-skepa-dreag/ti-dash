import pytest
from litestar.testing import AsyncTestClient
from ti_dash.web.app import create_app


@pytest.fixture
async def client(tmp_path):
    async with AsyncTestClient(app=create_app(str(tmp_path / "t.db"))) as c:
        yield c


async def test_score_requires_owning_the_seat(client):
    await client.get("/")                       # device A cookie
    await client.post("/action/claim_seat", params={"seat": 0})
    # A owns seat 0; scoring seat 0 works
    r = await client.post("/action/score", params={"seat": 0, "delta": 2})
    assert r.status_code in (200, 204)
    page = await client.get("/action/debug_players")
    assert "VP 2" in page.text


async def test_score_unauthorized_is_rejected(client):
    await client.get("/")
    # seat 0 is unclaimed; a device that does not own it cannot score
    r = await client.post("/action/score", params={"seat": 0, "delta": 5})
    assert r.status_code == 403
    page = await client.get("/action/debug_players")
    assert "VP 0" in page.text


async def test_toggle_agenda_flag(client):
    await client.get("/")
    await client.post("/action/admin_logout")   # ensure known state
    r = await client.post("/action/toggle_agenda")
    assert r.status_code in (200, 204)
