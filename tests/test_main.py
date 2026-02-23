import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_read_root(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to FastAPI Blog"}
