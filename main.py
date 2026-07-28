"""Twilight Imperium dashboard — NiceGUI 3.x.

Run:  python main.py     then open http://<your-lan-ip>:8080 on every phone.

Architecture note
-----------------
NiceGUI 3.0 removed the shared "auto-index" client, so UI in global scope is no
longer shared between browsers. The replacement pattern, used here:

    game     -> a long-living plain-Python object (game.py)
    changed  -> a nicegui.Event
    @ui.page -> per-client UI that subscribes to `changed`

Any mutation calls `touch()`, every connected device re-renders. Subscriptions
made inside a UI context are unsubscribed automatically when that client goes
away, so players closing their phones don't leak handlers.

Identity / auth (F9)
---------------------
`device_id` is a per-browser id (`app.storage.browser["device_id"]`, a
NiceGUI-managed signed cookie) — "this phone," not a login. `is_admin` gates
behind a shared password (`game.config.admin_password`) compared in
`admin_login_dialog()`; once entered it's remembered the same way. Both are
passed as plain arguments into every `game.*` mutator that checks
authorization — game.py never imports nicegui or sees browser storage.
"""

import uuid
from pathlib import Path

from nicegui import app, ui
from nicegui import Event

from db import EventStore
from game import COLORS, FACTION_PRESETS, FACTIONS, PHASES, STRATEGY_CARDS, Game

game = Game.demo()
changed: Event = Event()

# F13 — sqlite event log lives next to the source, not under version control
# (see .gitignore); game.py never imports db.py, it only calls game.sink(...).
DB_PATH = Path(__file__).parent / "ti-dash.db"
store = EventStore(DB_PATH)
game.sink = store.append
app.on_shutdown(store.close)


def touch() -> None:
    """Broadcast: re-render the board on every connected device."""
    changed.emit()


def guarded(action, *, refresh: bool = True) -> None:
    """Run a game.py mutation; show a notification instead of crashing when
    it's rejected for authorization (F9, PermissionError) or because the
    game is paused (F10, RuntimeError)."""
    try:
        action()
    except (PermissionError, RuntimeError) as exc:
        ui.notify(str(exc), color="negative")
        return
    if refresh:
        touch()


# --- Look -----------------------------------------------------------------
# Roman inscriptional capitals for the imperial chrome, Plex for data. The
# faction colours are the palette -- they encode who owns what, so the rest of
# the interface stays quiet brass-on-void and lets them carry the meaning.

VOID = "#0b0a1a"
PANEL = "#151330"
RAISED = "#1e1b42"
BRASS = "#c9a227"
DIM = "#8e8bb0"
INK = "#ece9ff"
RED = "#e0483c"

