"""RelationAPI 测试模块

测试覆盖:
1. rules - 获取关联规则
2. work_item_list - 获取关联工作项列表
3. batch_bind - 批量绑定关联
4. delete - 删除关联

单测范式:
- patch get_project_client 返回 AsyncMock
- 覆盖每个方法至少 success + err_code case
- 断言 path 与 payload
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.unit.providers.lark_project.api.conftest import create_mock_response


@pytest.fixture
def mock_client():
    """模拟 ProjectClient"""
    with patch("src.providers.lark_project.api.relation.get_project_client") as mock:
        client_instance = AsyncMock()
        mock.return_value = client_instance
        yield client_instance


@pytest.fixture
def api(mock_client):
    """创建 RelationAPI 实例"""
    from src.providers.lark_project.api.relation import RelationAPI

    return RelationAPI()


class TestRules:
    """测试 rules 方法"""

    @pytest.mark.asyncio
    async def test_rules_success(self, api, mock_client):
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": {"rules": []}}
        )

        result = await api.rules(project_key="pk")

        assert result == {"rules": []}
        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/open_api/pk/relation/rules"
        assert call_args[1]["json"] == {}

    @pytest.mark.asyncio
    async def test_rules_err_code(self, api, mock_client):
        mock_client.post.return_value = create_mock_response(
            {"err_code": 10001, "err_msg": "权限不足"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.rules(project_key="pk")

        assert "获取关联规则失败" in str(exc_info.value)
        assert "权限不足" in str(exc_info.value)


class TestWorkItemList:
    """测试 work_item_list 方法"""

    @pytest.mark.asyncio
    async def test_work_item_list_success(self, api, mock_client):
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": {"work_items": [], "total": 0}}
        )

        result = await api.work_item_list(
            project_key="pk",
            work_item_type_key="tk",
            work_item_id=123,
            page_num=2,
            page_size=10,
        )

        assert result == {"work_items": [], "total": 0}
        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/open_api/pk/relation/tk/123/work_item_list"
        assert call_args[1]["json"]["page_num"] == 2
        assert call_args[1]["json"]["page_size"] == 10

    @pytest.mark.asyncio
    async def test_work_item_list_err_code(self, api, mock_client):
        mock_client.post.return_value = create_mock_response(
            {"err_code": 10002, "err_msg": "工作项不存在"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.work_item_list(
                project_key="pk",
                work_item_type_key="tk",
                work_item_id=123,
            )

        assert "获取关联工作项列表失败" in str(exc_info.value)
        assert "工作项不存在" in str(exc_info.value)


class TestBatchBind:
    """测试 batch_bind 方法"""

    @pytest.mark.asyncio
    async def test_batch_bind_success(self, api, mock_client):
        mock_client.post.return_value = create_mock_response({"err_code": 0, "data": {}})

        await api.batch_bind(
            project_key="pk",
            work_item_type_key="tk",
            work_item_id=123,
            relation_key="rk",
            work_item_ids=[1, 2, 3],
        )

        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/open_api/pk/relation/tk/123/batch_bind"
        assert call_args[1]["json"] == {"relation_key": "rk", "work_item_ids": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_batch_bind_err_code(self, api, mock_client):
        mock_client.post.return_value = create_mock_response(
            {"err_code": 10003, "err_msg": "绑定失败"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.batch_bind(
                project_key="pk",
                work_item_type_key="tk",
                work_item_id=123,
                relation_key="rk",
                work_item_ids=[1],
            )

        assert "批量绑定关联失败" in str(exc_info.value)
        assert "绑定失败" in str(exc_info.value)


class TestDelete:
    """测试 delete 方法"""

    @pytest.mark.asyncio
    async def test_delete_success(self, api, mock_client):
        mock_client.delete.return_value = create_mock_response({"err_code": 0, "data": {}})

        await api.delete(project_key="pk", work_item_type_key="tk", work_item_id=123)

        mock_client.delete.assert_awaited_once()
        call_args = mock_client.delete.call_args
        assert call_args[0][0] == "/open_api/pk/relation/tk/123"

    @pytest.mark.asyncio
    async def test_delete_err_code(self, api, mock_client):
        mock_client.delete.return_value = create_mock_response(
            {"err_code": 10004, "err_msg": "删除失败"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.delete(project_key="pk", work_item_type_key="tk", work_item_id=123)

        assert "删除关联失败" in str(exc_info.value)
        assert "删除失败" in str(exc_info.value)
