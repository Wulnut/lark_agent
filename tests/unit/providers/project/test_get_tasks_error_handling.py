import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from src.providers.project.work_item_provider import WorkItemProvider

@pytest.fixture
def mock_work_item_api():
    with patch("src.providers.project.work_item_provider.WorkItemAPI") as mock_cls:
        yield mock_cls.return_value

@pytest.fixture
def mock_metadata():
    with patch("src.providers.project.work_item_provider.MetadataManager") as mock_cls:
        mock_instance = AsyncMock()
        mock_cls.get_instance.return_value = mock_instance
        yield mock_instance

@pytest.mark.asyncio
async def test_get_tasks_stops_on_error(mock_work_item_api, mock_metadata):
    """
    Test that get_tasks stops fetching pages when an error occurs to ensure data consistency.
    """
    mock_metadata.get_project_key.return_value = "proj_123"
    mock_metadata.get_type_key.return_value = "type_issue"

    # Mock filter to simulate error on one of the pages
    async def mock_filter(project_key, work_item_type_keys, page_num, page_size, **kwargs):
        if page_num == 2:
            raise Exception("Simulated network error")

        # Page 1 returns items
        if page_num == 1:
            return {
                "work_items": [
                    {"id": 1, "name": "Task 1", "fields": [{"field_value": 999}]}
                ],
                "total": 100
            }

        # Pages > 2 should not ideally be reached or processed if we stop early
        return {
            "work_items": [
                {"id": page_num, "name": f"Task {page_num}", "fields": [{"field_value": 999}]}
            ],
            "total": 100
        }

    mock_work_item_api.filter.side_effect = mock_filter

    provider = WorkItemProvider("My Project")

    # Execute
    # We search for related_to=999 to trigger the pagination logic
    result = await provider.get_tasks(related_to=999)

    # Verify
    # Should contain items from page 1
    # Should NOT fail completely (it returns partial results with warning in log)
    # But specifically, we want to ensure it didn't continue indefinitely or crash

    # In the implementation:
    # It catches exception, sets has_error=True, and then breaks the loop.
    # However, since we use asyncio.gather, all tasks in the current batch (pages 1-5) run concurrently.
    # Page 2 fails, but 1, 3, 4, 5 succeed.
    # So we expect 4 items (from pages 1, 3, 4, 5).
    # The crucial part is that it should NOT fetch the NEXT batch (page 6+).

    items = result["items"]
    # 4 items from pages 1, 3, 4, 5
    assert len(items) == 4

    # Verify that it tried to fetch page 2 (which failed)
    # And verify it did NOT fetch page 6 (which would be in the next batch)

    call_args_list = mock_work_item_api.filter.call_args_list
    pages_fetched = [call.kwargs['page_num'] for call in call_args_list]

    assert 2 in pages_fetched
    assert 6 not in pages_fetched
