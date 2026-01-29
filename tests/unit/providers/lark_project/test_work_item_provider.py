from unittest.mock import AsyncMock, patch

import pytest

from src.providers.lark_project.work_item_provider import WorkItemProvider


@pytest.fixture
def mock_work_item_api():
    """Mock WorkItemAPI 实例"""
    with patch("src.providers.lark_project.work_item_provider.WorkItemAPI") as mock_cls:
        yield mock_cls.return_value


@pytest.fixture
def mock_metadata():
    """Mock MetadataManager 实例"""
    with patch(
        "src.providers.lark_project.work_item_provider.MetadataManager"
    ) as mock_cls:
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
        """测试字段名不存在时返回失败结果"""
        mock_metadata.get_project_key.return_value = "proj_123"
        mock_metadata.get_type_key.return_value = "type_issue"
        # 模拟 get_field_key 抛出 ValueError
        mock_metadata.get_field_key.side_effect = ValueError(
            "字段 'status' 不存在"
        )

        provider = WorkItemProvider("My Project")

        # 现在不再抛出异常，而是返回结果列表
        results = await provider.update_issue(issue_id=1001, status="进行中")

        assert len(results) == 1
        assert results[0].success is False
        assert "不存在" in results[0].message
        assert results[0].field_name == "status"

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

    # 模拟 field_key -> field_name 映射
    async def mock_get_field_name(project_key, type_key, field_key):
        field_key_to_name = {
            "owner": "owner",
            "status": "status",
            "priority": "priority",
            "creator": "creator",
        }
        return field_key_to_name.get(field_key)

    mock_metadata.get_field_name = AsyncMock(side_effect=mock_get_field_name)

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

    # 验证 fields 数组中每个字段都包含 field_name
    assert "fields" in result
    fields = result["fields"]
    assert len(fields) > 0
    for field in fields:
        assert "field_name" in field, f"字段 {field.get('field_key')} 缺少 field_name"
        assert "field_key" in field
        assert "field_value" in field

    # 验证常用字段的顶级别名
    assert result.get("readable_owner") == "张三"
    assert result.get("readable_creator") == "李四"

    # 验证原始数据仍然存在
    assert "field_value_pairs" in result


class TestBatchUpdateIssues:
    """测试批量更新工作项"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mock_work_item_api, mock_metadata):
        mock_metadata.get_project_key.return_value = "proj_123"
        mock_metadata.get_type_key.return_value = "type_issue"
        # 模拟 get_field_key，对 'InvalidField' 抛出异常
        mock_metadata.get_field_key.side_effect = lambda pk, tk, name: (
            f"field_{name}"
            if name != "InvalidField"
            else (_ for _ in ()).throw(ValueError("字段 'InvalidField' 不存在"))
        )
        mock_metadata.get_option_value.side_effect = lambda pk, tk, fk, val: (
            "opt_val"
            if fk in ["field_priority", "field_status"]
            else (_ for _ in ()).throw(Exception("不是选项字段"))
        )
        mock_metadata.get_user_key.return_value = "user_abc"

        # mock_work_item_api.update 会被 _perform_single_field_update 调用
        # 模拟每次更新都成功
        mock_work_item_api.update = AsyncMock(return_value=None)

    @pytest.mark.asyncio
    async def test_batch_update_issues_all_success(self, mock_work_item_api):
        issue_ids = [101, 102]
        results = await WorkItemProvider("My Project").batch_update_issues(
            issue_ids=issue_ids,
            name="New Title",
            priority="P1",
            extra_fields={"自定义字段": "Custom Value"},
        )

        assert (
            len(results) == len(issue_ids) * 3
        )  # 2 issues * 3 fields (name, priority, extra_field)
        for result in results:
            assert result.success is True
            assert result.issue_id in issue_ids
            assert "更新成功" in result.message

        # Verify calls for each field and each issue
        # 总共 2 issues * 3 fields = 6 次调用 WorkItemAPI.update
        assert mock_work_item_api.update.call_count == len(issue_ids) * 3

        call_args_list = mock_work_item_api.update.call_args_list
        # 检查 issue 101 的 'name' 字段更新
        assert any(
            call.args[2] == 101
            and call.args[3][0]["field_key"] == "name"
            and call.args[3][0]["field_value"] == "New Title"
            for call in call_args_list
        )
        # 检查 issue 102 的 'priority' 字段更新
        assert any(
            call.args[2] == 102
            and call.args[3][0]["field_key"] == "field_priority"
            and call.args[3][0]["field_value"]["value"] == "opt_val"
            for call in call_args_list
        )
        # 检查 issue 101 的 '自定义字段' 更新
        assert any(
            call.args[2] == 101
            and call.args[3][0]["field_key"] == "field_自定义字段"
            and call.args[3][0]["field_value"] == "Custom Value"
            for call in call_args_list
        )

    @pytest.mark.asyncio
    async def test_batch_update_issues_partial_failure(
        self, mock_work_item_api, mock_metadata
    ):
        issue_ids = [101, 102]

        # 模拟 get_field_key 在解析 'InvalidField' 时抛出异常
        # 这样 _perform_single_field_update 会捕获它并返回 success=False

        results = await WorkItemProvider("My Project").batch_update_issues(
            issue_ids=issue_ids,
            name="Partial Update Title",
            priority="P2",
            extra_fields={"InvalidField": "Some Value", "ValidField": "Another Value"},
        )

        # 预期总共有 2 issues * 4 fields = 8 个结果 (name, priority, InvalidField, ValidField)
        assert len(results) == len(issue_ids) * 4

        success_count = sum(1 for r in results if r.success)
        failure_count = sum(1 for r in results if not r.success)

        # 预期:
        # 101: name (success), priority (success), InvalidField (fail), ValidField (success)
        # 102: name (success), priority (success), InvalidField (fail), ValidField (success)
        # 总计: 6 success, 2 fail
        assert success_count == 6
        assert failure_count == 2

        # 检查具体的失败结果
        failed_results = [r for r in results if not r.success]
        assert len(failed_results) == 2

        for failed_res in failed_results:
            assert failed_res.field_name == "InvalidField"
            assert "不存在" in failed_res.message
            assert failed_res.issue_id in issue_ids

        # 检查成功的调用 WorkItemAPI.update 的次数
        # 2 issues * 3 (name, priority, ValidField) = 6 次 api.update 调用
        assert mock_work_item_api.update.call_count == 6

    @pytest.mark.asyncio
    async def test_batch_update_issues_no_fields_to_update(self, mock_work_item_api):
        issue_ids = [101, 102]
        results = await WorkItemProvider("My Project").batch_update_issues(
            issue_ids=issue_ids
        )
        assert len(results) == 0
        mock_work_item_api.update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_batch_update_issues_empty_issue_ids(self, mock_work_item_api):
        results = await WorkItemProvider("My Project").batch_update_issues(
            issue_ids=[], name="Test"
        )
        assert len(results) == 0
        mock_work_item_api.update.assert_not_awaited()
