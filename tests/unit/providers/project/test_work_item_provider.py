from unittest.mock import AsyncMock, patch

import pytest

from src.providers.project.work_item_provider import WorkItemProvider


@pytest.fixture
def mock_work_item_api():
    """Mock WorkItemAPI 实例"""
    with patch("src.providers.project.work_item_provider.WorkItemAPI") as mock_cls:
        yield mock_cls.return_value


@pytest.fixture
def mock_metadata():
    """Mock MetadataManager 实例"""
    with patch("src.providers.project.work_item_provider.MetadataManager") as mock_cls:
        mock_instance = AsyncMock()
        mock_cls.get_instance.return_value = mock_instance
        yield mock_instance


@pytest.mark.asyncio
async def test_create_issue(mock_work_item_api, mock_metadata):
    # Setup mocks
    mock_metadata.get_project_key.return_value = "proj_123"
    mock_metadata.get_type_key.return_value = "type_issue"
    mock_metadata.get_field_key.side_effect = lambda pk, tk, name: f"field_{name}"
    mock_metadata.get_option_value.return_value = "opt_high"
    mock_metadata.get_user_key.return_value = "user_456"

    mock_work_item_api.create = AsyncMock(return_value=1001)
    mock_work_item_api.update = AsyncMock()

    # Init provider
    provider = WorkItemProvider("My Project")

    # Execute
    issue_id = await provider.create_issue(
        name="Test Issue", priority="High", description="Desc", assignee="Alice"
    )

    # Verify
    assert issue_id == 1001

    # Check Metadata calls
    mock_metadata.get_project_key.assert_awaited_with("My Project")
    mock_metadata.get_type_key.assert_awaited_with("proj_123", "问题管理")

    # Check Create call
    # Create should be called with minimal fields first
    mock_work_item_api.create.assert_awaited_once()
    args, _ = mock_work_item_api.create.call_args
    assert args[0] == "proj_123"
    assert args[1] == "type_issue"
    assert args[2] == "Test Issue"

    fields = args[3]
    # 使用字典方式验证字段值，更清晰
    field_dict = {f["field_key"]: f["field_value"] for f in fields}
    assert field_dict.get("field_description") == "Desc"
    assert field_dict.get("owner") == "user_456"

    # Check Update call (for priority)
    mock_work_item_api.update.assert_awaited_once()
    args, _ = mock_work_item_api.update.call_args
    assert args[2] == 1001  # issue_id
    update_fields = args[3]
    assert update_fields[0]["field_key"] == "field_priority"
    assert update_fields[0]["field_value"] == "opt_high"


@pytest.mark.asyncio
async def test_get_issue_details(mock_work_item_api, mock_metadata):
    mock_metadata.get_project_key.return_value = "proj_123"
    mock_metadata.get_type_key.return_value = "type_issue"

    mock_work_item_api.query = AsyncMock(return_value=[{"id": 1001, "name": "Issue"}])

    provider = WorkItemProvider("My Project")
    details = await provider.get_issue_details(1001)

    assert details["id"] == 1001
    mock_work_item_api.query.assert_awaited_with("proj_123", "type_issue", [1001])


@pytest.mark.asyncio
async def test_delete_issue(mock_work_item_api, mock_metadata):
    mock_metadata.get_project_key.return_value = "proj_123"
    mock_metadata.get_type_key.return_value = "type_issue"
    mock_work_item_api.delete = AsyncMock()

    provider = WorkItemProvider("My Project")
    await provider.delete_issue(1001)

    mock_work_item_api.delete.assert_awaited_with("proj_123", "type_issue", 1001)


@pytest.mark.asyncio
async def test_update_issue(mock_work_item_api, mock_metadata):
    """测试更新 Issue"""
    # Setup mocks
    mock_metadata.get_project_key.return_value = "proj_123"
    mock_metadata.get_type_key.return_value = "type_issue"
    mock_metadata.get_field_key.side_effect = lambda pk, tk, name: f"field_{name}"
    mock_metadata.get_option_value.return_value = "opt_p0"
    mock_metadata.get_user_key.return_value = "user_789"

    mock_work_item_api.update = AsyncMock()

    provider = WorkItemProvider("My Project")

    # Execute: 更新多个字段
    await provider.update_issue(
        issue_id=1001,
        name="Updated Title",
        priority="P0",
        assignee="Bob",
    )

    # Verify
    mock_work_item_api.update.assert_awaited_once()
    args, _ = mock_work_item_api.update.call_args

    assert args[0] == "proj_123"  # project_key
    assert args[1] == "type_issue"  # type_key
    assert args[2] == 1001  # issue_id

    update_fields = args[3]
    # 应该包含 name, priority, owner 三个字段
    field_keys = [f["field_key"] for f in update_fields]
    assert "name" in field_keys
    assert "field_priority" in field_keys
    assert "owner" in field_keys


