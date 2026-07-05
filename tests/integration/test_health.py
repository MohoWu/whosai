import asyncio

from httpx import ASGITransport, AsyncClient

from whosai.transport.http import create_app


def test_health_endpoint() -> None:
    async def request_health() -> tuple[int, object]:
        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")
        return response.status_code, response.json()

    status_code, body = asyncio.run(request_health())

    assert status_code == 200
    assert body == {"status": "ok"}
