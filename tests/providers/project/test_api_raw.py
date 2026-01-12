import pytest
import respx
from httpx import Response
from src.providers.project.api import WorkItemAPI


@pytest.mark.asyncio
async def test_filter_work_items(respx_mock):
    api = WorkItemAPI()
    project_key = "TEST_PROJ"

    # Mock Response
    mock_data = {
        "code": 0,
        "msg": "success",
        "data": {
            "data": [
                {
                    "id": 101,
                    "name": "Task A",
                    "project_key": project_key,
                    "work_item_type_key": "task",
                },
                {
                    "id": 102,
                    "name": "Task B",
                    "project_key": project_key,
                    "work_item_type_key": "bug",
                },
            ],
            "pagination": {"total": 2, "page_num": 1, "page_size": 50},
        },
    }

    # Exact match on URL
    route = respx_mock.post(
        f"https://project.feishu.cn/open_api/{project_key}/work_item/filter"
    ).mock(return_value=Response(200, json=mock_data))

    response = await api.filter_work_items(project_key, status=["in_progress"])

    assert response.is_success
    assert len(response.data.items) == 2
    assert response.data.items[0].name == "Task A"
    assert route.called

    # Verify request payload
    import json

    req_body = json.loads(route.calls.last.request.content)
    assert req_body["work_item_status"] == ["in_progress"]


@pytest.mark.asyncio
async def test_create_work_item(respx_mock):
    api = WorkItemAPI()
    project_key = "TEST_PROJ"

    mock_data = {
        "code": 0,
        "msg": "success",
        "data": 888888,  # The ID
    }

    route = respx_mock.post(
        f"https://project.feishu.cn/open_api/{project_key}/work_item/create"
    ).mock(return_value=Response(200, json=mock_data))

    resp = await api.create_work_item(project_key, "New Feature", "story")

    assert resp.is_success
    assert resp.data == 888888

    # Verify payload
    import json

    req_body = json.loads(route.calls.last.request.content)
    assert req_body["name"] == "New Feature"
    assert req_body["work_item_type_key"] == "story"
