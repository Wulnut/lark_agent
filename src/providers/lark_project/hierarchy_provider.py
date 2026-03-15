"""HierarchyProvider - 父子/子任务（关联关系）业务编排层

职责:
- 对 RelationAPI 的原子能力做最小业务编排
- 统一 project/type 解析（复用 MetadataManager）
- relation rule 选择（relation_name -> relation_key）
- 提供父子/子任务的 list/bind/unbind 能力
- 捕获底层异常并转换为中文可读错误

注意:
- MCP 层负责 tool 注册与统一 with_error_handling。
- 本 Provider 当前最小输出：list 仅返回 work_item_ids 列表。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.core.config import settings
from src.providers.base import Provider
from src.providers.lark_project.api.relation import RelationAPI
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


class HierarchyProvider(Provider):
    """父子/子任务（关联关系）业务 Provider。"""

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

        self.api = RelationAPI()
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

    def _extract_rule_name(self, rule: Dict[str, Any]) -> Optional[str]:
        v = rule.get("name")
        if isinstance(v, str) and v.strip():
            return v.strip()
        return None

    def _extract_relation_key(self, rule: Dict[str, Any]) -> Optional[str]:
        for k in ("relation_key", "relationKey", "key"):
            v = rule.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    async def _select_relation_rule(
        self, project_key: str, relation_name: Optional[str]
    ) -> Dict[str, Any]:
        raw = await self.api.rules(project_key)
        rules = raw.get("rules") or []
        candidates: List[str] = []
        rule_by_name: Dict[str, Dict[str, Any]] = {}

        for r in rules:
            if not isinstance(r, dict):
                continue
            name = self._extract_rule_name(r)
            if not name:
                continue
            candidates.append(name)
            rule_by_name[name] = r

        if relation_name:
            name = relation_name.strip()
            if name in rule_by_name:
                return rule_by_name[name]
            raise ValueError(f"无法匹配 relation_name '{name}'，可选: {candidates}")

        if len(rule_by_name) == 1:
            only = next(iter(rule_by_name.values()))
            return only

        raise ValueError(f"存在多个关联规则，请指定 relation_name，可选: {candidates}")

    async def list_child_tasks(
        self,
        parent_issue_id: int,
        relation_name: Optional[str] = None,
        page_num: int = 1,
        page_size: int = 20,
    ) -> List[int]:
        try:
            project_key = await self._get_project_key()
            type_key = await self._get_type_key()
            rule = await self._select_relation_rule(project_key, relation_name)
            relation_key = self._extract_relation_key(rule)
            if not relation_key:
                raise ValueError("关联规则缺少 relation_key")

            raw = await self.api.work_item_list(
                project_key=project_key,
                work_item_type_key=type_key,
                work_item_id=parent_issue_id,
                page_num=page_num,
                page_size=page_size,
                relation_key=relation_key,
            )
        except ValueError:
            raise
        except Exception as e:
            raise Exception(_to_chinese_error_message(e)) from e

        return raw.get("work_item_ids") or []

    async def bind_child_tasks(
        self,
        parent_issue_id: int,
        child_issue_ids: List[int],
        relation_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            project_key = await self._get_project_key()
            type_key = await self._get_type_key()
            rule = await self._select_relation_rule(project_key, relation_name)
            relation_key = self._extract_relation_key(rule)
            if not relation_key:
                raise ValueError("关联规则缺少 relation_key")

            await self.api.batch_bind(
                project_key=project_key,
                work_item_type_key=type_key,
                work_item_id=parent_issue_id,
                relation_key=relation_key,
                work_item_ids=child_issue_ids,
            )
        except ValueError:
            raise
        except Exception as e:
            raise Exception(_to_chinese_error_message(e)) from e

        return {
            "parent_issue_id": parent_issue_id,
            "child_issue_ids": child_issue_ids,
            "relation_name": relation_name or self._extract_rule_name(rule) or "",
        }

    async def unbind_child_tasks(
        self,
        parent_issue_id: int,
        relation_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            project_key = await self._get_project_key()
            type_key = await self._get_type_key()
            rule = await self._select_relation_rule(project_key, relation_name)

            await self.api.delete(
                project_key=project_key,
                work_item_type_key=type_key,
                work_item_id=parent_issue_id,
            )
        except ValueError:
            raise
        except Exception as e:
            raise Exception(_to_chinese_error_message(e)) from e

        return {
            "parent_issue_id": parent_issue_id,
            "relation_name": relation_name or self._extract_rule_name(rule) or "",
        }