@pytest.mark.asyncio
async def test_update_issue_partial(mock_work_item_api, mock_metadata):
    """测试部分更新 Issue（只更新一个字段）"""
    mock_metadata.get_project_key.return_value = "proj_123"
    mock_metadata.get_type_key.return_value = "type_issue"
    mock_metadata.get_field_key.side_effect = lambda pk, tk, name: f"field_{name}"
    mock_metadata.get_option_value.return_value = "opt_done"

    mock_work_item_api.update = AsyncMock()

    provider = WorkItemProvider("My Project")

    # Execute: 只更新状态
    await provider.update_issue(issue_id=1001, status="已完成")

    # Verify
    mock_work_item_api.update.assert_awaited_once()
    args, _ = mock_work_item_api.update.call_args

    update_fields = args[3]
    assert len(update_fields) == 1
    assert update_fields[0]["field_key"] == "field_status"
    # _resolve_field_value_for_update 返回 {label, value} 结构用于 select 类型字段
    assert update_fields[0]["field_value"] == {"label": "已完成", "value": "opt_done"}


@pytest.mark.asyncio
async def test_filter_issues(mock_work_item_api, mock_metadata):
    """测试过滤查询 Issues"""
    # Setup mocks
    mock_metadata.get_project_key.return_value = "proj_123"
    mock_metadata.get_type_key.return_value = "type_issue"
    mock_metadata.get_field_key.side_effect = lambda pk, tk, name: f"field_{name}"
    mock_metadata.get_option_value.side_effect = lambda pk, tk, fk, val: f"opt_{val}"
    mock_metadata.get_user_key.return_value = "user_alice"

    mock_work_item_api.search_params = AsyncMock(
        return_value={
            "work_items": [
                {"id": 1001, "name": "Issue 1"},
                {"id": 1002, "name": "Issue 2"},
            ],
            "pagination": {"total": 2, "page_num": 1, "page_size": 20},
        }
    )

    provider = WorkItemProvider("My Project")

    # Execute: 按状态和负责人过滤
    result = await provider.filter_issues(
        status=["进行中", "待处理"],
        owner="Alice",
        page_num=1,
        page_size=20,
    )

    # Verify result
    assert result["total"] == 2
    assert len(result["items"]) == 2
    assert result["items"][0]["id"] == 1001

    # Verify API call
    mock_work_item_api.search_params.assert_awaited_once()
    args, kwargs = mock_work_item_api.search_params.call_args

    assert kwargs["project_key"] == "proj_123"
    assert kwargs["work_item_type_key"] == "type_issue"
    assert kwargs["page_num"] == 1
    assert kwargs["page_size"] == 20

    # 检查 search_group 结构
    search_group = kwargs["search_group"]
    assert search_group["conjunction"] == "AND"
    assert len(search_group["search_params"]) == 2  # status + owner


@pytest.mark.asyncio
async def test_filter_issues_by_priority(mock_work_item_api, mock_metadata):
    """测试按优先级过滤"""
    mock_metadata.get_project_key.return_value = "proj_123"
    mock_metadata.get_type_key.return_value = "type_issue"
    mock_metadata.get_field_key.side_effect = lambda pk, tk, name: f"field_{name}"
    mock_metadata.get_option_value.side_effect = lambda pk, tk, fk, val: f"opt_{val}"

    mock_work_item_api.search_params = AsyncMock(
        return_value={
            "work_items": [{"id": 1001, "name": "P0 Issue"}],
            "pagination": {"total": 1, "page_num": 1, "page_size": 20},
        }
    )

    provider = WorkItemProvider("My Project")

    # Execute: 按优先级过滤
    result = await provider.filter_issues(priority=["P0", "P1"])

    # Verify
    assert result["total"] == 1

    # 检查 search_group 包含 priority 条件
    _, kwargs = mock_work_item_api.search_params.call_args
    search_group = kwargs["search_group"]
    conditions = search_group["search_params"]

    assert len(conditions) == 1
    assert conditions[0]["field_key"] == "field_priority"
    assert conditions[0]["operator"] == "IN"
    assert "opt_P0" in conditions[0]["value"]
    assert "opt_P1" in conditions[0]["value"]


