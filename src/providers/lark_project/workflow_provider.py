"""WorkflowProvider - 工作项工作流业务编排层

职责:
- 对 WorkflowAPI 的原子能力做最小业务编排
- 统一 project/type 解析（复用 MetadataManager）
- 将人类输入的目标状态名 target_status 解析为 state_key 与 transition_id
- 提供状态流转前必填信息查询与执行流转能力
- 捕获底层异常并转换为中文可读错误

注意:
- MCP 层负责 tool 注册与统一 with_error_handling。
- 本 Provider 当前仅支持 fields: list[dict] 透传（不做 FieldResolver 复杂解析）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from src.core.config import settings
from src.providers.base import Provider
from src.providers.lark_project.api.workflow import WorkflowAPI
from src.providers.lark_project.managers import MetadataManager

logger = logging.getLogger(__name__)


def _to_chinese_error_message(exc: Exception) -> str:
    """将底层异常转换为中文可读错误消息。"""

    msg = str(exc)
    if not msg:
        return "未知错误"

    if "Network" in msg or "network" in msg or "Connection" in msg or "Timeout" in msg:
        return "网络请求失败"

    has_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in msg)
    has_ascii_alpha = any(ch.isascii() and ch.isalpha() for ch in msg)
    if has_ascii_alpha and not has_chinese:
        return "系统内部错误"

    return msg


class WorkflowProvider(Provider):
    """工作流业务 Provider。"""

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

        self.api = WorkflowAPI()
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
        self._resolved_type_key = await self.meta.get_type_key(project_key, self.work_item_type_name)
        return self._resolved_type_key

    def _extract_state_name(self, state: Dict[str, Any]) -> Optional[str]:
        for key in ("name", "state_name", "label"):
            v = state.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    def _extract_state_key(self, state: Dict[str, Any]) -> Optional[str]:
        for key in ("state_key", "key", "stateKey"):
            v = state.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    def _extract_transition_id(self, transition: Dict[str, Any]) -> Optional[str]:
        for key in ("transition_id", "id", "transitionId"):
            v = transition.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    def _extract_transition_to_state_key(self, transition: Dict[str, Any]) -> Optional[str]:
        for key in ("to_state_key", "to_state", "toStateKey", "toState"):
            v = transition.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    async def _resolve_state_and_transition(
        self,
        issue_id: int,
        target_status: str,
    ) -> Tuple[str, str, List[str]]:
        """解析 target_status -> (state_key, transition_id, available_state_names)。"""

        project_key = await self._get_project_key()
        type_key = await self._get_type_key()

        wf = await self.api.query_work_item_workflow(
            project_key=project_key,
            work_item_type_key=type_key,
            work_item_id=issue_id,
        )

        states = wf.get("states") or []
        transitions = wf.get("transitions") or []

        available_names: List[str] = []
        matched_state_key: Optional[str] = None

        t = target_status.strip() if target_status else ""
        if not t:
            raise ValueError("target_status 不能为空")

        for s in states:
            if not isinstance(s, dict):
                continue
            name = self._extract_state_name(s)
            if name:
                available_names.append(name)
            if name == t:
                matched_state_key = self._extract_state_key(s)

        if not matched_state_key:
            raise ValueError(
                f"无法匹配目标状态 '{t}'。可选状态: {available_names}"
            )

        matched_transition_id: Optional[str] = None
        for tr in transitions:
            if not isinstance(tr, dict):
                continue
            if self._extract_transition_to_state_key(tr) == matched_state_key:
                matched_transition_id = self._extract_transition_id(tr)
                if matched_transition_id:
                    break

        if not matched_transition_id:
            # transitions 缺失时，仍给出可读错误（后续可扩展为根据当前状态推导）
            raise ValueError(
                f"无法找到流转到状态 '{t}' 的 transition_id。可选状态: {available_names}"
            )

        return matched_state_key, matched_transition_id, available_names

    async def get_transition_requirements(
        self,
        issue_id: int,
        target_status: str,
        mode: str = "",
    ) -> Dict[str, Any]:
        """查询将工作项流转到 target_status 前，服务端要求填写的必填信息。"""

        try:
            project_key = await self._get_project_key()
            type_key = await self._get_type_key()
            state_key, _, _ = await self._resolve_state_and_transition(
                issue_id=issue_id,
                target_status=target_status,
            )

            raw = await self.api.get_transition_required_info(
                project_key=project_key,
                work_item_type_key=type_key,
                work_item_id=issue_id,
                state_key=state_key,
                mode=mode,
            )
        except ValueError:
            raise
        except Exception as e:
            raise Exception(_to_chinese_error_message(e)) from e

        # 当前最小实现：至少 required_fields 原样透传
        return {
            "required_fields": raw.get("required_fields") or [],
        }

    async def transition_task_status(
        self,
        issue_id: int,
        target_status: str,
        fields: Optional[List[Dict[str, Any]]] = None,
        mode: str = "",
    ) -> Dict[str, Any]:
        """执行工作项状态流转。"""

        try:
            project_key = await self._get_project_key()
            type_key = await self._get_type_key()
            _, transition_id, _ = await self._resolve_state_and_transition(
                issue_id=issue_id,
                target_status=target_status,
            )

            payload_fields = fields or []

            logger.info(
                "Transition work item: project_key=%s, type_key=%s, issue_id=%s, target_status=%s, transition_id=%s, fields_count=%d, mode=%s",
                project_key,
                type_key,
                issue_id,
                target_status,
                transition_id,
                len(payload_fields),
                mode,
            )

            await self.api.state_change(
                project_key=project_key,
                work_item_type_key=type_key,
                work_item_id=issue_id,
                transition_id=transition_id,
                fields=payload_fields,
            )
        except ValueError:
            raise
        except Exception as e:
            raise Exception(_to_chinese_error_message(e)) from e

        return {
            "issue_id": issue_id,
            "target_status": target_status,
        }
