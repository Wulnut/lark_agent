"""RelationAPI - 工作项关联原子能力封装

对应 Open API:
- 获取关联规则: POST /open_api/:project_key/relation/rules
- 获取关联工作项列表: POST /open_api/:project_key/relation/:work_item_type_key/:work_item_id/work_item_list
- 批量绑定关联: POST /open_api/:project_key/relation/:work_item_type_key/:work_item_id/batch_bind
- 删除关联: DELETE /open_api/:project_key/relation/:work_item_type_key/:work_item_id

说明:
- 本模块仅负责 HTTP 调用与 err_code 校验，不包含业务编排与数据清洗。
- 业务侧（Provider）负责参数默认值、可读化输出、中文错误语义等。
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from src.core.project_client import ProjectClient, get_project_client

logger = logging.getLogger(__name__)

# 安全校验：project_key / type_key / relation_key 的合法字符白名单
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


class RelationAPI:
    """飞书项目工作项关联 API 封装 (Data Layer)。"""

    def __init__(self, client: Optional[ProjectClient] = None):
        self.client = client or get_project_client()

    def _validate_keys(
        self,
        project_key: str,
        work_item_type_key: Optional[str] = None,
        relation_key: Optional[str] = None,
    ) -> None:
        """校验所有 key 参数的安全性。"""
        _validate_key(project_key, "project_key")
        if work_item_type_key:
            _validate_key(work_item_type_key, "work_item_type_key")
        if relation_key:
            _validate_key(relation_key, "relation_key")

    async def rules(self, project_key: str) -> Dict[str, Any]:
        """获取关联规则。"""
        self._validate_keys(project_key)

        url = f"/open_api/{project_key}/relation/rules"
        payload: Dict[str, Any] = {}

        logger.debug("Getting relation rules: project_key=%s", project_key)

        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "获取关联规则失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"获取关联规则失败: {err_msg}")

        return data.get("data", {})

    async def work_item_list(
        self,
        project_key: str,
        work_item_type_key: str,
        work_item_id: int,
        page_num: int = 1,
        page_size: int = 20,
        relation_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取关联工作项列表。"""
        self._validate_keys(project_key, work_item_type_key, relation_key)

        url = f"/open_api/{project_key}/relation/{work_item_type_key}/{work_item_id}/work_item_list"
        payload: Dict[str, Any] = {"page_num": page_num, "page_size": page_size}
        if relation_key:
            payload["relation_key"] = relation_key

        logger.debug(
            "Getting related work items: project_key=%s, type_key=%s, id=%s, page=%d/%d, relation_key=%s",
            project_key,
            work_item_type_key,
            work_item_id,
            page_num,
            page_size,
            relation_key,
        )

        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "获取关联工作项列表失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"获取关联工作项列表失败: {err_msg}")

        return data.get("data", {})

    async def batch_bind(
        self,
        project_key: str,
        work_item_type_key: str,
        work_item_id: int,
        relation_key: str,
        work_item_ids: List[int],
    ) -> Dict[str, Any]:
        """批量绑定关联。"""
        self._validate_keys(project_key, work_item_type_key, relation_key)

        url = f"/open_api/{project_key}/relation/{work_item_type_key}/{work_item_id}/batch_bind"
        payload = {"relation_key": relation_key, "work_item_ids": work_item_ids}

        logger.debug(
            "Batch binding relation: project_key=%s, type_key=%s, id=%s, relation_key=%s, ids_count=%d",
            project_key,
            work_item_type_key,
            work_item_id,
            relation_key,
            len(work_item_ids),
        )

        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "批量绑定关联失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"批量绑定关联失败: {err_msg}")

        return data.get("data", {})

    async def delete(self, project_key: str, work_item_type_key: str, work_item_id: int) -> None:
        """删除关联。"""
        self._validate_keys(project_key, work_item_type_key)

        url = f"/open_api/{project_key}/relation/{work_item_type_key}/{work_item_id}"

        logger.debug(
            "Deleting relation: project_key=%s, type_key=%s, id=%s",
            project_key,
            work_item_type_key,
            work_item_id,
        )

        resp = await self.client.delete(url)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "删除关联失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"删除关联失败: {err_msg}")
