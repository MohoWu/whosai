import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from whosai.application.game_service import GameService
from whosai.domain.game import GameConfig
from whosai.infrastructure.memory import (
    InMemoryGameRepository,
    SeededRandomSource,
    SequenceIdGenerator,
)
from whosai.transport.http import create_app


class FixedClock:
    def __init__(self) -> None:
        self._now = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, *, by: timedelta) -> None:
        self._now += by


def test_http_matchmaking_creates_a_hidden_role_game() -> None:
    async def scenario() -> None:
        service = GameService(
            repository=InMemoryGameRepository(),
            clock=FixedClock(),
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
        transport = ASGITransport(app=create_app(game_service=service))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            joins = [
                await client.post(
                    "/api/matchmaking/join",
                    headers={"Idempotency-Key": f"join-{index}"},
                )
                for index in range(1, 4)
            ]
            assert joins[0].status_code == 200
            assert joins[0].json()["status"] == "waiting"
            assert joins[2].json()["status"] == "matched"

            first = joins[0].json()
            match = await client.get(
                f"/api/matchmaking/{first['ticket_id']}",
                headers={"Authorization": f"Bearer {first['player_token']}"},
            )
            assert match.status_code == 200
            assert match.json()["game_id"] == "game-1"

            game = await client.get(
                "/api/games/game-1",
                headers={"Authorization": f"Bearer {first['player_token']}"},
            )
            assert game.status_code == 200
            assert len(game.json()["seats"]) == 4
            assert all(seat["role"] is None for seat in game.json()["seats"])

    asyncio.run(scenario())


def test_http_players_can_chat_and_vote_the_ai_out() -> None:
    async def scenario() -> None:
        clock = FixedClock()
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
        transport = ASGITransport(app=create_app(game_service=service))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            joins = [
                (
                    await client.post(
                        "/api/matchmaking/join",
                        headers={"Idempotency-Key": f"join-{index}"},
                    )
                ).json()
                for index in range(1, 4)
            ]
            matched = [
                (
                    await client.get(
                        f"/api/matchmaking/{join['ticket_id']}",
                        headers={"Authorization": f"Bearer {join['player_token']}"},
                    )
                ).json()
                for join in joins
            ]

            player = matched[0]
            auth = {"Authorization": f"Bearer {player['player_token']}"}
            chat = await client.post(
                "/api/games/game-1/chat",
                headers={**auth, "Idempotency-Key": "chat-1"},
                json={"content": "Which one of us is the AI?"},
            )
            assert chat.status_code == 200
            duplicate = await client.post(
                "/api/games/game-1/chat",
                headers={**auth, "Idempotency-Key": "chat-1"},
                json={"content": "This duplicate must not be posted."},
            )
            assert [message["content"] for message in duplicate.json()["messages"]] == [
                "Which one of us is the AI?"
            ]

            clock.advance(by=config.discussion_duration)
            voting = await client.get("/api/games/game-1", headers=auth)
            assert voting.json()["phase"] == "voting"
            human_seats = {match["seat_id"] for match in matched}
            ai_seat = next(
                seat["id"] for seat in voting.json()["seats"] if seat["id"] not in human_seats
            )

            for match in matched:
                vote = await client.post(
                    "/api/games/game-1/votes",
                    headers={
                        "Authorization": f"Bearer {match['player_token']}",
                        "Idempotency-Key": f"vote-{match['seat_id']}",
                    },
                    json={"target_id": ai_seat},
                )
                assert vote.status_code == 200

            clock.advance(by=config.voting_duration)
            finished = await client.get("/api/games/game-1", headers=auth)
            assert finished.json()["phase"] == "finished"
            assert finished.json()["winner"] == "humans"
            assert all(seat["role"] is not None for seat in finished.json()["seats"])
            assert finished.json()["round_results"] == [
                {
                    "round_number": 1,
                    "eliminated_id": ai_seat,
                    "votes": [
                        {
                            "voter_id": match["seat_id"],
                            "target_id": ai_seat,
                        }
                        for match in matched
                    ],
                }
            ]

    asyncio.run(scenario())


def test_http_test_control_can_expire_a_phase_when_explicitly_enabled() -> None:
    async def scenario() -> None:
        service = GameService(
            repository=InMemoryGameRepository(),
            clock=FixedClock(),
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
        transport = ASGITransport(
            app=create_app(
                game_service=service,
                enable_test_controls=True,
            )
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            joins = [
                (
                    await client.post(
                        "/api/matchmaking/join",
                        headers={"Idempotency-Key": f"join-{index}"},
                    )
                ).json()
                for index in range(1, 4)
            ]
            player = joins[-1]
            response = await client.post(
                "/api/testing/games/game-1/advance",
                headers={
                    "Authorization": f"Bearer {player['player_token']}",
                    "Idempotency-Key": "advance-discussion",
                },
            )

            assert response.status_code == 200
            assert response.json()["phase"] == "voting"

    asyncio.run(scenario())


def test_http_serves_the_built_frontend_without_shadowing_the_api(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        (tmp_path / "index.html").write_text(
            "<!doctype html><title>Who's AI?</title>",
            encoding="utf-8",
        )
        service = GameService(
            repository=InMemoryGameRepository(),
            clock=FixedClock(),
            ids=SequenceIdGenerator([]),
            random_source=SeededRandomSource(seed=7),
        )
        transport = ASGITransport(
            app=create_app(
                game_service=service,
                frontend_directory=tmp_path,
            )
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            frontend = await client.get("/")
            health = await client.get("/api/health")

            assert frontend.status_code == 200
            assert "Who's AI?" in frontend.text
            assert health.status_code == 200
            assert health.json() == {"status": "ok"}

    asyncio.run(scenario())
