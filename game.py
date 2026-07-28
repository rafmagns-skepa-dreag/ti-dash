"""Twilight Imperium 4 session state.

Deliberately free of any NiceGUI import: this module is the long-living object,
the UI is short-living and subscribes to it. Keeping the seam here is what makes
the multi-device sync in main.py straightforward.

`game.py` also stays ignorant of sqlite (db.py) — mutations that should be
persisted go through the `Game.sink` callable (see `Game.note`), the same
`touch()`-style decoupling main.py already uses for rendering, just applied to
persistence.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, fields
from typing import Callable

# --- Reference data -------------------------------------------------------

STRATEGY_CARDS: dict[int, str] = {
    1: "Leadership",
    2: "Diplomacy",
    3: "Politics",
    4: "Construction",
    5: "Trade",
    6: "Warfare",
    7: "Technology",
    8: "Imperial",
}

PHASES = ("Strategy", "Action", "Status", "Agenda")

# Player colours as they appear in the box, with hexes tuned for a dark UI.
COLORS: dict[str, str] = {
    "Red": "#e0483c",
    "Blue": "#3d8fd8",
    "Green": "#3fa863",
    "Yellow": "#e0b73c",
    "Purple": "#9264c8",
    "Orange": "#e08a3c",
    "Pink": "#e07ab0",
    "Black": "#8b8fa3",
}

# F1 (Thunder's Edge factions) is deliberately NOT implemented here.
# SPEC.md §3/F1 and §6 flag Thunder's Edge as "blocked on data": there is no
# verified faction list for it (box insert / rules PDF / BGG page) available
# to this change, and the spec explicitly says not to fabricate faction
# names. Once a verified list exists, adding it is a pure data change to the
# FACTIONS tuple below (see SPEC.md F1 for the exact shape expected).
FACTIONS = (
    "The Arborec",
    "The Barony of Letnev",
    "The Clan of Saar",
    "The Embers of Muaat",
    "The Emirates of Hacan",
    "The Federation of Sol",
    "The Ghosts of Creuss",
    "The L1Z1X Mindnet",
    "The Mentak Coalition",
    "The Naalu Collective",
    "The Nekro Virus",
    "Sardakk N'orr",
    "The Universities of Jol-Nar",
    "The Winnu",
    "The Xxcha Kingdom",
    "The Yin Brotherhood",
    "The Yssaril Tribes",
    # Prophecy of Kings
    "The Argent Flight",
    "The Empyrean",
    "The Mahact Gene-Sorcerers",
    "The Naaz-Rokha Alliance",
    "The Nomad",
    "The Titans of Ul",
    "The Vuil'Raith Cabal",
    "The Council Keleres",
)

# F4 — named (faction -> suggested color) presets shown as quick-pick chips in
# add_player_dialog(). Purely a dialog default; the player can still override
# the color manually. Kept small and drawn from well-known box-art pairings
# rather than trying to cover every faction.
FACTION_PRESETS: dict[str, str] = {
    "The Federation of Sol": "Blue",
    "The Barony of Letnev": "Red",
    "The Emirates of Hacan": "Yellow",
    "The Xxcha Kingdom": "Green",
    "The Arborec": "Green",
    "The Yssaril Tribes": "Purple",
    "The Mentak Coalition": "Orange",
    "The Naalu Collective": "Pink",
    "The Clan of Saar": "Orange",
    "The Universities of Jol-Nar": "Blue",
    "The L1Z1X Mindnet": "Black",
    "The Nekro Virus": "Black",
    "Sardakk N'orr": "Red",
    "The Ghosts of Creuss": "Purple",
    "The Embers of Muaat": "Red",
    "The Winnu": "Yellow",
    "The Yin Brotherhood": "Black",
}


# --- Clock ------------------------------------------------------------------


@dataclass
class Clock:
    """A duration that starts running, can be stopped/banked, resumed, and
    reset, readable either as elapsed time or as signed remaining time
    (negative once expired).

    Every timer in the app (turn, secondary, status, agenda, phase) is this
    same shape; extracting it here means `time.monotonic()` arithmetic is
    written once instead of re-derived per timer. Timestamp-derived (not
    ticker-incremented) so N connected browsers can't make a clock run N
    times too fast.
    """

    duration: float | None = None  # seconds; None = stopwatch (no countdown)
    banked: float = 0.0  # accumulated seconds from prior run(s)
    started_at: float | None = None  # time.monotonic() timestamp, or None if stopped

    def start(self) -> None:
        """No-op if already running."""
        if self.started_at is None:
            self.started_at = time.monotonic()

    def stop(self) -> None:
        """Folds running time into `banked`. No-op if already stopped."""
        if self.started_at is not None:
            self.banked += time.monotonic() - self.started_at
            self.started_at = None

    def reset(self, duration: float | None = None) -> None:
        """Clears banked time, stops the clock, and sets a new duration
        (defaulting to no duration / stopwatch mode)."""
        self.banked = 0.0
        self.started_at = None
        self.duration = duration

    def elapsed(self) -> float:
        running = time.monotonic() - self.started_at if self.started_at is not None else 0.0
        return self.banked + running

    def remaining(self) -> float | None:
        """None until a duration is set; goes negative past expiry."""
        if self.duration is None:
            return None
        return self.duration - self.elapsed()

    @property
    def running(self) -> bool:
        return self.started_at is not None


# --- Config -------------------------------------------------------------------


@dataclass
class TimerConfig:
    turn_seconds: float = 180.0  # F2/F12 — per-turn action timer
    secondary_seconds: float = 60.0  # F5 — secondary strategy action window
    status_phase_seconds: float = 120.0  # F7 — per-person status phase timer
    agenda_reveal_seconds: float = 60.0  # F8 — "when/after an agenda is revealed"
    agenda_vote_seconds: float = 90.0  # F8 — per-person vote timer
    admin_password: str = ""  # F9 — shared secret gating admin mode
    warn_at: tuple[float, ...] = (60.0, 10.0)  # F3 — seconds-remaining sound cues


# --- Model ----------------------------------------------------------------


@dataclass
class Player:
    name: str
    faction: str
    color: str
    vp: int = 0
    trade_goods: int = 0
    strategy_card: int | None = None
    passed: bool = False
    tactic: int = 3
    fleet: int = 3
    strategy: int = 2
    turn_clock: Clock = field(default_factory=Clock)
    claim_token: str | None = None  # F9 — device id that owns this seat, or None

    @property
    def initiative(self) -> int:
        """Unpicked players sort last; the card number *is* the initiative."""
        return self.strategy_card if self.strategy_card is not None else 99

    @property
    def command_total(self) -> int:
        return self.tactic + self.fleet + self.strategy

    @property
    def banked(self) -> float:
        """Backward-compatible read view onto `turn_clock.banked`.

        `Player.banked` was a plain float pre-refactor; T0's baseline tests
        (tests/test_game_baseline.py) read it directly, so it's kept as a
        read-only property rather than deleted outright. New code should
        read `turn_clock.banked`/`turn_clock.elapsed()` directly instead.
        """
        return self.turn_clock.banked


@dataclass
class LogEntry:
    round: int
    phase: str
    text: str
    kind: str = "note"
    player: str | None = None
    payload: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    silent: bool = False  # True = persisted but not shown in the session-log panel

    def __str__(self) -> str:
        return f"R{self.round} · {self.text}"

    def __contains__(self, item: str) -> bool:
        """Lets `"substring" in entry` work like it did when `game.log` held
        plain strings — see T0's baseline tests, which predate LogEntry and
        check log content this way. New code should read `.text` directly."""
        return item in str(self)


# --- Game -------------------------------------------------------------------


@dataclass
class Game:
    players: list[Player] = field(default_factory=list)
    round: int = 1
    phase: str = "Strategy"
    speaker: int = 0
    vp_goal: int = 10
    active: int | None = None
    log: list[LogEntry] = field(default_factory=list)
    config: TimerConfig = field(default_factory=TimerConfig)  # F16
    paused: bool = False  # F10
    phase_clock: Clock = field(default_factory=Clock)  # F14
    status_clocks: dict[str, Clock] = field(default_factory=dict)  # F7, F8 (vote); per player name
    secondary_clock: Clock | None = None  # F5
    agenda_clock: Clock | None = None  # F8
    sink: Callable[[LogEntry], None] | None = None  # F13 — set by main.py at startup

    # -- derived views ----------------------------------------------------

    def initiative_order(self) -> list[Player]:
        return sorted(self.players, key=lambda p: p.initiative)

    def standings(self) -> list[Player]:
        return sorted(self.players, key=lambda p: (-p.vp, p.initiative))

    def leader(self) -> Player | None:
        return self.standings()[0] if self.players else None

    def winner(self) -> Player | None:
        return next((p for p in self.players if p.vp >= self.vp_goal), None)

    def elapsed(self, player: Player) -> float:
        """Backward-compatible convenience wrapper.

        Pre-refactor this reimplemented the monotonic-timestamp arithmetic
        that now lives on `Clock`; T0's baseline tests call `game.elapsed`
        directly, so it's kept as a one-line delegate. New code should call
        `player.turn_clock.elapsed()` directly.
        """
        return player.turn_clock.elapsed()

    @property
    def turn_started(self) -> float | None:
        """Backward-compatible read view onto the active player's
        `turn_clock.started_at`. Kept for T0's baseline tests; new code
        should read `player.turn_clock.started_at` (or `.running`) instead.
        """
        if self.active is None:
            return None
        return self.players[self.active].turn_clock.started_at

    def taken_cards(self) -> set[int]:
        return {p.strategy_card for p in self.players if p.strategy_card} - {None}

    # -- internal helpers ---------------------------------------------------

    def _check_not_paused(self) -> None:
        if self.paused:
            raise RuntimeError("game is paused")

    # -- logging / persistence (F13) -----------------------------------------

    def note(
        self,
        text: str,
        *,
        kind: str = "note",
        player: str | None = None,
        payload: dict | None = None,
        silent: bool = False,
    ) -> None:
        entry = LogEntry(
            round=self.round,
            phase=self.phase,
            text=text,
            kind=kind,
            player=player,
            payload=payload or {},
            silent=silent,
        )
        if not silent:
            self.log.insert(0, entry)
            del self.log[60:]
        if self.sink is not None:
            self.sink(entry)

    # -- roster -------------------------------------------------------------

    def add_player(self, name: str, faction: str, color: str) -> None:
        self._check_not_paused()
        self.players.append(Player(name=name, faction=faction, color=color))
        self.note(f"{name} joined as {faction}")

    # -- F9: seats / roles ----------------------------------------------------

    def claim_seat(self, player: Player, device_id: str) -> None:
        self._check_not_paused()
        if player.claim_token is not None and player.claim_token != device_id:
            raise PermissionError(f"{player.name}'s seat is already claimed")
        player.claim_token = device_id
        self.note(f"{player.name}'s seat claimed", kind="claim_seat", player=player.name)

    def unclaim_seat(self, player: Player, device_id: str, *, is_admin: bool = False) -> None:
        self._check_not_paused()
        if not is_admin and player.claim_token != device_id:
            raise PermissionError("not your seat")
        player.claim_token = None
        self.note(f"{player.name}'s seat unclaimed", kind="unclaim_seat", player=player.name)

    def authorize(self, player: Player, device_id: str | None = None, *, is_admin: bool = False) -> None:
        """Raise PermissionError unless `is_admin` or the caller owns this
        seat.

        `device_id`/`is_admin` default to values that reproduce pre-F9
        behavior when omitted: an unclaimed seat (`claim_token is None`)
        matches the default `device_id=None`, so callers that don't pass
        identity (including T0's baseline tests, written before F9 existed)
        keep working against the still-unclaimed demo roster. main.py always
        passes real values from browser storage.
        """
        if not is_admin and player.claim_token != device_id:
            raise PermissionError(f"not authorized to act for {player.name}")

    # -- scoring / cards / speaker (player-scoped actions, F9-guarded) ---------

    def score(
        self, player: Player, delta: int, device_id: str | None = None, *, is_admin: bool = False
    ) -> None:
        self._check_not_paused()
        self.authorize(player, device_id, is_admin=is_admin)
        player.vp = max(0, min(self.vp_goal, player.vp + delta))
        verb = "scored" if delta > 0 else "lost"
        self.note(f"{player.name} {verb} {abs(delta)} VP → {player.vp}")

    def assign_card(
        self,
        player: Player,
        card: int | None,
        device_id: str | None = None,
        *,
        is_admin: bool = False,
    ) -> None:
        self._check_not_paused()
        self.authorize(player, device_id, is_admin=is_admin)
        for other in self.players:
            if other is not player and other.strategy_card == card:
                other.strategy_card = None
        player.strategy_card = card
        if card:
            self.note(f"{player.name} took {card} · {STRATEGY_CARDS[card]}")

    def adjust_counter(
        self,
        player: Player,
        counter: str,
        delta: int,
        device_id: str | None = None,
        *,
        is_admin: bool = False,
    ) -> None:
        """Covers the trade goods / tactic / fleet / strategy +/- counters on
        player_card(). Not in SPEC.md's explicit method list, but F9 calls
        out "the counters in player_card" as one of the player-scoped
        actions that must gain an authorize() guard; today those counters
        are inline setattr() calls in main.py with nowhere to put that
        guard, so this pulls them into game.py alongside the other
        player-scoped mutators.
        """
        if counter not in {"trade_goods", "tactic", "fleet", "strategy"}:
            raise ValueError(f"unknown counter {counter!r}")
        self._check_not_paused()
        self.authorize(player, device_id, is_admin=is_admin)
        setattr(player, counter, max(0, getattr(player, counter) + delta))

    def pass_speaker(
        self, player: Player, device_id: str | None = None, *, is_admin: bool = True
    ) -> None:
        """Admin-or-current-speaker, matching who's allowed to hand off
        Speaker at the table (SPEC.md F9). `is_admin` defaults to True (not
        False) so pre-F9 callers — including T0's baseline tests — that
        don't pass identity keep the old unrestricted behavior; main.py
        always passes the real value from browser storage.
        """
        self._check_not_paused()
        current_speaker = self.players[self.speaker] if self.players else None
        if not is_admin and (current_speaker is None or current_speaker.claim_token != device_id):
            raise PermissionError("only admin or the current speaker can pass the speaker token")
        self.speaker = self.players.index(player)
        self.note(f"{player.name} is now Speaker")

    # -- turn clock (F2, F9, F12, F15) -----------------------------------------

    def start_turn(
        self, player: Player, device_id: str | None = None, *, is_admin: bool = False
    ) -> None:
        self._check_not_paused()
        self.authorize(player, device_id, is_admin=is_admin)
        self._start_turn(player)

    def _start_turn(self, player: Player) -> None:
        """Unauthenticated turn-start mechanics, used both by the public
        start_turn() (after its own authorize() check) and by next_turn()'s
        automatic turn-order advancement, which isn't "someone acting for
        player X" so much as the game clock ticking forward and shouldn't
        require player X's own device to authorize it.
        """
        self.end_turn()
        self.active = self.players.index(player)
        # F12: a turn always begins from the full configured duration, not
        # wherever a stale clock left off.
        player.turn_clock.reset(self.config.turn_seconds)
        player.turn_clock.start()

    def end_turn(self) -> None:
        self._check_not_paused()
        if self.active is not None:
            player = self.players[self.active]
            player.turn_clock.stop()
            # F15 — silent bookkeeping entry for the end-of-game "time per
            # player" report; not meant to clutter the human-readable log.
            self.note(
                f"{player.name}'s turn lasted {player.turn_clock.elapsed():.0f}s",
                kind="turn_span",
                player=player.name,
                payload={"duration": player.turn_clock.elapsed()},
                silent=True,
            )
        self.active = None

    def next_turn(self) -> None:
        """Advance to the next unpassed player in initiative order.

        F6: when nobody is left to act during the Action phase, auto-advance
        to Status instead of just ending the turn.
        """
        self._check_not_paused()
        order = [p for p in self.initiative_order() if not p.passed]
        if not order:
            self.end_turn()
            if self.phase == "Action":
                self.advance_phase(is_admin=True)
            return
        if self.active is None:
            self._start_turn(order[0])
            return
        current = self.players[self.active]
        if current in order:
            nxt = order[(order.index(current) + 1) % len(order)]
        else:
            nxt = order[0]
        self._start_turn(nxt)

    def toggle_pass(
        self, player: Player, device_id: str | None = None, *, is_admin: bool = False
    ) -> None:
        self._check_not_paused()
        self.authorize(player, device_id, is_admin=is_admin)
        player.passed = not player.passed
        self.note(f"{player.name} {'passed' if player.passed else 'un-passed'}")
        if player.passed and self.active is not None and self.players[self.active] is player:
            self.next_turn()

    # -- phases (F6, F9, F14) ---------------------------------------------------

    def set_phase(self, phase: str, *, is_admin: bool = True) -> None:
        """Admin-only (SPEC.md F9). `is_admin` defaults to True so pre-F9
        callers — T0's baseline tests, and advance_phase()'s own internal
        call after it has already checked admin — keep working; main.py
        always passes the real value.
        """
        self._check_not_paused()
        if not is_admin:
            raise PermissionError("only admin can change phase")
        if self.phase_clock.running:
            # F14 — silent bookkeeping entry for the end-of-game "time per
            # phase" report.
            self.note(
                f"{self.phase} phase lasted {self.phase_clock.elapsed():.0f}s",
                kind="phase_span",
                payload={"duration": self.phase_clock.elapsed()},
                silent=True,
            )
        self.phase_clock.reset()
        self.phase_clock.start()
        self.phase = phase
        self.note(f"{phase} phase")
        if phase != "Action":
            self.end_turn()

    def advance_phase(self, *, is_admin: bool = True) -> None:
        self._check_not_paused()
        if not is_admin:
            raise PermissionError("only admin can advance the phase")
        idx = PHASES.index(self.phase)
        if idx == len(PHASES) - 1:
            self.new_round(is_admin=True)
        else:
            self.set_phase(PHASES[idx + 1], is_admin=True)
            if self.phase == "Action":
                self.next_turn()

    def new_round(self, *, is_admin: bool = True) -> None:
        self._check_not_paused()
        if not is_admin:
            raise PermissionError("only admin can start a new round")
        self.round += 1
        for p in self.players:
            p.strategy_card = None
            p.passed = False
        # F7/F8 — per-round timer bookkeeping is scoped to the round, same as
        # strategy cards and passed flags.
        self.status_clocks.clear()
        self.agenda_clock = None
        # Routes through set_phase() (rather than setting self.phase
        # directly, as pre-refactor) so F14's phase_span accounting captures
        # the outgoing Agenda phase's duration at round rollover too.
        self.set_phase("Strategy", is_admin=True)
        self.note("New round begins")

    # -- F5: secondary strategy action timer -----------------------------------

    def start_secondary(self) -> None:
        self._check_not_paused()
        self.secondary_clock = Clock(duration=self.config.secondary_seconds)
        self.secondary_clock.start()

    def clear_secondary(self) -> None:
        self._check_not_paused()
        self.secondary_clock = None

    # -- F7: status phase timer per person --------------------------------------

    def start_status_clock(self, player: Player) -> None:
        self._check_not_paused()
        clock = self.status_clocks.setdefault(player.name, Clock())
        clock.reset(self.config.status_phase_seconds)
        clock.start()

    def stop_status_clock(self, player: Player) -> None:
        self._check_not_paused()
        if clock := self.status_clocks.get(player.name):
            clock.stop()

    # -- F8: agenda phase timers -----------------------------------------------

    def start_agenda_reveal(self) -> None:
        self._check_not_paused()
        self.agenda_clock = Clock(duration=self.config.agenda_reveal_seconds)
        self.agenda_clock.start()

    def start_agenda_vote(self, player: Player) -> None:
        """Reuses `status_clocks` (rather than a third parallel
        dict[str, Clock]) for per-player agenda vote timers — see SPEC.md
        F8/§6: both are "per-player countdown active during a phase," and
        the two phases don't run concurrently, but this is flagged as a
        scope-saving call worth confirming, not a rules requirement."""
        self._check_not_paused()
        clock = self.status_clocks.setdefault(player.name, Clock())
        clock.reset(self.config.agenda_vote_seconds)
        clock.start()

    # -- F10: pause ---------------------------------------------------------------

    def pause(self) -> None:
        if self.paused:
            return
        self.paused = True
        if self.active is not None:
            self.players[self.active].turn_clock.stop()
        self.phase_clock.stop()
        for clock in self.status_clocks.values():
            clock.stop()
        if self.secondary_clock:
            self.secondary_clock.stop()
        if self.agenda_clock:
            self.agenda_clock.stop()
        self.note("Game paused", kind="pause")

    def resume(self) -> None:
        if not self.paused:
            return
        self.paused = False
        if self.active is not None:
            self.players[self.active].turn_clock.start()
        self.phase_clock.start()
        self.note("Game resumed", kind="resume")
        # status/secondary/agenda clocks resume individually via their own
        # UI, since not all of them are necessarily meant to keep running
        # post-break.

    # -- F11: admin resets a player's turn timer -----------------------------------

    def reset_turn_clock(self, player: Player, *, is_admin: bool) -> None:
        self._check_not_paused()
        if not is_admin:
            raise PermissionError("only admin can reset another player's timer")
        player.turn_clock.reset(self.config.turn_seconds)
        if self.active is not None and self.players[self.active] is player:
            player.turn_clock.start()
        self.note(f"{player.name}'s turn timer reset", kind="turn_reset", player=player.name)

    # -- F16: config ----------------------------------------------------------------

    def update_config(self, is_admin: bool, **kwargs) -> None:
        self._check_not_paused()
        if not is_admin:
            raise PermissionError("only admin can change config")
        valid_fields = {f.name for f in fields(TimerConfig)}
        for key in kwargs:
            if key not in valid_fields:
                raise ValueError(f"unknown config field {key!r}")
        for key, value in kwargs.items():
            setattr(self.config, key, value)
        self.note("Timer settings updated", kind="config_change", payload=kwargs)

    # -- demo ------------------------------------------------------------------

    @classmethod
    def demo(cls) -> Game:
        game = cls()
        for name, faction, color in [
            ("Ana", "The Emirates of Hacan", "Yellow"),
            ("Bo", "The Federation of Sol", "Blue"),
            ("Cass", "The Nekro Virus", "Red"),
            ("Dev", "The Xxcha Kingdom", "Green"),
        ]:
            game.add_player(name, faction, color)
        game.log.clear()
        return game
