import asyncio
from typing import Callable

from litestar import Litestar, Request, get, post
from litestar.response import Response

from datastar_py.litestar import DatastarResponse, ServerSentEventGenerator as SSE

from ti_dash.domain.game import Game
from ti_dash.persistence.db import Database
from ti_dash.web.broadcast import Broadcaster
from ti_dash.web.identity import DEVICE_COOKIE, ADMIN_COOKIE, new_device_id
from ti_dash.web import render


class AppState:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.game = Game.demo()
        self.broadcaster = Broadcaster()
        self.lock = asyncio.Lock()

    def _patches(self) -> list[str]:
        return [
            render.phasebar_fragment(self.game),
            render.timer_fragment(self.game),
            render.players_fragment(self.game),
        ]

    async def load(self) -> None:
        await self.db.connect()
        loaded = await self.db.load_snapshot()
        if loaded is not None:
            self.game = loaded

    async def apply(self, mutate: Callable[[Game], None]) -> None:
        async with self.lock:
            mutate(self.game)
            if self.game.pending_records:
                await self.db.append_records(self.game.pending_records)
                self.game.pending_records.clear()
            await self.db.save_snapshot(self.game)
            payload = "\n".join(self._patches())
        await self.broadcaster.publish(payload)


def create_app(db_path: str) -> Litestar:
    state = AppState(Database(db_path))

    def device_id_of(request: Request) -> str:
        return request.cookies.get(DEVICE_COOKIE, "")

    def is_admin_of(request: Request) -> bool:
        return request.cookies.get(ADMIN_COOKIE) == "1"

    @get("/")
    async def index(request: Request) -> Response:
        did = request.cookies.get(DEVICE_COOKIE)
        html = render.full_page(state.game, is_admin=is_admin_of(request))
        resp = Response(content=html, media_type="text/html")
        if not did:
            resp.set_cookie(DEVICE_COOKIE, new_device_id())
        return resp

    @get("/events")
    async def events() -> DatastarResponse:
        queue = state.broadcaster.subscribe()

        async def stream():
            # initial paint
            yield SSE.patch_elements(render.phasebar_fragment(state.game))
            yield SSE.patch_elements(render.timer_fragment(state.game))
            yield SSE.patch_elements(render.players_fragment(state.game))
            try:
                while True:
                    payload = await queue.get()
                    for fragment in payload.split("\n"):
                        yield SSE.patch_elements(fragment)
            finally:
                state.broadcaster.unsubscribe(queue)

        return DatastarResponse(stream())

    @post("/action/claim_seat")
    async def claim_seat(request: Request, seat: int) -> Response:
        did = device_id_of(request)
        await state.apply(lambda g: g.claim_seat(g.players[seat], did))
        return Response(content="", status_code=204)

    @post("/action/release_seat")
    async def release_seat(request: Request, seat: int) -> Response:
        did = device_id_of(request)
        admin = is_admin_of(request)
        await state.apply(lambda g: g.release_seat(g.players[seat], did, is_admin=admin))
        return Response(content="", status_code=204)

    @post("/action/toggle_pause")
    async def toggle_pause() -> Response:
        await state.apply(lambda g: (g.resume() if g.paused else g.pause()))
        return Response(content="", status_code=204)

    @post("/action/advance")
    async def advance() -> Response:
        # Gate button: perform the correct transition based on phase.
        await state.apply(_advance_transition)
        return Response(content="", status_code=204)

    @get("/action/debug_players")
    async def debug_players() -> Response:
        return Response(content=render.players_fragment(state.game), media_type="text/html")

    async def _startup(app: Litestar) -> None:
        await state.load()

    return Litestar(
        route_handlers=[index, events, claim_seat, release_seat, toggle_pause,
                        advance, debug_players],
        on_startup=[_startup],
    )


def _advance_transition(g: Game) -> None:
    if g.phase == "Strategy":
        g.start_action_phase()
    elif g.phase == "Action":
        g.start_status_phase()
    elif g.phase == "Status":
        g.start_agenda_phase() if g.agenda_enabled_this_round else g.new_round()
    elif g.phase == "Agenda":
        g.new_round()
