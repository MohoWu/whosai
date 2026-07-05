import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from whosai.application.models import AIDecisionTrigger
from whosai.application.scheduling import AIPlayerScheduler
from whosai.domain.game import Game, Phase, create_four_seat_game, post_chat


class FixedClock:
    def __init__(self) -> None:
        self._now = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, *, by: timedelta) -> None:
        self._now += by


class ManualJob:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


@dataclass(slots=True)
class PendingCallback:
    deadline: datetime
    callback: Callable[[], Awaitable[None]]
    job: ManualJob


class ManualTimers:
    def __init__(self, *, clock: FixedClock) -> None:
        self.clock = clock
        self.callbacks: list[PendingCallback] = []

    def schedule(
        self,
        *,
        deadline: datetime,
        callback: Callable[[], Awaitable[None]],
    ) -> ManualJob:
        job = ManualJob()
        self.callbacks.append(PendingCallback(deadline, callback, job))
        return job

    @property
    def pending_deadlines(self) -> tuple[datetime, ...]:
        return tuple(callback.deadline for callback in self.callbacks if not callback.job.cancelled)

    async def run_due(self) -> None:
        due = [
            callback
            for callback in self.callbacks
            if not callback.job.cancelled and callback.deadline <= self.clock.now()
        ]
        for callback in due:
            self.callbacks.remove(callback)
        await asyncio.gather(*(callback.callback() for callback in due))


def add_message(
    game: Game,
    *,
    clock: FixedClock,
    message_id: str,
    content: str,
) -> Game:
    return post_chat(
        game,
        message_id=message_id,
        seat_id="Player 1",
        content=content,
        now=clock.now(),
    )


def test_ai_debounce_never_moves_past_thirty_seconds_from_first_unread_message() -> None:
    async def scenario() -> None:
        clock = FixedClock()
        timers = ManualTimers(clock=clock)
        scheduler = AIPlayerScheduler(clock=clock, timers=timers)
        game = create_four_seat_game(
            game_id="game-1",
            ai_seat_id="Player 4",
            now=clock.now(),
        )
        scheduler.discussion_started(game)
        triggers: list[AIDecisionTrigger] = []

        async def record(trigger: AIDecisionTrigger) -> None:
            triggers.append(trigger)

        for index in range(6):
            game = add_message(
                game,
                clock=clock,
                message_id=f"message-{index}",
                content="Player 4 should answer this burst.",
            )
            scheduler.chat_posted(
                game,
                author_seat_id="Player 1",
                on_decision=record,
            )
            if index < 5:
                clock.advance(by=timedelta(seconds=5))

        first_message_at = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)
        assert timers.pending_deadlines == (first_message_at + timedelta(seconds=30),)

        clock.advance(by=timedelta(seconds=5))
        await timers.run_due()

        assert len(triggers) == 1
        assert triggers[0].new_message_count == 6
        assert triggers[0].direct_mention is True
        assert triggers[0].through_message_id == "message-5"

    asyncio.run(scenario())


def test_direct_mention_requires_clear_case_insensitive_label_boundaries() -> None:
    async def scenario() -> None:
        clock = FixedClock()
        timers = ManualTimers(clock=clock)
        scheduler = AIPlayerScheduler(clock=clock, timers=timers)
        game = create_four_seat_game(
            game_id="game-1",
            ai_seat_id="Player 3",
            now=clock.now(),
        )
        scheduler.discussion_started(game)
        triggers: list[AIDecisionTrigger] = []

        async def record(trigger: AIDecisionTrigger) -> None:
            triggers.append(trigger)

        game = add_message(
            game,
            clock=clock,
            message_id="message-1",
            content="player 30 is not a mention, but @pLaYeR 3 is.",
        )
        scheduler.chat_posted(
            game,
            author_seat_id="Player 1",
            on_decision=record,
        )
        clock.advance(by=timedelta(seconds=6))
        await timers.run_due()

        assert triggers[0].direct_mention is True

    asyncio.run(scenario())


def test_similar_label_without_clear_boundary_is_not_a_direct_mention() -> None:
    async def scenario() -> None:
        clock = FixedClock()
        timers = ManualTimers(clock=clock)
        scheduler = AIPlayerScheduler(clock=clock, timers=timers)
        game = create_four_seat_game(
            game_id="game-1",
            ai_seat_id="Player 3",
            now=clock.now(),
        )
        scheduler.discussion_started(game)
        triggers: list[AIDecisionTrigger] = []

        async def record(trigger: AIDecisionTrigger) -> None:
            triggers.append(trigger)

        game = add_message(
            game,
            clock=clock,
            message_id="message-1",
            content="Player 30 is a different label.",
        )
        scheduler.chat_posted(
            game,
            author_seat_id="Player 1",
            on_decision=record,
        )
        clock.advance(by=timedelta(seconds=6))
        await timers.run_due()

        assert triggers[0].direct_mention is False

    asyncio.run(scenario())


def test_voting_cancels_a_pending_discussion_job_and_triggers_once_immediately() -> None:
    async def scenario() -> None:
        clock = FixedClock()
        timers = ManualTimers(clock=clock)
        scheduler = AIPlayerScheduler(clock=clock, timers=timers)
        game = create_four_seat_game(
            game_id="game-1",
            ai_seat_id="Player 4",
            now=clock.now(),
        )
        scheduler.discussion_started(game)
        triggers: list[AIDecisionTrigger] = []

        async def record(trigger: AIDecisionTrigger) -> None:
            triggers.append(trigger)

        game = add_message(
            game,
            clock=clock,
            message_id="message-1",
            content="Last message before voting.",
        )
        scheduler.chat_posted(
            game,
            author_seat_id="Player 1",
            on_decision=record,
        )
        voting = replace(game, phase=Phase.VOTING)
        scheduler.voting_started(voting, on_decision=record)

        assert timers.pending_deadlines == (clock.now(),)
        await timers.run_due()
        clock.advance(by=timedelta(seconds=6))
        await timers.run_due()

        assert len(triggers) == 1
        assert triggers[0].phase is Phase.VOTING
        assert triggers[0].new_message_count == 1

    asyncio.run(scenario())
