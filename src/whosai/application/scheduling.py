import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from whosai.application.models import AIDecisionTrigger
from whosai.application.ports import Clock, ScheduledJob, TimerScheduler
from whosai.domain.game import Game, Phase, Role

AI_DEBOUNCE = timedelta(seconds=6)
AI_MAXIMUM_WAIT = timedelta(seconds=30)

PhaseDeadlineHandler = Callable[[str], Awaitable[None]]
AIDecisionHandler = Callable[[AIDecisionTrigger], Awaitable[None]]


@dataclass(slots=True)
class _PhaseJob:
    deadline: datetime
    generation: int
    handle: ScheduledJob


class PhaseScheduler:
    """Keep one authoritative phase-deadline job per game."""

    def __init__(self, *, timers: TimerScheduler) -> None:
        self._timers = timers
        self._jobs: dict[str, _PhaseJob] = {}
        self._generations: dict[str, int] = {}

    def synchronize(self, game: Game, *, on_deadline: PhaseDeadlineHandler) -> None:
        deadline = game.phase_deadline
        existing = self._jobs.get(game.id)
        if deadline is None:
            self.cancel(game.id)
            return
        if existing is not None and existing.deadline == deadline:
            return
        if existing is not None:
            existing.handle.cancel()

        generation = self._generations.get(game.id, 0) + 1
        self._generations[game.id] = generation

        async def fire() -> None:
            current = self._jobs.get(game.id)
            if current is None or current.generation != generation:
                return
            self._jobs.pop(game.id, None)
            await on_deadline(game.id)

        handle = self._timers.schedule(deadline=deadline, callback=fire)
        self._jobs[game.id] = _PhaseJob(
            deadline=deadline,
            generation=generation,
            handle=handle,
        )

    def cancel(self, game_id: str) -> None:
        job = self._jobs.pop(game_id, None)
        if job is not None:
            job.handle.cancel()

    def close(self) -> None:
        for game_id in tuple(self._jobs):
            self.cancel(game_id)


@dataclass(slots=True)
class _AISeatState:
    round_number: int
    phase: Phase
    turn_number: int = 0
    unread_message_count: int = 0
    direct_mention: bool = False
    first_unread_at: datetime | None = None
    through_message_id: str | None = None
    generation: int = 0
    handle: ScheduledJob | None = None


