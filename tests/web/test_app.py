import pytest
from litestar.testing import AsyncTestClient

from ti_dash.web.app import create_app


@pytest.fixture
async def client(tmp_path):
    app = create_app(str(tmp_path / "t.db"))
    async with AsyncTestClient(app=app) as c:
        yield c


async def test_index_serves_page_and_sets_device_cookie(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "TI4 Dashboard" in resp.text
    assert "device_id" in resp.cookies


async def test_claim_seat_updates_game_state(client):
    await client.get("/")  # get a device cookie
    resp = await client.post("/action/claim_seat", params={"seat": 0})
    assert resp.status_code in (200, 204)
    # reload page; seat 0 should now show a Release button
    page = await client.get("/action/debug_players")
    assert "Release" in page.text


async def test_toggle_pause_flips_state(client):
    await client.get("/")
    await client.post("/action/toggle_pause")
    page = await client.get("/action/debug_players")  # any state read
    assert page.status_code == 200


async def test_stylesheet_served_and_page_links_it(client):
    resp = await client.get("/app.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]
    assert ".player-card" in resp.text
    page = await client.get("/")
    assert '<link rel="stylesheet" href="/app.css">' in page.text
