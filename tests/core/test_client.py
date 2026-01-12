import pytest
import respx
from httpx import Response
from src.core.client import ProjectClient
from src.core.config import settings


@pytest.mark.asyncio
async def test_project_client_init_headers():
    """Test that ProjectClient initializes with correct headers from settings."""
    # Patch settings
    settings.FEISHU_PROJECT_USER_TOKEN = "mock_plugin_token"
    settings.FEISHU_PROJECT_USER_KEY = "mock_user_key"

    client = ProjectClient()

    assert client.headers["X-PLUGIN-TOKEN"] == "mock_plugin_token"
    assert client.headers["X-USER-KEY"] == "mock_user_key"
    assert client.headers["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_project_client_post(respx_mock):
    """Test ProjectClient.post method wrapper."""
    client = ProjectClient(base_url="https://mock.api")

    # Mock endpoint
    route = respx_mock.post("https://mock.api/test/create").mock(
        return_value=Response(200, json={"data": "success"})
    )

    response = await client.post("/test/create", json={"foo": "bar"})

    assert response.status_code == 200
    assert response.json() == {"data": "success"}
    assert route.called

    # Verify request payload
    last_req = route.calls.last.request
    import json

    assert json.loads(last_req.content) == {"foo": "bar"}


@pytest.mark.asyncio
async def test_project_client_get(respx_mock):
    """Test ProjectClient.get method wrapper."""
    client = ProjectClient(base_url="https://mock.api")

    route = respx_mock.get("https://mock.api/test/query").mock(
        return_value=Response(200, json={"items": []})
    )

    response = await client.get("/test/query", params={"page": 1})

    assert response.status_code == 200
    assert route.called
    # httpx merges params into URL
    assert "page=1" in str(route.calls.last.request.url)