CSS = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
  body {{ background: {VOID}; color: {INK}; font-family: 'IBM Plex Sans', sans-serif; }}
  .imperial {{ font-family: 'Cinzel', serif; letter-spacing: .08em; text-transform: uppercase; }}
  .num {{ font-family: 'IBM Plex Mono', monospace; font-variant-numeric: tabular-nums; }}
  .panel {{ background: {PANEL}; border: 1px solid #2a2758; border-radius: 10px; }}
  .rule {{ height: 1px; background: linear-gradient(90deg, {BRASS}55, transparent); }}
</style>
"""

# F3 — a short synthesized beep via Web Audio, no bundled asset file.
BEEP_JS = """
(() => {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = 880;
    gain.gain.value = 0.15;
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.15);
  } catch (e) { /* audio unsupported/blocked; not fatal */ }
})()
"""


def chip(text: str, color: str = BRASS) -> ui.label:
    return (
        ui.label(text)
        .classes("imperial text-[10px] px-2 py-[2px] rounded")
        .style(f"background:{color}22; color:{color}; border:1px solid {color}55")
    )


def format_clock(seconds: float) -> str:
    sign = "-" if seconds < 0 else ""
    secs = int(abs(seconds))
    return f"{sign}{secs // 60:02d}:{secs % 60:02d}"


# --- Signature element ----------------------------------------------------


def victory_track() -> None:
    """The scoreboard as it exists on the table: a 0..10 track with tokens on it.

    A number in a card would be smaller and easier to build, but the track is
    the artefact players actually look at, and it shows the gaps between
    everyone at a glance rather than just the ordering.
    """
    with ui.element("div").classes("panel w-full p-4"):
        with ui.row().classes("items-baseline gap-3 mb-3"):
            ui.label("Victory Track").classes("imperial text-sm").style(f"color:{BRASS}")
            ui.label(f"first to {game.vp_goal}").classes("text-xs").style(f"color:{DIM}")

        with ui.row().classes("w-full gap-[3px] no-wrap"):
            for step in range(game.vp_goal + 1):
                here = [p for p in game.players if p.vp == step]
                is_goal = step == game.vp_goal
                with ui.column().classes("flex-1 items-center gap-1"):
                    ui.label(str(step)).classes("num text-[11px]").style(
                        f"color:{BRASS if is_goal else DIM}"
                    )
                    with ui.element("div").classes(
                        "w-full rounded flex flex-col items-center justify-end gap-[3px] p-1"
                    ).style(
                        f"min-height:74px;"
                        f"background:{RAISED if here else '#12102a'};"
                        f"border:1px solid {BRASS + '66' if is_goal else '#2a2758'}"
                    ):
                        for p in here:
                            ui.element("div").classes("rounded-full").style(
                                f"width:16px;height:16px;background:{COLORS[p.color]};"
                                f"box-shadow:0 0 8px {COLORS[p.color]}88"
                            ).tooltip(f"{p.name} — {p.faction}")


# --- Admin / config (F9, F16) ------------------------------------------------


def admin_login_dialog(device_id: str) -> None:
    with ui.dialog() as dialog, ui.card().style(f"background:{PANEL}"):
        ui.label("Admin login").classes("imperial text-sm").style(f"color:{BRASS}")
        password = ui.input("Password", password=True).props("dense outlined dark").classes("w-64")

        def submit() -> None:
            if password.value == game.config.admin_password:
                app.storage.browser["is_admin"] = True
                dialog.close()
                touch()
            else:
                ui.notify("Wrong password", color="negative")

        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat dense no-caps")
            ui.button("Enter", on_click=submit).props("dense no-caps unelevated").style(
                f"background:{BRASS};color:{VOID}"
            )
    dialog.open()


def settings_dialog(is_admin: bool) -> None:
    cfg = game.config
    with ui.dialog() as dialog, ui.card().style(f"background:{PANEL}"):
        ui.label("Timer settings").classes("imperial text-sm").style(f"color:{BRASS}")
        fields = {
            "turn_seconds": ui.number("Turn timer (s)", value=cfg.turn_seconds),
            "secondary_seconds": ui.number("Secondary action (s)", value=cfg.secondary_seconds),
            "status_phase_seconds": ui.number("Status phase (s)", value=cfg.status_phase_seconds),
            "agenda_reveal_seconds": ui.number(
                "Agenda reveal (s)", value=cfg.agenda_reveal_seconds
            ),
            "agenda_vote_seconds": ui.number("Agenda vote (s)", value=cfg.agenda_vote_seconds),
        }
        for widget in fields.values():
            widget.props("dense outlined dark").classes("w-64")
        admin_password = (
            ui.input("Admin password", password=True, value=cfg.admin_password)
            .props("dense outlined dark")
            .classes("w-64")
        )

        def submit() -> None:
            guarded(
                lambda: game.update_config(
                    is_admin,
                    **{name: widget.value for name, widget in fields.items()},
                    admin_password=admin_password.value,
                )
            )
            dialog.close()

        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat dense no-caps")
            ui.button("Save", on_click=submit).props("dense no-caps unelevated").style(
                f"background:{BRASS};color:{VOID}"
            )
    dialog.open()


def report_dialog() -> None:
    """F14/F15 — end-of-game (but also useful mid-game) time report, reading
    the persisted event log rather than any in-memory bookkeeping."""
    phase_totals = store.phase_totals()
    player_totals = store.player_totals()
    with ui.dialog() as dialog, ui.card().style(f"background:{PANEL}").classes("w-96"):
        ui.label("Session report").classes("imperial text-sm").style(f"color:{BRASS}")

        ui.label("Time per phase").classes("imperial text-[10px] mt-2").style(f"color:{DIM}")
        if phase_totals:
            for phase, seconds in sorted(phase_totals.items(), key=lambda kv: -kv[1]):
                with ui.row().classes("w-full justify-between"):
                    ui.label(phase).classes("text-xs").style(f"color:{INK}")
                    ui.label(format_clock(seconds)).classes("num text-xs").style(f"color:{BRASS}")
        else:
            ui.label("No phase data yet").classes("text-xs").style(f"color:{DIM}")

        ui.label("Time per player").classes("imperial text-[10px] mt-3").style(f"color:{DIM}")
        if player_totals:
            for name, seconds in sorted(player_totals.items(), key=lambda kv: -kv[1]):
                with ui.row().classes("w-full justify-between"):
                    ui.label(name).classes("text-xs").style(f"color:{INK}")
                    ui.label(format_clock(seconds)).classes("num text-xs").style(f"color:{BRASS}")
        else:
            ui.label("No turn data yet").classes("text-xs").style(f"color:{DIM}")

        with ui.row().classes("w-full justify-end"):
            ui.button("Close", on_click=dialog.close).props("flat dense no-caps")
    dialog.open()


# --- Header ---------------------------------------------------------------


def round_header(device_id: str, is_admin: bool) -> None:
    with ui.row().classes("w-full items-center justify-between"):
        with ui.column().classes("gap-0"):
            ui.label("Twilight Imperium").classes("imperial text-xl").style(f"color:{BRASS}")
            leader = game.leader()
            subtitle = (
                f"{leader.name} leads on {leader.vp}" if leader and leader.vp else "No points scored"
            )
            if game.paused:
                subtitle = "Paused · " + subtitle
            ui.label(subtitle).classes("text-xs").style(f"color:{DIM}")

        with ui.row().classes("items-center gap-2"):
            ui.label(f"Round {game.round}").classes("num text-sm").style(f"color:{INK}")
            ui.label("·").style(f"color:{DIM}")
            for phase in PHASES:
                active = phase == game.phase
                ui.button(
                    phase,
                    on_click=lambda p=phase: guarded(lambda: game.set_phase(p, is_admin=is_admin)),
                ).props("flat dense no-caps").classes("imperial text-[10px] px-2").style(
                    f"color:{BRASS if active else DIM};"
                    f"background:{BRASS + '22' if active else 'transparent'}"
                )
            ui.button(
                "Next phase",
                on_click=lambda: guarded(lambda: game.advance_phase(is_admin=is_admin)),
            ).props("dense no-caps unelevated").classes("imperial text-[10px]").style(
                f"background:{BRASS}; color:{VOID}"
            )

            ui.button(
                "Resume" if game.paused else "Pause",
                on_click=lambda: guarded(game.resume if game.paused else game.pause),
            ).props("flat dense no-caps").classes("imperial text-[10px]").style(
                f"color:{RED if game.paused else DIM}"
            )

            ui.button(icon="query_stats", on_click=report_dialog).props(
                "flat dense round size=sm"
            ).style(f"color:{DIM}").tooltip("Session report")

            if is_admin:
                ui.button(
                    icon="settings", on_click=lambda: settings_dialog(is_admin)
                ).props("flat dense round size=sm").style(f"color:{BRASS}").tooltip(
                    "Timer settings (admin)"
                )
            else:
                ui.button(icon="lock", on_click=lambda: admin_login_dialog(device_id)).props(
                    "flat dense round size=sm"
                ).style(f"color:{DIM}").tooltip("Admin login")


# --- Turn clock (F2, F3) ---------------------------------------------------


@ui.refreshable
def turn_banner() -> None:
    """Refreshed once a second per client, but the clock is derived from a
    server timestamp, so extra browsers can't make it run fast."""
    if game.phase != "Action" or game.active is None:
        with ui.element("div").classes("panel w-full p-3"):
            ui.label(
                "Action phase not running" if game.phase != "Action" else "No active turn"
            ).classes("imperial text-xs").style(f"color:{DIM}")
        return

    p = game.players[game.active]
    remaining = p.turn_clock.remaining()
    overtime = remaining is not None and remaining < 0
    color = RED if overtime else COLORS[p.color]
    display = format_clock(remaining) if remaining is not None else format_clock(p.turn_clock.elapsed())

    with ui.element("div").classes("panel w-full p-3").style(
        f"border-color:{color}88; background:{color}14"
    ):
        with ui.row().classes("w-full items-center justify-between no-wrap"):
            with ui.row().classes("items-center gap-3"):
                ui.element("div").classes("rounded-full").style(
                    f"width:12px;height:12px;background:{color}"
                )
                with ui.column().classes("gap-0"):
                    ui.label(f"{p.name} is up").classes("imperial text-sm").style(f"color:{INK}")
                    ui.label(p.faction).classes("text-xs").style(f"color:{DIM}")
            ui.label(display).classes("num text-2xl").style(f"color:{color}")
            ui.button("End turn", on_click=lambda: guarded(game.next_turn)).props(
                "dense no-caps unelevated"
            ).classes("imperial text-[10px]").style(f"background:{BRASS};color:{VOID}")


