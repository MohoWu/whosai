from collections import Counter
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from whosai.domain.keywords import LocalizedText


class Phase(StrEnum):
    LOBBY = "lobby"
    DISCUSSION = "discussion"
    VOTING = "voting"
    RESOLUTION = "resolution"
    FINISHED = "finished"


class Role(StrEnum):
    HUMAN = "human"
    AI = "ai"


class Winner(StrEnum):
    HUMANS = "humans"
    AI = "ai"


@dataclass(frozen=True, slots=True)
class GameConfig:
    discussion_duration: timedelta = timedelta(seconds=300)
    voting_duration: timedelta = timedelta(seconds=30)

    def __post_init__(self) -> None:
        if self.discussion_duration <= timedelta(0):
            raise ValueError("Discussion duration must be positive.")
        if self.voting_duration <= timedelta(0):
            raise ValueError("Voting duration must be positive.")


@dataclass(frozen=True, slots=True)
class Seat:
    id: str
    role: Role
    alive: bool = True


@dataclass(frozen=True, slots=True)
class ChatMessage:
    id: str
    seat_id: str
    content: str
    sent_at: datetime


@dataclass(frozen=True, slots=True)
class Vote:
    voter_id: str
    target_id: str


@dataclass(frozen=True, slots=True)
class RoundResult:
    round_number: int
    eliminated_id: str | None
    votes: tuple[Vote, ...]


@dataclass(frozen=True, slots=True)
class RoundSecret:
    category: LocalizedText
    keyword: LocalizedText
    uninformed_seat_id: str


@dataclass(frozen=True, slots=True)
class PlayerRoundBrief:
    category: LocalizedText
    keyword: LocalizedText | None


@dataclass(frozen=True, slots=True)
class Game:
    id: str
    seats: tuple[Seat, ...]
    phase: Phase
    round_number: int
    phase_deadline: datetime | None
    winner: Winner | None
    config: GameConfig
    messages: tuple[ChatMessage, ...] = ()
    votes: tuple[Vote, ...] = ()
    round_results: tuple[RoundResult, ...] = ()
    round_secret: RoundSecret | None = None


@dataclass(frozen=True, slots=True)
class PublicSeat:
    id: str
    alive: bool
    role: Role | None


@dataclass(frozen=True, slots=True)
class PublicGameState:
    id: str
    seats: tuple[PublicSeat, ...]
    phase: Phase
    round_number: int
    phase_deadline: datetime | None
    winner: Winner | None
    messages: tuple[ChatMessage, ...]
    round_results: tuple[RoundResult, ...]
    round_brief: PlayerRoundBrief | None


def create_four_seat_game(
    *,
    game_id: str,
    ai_seat_id: str,
    now: datetime,
    config: GameConfig | None = None,
) -> Game:
    if now.tzinfo is None:
        raise ValueError("Game creation time must include a timezone.")

    seat_ids = tuple(f"Player {index}" for index in range(1, 5))
    if ai_seat_id not in seat_ids:
        raise ValueError(f"Unknown AI seat: {ai_seat_id}.")

    effective_config = config or GameConfig()
    started_at = now.astimezone(UTC)
    seats = tuple(
        Seat(id=seat_id, role=Role.AI if seat_id == ai_seat_id else Role.HUMAN)
        for seat_id in seat_ids
    )
    return Game(
        id=game_id,
        seats=seats,
        phase=Phase.DISCUSSION,
        round_number=1,
        phase_deadline=started_at + effective_config.discussion_duration,
        winner=None,
        config=effective_config,
    )


def assign_round_secret(
    game: Game,
    *,
    category: LocalizedText,
    keyword: LocalizedText,
    uninformed_seat_id: str,
) -> Game:
    if game.phase is not Phase.DISCUSSION:
        raise ValueError("Round secrets can only be assigned during discussion.")
    uninformed_seat = next(
        (seat for seat in game.seats if seat.id == uninformed_seat_id),
        None,
    )
    if uninformed_seat is None:
        raise ValueError(f"Unknown uninformed seat: {uninformed_seat_id}.")
    if not uninformed_seat.alive:
        raise ValueError("The uninformed seat must be alive.")
    return replace(
        game,
        round_secret=RoundSecret(
            category=category,
            keyword=keyword,
            uninformed_seat_id=uninformed_seat_id,
        ),
    )


def player_round_brief(game: Game, *, seat_id: str) -> PlayerRoundBrief | None:
    seat = next((candidate for candidate in game.seats if candidate.id == seat_id), None)
    if seat is None:
        raise ValueError(f"Unknown seat: {seat_id}.")
    if not seat.alive or game.round_secret is None:
        return None
    return PlayerRoundBrief(
        category=game.round_secret.category,
        keyword=(
            None if game.round_secret.uninformed_seat_id == seat_id else game.round_secret.keyword
        ),
    )


