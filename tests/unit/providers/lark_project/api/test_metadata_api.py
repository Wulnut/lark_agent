"""
MetadataAPI 测试模块

测试覆盖:
1. get_work_item_types - 正常响应、错误处理
2. get_business_lines - 正常响应、错误处理
3. get_work_item_type_config - 正常响应、错误处理
4. get_workflow_templates - 正常响应、错误处理
"""

import pytest
from unittest.mock import AsyncMock, patch
from src.providers.lark_project.api.metadata import MetadataAPI
from tests.unit.providers.lark_project.api.conftest import create_mock_response


@pytest.fixture
def mock_client():
    """模拟 ProjectClient"""
    with patch("src.providers.lark_project.api.metadata.get_project_client") as mock:
        client_instance = AsyncMock()
        mock.return_value = client_instance
        yield client_instance


@pytest.fixture
def api(mock_client):
    """创建 MetadataAPI 实例"""
    return MetadataAPI()


class TestGetWorkItemTypes:
    """测试 get_work_item_types 方法"""

    @pytest.mark.asyncio
    async def test_get_work_item_types_success(self, api, mock_client):
        """测试正常获取工作项类型"""
        mock_client.get.return_value = create_mock_response(
            {
                "err_code": 0,
                "data": [
                    {"name": "需求", "type_key": "story"},
                    {"name": "缺陷", "type_key": "bug"},
                    {"name": "任务", "type_key": "task"},
                ],
            }
        )

        result = await api.get_work_item_types("test_project")

        assert len(result) == 3
        assert result[0]["name"] == "需求"
        assert result[0]["type_key"] == "story"

        # 验证请求路径
        mock_client.get.assert_awaited_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/open_api/test_project/work_item/all-types"

    @pytest.mark.asyncio
    async def test_get_work_item_types_empty(self, api, mock_client):
        """测试空类型列表返回"""
        mock_client.get.return_value = create_mock_response({"err_code": 0, "data": []})

        result = await api.get_work_item_types("empty_project")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_work_item_types_error(self, api, mock_client):
        """测试 API 错误处理"""
        mock_client.get.return_value = create_mock_response(
            {"err_code": 10001, "err_msg": "空间不存在"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.get_work_item_types("invalid_project")

        assert "获取工作项类型失败" in str(exc_info.value)
        assert "空间不存在" in str(exc_info.value)


class TestGetBusinessLines:
    """测试 get_business_lines 方法"""

    @pytest.mark.asyncio
    async def test_get_business_lines_success(self, api, mock_client):
        """测试正常获取业务线"""
        mock_client.get.return_value = create_mock_response(
            {
                "err_code": 0,
                "data": [
                    {"id": "biz_1", "name": "产品线A"},
                    {"id": "biz_2", "name": "产品线B"},
                ],
            }
        )

        result = await api.get_business_lines("test_project")

        assert len(result) == 2
        assert result[0]["name"] == "产品线A"

        # 验证请求路径
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/open_api/test_project/business/all"

    @pytest.mark.asyncio
    async def test_get_business_lines_empty(self, api, mock_client):
        """测试空业务线列表"""
        mock_client.get.return_value = create_mock_response({"err_code": 0, "data": []})

        result = await api.get_business_lines("no_biz_project")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_business_lines_error(self, api, mock_client):
        """测试 API 错误处理"""
        mock_client.get.return_value = create_mock_response(
            {"err_code": 10002, "err_msg": "权限不足"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.get_business_lines("no_access_project")

        assert "获取业务线详情失败" in str(exc_info.value)


class TestGetWorkItemTypeConfig:
    """测试 get_work_item_type_config 方法"""

    @pytest.mark.asyncio
    async def test_get_work_item_type_config_success(self, api, mock_client):
        """测试正常获取工作项类型配置"""
        mock_client.get.return_value = create_mock_response(
            {
                "err_code": 0,
                "data": {
                    "type_key": "story",
                    "name": "需求",
                    "description": "需求类型描述",
                    "is_disabled": False,
                },
            }
        )

        result = await api.get_work_item_type_config("test_project", "story")

        assert result["type_key"] == "story"
        assert result["name"] == "需求"

        # 验证请求路径
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/open_api/test_project/work_item/type/story"

    @pytest.mark.asyncio
    async def test_get_work_item_type_config_error(self, api, mock_client):
        """测试 API 错误处理"""
        mock_client.get.return_value = create_mock_response(
            {"err_code": 10003, "err_msg": "工作项类型不存在"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.get_work_item_type_config("project", "invalid_type")

        assert "获取工作项类型配置失败" in str(exc_info.value)


class TestGetWorkflowTemplates:
    """测试 get_workflow_templates 方法"""

    @pytest.mark.asyncio
    async def test_get_workflow_templates_success(self, api, mock_client):
        """测试正常获取流程模板"""
        mock_client.get.return_value = create_mock_response(
            {
                "err_code": 0,
                "data": [
                    {"template_id": 1, "template_name": "默认流程"},
                    {"template_id": 2, "template_name": "敏捷流程"},
                ],
            }
        )

        result = await api.get_workflow_templates("test_project", "story")

        assert len(result) == 2
        assert result[0]["template_name"] == "默认流程"

        # 验证请求路径
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/open_api/test_project/template_list/story"

    @pytest.mark.asyncio
    async def test_get_workflow_templates_empty(self, api, mock_client):
        """测试空模板列表"""
        mock_client.get.return_value = create_mock_response({"err_code": 0, "data": []})

        result = await api.get_workflow_templates("project", "type")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_workflow_templates_error(self, api, mock_client):
        """测试 API 错误处理"""
        mock_client.get.return_value = create_mock_response(
            {"err_code": 10004, "err_msg": "无法获取模板"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.get_workflow_templates("project", "type")

        assert "获取流程模板列表失败" in str(exc_info.value)