@pytest.mark.asyncio
async def test_get_tasks(mock_work_item_api, mock_metadata):
    """测试获取工作项（支持全量和过滤）"""
    mock_metadata.get_project_key.return_value = "proj_123"
    mock_metadata.get_type_key.return_value = "type_issue"
    mock_metadata.get_field_key.side_effect = lambda pk, tk, name: f"field_{name}"
    mock_metadata.get_option_value.side_effect = lambda pk, tk, fk, val: f"opt_{val}"

    mock_work_item_api.search_params = AsyncMock(
        return_value={
            "work_items": [
                {"id": 1001, "name": "Task 1"},
                {"id": 1002, "name": "Task 2"},
            ],
            "pagination": {"total": 2, "page_num": 1, "page_size": 50},
        }
    )

    provider = WorkItemProvider("My Project")

    # Execute - 获取全部任务
    result = await provider.get_tasks(page_size=50)

    # Verify
    assert result["total"] == 2
    assert result["page_num"] == 1
    assert result["page_size"] == 50
    assert len(result["items"]) == 2
    assert result["items"][0]["id"] == 1001

    # 检查调用了 search_params
    mock_work_item_api.search_params.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_available_options(mock_work_item_api, mock_metadata):
    """测试列出字段可用选项"""
    mock_metadata.get_project_key.return_value = "proj_123"
    mock_metadata.get_type_key.return_value = "type_issue"
    mock_metadata.get_field_key.return_value = "field_status"
    mock_metadata.list_options.return_value = {
        "待处理": "opt_pending",
        "进行中": "opt_in_progress",
        "已完成": "opt_done",
    }

    provider = WorkItemProvider("My Project")

    # Execute
    options = await provider.list_available_options("status")

    # Verify
    assert "待处理" in options
    assert options["待处理"] == "opt_pending"
    mock_metadata.list_options.assert_awaited_with(
        "proj_123", "type_issue", "field_status"
    )


@pytest.mark.asyncio
async def test_filter_issues_empty_conditions(mock_work_item_api, mock_metadata):
    """测试无过滤条件时的查询"""
    mock_metadata.get_project_key.return_value = "proj_123"
    mock_metadata.get_type_key.return_value = "type_issue"

    mock_work_item_api.search_params = AsyncMock(
        return_value={
            "work_items": [],
            "pagination": {"total": 0, "page_num": 1, "page_size": 20},
        }
    )

    provider = WorkItemProvider("My Project")

    # Execute: 无任何过滤条件
    result = await provider.filter_issues()

    # Verify
    assert result["total"] == 0
    assert result["items"] == []

    # 检查 search_group 为空条件
    _, kwargs = mock_work_item_api.search_params.call_args
    search_group = kwargs["search_group"]
    assert search_group["search_params"] == []


# =============================================================================
# 异常流测试 (Exception Flow Tests)
# =============================================================================


