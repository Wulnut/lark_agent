import pytest
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
async def test_resolve_related_to_exact_match_priority(mock_work_item_api, mock_metadata):
    """
    Test that resolve_related_to prioritizes exact matches over partial matches.
    Scenario:
    - User searches for "Bug"
    - "Issue Management" type has an item named "Bug Fix" (partial match)
    - "Task" type has an item named "Bug" (exact match)
    - The system should return the ID of "Bug", not "Bug Fix", even if "Bug Fix" is found first.
    """
    # Setup
    mock_metadata.get_project_key.return_value = "proj_123"

    # Mock get_tasks behavior for the temporary provider used inside resolve_related_to
    # We need to mock WorkItemProvider.get_tasks or the API call inside it.
    # Since resolve_related_to instantiates new WorkItemProvider instances,
    # mocking the API class (which is instantiated in __init__) is effective.

    async def mock_search_params(project_key, work_item_type_key, search_group, page_num, page_size, **kwargs):
        # Determine which type we are searching in based on the type key passed (mocked)
        # However, WorkItemProvider resolves type key internally.
        # Let's verify what happens.
        return {"work_items": [], "total": 0}

    # Better approach: Mock get_tasks on the instances created.
    # But we can't easily access those instances.
    # Instead, let's mock the API response based on the "work_item_type_name"
    # that would have been used to resolve the type_key.

    # But resolve_related_to calls `await temp_provider.get_tasks(name_keyword=related_to)`
    # which calls `self.api.filter(...)` if name_keyword is present.

    async def mock_filter(project_key, work_item_type_keys, page_num, page_size, work_item_name=None, **kwargs):
        # We can distinguish calls by the mocked type key, but that requires mocking metadata to return distinct keys
        pass

    # Let's simplify:
    # We will mock WorkItemProvider.get_tasks directly to return prepared results based on the 'work_item_type_name'
    # of the provider instance.

    # Since resolve_related_to creates new instances:
    # temp_provider = WorkItemProvider(..., work_item_type_name=search_type)

    # We can use `side_effect` on the class init? No, that's hard.
    # Let's stick to mocking the API and Metadata.

    mock_metadata.get_type_key.side_effect = lambda project, type_name: f"key_{type_name}"

    async def mock_filter_impl(project_key, work_item_type_keys, page_num, page_size, work_item_name=None, **kwargs):
        type_key = work_item_type_keys[0]

        if type_key == "key_Issue管理":
            # Returns partial match
            return {
                "work_items": [
                    {"id": 101, "name": "Bug Fix", "fields": []}
                ],
                "total": 1
            }
        elif type_key == "key_任务":
            # Returns exact match
            return {
                "work_items": [
                    {"id": 102, "name": "Bug", "fields": []}
                ],
                "total": 1
            }
        return {"work_items": [], "total": 0}

    mock_work_item_api.filter.side_effect = mock_filter_impl

    provider = WorkItemProvider("My Project")

    # Execute
    result_id = await provider.resolve_related_to("Bug")

    # Verify
    # Should be 102 ("Bug"), not 101 ("Bug Fix")
    assert result_id == 102

@pytest.mark.asyncio
async def test_resolve_related_to_partial_match_fallback(mock_work_item_api, mock_metadata):
    """
    Test that resolve_related_to falls back to partial match if no exact match is found.
    """
    mock_metadata.get_project_key.return_value = "proj_123"
    mock_metadata.get_type_key.side_effect = lambda project, type_name: f"key_{type_name}"

    async def mock_filter_impl(project_key, work_item_type_keys, page_num, page_size, work_item_name=None, **kwargs):
        type_key = work_item_type_keys[0]

        if type_key == "key_Issue管理":
            # Returns partial match
            return {
                "work_items": [
                    {"id": 101, "name": "Bug Fix", "fields": []}
                ],
                "total": 1
            }
        # No exact match anywhere
        return {"work_items": [], "total": 0}

    mock_work_item_api.filter.side_effect = mock_filter_impl

    provider = WorkItemProvider("My Project")

    # Execute
    result_id = await provider.resolve_related_to("Bug")

    # Verify
    # Should be 101 ("Bug Fix") as it's the only match
    assert result_id == 101
