from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_target_status_match_failed_should_list_available_statuses():
    """当 target_status 无法匹配时，应返回中文提示并包含可选状态列表。"""

    from src.providers.lark_project.workflow_provider import WorkflowProvider

    with patch(
        "src.providers.lark_project.workflow_provider.MetadataManager"
    ) as mock_meta_cls, patch(
        "src.providers.lark_project.workflow_provider.WorkflowAPI"
    ) as mock_api_cls:
        mock_meta = AsyncMock()
        mock_meta.get_project_key.return_value = "pk"
        mock_meta.get_type_key.return_value = "tk"
        mock_meta_cls.get_instance.return_value = mock_meta

        mock_api = AsyncMock()
        mock_api.query_work_item_workflow.return_value = {
            "states": [
                {"state_key": "s1", "name": "待处理"},
                {"state_key": "s2", "name": "已完成"},
            ],
            "transitions": [
                {"transition_id": "t2", "to_state_key": "s2"},
            ],
        }
        mock_api_cls.return_value = mock_api

        provider = WorkflowProvider(project_name="My Project", work_item_type_name="问题管理")

        with pytest.raises(ValueError) as exc_info:
            await provider.get_transition_requirements(
                issue_id=123,
                target_status="不存在",
                mode="",
            )

        msg = str(exc_info.value)
        assert "可选状态" in msg
        assert "待处理" in msg


@pytest.mark.asyncio
async def test_get_transition_required_info_success_should_pass_correct_params():
    from src.providers.lark_project.workflow_provider import WorkflowProvider

    with patch(
        "src.providers.lark_project.workflow_provider.MetadataManager"
    ) as mock_meta_cls, patch(
        "src.providers.lark_project.workflow_provider.WorkflowAPI"
    ) as mock_api_cls:
        mock_meta = AsyncMock()
        mock_meta.get_project_key.return_value = "pk"
        mock_meta.get_type_key.return_value = "tk"
        mock_meta_cls.get_instance.return_value = mock_meta

        mock_api = AsyncMock()
        mock_api.query_work_item_workflow.return_value = {
            "states": [
                {"state_key": "s2", "name": "已完成"},
            ],
            "transitions": [
                {"transition_id": "t2", "to_state_key": "s2"},
            ],
        }
        mock_api.get_transition_required_info.return_value = {
            "required_fields": [{"field_key": "k"}]
        }
        mock_api_cls.return_value = mock_api

        provider = WorkflowProvider(project_name="My Project", work_item_type_name="问题管理")
        result = await provider.get_transition_requirements(
            issue_id=123,
            target_status="已完成",
            mode="strict",
        )

        assert result["required_fields"][0]["field_key"] == "k"

        mock_api.get_transition_required_info.assert_awaited_once_with(
            project_key="pk",
            work_item_type_key="tk",
            work_item_id=123,
            state_key="s2",
            mode="strict",
        )


@pytest.mark.asyncio
async def test_transition_success_should_call_state_change_with_transition_id_and_fields():
    from src.providers.lark_project.workflow_provider import WorkflowProvider

    with patch(
        "src.providers.lark_project.workflow_provider.MetadataManager"
    ) as mock_meta_cls, patch(
        "src.providers.lark_project.workflow_provider.WorkflowAPI"
    ) as mock_api_cls:
        mock_meta = AsyncMock()
        mock_meta.get_project_key.return_value = "pk"
        mock_meta.get_type_key.return_value = "tk"
        mock_meta_cls.get_instance.return_value = mock_meta

        mock_api = AsyncMock()
        mock_api.query_work_item_workflow.return_value = {
            "states": [
                {"state_key": "s2", "name": "已完成"},
            ],
            "transitions": [
                {"transition_id": "t2", "to_state_key": "s2"},
            ],
        }
        mock_api.state_change.return_value = None
        mock_api_cls.return_value = mock_api

        provider = WorkflowProvider(project_name="My Project", work_item_type_name="问题管理")
        fields = [{"field_key": "field_x", "field_value": "y"}]

        result = await provider.transition_task_status(
            issue_id=123,
            target_status="已完成",
            fields=fields,
        )

        assert result["issue_id"] == 123
        assert result["target_status"] == "已完成"

        mock_api.state_change.assert_awaited_once_with(
            project_key="pk",
            work_item_type_key="tk",
            work_item_id=123,
            transition_id="t2",
            fields=fields,
        )


@pytest.mark.asyncio
async def test_underlying_english_error_should_be_translated_to_chinese():
    from src.providers.lark_project.workflow_provider import WorkflowProvider

    with patch(
        "src.providers.lark_project.workflow_provider.MetadataManager"
    ) as mock_meta_cls, patch(
        "src.providers.lark_project.workflow_provider.WorkflowAPI"
    ) as mock_api_cls:
        mock_meta = AsyncMock()
        mock_meta.get_type_key.side_effect = Exception("Some Unknown Error")
        mock_meta_cls.get_instance.return_value = mock_meta

        mock_api_cls.return_value = AsyncMock()

        provider = WorkflowProvider(project_key="pk", work_item_type_name="问题管理")

        with pytest.raises(Exception) as exc_info:
            await provider.get_transition_requirements(
                issue_id=123,
                target_status="已完成",
                mode="",
            )

        assert "系统内部错误" in str(exc_info.value)
