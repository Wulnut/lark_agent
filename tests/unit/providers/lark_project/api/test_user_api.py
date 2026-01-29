"""
UserAPI 测试模块

测试覆盖:
1. get_team_members - 正常响应、错误处理
2. query_users - 正常响应、多种参数组合、错误处理
3. search_users - 正常响应、带 project_key、错误处理
4. get_user_group_members - 正常响应、分页、错误处理
5. create_user_group - 正常响应、错误处理
"""

import pytest
from unittest.mock import AsyncMock, patch
from src.providers.lark_project.api.user import UserAPI
from tests.unit.providers.lark_project.api.conftest import create_mock_response


@pytest.fixture
def mock_client():
    """模拟 ProjectClient"""
    with patch("src.providers.lark_project.api.user.get_project_client") as mock:
        client_instance = AsyncMock()
        mock.return_value = client_instance
        yield client_instance


@pytest.fixture
def api(mock_client):
    """创建 UserAPI 实例"""
    return UserAPI()


class TestGetTeamMembers:
    """测试 get_team_members 方法"""

    @pytest.mark.asyncio
    async def test_get_team_members_success(self, api, mock_client):
        """测试正常获取团队成员"""
        mock_client.get.return_value = create_mock_response(
            {
                "err_code": 0,
                "data": [
                    {"user_key": "user_1", "name": "张三"},
                    {"user_key": "user_2", "name": "李四"},
                ],
            }
        )

        result = await api.get_team_members("test_project")

        assert len(result) == 2
        assert result[0]["name"] == "张三"

        # 验证请求路径
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/open_api/test_project/teams/all"

    @pytest.mark.asyncio
    async def test_get_team_members_empty(self, api, mock_client):
        """测试空团队"""
        mock_client.get.return_value = create_mock_response({"err_code": 0, "data": []})

        result = await api.get_team_members("empty_project")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_team_members_error(self, api, mock_client):
        """测试 API 错误处理"""
        mock_client.get.return_value = create_mock_response(
            {"err_code": 10001, "err_msg": "项目不存在"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.get_team_members("invalid_project")

        assert "获取团队成员失败" in str(exc_info.value)


class TestQueryUsers:
    """测试 query_users 方法"""

    @pytest.mark.asyncio
    async def test_query_users_by_keys(self, api, mock_client):
        """测试通过 user_keys 查询"""
        mock_client.post.return_value = create_mock_response(
            {
                "err_code": 0,
                "data": [
                    {"user_key": "user_1", "name": "张三", "email": "zhangsan@test.com"}
                ],
            }
        )

        result = await api.query_users(user_keys=["user_1"])

        assert len(result) == 1
        assert result[0]["email"] == "zhangsan@test.com"

        # 验证请求
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/open_api/user/query"
        assert call_args[1]["json"]["user_keys"] == ["user_1"]

    @pytest.mark.asyncio
    async def test_query_users_by_emails(self, api, mock_client):
        """测试通过邮箱查询"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": [{"user_key": "user_1", "email": "test@test.com"}]}
        )

        await api.query_users(emails=["test@test.com"])

        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["emails"] == ["test@test.com"]

    @pytest.mark.asyncio
    async def test_query_users_multiple_params(self, api, mock_client):
        """测试多参数组合查询"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": []}
        )

        await api.query_users(
            user_keys=["key1"],
            emails=["email@test.com"],
            out_ids=["out_1"],
            tenant_key="tenant_1",
        )

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert "user_keys" in payload
        assert "emails" in payload
        assert "out_ids" in payload
        assert "tenant_key" in payload

    @pytest.mark.asyncio
    async def test_query_users_error(self, api, mock_client):
        """测试 API 错误处理"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 10002, "err_msg": "用户不存在"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.query_users(user_keys=["invalid"])

        assert "获取用户详情失败" in str(exc_info.value)


class TestSearchUsers:
    """测试 search_users 方法"""

    @pytest.mark.asyncio
    async def test_search_users_success(self, api, mock_client):
        """测试正常搜索用户"""
        mock_client.post.return_value = create_mock_response(
            {
                "err_code": 0,
                "data": [
                    {"user_key": "user_1", "name": "张三"},
                    {"user_key": "user_2", "name": "张四"},
                ],
            }
        )

        result = await api.search_users("张")

        assert len(result) == 2

        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/open_api/user/search"
        assert call_args[1]["json"]["query"] == "张"

    @pytest.mark.asyncio
    async def test_search_users_with_project_key(self, api, mock_client):
        """测试带项目限定的搜索"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": []}
        )

        await api.search_users("test", project_key="test_project")

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["query"] == "test"
        assert payload["project_key"] == "test_project"

    @pytest.mark.asyncio
    async def test_search_users_empty_result(self, api, mock_client):
        """测试空搜索结果"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": []}
        )

        result = await api.search_users("不存在的用户")

        assert result == []

    @pytest.mark.asyncio
    async def test_search_users_error(self, api, mock_client):
        """测试 API 错误处理"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 10003, "err_msg": "搜索失败"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.search_users("test")

        assert "搜索用户失败" in str(exc_info.value)


class TestGetUserGroupMembers:
    """测试 get_user_group_members 方法"""

    @pytest.mark.asyncio
    async def test_get_user_group_members_success(self, api, mock_client):
        """测试正常获取用户组成员"""
        mock_client.post.return_value = create_mock_response(
            {
                "err_code": 0,
                "data": {
                    "items": [{"user_key": "user_1"}],
                    "total": 1,
                    "page_num": 1,
                    "page_size": 10,
                },
            }
        )

        result = await api.get_user_group_members("test_project", "custom", ["group_1"])

        assert result["total"] == 1

        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/open_api/test_project/user_groups/members/page"

    @pytest.mark.asyncio
    async def test_get_user_group_members_pagination(self, api, mock_client):
        """测试分页参数"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": {"items": [], "total": 100}}
        )

        await api.get_user_group_members(
            "project", "type", ["group"], page_num=2, page_size=20
        )

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["page_num"] == 2
        assert payload["page_size"] == 20

    @pytest.mark.asyncio
    async def test_get_user_group_members_error(self, api, mock_client):
        """测试 API 错误处理"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 10004, "err_msg": "用户组不存在"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.get_user_group_members("project", "type", ["invalid"])

        assert "查询用户组成员失败" in str(exc_info.value)


class TestCreateUserGroup:
    """测试 create_user_group 方法"""

    @pytest.mark.asyncio
    async def test_create_user_group_success(self, api, mock_client):
        """测试正常创建用户组"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": {"group_id": "new_group_123"}}
        )

        result = await api.create_user_group(
            "test_project", "测试用户组", ["user_1", "user_2"]
        )

        assert result["group_id"] == "new_group_123"

        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/open_api/test_project/user_group"
        payload = call_args[1]["json"]
        assert payload["name"] == "测试用户组"
        assert payload["users"] == ["user_1", "user_2"]

    @pytest.mark.asyncio
    async def test_create_user_group_error(self, api, mock_client):
        """测试创建失败"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 10005, "err_msg": "用户组名称已存在"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.create_user_group("project", "重复名称", [])

        assert "创建用户组失败" in str(exc_info.value)