@ui.refreshable
def secondary_banner() -> None:
    """F5 — secondary strategy action window, visible whenever active."""
    if game.secondary_clock is None:
        return
    remaining = game.secondary_clock.remaining()
    with ui.row().classes("w-full items-center justify-between panel p-2").style(
        f"border-color:{BRASS}55"
    ):
        ui.label("Secondary action window").classes("imperial text-[10px]").style(f"color:{DIM}")
        ui.label(format_clock(remaining) if remaining is not None else "").classes(
            "num text-sm"
        ).style(f"color:{BRASS}")
        ui.button("Dismiss", on_click=lambda: guarded(game.clear_secondary)).props(
            "flat dense no-caps size=sm"
        ).style(f"color:{DIM}")


@ui.refreshable
def status_banner() -> None:
    """F7 — one countdown chip per player with a running status clock."""
    running = {name: clock for name, clock in game.status_clocks.items() if clock.running}
    if game.phase != "Status" or not running:
        return
    with ui.row().classes("w-full items-center gap-2 flex-wrap"):
        for name, clock in running.items():
            remaining = clock.remaining()
            with ui.row().classes("items-center gap-1 px-2 py-1 rounded panel"):
                ui.label(name).classes("text-[11px]").style(f"color:{INK}")
                ui.label(format_clock(remaining) if remaining is not None else "").classes(
                    "num text-xs"
                ).style(f"color:{BRASS}")


