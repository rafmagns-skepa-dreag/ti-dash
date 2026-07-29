"""Application stylesheet, served verbatim at /app.css.

Kept as a plain string (not htpy) because htpy escapes <style> contents,
which would mangle CSS combinators and quotes. A dedicated text/css route
is also cacheable by the browser.
"""

CSS = """
:root {
  --bg: #0f1117;
  --panel: #181b24;
  --panel-2: #20242f;
  --line: #2c313d;
  --text: #e7e9ee;
  --muted: #9aa0ad;
  --accent: #4f8cff;
  --accent-ink: #ffffff;
  --warn: #e0483c;
  --radius: 12px;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  line-height: 1.4;
  padding: 0 0 3rem;
}

h1 {
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  margin: 0;
  padding: 0.75rem 1rem;
  color: var(--muted);
  text-transform: uppercase;
}

/* --- phase bar --------------------------------------------------------- */
#phasebar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 1rem;
  background: var(--panel);
  border-bottom: 1px solid var(--line);
}

#phasebar span {
  background: var(--panel-2);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 0.25rem 0.75rem;
  font-size: 0.85rem;
  white-space: nowrap;
}

/* --- active timer ------------------------------------------------------ */
#active-timer {
  text-align: center;
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  font-size: clamp(3rem, 14vw, 7rem);
  font-weight: 700;
  padding: 1.5rem 1rem;
  letter-spacing: 0.02em;
}

/* --- players grid ------------------------------------------------------ */
#players {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.75rem;
  padding: 0 1rem;
}

.player-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-left: 6px solid var(--line);
  border-radius: var(--radius);
  padding: 0.85rem 0.9rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.player-card .name {
  font-weight: 700;
  font-size: 1.05rem;
}

.player-card .swatch {
  display: inline-block;
  width: 0.9rem;
  height: 0.9rem;
  border-radius: 50%;
  margin-right: 0.5rem;
  vertical-align: middle;
  border: 1px solid rgba(255, 255, 255, 0.35);
}

.player-card .faction {
  color: var(--muted);
  font-size: 0.85rem;
}

.player-card .vp {
  font-size: 1.5rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.player-card .card {
  display: inline-block;
  font-size: 0.8rem;
  color: var(--muted);
}

.player-card .passed:not(:empty) {
  align-self: flex-start;
  background: var(--warn);
  color: #fff;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
}

/* --- buttons ----------------------------------------------------------- */
button {
  font: inherit;
  cursor: pointer;
  border: 1px solid var(--line);
  background: var(--panel-2);
  color: var(--text);
  border-radius: 8px;
  padding: 0.55rem 0.9rem;
  min-height: 2.5rem;
}

button:hover { background: #2a3040; }
button:active { transform: translateY(1px); }

.player-card button.claim { margin-top: 0.25rem; }

#phasebar button.pause,
#phasebar button.gate {
  background: var(--accent);
  color: var(--accent-ink);
  border-color: transparent;
  font-weight: 600;
}

#phasebar button.gate { margin-left: auto; }
"""
