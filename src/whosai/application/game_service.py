import asyncio
from dataclasses import replace

from whosai.application.models import (
    AIDecisionTrigger,
    AIPlayerRequest,
    MatchStatus,
    MatchTicket,
)
from whosai.application.ports import (
    AIPlayer,
    Clock,
    GameRepository,
    IdGenerator,
    RandomSource,
)
from whosai.application.scheduling import AIPlayerScheduler, PhaseScheduler
from whosai.domain.game import (
    Game,
    Phase,
    PublicGameState,
    Role,
    advance_game,
    create_four_seat_game,
    post_chat,
    public_game_state,
)
from whosai.domain.game import (
    cast_vote as apply_vote,
)


class ResourceNotFoundError(LookupError):
    pass


class PlayerAuthorizationError(PermissionError):
    pass


class GameService:
    def __init__(
        self,
        *,
        repository: GameRepository,
        clock: Clock,
        ids: IdGenerator,
        random_source: RandomSource,
        phase_scheduler: PhaseScheduler | None = None,
        ai_scheduler: AIPlayerScheduler | None = None,
        ai_player: AIPlayer | None = None,
    ) -> None:
        if (ai_scheduler is None) != (ai_player is None):
            raise ValueError("AI scheduler and AI player must be configured together.")
        self._repository = repository
        self._clock = clock
        self._ids = ids
        self._random_source = random_source
        self._phase_scheduler = phase_scheduler
        self._ai_scheduler = ai_scheduler
        self._ai_player = ai_player
        self._lock = asyncio.Lock()

    async def join_matchmaking(self, *, idempotency_key: str) -> MatchTicket:
        if not idempotency_key.strip():
            raise ValueError("An idempotency key is required.")

        async with self._lock:
            existing = await self._repository.get_ticket_by_join_key(idempotency_key)
            if existing is not None:
                return existing

            ticket = MatchTicket(
                ticket_id=self._ids.new_id(),
                player_token=self._ids.new_id(),
                join_idempotency_key=idempotency_key,
                status=MatchStatus.WAITING,
            )
            await self._repository.save_ticket(ticket)
            waiting = await self._repository.waiting_tickets(limit=3)
            if len(waiting) == 3:
                await self._start_game(waiting)

            saved = await self._repository.get_ticket(ticket.ticket_id)
            if saved is None:
                raise RuntimeError("Match ticket disappeared after it was saved.")
            return saved

    async def get_match(self, *, ticket_id: str, player_token: str) -> MatchTicket:
        ticket = await self._repository.get_ticket(ticket_id)
        if ticket is None:
            raise ResourceNotFoundError(f"Unknown match ticket: {ticket_id}.")
        if ticket.player_token != player_token:
            raise PlayerAuthorizationError("The player token does not own this match ticket.")
        return ticket

    async def get_game(self, *, game_id: str, player_token: str) -> PublicGameState:
        async with self._lock:
            await self._authorize_player(game_id=game_id, player_token=player_token)
            game = await self._repository.get_game(game_id)
            if game is None:
                raise ResourceNotFoundError(f"Unknown game: {game_id}.")
            advanced = await self._advance_to_now(game)
            return public_game_state(advanced)

    async def send_chat(
        self,
        *,
        game_id: str,
        player_token: str,
        content: str,
        idempotency_key: str,
    ) -> PublicGameState:
        self._validate_idempotency_key(idempotency_key)
        async with self._lock:
            seat_id, game = await self._load_authorized_game(
                game_id=game_id,
                player_token=player_token,
            )
            updated = await self._send_chat_for_seat(
                game,
                seat_id=seat_id,
                content=content,
                idempotency_key=idempotency_key,
            )
            return public_game_state(updated)

    async def cast_vote(
        self,
        *,
        game_id: str,
        player_token: str,
        target_id: str,
        idempotency_key: str,
    ) -> PublicGameState:
        self._validate_idempotency_key(idempotency_key)
        async with self._lock:
            seat_id, game = await self._load_authorized_game(
                game_id=game_id,
                player_token=player_token,
            )
            updated = await self._cast_vote_for_seat(
                game,
                seat_id=seat_id,
                target_id=target_id,
                idempotency_key=idempotency_key,
            )
            return public_game_state(updated)

    async def advance_phase_for_testing(
        self,
        *,
        game_id: str,
        player_token: str,
        idempotency_key: str,
    ) -> PublicGameState:
        """Expire the current deadline through an authenticated test-only command."""
        self._validate_idempotency_key(idempotency_key)
        async with self._lock:
            seat_id, game = await self._load_authorized_game(
                game_id=game_id,
                player_token=player_token,
            )
            if await self._repository.has_command(
                game_id=game.id,
                seat_id=seat_id,
                command="test-advance",
                idempotency_key=idempotency_key,
            ):
                return public_game_state(game)
            if game.phase_deadline is None:
                raise ValueError("The current phase does not have a deadline.")

            expired = replace(game, phase_deadline=self._clock.now())
            await self._repository.save_game(expired)
            advanced = await self._advance_to_now(expired)
            await self._repository.save_command(
                game_id=game.id,
                seat_id=seat_id,
                command="test-advance",
                idempotency_key=idempotency_key,
            )
            return public_game_state(advanced)

    async def _start_game(self, tickets: tuple[MatchTicket, ...]) -> None:
        game_id = self._ids.new_id()
        seat_ids = self._random_source.shuffled(("Player 1", "Player 2", "Player 3", "Player 4"))
        ai_seat_id, *human_seat_ids = seat_ids
        game = create_four_seat_game(
            game_id=game_id,
            ai_seat_id=ai_seat_id,
            now=self._clock.now(),
        )
        await self._repository.save_game(game)
        self._synchronize_new_game(game)
        for ticket, seat_id in zip(tickets, human_seat_ids, strict=True):
            await self._repository.save_ticket(
                replace(
                    ticket,
                    status=MatchStatus.MATCHED,
                    game_id=game_id,
                    seat_id=seat_id,
                )
            )

    async def _authorize_player(self, *, game_id: str, player_token: str) -> MatchTicket:
        ticket = await self._repository.get_ticket_for_player(
            game_id=game_id,
            player_token=player_token,
        )
        if ticket is None:
            raise PlayerAuthorizationError("The player token does not belong to this game.")
        return ticket

    async def _load_authorized_game(
        self,
        *,
        game_id: str,
        player_token: str,
    ) -> tuple[str, Game]:
        ticket = await self._authorize_player(
            game_id=game_id,
            player_token=player_token,
        )
        if ticket.seat_id is None:
            raise RuntimeError("A matched ticket must have a seat ID.")
        game = await self._repository.get_game(game_id)
        if game is None:
            raise ResourceNotFoundError(f"Unknown game: {game_id}.")
        advanced = await self._advance_to_now(game)
        return ticket.seat_id, advanced

    @staticmethod
    def _validate_idempotency_key(idempotency_key: str) -> None:
        if not idempotency_key.strip():
            raise ValueError("An idempotency key is required.")

    async def advance_due_phase(self, game_id: str) -> None:
        """Advance one game's expired deadlines without requiring a client request."""
        async with self._lock:
            game = await self._repository.get_game(game_id)
            if game is None:
                return
            advanced = await self._advance_to_now(game)
            if advanced == game and self._phase_scheduler is not None:
                self._phase_scheduler.synchronize(
                    game,
                    on_deadline=self.advance_due_phase,
                )

    async def _advance_to_now(self, game: Game) -> Game:
        now = self._clock.now()
        current = game
        transitions: list[tuple[Game, Game]] = []
        while current.phase_deadline is not None and current.phase_deadline <= now:
            advanced = advance_game(current, now=now)
            if advanced == current:
                break
            transitions.append((current, advanced))
            current = advanced
        if current != game:
            await self._repository.save_game(current)
            for previous, advanced in transitions:
                self._synchronize_phase_transition(previous, advanced)
        return current

    def _synchronize_new_game(self, game: Game) -> None:
        if self._phase_scheduler is not None:
            self._phase_scheduler.synchronize(
                game,
                on_deadline=self.advance_due_phase,
            )
        if self._ai_scheduler is not None:
            self._ai_scheduler.discussion_started(game)

    def _synchronize_phase_transition(self, previous: Game, current: Game) -> None:
        if self._phase_scheduler is not None:
            self._phase_scheduler.synchronize(
                current,
                on_deadline=self.advance_due_phase,
            )
        if self._ai_scheduler is None or previous.phase is current.phase:
            return
        if current.phase is Phase.VOTING:
            self._ai_scheduler.voting_started(
                current,
                on_decision=self._run_ai_decision,
            )
        elif current.phase is Phase.DISCUSSION:
            self._ai_scheduler.discussion_started(current)
        elif current.phase is Phase.FINISHED:
            self._ai_scheduler.game_finished(current.id)

    def _schedule_ai_for_chat(self, game: Game, *, author_seat_id: str) -> None:
        if self._ai_scheduler is None:
            return
        self._ai_scheduler.chat_posted(
            game,
            author_seat_id=author_seat_id,
            on_decision=self._run_ai_decision,
        )

    async def _run_ai_decision(self, trigger: AIDecisionTrigger) -> None:
        if self._ai_player is None:
            return

        async with self._lock:
            game = await self._repository.get_game(trigger.game_id)
            if game is None:
                return
            game = await self._advance_to_now(game)
            request = self._build_ai_request(game, trigger)
        if request is None:
            return

        decision = await self._ai_player.decide(request)

        async with self._lock:
            current = await self._repository.get_game(trigger.game_id)
            if current is None:
                return
            current = await self._advance_to_now(current)
            if not self._trigger_is_current(current, trigger):
                return

            idempotency_key = (
                f"ai:{trigger.phase.value}:{trigger.round_number}:{trigger.turn_number}"
            )
            if decision.action == "wait":
                return
            if decision.action == "speak":
                if decision.response is None:
                    return
                await self._send_chat_for_seat(
                    current,
                    seat_id=trigger.seat_id,
                    content=decision.response,
                    idempotency_key=idempotency_key,
                    message_id=(
                        f"{trigger.game_id}:{trigger.seat_id}:"
                        f"{trigger.round_number}:{trigger.turn_number}"
                    ),
                )
                return
            if (
                decision.action == "vote"
                and decision.target_seat_id in request.eligible_vote_targets
            ):
                await self._cast_vote_for_seat(
                    current,
                    seat_id=trigger.seat_id,
                    target_id=decision.target_seat_id,
                    idempotency_key=idempotency_key,
                )

    async def _send_chat_for_seat(
        self,
        game: Game,
        *,
        seat_id: str,
        content: str,
        idempotency_key: str,
        message_id: str | None = None,
    ) -> Game:
        if await self._repository.has_command(
            game_id=game.id,
            seat_id=seat_id,
            command="chat",
            idempotency_key=idempotency_key,
        ):
            return game
        updated = post_chat(
            game,
            message_id=message_id or self._ids.new_id(),
            seat_id=seat_id,
            content=content,
            now=self._clock.now(),
        )
        await self._repository.save_game(updated)
        await self._repository.save_command(
            game_id=game.id,
            seat_id=seat_id,
            command="chat",
            idempotency_key=idempotency_key,
        )
        self._schedule_ai_for_chat(updated, author_seat_id=seat_id)
        return updated

    async def _cast_vote_for_seat(
        self,
        game: Game,
        *,
        seat_id: str,
        target_id: str,
        idempotency_key: str,
    ) -> Game:
        if await self._repository.has_command(
            game_id=game.id,
            seat_id=seat_id,
            command="vote",
            idempotency_key=idempotency_key,
        ):
            return game
        updated = apply_vote(
            game,
            voter_id=seat_id,
            target_id=target_id,
        )
        await self._repository.save_game(updated)
        await self._repository.save_command(
            game_id=game.id,
            seat_id=seat_id,
            command="vote",
            idempotency_key=idempotency_key,
        )
        return updated

    @staticmethod
    def _build_ai_request(
        game: Game,
        trigger: AIDecisionTrigger,
    ) -> AIPlayerRequest | None:
        if not GameService._trigger_is_current(game, trigger):
            return None

        chat_history = game.messages
        if trigger.phase is Phase.DISCUSSION:
            if trigger.through_message_id is None:
                return None
            through_index = next(
                (
                    index
                    for index, message in enumerate(game.messages)
                    if message.id == trigger.through_message_id
                ),
                None,
            )
            if through_index is None:
                return None
            chat_history = game.messages[: through_index + 1]

        eligible_vote_targets: tuple[str, ...] = ()
        if trigger.phase is Phase.VOTING:
            eligible_vote_targets = tuple(
                seat.id for seat in game.seats if seat.alive and seat.id != trigger.seat_id
            )

        return AIPlayerRequest(
            game_id=trigger.game_id,
            seat_id=trigger.seat_id,
            round_number=trigger.round_number,
            phase=trigger.phase,
            turn_number=trigger.turn_number,
            new_message_count=trigger.new_message_count,
            direct_mention=trigger.direct_mention,
            chat_history=chat_history,
            eligible_vote_targets=eligible_vote_targets,
        )

    @staticmethod
    def _trigger_is_current(game: Game, trigger: AIDecisionTrigger) -> bool:
        if game.round_number != trigger.round_number or game.phase is not trigger.phase:
            return False
        seat = next((seat for seat in game.seats if seat.id == trigger.seat_id), None)
        return seat is not None and seat.alive and seat.role is Role.AI

    def close(self) -> None:
        if self._phase_scheduler is not None:
            self._phase_scheduler.close()
        if self._ai_scheduler is not None:
            self._ai_scheduler.close()


__all__ = ["GameService", "MatchStatus"]