@ui.refreshable
def agenda_banner() -> None:
    """F8 — reveal timer and (reusing status_clocks) per-player vote timers."""
    if game.phase != "Agenda":
        return
    if game.agenda_clock is not None:
        remaining = game.agenda_clock.remaining()
        with ui.row().classes("w-full items-center justify-between panel p-2").style(
            f"border-color:{BRASS}55"
        ):
            ui.label("Agenda reveal").classes("imperial text-[10px]").style(f"color:{DIM}")
            ui.label(format_clock(remaining) if remaining is not None else "").classes(
                "num text-sm"
            ).style(f"color:{BRASS}")
    status_banner.refresh()  # vote timers reuse status_clocks/status_banner's rendering


# --- Player cards (F4, F9, F11) --------------------------------------------


def counter(label: str, value: int, on_change, color: str) -> None:
    with ui.column().classes("items-center gap-0"):
        ui.label(label).classes("imperial text-[9px]").style(f"color:{DIM}")
        with ui.row().classes("items-center gap-1 no-wrap"):
            ui.button(icon="remove", on_click=lambda: on_change(-1)).props(
                "flat dense round size=xs"
            ).style(f"color:{DIM}")
            ui.label(str(value)).classes("num text-base w-5 text-center").style(f"color:{color}")
            ui.button(icon="add", on_click=lambda: on_change(1)).props(
                "flat dense round size=xs"
            ).style(f"color:{DIM}")


