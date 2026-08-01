import time
from dataclasses import asdict, dataclass, field
from typing import Final

from ti_dash.domain.clock import Clock
from ti_dash.domain.config import TimerConfig
from ti_dash.domain.models import Player, TurnRecord
from ti_dash.domain.reference import Color, Context, Faction, Phase, StrategyCard


@dataclass
class Game:
    players: Final[list[Player]] = field(default_factory=list)
    speaker_seat_number: int = 0
    round: int = 1
    vp_goal: int = 10
    phase: Phase = Phase.Strategy
    awaiting_admin: bool = False
    active: int | None = None
    paused: bool = False
    strategy_pick_started: bool = False
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
    _resume_clocks: list = field(default_factory=list)
    _turn_no: int = 0

    def __post_init__(self):
        if self.players and all(p.passed for p in self.players):
            self.awaiting_admin = True
        self.paused = True

    def to_dict(self) -> dict:
        return {
            "speaker_seat_number": self.speaker_seat_number,
            "round": self.round,
            "vp_goal": self.vp_goal,
            "phase": self.phase.name,
            "awaiting_admin": self.awaiting_admin,
            "active": self.active,
            "paused": self.paused,
            "strategy_pick_started": self.strategy_pick_started,
            "agenda_enabled_this_round": self.agenda_enabled_this_round,
            "config": asdict(self.config),
            "players": [p.to_dict() for p in self.players],
            "_sequence": self._sequence,
        }

    @staticmethod
    def from_dict(data: dict) -> Game:
        data["players"] = [Player.from_dict(**pd) for pd in data["players"]]
        data["phase"] = Phase[data["phase"]]
        data["config"].pop("admin_password", None)
        data["config"] = TimerConfig(**data["config"])
        if "sequence" in data:
            data["_sequence"] = data.pop("sequence")
        if "admin_password" in data:
            del data["admin_password"]
        return Game(**data)

    def speaker_order(self, offset: int = 0) -> list[Player]:
        return (
            self.players[self.speaker_seat_number + offset :]
            + self.players[: self.speaker_seat_number + offset]
        )

    @property
    def current_phase_ordering(self) -> list[Player]:
        match self.phase:
            case Phase.Strategy:
                return self.speaker_order(offset=0)
            case Phase.Action:
                return self.initiative_order()
            case Phase.Agenda:
                return self.speaker_order(offset=1)
            case Phase.Status:
                return self.initiative_order()
            case _ as e:
                raise RuntimeError(f"Unknown phase {e}")

    @property
    def next_player(self) -> Player | None:
        if self.active is None:
            return None
        idx = self._find_next_unpassed_player()
        if idx is None or idx == self.active:
            return None
        return self.current_phase_ordering[idx]

    def initiative_order(self) -> list[Player]:
        return sorted(self.players, key=lambda p: p.initiative)

    # -- roster / seats ---------------------------------------------------
    def claim_seat(self, player: Player, device_id: str) -> None:
        if player.claim_token is not None and player.claim_token != device_id:
            raise PermissionError(f"{player.name}'s seat is already claimed")
        # Release any other seat currently owned by this device
        for other in self.players:
            if other is not player and other.claim_token == device_id:
                other.claim_token = None
        player.claim_token = device_id

    def release_seat(
        self, player: Player, device_id: str, *, is_admin: bool = False
    ) -> None:
        if not is_admin and player.claim_token != device_id:
            raise PermissionError("not your seat")
        player.claim_token = None

    def set_speaker(self, player: Player) -> None:
        self.speaker_seat_number = player.seat

    def authorize(
        self, player: Player, device_id: str | None, *, is_admin: bool
    ) -> None:
        if not is_admin and player.claim_token != device_id:
            raise PermissionError(f"not authorized to act for {player.name}")

    # -- pause/resume --------------------------------------------------------
    def _all_clocks(self) -> list[Clock]:
        return [
            self.strategy_pick_clock,
            self.action_clock,
            self.secondary_clock,
            self.status_clock,
            self.agenda_window_clock,
            self.agenda_vote_clock,
        ]

    def active_clock(self) -> Clock | None:
        return next((c for c in self._all_clocks() if c.running), None)

    def pause(self) -> None:
        self._resume_clocks = [c for c in self._all_clocks() if c.running]
        for clock in self._resume_clocks:
            clock.stop()
        self.paused = True

    def resume(self) -> None:
        self.paused = False
        if self._resume_clocks:
            for clock in self._resume_clocks:
                clock.start()
            self._resume_clocks = []
            return
        if self.phase == Phase.Strategy and not self.strategy_pick_started:
            self.begin_strategy_pick()

    def _check_not_paused(self) -> None:
        if self.paused:
            raise RuntimeError("game is paused")

    def _seat_index(self, player) -> int:
        return self.players.index(player)

    def start_action_phase(self) -> None:
        self.phase = Phase.Action
        self.awaiting_admin = False
        self._turn_no = 0
        self.active = 0
        self.action_clock.reset(self.config.budget_for(Context.ACTION))
        self.action_clock.start()
        self.unpass_players()

    def _current(self) -> Player | None:
        return (
            self.current_phase_ordering[self.active]
            if self.active is not None
            else None
        )

    def end_turn(self, player, device_id=None, *, is_admin=False) -> None:
        self._check_not_paused()
        self.authorize(player, device_id, is_admin=is_admin)
        self.action_clock.stop()
        self._record(
            Context.ACTION,
            player=player,
            turn=self._turn_no,
            duration=self.action_clock.elapsed(),
        )
        self._advance_action()

    def pass_turn(self, player, device_id=None, *, is_admin=False) -> None:
        self._check_not_paused()
        self.authorize(player, device_id, is_admin=is_admin)
        player.passed = True
        self.action_clock.stop()
        self._record(
            Context.ACTION,
            player=player,
            turn=self._turn_no,
            duration=self.action_clock.elapsed(),
        )
        self._advance_action()

    def _advance_action(self) -> None:
        self._turn_no += 1

        nxt = self._find_next_unpassed_player()
        if nxt is None:
            self.action_clock.stop()
            self.active = None
            self.awaiting_admin = True
            return
        self.active = nxt
        self.action_clock.reset(self.config.budget_for(Context.ACTION))
        self.action_clock.start()

    def open_secondary(self) -> None:
        self.secondary_clock.reset(self.config.budget_for(Context.SECONDARY))
        self.secondary_clock.start()

    def close_secondary(self) -> None:
        self.secondary_clock.stop()
        self._record(
            Context.SECONDARY,
            player=self._current(),
            turn=self._turn_no,
            duration=self.secondary_clock.elapsed(),
        )

    def score(self, player, delta, device_id=None, *, is_admin=False) -> None:
        self._check_not_paused()
        self.authorize(player, device_id, is_admin=is_admin)
        player.vp = max(0, min(self.vp_goal, player.vp + delta))

    def begin_strategy_pick(self) -> None:
        self.strategy_pick_started = True
        self.strategy_pick_clock.reset(self.config.budget_for(Context.STRATEGY_PICK))
        self.strategy_pick_clock.start()

    def pick_strategy_card(
        self, player, card: StrategyCard, device_id=None, *, is_admin=False
    ) -> None:
        self._check_not_paused()
        self.authorize(player, device_id, is_admin=is_admin)
        for other in self.players:
            if other is not player and other.strategy_card is card:
                other.strategy_card = None
        player.strategy_card = card
        self.strategy_pick_clock.stop()
        self._record(
            Context.STRATEGY_PICK,
            player=player,
            turn=None,
            duration=self.strategy_pick_clock.elapsed(),
        )
        if all(p.strategy_card is not None for p in self.players):
            self.awaiting_admin = True

    def unset_strategy_card(self, player: Player, *, is_admin: bool = False) -> None:
        if not is_admin:
            raise PermissionError("only admin can unset a strategy card")
        player.strategy_card = None
        self.awaiting_admin = False

    def set_passed(
        self, player: Player, passed: bool, *, is_admin: bool = False
    ) -> None:
        if not is_admin:
            raise PermissionError("only admin can change pass status")
        player.passed = passed
        if passed or not self.awaiting_admin:
            return
        # The round had gated on everyone passing; bring the un-passed
        # player back into rotation instead of leaving the gate stuck.
        if self.phase == Phase.Action:
            self.awaiting_admin = False
            self.active = self.current_phase_ordering.index(player)
            self.action_clock.reset(self.config.budget_for(Context.ACTION))
            self.action_clock.start()
        elif self.phase == Phase.Status:
            self.awaiting_admin = False
            self.status_clock.reset(self.config.budget_for(Context.STATUS))
            self.status_clock.start()
        if self.active and self.current_phase_ordering[self.active] is player:
            self.active = self._find_next_unpassed_player()

    def _record(
        self, context: Context, *, player, turn: int | None, duration: float
    ) -> None:
        self._sequence += 1
        self.pending_records.append(
            TurnRecord(
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
            )
        )

    def start_strategy_phase(self) -> None:
        self.phase = Phase.Strategy
        self.awaiting_admin = False
        self.active = None
        self.strategy_pick_started = False
        self.unpass_players()

    def start_status_phase(self) -> None:
        self.phase = Phase.Status
        self.awaiting_admin = False
        self.active = None
        self.unpass_players()
        self.status_clock.reset(self.config.budget_for(Context.STATUS))
        self.status_clock.start()

    def end_status_phase(self) -> None:
        self.status_clock.stop()
        self._record(
            Context.STATUS, player=None, turn=None, duration=self.status_clock.elapsed()
        )
        self.awaiting_admin = True

    def pass_status(self, player, device_id=None, *, is_admin=False) -> None:
        self._check_not_paused()
        self.authorize(player, device_id, is_admin=is_admin)
        player.passed = True
        if all(p.passed for p in self.players):
            self.end_status_phase()

    def start_agenda_phase(self) -> None:
        self.phase = Phase.Agenda
        self.awaiting_admin = False
        self.unpass_players()

    def open_agenda_window(self) -> None:
        if self.agenda_vote_clock.running:
            self.agenda_vote_clock.stop()
        # Debate order tracks its own pass state via `player.passed`, kept
        # separate from vote eligibility by resetting it here and again in
        # begin_agenda_vote().
        self.unpass_players()
        self.active = 0
        self.agenda_window_clock.reset(self.config.budget_for(Context.AGENDA_WINDOW))
        self.agenda_window_clock.start()

    def close_agenda_window(self) -> None:
        self.agenda_window_clock.stop()
        self._record(
            Context.AGENDA_WINDOW,
            player=None,
            turn=None,
            duration=self.agenda_window_clock.elapsed(),
        )

    def end_agenda_window_turn(self, player, device_id=None, *, is_admin=False) -> None:
        self._check_not_paused()
        self.authorize(player, device_id, is_admin=is_admin)
        self._advance_agenda_window()

    def pass_agenda_window(self, player, device_id=None, *, is_admin=False) -> None:
        self._check_not_paused()
        self.authorize(player, device_id, is_admin=is_admin)
        player.passed = True
        self._advance_agenda_window()

    def _advance_agenda_window(self) -> None:
        self.active = self._find_next_unpassed_player()
        if self.active is None:
            self.agenda_window_clock.stop()
            return
        self.agenda_window_clock.reset(self.config.budget_for(Context.AGENDA_WINDOW))
        self.agenda_window_clock.start()

    def begin_agenda_vote(self) -> None:
        self.unpass_players()
        if self.agenda_window_clock.running:
            self.close_agenda_window()
        self.active = 0
        self.agenda_vote_clock.reset(self.config.budget_for(Context.AGENDA_VOTE))
        self.agenda_vote_clock.start()

    def cast_agenda_vote(self, player, device_id=None, *, is_admin=False) -> None:
        self._check_not_paused()
        self.authorize(player, device_id, is_admin=is_admin)
        if self._current() is not player:
            raise PermissionError(f"it is not {player.name}'s turn to vote")
        self.agenda_vote_clock.stop()
        self._record(
            Context.AGENDA_VOTE,
            player=player,
            turn=None,
            duration=self.agenda_vote_clock.elapsed(),
        )
        player.passed = True
        self._advance_vote()

    def _find_next_unpassed_player(self) -> int | None:
        assert self.active is not None
        start = self.active + 1

        current_order = self.current_phase_ordering
        nxt = None
        for i in range(len(self.players)):
            possible = (start + i) % len(self.players)
            if not current_order[possible].passed:
                nxt = possible
                break
        return nxt

    def _advance_vote(self) -> None:
        assert self.active is not None
        self.active = self._find_next_unpassed_player()
        if self.active is None:
            return
        self.agenda_vote_clock.reset(self.config.budget_for(Context.AGENDA_VOTE))
        self.agenda_vote_clock.start()

    def end_agenda_phase(self) -> None:
        self.awaiting_admin = True

    def enable_agenda_phase(self) -> None:
        self.agenda_enabled_this_round = True

    def new_round(self) -> None:
        self.round += 1
        self.unpass_players()
        for p in self.players:
            p.strategy_card = None
        self.active = None
        for c in self._all_clocks():
            c.reset()
        self.start_strategy_phase()

    def add_player(self, name: str, faction: str, color: str) -> Player:
        player = Player(
            name=name,
            faction=Faction(faction),
            color=Color[color.upper()],
            seat=len(self.players),
        )
        self.players.append(player)
        return player

    def unpass_players(self):
        for player in self.players:
            player.passed = False
