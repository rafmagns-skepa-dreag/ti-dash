# TI4 Dashboard — Feature Spec

Source of truth for the work described in `NOTES.md`. Each feature below (`F1`–`F16`)
maps to one NOTES bullet, in order. The spec assumes the existing three-layer
architecture from `README.md` and keeps its central rule intact:

```
game.py   long-living plain-Python state — no nicegui import, no I/O
db.py     (new) sqlite persistence   — no nicegui import
main.py   per-client UI, wires game.py + db.py together, owns all NiceGUI calls
```

`game.py` gains countdown/role/config concepts but stays a pure, synchronously
testable object graph. `db.py` is the only module allowed to touch disk.
`main.py` is the only module allowed to import `nicegui`.

---

## 0. Baseline: tests for what already exists

There are currently zero tests, and this spec adds nontrivial state machine
logic on top of `game.py`. **Before adding any feature below, write regression
tests for current behavior**, so later changes have a tripwire. This is `T0`
in the testing plan (§6) — do it first, as its own PR.

Cover, at minimum: `add_player`, `score` (clamping at `0` and `vp_goal`),
`assign_card` (stealing a card from another player), `pass_speaker`,
`start_turn`/`end_turn`/`elapsed` (banked time accumulates, only the active
player's clock runs), `next_turn` (skips passed players, wraps, ends turn when
everyone has passed), `toggle_pass` (auto-advances off the passing player),
`set_phase`/`advance_phase` (Agenda → new round), `new_round` (clears cards
and passes), and `Game.demo()`.

---

## 1. New concepts

### 1.1 `Clock` — countdown/count-up primitive

Every timer in NOTES (`F2`, `F5`, `F7`, `F8`, `F12`) is the same shape: a
duration that starts running, can be stopped/banked, resumed, reset, and read
either as elapsed time or as signed remaining time (negative once expired).
Rather than re-deriving `time.monotonic()` arithmetic four times as the code
currently does for the turn clock alone (`Game.elapsed`, `start_turn`,
`end_turn`), extract one primitive and reuse it everywhere:

```python
@dataclass
class Clock:
    duration: float | None = None   # seconds; None = stopwatch (no countdown)
    banked: float = 0.0             # accumulated seconds from prior run(s)
    started_at: float | None = None # time.monotonic() timestamp, or None if stopped

    def start(self) -> None: ...            # no-op if already running
    def stop(self) -> None: ...             # folds running time into `banked`
    def reset(self, duration: float | None = None) -> None: ...  # banked=0, stopped
    def elapsed(self) -> float: ...          # banked + (now - started_at if running)
    def remaining(self) -> float | None: ... # duration - elapsed(); None if no duration
    @property
    def running(self) -> bool: ...
```

`Game.elapsed(player)` today reimplements exactly this for the turn clock; it
becomes `player.turn_clock.elapsed()` (see §2). Existing behavior — banked
time survives across turns, only the active clock advances, N browsers can't
speed it up because it's timestamp-derived — is preserved by construction.

### 1.2 Seats and roles (`F9`)

Each `Player` gets a `claim_token: str | None`. A device "owns" a seat once
`claim_token` is set to that device's id; it can act for that player until it
unclaims. A separate `is_admin` capability, not tied to a seat, can act for
anyone and edit game state unconditionally.

Identity is a per-browser id, not a login: `main.py` reads/writes
`app.storage.browser["device_id"]` (a NiceGUI-managed signed cookie, stable
per browser, private per user — exactly "this phone"). Admin is a checkbox
behind a shared password compared against `TimerConfig.admin_password`; once
entered, `app.storage.browser["is_admin"] = True` for that browser.

`game.py` never sees NiceGUI storage — it only receives `device_id: str` and
`is_admin: bool` as plain arguments to mutation methods that need to check
authorization (see `Game.claim_seat` / `Game.unclaim_seat` /
`Game.authorize` below). This keeps the auth *check* pure and testable while
the auth *identity* stays in main.py where storage lives.