def player_card(p, device_id: str, is_admin: bool) -> None:
    color = COLORS[p.color]
    is_speaker = game.players[game.speaker] is p
    is_active = game.active is not None and game.players[game.active] is p
    owned_by_me = p.claim_token == device_id
    claimed_by_other = p.claim_token is not None and not owned_by_me
    can_act = is_admin or owned_by_me

    with ui.element("div").classes("panel p-3").style(
        f"border-color:{color + 'aa' if is_active else '#2a2758'};"
        f"opacity:{0.55 if p.passed else 1}"
    ):
        # Identity row
        with ui.row().classes("w-full items-center justify-between no-wrap mb-2"):
            with ui.row().classes("items-center gap-2 no-wrap"):
                ui.element("div").style(
                    f"width:10px;height:28px;border-radius:2px;background:{color}"
                )
                with ui.column().classes("gap-0"):
                    ui.label(p.name).classes("imperial text-sm").style(f"color:{INK}")
                    ui.label(p.faction).classes("text-[11px] leading-tight").style(f"color:{DIM}")
            with ui.column().classes("items-end gap-1"):
                if is_speaker:
                    chip("Speaker")
                if p.passed:
                    chip("Passed", DIM)
                if claimed_by_other:
                    ui.icon("lock").style(f"color:{DIM}").tooltip("Claimed by another device")

        ui.element("div").classes("rule w-full mb-2")

        # Seat claim/unclaim (F9)
        with ui.row().classes("w-full mb-2"):
            if p.claim_token is None:
                ui.button(
                    "Claim seat", on_click=lambda p=p: guarded(lambda: game.claim_seat(p, device_id))
                ).props("flat dense no-caps size=sm").classes("imperial text-[10px]").style(
                    f"color:{BRASS}"
                )
            elif owned_by_me:
                ui.button(
                    "Unclaim seat",
                    on_click=lambda p=p: guarded(lambda: game.unclaim_seat(p, device_id)),
                ).props("flat dense no-caps size=sm").classes("imperial text-[10px]").style(
                    f"color:{DIM}"
                )
            elif is_admin:
                ui.button(
                    "Unclaim (admin)",
                    on_click=lambda p=p: guarded(
                        lambda: game.unclaim_seat(p, device_id, is_admin=True)
                    ),
                ).props("flat dense no-caps size=sm").classes("imperial text-[10px]").style(
                    f"color:{DIM}"
                )

        if claimed_by_other and not is_admin:
            # F9: claimed-by-others seats show identity but no action row.
            mins = int(p.turn_clock.elapsed()) // 60
            ui.label(f"{mins} min at the table").classes("num text-[10px] mt-1").style(
                f"color:{DIM}"
            )
            return

        # Victory points
        with ui.row().classes("w-full items-center justify-between no-wrap mb-2"):
            ui.label("Victory points").classes("imperial text-[10px]").style(f"color:{DIM}")
            with ui.row().classes("items-center gap-1 no-wrap"):
                ui.button(
                    icon="remove",
                    on_click=lambda p=p: guarded(
                        lambda: game.score(p, -1, device_id, is_admin=is_admin)
                    ),
                ).props("flat dense round size=sm").style(f"color:{DIM}")
                ui.label(str(p.vp)).classes("num text-2xl w-8 text-center").style(f"color:{color}")
                ui.button(
                    icon="add",
                    on_click=lambda p=p: guarded(
                        lambda: game.score(p, 1, device_id, is_admin=is_admin)
                    ),
                ).props("flat dense round size=sm").style(f"color:{color}")

        # Strategy card — the number is the initiative, so it is worth showing
        options = {None: "— none —"} | {
            n: f"{n} · {name}"
            for n, name in STRATEGY_CARDS.items()
            if n not in game.taken_cards() or n == p.strategy_card
        }

        def on_card_change(e, p=p) -> None:
            guarded(lambda: game.assign_card(p, e.value, device_id, is_admin=is_admin))
            if e.value:
                # F5 — every other player gets a window to declare a secondary
                # action once the primary player's card is taken.
                guarded(game.start_secondary)

        ui.select(options, value=p.strategy_card, on_change=on_card_change).props(
            "dense outlined dark options-dense"
        ).classes("w-full text-xs mb-2")

        # Economy and command tokens
        with ui.row().classes("w-full justify-between no-wrap mb-2"):
            counter(
                "Trade",
                p.trade_goods,
                lambda d, p=p: guarded(
                    lambda: game.adjust_counter(p, "trade_goods", d, device_id, is_admin=is_admin)
                ),
                BRASS,
            )
            counter(
                "Tactic",
                p.tactic,
                lambda d, p=p: guarded(
                    lambda: game.adjust_counter(p, "tactic", d, device_id, is_admin=is_admin)
                ),
                INK,
            )
            counter(
                "Fleet",
                p.fleet,
                lambda d, p=p: guarded(
                    lambda: game.adjust_counter(p, "fleet", d, device_id, is_admin=is_admin)
                ),
                INK,
            )
            counter(
                "Strat",
                p.strategy,
                lambda d, p=p: guarded(
                    lambda: game.adjust_counter(p, "strategy", d, device_id, is_admin=is_admin)
                ),
                INK,
            )

        # Actions
        with ui.row().classes("w-full gap-1 no-wrap"):
            ui.button(
                "Take turn",
                on_click=lambda p=p: guarded(
                    lambda: game.start_turn(p, device_id, is_admin=is_admin)
                ),
            ).props("flat dense no-caps size=sm").classes("imperial text-[10px] flex-1").style(
                f"color:{color}"
            )
            ui.button(
                "Un-pass" if p.passed else "Pass",
                on_click=lambda p=p: guarded(
                    lambda: game.toggle_pass(p, device_id, is_admin=is_admin)
                ),
            ).props("flat dense no-caps size=sm").classes(
                "imperial text-[10px] flex-1"
            ).style(f"color:{DIM}")
            ui.button(
                icon="campaign",
                on_click=lambda p=p: guarded(
                    lambda: game.pass_speaker(p, device_id, is_admin=is_admin)
                ),
            ).props("flat dense round size=sm").style(f"color:{DIM}").tooltip("Make Speaker")
            if is_admin:
                ui.button(
                    icon="restart_alt",
                    on_click=lambda p=p: guarded(
                        lambda: game.reset_turn_clock(p, is_admin=is_admin)
                    ),
                ).props("flat dense round size=sm").style(f"color:{DIM}").tooltip(
                    "Reset turn timer (admin)"
                )

        mins = int(p.turn_clock.elapsed()) // 60
        ui.label(f"{mins} min at the table").classes("num text-[10px] mt-1").style(f"color:{DIM}")


