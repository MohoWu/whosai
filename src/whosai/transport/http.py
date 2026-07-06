import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from whosai.ai.graph import build_ai_player_graph, with_decision_schema
from whosai.ai.player import LangGraphAIPlayer
from whosai.ai.providers import build_deepseek_chat_model
from whosai.ai.scripted import ScriptedAIPlayer
from whosai.application.game_service import (
    GameService,
    PlayerAuthorizationError,
    ResourceNotFoundError,
)
from whosai.application.models import MatchStatus
from whosai.application.ports import AIPlayer
from whosai.application.scheduling import AIPlayerScheduler, PhaseScheduler
from whosai.domain.game import Phase, Role, Winner
from whosai.infrastructure.memory import (
    InMemoryGameRepository,
    SeededRandomSource,
    SystemClock,
    UUIDIdGenerator,
)
from whosai.infrastructure.timers import AsyncioTimerScheduler


class HealthResponse(BaseModel):
    status: Literal["ok"]


class MatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticket_id: str
    player_token: str
    status: MatchStatus
    game_id: str | None
    seat_id: str | None


class SeatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alive: bool
    role: Role | None


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    seat_id: str
    content: str
    sent_at: datetime


class VoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    voter_id: str
    target_id: str


class RoundResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    round_number: int
    eliminated_id: str | None
    votes: tuple[VoteResponse, ...]


class LocalizedTextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    en: str
    zh_cn: str


class RoundBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: LocalizedTextResponse
    keyword: LocalizedTextResponse | None


class GameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    seats: tuple[SeatResponse, ...]
    phase: Phase
    round_number: int
    phase_deadline: datetime | None
    winner: Winner | None
    messages: tuple[ChatMessageResponse, ...]
    round_results: tuple[RoundResultResponse, ...]
    round_brief: RoundBriefResponse | None


class SendChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=500)


class CastVoteRequest(BaseModel):
    target_id: str = Field(min_length=1)


bearer_scheme = HTTPBearer(auto_error=False)
DEFAULT_FRONTEND_DIRECTORY = Path(__file__).resolve().parents[3] / "frontend" / "dist"


def _build_game_service(*, testing: bool) -> GameService:
    clock = SystemClock()
    timers = AsyncioTimerScheduler(clock=clock)
    phase_scheduler = PhaseScheduler(timers=timers)
    ai_scheduler: AIPlayerScheduler | None = None
    ai_player: AIPlayer | None = None
    random_source = SeededRandomSource(seed=7) if testing else SeededRandomSource()
    if testing:
        ai_player = ScriptedAIPlayer()
        ai_scheduler = AIPlayerScheduler(
            clock=clock,
            timers=timers,
            debounce=timedelta(milliseconds=100),
            maximum_wait=timedelta(milliseconds=500),
        )
    elif os.getenv("DEEPSEEK_API_KEY"):
        decision_model = with_decision_schema(build_deepseek_chat_model())
        ai_player = LangGraphAIPlayer(build_ai_player_graph(decision_model))
        ai_scheduler = AIPlayerScheduler(clock=clock, timers=timers)

    return GameService(
        repository=InMemoryGameRepository(),
        clock=clock,
        ids=UUIDIdGenerator(),
        random_source=random_source,
        phase_scheduler=phase_scheduler,
        ai_scheduler=ai_scheduler,
        ai_player=ai_player,
    )


def _require_player_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A bearer player token is required.",
        )
    return credentials.credentials


def create_app(
    *,
    game_service: GameService | None = None,
    enable_test_controls: bool = False,
    frontend_directory: Path | None = None,
) -> FastAPI:
    service = game_service or _build_game_service(testing=enable_test_controls)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        del app
        yield
        service.close()

    app = FastAPI(title="Who's AI?", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(ResourceNotFoundError)
    async def resource_not_found(
        request: Request,
        error: ResourceNotFoundError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(error)},
        )

    @app.exception_handler(PlayerAuthorizationError)
    async def player_not_authorized(
        request: Request,
        error: PlayerAuthorizationError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": str(error)},
        )

    @app.exception_handler(ValueError)
    async def game_rule_violation(
        request: Request,
        error: ValueError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(error)},
        )

    @app.get("/api/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.post(
        "/api/matchmaking/join",
        response_model=MatchResponse,
        tags=["matchmaking"],
    )
    async def join_matchmaking(
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
    ) -> MatchResponse:
        ticket = await service.join_matchmaking(idempotency_key=idempotency_key)
        return MatchResponse.model_validate(ticket)

    @app.get(
        "/api/matchmaking/{ticket_id}",
        response_model=MatchResponse,
        tags=["matchmaking"],
    )
    async def get_match(
        ticket_id: str,
        player_token: Annotated[str, Depends(_require_player_token)],
    ) -> MatchResponse:
        ticket = await service.get_match(
            ticket_id=ticket_id,
            player_token=player_token,
        )
        return MatchResponse.model_validate(ticket)

    @app.get(
        "/api/games/{game_id}",
        response_model=GameResponse,
        tags=["games"],
    )
    async def get_game(
        game_id: str,
        player_token: Annotated[str, Depends(_require_player_token)],
    ) -> GameResponse:
        game = await service.get_game(
            game_id=game_id,
            player_token=player_token,
        )
        return GameResponse.model_validate(game)

    @app.post(
        "/api/games/{game_id}/chat",
        response_model=GameResponse,
        tags=["games"],
    )
    async def send_chat(
        game_id: str,
        command: SendChatRequest,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
        player_token: Annotated[str, Depends(_require_player_token)],
    ) -> GameResponse:
        game = await service.send_chat(
            game_id=game_id,
            player_token=player_token,
            content=command.content,
            idempotency_key=idempotency_key,
        )
        return GameResponse.model_validate(game)

    @app.post(
        "/api/games/{game_id}/votes",
        response_model=GameResponse,
        tags=["games"],
    )
    async def cast_vote(
        game_id: str,
        command: CastVoteRequest,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
        player_token: Annotated[str, Depends(_require_player_token)],
    ) -> GameResponse:
        game = await service.cast_vote(
            game_id=game_id,
            player_token=player_token,
            target_id=command.target_id,
            idempotency_key=idempotency_key,
        )
        return GameResponse.model_validate(game)

    if enable_test_controls:

        @app.post(
            "/api/testing/games/{game_id}/advance",
            response_model=GameResponse,
            include_in_schema=False,
        )
        async def advance_phase_for_testing(
            game_id: str,
            idempotency_key: Annotated[
                str,
                Header(alias="Idempotency-Key", min_length=1),
            ],
            player_token: Annotated[str, Depends(_require_player_token)],
        ) -> GameResponse:
            game = await service.advance_phase_for_testing(
                game_id=game_id,
                player_token=player_token,
                idempotency_key=idempotency_key,
            )
            return GameResponse.model_validate(game)

    static_directory = frontend_directory or DEFAULT_FRONTEND_DIRECTORY
    if static_directory.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=static_directory, html=True),
            name="frontend",
        )

    return app