class TestProviderExceptionHandling:
    """Provider 异常处理测试"""

    @pytest.mark.asyncio
    async def test_project_not_found(self, mock_work_item_api, mock_metadata):
        """测试项目不存在时抛出明确错误"""
        mock_metadata.get_project_key.side_effect = ValueError(
            "项目 'Unknown Project' 不存在"
        )

        provider = WorkItemProvider("Unknown Project")

        with pytest.raises(ValueError) as exc_info:
            await provider.create_issue(name="Test")

        assert "不存在" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_work_item_type_not_found(self, mock_work_item_api, mock_metadata):
        """测试工作项类型不存在时抛出明确错误"""
        mock_metadata.get_project_key.return_value = "proj_123"
        mock_metadata.get_type_key.side_effect = ValueError(
            "工作项类型 'Unknown' 不存在"
        )
        # 当使用默认类型 "问题管理" 时，fallback 逻辑会尝试获取可用类型
        # 返回空字典模拟没有可用类型的情况
        mock_metadata.list_types.return_value = {}

        provider = WorkItemProvider("My Project")

        with pytest.raises(ValueError) as exc_info:
            await provider.create_issue(name="Test")

        # 新的错误信息格式：没有可用的工作项类型
        assert "没有可用的工作项类型" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_api_error_propagation(self, mock_work_item_api, mock_metadata):
        """测试 API 错误被正确传递"""
        mock_metadata.get_project_key.return_value = "proj_123"
        mock_metadata.get_type_key.return_value = "type_issue"
        mock_metadata.get_field_key.side_effect = lambda pk, tk, name: f"field_{name}"
        mock_work_item_api.create = AsyncMock(
            side_effect=Exception("API 调用失败: 500 Internal Server Error")
        )

        provider = WorkItemProvider("My Project")

        with pytest.raises(Exception) as exc_info:
            await provider.create_issue(name="Test")

        assert "API 调用失败" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_field_key_not_found(self, mock_work_item_api, mock_metadata):
        """测试字段名不存在时抛出明确错误"""
        mock_metadata.get_project_key.return_value = "proj_123"
        mock_metadata.get_type_key.return_value = "type_issue"
        mock_metadata.get_field_key.side_effect = ValueError(
            "字段 'unknown_field' 不存在"
        )

        provider = WorkItemProvider("My Project")

        with pytest.raises(ValueError) as exc_info:
            await provider.update_issue(issue_id=1001, status="进行中")

        assert "不存在" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_option_value_fallback(self, mock_work_item_api, mock_metadata):
        """测试选项值解析失败时的回退机制"""
        mock_metadata.get_project_key.return_value = "proj_123"
        mock_metadata.get_type_key.return_value = "type_issue"
        mock_metadata.get_field_key.side_effect = lambda pk, tk, name: f"field_{name}"

        # 模拟 get_option_value 抛出异常
        mock_metadata.get_option_value.side_effect = Exception("Option not found")

        mock_work_item_api.update = AsyncMock()

        provider = WorkItemProvider("My Project")

        # Execute: 更新 invalid 选项
        await provider.update_issue(issue_id=1001, status="InvalidOption")

        # Verify: API 应该被调用，且使用原始值 "InvalidOption"
        mock_work_item_api.update.assert_awaited_once()
        args, _ = mock_work_item_api.update.call_args
        update_fields = args[3]

        assert len(update_fields) == 1
        assert update_fields[0]["field_value"] == "InvalidOption"


# =============================================================================
# 分页边界测试 (Pagination Boundary Tests)
# =============================================================================