# --- Roster management ----------------------------------------------------


def add_player_dialog() -> None:
    with ui.dialog() as dialog, ui.card().style(f"background:{PANEL}"):
        ui.label("Add player").classes("imperial text-sm").style(f"color:{BRASS}")
        name = ui.input("Name").props("dense outlined dark").classes("w-64")

        taken = {p.color for p in game.players}
        free = [c for c in COLORS if c not in taken] or list(COLORS)
        color = ui.select(free, value=free[0]).props("dense outlined dark").classes("w-64")

        def on_faction_change(e) -> None:
            # F4 — presets pre-select a color but never remove the ability to
            # override it manually afterward.
            preset = FACTION_PRESETS.get(e.value)
            if preset and preset in free:
                color.value = preset

        faction = (
            ui.select(list(FACTIONS), value=FACTIONS[0], with_input=True, on_change=on_faction_change)
            .props("dense outlined dark")
            .classes("w-64")
        )

        if FACTION_PRESETS:
            ui.label("Quick picks").classes("imperial text-[9px] mt-1").style(f"color:{DIM}")
            with ui.row().classes("gap-1 flex-wrap w-64"):
                for preset_faction in list(FACTION_PRESETS)[:6]:

                    def pick(f=preset_faction) -> None:
                        faction.value = f
                        on_faction_change(type("E", (), {"value": f})())

                    ui.button(preset_faction.removeprefix("The "), on_click=pick).props(
                        "flat dense no-caps size=sm"
                    ).classes("text-[10px]").style(f"color:{DIM}")

        def submit() -> None:
            if not name.value:
                ui.notify("Name required", color="negative")
                return
            game.add_player(name.value, faction.value, color.value)
            dialog.close()
            touch()

        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat dense no-caps")
            ui.button("Add", on_click=submit).props("dense no-caps unelevated").style(
                f"background:{BRASS};color:{VOID}"
            )
    dialog.open()


# --- Page -----------------------------------------------------------------


