from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime
from typing import Protocol

from whosai.application.models import AIPlayerDecision, AIPlayerRequest, MatchTicket
from whosai.domain.game import Game


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdGenerator(Protocol):
    def new_id(self) -> str: ...


class RandomSource(Protocol):
    def shuffled(self, values: Sequence[str]) -> tuple[str, ...]: ...


class ScheduledJob(Protocol):
    def cancel(self) -> None: ...


ScheduledCallback = Callable[[], Awaitable[None]]


class TimerScheduler(Protocol):
    def schedule(
        self,
        *,
        deadline: datetime,
        callback: ScheduledCallback,
    ) -> ScheduledJob: ...


class AIPlayer(Protocol):
    async def decide(self, request: AIPlayerRequest) -> AIPlayerDecision: ...


class GameRepository(Protocol):
    async def get_game(self, game_id: str) -> Game | None: ...

    async def save_game(self, game: Game) -> None: ...

    async def get_ticket(self, ticket_id: str) -> MatchTicket | None: ...

    async def get_ticket_by_join_key(
        self,
        idempotency_key: str,
    ) -> MatchTicket | None: ...

    async def get_ticket_for_player(
        self,
        *,
        game_id: str,
        player_token: str,
    ) -> MatchTicket | None: ...

    async def save_ticket(self, ticket: MatchTicket) -> None: ...

    async def waiting_tickets(self, *, limit: int) -> tuple[MatchTicket, ...]: ...

    async def has_command(
        self,
        *,
        game_id: str,
        seat_id: str,
        command: str,
        idempotency_key: str,
    ) -> bool: ...

    async def save_command(
        self,
        *,
        game_id: str,
        seat_id: str,
        command: str,
        idempotency_key: str,
    ) -> None: ...
