# Twilight Imperium 4 Dashboard

A shared, real-time dashboard for an in-person game of Twilight Imperium 4
(with the Prophecy of Kings and Thunder's Edge expansions). Runs on a home
server; open it on a shared TV and on each player's phone — every change on
one device appears on all of them via Datastar SSE.

Tracks per-segment turn timers (recorded to SQLite), the full phase flow with
admin-gated transitions, seating/speaker and initiative orderings, player
faction/color, and victory points. Includes a global pause for meal breaks.

## Run

```bash
uv run python -m ti_dash
```

Then open `http://<your-lan-ip>:8000` on every device at the table.

## How it works

Three layers:

- `ti_dash/domain/` — pure game rules (Game, Player, Clock, phase machine,
  orderings, authorization). No web or database imports; fully unit-tested.
- `ti_dash/persistence/` — SQLite (via aiosqlite): a durable game snapshot
  plus an append-only `turn_records` table. The database and tables are
  created automatically on first run. Game state survives a restart; the
  live running timer is intentionally not restored.
- `ti_dash/web/` — the Litestar app: htpy-rendered HTML, Datastar SSE
  fan-out to every connected device, and per-action endpoints.

## Seats and admin

Each device claims a player seat (a per-browser cookie) and may act only for
that seat. Admin mode is entered with a shared password
(`TimerConfig.admin_password`, default `password`) and can edit anything for
anyone.

## Configuration

Timer budgets and the admin password live in `TimerConfig`
(`ti_dash/domain/config.py`). Thunder's Edge faction names are populated in
`ti_dash/domain/reference.py` (a marked section to fill in).

## Tests

```bash
uv run pytest
```
