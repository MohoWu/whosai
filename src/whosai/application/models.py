from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from whosai.domain.game import ChatMessage, Phase


class MatchStatus(StrEnum):
    WAITING = "waiting"
    MATCHED = "matched"


@dataclass(frozen=True, slots=True)
class MatchTicket:
    ticket_id: str
    player_token: str
    join_idempotency_key: str
    status: MatchStatus
    game_id: str | None = None
    seat_id: str | None = None


@dataclass(frozen=True, slots=True)
class AIDecisionTrigger:
    game_id: str
    seat_id: str
    round_number: int
    phase: Phase
    turn_number: int
    new_message_count: int
    direct_mention: bool
    through_message_id: str | None


@dataclass(frozen=True, slots=True)
class AIPlayerRequest:
    game_id: str
    seat_id: str
    round_number: int
    phase: Phase
    turn_number: int
    new_message_count: int
    direct_mention: bool
    chat_history: tuple[ChatMessage, ...]
    eligible_vote_targets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AIPlayerDecision:
    action: Literal["speak", "wait", "vote"]
    response: str | None
    target_seat_id: str | None
