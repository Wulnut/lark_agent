"""
ProjectAPI 测试模块

测试覆盖:
1. list_projects - 正常响应、错误处理
2. get_project_details - 正常响应、错误处理、参数验证
"""

import pytest
from unittest.mock import AsyncMock, patch
from src.providers.lark_project.api.project import ProjectAPI
from tests.unit.providers.lark_project.api.conftest import create_mock_response


@pytest.fixture
def mock_client():
    """模拟 ProjectClient"""
    with patch("src.providers.lark_project.api.project.get_project_client") as mock:
        client_instance = AsyncMock()
        mock.return_value = client_instance
        yield client_instance


@pytest.fixture
def api(mock_client):
    """创建 ProjectAPI 实例"""
    return ProjectAPI()


class TestListProjects:
    """测试 list_projects 方法"""

    @pytest.mark.asyncio
    async def test_list_projects_success(self, api, mock_client):
        """测试正常获取空间列表"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": ["project_key_1", "project_key_2"]}
        )

        result = await api.list_projects()

        assert result == ["project_key_1", "project_key_2"]
        mock_client.post.assert_awaited_once()

        # 验证请求路径
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/open_api/projects"

    @pytest.mark.asyncio
    async def test_list_projects_with_params(self, api, mock_client):
        """测试带参数的空间列表请求"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": ["project_key_1"]}
        )

        result = await api.list_projects(
            user_key="test_user",
            tenant_group_id=123,
            asset_key="asset_1",
            order=["name"],
        )

        assert result == ["project_key_1"]

        # 验证请求参数
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["user_key"] == "test_user"
        assert payload["tenant_group_id"] == 123
        assert payload["asset_key"] == "asset_1"
        assert payload["order"] == ["name"]

    @pytest.mark.asyncio
    async def test_list_projects_empty(self, api, mock_client):
        """测试空列表返回"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": []}
        )

        result = await api.list_projects()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_projects_error(self, api, mock_client):
        """测试 API 错误处理"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 10001, "err_msg": "权限不足"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.list_projects()

        assert "获取空间列表失败" in str(exc_info.value)
        assert "权限不足" in str(exc_info.value)


class TestGetProjectDetails:
    """测试 get_project_details 方法"""

    @pytest.mark.asyncio
    async def test_get_project_details_success(self, api, mock_client):
        """测试正常获取空间详情"""
        mock_client.post.return_value = create_mock_response(
            {
                "err_code": 0,
                "data": {"project_key_1": {"name": "测试项目", "simple_name": "test"}},
            }
        )

        result = await api.get_project_details(["project_key_1"])

        assert "project_key_1" in result
        assert result["project_key_1"]["name"] == "测试项目"

        # 验证请求路径
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/open_api/projects/detail"

    @pytest.mark.asyncio
    async def test_get_project_details_multiple(self, api, mock_client):
        """测试批量获取多个空间详情"""
        mock_client.post.return_value = create_mock_response(
            {
                "err_code": 0,
                "data": {"key_1": {"name": "项目1"}, "key_2": {"name": "项目2"}},
            }
        )

        result = await api.get_project_details(["key_1", "key_2"])

        assert len(result) == 2
        assert result["key_1"]["name"] == "项目1"
        assert result["key_2"]["name"] == "项目2"

    @pytest.mark.asyncio
    async def test_get_project_details_with_simple_names(self, api, mock_client):
        """测试使用简称查询"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": {"key_1": {"name": "项目1"}}}
        )

        await api.get_project_details(
            project_keys=["key_1"], simple_names=["test_name"]
        )

        # 验证请求参数包含 simple_names
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["simple_names"] == ["test_name"]

    @pytest.mark.asyncio
    async def test_get_project_details_error(self, api, mock_client):
        """测试 API 错误处理"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 10002, "err_msg": "项目不存在"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.get_project_details(["invalid_key"])

        assert "获取空间详情失败" in str(exc_info.value)
        assert "项目不存在" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_project_details_empty_keys(self, api, mock_client):
        """测试空 Key 列表"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": {}}
        )

        result = await api.get_project_details([])

        assert result == {}
