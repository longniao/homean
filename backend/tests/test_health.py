from httpx import AsyncClient


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "test-request-id"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"] == "test-request-id"
