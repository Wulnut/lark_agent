"""
WorkItemAPI 测试模块

测试覆盖:
1. create - 创建工作项
2. query - 查询工作项
3. update - 更新工作项
4. delete - 删除工作项
5. filter - 过滤工作项
6. search_params - 参数化搜索
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.providers.project.api.work_item import WorkItemAPI


@pytest.fixture
def mock_client():
    """模拟 ProjectClient"""
    with patch("src.providers.project.api.work_item.get_project_client") as mock:
        client_instance = AsyncMock()
        mock.return_value = client_instance
        yield client_instance


@pytest.fixture
def api(mock_client):
    """创建 WorkItemAPI 实例"""
    return WorkItemAPI()


def _create_response(data: dict) -> MagicMock:
    """创建模拟响应对象"""
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


class TestCreate:
    """测试 create 方法"""

    @pytest.mark.asyncio
    async def test_create_success(self, api, mock_client):
        """测试正常创建工作项"""
        mock_client.post.return_value = _create_response({"err_code": 0, "data": 12345})

        result = await api.create(
            "pk", "tk", "name", [{"field_key": "k", "field_value": "v"}]
        )

        assert result == 12345
        mock_client.post.assert_awaited_once()
        args = mock_client.post.call_args
        assert args[0][0] == "/open_api/pk/work_item/create"
        assert args[1]["json"]["name"] == "name"


class TestQuery:
    """测试 query 方法"""

    @pytest.mark.asyncio
    async def test_query_success(self, api, mock_client):
        """测试正常查询工作项"""
        mock_client.post.return_value = _create_response(
            {"err_code": 0, "data": [{"id": 1}]}
        )

        result = await api.query("pk", "tk", [1])

        assert len(result) == 1
        assert result[0]["id"] == 1


class TestUpdate:
    """测试 update 方法"""

    @pytest.mark.asyncio
    async def test_update_success(self, api, mock_client):
        """测试正常更新工作项"""
        mock_client.put.return_value = _create_response({"err_code": 0, "data": {}})

        await api.update("pk", "tk", 1, [])

        mock_client.put.assert_awaited_once()


class TestDelete:
    """测试 delete 方法"""

    @pytest.mark.asyncio
    async def test_delete_success(self, api, mock_client):
        """测试正常删除工作项"""
        mock_client.delete.return_value = _create_response({"err_code": 0, "data": {}})

        await api.delete("pk", "tk", 1)

        mock_client.delete.assert_awaited_once()


class TestFilter:
    """测试 filter 方法"""

    @pytest.mark.asyncio
    async def test_filter_success(self, api, mock_client):
        """测试正常过滤工作项"""
        mock_client.post.return_value = _create_response(
            {"err_code": 0, "data": {"items": []}}
        )

        await api.filter("pk", ["tk"])

        mock_client.post.assert_awaited_once()
        args = mock_client.post.call_args
        assert args[0][0] == "/open_api/pk/work_item/filter"


class TestSearchParams:
    """测试 search_params 方法"""

    @pytest.mark.asyncio
    async def test_search_params_success(self, api, mock_client):
        """测试正常参数化搜索"""
        mock_client.post.return_value = _create_response({"err_code": 0, "data": {}})

        await api.search_params("pk", "tk", {"conjunction": "AND"})

        mock_client.post.assert_awaited_once()
        args = mock_client.post.call_args
        assert args[0][0] == "/open_api/pk/work_item/tk/search/params"
