"""
MetadataManager 测试模块

测试覆盖:
1. get_project_key - 项目名称解析、缓存命中
2. get_type_key - 类型名称解析、缓存命中
3. get_field_key - 字段名称解析、别名支持
4. get_option_value - 选项值解析
5. get_user_key - 用户搜索
6. resolve_field_value - 级联解析
7. 缓存管理 - clear_cache, reset_instance
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.providers.lark_project.managers.metadata_manager import MetadataManager


@pytest.fixture(autouse=True)
def reset_singleton():
    """每个测试前重置单例"""
    MetadataManager.reset_instance()
    yield
    MetadataManager.reset_instance()


@pytest.fixture
def mock_project_api():
    """模拟 ProjectAPI"""
    api = AsyncMock()
    return api


@pytest.fixture
def mock_metadata_api():
    """模拟 MetadataAPI"""
    api = AsyncMock()
    return api


@pytest.fixture
def mock_field_api():
    """模拟 FieldAPI"""
    api = AsyncMock()
    return api


@pytest.fixture
def mock_user_api():
    """模拟 UserAPI"""
    api = AsyncMock()
    return api


@pytest.fixture
def manager(mock_project_api, mock_metadata_api, mock_field_api, mock_user_api):
    """创建 MetadataManager 实例"""
    return MetadataManager(
        project_api=mock_project_api,
        metadata_api=mock_metadata_api,
        field_api=mock_field_api,
        user_api=mock_user_api,
    )


class TestGetProjectKey:
    """测试 get_project_key 方法"""

    @pytest.mark.asyncio
    async def test_get_project_key_success(self, manager, mock_project_api):
        """测试正常获取项目 Key"""
        mock_project_api.list_projects.return_value = ["project_key_1", "project_key_2"]
        mock_project_api.get_project_details.return_value = {
            "project_key_1": {"name": "Project A"},
            "project_key_2": {"name": "Project B"},
        }

        result = await manager.get_project_key("Project A")

        assert result == "project_key_1"

    @pytest.mark.asyncio
    async def test_get_project_key_cache_hit(self, manager, mock_project_api):
        """测试缓存命中"""
        mock_project_api.list_projects.return_value = ["project_key_1"]
        mock_project_api.get_project_details.return_value = {
            "project_key_1": {"name": "Project A"}
        }

        # 第一次调用
        await manager.get_project_key("Project A")
        # 第二次调用应该命中缓存
        result = await manager.get_project_key("Project A")

        assert result == "project_key_1"
        # API 应该只被调用一次
        assert mock_project_api.list_projects.call_count == 1

    @pytest.mark.asyncio
    async def test_get_project_key_not_found(self, manager, mock_project_api):
        """测试项目未找到"""
        mock_project_api.list_projects.return_value = ["project_key_1"]
        mock_project_api.get_project_details.return_value = {
            "project_key_1": {"name": "Other Project"}
        }

        with pytest.raises(Exception) as exc_info:
            await manager.get_project_key("Non-existent Project")

        assert "未找到" in str(exc_info.value)


class TestGetTypeKey:
    """测试 get_type_key 方法"""

    @pytest.mark.asyncio
    async def test_get_type_key_success(self, manager, mock_metadata_api):
        """测试正常获取类型 Key"""
        mock_metadata_api.get_work_item_types.return_value = [
            {"name": "Issue", "type_key": "type_issue"},
            {"name": "需求", "type_key": "type_story"},
        ]

        result = await manager.get_type_key("project_1", "Issue")

        assert result == "type_issue"

    @pytest.mark.asyncio
    async def test_get_type_key_cache_hit(self, manager, mock_metadata_api):
        """测试缓存命中"""
        mock_metadata_api.get_work_item_types.return_value = [
            {"name": "Issue", "type_key": "type_issue"}
        ]

        # 第一次调用
        await manager.get_type_key("project_1", "Issue")
        # 第二次调用应该命中缓存
        result = await manager.get_type_key("project_1", "Issue")

        assert result == "type_issue"
        assert mock_metadata_api.get_work_item_types.call_count == 1

    @pytest.mark.asyncio
    async def test_get_type_key_not_found(self, manager, mock_metadata_api):
        """测试类型未找到"""
        mock_metadata_api.get_work_item_types.return_value = [
            {"name": "Issue", "type_key": "type_issue"}
        ]

        with pytest.raises(Exception) as exc_info:
            await manager.get_type_key("project_1", "非存在类型")

        assert "未找到" in str(exc_info.value)
        assert "Issue" in str(exc_info.value)  # 应该显示可用类型


class TestGetFieldKey:
    """测试 get_field_key 方法"""

    @pytest.mark.asyncio
    async def test_get_field_key_by_name(self, manager, mock_field_api):
        """测试通过字段名称获取 Key"""
        mock_field_api.get_all_fields.return_value = [
            {
                "field_name": "优先级",
                "field_key": "priority",
                "field_alias": "priority",
            },
            {"field_name": "描述", "field_key": "description"},
        ]

        result = await manager.get_field_key("project_1", "type_1", "优先级")

        assert result == "priority"

    @pytest.mark.asyncio
    async def test_get_field_key_by_alias(self, manager, mock_field_api):
        """测试通过字段别名获取 Key"""
        mock_field_api.get_all_fields.return_value = [
            {"field_name": "优先级", "field_key": "priority", "field_alias": "prio"},
        ]

        result = await manager.get_field_key("project_1", "type_1", "prio")

        assert result == "priority"

    @pytest.mark.asyncio
    async def test_get_field_key_is_key(self, manager, mock_field_api):
        """测试输入本身就是 Key"""
        mock_field_api.get_all_fields.return_value = [
            {"field_name": "优先级", "field_key": "priority"},
        ]

        result = await manager.get_field_key("project_1", "type_1", "priority")

        assert result == "priority"

    @pytest.mark.asyncio
    async def test_get_field_key_not_found(self, manager, mock_field_api):
        """测试字段未找到"""
        mock_field_api.get_all_fields.return_value = [
            {"field_name": "优先级", "field_key": "priority"},
        ]

        with pytest.raises(Exception) as exc_info:
            await manager.get_field_key("project_1", "type_1", "不存在字段")

        assert "未找到" in str(exc_info.value)


class TestGetOptionValue:
    """测试 get_option_value 方法"""

    @pytest.mark.asyncio
    async def test_get_option_value_success(self, manager, mock_field_api):
        """测试正常获取选项值"""
        mock_field_api.get_all_fields.return_value = [
            {
                "field_name": "优先级",
                "field_key": "priority",
                "options": [
                    {"label": "P0", "value": "option_1"},
                    {"label": "P1", "value": "option_2"},
                ],
            },
        ]

        result = await manager.get_option_value("project_1", "type_1", "priority", "P0")

        assert result == "option_1"

    @pytest.mark.asyncio
    async def test_get_option_value_is_value(self, manager, mock_field_api):
        """测试输入本身就是 Value"""
        mock_field_api.get_all_fields.return_value = [
            {
                "field_name": "优先级",
                "field_key": "priority",
                "options": [{"label": "P0", "value": "option_1"}],
            },
        ]

        result = await manager.get_option_value(
            "project_1", "type_1", "priority", "option_1"
        )

        assert result == "option_1"

    @pytest.mark.asyncio
    async def test_get_option_value_not_found(self, manager, mock_field_api):
        """测试选项未找到"""
        mock_field_api.get_all_fields.return_value = [
            {
                "field_name": "优先级",
                "field_key": "priority",
                "options": [{"label": "P0", "value": "option_1"}],
            },
        ]

        with pytest.raises(Exception) as exc_info:
            await manager.get_option_value("project_1", "type_1", "priority", "P99")

        assert "未找到" in str(exc_info.value)


    @pytest.mark.asyncio
    async def test_get_option_value_nested(self, manager, mock_field_api):
        """测试嵌套选项值解析 (Tree Select)"""
        mock_field_api.get_all_fields.return_value = [
            {
                "field_name": "模块",
                "field_key": "module",
                "options": [
                    {
                        "label": "Parent",
                        "value": "p_1",
                        "children": [
                            {
                                "label": "Child",
                                "value": "c_1",
                                "children": [{"label": "Grandchild", "value": "g_1"}],
                            }
                        ],
                    }
                ],
            }
        ]

        # 1. 查找父选项
        val_p = await manager.get_option_value("p_key", "t_key", "module", "Parent")
        assert val_p == "p_1"

        # 2. 查找子选项
        val_c = await manager.get_option_value("p_key", "t_key", "module", "Child")
        assert val_c == "c_1"

        # 3. 查找孙选项
        val_g = await manager.get_option_value("p_key", "t_key", "module", "Grandchild")
        assert val_g == "g_1"


class TestGetUserKey:
    """测试 get_user_key 方法"""

    @pytest.mark.asyncio
    async def test_get_user_key_success(self, manager, mock_user_api):
        """测试正常获取用户 Key"""
        mock_user_api.search_users.return_value = [
            {"user_key": "user_key_1", "name_cn": "张三", "email": "zhang@test.com"}
        ]

        result = await manager.get_user_key("张三")

        assert result == "user_key_1"

    @pytest.mark.asyncio
    async def test_get_user_key_cache_hit(self, manager, mock_user_api):
        """测试缓存命中"""
        mock_user_api.search_users.return_value = [
            {"user_key": "user_key_1", "name_cn": "张三"}
        ]

        # 第一次调用
        await manager.get_user_key("张三")
        # 第二次调用应该命中缓存
        result = await manager.get_user_key("张三")

        assert result == "user_key_1"
        assert mock_user_api.search_users.call_count == 1

    @pytest.mark.asyncio
    async def test_get_user_key_not_found(self, manager, mock_user_api):
        """测试用户未找到"""
        mock_user_api.search_users.return_value = []

        with pytest.raises(Exception) as exc_info:
            await manager.get_user_key("不存在用户")

        assert "未找到" in str(exc_info.value)


class TestResolveFieldValue:
    """测试 resolve_field_value 方法"""

    @pytest.mark.asyncio
    async def test_resolve_field_value_full(
        self, manager, mock_project_api, mock_metadata_api, mock_field_api
    ):
        """测试完整的级联解析"""
        # 设置 mock
        mock_project_api.list_projects.return_value = ["project_key_1"]
        mock_project_api.get_project_details.return_value = {
            "project_key_1": {"name": "Project A"}
        }
        mock_metadata_api.get_work_item_types.return_value = [
            {"name": "Issue", "type_key": "type_issue"}
        ]
        mock_field_api.get_all_fields.return_value = [
            {
                "field_name": "优先级",
                "field_key": "priority",
                "options": [{"label": "P0", "value": "option_1"}],
            }
        ]

        result = await manager.resolve_field_value(
            project_name="Project A",
            type_name="Issue",
            field_name="优先级",
            value_label="P0",
        )

        assert result["project_key"] == "project_key_1"
        assert result["type_key"] == "type_issue"
        assert result["field_key"] == "priority"
        assert result["option_value"] == "option_1"

    @pytest.mark.asyncio
    async def test_resolve_field_value_without_option(
        self, manager, mock_project_api, mock_metadata_api, mock_field_api
    ):
        """测试不带选项的级联解析"""
        mock_project_api.list_projects.return_value = ["project_key_1"]
        mock_project_api.get_project_details.return_value = {
            "project_key_1": {"name": "Project A"}
        }
        mock_metadata_api.get_work_item_types.return_value = [
            {"name": "Issue", "type_key": "type_issue"}
        ]
        mock_field_api.get_all_fields.return_value = [
            {"field_name": "描述", "field_key": "description"}
        ]

        result = await manager.resolve_field_value(
            project_name="Project A",
            type_name="Issue",
            field_name="描述",
        )

        assert result["project_key"] == "project_key_1"
        assert result["type_key"] == "type_issue"
        assert result["field_key"] == "description"
        assert "option_value" not in result


class TestCacheManagement:
    """测试缓存管理"""

    @pytest.mark.asyncio
    async def test_clear_cache(self, manager, mock_project_api):
        """测试清空缓存"""
        mock_project_api.list_projects.return_value = ["project_key_1"]
        mock_project_api.get_project_details.return_value = {
            "project_key_1": {"name": "Project A"}
        }

        # 第一次调用
        await manager.get_project_key("Project A")
        assert mock_project_api.list_projects.call_count == 1

        # 清空缓存
        manager.clear_cache()

        # 第二次调用应该再次调用 API
        await manager.get_project_key("Project A")
        assert mock_project_api.list_projects.call_count == 2

    def test_singleton_pattern(self):
        """测试单例模式"""
        instance1 = MetadataManager.get_instance()
        instance2 = MetadataManager.get_instance()

        assert instance1 is instance2

    def test_reset_instance(self):
        """测试重置单例"""
        instance1 = MetadataManager.get_instance()
        MetadataManager.reset_instance()
        instance2 = MetadataManager.get_instance()

        assert instance1 is not instance2


class TestListMethods:
    """测试 list 方法"""

    @pytest.mark.asyncio
    async def test_list_projects(self, manager, mock_project_api):
        """测试列出所有项目"""
        mock_project_api.list_projects.return_value = ["key_1", "key_2"]
        mock_project_api.get_project_details.return_value = {
            "key_1": {"name": "Project A"},
            "key_2": {"name": "Project B"},
        }

        result = await manager.list_projects()

        assert result == {"Project A": "key_1", "Project B": "key_2"}

    @pytest.mark.asyncio
    async def test_list_types(self, manager, mock_metadata_api):
        """测试列出所有类型"""
        mock_metadata_api.get_work_item_types.return_value = [
            {"name": "Issue", "type_key": "type_1"},
            {"name": "Story", "type_key": "type_2"},
        ]

        result = await manager.list_types("project_1")

        assert result == {"Issue": "type_1", "Story": "type_2"}

    @pytest.mark.asyncio
    async def test_list_fields(self, manager, mock_field_api):
        """测试列出所有字段"""
        mock_field_api.get_all_fields.return_value = [
            {"field_name": "优先级", "field_key": "priority"},
            {"field_name": "描述", "field_key": "description"},
        ]

        result = await manager.list_fields("project_1", "type_1")

        assert result["优先级"] == "priority"
        assert result["描述"] == "description"

    @pytest.mark.asyncio
    async def test_list_options(self, manager, mock_field_api):
        """测试列出所有选项"""
        mock_field_api.get_all_fields.return_value = [
            {
                "field_name": "优先级",
                "field_key": "priority",
                "options": [
                    {"label": "P0", "value": "option_1"},
                    {"label": "P1", "value": "option_2"},
                ],
            }
        ]

        result = await manager.list_options("project_1", "type_1", "priority")

        assert result == {"P0": "option_1", "P1": "option_2"}
