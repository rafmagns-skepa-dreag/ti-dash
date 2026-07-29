# TI4 Dashboard — Design Spec

A shared, real-time dashboard for an in-person game of **Twilight Imperium 4**
(with the *Prophecy of Kings* and *Thunder's Edge* expansions). Runs on a home
server; the group opens it on a shared TV and on each player's phone, all
viewing and controlling the same live game state. Built with **Litestar +
Datastar** in Python. Built from scratch — no prior code, specs, or notes in
the repository history are reused.

## Goals

- Track how long players take, per timed segment, and **record every segment to
  the database** (round, turn, context, duration) — the primary feature.
- Drive the full TI4 phase structure with **admin-gated transitions** between
  phases (an explicit "pause" before each phase starts).
- Track both game orderings: **seating/speaker order** and **initiative order**.
- Track player faction, color, and victory points.
- Let each player act only for their own seat; let an admin edit everything.
- Provide a global pause for meal breaks.

## Non-goals (v1)

- No accounts/logins (identity is a per-browser cookie).
- No "New game" UI, no multi-game management, no historical stats screens.
- No experienced/new player time buckets yet (designed-for; not built).
- No concurrent per-player Status-phase timers yet (single shared timer).
- No sound cues.
- No 3–4-player two-cards-each Strategy variant (one card per player only).

## Deployment & runtime model

- Single authoritative `Game` instance in memory on the server.
- Multiple devices (TV + phones) on the LAN, all synced in real time via
  Datastar SSE.
- SQLite for durable state. On startup, if the database/tables do not exist,
  create them; if a saved snapshot exists, load it; otherwise start empty.
- The **live running clock is disposable** across restarts; the game state and
  the append-only turn records are durable.

## Architecture — three layers

```
domain/       pure Python: Game, Player, Clock, phase machine, orderings,
              authorization, reference data. No Litestar, no SQLite, no I/O.
persistence/  the only module that touches SQLite (aiosqlite): snapshot
              save/load + append-only turn records.
web/          Litestar routes, Datastar SSE broadcast, htpy-style HTML
              components. Supplies identity/admin from cookies; enforces
              nothing itself beyond delegating to the domain authorization.
```

The seam is strict: the domain is synchronously unit-testable with no browser
and no disk. Persisted mutations flow out through a `pending_records` list the
web layer drains; the domain never imports sqlite.

## 1. Domain data model (`domain/`)

### `Clock` — the single timing primitive (timestamp-derived)

Every timer in the app is this same shape, so `time.monotonic()` arithmetic is
written once. Being timestamp-derived (not ticker-incremented) means N connected
browsers cannot make a clock run N times too fast.

Fields:
- `duration: float | None` — the budget in seconds (`None` = stopwatch).
- `banked: float` — accumulated seconds from prior running intervals, frozen
  while stopped.
- `started_at: float | None` — `time.monotonic()` timestamp while running, else
  `None`.

Behavior:
- `start()` — sets `started_at` if not already running.
- `stop()` — folds running time into `banked`, clears `started_at`.
- `reset(duration=None)` — `banked=0`, stopped, new duration.
- `elapsed()` — `banked + (now − started_at if running)`.
- `remaining()` — `duration − elapsed()`; goes **negative** past expiry (no
  floor); `None` if no duration.
- `running` — `started_at is not None`.

`(banked, started_at)` fully captures "time used" and "is the meter running."
`banked` is what survives a pause/resume and what gets recorded when a segment
ends. `started_at is None` is exactly the not-running state (before a segment
begins, during a global pause, or after it ends).

The web layer derives from the clock what a client needs to tick locally: an
`ends_at` wall-clock timestamp (only meaningful while running) plus
`running`/`paused`.

### `Player`

- `name: str`, `faction: str`, `color: str`, `vp: int`
- `strategy_card: int | None` — the card number **is** the initiative value;
  unpicked sorts last.
- `passed: bool` — has passed for the current Action phase.
- `seat: int` — fixed position in the table/speaker order.
- `claim_token: str | None` — the `device_id` that owns this seat, or `None`.

No live per-player timing totals are stored; totals are aggregations over the
`turn_records` table (single source of truth).

### `Game` — the authoritative object

- `players: list[Player]`, `speaker: int` (seat index), `round: int`,
  `vp_goal: int` (default 10).
- `phase` — `Strategy | Action | Status | Agenda`, plus an `awaiting_admin`
  gate flag marking "phase work complete, waiting for the admin to start the
  next phase."
- `active: int | None` — whose turn it is now.
- `paused: bool` — global meal-break pause.
- `agenda_enabled_this_round: bool` — admin toggle for whether Agenda runs.
- Context clocks: `strategy_pick`, `action` (turn), `secondary`, `status`
  (shared), `agenda_window`, `agenda_vote`.
- `config: TimerConfig`.
- `pending_records: list[TurnRecord]` — drained by the web layer.

### Two orderings (both first-class)

- **Seating/speaker order:** `players` sorted by `seat`, rotated to begin at
  `speaker`. Drives Strategy-phase card picks and Agenda voting.
- **Initiative order:** `players` sorted by `strategy_card` (unpicked last).
  Drives Action-phase turns.

### Reference data (`domain/reference.py`)

- `COLORS`: the standard 8 — Red, Blue, Green, Yellow, Purple, Orange, Pink,
  Black.
- `STRATEGY_CARDS`: 1–8 (Leadership, Diplomacy, Politics, Construction, Trade,
  Warfare, Technology, Imperial).
- `FACTIONS`: base game + *Prophecy of Kings* populated; a clearly-marked,
  empty **Thunder's Edge** section with a comment for the user to fill in.
  Built fresh, not lifted from old repository files.

## 2. Phase state machine

The game cycles through phases but **never auto-advances** — each transition
waits on an admin "Start [next phase]" button (the inter-phase pause). This is
modeled with the `awaiting_admin` gate: when a phase's work completes, the game
sets the gate and surfaces the button; the admin's click performs the
transition.

**Strategy phase**
- App walks players in **speaker order**. The current picker's
  `strategy_pick` clock runs.
- Picker chooses a card → record a `strategy_pick` segment → advance to the
  next picker.
- One card per player. When all players have a card → gate: *Start Action
  phase*.

**Action phase**
- Turn order = **initiative order**. `active` = first in initiative.
- The active player's `action` clock runs. On their turn they either take an
  action and end their turn, or **pass**.
- Ending a turn → record an `action` segment (round, turn, player) → advance to
  the next non-passed player in initiative order (wraps).
- **Secondary window:** during a turn a "strategic action" opens the secondary
  window; the `secondary` clock runs for reacting players; recorded separately
  (context `secondary`). Modeled as a start/stop sub-event within the turn.
- Once a player passes (`passed=True`) they are skipped for the rest of the
  round. When all have passed → gate: *Start Status phase*.

**Status phase**
- A **single shared** `status` clock (concurrent per-player timers deferred).
  When the segment ends it is recorded (context `status`, no per-player seat).
- Gate: the admin sees the **Agenda toggle** (`agenda_enabled_this_round`) and
  chooses *Start Agenda phase* or *Start next round*.

**Agenda phase** (only if enabled this round)
- Resolves agendas one at a time. For each:
  - **When/after window** — deciding whether to play an action card →
    `agenda_window` clock (context `agenda_window`).
  - **Voting** in **speaker order** (Speaker votes last) — per-player
    `agenda_vote` clock (context `agenda_vote`).
- After the agendas → gate: *Start next round*.

**New round** (the gate transition after Status or Agenda)
- `round += 1`; clear every `strategy_card` and `passed`; reset context clocks;
  return to Strategy phase (behind its own start gate). Speaker persists
  (changes only via admin/Politics), as in the real game.

**Global pause** (meal break) overrides everything: stops whichever context
clock is running; resume restarts it from its banked value. Game-mutating
actions are blocked while paused.

## 3. Timers, recorded data & config

### Timed contexts

| Context | Order it follows | Recorded |
|---|---|---|
| `strategy_pick` | speaker order | yes |
| `action` (main turn) | initiative order | yes |
| `secondary` | reacting players | yes |
| `status` (shared) | — | yes |
| `agenda_window` | — | yes |
| `agenda_vote` | speaker order | yes |

### Recorded turn data (`turn_records`, append-only)

When a timed segment ends (including force-end via advancing), one immutable
row is appended:
- `sequence` — monotonic ordering across all recorded segments (PK).
- `round` — the TI4 game round.
- `turn` — the player's action-phase turn number (where applicable).
- `phase`, `context`.
- `player_name`, `seat` — nullable for shared timers (status).
- `duration_seconds` — the **full actual elapsed time**, even when over budget
  (no clamping).
- `over_budget: bool`.
- `ended_at` — wall clock.

Naming convention throughout: **`round`** = a full TI4 game round; **`turn`** =
a single player's action-phase turn (a round contains many turns); **`sequence`**
= the monotonic per-record counter across all segments.

### Overtime

When `remaining()` goes negative the clock keeps counting. The UI shows negative
time in a warning color. No auto-pass, no forced end. `over_budget=true` plus the
full signed/actual `duration` capture it.

### Config (`TimerConfig`, admin-editable, persisted)

One budget per context: `strategy_pick_seconds`, `action_seconds`,
`secondary_seconds`, `status_seconds`, `agenda_window_seconds`,
`agenda_vote_seconds` — plus `vp_goal` and `admin_password`.

Future **experienced/new** buckets slot in cleanly: each budget becomes a small
`{experienced, new}` pair and the clock's `duration` is chosen by the active
player's bucket. Designed-for, not built now.

## 4. Seats, claiming & admin

**Identity** is per-browser, not a login. On first visit the server issues a
signed cookie holding a random `device_id` (stable per browser, private to that
device).

**Claiming a seat**
- Each seat shows a "Claim" button when unclaimed; tapping sets
  `Player.claim_token = device_id`.
- A device may act **only** for the seat it owns: end its own turn, pass, adjust
  its own VP, pick its own strategy card, cast its own vote.
- "Release seat" clears the token. A seat owned by another device is not
  claimable (admin can force-reassign).
- **One seat per device** — claiming a second releases the first.

**Admin mode**
- A device enters admin mode by submitting the shared `admin_password`, flipping
  a cookie-backed `is_admin` flag that survives reloads.
- Admin can do everything for anyone: end/advance turns, override the active
  player, edit any VP/faction/color/seat order/speaker, reassign or force-release
  seats, trigger phase transitions, toggle the agenda phase, edit config, and
  drive the global pause. Admin does not need to claim a seat.

**Authorization rule** (enforced in the domain layer): every player-scoped
mutation takes `(device_id, is_admin)` and succeeds only if `is_admin` or
`device_id == player.claim_token`. The web layer supplies these from the cookie
and additionally hides controls the device cannot use, but the domain is the
real gate.

## 5. Web layer & Datastar sync (`web/`)

**App shape:** a Litestar app serving one dashboard page, a set of action
endpoints, and one SSE stream. The single `Game` instance is guarded by an
`asyncio.Lock` so mutations are serialized.

**Sync loop:**
1. Each device holds an SSE connection to `GET /events`. The server keeps a set
   of per-client async queues (subscribers).
2. A user action is a `POST /action/<name>` (Datastar `@post(...)`), carrying
   the cookie `device_id` + `is_admin`.
3. Handler: acquire lock → authorize → mutate `Game` → drain `pending_records`
   and persist + rewrite snapshot → render affected HTML fragment(s) →
   **broadcast** them to every subscriber queue.
4. Each SSE stream drains its queue, emitting Datastar `patch-elements` events;
   every device's DOM updates near-instantly.

There is one code path for "something changed": render + broadcast. First page
load renders the full dashboard; everything after is fragment patches (player
cards, active-timer panel, phase/gate bar, log).

**Timers (client-tick):** a timer element is rendered with the clock's
authoritative state as data — `ends_at` (epoch ms), `running`, `paused` — into a
Datastar signal. A 1-second client-side interval updates a local `now` signal;
the displayed countdown is a derived expression (`ends_at − now`), formatted,
turning to a warning color and showing negative past zero. The **server only
re-pushes a timer when its state changes** (start / stop / pause / reset / new
budget), never once per second. All devices tick off the same authoritative
`ends_at`, so they stay in lockstep with no per-second server traffic.

**Rendering:** server-side HTML via **htpy-style Python components** (in-language,
unit-testable), kept small and focused. Broadcasts patch regions, not the whole
page.

**Layout** (one responsive page):
- **TV / wide:** full board — seating order, initiative order, the big active
  timer, VP standings, phase/gate bar, pause state.
- **Phone / narrow:** the device's own seat controls front and center (claim,
  end turn, pass, VP, card pick, vote), plus a compact "whose turn + timer" view.

