import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMCPCommentTools:

    @pytest.mark.asyncio
    async def test_add_task_comment_success_project_name_branch(self):
        from src.mcp_server import add_task_comment

        with patch("src.mcp_server.CommentProvider") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.add_comment = AsyncMock(return_value={"comment_id": "c1"})
            mock_cls.return_value = mock_instance

            result = await add_task_comment(
                issue_id=123,
                content="hello",
                project="proj_xxx",
                work_item_type="Issue管理",
            )

            data = json.loads(result)
            assert data["success"] is True
            assert data["data"]["comment_id"] == "c1"

            # project 不以 project_ 开头时，应被当作 project_name
            mock_cls.assert_called_once_with(
                project_name="proj_xxx",
                work_item_type_name="Issue管理",
            )
            mock_instance.add_comment.assert_awaited_once_with(123, "hello")

    @pytest.mark.asyncio
    async def test_add_task_comment_project_key_branch(self):
        from src.mcp_server import add_task_comment

        with patch("src.mcp_server.CommentProvider") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.add_comment = AsyncMock(return_value={"comment_id": "c1"})
            mock_cls.return_value = mock_instance

            result = await add_task_comment(
                issue_id=123,
                content="hello",
                project="project_abc",
                work_item_type="Issue管理",
            )

            data = json.loads(result)
            assert data["success"] is True
            assert data["data"]["comment_id"] == "c1"

            # project 以 project_ 开头时应被当作 project_key
            mock_cls.assert_called_once_with(
                project_key="project_abc",
                work_item_type_name="Issue管理",
            )
            mock_instance.add_comment.assert_awaited_once_with(123, "hello")

    @pytest.mark.asyncio
    async def test_list_task_comments_success_project_name_branch(self):
        from src.mcp_server import list_task_comments

        with patch("src.mcp_server.CommentProvider") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.list_comments = AsyncMock(
                return_value={
                    "total": 1,
                    "page_num": 1,
                    "page_size": 20,
                    "items": [{"comment_id": "c1", "content": "hello"}],
                }
            )
            mock_cls.return_value = mock_instance

            result = await list_task_comments(
                issue_id=123,
                project="proj_xxx",
                work_item_type="Issue管理",
            )
            data = json.loads(result)

            assert data["success"] is True
            assert data["data"]["total"] == 1
            assert data["data"]["page_num"] == 1
            assert data["data"]["page_size"] == 20
            assert isinstance(data["data"]["items"], list)

            mock_cls.assert_called_once_with(
                project_name="proj_xxx",
                work_item_type_name="Issue管理",
            )
            mock_instance.list_comments.assert_awaited_once_with(
                123, page_num=1, page_size=20
            )

    @pytest.mark.asyncio
    async def test_list_task_comments_success_project_key_branch(self):
        from src.mcp_server import list_task_comments

        with patch("src.mcp_server.CommentProvider") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.list_comments = AsyncMock(return_value={"total": 0, "items": []})
            mock_cls.return_value = mock_instance

            result = await list_task_comments(issue_id=123, project="project_abc")
            data = json.loads(result)

            assert data["success"] is True
            assert "data" in data
            # 结构字段存在即可（此分支 mock 返回较少字段）
            assert isinstance(data["data"], dict)

            mock_cls.assert_called_once_with(project_key="project_abc")
            mock_instance.list_comments.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_task_comment_success_project_name_branch(self):
        from src.mcp_server import update_task_comment

        with patch("src.mcp_server.CommentProvider") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.update_comment = AsyncMock(return_value=None)
            mock_cls.return_value = mock_instance

            result = await update_task_comment(
                issue_id=123,
                comment_id="c1",
                content="new",
                project="proj_xxx",
                work_item_type="Issue管理",
            )
            data = json.loads(result)

            assert data["success"] is True
            assert data["data"]["issue_id"] == 123
            assert data["data"]["comment_id"] == "c1"

            mock_cls.assert_called_once_with(
                project_name="proj_xxx",
                work_item_type_name="Issue管理",
            )
            mock_instance.update_comment.assert_awaited_once_with(123, "c1", "new")

    @pytest.mark.asyncio
    async def test_update_task_comment_success_project_key_branch(self):
        from src.mcp_server import update_task_comment

        with patch("src.mcp_server.CommentProvider") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.update_comment = AsyncMock(return_value=None)
            mock_cls.return_value = mock_instance

            result = await update_task_comment(
                issue_id=123,
                comment_id="c1",
                content="new",
                project="project_abc",
            )
            data = json.loads(result)

            assert data["success"] is True
            assert data["data"]["issue_id"] == 123
            assert data["data"]["comment_id"] == "c1"

            mock_cls.assert_called_once_with(project_key="project_abc")
            mock_instance.update_comment.assert_awaited_once_with(123, "c1", "new")

    @pytest.mark.asyncio
    async def test_delete_task_comment_success_project_name_branch(self):
        from src.mcp_server import delete_task_comment

        with patch("src.mcp_server.CommentProvider") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.delete_comment = AsyncMock(return_value=None)
            mock_cls.return_value = mock_instance

            result = await delete_task_comment(
                issue_id=123,
                comment_id="c1",
                project="proj_xxx",
                work_item_type="Issue管理",
            )
            data = json.loads(result)

            assert data["success"] is True
            assert data["data"]["issue_id"] == 123
            assert data["data"]["comment_id"] == "c1"

            mock_cls.assert_called_once_with(
                project_name="proj_xxx",
                work_item_type_name="Issue管理",
            )
            mock_instance.delete_comment.assert_awaited_once_with(123, "c1")

    @pytest.mark.asyncio
    async def test_delete_task_comment_success_project_key_branch(self):
        from src.mcp_server import delete_task_comment

        with patch("src.mcp_server.CommentProvider") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.delete_comment = AsyncMock(return_value=None)
            mock_cls.return_value = mock_instance

            result = await delete_task_comment(
                issue_id=123,
                comment_id="c1",
                project="project_abc",
            )
            data = json.loads(result)

            assert data["success"] is True
            assert data["data"]["issue_id"] == 123
            assert data["data"]["comment_id"] == "c1"

            mock_cls.assert_called_once_with(project_key="project_abc")
            mock_instance.delete_comment.assert_awaited_once_with(123, "c1")