class TestProviderPagination:
    """Provider 分页边界测试"""

    @pytest.mark.asyncio
    async def test_get_tasks_large_page_size(self, mock_work_item_api, mock_metadata):
        """测试超大分页 (page_size > 100)"""
        mock_metadata.get_project_key.return_value = "proj_123"
        mock_metadata.get_type_key.return_value = "type_issue"

        mock_work_item_api.search_params = AsyncMock(
            return_value={"work_items": [], "pagination": {}}
        )

        provider = WorkItemProvider("My Project")

        # Execute: page_size=200
        await provider.get_tasks(page_size=200)

        # Verify API called with 200 (passthrough)
        _, kwargs = mock_work_item_api.search_params.call_args
        assert kwargs["page_size"] == 200

    @pytest.mark.asyncio
    async def test_get_tasks_empty_page(self, mock_work_item_api, mock_metadata):
        """测试获取空页（没有任何工作项）"""
        mock_metadata.get_project_key.return_value = "proj_123"
        mock_metadata.get_type_key.return_value = "type_issue"

        mock_work_item_api.search_params = AsyncMock(
            return_value={
                "work_items": [],
                "pagination": {"total": 0, "page_num": 1, "page_size": 50},
            }
        )

        provider = WorkItemProvider("My Project")
        result = await provider.get_tasks(page_size=50)

        assert result["total"] == 0
        assert result["items"] == []
        assert result["page_num"] == 1
        assert result["page_size"] == 50

    @pytest.mark.asyncio
    async def test_get_tasks_last_page(self, mock_work_item_api, mock_metadata):
        """测试获取最后一页（部分数据）"""
        mock_metadata.get_project_key.return_value = "proj_123"
        mock_metadata.get_type_key.return_value = "type_issue"

        # 假设总共 55 条数据，每页 20 条，第 3 页只有 15 条
        mock_work_item_api.search_params = AsyncMock(
            return_value={
                "work_items": [{"id": i, "name": f"Task {i}"} for i in range(41, 56)],
                "pagination": {"total": 55, "page_num": 3, "page_size": 20},
            }
        )

        provider = WorkItemProvider("My Project")
        result = await provider.get_tasks(page_num=3, page_size=20)

        assert result["total"] == 55
        assert len(result["items"]) == 15  # 最后一页只有 15 条
        assert result["page_num"] == 3

    @pytest.mark.asyncio
    async def test_get_tasks_beyond_total_pages(
        self, mock_work_item_api, mock_metadata
    ):
        """测试请求超出总页数的页码（应返回空列表）"""
        mock_metadata.get_project_key.return_value = "proj_123"
        mock_metadata.get_type_key.return_value = "type_issue"

        mock_work_item_api.search_params = AsyncMock(
            return_value={
                "work_items": [],
                "pagination": {"total": 55, "page_num": 100, "page_size": 20},
            }
        )

        provider = WorkItemProvider("My Project")
        result = await provider.get_tasks(page_num=100, page_size=20)

        assert result["total"] == 55
        assert result["items"] == []
        assert result["page_num"] == 100

    @pytest.mark.asyncio
    async def test_filter_issues_with_pagination(
        self, mock_work_item_api, mock_metadata
    ):
        """测试过滤查询的分页参数正确传递"""
        mock_metadata.get_project_key.return_value = "proj_123"
        mock_metadata.get_type_key.return_value = "type_issue"
        mock_metadata.get_field_key.side_effect = lambda pk, tk, name: f"field_{name}"
        mock_metadata.get_option_value.side_effect = (
            lambda pk, tk, fk, val: f"opt_{val}"
        )

        mock_work_item_api.search_params = AsyncMock(
            return_value={
                "work_items": [{"id": 1, "name": "Task 1"}],
                "pagination": {"total": 100, "page_num": 5, "page_size": 10},
            }
        )

        provider = WorkItemProvider("My Project")
        result = await provider.filter_issues(
            status=["进行中"],
            page_num=5,
            page_size=10,
        )

        # 验证分页参数被正确传递
        _, kwargs = mock_work_item_api.search_params.call_args
        assert kwargs["page_num"] == 5
        assert kwargs["page_size"] == 10

        # 验证返回值包含分页信息
        assert result["total"] == 100
        assert result["page_num"] == 5
        assert result["page_size"] == 10


@pytest.mark.asyncio
async def test_get_readable_issue_details(mock_work_item_api, mock_metadata):
    """测试获取可读的工作项详情（用户字段转换为人名）"""
    mock_metadata.get_project_key.return_value = "proj_123"
    mock_metadata.get_type_key.return_value = "type_issue"
    # 模拟字段映射 - 使用英文字段名以匹配测试期望
    mock_metadata.list_fields = AsyncMock(
        return_value={
            "owner": "owner",
            "status": "status",
            "priority": "priority",
            "creator": "creator",
        }
    )

    # 模拟 API 返回包含用户字段的工作项
    mock_work_item_api.query = AsyncMock(
        return_value=[
            {
                "id": 1001,
                "name": "Test Issue",
                "field_value_pairs": [
                    {
                        "field_key": "owner",
                        "field_value": [{"name": "张三", "user_key": "user_123"}],
                    },
                    {
                        "field_key": "status",
                        "field_value": {"label": "进行中", "value": "opt_in_progress"},
                    },
                    {
                        "field_key": "priority",
                        "field_value": {"label": "P0", "value": "opt_p0"},
                    },
                    {
                        "field_key": "creator",
                        "field_value": {"name": "李四", "user_key": "user_456"},
                    },
                ],
            }
        ]
    )

    provider = WorkItemProvider("My Project")
    result = await provider.get_readable_issue_details(1001)

    # 验证基本字段
    assert result["id"] == 1001
    assert result["name"] == "Test Issue"

    # 验证可读字段存在
    assert "readable_fields" in result
    readable_fields = result["readable_fields"]

    # 验证用户字段转换为人名
    assert readable_fields["owner"] == "张三"
    assert readable_fields["creator"] == "李四"
    assert readable_fields["status"] == "进行中"
    assert readable_fields["priority"] == "P0"

    # 验证常用字段的顶级别名
    assert result.get("readable_owner") == "张三"
    assert result.get("readable_creator") == "李四"

    # 验证原始数据仍然存在
    assert "field_value_pairs" in result
