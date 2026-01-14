"""
FieldAPI 测试模块

测试覆盖:
1. get_all_fields - 正常响应、错误处理
2. create_field - 正常响应、错误处理
3. update_field - 正常响应、错误处理
4. get_work_item_relations - 正常响应、错误处理
"""

import pytest
from unittest.mock import AsyncMock, patch
from src.providers.project.api.field import FieldAPI
from tests.unit.providers.project.api.conftest import create_mock_response


@pytest.fixture
def mock_client():
    """模拟 ProjectClient"""
    with patch("src.providers.project.api.field.get_project_client") as mock:
        client_instance = AsyncMock()
        mock.return_value = client_instance
        yield client_instance


@pytest.fixture
def api(mock_client):
    """创建 FieldAPI 实例"""
    return FieldAPI()


class TestGetAllFields:
    """测试 get_all_fields 方法"""

    @pytest.mark.asyncio
    async def test_get_all_fields_success(self, api, mock_client):
        """测试正常获取字段列表"""
        mock_client.post.return_value = create_mock_response(
            {
                "err_code": 0,
                "data": [
                    {
                        "field_name": "优先级",
                        "field_key": "priority",
                        "field_alias": "priority",
                        "options": [
                            {"label": "高", "value": "P0"},
                            {"label": "中", "value": "P1"},
                            {"label": "低", "value": "P2"},
                        ],
                    },
                    {
                        "field_name": "负责人",
                        "field_key": "owner",
                        "field_alias": "owner",
                    },
                ],
            }
        )

        result = await api.get_all_fields("test_project", "story")

        assert len(result) == 2
        assert result[0]["field_name"] == "优先级"
        assert len(result[0]["options"]) == 3

        # 验证请求
        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/open_api/test_project/field/all"
        assert call_args[1]["json"]["work_item_type_key"] == "story"

    @pytest.mark.asyncio
    async def test_get_all_fields_empty(self, api, mock_client):
        """测试空字段列表"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": []}
        )

        result = await api.get_all_fields("project", "type")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_fields_with_nested_options(self, api, mock_client):
        """测试带嵌套选项的字段"""
        mock_client.post.return_value = create_mock_response(
            {
                "err_code": 0,
                "data": [
                    {
                        "field_name": "状态",
                        "field_key": "status",
                        "options": [
                            {
                                "label": "待处理",
                                "value": "todo",
                                "children": [{"label": "子状态1", "value": "sub1"}],
                            }
                        ],
                    }
                ],
            }
        )

        result = await api.get_all_fields("project", "type")

        assert result[0]["options"][0]["children"][0]["label"] == "子状态1"

    @pytest.mark.asyncio
    async def test_get_all_fields_error(self, api, mock_client):
        """测试 API 错误处理"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 10001, "err_msg": "类型不存在"}
        )

        with pytest.raises(Exception, match=r"获取字段信息失败.*类型不存在"):
            await api.get_all_fields("project", "invalid_type")


class TestCreateField:
    """测试 create_field 方法"""

    @pytest.mark.asyncio
    async def test_create_field_success(self, api, mock_client):
        """测试正常创建字段"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": {"field_key": "new_field_123"}}
        )

        result = await api.create_field(
            "test_project", "story", field_name="自定义字段", field_type_key="text"
        )

        assert result["field_key"] == "new_field_123"

        # 验证请求
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/open_api/test_project/field/story/create"
        payload = call_args[1]["json"]
        assert payload["field_name"] == "自定义字段"
        assert payload["field_type_key"] == "text"

    @pytest.mark.asyncio
    async def test_create_field_with_options(self, api, mock_client):
        """测试创建带选项的字段"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": {"field_key": "select_field"}}
        )

        await api.create_field(
            "project",
            "type",
            field_name="选择字段",
            field_type_key="select",
            field_alias="custom_select",
            help_description="这是一个选择字段",
        )

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["field_alias"] == "custom_select"
        assert payload["help_description"] == "这是一个选择字段"

    @pytest.mark.asyncio
    async def test_create_field_error(self, api, mock_client):
        """测试创建字段失败"""
        mock_client.post.return_value = create_mock_response(
            {"err_code": 10002, "err_msg": "字段名称已存在"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.create_field("project", "type", "重复字段", "text")

        assert "创建自定义字段失败" in str(exc_info.value)


class TestUpdateField:
    """测试 update_field 方法"""

    @pytest.mark.asyncio
    async def test_update_field_success(self, api, mock_client):
        """测试正常更新字段"""
        mock_client.put.return_value = create_mock_response({"err_code": 0, "data": {}})

        result = await api.update_field(
            "test_project", "story", field_key="field_123", field_name="新名称"
        )

        assert result == {}

        # 验证请求
        mock_client.put.assert_awaited_once()
        call_args = mock_client.put.call_args
        assert call_args[0][0] == "/open_api/test_project/field/story"
        payload = call_args[1]["json"]
        assert payload["field_key"] == "field_123"
        assert payload["field_name"] == "新名称"

    @pytest.mark.asyncio
    async def test_update_field_error(self, api, mock_client):
        """测试更新字段失败"""
        mock_client.put.return_value = create_mock_response(
            {"err_code": 10003, "err_msg": "字段不存在"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.update_field("project", "type", "invalid_field")

        assert "更新自定义字段失败" in str(exc_info.value)


class TestGetWorkItemRelations:
    """测试 get_work_item_relations 方法"""

    @pytest.mark.asyncio
    async def test_get_work_item_relations_success(self, api, mock_client):
        """测试正常获取工作项关系"""
        mock_client.get.return_value = create_mock_response(
            {
                "err_code": 0,
                "data": [
                    {"relation_id": "rel_1", "name": "父子关系", "relation_type": 1}
                ],
            }
        )

        result = await api.get_work_item_relations("test_project")

        assert len(result) == 1
        assert result[0]["name"] == "父子关系"

        # 验证请求路径
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/open_api/test_project/work_item/relation"

    @pytest.mark.asyncio
    async def test_get_work_item_relations_empty(self, api, mock_client):
        """测试空关系列表"""
        mock_client.get.return_value = create_mock_response({"err_code": 0, "data": []})

        result = await api.get_work_item_relations("project")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_work_item_relations_error(self, api, mock_client):
        """测试 API 错误处理"""
        mock_client.get.return_value = create_mock_response(
            {"err_code": 10004, "err_msg": "无权限"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.get_work_item_relations("no_access_project")

        assert "获取工作项关系列表失败" in str(exc_info.value)
