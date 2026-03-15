from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.providers.lark_project.comment_provider import CommentProvider


@pytest.fixture
def mock_meta():
    with patch(
        "src.providers.lark_project.comment_provider.MetadataManager"
    ) as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.get_project_key.return_value = "pk"
        mock_instance.get_type_key.return_value = "tk"
        mock_cls.get_instance.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_api():
    with patch("src.providers.lark_project.comment_provider.CommentAPI") as mock_cls:
        mock_instance = AsyncMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def provider(mock_meta, mock_api):
    return CommentProvider(project_name="My Project", work_item_type_name="问题管理")


@pytest.mark.asyncio
async def test_add_comment_success(provider, mock_api):
    mock_api.create.return_value = {"comment_id": "c1"}

    result = await provider.add_comment(issue_id=123, content="hello")

    assert result == {"comment_id": "c1"}
    mock_api.create.assert_awaited_once_with(
        project_key="pk",
        work_item_type_key="tk",
        work_item_id=123,
        content="hello",
    )


@pytest.mark.asyncio
async def test_add_comment_empty_content(provider, mock_api):
    with pytest.raises(ValueError) as exc_info:
        await provider.add_comment(issue_id=123, content="   ")

    assert "评论内容不能为空" in str(exc_info.value)
    mock_api.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_comments_simplify(provider, mock_api):
    mock_api.list.return_value = {
        "items": [
            {
                "comment_id": "c1",
                "author": "u1",
                "create_time": 111,
                "content": "hello",
            }
        ],
        "total": 1,
    }

    result = await provider.list_comments(issue_id=123, page_num=1, page_size=20)

    assert result["total"] == 1
    assert result["items"][0]["comment_id"] == "c1"


@pytest.mark.asyncio
async def test_add_comment_error(provider, mock_api):
    mock_api.create.side_effect = Exception("权限不足")

    with pytest.raises(Exception) as exc_info:
        await provider.add_comment(issue_id=123, content="hello")

    assert "权限不足" in str(exc_info.value)


@pytest.mark.asyncio
async def test_add_comment_network_error_to_chinese(provider, mock_api):
    mock_api.create.side_effect = Exception("Network Error")

    with pytest.raises(Exception) as exc_info:
        await provider.add_comment(issue_id=123, content="hello")

    assert "网络" in str(exc_info.value)
    assert "Network" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_list_comments_error(provider, mock_api):
    mock_api.list.side_effect = Exception("工作项不存在")

    with pytest.raises(Exception) as exc_info:
        await provider.list_comments(issue_id=123)

    assert "工作项不存在" in str(exc_info.value)


@pytest.mark.asyncio
async def test_list_comments_network_error_to_chinese(provider, mock_api):
    mock_api.list.side_effect = Exception("Network Error")

    with pytest.raises(Exception) as exc_info:
        await provider.list_comments(issue_id=123)

    assert "网络" in str(exc_info.value)
    assert "Network" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_list_comments_unknown_english_error_to_chinese(provider, mock_api):
    mock_api.list.side_effect = Exception("Some Unknown Error")

    with pytest.raises(Exception) as exc_info:
        await provider.list_comments(issue_id=123)

    assert "系统" in str(exc_info.value)
    assert "Unknown" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_comment_success(provider, mock_api):
    mock_api.update.return_value = None

    await provider.update_comment(issue_id=123, comment_id="c1", content="new")

    mock_api.update.assert_awaited_once_with(
        project_key="pk",
        work_item_type_key="tk",
        work_item_id=123,
        comment_id="c1",
        content="new",
    )


@pytest.mark.asyncio
async def test_update_comment_error(provider, mock_api):
    mock_api.update.side_effect = Exception("权限不足")

    with pytest.raises(Exception) as exc_info:
        await provider.update_comment(issue_id=123, comment_id="c1", content="new")

    assert "权限不足" in str(exc_info.value)


@pytest.mark.asyncio
async def test_delete_comment_success(provider, mock_api):
    mock_api.delete.return_value = None

    await provider.delete_comment(issue_id=123, comment_id="c1")

    mock_api.delete.assert_awaited_once_with(
        project_key="pk",
        work_item_type_key="tk",
        work_item_id=123,
        comment_id="c1",
    )


@pytest.mark.asyncio
async def test_delete_comment_error(provider, mock_api):
    mock_api.delete.side_effect = Exception("删除失败")

    with pytest.raises(Exception) as exc_info:
        await provider.delete_comment(issue_id=123, comment_id="c1")

    assert "删除失败" in str(exc_info.value)