def public_game_state(
    game: Game,
    *,
    viewer_seat_id: str | None = None,
) -> PublicGameState:
    reveal_roles = game.phase is Phase.FINISHED
    return PublicGameState(
        id=game.id,
        seats=tuple(
            PublicSeat(
                id=seat.id,
                alive=seat.alive,
                role=seat.role if reveal_roles else None,
            )
            for seat in game.seats
        ),
        phase=game.phase,
        round_number=game.round_number,
        phase_deadline=game.phase_deadline,
        winner=game.winner,
        messages=game.messages,
        round_results=game.round_results,
        round_brief=(
            player_round_brief(game, seat_id=viewer_seat_id) if viewer_seat_id is not None else None
        ),
    )


def advance_game(game: Game, *, now: datetime) -> Game:
    if now.tzinfo is None:
        raise ValueError("Game advancement time must include a timezone.")
    if game.phase_deadline is None or now < game.phase_deadline:
        return game

    advanced_at = now.astimezone(UTC)
    if game.phase is Phase.DISCUSSION:
        return replace(
            game,
            phase=Phase.VOTING,
            phase_deadline=advanced_at + game.config.voting_duration,
        )
    if game.phase is Phase.VOTING:
        return _resolve_voting(game, now=advanced_at)
    return game


def post_chat(
    game: Game,
    *,
    message_id: str,
    seat_id: str,
    content: str,
    now: datetime,
) -> Game:
    if now.tzinfo is None:
        raise ValueError("Chat time must include a timezone.")
    if game.phase is not Phase.DISCUSSION:
        raise ValueError("Chat is only allowed during discussion.")
    if game.phase_deadline is not None and now >= game.phase_deadline:
        raise ValueError("The discussion deadline has passed.")

    seat = next((candidate for candidate in game.seats if candidate.id == seat_id), None)
    if seat is None:
        raise ValueError(f"Unknown seat: {seat_id}.")
    if not seat.alive:
        raise ValueError("Eliminated players cannot chat.")

    normalized_content = content.strip()
    if not normalized_content:
        raise ValueError("Chat content cannot be empty.")
    if len(normalized_content) > 500:
        raise ValueError("Chat content cannot exceed 500 characters.")

    message = ChatMessage(
        id=message_id,
        seat_id=seat_id,
        content=normalized_content,
        sent_at=now.astimezone(UTC),
    )
    return replace(game, messages=(*game.messages, message))


def cast_vote(game: Game, *, voter_id: str, target_id: str) -> Game:
    if game.phase is not Phase.VOTING:
        raise ValueError("Votes are only allowed during voting.")

    voter = next((seat for seat in game.seats if seat.id == voter_id), None)
    target = next((seat for seat in game.seats if seat.id == target_id), None)
    if voter is None:
        raise ValueError(f"Unknown voter: {voter_id}.")
    if target is None:
        raise ValueError(f"Unknown vote target: {target_id}.")
    if not voter.alive:
        raise ValueError("Eliminated players cannot vote.")
    if not target.alive:
        raise ValueError("Votes must target a living player.")
    if any(vote.voter_id == voter_id for vote in game.votes):
        raise ValueError("A player's first vote is final.")

    return replace(game, votes=(*game.votes, Vote(voter_id=voter_id, target_id=target_id)))


def _resolve_voting(game: Game, *, now: datetime) -> Game:
    resolution = replace(game, phase=Phase.RESOLUTION, phase_deadline=None)
    vote_counts = Counter(vote.target_id for vote in resolution.votes)
    eliminated_id: str | None = None
    if vote_counts:
        highest_count = max(vote_counts.values())
        leaders = [target_id for target_id, count in vote_counts.items() if count == highest_count]
        if len(leaders) == 1:
            eliminated_id = leaders[0]

    seats = tuple(
        replace(seat, alive=False) if seat.id == eliminated_id else seat
        for seat in resolution.seats
    )
    round_result = RoundResult(
        round_number=resolution.round_number,
        eliminated_id=eliminated_id,
        votes=resolution.votes,
    )
    round_results = (*resolution.round_results, round_result)
    living_humans = sum(seat.alive and seat.role is Role.HUMAN for seat in seats)
    living_ais = sum(seat.alive and seat.role is Role.AI for seat in seats)

    winner: Winner | None = None
    if living_ais == 0:
        winner = Winner.HUMANS
    elif living_humans == living_ais:
        winner = Winner.AI

    if winner is not None:
        return replace(
            resolution,
            seats=seats,
            phase=Phase.FINISHED,
            winner=winner,
            round_results=round_results,
        )

    return replace(
        resolution,
        seats=seats,
        phase=Phase.DISCUSSION,
        round_number=resolution.round_number + 1,
        phase_deadline=now + resolution.config.discussion_duration,
        messages=(),
        votes=(),
        round_results=round_results,
        round_secret=None,
    )