### 1.3 `TimerConfig` (`F16`)

```python
@dataclass
class TimerConfig:
    turn_seconds: float = 180.0            # F2/F12 — per-turn action timer
    secondary_seconds: float = 60.0        # F5 — secondary strategy action window
    status_phase_seconds: float = 120.0    # F7 — per-person status phase timer
    agenda_reveal_seconds: float = 60.0    # F8 — "when/after an agenda is revealed"
    agenda_vote_seconds: float = 90.0      # F8 — per-person vote timer
    admin_password: str = ""               # F9 — shared secret gating admin mode
    warn_at: tuple[float, ...] = (60.0, 10.0)  # F3 — seconds-remaining sound cues
```

One instance lives on `Game` (`Game.config: TimerConfig`). Every place that
currently hardcodes a duration reads it from here instead. Admin can edit it
live from a settings dialog; changes only affect clocks started afterward
(a running clock keeps its original `duration`, matching how changing an
oven's target temp mid-bake doesn't rewind the timer already ticking).

### 1.4 Persistence (`F13`)

New module `db.py`, stdlib `sqlite3` only:

```python
class EventStore:
    def __init__(self, path: str | Path) -> None: ...   # opens/creates db, runs migrations
    def append(self, entry: LogEntry) -> None: ...        # one INSERT
    def phase_totals(self, round: int | None = None) -> dict[str, float]: ...
    def player_totals(self) -> dict[str, float]: ...
    def close(self) -> None: ...
```

Schema:

```sql
CREATE TABLE IF NOT EXISTS events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       REAL    NOT NULL,   -- time.time(), wall clock, for human-readable audit
    round    INTEGER NOT NULL,
    phase    TEXT    NOT NULL,
    player   TEXT,               -- NULL for game-level events
    kind     TEXT    NOT NULL,   -- 'score' | 'phase_change' | 'phase_span' |
                                  -- 'turn_span' | 'assign_card' | 'pass_speaker' |
                                  -- 'toggle_pass' | 'claim_seat' | 'unclaim_seat' |
                                  -- 'pause' | 'resume' | 'config_change' | ...
    payload  TEXT                -- JSON blob, kind-specific
);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
```

`game.py` stays ignorant of sqlite. It exposes a single seam:

```python
@dataclass
class Game:
    ...
    sink: Callable[[LogEntry], None] | None = None   # set by main.py at startup
```

`Game.note(...)` (renamed/extended, see §2) builds a `LogEntry`, appends it to
`self.log` for on-screen display, and — if `sink` is set — calls
`sink(entry)`. `main.py` sets `game.sink = store.append` once at startup. This
is the same pattern `touch()`/`changed.emit()` already uses to keep `game.py`
decoupled from its observers, just applied to persistence instead of
rendering.

`F14`/`F15` (end-of-game reports) are then pure queries — `phase_totals()`
sums duration of `phase_span` events grouped by phase; `player_totals()` sums
`turn_span` events grouped by player. No new bookkeeping needed beyond
recording those two span kinds when a phase/turn ends.

---

## 2. `game.py` — concrete deltas

```python
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
    turn_clock: Clock = field(default_factory=Clock)      # replaces `banked: float`
    claim_token: str | None = None                          # F9

@dataclass
class LogEntry:
    round: int
    phase: str
    text: str
    kind: str = "note"
    player: str | None = None
    payload: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    silent: bool = False   # True = persisted but not shown in the session-log panel

@dataclass
class Game:
    players: list[Player] = field(default_factory=list)
    round: int = 1
    phase: str = "Strategy"
    speaker: int = 0
    vp_goal: int = 10
    active: int | None = None
    log: list[LogEntry] = field(default_factory=list)
    config: TimerConfig = field(default_factory=TimerConfig)   # F16
    paused: bool = False                                         # F10
    phase_clock: Clock = field(default_factory=Clock)            # F14
    status_clocks: dict[str, Clock] = field(default_factory=dict)   # F7, per player name
    secondary_clock: Clock | None = None                          # F5
    agenda_clock: Clock | None = None                             # F8
    sink: Callable[[LogEntry], None] | None = None
```

