# Twilight Imperium dashboard — NiceGUI

A shared game tracker for a table of 3–8 players. Open it on the TV and on
everyone's phone; any change on one device appears on all of them.

## Run

```bash
pip install nicegui        # tested against 3.15
python main.py
```

Then open `http://<your-lan-ip>:8080` on every device at the table.

## Why it's built this way

NiceGUI 3.0 **removed the shared "auto-index" client**. In 2.x, UI elements in
global scope were served at `/` as a single client shared by every browser, which
made a shared dashboard nearly free. That's gone — global-scope UI is now
re-evaluated per visit ("script mode"), so each browser gets its own instance.

The replacement is the `Event` system, added in 3.0 for exactly this:

```
game     long-living plain-Python object   (game.py — no nicegui import)
changed  nicegui.Event
@ui.page per-client UI that subscribes to `changed`
```

Every mutation calls `touch()`, which emits the event; each connected client's
`@ui.refreshable` board rebuilds. Subscriptions made inside a UI context are
unsubscribed automatically when that client disconnects, so players closing
their phone browsers don't leak handlers.

`game.py` importing nothing from NiceGUI is the load-bearing part — it's what
lets the UI stay disposable while the game state persists.

## One trap worth knowing

The turn clock is derived from a server-side `time.monotonic()` timestamp
(`Game.elapsed`), not incremented by a ticker. A per-client `ui.timer` only
triggers a repaint. If you instead had each client's timer add a second to the
counter, six connected phones would make the clock run six times too fast.

## Not included

Objectives (public stage I/II and secrets), technology trees, and the galaxy map.
Objectives are the natural next addition: add a `list[Objective]` to `Game`, a
`scored_by: set[str]`, and a grid of toggles — scoring already routes through
`Game.score()`, so the track and standings update for free.

State is in-memory and resets on restart. For a game spanning sessions, pickle
`Game` on change, or swap the dataclasses for SQLModel rows.
