from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.providers.lark_project.comment_provider import CommentProvider


@pytest.fixture
def provider_project_key():
    return CommentProvider(project_key="pk", work_item_type_name="问题管理")


@pytest.fixture
def mock_meta_for_project_key():
    with patch(
        "src.providers.lark_project.comment_provider.MetadataManager"
    ) as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.get_type_key.return_value = "tk"
        mock_cls.get_instance.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_api_for_project_key():
    with patch("src.providers.lark_project.comment_provider.CommentAPI") as mock_cls:
        mock_instance = AsyncMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.mark.asyncio
async def test_project_key_add_comment_success(mock_meta_for_project_key, mock_api_for_project_key):
    provider = CommentProvider(project_key="pk", work_item_type_name="问题管理")
    mock_api_for_project_key.create.return_value = {"comment_id": "c1"}

    result = await provider.add_comment(issue_id=123, content="hello")

    assert result["comment_id"] == "c1"
    mock_api_for_project_key.create.assert_awaited_once_with(
        project_key="pk",
        work_item_type_key="tk",
        work_item_id=123,
        content="hello",
    )


@pytest.mark.asyncio
async def test_project_key_list_comments_success(mock_meta_for_project_key, mock_api_for_project_key):
    provider = CommentProvider(project_key="pk", work_item_type_name="问题管理")
    mock_api_for_project_key.list.return_value = {"items": [], "total": 0}

    result = await provider.list_comments(issue_id=123)

    assert result["total"] == 0
    mock_api_for_project_key.list.assert_awaited_once_with(
        project_key="pk",
        work_item_type_key="tk",
        work_item_id=123,
        page_num=1,
        page_size=20,
    )


@pytest.mark.asyncio
async def test_project_key_update_comment_success(mock_meta_for_project_key, mock_api_for_project_key):
    provider = CommentProvider(project_key="pk", work_item_type_name="问题管理")
    mock_api_for_project_key.update.return_value = None

    await provider.update_comment(issue_id=123, comment_id="c1", content="new")

    mock_api_for_project_key.update.assert_awaited_once_with(
        project_key="pk",
        work_item_type_key="tk",
        work_item_id=123,
        comment_id="c1",
        content="new",
    )


@pytest.mark.asyncio
async def test_project_key_delete_comment_success(mock_meta_for_project_key, mock_api_for_project_key):
    provider = CommentProvider(project_key="pk", work_item_type_name="问题管理")
    mock_api_for_project_key.delete.return_value = None

    await provider.delete_comment(issue_id=123, comment_id="c1")

    mock_api_for_project_key.delete.assert_awaited_once_with(
        project_key="pk",
        work_item_type_key="tk",
        work_item_id=123,
        comment_id="c1",
    )