`turn_started: float | None` and `Player.banked: float` are removed; both
fold into `Player.turn_clock`. `Game.elapsed(player)` becomes
`player.turn_clock.elapsed()`; `remaining` becomes
`player.turn_clock.remaining()`, which is `None` until a duration is set and
goes negative past expiry (`F2`).

Mutating methods gain an `authorize(player, device_id, is_admin)` guard
(`F9`) — raises `PermissionError` unless `is_admin` or
`player.claim_token == device_id`. `main.py` catches this and shows
`ui.notify(..., color="negative")` instead of applying the change. Read-only
methods (`standings`, `initiative_order`, …) are unaffected.

---

## 3. Feature specs

### F1 — Thunder's Edge factions

Extend the `FACTIONS` tuple in `game.py` with Thunder's Edge's faction names.

**Blocked on data**: Thunder's Edge is not a product this spec has a verified
faction list for. Do not fabricate faction names — get the authoritative list
(box insert / rules PDF / BGG page) before implementing. Once supplied, this
is a pure data change: append to `FACTIONS`, no logic changes, so it needs no
new behavioral tests beyond `test_factions_are_unique` and
`test_faction_count_matches_expected` (§6) once the list is known.

### F2 — Countdown timer, goes negative

`Player.turn_clock.duration = game.config.turn_seconds`, set whenever
`start_turn` is called. `turn_banner()` in `main.py` renders
`remaining = player.turn_clock.remaining()`; when `remaining < 0` it shows
`-MM:SS` and switches the panel to an overtime style (e.g. red border) instead
of the faction color.

Tests (`Clock`, in `tests/test_timers.py`):
- `test_clock_remaining_none_without_duration`
- `test_clock_remaining_counts_down`
- `test_clock_remaining_goes_negative_past_expiry`
- `test_clock_stop_start_preserves_banked_time`
- `test_clock_reset_clears_banked_and_stops`

### F3 — Sound at configured times

Client-side only, no `game.py` change beyond exposing `config.warn_at`.
`turn_banner.refresh()` (called every second by the existing `ui.timer(1.0,
...)`) checks whether `remaining` has just crossed one of `config.warn_at`
thresholds (or `0`) since the previous tick, and if so calls
`ui.run_javascript(...)` to play a short beep (Web Audio `OscillatorNode`, no
asset file needed — keeps `db.py`/repo free of binary assets). Track
"just crossed" with a per-client `last_seen_remaining` local variable inside
the page closure, so multiple browsers don't need server coordination and a
browser that was in the background doesn't fire a backlog of beeps on
reconnect.

This is UI-only and not meaningfully unit-testable without a browser; cover
it with one `nicegui.testing.User` smoke test that the audio JS call happens
at least once during a timer that's forced to expire (see §6, `T-UI`), and
otherwise rely on manual verification (call out in PR description).

### F4 — Faction/color selection with presets

`add_player_dialog()` already lets a user pick faction and an unused color
from `COLORS`. "Presets" = named bundles of `(faction, color)` shown as
quick-pick chips above the manual selects, e.g. common faction/color pairings
from the box art. Add `FACTION_PRESETS: dict[str, str]` (faction → suggested
color) to `game.py`; the dialog pre-selects that color when a faction is
chosen but still lets the player override it. No new `Game` mutation method —
this only changes dialog defaults.

