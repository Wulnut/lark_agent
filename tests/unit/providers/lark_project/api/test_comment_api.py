"""CommentAPI 测试模块

测试覆盖:
1. create - 创建评论
2. list - 获取评论列表
3. update - 更新评论
4. delete - 删除评论

单测范式:
- patch get_project_client 返回 AsyncMock
- 覆盖每个方法至少 success + err_code case
- 断言 path 与 payload/params
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.unit.providers.lark_project.api.conftest import create_mock_response


@pytest.fixture
def mock_client():
    """模拟 ProjectClient"""
    with patch("src.providers.lark_project.api.comment.get_project_client") as mock:
        client_instance = AsyncMock()
        mock.return_value = client_instance
        yield client_instance


@pytest.fixture
def api(mock_client):
    """创建 CommentAPI 实例"""
    from src.providers.lark_project.api.comment import CommentAPI

    return CommentAPI()


class TestCreate:
    """测试 create 方法"""

    @pytest.mark.asyncio
    async def test_create_success(self, api, mock_client):
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": {"comment_id": "c1"}}
        )

        result = await api.create(
            project_key="pk",
            work_item_type_key="tk",
            work_item_id=123,
            content="hello",
        )

        assert result == {"comment_id": "c1"}
        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.call_args
        assert (
            call_args[0][0]
            == "/open_api/pk/work_item/tk/123/comment/create"
        )
        assert call_args[1]["json"] == {"content": "hello"}

    @pytest.mark.asyncio
    async def test_create_err_code(self, api, mock_client):
        mock_client.post.return_value = create_mock_response(
            {"err_code": 10001, "err_msg": "权限不足"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.create(
                project_key="pk",
                work_item_type_key="tk",
                work_item_id=123,
                content="hello",
            )

        assert "创建评论失败" in str(exc_info.value)
        assert "权限不足" in str(exc_info.value)


class TestList:
    """测试 list 方法"""

    @pytest.mark.asyncio
    async def test_list_success(self, api, mock_client):
        mock_client.get.return_value = create_mock_response(
            {"err_code": 0, "data": {"items": [], "total": 0}}
        )

        result = await api.list(
            project_key="pk",
            work_item_type_key="tk",
            work_item_id=123,
            page_size=10,
            page_num=2,
        )

        assert result == {"items": [], "total": 0}
        mock_client.get.assert_awaited_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/open_api/pk/work_item/tk/123/comments"
        assert call_args[1]["params"] == {"page_size": 10, "page_num": 2}

    @pytest.mark.asyncio
    async def test_list_err_code(self, api, mock_client):
        mock_client.get.return_value = create_mock_response(
            {"err_code": 10002, "err_msg": "工作项不存在"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.list(
                project_key="pk",
                work_item_type_key="tk",
                work_item_id=123,
            )

        assert "获取评论列表失败" in str(exc_info.value)
        assert "工作项不存在" in str(exc_info.value)


class TestUpdate:
    """测试 update 方法"""

    @pytest.mark.asyncio
    async def test_update_success(self, api, mock_client):
        mock_client.put.return_value = create_mock_response({"err_code": 0, "data": {}})

        await api.update(
            project_key="pk",
            work_item_type_key="tk",
            work_item_id=123,
            comment_id="c1",
            content="new",
        )

        mock_client.put.assert_awaited_once()
        call_args = mock_client.put.call_args
        assert call_args[0][0] == "/open_api/pk/work_item/tk/123/comment/c1"
        assert call_args[1]["json"] == {"content": "new"}

    @pytest.mark.asyncio
    async def test_update_err_code(self, api, mock_client):
        mock_client.put.return_value = create_mock_response(
            {"err_code": 10003, "err_msg": "评论不存在"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.update(
                project_key="pk",
                work_item_type_key="tk",
                work_item_id=123,
                comment_id="c1",
                content="new",
            )

        assert "更新评论失败" in str(exc_info.value)
        assert "评论不存在" in str(exc_info.value)


class TestDelete:
    """测试 delete 方法"""

    @pytest.mark.asyncio
    async def test_delete_success(self, api, mock_client):
        mock_client.delete.return_value = create_mock_response(
            {"err_code": 0, "data": {}}
        )

        await api.delete(
            project_key="pk",
            work_item_type_key="tk",
            work_item_id=123,
            comment_id="c1",
        )

        mock_client.delete.assert_awaited_once()
        call_args = mock_client.delete.call_args
        assert call_args[0][0] == "/open_api/pk/work_item/tk/123/comment/c1"

    @pytest.mark.asyncio
    async def test_delete_err_code(self, api, mock_client):
        mock_client.delete.return_value = create_mock_response(
            {"err_code": 10004, "err_msg": "删除失败"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.delete(
                project_key="pk",
                work_item_type_key="tk",
                work_item_id=123,
                comment_id="c1",
            )

        assert "删除评论失败" in str(exc_info.value)
        assert "删除失败" in str(exc_info.value)


class TestValidation:
    """测试参数安全校验"""

    @pytest.mark.asyncio
    async def test_validate_project_key_invalid(self, api, mock_client):
        with pytest.raises(ValueError):
            await api.create(
                project_key="../pk",
                work_item_type_key="tk",
                work_item_id=123,
                content="hello",
            )

        mock_client.post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_validate_type_key_invalid(self, api, mock_client):
        with pytest.raises(ValueError):
            await api.list(
                project_key="pk",
                work_item_type_key="tk/../../",
                work_item_id=123,
            )

        mock_client.get.assert_not_awaited()
