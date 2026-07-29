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


async def test_begin_pick_does_not_500(client):
    """FIX 1: begin_pick should work without TypeError (domain method takes only player)"""
    await client.get("/")  # get device cookie
    r = await client.post("/action/begin_pick", params={"seat": 0})
    assert r.status_code in (200, 204), f"Expected success, got {r.status_code}"


async def test_claim_seat_conflict_returns_403_not_500(client):
    """FIX 2: claim_seat should map PermissionError to 403, not 500"""
    # Device A claims seat 0
    await client.get("/")
    r = await client.post("/action/claim_seat", params={"seat": 0})
    assert r.status_code in (200, 204)
    
    # Device B tries to claim the same seat (different device_id cookie)
    async with AsyncTestClient(app=client.app) as client2:
        await client2.get("/")  # gets its own device_id cookie
        r2 = await client2.post("/action/claim_seat", params={"seat": 0})
        assert r2.status_code == 403, f"Expected 403 for conflict, got {r2.status_code}"
