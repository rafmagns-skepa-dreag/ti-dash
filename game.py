"""Twilight Imperium 4 session state.

Deliberately free of any NiceGUI import: this module is the long-living object,
the UI is short-living and subscribes to it. Keeping the seam here is what makes
the multi-device sync in main.py straightforward.
"""

import time
from dataclasses import dataclass, field

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
    banked: float = 0.0
    """Seconds spent on this player's completed turns."""

    @property
    def initiative(self) -> int:
        """Unpicked players sort last; the card number *is* the initiative."""
        return self.strategy_card if self.strategy_card is not None else 99

    @property
    def command_total(self) -> int:
        return self.tactic + self.fleet + self.strategy


@dataclass
class Game:
    players: list[Player] = field(default_factory=list)
    round: int = 1
    phase: str = "Strategy"
    speaker: int = 0
    vp_goal: int = 10
    active: int | None = None
    turn_started: float | None = None
    log: list[str] = field(default_factory=list)

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
        """Turn time including the turn currently in progress.

        Computed from a timestamp rather than incremented by a ticker, so that
        N connected browsers cannot make the clock run N times too fast.
        """
        running = 0.0
        if (
            self.active is not None
            and self.turn_started is not None
            and self.players[self.active] is player
        ):
            running = time.monotonic() - self.turn_started
        return player.banked + running

    def taken_cards(self) -> set[int]:
        return {p.strategy_card for p in self.players if p.strategy_card} - {None}

    # -- mutations --------------------------------------------------------

    def note(self, message: str) -> None:
        self.log.insert(0, f"R{self.round} · {message}")
        del self.log[60:]

    def add_player(self, name: str, faction: str, color: str) -> None:
        self.players.append(Player(name=name, faction=faction, color=color))
        self.note(f"{name} joined as {faction}")

    def score(self, player: Player, delta: int) -> None:
        player.vp = max(0, min(self.vp_goal, player.vp + delta))
        verb = "scored" if delta > 0 else "lost"
        self.note(f"{player.name} {verb} {abs(delta)} VP → {player.vp}")

    def assign_card(self, player: Player, card: int | None) -> None:
        for other in self.players:
            if other is not player and other.strategy_card == card:
                other.strategy_card = None
        player.strategy_card = card
        if card:
            self.note(f"{player.name} took {card} · {STRATEGY_CARDS[card]}")

    def pass_speaker(self, player: Player) -> None:
        self.speaker = self.players.index(player)
        self.note(f"{player.name} is now Speaker")

    def start_turn(self, player: Player) -> None:
        self.end_turn()
        self.active = self.players.index(player)
        self.turn_started = time.monotonic()

    def end_turn(self) -> None:
        if self.active is not None and self.turn_started is not None:
            self.players[self.active].banked += time.monotonic() - self.turn_started
        self.active = None
        self.turn_started = None

    def next_turn(self) -> None:
        """Advance to the next unpassed player in initiative order."""
        order = [p for p in self.initiative_order() if not p.passed]
        if not order:
            self.end_turn()
            return
        if self.active is None:
            self.start_turn(order[0])
            return
        current = self.players[self.active]
        if current in order:
            nxt = order[(order.index(current) + 1) % len(order)]
        else:
            nxt = order[0]
        self.start_turn(nxt)

    def toggle_pass(self, player: Player) -> None:
        player.passed = not player.passed
        self.note(f"{player.name} {'passed' if player.passed else 'un-passed'}")
        if player.passed and self.active is not None and self.players[self.active] is player:
            self.next_turn()

    def set_phase(self, phase: str) -> None:
        self.phase = phase
        self.note(f"{phase} phase")
        if phase != "Action":
            self.end_turn()

    def advance_phase(self) -> None:
        idx = PHASES.index(self.phase)
        if idx == len(PHASES) - 1:
            self.new_round()
        else:
            self.set_phase(PHASES[idx + 1])
            if self.phase == "Action":
                self.next_turn()

    def new_round(self) -> None:
        self.end_turn()
        self.round += 1
        self.phase = "Strategy"
        for p in self.players:
            p.strategy_card = None
            p.passed = False
        self.note("New round begins")

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