class AIPlayerScheduler:
    """Apply chat debounce and voting-trigger policy independently of phase timing."""

    def __init__(
        self,
        *,
        clock: Clock,
        timers: TimerScheduler,
        debounce: timedelta = AI_DEBOUNCE,
        maximum_wait: timedelta = AI_MAXIMUM_WAIT,
    ) -> None:
        if debounce <= timedelta(0):
            raise ValueError("AI debounce must be positive.")
        if maximum_wait < debounce:
            raise ValueError("AI maximum wait must not be shorter than its debounce.")
        self._clock = clock
        self._timers = timers
        self._debounce = debounce
        self._maximum_wait = maximum_wait
        self._states: dict[tuple[str, str], _AISeatState] = {}

    def discussion_started(self, game: Game) -> None:
        self.cancel_game(game.id)
        for seat in game.seats:
            if seat.alive and seat.role is Role.AI:
                self._states[(game.id, seat.id)] = _AISeatState(
                    round_number=game.round_number,
                    phase=Phase.DISCUSSION,
                )

    def chat_posted(
        self,
        game: Game,
        *,
        author_seat_id: str,
        on_decision: AIDecisionHandler,
    ) -> None:
        if game.phase is not Phase.DISCUSSION or not game.messages:
            return

        message = game.messages[-1]
        now = self._clock.now()
        for seat in game.seats:
            if not seat.alive or seat.role is not Role.AI or seat.id == author_seat_id:
                continue

            key = (game.id, seat.id)
            state = self._state_for(game, seat.id)
            if state.unread_message_count == 0:
                state.first_unread_at = now
            state.unread_message_count += 1
            state.direct_mention = state.direct_mention or _mentions_seat(
                message.content,
                seat.id,
            )
            state.through_message_id = message.id
            self._schedule_discussion_decision(
                key=key,
                state=state,
                on_decision=on_decision,
            )

    def voting_started(
        self,
        game: Game,
        *,
        on_decision: AIDecisionHandler,
    ) -> None:
        living_ai_seats = tuple(seat for seat in game.seats if seat.alive and seat.role is Role.AI)
        for seat in living_ai_seats:
            state = self._state_for(game, seat.id)
            if state.handle is not None:
                state.handle.cancel()
                state.handle = None
            state.phase = Phase.VOTING
            state.turn_number += 1
            trigger = AIDecisionTrigger(
                game_id=game.id,
                seat_id=seat.id,
                round_number=game.round_number,
                phase=Phase.VOTING,
                turn_number=state.turn_number,
                new_message_count=state.unread_message_count,
                direct_mention=state.direct_mention,
                through_message_id=game.messages[-1].id if game.messages else None,
            )
            state.unread_message_count = 0
            state.direct_mention = False
            state.first_unread_at = None
            state.through_message_id = trigger.through_message_id

            async def fire_vote(
                trigger: AIDecisionTrigger = trigger,
            ) -> None:
                await on_decision(trigger)

            state.handle = self._timers.schedule(
                deadline=self._clock.now(),
                callback=fire_vote,
            )

    def game_finished(self, game_id: str) -> None:
        self.cancel_game(game_id)

    def cancel_game(self, game_id: str) -> None:
        keys = tuple(key for key in self._states if key[0] == game_id)
        for key in keys:
            state = self._states.pop(key)
            if state.handle is not None:
                state.handle.cancel()

    def close(self) -> None:
        for game_id in {key[0] for key in self._states}:
            self.cancel_game(game_id)

    def _state_for(self, game: Game, seat_id: str) -> _AISeatState:
        key = (game.id, seat_id)
        state = self._states.get(key)
        if state is None or state.round_number != game.round_number:
            if state is not None and state.handle is not None:
                state.handle.cancel()
            state = _AISeatState(
                round_number=game.round_number,
                phase=game.phase,
            )
            self._states[key] = state
        return state

    def _schedule_discussion_decision(
        self,
        *,
        key: tuple[str, str],
        state: _AISeatState,
        on_decision: AIDecisionHandler,
    ) -> None:
        if state.first_unread_at is None or state.through_message_id is None:
            raise RuntimeError("Unread AI scheduling state is incomplete.")
        if state.handle is not None:
            state.handle.cancel()

        debounce_deadline = self._clock.now() + self._debounce
        maximum_deadline = state.first_unread_at + self._maximum_wait
        deadline = min(debounce_deadline, maximum_deadline)
        state.generation += 1
        generation = state.generation
        round_number = state.round_number

        async def fire() -> None:
            current = self._states.get(key)
            if (
                current is None
                or current.generation != generation
                or current.round_number != round_number
                or current.phase is not Phase.DISCUSSION
            ):
                return
            current.handle = None
            current.turn_number += 1
            trigger = AIDecisionTrigger(
                game_id=key[0],
                seat_id=key[1],
                round_number=current.round_number,
                phase=Phase.DISCUSSION,
                turn_number=current.turn_number,
                new_message_count=current.unread_message_count,
                direct_mention=current.direct_mention,
                through_message_id=current.through_message_id,
            )
            current.unread_message_count = 0
            current.direct_mention = False
            current.first_unread_at = None
            await on_decision(trigger)

        state.handle = self._timers.schedule(deadline=deadline, callback=fire)


def _mentions_seat(content: str, seat_id: str) -> bool:
    pattern = rf"(?<!\w){re.escape(seat_id)}(?!\w)"
    return re.search(pattern, content, flags=re.IGNORECASE) is not None


__all__ = [
    "AI_DEBOUNCE",
    "AI_MAXIMUM_WAIT",
    "AIPlayerScheduler",
    "PhaseScheduler",
]