The exact TV/phone split will be refined once it is running.

## 6. Persistence (`persistence/`)

The only module that touches SQLite (via `aiosqlite`). Two pieces:

- **`game_state`** — a single-row snapshot table holding a JSON serialization of
  the durable `Game`: players (name, faction, color, vp, seat, strategy_card,
  passed, claim_token), speaker, round, phase + gate state,
  `agenda_enabled_this_round`, and `config`. Rewritten on each persisted
  mutation. **Excludes live clock timestamps** — on load, all clocks reconstruct
  stopped/zeroed, so a restart resumes the game but discards any mid-run timer.
- **`turn_records`** — append-only, schema per §3. Never rewritten; survives
  restarts; feeds future stats.

**Startup:** connect to SQLite; if the database/tables do not exist, create
them. If a snapshot exists, load it (clocks stopped); otherwise start an empty
game. There is no "New game" UI in v1.

Persisted mutations reach disk via the domain's `pending_records` list, drained
by the web handler after each action; the domain never imports sqlite.

## 7. Testing (TDD)

Priority order:

1. **Domain unit tests** (the bulk, fast, no I/O): `Clock`
   (banked/stop/resume/negative), both orderings, the full phase machine (gates,
   one-card picks, initiative turns, pass/skip/wrap, shared status, optional
   agenda, new-round reset), authorization (seat vs admin), over-budget
   recording, global pause blocking mutations.
2. **Persistence tests:** snapshot round-trip; restart discards live clocks but
   keeps game + records; append-only records; create-on-missing at startup.
3. **Web integration tests** (Litestar test client, lighter): an action mutates
   + authorizes correctly and broadcasts a fragment; an unauthorized action is
   rejected; the SSE stream emits on change.