@ui.page("/")
def dashboard() -> None:
    ui.add_head_html(CSS)
    ui.query(".nicegui-content").classes("p-0")

    if "device_id" not in app.storage.browser:
        app.storage.browser["device_id"] = str(uuid.uuid4())
    device_id: str = app.storage.browser["device_id"]

    def is_admin() -> bool:
        return bool(app.storage.browser.get("is_admin", False))

    @ui.refreshable
    def board() -> None:
        admin = is_admin()
        with ui.column().classes("w-full max-w-[1400px] mx-auto gap-4 p-5"):
            round_header(device_id, admin)

            if winner := game.winner():
                with ui.element("div").classes("panel w-full p-4").style(
                    f"border-color:{BRASS}; background:{BRASS}18"
                ):
                    ui.label(f"{winner.name} wins the Imperium").classes(
                        "imperial text-lg"
                    ).style(f"color:{BRASS}")

            victory_track()
            turn_banner()
            secondary_banner()
            status_banner()
            agenda_banner()

            # Initiative strip — ordering here is real information, not decoration
            order = [p for p in game.initiative_order() if p.strategy_card]
            if order:
                with ui.row().classes("items-center gap-2 flex-wrap"):
                    ui.label("Initiative").classes("imperial text-[10px]").style(f"color:{DIM}")
                    for p in order:
                        with ui.row().classes("items-center gap-1 px-2 py-1 rounded").style(
                            f"background:{RAISED};border:1px solid {COLORS[p.color]}55"
                        ):
                            ui.label(str(p.strategy_card)).classes("num text-xs").style(
                                f"color:{COLORS[p.color]}"
                            )
                            ui.label(p.name).classes("text-[11px]").style(f"color:{INK}")

            with ui.grid().classes("w-full gap-3").style(
                "grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))"
            ):
                for p in game.initiative_order():
                    player_card(p, device_id, admin)

            with ui.row().classes("gap-2"):
                ui.button("Add player", on_click=add_player_dialog).props(
                    "flat dense no-caps"
                ).classes("imperial text-[10px]").style(f"color:{BRASS}")
                ui.button(
                    "New round",
                    on_click=lambda: guarded(lambda: game.new_round(is_admin=admin)),
                ).props("flat dense no-caps").classes("imperial text-[10px]").style(f"color:{DIM}")

            if game.log:
                with ui.expansion("Session log").classes("w-full text-xs").style(f"color:{DIM}"):
                    for entry in game.log[:25]:
                        ui.label(str(entry)).classes("num text-[11px]").style(f"color:{DIM}")

    board()

    # Every device rebuilds when anyone touches the game.
    changed.subscribe(board.refresh)

    # Local ticker for the clock only; state still lives on the server.
    ui.timer(1.0, turn_banner.refresh)
    ui.timer(1.0, secondary_banner.refresh)
    ui.timer(1.0, status_banner.refresh)
    ui.timer(1.0, agenda_banner.refresh)

    # F3 — per-client sound-cue tracking, deliberately separate from the
    # shared turn_banner refreshable: "just crossed a threshold" is a
    # per-connection concept (so reconnecting doesn't fire a backlog of
    # beeps), unlike the countdown display itself, which is shared state.
    last_seen_remaining = {"value": None}

    def sound_check() -> None:
        if game.phase != "Action" or game.active is None:
            last_seen_remaining["value"] = None
            return
        remaining = game.players[game.active].turn_clock.remaining()
        if remaining is None:
            return
        previous = last_seen_remaining["value"]
        last_seen_remaining["value"] = remaining
        if previous is None:
            return
        for threshold in (*game.config.warn_at, 0.0):
            if previous > threshold >= remaining:
                ui.run_javascript(BEEP_JS)
                break

    ui.timer(1.0, sound_check)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="Twilight Imperium",
        dark=True,
        favicon="🌌",
        port=8080,
        # F9 needs app.storage.browser (a signed cookie) for device_id/admin;
        # NiceGUI requires a secret to sign it. This app is meant for a LAN
        # party, not the open internet — the real access gate is
        # config.admin_password, not this secret.
        storage_secret="ti-dash-dev-secret",
    )
