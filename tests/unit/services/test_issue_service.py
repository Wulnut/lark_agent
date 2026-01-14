import pytest
from unittest.mock import AsyncMock, patch
from src.services.issue_service import IssueService


@pytest.fixture
def mock_provider():
    with patch("src.services.issue_service.WorkItemProvider") as mock:
        yield mock.return_value


@pytest.mark.asyncio
async def test_create_issue(mock_provider):
    mock_provider.create_issue = AsyncMock(return_value=123)

    service = IssueService(project_name="Test Project")
    res = await service.create_issue("Title", "P1")

    assert "123" in res
    mock_provider.create_issue.assert_awaited_with(
        name="Title", priority="P1", description="", assignee=None
    )


@pytest.mark.asyncio
async def test_get_issue(mock_provider):
    mock_provider.get_issue_details = AsyncMock(return_value={"id": 1})

    service = IssueService(project_name="Test Project")
    res = await service.get_issue(1)

    assert res["id"] == 1
    mock_provider.get_issue_details.assert_awaited_with(1)


@pytest.mark.asyncio
async def test_init_with_project_key(mock_provider):
    """Test initialization with project_key."""
    with patch("src.services.issue_service.WorkItemProvider") as MockProvider:
        IssueService(project_key="proj_123")
        MockProvider.assert_called_with(project_name=None, project_key="proj_123")


@pytest.mark.asyncio
async def test_concurrency_safe(mock_provider):
    """Test concurrent operations."""
    import asyncio

    mock_provider.create_issue = AsyncMock(side_effect=lambda name, **kw: int(name))

    service = IssueService(project_name="Test Project")

    async def create_task(i):
        return await service.create_issue(str(i), "P1")

    # Run 10 creations concurrently
    results = await asyncio.gather(*(create_task(i) for i in range(10)))

    assert len(results) == 10
    assert "9" in results[-1]  # Results are strings like "Created issue #9"
    assert mock_provider.create_issue.call_count == 10
