from unittest.mock import AsyncMock, patch

import pytest

from src.providers.lark_project.comment_provider import CommentProvider


@pytest.mark.asyncio
async def test_init_with_project_key_only_resolves_type_key():
    with patch("src.providers.lark_project.comment_provider.MetadataManager") as mock_cls:
        mock_meta = AsyncMock()
        mock_meta.get_type_key.return_value = "tk"
        mock_cls.get_instance.return_value = mock_meta

        provider = CommentProvider(project_key="pk", work_item_type_name="问题管理")
        type_key = await provider._get_type_key()

        assert type_key == "tk"
        mock_meta.get_type_key.assert_awaited_once_with("pk", "问题管理")


@pytest.mark.asyncio
async def test_init_with_default_project_key_from_settings(monkeypatch):
    monkeypatch.setattr(
        "src.providers.lark_project.comment_provider.settings.FEISHU_PROJECT_KEY",
        "pk_default",
    )

    with patch("src.providers.lark_project.comment_provider.MetadataManager") as mock_cls, patch(
        "src.providers.lark_project.comment_provider.CommentAPI"
    ) as mock_api_cls:
        mock_meta = AsyncMock()
        mock_meta.get_type_key.return_value = "tk"
        mock_cls.get_instance.return_value = mock_meta

        mock_api = AsyncMock()
        mock_api.create.return_value = {"comment_id": "c1"}
        mock_api_cls.return_value = mock_api

        provider = CommentProvider(work_item_type_name="问题管理")
        result = await provider.add_comment(issue_id=123, content="hello")

        assert result["comment_id"] == "c1"
        mock_api.create.assert_awaited_once()