Tests:
- `test_faction_presets_reference_only_known_factions_and_colors` (asserts
  every key is in `FACTIONS` and every value is in `COLORS`, so a future edit
  to either table can't silently desync from the presets)

### F5 — Secondary strategy action timer

When a strategy card is assigned during the Strategy phase, the *primary*
player uses it now; every other player gets a window to declare a secondary
action. Add `Game.start_secondary(config duration)`:

```python
def start_secondary(self) -> None:
    self.secondary_clock = Clock(duration=self.config.secondary_seconds)
    self.secondary_clock.start()

def clear_secondary(self) -> None:
    self.secondary_clock = None
```

`main.py` shows a small countdown chip (same style as `turn_banner`) whenever
`game.secondary_clock is not None`, with a manual "clear" (admin or any
un-claimed... no — any seated player, since it's shared) dismiss button.
Triggered from `assign_card`'s existing card-picked branch in
`player_card()`.

Tests:
- `test_start_secondary_creates_running_clock_with_configured_duration`
- `test_clear_secondary_resets_to_none`
- `test_secondary_clock_independent_of_turn_clock` (starting one doesn't
  pause/reset the other)

### F6 — Auto-advance Action → Status when all pass

`Game.next_turn()` already special-cases "no unpassed players left":
today it just calls `end_turn()`. Change it to also advance the phase when
that emptiness happens *during the Action phase*:

```python
def next_turn(self) -> None:
    order = [p for p in self.initiative_order() if not p.passed]
    if not order:
        self.end_turn()
        if self.phase == "Action":
            self.advance_phase()
        return
    ...
```

Guard against double-advancing: `advance_phase()` from Status onward doesn't
touch `next_turn`, so no re-entrancy risk. `toggle_pass` already routes
through `next_turn`, so no other call site changes.

Tests:
- `test_last_player_passing_advances_to_status_phase`
- `test_passing_during_non_action_phase_does_not_advance` (n/a today since
  passing is only meaningful in Action, but assert `toggle_pass` outside
  Action doesn't touch `phase`)
- `test_all_pass_then_new_round_resets_passed_flags` (regression: `new_round`
  must still clear `passed` so the next Action phase isn't pre-empty)

### F7 — Status phase timer per person

`Game.status_clocks: dict[str, Clock]` keyed by player name (§2). On
entering Status phase (`set_phase("Status")`), lazily create+start a clock
for whichever player is "current" for status resolution — status phase in
TI4 isn't strictly turn-order gated the way Action is, so this spec treats it
as one clock per player, started/stopped individually, not a single
`active`-index turn cursor:

```python
def start_status_clock(self, player: Player) -> None:
    clock = self.status_clocks.setdefault(player.name, Clock())
    clock.reset(self.config.status_phase_seconds)
    clock.start()

def stop_status_clock(self, player: Player) -> None:
    if clock := self.status_clocks.get(player.name):
        clock.stop()
```

`status_clocks` is cleared in `new_round()` alongside the existing
`strategy_card`/`passed` reset.

Tests:
- `test_start_status_clock_creates_and_starts_per_player`
- `test_stop_status_clock_bank_time`
- `test_status_clocks_cleared_on_new_round`
- `test_status_clock_independent_per_player` (starting Bo's doesn't affect
  Ana's)

### F8 — Agenda phase timers

Two independent clocks on `Game`, mirroring `secondary_clock`:

```python
def start_agenda_reveal(self) -> None:
    self.agenda_clock = Clock(duration=self.config.agenda_reveal_seconds)
    self.agenda_clock.start()

def start_agenda_vote(self, player: Player) -> None:
    clock = self.status_clocks.setdefault(player.name, Clock())  # reuse per-player map
    clock.reset(self.config.agenda_vote_seconds)
    clock.start()
```

Reusing `status_clocks` for per-player agenda vote timers (rather than adding
a third parallel `dict[str, Clock]`) is deliberate: both are "per-player
countdown active during a phase," and NOTES doesn't ask for them to coexist
(you're never voting and resolving status simultaneously). If that turns out
to be wrong once this is built, split it into `agenda_vote_clocks` — flag
this as a design call worth confirming with the user during implementation,
not baked in silently.

Tests:
- `test_start_agenda_reveal_creates_running_clock`
- `test_start_agenda_vote_reuses_per_player_clock_slot`
- `test_agenda_clocks_cleared_on_new_round`

### F9 — Seat claim / unclaim / admin override

```python
def claim_seat(self, player: Player, device_id: str) -> None:
    if player.claim_token is not None and player.claim_token != device_id:
        raise PermissionError(f"{player.name}'s seat is already claimed")
    player.claim_token = device_id
    self.note(f"{player.name}'s seat claimed", kind="claim_seat", player=player.name)

def unclaim_seat(self, player: Player, device_id: str, *, is_admin: bool = False) -> None:
    if not is_admin and player.claim_token != device_id:
        raise PermissionError("not your seat")
    player.claim_token = None
    self.note(f"{player.name}'s seat unclaimed", kind="unclaim_seat", player=player.name)

def authorize(self, player: Player, device_id: str, *, is_admin: bool) -> None:
    if not is_admin and player.claim_token != device_id:
        raise PermissionError(f"not authorized to act for {player.name}")
```

Every existing mutation that's "a player's own action" (`score`,
`assign_card` for yourself, `toggle_pass` for yourself, `start_turn` for
yourself, the counters in `player_card`) calls `self.authorize(player,
device_id, is_admin=is_admin)` first. `pass_speaker`, `set_phase`,
`advance_phase`, `new_round`, config edits, and admin timer resets (`F11`)
require `is_admin` only (any seated player *can* still hand off Speaker to
someone else per the rules — treat `pass_speaker` as admin-or-current-speaker,
matching who's allowed to do it at the table).

`main.py` passes `device_id`/`is_admin` from browser storage into every
`on_click` that currently calls a `game.*` mutator directly, and wraps the
call in a `try/except PermissionError as e: ui.notify(str(e), color="negative")`.
Unclaimed seats show a "Claim seat" button in place of the action row;
claimed-by-others seats show name/faction but no action buttons, only a
lock icon.

Tests:
- `test_claim_seat_sets_token`
- `test_claim_seat_twice_same_device_is_idempotent`
- `test_claim_seat_by_second_device_raises`
- `test_unclaim_seat_requires_owning_device_or_admin`
- `test_authorize_allows_owning_device`
- `test_authorize_allows_admin_for_any_player`
- `test_authorize_rejects_other_device`
- `test_score_raises_without_authorization`
- `test_pass_speaker_requires_admin_or_current_speaker`

### F10 — Pause button

```python
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
    # status/secondary/agenda clocks resume individually via their own UI,
    # since not all of them are necessarily meant to keep running post-break
```

Stopping (not resetting) every running clock is what makes pause resumable
without losing elapsed time — this is the same `banked` mechanism `Clock`
already provides for turn switches, applied game-wide. All mutating methods
besides `pause`/`resume`/read-only views raise `RuntimeError("game is
paused")` when `self.paused` — cheapest way to guarantee a break doesn't let
someone sneak in a VP change that skews `F14`/`F15` numbers.

Tests:
- `test_pause_stops_active_turn_clock`
- `test_resume_restarts_active_turn_clock_without_losing_banked_time`
- `test_pause_is_idempotent`
- `test_score_raises_while_paused`
- `test_pause_and_resume_noop_when_already_in_that_state`

### F11 — Admin resets a player's turn timer

```python
def reset_turn_clock(self, player: Player, *, is_admin: bool) -> None:
    if not is_admin:
        raise PermissionError("only admin can reset another player's timer")
    player.turn_clock.reset(self.config.turn_seconds)
    if self.active is not None and self.players[self.active] is player:
        player.turn_clock.start()
    self.note(f"{player.name}'s turn timer reset", kind="turn_reset", player=player.name)
```

Tests:
- `test_reset_turn_clock_requires_admin`
- `test_reset_turn_clock_on_active_player_restarts_running`
- `test_reset_turn_clock_on_inactive_player_stays_stopped`

### F12 — Timer is per-turn

Already true in spirit (`start_turn` calls `end_turn` first, which banks the
outgoing player's time and clears `active`/clock state) — `F2`'s `Clock`
refactor keeps this. The one gap: today a fresh `Player.banked` starts at
`0.0`; make sure `Clock()` (no args) also defaults to a stopped, zero-banked,
no-duration clock, and that `start_turn` sets
`player.turn_clock.reset(self.config.turn_seconds)` before starting, so a
turn always begins from the full configured duration rather than continuing
wherever a stale clock left off (relevant once `F11`'s reset exists and once
timers are configurable, since a mid-game config change shouldn't retroactively
resize a clock already in progress).

Tests:
- `test_start_turn_always_resets_duration_to_current_config`
- `test_changing_config_mid_turn_does_not_resize_running_clock`

### F13 — SQLite persistence of all actions

Covered in §1.4/§2. Implementation notes:

- `main.py` opens `EventStore(Path("ti-dash.db"))` at module load (sibling to
  `game.py`/`main.py`, added to `.gitignore` — it's local session data, not
  source), assigns `game.sink = store.append`, and calls `store.close()` in
  an `app.on_shutdown` handler.
- `Game.note()` signature grows to `note(self, text, *, kind="note",
  player=None, payload=None, silent=False)`, builds a `LogEntry`, appends to
  `self.log` (trimmed to 60 as today) unless a caller only wants persistence
  without UI clutter (`silent=True` — used for `phase_span`/`turn_span`
  bookkeeping entries, which are numerous and not meant for the human log).
  Every existing `self.note(...)` call site keeps working since `text` stays
  the first positional arg.
- `EventStore.append` must not raise into `game.py`'s mutation path if disk
  write fails (a full disk shouldn't crash the dashboard mid-game) — catch
  and log to stderr inside `EventStore.append` itself, keep `game.py` fully
  unaware of the failure mode.

Tests (`tests/test_persistence.py`, using `tmp_path`):
- `test_event_store_creates_db_file_and_schema`
- `test_append_persists_row_with_expected_columns`
- `test_append_survives_reopen` (write, close, reopen same path, query)
- `test_phase_totals_sums_phase_span_events_by_phase`
- `test_player_totals_sums_turn_span_events_by_player`
- `test_append_failure_does_not_raise` (point at an unwritable path, assert
  no exception propagates)
- `test_game_sink_receives_every_mutation` (wire a `list.append`-backed fake
  sink into a `Game`, drive it through a handful of mutations, assert the
  expected `kind`s appear in order) — this is the contract test that keeps
  `game.py` and `db.py` decoupled but compatible.

### F14 — Time spent per phase, end of game

`Game.set_phase()` currently just relabels `self.phase` and calls
`end_turn()`. Extend it to bank `phase_clock` under the *outgoing* phase's
name before switching:

```python
def set_phase(self, phase: str) -> None:
    if self.phase_clock.running:
        self.note(
            f"{self.phase} phase lasted {self.phase_clock.elapsed():.0f}s",
            kind="phase_span", payload={"duration": self.phase_clock.elapsed()},
            silent=True,
        )
    self.phase_clock.reset()
    self.phase_clock.start()
    self.phase = phase
    self.note(f"{phase} phase")
    if phase != "Action":
        self.end_turn()
```

End-of-game report is a `main.py` view (dialog or `/report` page) that reads
`store.phase_totals()` — a simple bar list, phase name → minutes, no new
`game.py` state needed beyond what's already logged.

Tests:
- `test_set_phase_emits_phase_span_for_outgoing_phase`
- `test_set_phase_does_not_emit_span_on_first_call` (no prior phase clock
  running yet)
- `test_phase_clock_restarts_on_every_phase_change`

### F15 — Time spent per player, end of game

Mirror of `F14` at `end_turn()`:

```python
def end_turn(self) -> None:
    if self.active is not None:
        player = self.players[self.active]
        player.turn_clock.stop()
        self.note(
            f"{player.name}'s turn lasted {player.turn_clock.elapsed():.0f}s",
            kind="turn_span", player=player.name,
            payload={"duration": player.turn_clock.elapsed()},
            silent=True,
        )
    self.active = None
```

Report view reads `store.player_totals()`. Because `turn_span` is emitted
every time a turn *ends* (not just at game end), the report is queryable
mid-game too ("who's been slow this round") — not required by NOTES but
falls out for free and is worth mentioning in the PR description rather than
building separately.

Tests:
- `test_end_turn_emits_turn_span_with_player_name`
- `test_end_turn_with_no_active_player_emits_nothing`
- `test_multiple_turns_same_player_accumulate_in_report` (integration-ish:
  drive `Game` + a fake sink through two of the same player's turns, assert
  `player_totals()`-equivalent aggregation sums both)

### F16 — Config options

`TimerConfig` (§1.3) plus an admin-only settings dialog in `main.py` (gear
icon in `round_header()`) with a field per `TimerConfig` attribute, saving
via `game.update_config(**kwargs)`:

```python
def update_config(self, is_admin: bool, **kwargs) -> None:
    if not is_admin:
        raise PermissionError("only admin can change config")
    for key, value in kwargs.items():
        setattr(self.config, key, value)
    self.note("Timer settings updated", kind="config_change", payload=kwargs)
```

Tests:
- `test_update_config_requires_admin`
- `test_update_config_applies_all_given_fields`
- `test_update_config_rejects_unknown_field` (use `dataclasses.fields` to
  validate keys before `setattr`, so a typo doesn't silently create a new
  attribute NiceGUI never reads)

---

## 4. `main.py` — UI delta summary

Not exhaustive line-by-line, but the shape of the changes:

- Module load: create `store = EventStore(...)`, `game.sink = store.append`,
  register `app.on_shutdown(store.close)`.
- `@ui.page("/")`: read/create `device_id` from `app.storage.browser`;
  read `is_admin` the same way; pass both into every mutating `on_click`.
- `player_card()`: claim/unclaim button when unowned/owned-by-me; hide action
  row (score buttons, counters, take-turn, pass) when claimed by someone else
  and `not is_admin`; wrap each mutating call in the `PermissionError`/
  `RuntimeError` (paused) `try/except` → `ui.notify`.
- `turn_banner()`: countdown instead of count-up; overtime styling when
  negative; sound-cue JS calls at `config.warn_at` crossings.
- `round_header()`: pause/resume toggle button; settings-gear button opening
  the config dialog; admin-login entry point if `not is_admin`.
- New: `status_banner()`, `secondary_banner()`, `agenda_banner()` — same
  visual pattern as `turn_banner()`, reading the corresponding `Game` clock(s).
- New: `report_dialog()` — reads `store.phase_totals()` /
  `store.player_totals()`, rendered as two small bar lists. Triggered from a
  "Session report" button, always visible (useful mid-game too, per `F15`
  note above) but most relevant once `game.winner()` is set.

---

## 5. Testing strategy

### Tooling

```toml
[dependency-groups]
dev = ["pytest>=8"]
```

`pytest.ini` / `[tool.pytest.ini_options]` in `pyproject.toml`:
`testpaths = ["tests"]`. All new tests live under `tests/`, one file per
concern as referenced above:

```
tests/
  conftest.py            # shared fixtures
  test_game_baseline.py  # T0 — regression coverage for pre-existing behavior
  test_timers.py         # Clock + turn/secondary/status/agenda clocks
  test_phases.py         # advance_phase, auto-advance-on-all-pass, phase spans
  test_roles.py          # claim/unclaim/authorize
  test_pause.py
  test_config.py
  test_persistence.py    # db.py, tmp_path-based
  test_reports.py        # phase_totals/player_totals against a fake/real store
```

### Making time deterministic

`Clock` calls `time.monotonic()`. Real `time.sleep()` in tests is slow and
flaky under load; instead, `conftest.py` provides:

```python
@pytest.fixture
def fake_clock(monkeypatch):
    """Controllable replacement for time.monotonic() across game.py."""
    state = {"t": 0.0}
    monkeypatch.setattr("game.time.monotonic", lambda: state["t"])
    def advance(seconds: float) -> None:
        state["t"] += seconds
    return advance
```

Every timer test drives time via `fake_clock(5.0)` rather than sleeping. Wall
clock (`time.time()`, used only for `LogEntry.ts`) doesn't need
determinism — tests assert its presence/type, not its value.

### DB tests

`EventStore` tests use `tmp_path / "events.db"` for on-disk round-trip tests,
and `sqlite3.connect(":memory:")` (via a constructor override or a
`EventStore.in_memory()` classmethod) for fast schema/query unit tests that
don't need the disk-durability guarantee itself.

### `game.py` ↔ `db.py` contract

`test_game_sink_receives_every_mutation` (§F13) is the one test that must
survive any future refactor of either module: it proves `game.py` can drive
persistence through nothing but the `sink` callable, with no import of
`db.py` inside `game.py`. If this test ever needs a change to pass, that's a
signal the decoupling is eroding — flag it rather than adjusting the test to
match.

### UI smoke tests (lower priority)

`nicegui.testing.User` (NiceGUI's async test harness) can drive `main.py`'s
actual page for a handful of end-to-end checks — worth having but not a
priority next to the `game.py`/`db.py` unit tests above, since it requires an
async test runner (`pytest-asyncio`) and is slower/more brittle:

- `test_page_loads_without_error`
- `test_claim_seat_hides_action_buttons_for_other_devices`
- `test_sound_cue_fires_near_expiry` (the one place `F3` gets any automated
  coverage — assert the expected `ui.run_javascript` call happens, not that
  audio is audible)

Add these in a later PR once the `game.py`/`db.py` suite is solid; call out
explicitly in that PR's description which paths are still manual-only (audio
actually audible, multi-browser sync under real network latency).

---

## 6. Open questions / non-goals

- **F1 faction list is unverified** — get the real Thunder's Edge faction
  names before touching `FACTIONS`; don't guess.
- **F8's reuse of `status_clocks` for agenda votes** is a scope-saving call,
  not a rules requirement — confirm it doesn't conflict once built (see F8).
- **Admin auth is a single shared password**, not per-admin accounts — matches
  "one admin runs the table" from NOTES; revisit only if multiple admins with
  distinct identities turns out to matter.
- **No cross-session game resume** — `db.py` is an audit/report log, not a
  snapshot/restore mechanism. `README.md` already flags in-memory state as a
  known limitation; rebuilding `Game` from the `events` table on restart is a
  plausible future extension of `F13` but is out of scope here.
- **Sound cues use synthesized beeps via Web Audio**, not bundled audio
  files, to avoid adding binary assets to the repo — revisit if a specific
  sound is requested.

---

## 7. Suggested implementation order

1. `T0` — baseline regression tests for current `game.py` (own PR, no
   behavior change).
2. `Clock` + `F2`/`F12` (countdown, per-turn reset) + tests.
3. `F16` config (`TimerConfig`) — needed by nearly everything after this.
4. `F9` seats/roles + `F10` pause + `F11` admin reset — the authorization
   layer, needed before exposing more actions to untrusted devices.
5. `F6` auto action→status advance.
6. `F7` status timers, `F8` agenda timers, `F5` secondary timer — same
   `Clock` pattern, mostly mechanical once §2–4 land.
7. `F13` persistence (`db.py`) + `F14`/`F15` reports.
8. `F3` sound cues, `F4` faction/color presets, `F1` Thunder's Edge factions
   (blocked on data) — lowest risk, do last.
