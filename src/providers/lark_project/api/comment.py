"""CommentAPI - 工作项评论原子能力封装

对应 Postman 集合:
- 评论 > 创建评论: POST /open_api/:project_key/work_item/:work_item_type_key/:work_item_id/comment/create
- 评论 > 获取评论列表: GET /open_api/:project_key/work_item/:work_item_type_key/:work_item_id/comments
- 评论 > 更新评论: PUT /open_api/:project_key/work_item/:work_item_type_key/:work_item_id/comment/:comment_id
- 评论 > 删除评论: DELETE /open_api/:project_key/work_item/:work_item_type_key/:work_item_id/comment/:comment_id

说明:
- 本模块仅负责 HTTP 调用与 err_code 校验，不包含业务编排与数据清洗。
- 业务侧（Provider）负责参数默认值、可读化输出、中文错误语义等。
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from src.core.project_client import ProjectClient, get_project_client

logger = logging.getLogger(__name__)

# 安全校验：project_key / type_key / comment_id 的合法字符白名单
# 仅允许字母、数字、下划线和连字符
_SAFE_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_key(key: str, key_name: str) -> None:
    """校验 key 是否符合安全规范（防止路径遍历攻击）。"""
    if not key:
        raise ValueError(f"{key_name} 不能为空")
    if not _SAFE_KEY_PATTERN.match(key):
        raise ValueError(
            f"{key_name} 包含非法字符，仅允许字母、数字、下划线和连字符: {key[:20]}..."
        )


class CommentAPI:
    """飞书项目工作项评论 API 封装 (Data Layer)。"""

    def __init__(self, client: Optional[ProjectClient] = None):
        self.client = client or get_project_client()

    def _validate_keys(
        self,
        project_key: str,
        work_item_type_key: Optional[str] = None,
        comment_id: Optional[str] = None,
    ) -> None:
        """校验所有 key 参数的安全性。"""
        _validate_key(project_key, "project_key")
        if work_item_type_key:
            _validate_key(work_item_type_key, "work_item_type_key")
        if comment_id:
            _validate_key(comment_id, "comment_id")

    async def create(
        self,
        project_key: str,
        work_item_type_key: str,
        work_item_id: int,
        content: str,
    ) -> Dict[str, Any]:
        """创建评论。"""
        self._validate_keys(project_key, work_item_type_key)

        url = (
            f"/open_api/{project_key}/work_item/{work_item_type_key}/{work_item_id}/comment/create"
        )
        payload = {"content": content}

        logger.debug(
            "Creating comment: project_key=%s, type_key=%s, work_item_id=%s, content_len=%d",
            project_key,
            work_item_type_key,
            work_item_id,
            len(content) if content else 0,
        )

        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "创建评论失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"创建评论失败: {err_msg}")

        return data.get("data", {})

    async def list(
        self,
        project_key: str,
        work_item_type_key: str,
        work_item_id: int,
        page_size: int = 20,
        page_num: int = 1,
    ) -> Dict[str, Any]:
        """获取评论列表。"""
        self._validate_keys(project_key, work_item_type_key)

        url = f"/open_api/{project_key}/work_item/{work_item_type_key}/{work_item_id}/comments"
        params = {"page_size": page_size, "page_num": page_num}

        logger.debug(
            "Listing comments: project_key=%s, type_key=%s, work_item_id=%s, page=%d/%d",
            project_key,
            work_item_type_key,
            work_item_id,
            page_num,
            page_size,
        )

        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "获取评论列表失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"获取评论列表失败: {err_msg}")

        return data.get("data", {})

    async def update(
        self,
        project_key: str,
        work_item_type_key: str,
        work_item_id: int,
        comment_id: str,
        content: str,
    ) -> None:
        """更新评论。"""
        self._validate_keys(project_key, work_item_type_key, comment_id)

        url = (
            f"/open_api/{project_key}/work_item/{work_item_type_key}/{work_item_id}/comment/{comment_id}"
        )
        payload = {"content": content}

        logger.debug(
            "Updating comment: project_key=%s, type_key=%s, work_item_id=%s, comment_id=%s, content_len=%d",
            project_key,
            work_item_type_key,
            work_item_id,
            comment_id,
            len(content) if content else 0,
        )

        resp = await self.client.put(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "更新评论失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"更新评论失败: {err_msg}")

    async def delete(
        self,
        project_key: str,
        work_item_type_key: str,
        work_item_id: int,
        comment_id: str,
    ) -> None:
        """删除评论。"""
        self._validate_keys(project_key, work_item_type_key, comment_id)

        url = (
            f"/open_api/{project_key}/work_item/{work_item_type_key}/{work_item_id}/comment/{comment_id}"
        )

        logger.debug(
            "Deleting comment: project_key=%s, type_key=%s, work_item_id=%s, comment_id=%s",
            project_key,
            work_item_type_key,
            work_item_id,
            comment_id,
        )

        resp = await self.client.delete(url)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "删除评论失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"删除评论失败: {err_msg}")
