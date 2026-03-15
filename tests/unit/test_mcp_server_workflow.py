import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMCPWorkflowTools:

    @pytest.mark.asyncio
    async def test_get_task_transition_requirements_success_project_name_branch(self):
        from src.mcp_server import get_task_transition_requirements

        with patch("src.mcp_server.WorkflowProvider") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.get_transition_requirements = AsyncMock(
                return_value={"required_fields": [{"field_key": "k"}]}
            )
            mock_cls.return_value = mock_instance

            result = await get_task_transition_requirements(
                issue_id=123,
                target_status="已完成",
                project="proj_xxx",
                work_item_type="Issue管理",
                mode="strict",
            )

            data = json.loads(result)
            assert data["success"] is True
            assert data["data"]["required_fields"][0]["field_key"] == "k"

            mock_cls.assert_called_once_with(
                project_name="proj_xxx",
                work_item_type_name="Issue管理",
            )
            mock_instance.get_transition_requirements.assert_awaited_once_with(
                issue_id=123,
                target_status="已完成",
                mode="strict",
            )

    @pytest.mark.asyncio
    async def test_get_task_transition_requirements_success_project_key_branch(self):
        from src.mcp_server import get_task_transition_requirements

        with patch("src.mcp_server.WorkflowProvider") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.get_transition_requirements = AsyncMock(
                return_value={"required_fields": []}
            )
            mock_cls.return_value = mock_instance

            result = await get_task_transition_requirements(
                issue_id=123,
                target_status="已完成",
                project="project_abc",
                work_item_type=None,
            )

            data = json.loads(result)
            assert data["success"] is True
            assert "data" in data

            mock_cls.assert_called_once_with(project_key="project_abc")
            mock_instance.get_transition_requirements.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_transition_task_status_success_project_name_branch(self):
        from src.mcp_server import transition_task_status

        with patch("src.mcp_server.WorkflowProvider") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.transition_task_status = AsyncMock(
                return_value={"issue_id": 123, "target_status": "已完成"}
            )
            mock_cls.return_value = mock_instance

            result = await transition_task_status(
                issue_id=123,
                target_status="已完成",
                fields=[{"field_key": "k", "field_value": "v"}],
                project="proj_xxx",
                work_item_type="Issue管理",
                mode="",
            )

            data = json.loads(result)
            assert data["success"] is True
            assert data["data"]["issue_id"] == 123

            mock_cls.assert_called_once_with(
                project_name="proj_xxx",
                work_item_type_name="Issue管理",
            )
            mock_instance.transition_task_status.assert_awaited_once_with(
                issue_id=123,
                target_status="已完成",
                fields=[{"field_key": "k", "field_value": "v"}],
                mode="",
            )

    @pytest.mark.asyncio
    async def test_transition_task_status_success_project_key_branch(self):
        from src.mcp_server import transition_task_status

        with patch("src.mcp_server.WorkflowProvider") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.transition_task_status = AsyncMock(
                return_value={"issue_id": 123, "target_status": "已完成"}
            )
            mock_cls.return_value = mock_instance

            result = await transition_task_status(
                issue_id=123,
                target_status="已完成",
                project="project_abc",
            )

            data = json.loads(result)
            assert data["success"] is True

            mock_cls.assert_called_once_with(project_key="project_abc")
            mock_instance.transition_task_status.assert_awaited_once()
