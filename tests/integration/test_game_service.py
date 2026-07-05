import asyncio
from datetime import UTC, datetime, timedelta

from whosai.application.game_service import GameService, MatchStatus
from whosai.domain.game import GameConfig
from whosai.infrastructure.memory import (
    InMemoryGameRepository,
    SeededRandomSource,
    SequenceIdGenerator,
)


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, *, by: timedelta) -> None:
        self._now += by


def test_three_humans_are_matched_into_one_hidden_role_game() -> None:
    async def scenario() -> None:
        service = GameService(
            repository=InMemoryGameRepository(),
            clock=FixedClock(datetime(2026, 7, 2, 12, 0, tzinfo=UTC)),
            ids=SequenceIdGenerator(
                [
                    "ticket-1",
                    "token-1",
                    "ticket-2",
                    "token-2",
                    "ticket-3",
                    "token-3",
                    "game-1",
                ]
            ),
            random_source=SeededRandomSource(seed=7),
        )

        first = await service.join_matchmaking(idempotency_key="join-1")
        second = await service.join_matchmaking(idempotency_key="join-2")
        third = await service.join_matchmaking(idempotency_key="join-3")

        assert first.status is MatchStatus.WAITING
        assert second.status is MatchStatus.WAITING
        assert third.status is MatchStatus.MATCHED

        matched = [
            await service.get_match(ticket_id=result.ticket_id, player_token=result.player_token)
            for result in (first, second, third)
        ]
        assert {result.game_id for result in matched} == {"game-1"}
        assert {result.seat_id for result in matched} <= {
            "Player 1",
            "Player 2",
            "Player 3",
            "Player 4",
        }
        assert len({result.seat_id for result in matched}) == 3

        snapshot = await service.get_game(
            game_id="game-1",
            player_token=first.player_token,
        )
        assert len(snapshot.seats) == 4
        assert all(seat.role is None for seat in snapshot.seats)

    asyncio.run(scenario())


def test_players_can_chat_and_vote_the_ai_out() -> None:
    async def scenario() -> None:
        clock = FixedClock(datetime(2026, 7, 2, 12, 0, tzinfo=UTC))
        config = GameConfig()
        service = GameService(
            repository=InMemoryGameRepository(),
            clock=clock,
            ids=SequenceIdGenerator(
                [
                    "ticket-1",
                    "token-1",
                    "ticket-2",
                    "token-2",
                    "ticket-3",
                    "token-3",
                    "game-1",
                    "message-1",
                ]
            ),
            random_source=SeededRandomSource(seed=7),
        )
        tickets = [
            await service.join_matchmaking(idempotency_key=f"join-{index}") for index in range(1, 4)
        ]
        matched = [
            await service.get_match(ticket_id=ticket.ticket_id, player_token=ticket.player_token)
            for ticket in tickets
        ]
        player = matched[0]
        assert player.game_id == "game-1"
        assert player.seat_id is not None

        await service.send_chat(
            game_id=player.game_id,
            player_token=player.player_token,
            content="Which one of us is the AI?",
            idempotency_key="chat-1",
        )
        discussion = await service.send_chat(
            game_id=player.game_id,
            player_token=player.player_token,
            content="This duplicate must not be posted.",
            idempotency_key="chat-1",
        )
        assert [message.content for message in discussion.messages] == [
            "Which one of us is the AI?"
        ]

        clock.advance(by=config.discussion_duration)
        voting = await service.get_game(
            game_id=player.game_id,
            player_token=player.player_token,
        )
        assert voting.phase.value == "voting"

        human_seats = {ticket.seat_id for ticket in matched}
        ai_seat = next(seat.id for seat in voting.seats if seat.id not in human_seats)
        for ticket in matched:
            await service.cast_vote(
                game_id=player.game_id,
                player_token=ticket.player_token,
                target_id=ai_seat,
                idempotency_key=f"vote-{ticket.seat_id}",
            )

        clock.advance(by=config.voting_duration)
        finished = await service.get_game(
            game_id=player.game_id,
            player_token=player.player_token,
        )
        assert finished.phase.value == "finished"
        assert finished.winner is not None
        assert finished.winner.value == "humans"
        assert sum(seat.role is not None for seat in finished.seats) == 4

    asyncio.run(scenario())
