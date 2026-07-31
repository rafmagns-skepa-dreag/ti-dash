import asyncio
from collections.abc import Callable

from datastar_py.litestar import DatastarResponse, read_signals
from datastar_py.litestar import ServerSentEventGenerator as SSE
from litestar import Litestar, Request, get, post
from litestar.exceptions import HTTPException
from litestar.response import Response

from ti_dash.domain.game import Game
from ti_dash.domain.models import Player
from ti_dash.domain.reference import Color, Faction, Phase
from ti_dash.persistence.db import Database
from ti_dash.web import render
from ti_dash.web.broadcast import Broadcaster
from ti_dash.web.identity import ADMIN_COOKIE, DEVICE_COOKIE, new_device_id
from ti_dash.web.styles import CSS

PLAYERS = [
    Player("Imogen", Faction.NAALU, Color.GREEN, 0),
    Player("Pavle", Faction.RAL_NEL, Color.BLACK, 1),
    Player("Gil", Faction.CRIMSON, Color.RED, 2),
    Player("Jim", Faction.DEEPWROUGHT, Color.BLUE, 3),
    Player("Izzy", Faction.KELERES, Color.PINK, 4),
    Player("Rich", Faction.FIRMAMENT, Color.PURPLE, 5),
    Player("Dani!", Faction.BASTION, Color.YELLOW, 6),
    Player("Summer", Faction.MUAAT, Color.ORANGE, 7),
]


class AppState:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.game = Game(players=PLAYERS)
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

    async def _guarded(state: AppState, mutate: Callable[[Game], None]) -> Response:
        try:
            await state.apply(mutate)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return Response(content="", status_code=204)

    @get("/")
    async def index(request: Request) -> Response:
        did = request.cookies.get(DEVICE_COOKIE)
        html = render.full_page(state.game, is_admin=is_admin_of(request))
        resp = Response(content=html, media_type="text/html")
        if not did:
            resp.set_cookie(DEVICE_COOKIE, new_device_id())
        return resp

    @get("/app.css")
    async def stylesheet() -> Response:
        return Response(content=CSS, media_type="text/css")

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
        return await _guarded(state, lambda g: g.claim_seat(g.players[seat], did))

    @post("/action/release_seat")
    async def release_seat(request: Request, seat: int) -> Response:
        did = device_id_of(request)
        admin = is_admin_of(request)
        return await _guarded(
            state, lambda g: g.release_seat(g.players[seat], did, is_admin=admin)
        )

    @post("/action/toggle_pause")
    async def toggle_pause() -> Response:
        await state.apply(lambda g: g.resume() if g.paused else g.pause())
        return Response(content="", status_code=204)

    @post("/action/advance")
    async def advance() -> Response:
        # Gate button: perform the correct transition based on phase.
        await state.apply(_advance_transition)
        return Response(content="", status_code=204)

    @get("/action/debug_players")
    async def debug_players() -> Response:
        return Response(
            content=render.players_fragment(state.game), media_type="text/html"
        )

    @post("/action/score")
    async def score(request: Request, seat: int, delta: int) -> Response:
        did, admin = device_id_of(request), is_admin_of(request)
        return await _guarded(
            state, lambda g: g.score(g.players[seat], delta, did, is_admin=admin)
        )

    @post("/action/pick_card")
    async def pick_card(request: Request, seat: int, card: int) -> Response:
        did, admin = device_id_of(request), is_admin_of(request)
        return await _guarded(
            state,
            lambda g: g.pick_strategy_card(g.players[seat], card, did, is_admin=admin),
        )

    @post("/action/begin_pick")
    async def begin_pick(request: Request, seat: int) -> Response:
        return await _guarded(state, lambda g: g.begin_strategy_pick())

    @post("/action/end_turn")
    async def end_turn(request: Request, seat: int) -> Response:
        did, admin = device_id_of(request), is_admin_of(request)
        return await _guarded(
            state, lambda g: g.end_turn(g.players[seat], did, is_admin=admin)
        )

    @post("/action/pass_turn")
    async def pass_turn(request: Request, seat: int) -> Response:
        did, admin = device_id_of(request), is_admin_of(request)
        return await _guarded(
            state, lambda g: g.pass_turn(g.players[seat], did, is_admin=admin)
        )

    @post("/action/open_secondary")
    async def open_secondary() -> Response:
        return await _guarded(state, lambda g: g.open_secondary())

    @post("/action/close_secondary")
    async def close_secondary() -> Response:
        return await _guarded(state, lambda g: g.close_secondary())

    @post("/action/open_agenda_window")
    async def open_agenda_window() -> Response:
        return await _guarded(state, lambda g: g.open_agenda_window())

    @post("/action/close_agenda_window")
    async def close_agenda_window() -> Response:
        return await _guarded(state, lambda g: g.close_agenda_window())

    @post("/action/begin_vote")
    async def begin_vote(request: Request, seat: int) -> Response:
        did, admin = device_id_of(request), is_admin_of(request)
        return await _guarded(
            state, lambda g: g.begin_agenda_vote(g.players[seat], did, is_admin=admin)
        )

    @post("/action/cast_vote")
    async def cast_vote(request: Request, seat: int) -> Response:
        did, admin = device_id_of(request), is_admin_of(request)
        return await _guarded(
            state, lambda g: g.cast_agenda_vote(g.players[seat], did, is_admin=admin)
        )

    @post("/action/toggle_agenda")
    async def toggle_agenda() -> Response:
        return await _guarded(
            state,
            lambda g: setattr(
                g, "agenda_enabled_this_round", not g.agenda_enabled_this_round
            ),
        )

    @post("/action/admin_login")
    async def admin_login(request: Request) -> Response:
        signals = await read_signals(request) or {}
        resp = Response(content="", status_code=204)
        if signals.get("password") == state.game.config.admin_password:
            resp.set_cookie(ADMIN_COOKIE, "1")
        return resp

    @post("/action/admin_logout")
    async def admin_logout() -> Response:
        resp = Response(content="", status_code=204)
        resp.delete_cookie(ADMIN_COOKIE)
        return resp

    async def _startup(app: Litestar) -> None:
        await state.load()

    return Litestar(
        route_handlers=[
            index,
            stylesheet,
            events,
            claim_seat,
            release_seat,
            toggle_pause,
            advance,
            debug_players,
            score,
            pick_card,
            begin_pick,
            end_turn,
            pass_turn,
            open_secondary,
            close_secondary,
            open_agenda_window,
            close_agenda_window,
            begin_vote,
            cast_vote,
            toggle_agenda,
            admin_login,
            admin_logout,
        ],
        on_startup=[_startup],
    )


def _advance_transition(g: Game) -> None:
    match g.phase:
        case Phase.Strategy:
            g.start_action_phase()
        case Phase.Action:
            g.start_status_phase()
        case Phase.Status:
            g.start_agenda_phase() if g.agenda_enabled_this_round else g.new_round()
        case Phase.Agenda:
            g.new_round()
