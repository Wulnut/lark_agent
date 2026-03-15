"""CommentProvider - 工作项评论业务编排层

职责:
- 对 CommentAPI 的原子能力做最小业务编排
- 统一 project/type 解析（复用 MetadataManager）
- 输出精简、可读的评论结构，减少上层 token 消耗
- 捕获底层异常并转换为中文可读错误

注意:
- MCP 层负责 tool 注册与统一 with_error_handling。
- 本 Provider 不做富文本（rich_text/doc_rich_text）处理，本期仅支持纯文本 content。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.core.config import settings
from src.providers.base import Provider
from src.providers.lark_project.api.comment import CommentAPI
from src.providers.lark_project.managers import MetadataManager

logger = logging.getLogger(__name__)


def _to_chinese_error_message(exc: Exception) -> str:
    """将底层异常转换为中文可读错误消息。"""
    msg = str(exc)
    if not msg:
        return "未知错误"

    # 简单网络错误识别（避免直接暴露英文 Network Error）
    if "Network" in msg or "network" in msg or "Connection" in msg or "Timeout" in msg:
        return "网络请求失败"

    # 若消息中几乎没有中文且包含英文/ASCII 字母，则返回统一中文错误
    has_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in msg)
    has_ascii_alpha = any(ch.isascii() and ch.isalpha() for ch in msg)
    if has_ascii_alpha and not has_chinese:
        return "系统内部错误"

    return msg


class CommentProvider(Provider):
    """评论业务 Provider。"""

    def __init__(
        self,
        project_name: Optional[str] = None,
        project_key: Optional[str] = None,
        work_item_type_name: str = "问题管理",
    ):
        if not project_name and not project_key:
            if settings.FEISHU_PROJECT_KEY:
                project_key = settings.FEISHU_PROJECT_KEY
            else:
                raise ValueError(
                    "必须提供 project_name 或 project_key，或设置 FEISHU_PROJECT_KEY 环境变量"
                )

        self.project_name = project_name
        self._project_key = project_key
        self.work_item_type_name = work_item_type_name

        self.api = CommentAPI()
        self.meta = MetadataManager.get_instance()

        self._resolved_type_key: Optional[str] = None

    async def _get_project_key(self) -> str:
        if not self._project_key:
            if self.project_name:
                self._project_key = await self.meta.get_project_key(self.project_name)
            else:
                raise ValueError("无法解析项目 project_key，请检查 project_name/project_key 是否正确")
        return self._project_key

    async def _get_type_key(self) -> str:
        if self._resolved_type_key is not None:
            return self._resolved_type_key

        project_key = await self._get_project_key()
        self._resolved_type_key = await self.meta.get_type_key(
            project_key, self.work_item_type_name
        )
        return self._resolved_type_key

    async def add_comment(self, issue_id: int, content: str) -> Dict[str, Any]:
        if not content or not content.strip():
            raise ValueError("评论内容不能为空")

        try:
            project_key = await self._get_project_key()
            type_key = await self._get_type_key()

            logger.info(
                "Adding comment: project_key=%s, type_key=%s, issue_id=%s, content_len=%d",
                project_key,
                type_key,
                issue_id,
                len(content),
            )

            raw = await self.api.create(
                project_key=project_key,
                work_item_type_key=type_key,
                work_item_id=issue_id,
                content=content,
            )
        except Exception as e:
            raise Exception(_to_chinese_error_message(e)) from e

        return {
            "comment_id": raw.get("comment_id")
            or raw.get("id")
            or raw.get("commentId")
            or raw.get("commentID")
        }

    async def list_comments(
        self,
        issue_id: int,
        page_num: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        try:
            project_key = await self._get_project_key()
            type_key = await self._get_type_key()

            raw = await self.api.list(
                project_key=project_key,
                work_item_type_key=type_key,
                work_item_id=issue_id,
                page_num=page_num,
                page_size=page_size,
            )
        except Exception as e:
            raise Exception(_to_chinese_error_message(e)) from e

        items = raw.get("items") or raw.get("comments") or []
        simplified: List[Dict[str, Any]] = []

        for c in items:
            simplified.append(
                {
                    "comment_id": c.get("comment_id")
                    or c.get("id")
                    or c.get("commentId"),
                    "author": c.get("author")
                    or c.get("creator")
                    or c.get("user"),
                    "create_time": c.get("create_time")
                    or c.get("created_at")
                    or c.get("createTime"),
                    "content": c.get("content") or c.get("text") or c.get("body"),
                }
            )

        return {
            "total": raw.get("total", len(simplified)),
            "page_num": page_num,
            "page_size": page_size,
            "items": simplified,
        }

    async def update_comment(self, issue_id: int, comment_id: str, content: str) -> None:
        if not content or not content.strip():
            raise ValueError("评论内容不能为空")

        try:
            project_key = await self._get_project_key()
            type_key = await self._get_type_key()

            await self.api.update(
                project_key=project_key,
                work_item_type_key=type_key,
                work_item_id=issue_id,
                comment_id=comment_id,
                content=content,
            )
        except Exception as e:
            raise Exception(_to_chinese_error_message(e)) from e

    async def delete_comment(self, issue_id: int, comment_id: str) -> None:
        try:
            project_key = await self._get_project_key()
            type_key = await self._get_type_key()

            await self.api.delete(
                project_key=project_key,
                work_item_type_key=type_key,
                work_item_id=issue_id,
                comment_id=comment_id,
            )
        except Exception as e:
            raise Exception(_to_chinese_error_message(e)) from e
