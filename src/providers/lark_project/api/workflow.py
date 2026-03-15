"""WorkflowAPI - 工作项工作流运行时原子能力封装

对应 Postman 集合:
- 工作流 > 查询工作项工作流信息: POST /open_api/:project_key/work_item/:work_item_type_key/:work_item_id/workflow/query
- 工作流 > 获取流转前必填信息: POST /open_api/work_item/transition_required_info/get
- 工作流 > 状态流转: POST /open_api/:project_key/workflow/:work_item_type_key/:work_item_id/node/state_change

说明:
- 本模块仅负责 HTTP 调用与 err_code 校验，不包含业务编排与数据清洗。
- 业务侧（Provider）负责状态名匹配、字段解析、中文错误语义等。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.core.project_client import ProjectClient, get_project_client

logger = logging.getLogger(__name__)


class WorkflowAPI:
    """飞书项目工作流运行时 API 封装 (Data Layer)。"""

    def __init__(self, client: Optional[ProjectClient] = None):
        self.client = client or get_project_client()

    async def query_work_item_workflow(
        self,
        project_key: str,
        work_item_type_key: str,
        work_item_id: int,
    ) -> Dict[str, Any]:
        """获取指定工作项的 workflow/runtime 信息。"""
        url = f"/open_api/{project_key}/work_item/{work_item_type_key}/{work_item_id}/workflow/query"

        resp = await self.client.post(url)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "获取工作项工作流信息失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"获取工作项工作流信息失败: {err_msg}")

        return data.get("data", {})

    async def get_transition_required_info(
        self,
        project_key: str,
        work_item_type_key: str,
        work_item_id: int,
        state_key: str,
        mode: str = "",
    ) -> Dict[str, Any]:
        """获取流转前必填信息。"""
        url = "/open_api/work_item/transition_required_info/get"
        payload = {
            "project_key": project_key,
            "work_item_type_key": work_item_type_key,
            "work_item_id": work_item_id,
            "state_key": state_key,
            "mode": mode,
        }

        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "获取流转必填信息失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"获取流转必填信息失败: {err_msg}")

        return data.get("data", {})

    async def state_change(
        self,
        project_key: str,
        work_item_type_key: str,
        work_item_id: int,
        transition_id: str,
        fields: List[Dict[str, Any]],
        role_owners: Optional[Dict[str, Any]] = None,
    ) -> None:
        """执行状态流转。"""
        url = f"/open_api/{project_key}/workflow/{work_item_type_key}/{work_item_id}/node/state_change"
        payload: Dict[str, Any] = {
            "transition_id": transition_id,
            "fields": fields,
            "role_owners": role_owners,
        }

        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "状态流转失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"状态流转失败: {err_msg}")
