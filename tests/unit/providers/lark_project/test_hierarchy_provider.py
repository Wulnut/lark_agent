from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_rules_single_should_auto_select_and_list_child_tasks_calls_work_item_list_with_relation_key():
    from src.providers.lark_project.hierarchy_provider import HierarchyProvider

    with patch(
        "src.providers.lark_project.hierarchy_provider.MetadataManager"
    ) as mock_meta_cls, patch(
        "src.providers.lark_project.hierarchy_provider.RelationAPI"
    ) as mock_api_cls:
        mock_meta = AsyncMock()
        mock_meta.get_type_key.return_value = "tk"
        mock_meta_cls.get_instance.return_value = mock_meta

        mock_api = AsyncMock()
        mock_api.rules.return_value = {"rules": [{"name": "子任务", "relation_key": "rk1"}]}
        mock_api.work_item_list.return_value = {"work_item_ids": [11, 12]}
        mock_api_cls.return_value = mock_api

        provider = HierarchyProvider(project_key="pk", work_item_type_name="问题管理")

        ids = await provider.list_child_tasks(parent_issue_id=123)

        assert ids == [11, 12]

        mock_api.rules.assert_awaited_once_with("pk")
        mock_meta.get_type_key.assert_awaited_once_with("pk", "问题管理")
        mock_api.work_item_list.assert_awaited_once_with(
            project_key="pk",
            work_item_type_key="tk",
            work_item_id=123,
            page_num=1,
            page_size=20,
            relation_key="rk1",
        )


@pytest.mark.asyncio
async def test_rules_multiple_without_relation_name_should_raise_value_error_and_list_candidates():
    from src.providers.lark_project.hierarchy_provider import HierarchyProvider

    with patch(
        "src.providers.lark_project.hierarchy_provider.MetadataManager"
    ) as mock_meta_cls, patch(
        "src.providers.lark_project.hierarchy_provider.RelationAPI"
    ) as mock_api_cls:
        mock_meta = AsyncMock()
        mock_meta.get_type_key.return_value = "tk"
        mock_meta_cls.get_instance.return_value = mock_meta

        mock_api = AsyncMock()
        mock_api.rules.return_value = {
            "rules": [
                {"name": "子任务", "relation_key": "rk1"},
                {"name": "关联", "relation_key": "rk2"},
            ]
        }
        mock_api_cls.return_value = mock_api

        provider = HierarchyProvider(project_key="pk", work_item_type_name="问题管理")

        with pytest.raises(ValueError) as exc_info:
            await provider.list_child_tasks(parent_issue_id=123)

        msg = str(exc_info.value)
        assert "relation_name" in msg
        assert "子任务" in msg
        assert "关联" in msg


@pytest.mark.asyncio
async def test_relation_name_not_found_should_raise_value_error_and_list_candidates():
    from src.providers.lark_project.hierarchy_provider import HierarchyProvider

    with patch(
        "src.providers.lark_project.hierarchy_provider.MetadataManager"
    ) as mock_meta_cls, patch(
        "src.providers.lark_project.hierarchy_provider.RelationAPI"
    ) as mock_api_cls:
        mock_meta = AsyncMock()
        mock_meta.get_type_key.return_value = "tk"
        mock_meta_cls.get_instance.return_value = mock_meta

        mock_api = AsyncMock()
        mock_api.rules.return_value = {
            "rules": [
                {"name": "子任务", "relation_key": "rk1"},
                {"name": "关联", "relation_key": "rk2"},
            ]
        }
        mock_api_cls.return_value = mock_api

        provider = HierarchyProvider(project_key="pk", work_item_type_name="问题管理")

        with pytest.raises(ValueError) as exc_info:
            await provider.list_child_tasks(parent_issue_id=123, relation_name="不存在")

        msg = str(exc_info.value)
        assert "无法匹配" in msg
        assert "子任务" in msg
        assert "关联" in msg


@pytest.mark.asyncio
async def test_bind_and_unbind_should_call_relation_api_with_correct_params():
    from src.providers.lark_project.hierarchy_provider import HierarchyProvider

    with patch(
        "src.providers.lark_project.hierarchy_provider.MetadataManager"
    ) as mock_meta_cls, patch(
        "src.providers.lark_project.hierarchy_provider.RelationAPI"
    ) as mock_api_cls:
        mock_meta = AsyncMock()
        mock_meta.get_type_key.return_value = "tk"
        mock_meta_cls.get_instance.return_value = mock_meta

        mock_api = AsyncMock()
        mock_api.rules.return_value = {"rules": [{"name": "子任务", "relation_key": "rk1"}]}
        mock_api.batch_bind.return_value = {}
        mock_api.delete.return_value = None
        mock_api_cls.return_value = mock_api

        provider = HierarchyProvider(project_key="pk", work_item_type_name="问题管理")

        bind_result = await provider.bind_child_tasks(
            parent_issue_id=123,
            child_issue_ids=[1, 2, 3],
            relation_name="子任务",
        )

        assert bind_result["parent_issue_id"] == 123
        assert bind_result["child_issue_ids"] == [1, 2, 3]
        assert bind_result["relation_name"] == "子任务"

        mock_api.batch_bind.assert_awaited_once_with(
            project_key="pk",
            work_item_type_key="tk",
            work_item_id=123,
            relation_key="rk1",
            work_item_ids=[1, 2, 3],
        )

        unbind_result = await provider.unbind_child_tasks(
            parent_issue_id=123,
            relation_name="子任务",
        )

        assert unbind_result["parent_issue_id"] == 123
        assert unbind_result["relation_name"] == "子任务"

        mock_api.delete.assert_awaited_once_with(
            project_key="pk", work_item_type_key="tk", work_item_id=123
        )


@pytest.mark.asyncio
async def test_underlying_english_error_should_be_translated_to_chinese():
    from src.providers.lark_project.hierarchy_provider import HierarchyProvider

    with patch(
        "src.providers.lark_project.hierarchy_provider.MetadataManager"
    ) as mock_meta_cls, patch(
        "src.providers.lark_project.hierarchy_provider.RelationAPI"
    ):
        mock_meta = AsyncMock()
        mock_meta.get_type_key.side_effect = Exception("Some Unknown Error")
        mock_meta_cls.get_instance.return_value = mock_meta

        provider = HierarchyProvider(project_key="pk", work_item_type_name="问题管理")

        with pytest.raises(Exception) as exc_info:
            await provider.list_child_tasks(parent_issue_id=123, relation_name="子任务")

        assert "系统内部错误" in str(exc_info.value)
