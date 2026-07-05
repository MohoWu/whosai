import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from whosai.application.game_service import GameService
from whosai.application.models import AIPlayerDecision, AIPlayerRequest
from whosai.application.scheduling import AIPlayerScheduler, PhaseScheduler
from whosai.domain.game import GameConfig, Phase, Role
from whosai.infrastructure.memory import (
    InMemoryGameRepository,
    SeededRandomSource,
    SequenceIdGenerator,
)


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


class ManualTimerScheduler:
    def __init__(self, *, clock: FixedClock) -> None:
        self._clock = clock
        self._callbacks: list[PendingCallback] = []

    def schedule(
        self,
        *,
        deadline: datetime,
        callback: Callable[[], Awaitable[None]],
    ) -> ManualJob:
        job = ManualJob()
        self._callbacks.append(
            PendingCallback(
                deadline=deadline,
                callback=callback,
                job=job,
            )
        )
        return job

    @property
    def pending_deadlines(self) -> tuple[datetime, ...]:
        return tuple(pending.deadline for pending in self._callbacks if not pending.job.cancelled)

    async def run_due(self) -> None:
        due = [
            pending
            for pending in self._callbacks
            if not pending.job.cancelled and pending.deadline <= self._clock.now()
        ]
        for pending in due:
            self._callbacks.remove(pending)
        await asyncio.gather(*(pending.callback() for pending in due))


class StubAIPlayer:
    def __init__(self, *, speak_response: str | None = None) -> None:
        self.speak_response = speak_response
        self.requests: list[AIPlayerRequest] = []

    async def decide(self, request: AIPlayerRequest) -> AIPlayerDecision:
        self.requests.append(request)
        if request.phase is Phase.VOTING:
            return AIPlayerDecision(
                action="vote",
                response=None,
                target_seat_id=request.eligible_vote_targets[0],
            )
        if self.speak_response is not None:
            return AIPlayerDecision(
                action="speak",
                response=self.speak_response,
                target_seat_id=None,
            )
        return AIPlayerDecision(
            action="wait",
            response=None,
            target_seat_id=None,
        )


def build_scheduled_service(
    *,
    ids: list[str],
    ai_player: StubAIPlayer,
) -> tuple[GameService, InMemoryGameRepository, FixedClock, ManualTimerScheduler]:
    repository = InMemoryGameRepository()
    clock = FixedClock()
    timers = ManualTimerScheduler(clock=clock)
    service = GameService(
        repository=repository,
        clock=clock,
        ids=SequenceIdGenerator(ids),
        random_source=SeededRandomSource(seed=7),
        phase_scheduler=PhaseScheduler(timers=timers),
        ai_scheduler=AIPlayerScheduler(clock=clock, timers=timers),
        ai_player=ai_player,
    )
    return service, repository, clock, timers


async def start_game(service: GameService) -> tuple[str, str]:
    tickets = [
        await service.join_matchmaking(idempotency_key=f"join-{index}") for index in range(1, 4)
    ]
    matched = await service.get_match(
        ticket_id=tickets[0].ticket_id,
        player_token=tickets[0].player_token,
    )
    assert matched.game_id is not None
    return matched.game_id, matched.player_token


def test_phase_scheduler_advances_deadlines_and_triggers_one_ai_vote() -> None:
    async def scenario() -> None:
        ai_player = StubAIPlayer()
        service, repository, clock, timers = build_scheduled_service(
            ids=[
                "ticket-1",
                "token-1",
                "ticket-2",
                "token-2",
                "ticket-3",
                "token-3",
                "game-1",
            ],
            ai_player=ai_player,
        )
        game_id, _ = await start_game(service)
        config = GameConfig()
        discussion_deadline = clock.now() + config.discussion_duration
        assert timers.pending_deadlines == (discussion_deadline,)

        clock.advance(by=config.discussion_duration)
        await timers.run_due()

        voting = await repository.get_game(game_id)
        assert voting is not None
        assert voting.phase is Phase.VOTING
        assert ai_player.requests == []
        assert sorted(timers.pending_deadlines) == [
            clock.now(),
            clock.now() + config.voting_duration,
        ]

        await timers.run_due()

        voted = await repository.get_game(game_id)
        assert voted is not None
        assert len(ai_player.requests) == 1
        request = ai_player.requests[0]
        assert request.phase is Phase.VOTING
        assert request.eligible_vote_targets
        assert len(voted.votes) == 1
        ai_seat = next(seat.id for seat in voted.seats if seat.role is Role.AI)
        assert voted.votes[0].voter_id == ai_seat

        clock.advance(by=config.voting_duration)
        await timers.run_due()

        next_round = await repository.get_game(game_id)
        assert next_round is not None
        assert next_round.phase is Phase.DISCUSSION
        assert next_round.round_number == 2
        assert timers.pending_deadlines == (clock.now() + config.discussion_duration,)

    asyncio.run(scenario())


def test_chat_debounce_accumulates_context_and_ai_speech_does_not_reschedule_itself() -> None:
    async def scenario() -> None:
        ai_player = StubAIPlayer(speak_response="Player 2 has been unusually quiet.")
        service, repository, clock, timers = build_scheduled_service(
            ids=[
                "ticket-1",
                "token-1",
                "ticket-2",
                "token-2",
                "ticket-3",
                "token-3",
                "game-1",
                "message-1",
                "message-2",
            ],
            ai_player=ai_player,
        )
        game_id, player_token = await start_game(service)
        game = await repository.get_game(game_id)
        assert game is not None
        ai_seat = next(seat.id for seat in game.seats if seat.role is Role.AI)

        await service.send_chat(
            game_id=game_id,
            player_token=player_token,
            content="Who seems suspicious?",
            idempotency_key="chat-1",
        )
        clock.advance(by=timedelta(seconds=5))
        await service.send_chat(
            game_id=game_id,
            player_token=player_token,
            content=f"{ai_seat}, what do you think?",
            idempotency_key="chat-2",
        )

        assert clock.now() + timedelta(seconds=6) in timers.pending_deadlines
        clock.advance(by=timedelta(seconds=5))
        await timers.run_due()
        assert ai_player.requests == []

        clock.advance(by=timedelta(seconds=1))
        await timers.run_due()

        assert len(ai_player.requests) == 1
        request = ai_player.requests[0]
        assert request.phase is Phase.DISCUSSION
        assert request.new_message_count == 2
        assert request.direct_mention is True
        assert [message.content for message in request.chat_history] == [
            "Who seems suspicious?",
            f"{ai_seat}, what do you think?",
        ]

        updated = await repository.get_game(game_id)
        assert updated is not None
        assert [message.content for message in updated.messages] == [
            "Who seems suspicious?",
            f"{ai_seat}, what do you think?",
            "Player 2 has been unusually quiet.",
        ]
        assert timers.pending_deadlines == (updated.phase_deadline,)

    asyncio.run(scenario())
