import random
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

from whosai.application.models import MatchStatus, MatchTicket
from whosai.domain.game import Game


class InMemoryGameRepository:
    def __init__(self) -> None:
        self._games: dict[str, Game] = {}
        self._tickets: dict[str, MatchTicket] = {}
        self._commands: set[tuple[str, str, str, str]] = set()

    async def get_game(self, game_id: str) -> Game | None:
        return self._games.get(game_id)

    async def save_game(self, game: Game) -> None:
        self._games[game.id] = game

    async def get_ticket(self, ticket_id: str) -> MatchTicket | None:
        return self._tickets.get(ticket_id)

    async def get_ticket_by_join_key(
        self,
        idempotency_key: str,
    ) -> MatchTicket | None:
        return next(
            (
                ticket
                for ticket in self._tickets.values()
                if ticket.join_idempotency_key == idempotency_key
            ),
            None,
        )

    async def get_ticket_for_player(
        self,
        *,
        game_id: str,
        player_token: str,
    ) -> MatchTicket | None:
        return next(
            (
                ticket
                for ticket in self._tickets.values()
                if ticket.game_id == game_id and ticket.player_token == player_token
            ),
            None,
        )

    async def save_ticket(self, ticket: MatchTicket) -> None:
        self._tickets[ticket.ticket_id] = ticket

    async def waiting_tickets(self, *, limit: int) -> tuple[MatchTicket, ...]:
        return tuple(
            ticket for ticket in self._tickets.values() if ticket.status is MatchStatus.WAITING
        )[:limit]

    async def has_command(
        self,
        *,
        game_id: str,
        seat_id: str,
        command: str,
        idempotency_key: str,
    ) -> bool:
        return (game_id, seat_id, command, idempotency_key) in self._commands

    async def save_command(
        self,
        *,
        game_id: str,
        seat_id: str,
        command: str,
        idempotency_key: str,
    ) -> None:
        self._commands.add((game_id, seat_id, command, idempotency_key))


class SequenceIdGenerator:
    def __init__(self, values: Sequence[str]) -> None:
        self._values = iter(values)

    def new_id(self) -> str:
        try:
            return next(self._values)
        except StopIteration as error:
            raise RuntimeError("The ID sequence is exhausted.") from error


class UUIDIdGenerator:
    def new_id(self) -> str:
        return uuid4().hex


class SeededRandomSource:
    def __init__(self, *, seed: int | None = None) -> None:
        self._random = random.Random(seed)

    def shuffled(self, values: Sequence[str]) -> tuple[str, ...]:
        return tuple(self._random.sample(tuple(values), k=len(values)))


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)
