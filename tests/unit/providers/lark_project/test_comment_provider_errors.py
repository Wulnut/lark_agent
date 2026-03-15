from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.providers.lark_project.comment_provider import CommentProvider


@pytest.mark.asyncio
async def test_project_key_list_comments_meta_error_to_chinese():
    with patch(
        "src.providers.lark_project.comment_provider.MetadataManager"
    ) as mock_cls, patch("src.providers.lark_project.comment_provider.CommentAPI"):
        mock_meta = AsyncMock()
        mock_meta.get_type_key.side_effect = Exception("Some Unknown Error")
        mock_cls.get_instance.return_value = mock_meta

        provider = CommentProvider(project_key="pk", work_item_type_name="问题管理")

        with pytest.raises(Exception) as exc_info:
            await provider.list_comments(issue_id=123)

        assert "系统" in str(exc_info.value)


@pytest.mark.asyncio
async def test_default_project_key_meta_error_to_chinese(monkeypatch):
    monkeypatch.setattr(
        "src.providers.lark_project.comment_provider.settings.FEISHU_PROJECT_KEY",
        "pk_default",
    )

    with patch(
        "src.providers.lark_project.comment_provider.MetadataManager"
    ) as mock_cls, patch("src.providers.lark_project.comment_provider.CommentAPI"):
        mock_meta = AsyncMock()
        mock_meta.get_type_key.side_effect = Exception("Some Unknown Error")
        mock_cls.get_instance.return_value = mock_meta

        provider = CommentProvider(work_item_type_name="问题管理")

        with pytest.raises(Exception) as exc_info:
            await provider.list_comments(issue_id=123)

        assert "系统" in str(exc_info.value)
