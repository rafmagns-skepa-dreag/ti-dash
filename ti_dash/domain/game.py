import time
from dataclasses import dataclass, field

from ti_dash.domain.clock import Clock
from ti_dash.domain.config import TimerConfig
from ti_dash.domain.models import Player
from ti_dash.domain.records import TurnRecord


@dataclass
class Game:
    players: list[Player] = field(default_factory=list)
    speaker: int = 0
    round: int = 1
    vp_goal: int = 10
    phase: str = "Strategy"
    awaiting_admin: bool = False
    active: int | None = None
    paused: bool = False
    agenda_enabled_this_round: bool = False
    config: TimerConfig = field(default_factory=TimerConfig)
    pending_records: list[TurnRecord] = field(default_factory=list)

    strategy_pick_clock: Clock = field(default_factory=Clock)
    action_clock: Clock = field(default_factory=Clock)
    secondary_clock: Clock = field(default_factory=Clock)
    status_clock: Clock = field(default_factory=Clock)
    agenda_window_clock: Clock = field(default_factory=Clock)
    agenda_vote_clock: Clock = field(default_factory=Clock)

    _sequence: int = 0
    _resume_clock: "Clock | None" = None

    # -- orderings --------------------------------------------------------
    def seating_order(self) -> list[Player]:
        ordered = sorted(self.players, key=lambda p: p.seat)
        if not ordered:
            return ordered
        start = next((i for i, p in enumerate(ordered) if p.seat == self.speaker), 0)
        return ordered[start:] + ordered[:start]

    def initiative_order(self) -> list[Player]:
        return sorted(self.players, key=lambda p: p.initiative)

    # -- roster / seats ---------------------------------------------------
    def add_player(self, name: str, faction: str, color: str) -> Player:
        player = Player(name=name, faction=faction, color=color, seat=len(self.players))
        self.players.append(player)
        return player

    def claim_seat(self, player: Player, device_id: str) -> None:
        if player.claim_token is not None and player.claim_token != device_id:
            raise PermissionError(f"{player.name}'s seat is already claimed")
        player.claim_token = device_id

    def release_seat(self, player: Player, device_id: str, *, is_admin: bool = False) -> None:
        if not is_admin and player.claim_token != device_id:
            raise PermissionError("not your seat")
        player.claim_token = None

    def authorize(self, player: Player, device_id: str | None, *, is_admin: bool) -> None:
        if not is_admin and player.claim_token != device_id:
            raise PermissionError(f"not authorized to act for {player.name}")

    # -- pause/resume --------------------------------------------------------
    def _all_clocks(self) -> list[Clock]:
        return [
            self.strategy_pick_clock, self.action_clock, self.secondary_clock,
            self.status_clock, self.agenda_window_clock, self.agenda_vote_clock,
        ]

    def active_clock(self) -> "Clock | None":
        return next((c for c in self._all_clocks() if c.running), None)

    def pause(self) -> None:
        running = self.active_clock()
        self._resume_clock = running
        if running is not None:
            running.stop()
        self.paused = True

    def resume(self) -> None:
        self.paused = False
        if self._resume_clock is not None:
            self._resume_clock.start()
            self._resume_clock = None

    def _check_not_paused(self) -> None:
        if self.paused:
            raise RuntimeError("game is paused")

    def _record(self, context: str, *, player, turn: int | None, duration: float) -> None:
        self._sequence += 1
        self.pending_records.append(TurnRecord(
            sequence=self._sequence,
            round=self.round,
            turn=turn,
            phase=self.phase,
            context=context,
            player_name=player.name if player is not None else None,
            seat=player.seat if player is not None else None,
            duration_seconds=duration,
            over_budget=duration > self.config.budget_for(context),
            ended_at=time.time(),
        ))

    # -- construction -----------------------------------------------------
    @classmethod
    def demo(cls) -> "Game":
        g = cls()
        g.players = [
            Player(name="Ana", faction="The Emirates of Hacan", color="Yellow", seat=0),
            Player(name="Bo", faction="The Naalu Collective", color="Green", seat=1),
            Player(name="Cass", faction="The Nomad", color="Blue", seat=2),
            Player(name="Dev", faction="The Winnu", color="Purple", seat=3),
        ]
        return g
