import pytest
from unittest.mock import AsyncMock, MagicMock
from src.providers.project.manager import ProjectManager
from src.schemas.project import BaseResponse, WorkItemListData, WorkItem, Pagination


@pytest.fixture
def mock_api():
    api = AsyncMock()
    return api


@pytest.mark.asyncio
async def test_get_active_tasks(mock_api):
    manager = ProjectManager(project_key="TEST_PROJ", api_client=mock_api)

    # Mock API Response
    mock_items = [
        WorkItem(
            id=1, name="Task 1", project_key="TEST_PROJ", work_item_type_key="task"
        ),
        WorkItem(id=2, name="Bug 1", project_key="TEST_PROJ", work_item_type_key="bug"),
    ]
    mock_response = BaseResponse[WorkItemListData](
        code=0,
        msg="success",
        data=WorkItemListData(data=mock_items, pagination=Pagination(total=2)),
    )
    mock_api.filter_work_items.return_value = mock_response

    # Action
    tasks = await manager.get_active_tasks()

    # Assertions
    mock_api.filter_work_items.assert_called_once()
    call_args = mock_api.filter_work_items.call_args
    assert call_args.kwargs["project_key"] == "TEST_PROJ"
    assert "in_progress" in call_args.kwargs["status"]

    # Verify simplified output
    assert len(tasks) == 2
    assert tasks[0]["id"] == 1
    assert tasks[0]["name"] == "Task 1"
    assert tasks[1]["type"] == "bug"


@pytest.mark.asyncio
async def test_create_task(mock_api):
    manager = ProjectManager(project_key="TEST_PROJ", api_client=mock_api)

    # Mock API Response
    mock_api.create_work_item.return_value = BaseResponse[int](
        code=0, msg="success", data=999
    )

    # Action
    result = await manager.create_task(name="New Task", type_key="story")

    # Assertions
    mock_api.create_work_item.assert_called_with(
        project_key="TEST_PROJ", name="New Task", type_key="story", template_id=None
    )
    assert result == 999
