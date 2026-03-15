import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMCPHierarchyTools:

    @pytest.mark.asyncio
    async def test_list_child_tasks_success_project_name_branch(self):
        from src.mcp_server import list_child_tasks

        with patch("src.mcp_server.HierarchyProvider") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.list_child_tasks = AsyncMock(return_value=[11, 12])
            mock_cls.return_value = mock_instance

            result = await list_child_tasks(
                parent_issue_id=123,
                relation_name="子任务",
                project="proj_xxx",
                work_item_type="Issue管理",
            )

            data = json.loads(result)
            assert data["success"] is True
            assert data["data"]["work_item_ids"] == [11, 12]

            mock_cls.assert_called_once_with(
                project_name="proj_xxx",
                work_item_type_name="Issue管理",
            )
            mock_instance.list_child_tasks.assert_awaited_once_with(
                parent_issue_id=123,
                relation_name="子任务",
                page_num=1,
                page_size=20,
            )

    @pytest.mark.asyncio
    async def test_list_child_tasks_success_project_key_branch(self):
        from src.mcp_server import list_child_tasks

        with patch("src.mcp_server.HierarchyProvider") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.list_child_tasks = AsyncMock(return_value=[])
            mock_cls.return_value = mock_instance

            result = await list_child_tasks(parent_issue_id=123, project="project_abc")

            data = json.loads(result)
            assert data["success"] is True

            mock_cls.assert_called_once_with(project_key="project_abc")
            mock_instance.list_child_tasks.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_bind_child_tasks_success_project_name_branch(self):
        from src.mcp_server import bind_child_tasks

        with patch("src.mcp_server.HierarchyProvider") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.bind_child_tasks = AsyncMock(
                return_value={
                    "parent_issue_id": 123,
                    "child_issue_ids": [1, 2],
                    "relation_name": "子任务",
                }
            )
            mock_cls.return_value = mock_instance

            result = await bind_child_tasks(
                parent_issue_id=123,
                child_issue_ids=[1, 2],
                relation_name="子任务",
                project="proj_xxx",
                work_item_type="Issue管理",
            )

            data = json.loads(result)
            assert data["success"] is True
            assert data["data"]["parent_issue_id"] == 123

            mock_cls.assert_called_once_with(
                project_name="proj_xxx",
                work_item_type_name="Issue管理",
            )
            mock_instance.bind_child_tasks.assert_awaited_once_with(
                parent_issue_id=123,
                child_issue_ids=[1, 2],
                relation_name="子任务",
            )

    @pytest.mark.asyncio
    async def test_unbind_child_tasks_success_project_name_branch(self):
        from src.mcp_server import unbind_child_tasks

        with patch("src.mcp_server.HierarchyProvider") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.unbind_child_tasks = AsyncMock(
                return_value={"parent_issue_id": 123, "relation_name": "子任务"}
            )
            mock_cls.return_value = mock_instance

            result = await unbind_child_tasks(
                parent_issue_id=123,
                relation_name="子任务",
                project="proj_xxx",
                work_item_type="Issue管理",
            )

            data = json.loads(result)
            assert data["success"] is True
            assert data["data"]["parent_issue_id"] == 123

            mock_cls.assert_called_once_with(
                project_name="proj_xxx",
                work_item_type_name="Issue管理",
            )
            mock_instance.unbind_child_tasks.assert_awaited_once_with(
                parent_issue_id=123,
                relation_name="子任务",
            )
