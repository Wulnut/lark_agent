import asyncio
import logging
import random
from typing import Any, Dict, List, Optional, Set, Tuple, Union, NamedTuple

import httpx

from src.core.cache import SimpleCache
from src.core.config import settings
from src.providers.base import Provider
from src.providers.lark_project.api.work_item import WorkItemAPI
from src.providers.lark_project.api.user import UserAPI
from src.providers.lark_project.managers import MetadataManager
from src.providers.lark_project.field_resolver import (
    FieldResolver,
)

logger = logging.getLogger(__name__)


# 定义一个 NamedTuple 来存储每个更新操作的结果
class UpdateResult(NamedTuple):
    success: bool
    issue_id: int
    field_name: str
    message: str
    field_value: Any = None  # 添加 field_value 字段，用于记录尝试更新的值


class WorkItemProvider(Provider):
    """
    工作项业务逻辑提供者 (Service/Provider Layer)
    串联 MetadataManager 和 WorkItemAPI，提供人性化的接口

    设计说明:
    - 使用 MetadataManager 实现零硬编码: 所有 Key/Value 通过名称动态解析
    - 使用 WorkItemAPI 执行原子操作
    - 支持从环境变量 FEISHU_PROJECT_KEY 读取默认项目
    """

    # 类常量：缓存中"未找到"的标记值
    _NOT_FOUND_MARKER: str = "__NOT_FOUND__"

    # 扫描配置常量（用于 related_to 客户端过滤）
    _SCAN_MAX_TOTAL_ITEMS: int = 500  # 最多扫描的记录数
    _SCAN_MAX_PAGES: int = 10  # 最多扫描的页数
    _SCAN_BATCH_SIZE: int = 50  # 每批记录数
    _SCAN_CONCURRENT_PAGES: int = 3  # 每次并发请求的页数

    # 负责人字段的候选名称列表（按优先级排序）
    _OWNER_FIELD_CANDIDATES: Tuple[str, ...] = (
        "owner",
        "当前负责人",
        "负责人",
        "经办人",
        "Assignee",
    )

    def __init__(
        self,
        project_name: Optional[str] = None,
        project_key: Optional[str] = None,
        work_item_type_name: str = "问题管理",
    ):
        # 优先使用显式传入的参数，否则使用环境变量配置
        if not project_name and not project_key:
            if settings.FEISHU_PROJECT_KEY:
                project_key = settings.FEISHU_PROJECT_KEY
            else:
                raise ValueError(
                    "Must provide either project_name or project_key, "
                    "or set FEISHU_PROJECT_KEY environment variable"
                )

        self.project_name = project_name
        self._project_key = project_key
        self.work_item_type_name = work_item_type_name
        self.api = WorkItemAPI()
        self.user_api = UserAPI()
        self.meta = MetadataManager.get_instance()

        # 线程安全：用于保护类型 Key 解析的锁和缓存
        self._type_key_lock = asyncio.Lock()
        self._resolved_type_key: Optional[str] = None

        # 缓存配置
        # 用户ID到姓名的缓存，TTL 10分钟（600秒）
        self._user_cache = SimpleCache(ttl=600)
        # 工作项ID到名称的缓存，TTL 5分钟（300秒）
        self._work_item_cache = SimpleCache(ttl=300)

        # 限制并发 API 请求数量，防止触发 429 频控 (15 QPS 限制)
        self._api_semaphore = asyncio.Semaphore(2)

        # 初始化抽取的子模块（P0-P2 重构）
        self.field_resolver = FieldResolver(self.meta)

    async def _get_project_key(self) -> str:
        if not self._project_key:
            if self.project_name:
                self._project_key = await self.meta.get_project_key(self.project_name)
            else:
                raise ValueError("Project key not resolved")
        return self._project_key

    async def _get_type_key(self) -> str:
        """
        获取工作项类型 Key（线程安全）

        使用锁保护状态检查和修改，避免竞态条件。
        当指定的类型不存在时，如果使用的是默认类型 "问题管理"，
        会自动 fallback 到项目中的第一个可用类型。

        Returns:
            工作项类型 Key

        Raises:
            ValueError: 当类型不存在且无法 fallback 时
        """
        async with self._type_key_lock:
            # 快速路径：已解析过则直接返回缓存
            if self._resolved_type_key is not None:
                return self._resolved_type_key

            project_key = await self._get_project_key()

            try:
                self._resolved_type_key = await self.meta.get_type_key(
                    project_key, self.work_item_type_name
                )
                return self._resolved_type_key
            except (ValueError, KeyError) as e:
                # 仅当使用默认类型 "问题管理" 时才尝试 fallback
                if self.work_item_type_name != "问题管理":
                    raise

                types = await self.meta.list_types(project_key)
                if not types:
                    raise ValueError(
                        f"项目 {project_key} 中没有可用的工作项类型"
                    ) from e

                # 使用 items() 同时获取 key 和 value，更 Pythonic
                first_type_name, first_type_key = next(iter(types.items()))
                logger.warning(
                    "默认类型 '问题管理' 不存在，临时使用 '%s' 替代",
                    first_type_name,
                )
                # 缓存解析结果，避免后续调用再次触发 fallback
                self._resolved_type_key = first_type_key
                return self._resolved_type_key

    async def _field_exists(
        self, project_key: str, type_key: str, field_name: str
    ) -> bool:
        """
        检查字段是否存在（不抛异常）

        Args:
            project_key: 项目空间 Key
            type_key: 工作项类型 Key
            field_name: 字段名称

        Returns:
            True: 字段存在
            False: 字段不存在
        """
        try:
            await self.meta.get_field_key(project_key, type_key, field_name)
            return True
        except (ValueError, KeyError) as e:
            logger.debug("Field '%s' not found: %s", field_name, e)
            return False

    def _is_item_related_to(self, item: Dict[str, Any], related_to: int) -> bool:
        """
        检查工作项是否与指定 ID 关联（DRY 辅助方法）

        Args:
            item: 工作项字典
            related_to: 关联的工作项 ID

        Returns:
            True: 关联，False: 不关联
        """
        for field in item.get("fields", []):
            field_value = field.get("field_value")
            if not field_value:
                continue
            if isinstance(field_value, list):
                if related_to in field_value:
                    return True
            elif field_value == related_to:
                return True
        return False

    def _normalize_api_result(
        self,
        result: Union[List, Dict, Any],
        page_num: int,
        page_size: int,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        标准化 API 返回结果（DRY 辅助方法）

        处理 API 可能返回列表或字典的情况，统一转换为 (items, pagination) 元组。

        Args:
            result: API 原始返回结果
            page_num: 请求的页码
            page_size: 请求的每页数量

        Returns:
            (items, pagination) 元组
        """
        if isinstance(result, list):
            items = result
            pagination = {
                "total": len(result),
                "page_num": page_num,
                "page_size": page_size,
            }
            logger.debug("API returned list format, converted to standard format")
        elif isinstance(result, dict):
            items = result.get("work_items", [])
            pagination = result.get("pagination", {})
            # 如果 pagination 不是字典，创建默认的
            if not isinstance(pagination, dict):
                pagination = {
                    "total": result.get("total", len(items)),
                    "page_num": page_num,
                    "page_size": page_size,
                }
        else:
            logger.warning(
                "Unexpected result type: %s, value: %s", type(result), result
            )
            items = []
            pagination = {
                "total": 0,
                "page_num": page_num,
                "page_size": page_size,
            }
        return items, pagination

    async def _resolve_owner_field_key(self, project_key: str, type_key: str) -> str:
        """
        动态解析负责人字段 Key（DRY 辅助方法）

        尝试按优先级顺序匹配候选字段名称。

        Args:
            project_key: 项目 Key
            type_key: 工作项类型 Key

        Returns:
            负责人字段 Key，默认为 "owner"
        """
        for candidate in self._OWNER_FIELD_CANDIDATES:
            try:
                key = await self.meta.get_field_key(project_key, type_key, candidate)
                if key:
                    logger.debug(
                        "Resolved owner field key to: %s ('%s')", key, candidate
                    )
                    return key
            except Exception:
                continue
        return "owner"  # 默认值

    async def _build_filter_condition(
        self,
        project_key: str,
        type_key: str,
        field_name: str,
        values: List[str],
    ) -> Optional[Dict[str, Any]]:
        """
        构建单个字段的过滤条件（DRY 辅助方法）

        将人类可读的字段值转换为 API 所需的过滤条件结构。

        Args:
            project_key: 项目 Key
            type_key: 工作项类型 Key
            field_name: 字段名称（如 "status", "priority"）
            values: 字段值列表

        Returns:
            过滤条件字典，如果字段不存在则返回 None
        """
        if not await self._field_exists(project_key, type_key, field_name):
            logger.warning(
                "Field '%s' not found in project, skipping filter", field_name
            )
            return None

        field_key = await self.meta.get_field_key(project_key, type_key, field_name)
        resolved_values = []

        for v in values:
            try:
                val = await self._resolve_field_value(project_key, type_key, field_key, v)
                resolved_values.append(val)
            except Exception as e:
                logger.warning("Failed to resolve %s '%s': %s", field_name, v, e)
                resolved_values.append(v)

        logger.info("Added %s filter: %s", field_name, values)
        return {
            "field_key": field_key,
            "operator": "IN",
            "value": resolved_values,
        }

    async def _build_owner_filter_condition(
        self,
        project_key: str,
        type_key: str,
        owner: str,
    ) -> Optional[Dict[str, Any]]:
        """
        构建负责人过滤条件（DRY 辅助方法）

        Args:
            project_key: 项目 Key
            type_key: 工作项类型 Key
            owner: 负责人（姓名或邮箱）

        Returns:
            过滤条件字典，如果解析失败则返回 None
        """
        try:
            user_key = await self.meta.get_user_key(owner)
            owner_field_key = await self._resolve_owner_field_key(project_key, type_key)
            logger.info("Added owner filter: %s (field_key=%s)", owner, owner_field_key)
            return {
                "field_key": owner_field_key,
                "operator": "IN",
                "value": [user_key],
            }
        except Exception as e:
            logger.warning(
                "Failed to resolve owner '%s': %s, skipping owner filter", owner, e
            )
            return None

    def _parse_raw_field_value(self, value: Any) -> Optional[str]:
        """
        解析原始字段值为可读字符串（DRY 辅助方法）

        Args:
            value: 原始字段值，可以是 dict、list 或其他类型

        Returns:
            解析后的字符串值，如果无法解析则返回 None
        """
        if value is None:
            return None
        # 选项类型字段: {label: "...", value: "..."}
        if isinstance(value, dict):
            return value.get("label") or value.get("value")
        # 用户类型字段: [{name: "...", name_cn: "..."}]
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value[0].get("name") or value[0].get("name_cn")
        # 其他类型: 转为字符串
        return str(value) if value else None

    def _extract_field_value(self, item: dict, field_key: str) -> Optional[str]:
        """
        从工作项中提取字段值

        支持两种数据结构：
        1. fields: 新版结构，字段以对象列表形式存在
        2. field_value_pairs: 旧版结构，字段以键值对列表形式存在

        Args:
            item: 工作项字典
            field_key: 字段 Key

        Returns:
            字段值（字符串），如果不存在则返回 None
        """
        # 优先从 fields 数组查找
        field = next(
            (f for f in item.get("fields", []) if f.get("field_key") == field_key),
            None,
        )
        if field:
            return self._parse_raw_field_value(field.get("field_value"))

        # 回退到 field_value_pairs
        pair = next(
            (
                p
                for p in item.get("field_value_pairs", [])
                if p.get("field_key") == field_key
            ),
            None,
        )
        if pair:
            return self._parse_raw_field_value(pair.get("field_value"))

        logger.debug(
            "Field key '%s' not found in item id=%s", field_key, item.get("id")
        )
        return None

    async def simplify_work_item(
        self, item: dict, field_mapping: Optional[Dict[str, str]] = None
    ) -> dict:
        """
        将工作项简化为摘要格式，减少 Token 消耗

        Args:
            item: 原始工作项字典
            field_mapping: 字段名称到字段Key的映射（可选）

        Returns:
            简化后的工作项字典，包含 id, name, status, priority, owner
        """

        # 使用field_mapping获取实际的字段Key，如果没有映射则使用字段名称作为Key
        def get_field_key(field_name: str) -> str:
            if field_mapping and field_name in field_mapping:
                return field_mapping[field_name]
            return field_name

        priority_key = get_field_key("priority")
        priority_raw = self._extract_field_value(item, priority_key)
        # 脱敏处理：截断优先级值
        priority_value = priority_raw[:20] if priority_raw else None

        return {
            "id": item.get("id"),
            "name": item.get("name"),
            "status": self._extract_field_value(item, get_field_key("status")),
            "priority": priority_value,
            "owner": self._extract_field_value(item, get_field_key("owner")),
        }

    async def simplify_work_items(
        self, items: List[dict], field_mapping: Optional[Dict[str, str]] = None
    ) -> List[dict]:
        """
        批量简化工作项列表

        Args:
            items: 原始工作项列表
            field_mapping: 字段名称到字段Key的映射（可选）

        Returns:
            简化后的工作项列表，owner 字段会转换为人名以提高可读性
        """
        logger.info("simplify_work_items: processing %d items", len(items))
        if items:
            logger.info("First item keys: %s", list(items[0].keys()))
            if "fields" in items[0]:
                fields = items[0].get("fields", [])
                logger.info(
                    "First item fields count: %d, field_keys: %s",
                    len(fields),
                    [f.get("field_key") for f in fields],
                )
        # 并行简化所有工作项
        tasks = [self.simplify_work_item(item, field_mapping) for item in items]
        simplified_items = await asyncio.gather(*tasks)

        # 批量转换 owner user_key 为人名
        owner_keys = []
        for item in simplified_items:
            owner = item.get("owner")
            if owner and isinstance(owner, str):
                # 检查是否是 user_key 格式（长数字字符串）
                if owner.isdigit() and len(owner) > 10:
                    owner_keys.append(owner)

        if owner_keys:
            # 去重
            unique_keys = list(set(owner_keys))
            logger.info("Converting %d unique owner keys to names", len(unique_keys))
            try:
                key_to_name = await self.meta.batch_get_user_names(unique_keys)
                # 替换 owner 字段
                for item in simplified_items:
                    owner = item.get("owner")
                    if owner and owner in key_to_name:
                        item["owner"] = key_to_name[owner]
            except Exception as e:
                logger.warning("Failed to convert owner keys to names: %s", e)
                # 失败时保持原样，不影响正常返回

        return simplified_items

    async def resolve_related_to(
        self, related_to: Union[int, str], project: Optional[str] = None
    ) -> int:
        """
        解析 related_to 参数，将名称转换为工作项 ID

        支持三种输入方式：
        1. 整数: 直接返回
        2. 数字字符串: 转换为整数返回
        3. 非数字字符串: 在多个工作项类型中并行搜索，返回匹配的 ID

        Args:
            related_to: 工作项 ID 或名称
            project: 项目标识符（可选），用于名称搜索

        Returns:
            工作项 ID

        Raises:
            ValueError: 未找到匹配的工作项
        """
        # 整数: 直接返回
        if isinstance(related_to, int):
            logger.info("resolve_related_to: 直接使用整数 ID: %s", related_to)
            return related_to

        # 字符串处理
        if isinstance(related_to, str):
            # 数字字符串: 转换为整数
            if related_to.isdigit():
                result = int(related_to)
                logger.info("resolve_related_to: 字符串转整数 ID: %s", result)
                return result

            # 非数字字符串: 按名称并行搜索
            logger.info("resolve_related_to: 按名称并行搜索 '%s'", related_to)

            # 在常见工作项类型中搜索
            search_types = [
                "项目管理",
                "需求管理",
                "Issue管理",
                "任务",
                "Epic",
                "事务管理",
            ]

            async def search_single_type(search_type: str) -> Tuple[str, List[dict]]:
                """搜索单个工作项类型，返回 (类型名, 结果列表)"""
                try:
                    temp_provider = WorkItemProvider(
                        project_name=self.project_name,
                        project_key=self._project_key,
                        work_item_type_name=search_type,
                    )
                    search_result = await temp_provider.get_tasks(
                        name_keyword=related_to, page_num=1, page_size=5
                    )
                    return (search_type, search_result.get("items", []))
                except Exception as e:
                    logger.debug(
                        "resolve_related_to: 在类型 '%s' 中搜索失败: %s",
                        search_type,
                        e,
                    )
                    return (search_type, [])

            # 并行搜索所有类型
            results = await asyncio.gather(
                *(search_single_type(t) for t in search_types)
            )

            # 处理结果：优先精确匹配，其次部分匹配
            candidates: List[Tuple[dict, str]] = []

            for search_type, items in results:
                for item in items:
                    item_name = item.get("name")
                    if item_name == related_to:
                        # 发现精确匹配，直接返回
                        logger.info(
                            "resolve_related_to: 精确匹配 '%s' (ID: %s, Type: %s)",
                            item_name,
                            item.get("id"),
                            search_type,
                        )
                        return item.get("id")

                    # 收集部分匹配作为候选
                    candidates.append((item, search_type))

            # 如果没有精确匹配，检查候选者
            if candidates:
                best_match, match_type = candidates[0]
                logger.info(
                    "resolve_related_to: 部分匹配 '%s' (ID: %s, Type: %s)",
                    best_match.get("name"),
                    best_match.get("id"),
                    match_type,
                )
                return best_match.get("id")

            raise ValueError(f"未找到名称为 '{related_to}' 的工作项")

        # 其他类型: 尝试转换
        try:
            result = int(related_to)
            logger.info("resolve_related_to: 类型转换 ID: %s", result)
            return result
        except (ValueError, TypeError):
            raise ValueError(
                f"related_to 必须是工作项 ID（整数）或名称（字符串），当前类型: {type(related_to)}"
            )

    async def _resolve_field_value(
        self, project_key: str, type_key: str, field_key: str, value: Any
    ) -> Any:
        """解析字段值：如果是 Select 类型且值为 Label，转换为 Option Value（纯字符串）

        用于搜索/过滤 API，需要纯 value 字符串。

        Args:
            project_key: 项目空间 Key
            type_key: 工作项类型 Key
            field_key: 字段 Key
            value: 输入值（可以是 label 或 value）

        Returns:
            选项的 value 字符串，或原值（非选择类型）
        """
        try:
            option_value = await self.meta.get_option_value(
                project_key, type_key, field_key, str(value)
            )
            logger.info(
                "Resolved option '%s' -> '%s' for field '%s'",
                value,
                option_value,
                field_key,
            )
            return option_value
        except Exception as e:
            logger.warning(
                "Failed to resolve option '%s' for field '%s': %s",
                value,
                field_key,
                e,
            )
            return value  # Fallback: 非选择类型字段直接返回原值

    async def _resolve_field_value_for_update(
        self, project_key: str, type_key: str, field_key: str, value: Any
    ) -> Any:
        """解析字段值用于更新 API：转换为 {label, value} 结构"""
        # 特殊处理：针对 multi_select 字段，如果值为空（None 或空字符串），返回空列表 []
        # 这允许通过 API 清空多选字段，同时也避免了对 "" 进行选项查询导致的报错
        try:
            field_type = await self.meta.get_field_type(
                project_key, type_key, field_key
            )
            if field_type == "multi_select" and (
                value is None or (isinstance(value, str) and not value.strip())
            ):
                logger.info(
                    "Empty value for multi_select field '%s', returning []", field_key
                )
                return []
        except Exception as e:
            logger.debug(
                "Failed to get field type in _resolve_field_value_for_update: %s", e
            )

        # 处理列表 (多选)
        if isinstance(value, list):
            results = []
            for item in value:
                # 递归调用处理单个值
                resolved_item = await self._resolve_field_value_for_update(
                    project_key, type_key, field_key, item
                )
                results.append(resolved_item)
            return results

        # 处理带分隔符的字符串 (伪多选支持 "A / B", "A, B", "A; B")
        if isinstance(value, str) and any(
            sep in value for sep in [" / ", ",", ";", "|"]
        ):
            # 策略：先尝试不拆分直接匹配（可能是一个带逗号的单选项标签）
            try:
                # 尝试直接获取，不抛出异常
                option_map = (
                    self.meta._option_cache.get(project_key, {})
                    .get(type_key, {})
                    .get(field_key, {})
                )
                if value in option_map or self.meta._fuzzy_match_option(
                    value, option_map
                ):
                    # 匹配成功，说明是一个整体，跳过拆分逻辑
                    pass
                else:
                    # 匹配失败，尝试多种分隔符拆分
                    parts = []
                    if " / " in value:
                        parts = [p.strip() for p in value.split(" / ") if p.strip()]
                    else:
                        for sep in [",", ";", "|"]:
                            if sep in value:
                                parts = [
                                    p.strip() for p in value.split(sep) if p.strip()
                                ]
                                break

                    if len(parts) > 1:
                        logger.info(
                            "Detected multi-value string, splitting '%s' into %s",
                            value,
                            parts,
                        )
                        return await self._resolve_field_value_for_update(
                            project_key, type_key, field_key, parts
                        )
            except Exception:
                pass

        try:
            # 获取选项值 (label -> value)
            option_value = await self.meta.get_option_value(
                project_key, type_key, field_key, str(value)
            )

            # 返回 {label, value} 结构供更新 API 使用
            result = {"label": str(value), "value": option_value}

            # 检查字段类型：multi_select 类型字段需要返回列表格式
            field_type = await self.meta.get_field_type(
                project_key, type_key, field_key
            )
            if field_type == "multi_select":
                # multi_select 类型字段必须返回列表格式，即使只有一个值
                result = [result]
                logger.info(
                    "Resolved option for multi_select update '%s' -> %s for field '%s'",
                    value,
                    result,
                    field_key,
                )
            else:
                logger.info(
                    "Resolved option for update '%s' -> %s for field '%s'",
                    value,
                    result,
                    field_key,
                )
            return result
        except Exception as e:
            # 只有在非 Debug 模式下才记录 Warning，避免正常的 Failed resolution 刷屏
            # 因为对于非 Select 字段（如文本、数字），这里抛错是预期的
            logger.debug(
                "Failed to resolve option '%s' for field '%s': %s",
                value,
                field_key,
                e,
            )

            # 检查字段类型，根据类型进行不同的处理
            field_type = await self.meta.get_field_type(
                project_key, type_key, field_key
            )

            # bool 类型字段：只接受有效的布尔值
            if field_type == "bool":
                # 如果已经是布尔值，直接返回
                if isinstance(value, bool):
                    return value

                # 尝试将字符串转换为布尔值
                if isinstance(value, str):
                    lower_val = value.lower()
                    if lower_val in ("true", "yes", "on", "1"):
                        return True
                    if lower_val in ("false", "no", "off", "0"):
                        return False

                # 如果输入不是有效的布尔值，抛出异常
                field_name = (
                    await self.meta.get_field_name(project_key, type_key, field_key)
                    or field_key
                )
                logger.warning(
                    "Invalid value '%s' for bool field '%s' (key=%s). "
                    "Expected: true/yes/on/1 or false/no/off/0",
                    value,
                    field_name,
                    field_key,
                )
                raise ValueError(
                    f"无法更新 bool 字段 '{field_name}': 值 '{value}' 不是有效的布尔值"
                )

            # multi_select 类型字段不能接受布尔值或无效选项
            if field_type == "multi_select":
                field_name = (
                    await self.meta.get_field_name(project_key, type_key, field_key)
                    or field_key
                )
                logger.warning(
                    "Cannot resolve option '%s' for multi_select field '%s' (key=%s). "
                    "Value must be one of the available options.",
                    value,
                    field_name,
                    field_key,
                )
                raise ValueError(
                    f"无法更新 multi_select 字段 '{field_name}': 值 '{value}' 不在可用选项中"
                )

            # Special handling regarding Boolean fields (Checkbox) - 兜底处理
            # 飞书 Checkbox 字段需要 bool 类型，但输入可能是 "true"/"yes" 字符串
            if isinstance(value, str):
                lower_val = value.lower()
                if lower_val in ("true", "yes", "on"):
                    return True
                if lower_val in ("false", "no", "off"):
                    return False

            return value  # Fallback: 非选择类型字段直接返回原值

    async def create_issue(
        self,
        name: str,
        priority: str = "P2",
        description: str = "",
        assignee: Optional[str] = None,
    ) -> int:
        """
        创建 Issue

        Args:
            name: Issue 标题
            priority: 优先级 (P0/P1/P2/P3)
            description: 描述
            assignee: 负责人（姓名或邮箱）

        Returns:
            创建的 Issue ID
        """
        project_key = await self._get_project_key()
        type_key = await self._get_type_key()

        logger.info("Creating Issue in Project: %s, Type: %s", project_key, type_key)

        # 1. Prepare fields for creation (minimal set)
        create_fields = []

        # Description
        if description:
            field_key = await self.meta.get_field_key(
                project_key, type_key, "description"
            )
            create_fields.append({"field_key": field_key, "field_value": description})

        # Assignee
        if assignee:
            field_key = "owner"
            user_key = await self.meta.get_user_key(assignee)
            create_fields.append({"field_key": field_key, "field_value": user_key})

        # 2. Create Work Item
        issue_data = await self.api.create(project_key, type_key, name, create_fields)
        # API 返回数据可能是列表 [{id: xxxx}] 或直接是 {id: xxxx}，确保返回整数 ID
        issue_id = None
        if isinstance(issue_data, list) and issue_data:
            issue_id = issue_data[0].get("id")
        elif isinstance(issue_data, dict):
            issue_id = issue_data.get("id")
        elif isinstance(issue_data, int):
            issue_id = issue_data

        if issue_id is None:
            raise ValueError("创建工作项失败: 未能获取到有效的 Issue ID")

        # 3. Update Priority (if needed)
        # Note: Priority cannot be set during creation for some reason, so we update it after.
        if priority:
            try:
                field_key = await self.meta.get_field_key(
                    project_key, type_key, "priority"
                )
                option_val = await self._resolve_field_value(
                    project_key, type_key, field_key, priority
                )

                logger.info(
                    "Updating priority to %s for issue %s...", option_val, issue_id
                )
                await self.api.update(
                    project_key,
                    type_key,
                    issue_id,
                    [{"field_key": field_key, "field_value": option_val}],
                )
            except Exception as e:
                logger.warning(
                    "Failed to update priority for issue %s: %s", issue_id, e
                )

        return int(issue_id)

    async def get_issue_details(self, issue_id: int) -> Dict[str, Any]:
        """
        获取 Issue 详情

        增强逻辑: 如果在当前类型中未找到，会自动尝试在项目的所有其他类型中搜索。
        """
        project_key = await self._get_project_key()
        type_key = await self._get_type_key()

        # 1. 尝试从当前类型获取
        try:
            items = await self.api.query(project_key, type_key, [issue_id])
            if items:
                return items[0]
        except Exception as e:
            logger.debug("Initial query failed for type %s: %s", type_key, e)

        # 2. 当前类型未找到，尝试跨类型搜索
        logger.info(
            "Issue %s not found in type %s, trying auto-discovery across all types...",
            issue_id,
            type_key,
        )

        try:
            # 获取所有类型
            all_types = await self.meta.list_types(project_key)

            # 排除已经试过的当前类型
            other_types = {
                name: key for name, key in all_types.items() if key != type_key
            }

            if not other_types:
                raise Exception(
                    f"Issue {issue_id} not found (no other types to search)"
                )

            # 并发搜索其他类型（分批次以防并发过高）
            found_item = None
            found_type_name = None

            # 将类型转换为列表以便分批
            type_items = list(other_types.items())
            batch_size = 5

            for i in range(0, len(type_items), batch_size):
                batch = type_items[i : i + batch_size]
                tasks = [
                    self.api.query(project_key, t_key, [issue_id])
                    for _t_name, t_key in batch
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for idx, res in enumerate(results):
                    if isinstance(res, list) and res:
                        found_item = res[0]
                        found_type_name = batch[idx][0]
                        _ = batch[idx][1]  # type_key not used here
                        break

                if found_item:
                    break

            if found_item:
                logger.info(
                    f"Auto-discovery success: Issue {issue_id} found in type '{found_type_name}'"
                )

                # 关键修正：如果是在其他类型中找到的，我们必须更新当前的 provider 状态或元数据上下文
                # 因为后续的字段解析（readable fields）依赖正确的 type_key
                # 这里我们临时通过修改 item 中的 work_item_type_key 来确保后续处理正确
                # 但更彻底的做法可能是更新 self._resolved_type_key，但这会影响该 Provider 实例后续的其他调用
                # 所以我们选择仅仅返回 item，而在 _enhance_work_item_with_readable_names 中会优先使用 item 中的 type key
                return found_item

        except Exception as e:
            logger.warning("Auto-discovery failed: %s", e)

        raise Exception(f"Issue {issue_id} not found in any work item type")

    async def _try_fetch_type(
        self, project_key: str, type_key: str, work_item_ids: List[int]
    ) -> List[Dict[str, Any]]:
        """
        尝试从指定类型中获取工作项

        Args:
            project_key: 项目 Key
            type_key: 工作项类型 Key
            work_item_ids: 工作项 ID 列表

        Returns:
            工作项列表，查询失败时返回空列表
        """
        try:
            return await self.api.query(project_key, type_key, work_item_ids)
        except Exception:
            return []

    async def _get_users_with_cache(self, user_keys: List[str]) -> Dict[str, str]:
        """
        通过缓存获取用户信息

        Args:
            user_keys: 用户Key列表

        Returns:
            用户Key到姓名的映射字典
        """
        user_map = {}
        users_to_fetch = []

        # 首先检查缓存
        for user_key in user_keys:
            cached_name = self._user_cache.get(user_key)
            if cached_name is not None:
                user_map[user_key] = cached_name
            else:
                users_to_fetch.append(user_key)

        # 如果有未缓存的用户，批量查询
        if users_to_fetch:
            try:
                users = await self.user_api.query_users(user_keys=users_to_fetch)
                for user in users:
                    user_key = user.get("user_key")
                    user_name = user.get("name_cn") or user.get("name_en") or user_key
                    if user_key:
                        user_map[user_key] = user_name
                        # 存入缓存
                        self._user_cache.set(user_key, user_name)
            except Exception as e:
                logger.warning("Failed to fetch users: %s", e)
                # 如果查询失败，将用户 Key 作为名称使用
                for user_key in users_to_fetch:
                    user_map[user_key] = user_key

        return user_map

    async def _get_work_items_with_cache(
        self, work_item_ids: List[int], project_key: str, type_key: str
    ) -> Tuple[Dict[int, str], List[int]]:
        """
        通过缓存获取工作项名称

        Args:
            work_item_ids: 工作项 ID 列表
            project_key: 项目 Key
            type_key: 工作项类型 Key

        Returns:
            (工作项 ID 到名称的映射字典, 未找到的 ID 列表)
        """
        work_item_map: Dict[int, str] = {}
        items_to_fetch: List[int] = []

        # 首先检查缓存
        for item_id in work_item_ids:
            cached_value = self._work_item_cache.get(str(item_id))
            if cached_value is not None:
                if cached_value != self._NOT_FOUND_MARKER:
                    work_item_map[item_id] = cached_value
                # 如果是 _NOT_FOUND_MARKER，则跳过，不添加到 items_to_fetch
            else:
                items_to_fetch.append(item_id)

        # 如果有未缓存的工作项，批量查询当前类型
        if items_to_fetch:
            try:
                items = await self.api.query(project_key, type_key, items_to_fetch)
                found_ids: Set[int] = set()
                for item in items:
                    item_id = item.get("id")
                    item_name = item.get("name") or ""
                    if item_id:
                        work_item_map[item_id] = item_name
                        # 存入缓存
                        self._work_item_cache.set(str(item_id), item_name)
                        found_ids.add(item_id)

                # 计算未找到的 ID，并缓存"未找到"标记
                not_found_ids = [
                    item_id for item_id in items_to_fetch if item_id not in found_ids
                ]
                for item_id in not_found_ids:
                    self._work_item_cache.set(str(item_id), self._NOT_FOUND_MARKER)

            except Exception as e:
                logger.debug("Failed to fetch work items in current type: %s", e)
                # 如果查询失败，所有待查询的 ID 都视为未找到
                not_found_ids = items_to_fetch
                # 不缓存失败结果，因为可能是临时错误
        else:
            not_found_ids = []

        return work_item_map, not_found_ids

    async def get_readable_issue_details(self, issue_id: int) -> Dict[str, Any]:
        """
        获取 Issue 详情，并将用户相关字段转换为人名以提高可读性

        Args:
            issue_id: Issue ID

        Returns:
            增强后的 Issue 详情，包含原始数据和可读字段
        """
        item = await self.get_issue_details(issue_id)
        return await self._enhance_work_item_with_readable_names(item)

    async def _enhance_work_item_with_readable_names(
        self, item: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        增强工作项数据，将字段 Key 和 ID 转换为可读名称

        Args:
            item: 原始工作项字典

        Returns:
            增强后的工作项字典，包含 readable_fields 字段
        """
        if not item:
            return item

        # 创建副本，避免修改原始数据
        enhanced = item.copy()

        # 获取项目和类型 Key
        project_key = item.get("project_key") or await self._get_project_key()
        type_key = item.get("work_item_type_key") or await self._get_type_key()

        # 准备收集 ID 的容器
        users_to_fetch = set()
        work_items_to_fetch = set()

        # 统一处理 fields (新版) 和 field_value_pairs (旧版)
        fields = item.get("fields", [])
        if not fields:
            # 尝试转换旧版结构
            field_value_pairs = item.get("field_value_pairs", [])
            for pair in field_value_pairs:
                fields.append(
                    {
                        "field_key": pair.get("field_key"),
                        "field_value": pair.get("field_value"),
                        # 旧版可能没有 type_key，后续只能尽力猜测
                        "field_type_key": "unknown",
                    }
                )

        # 第一遍遍历: 收集需要查询的 ID
        for field in fields:
            f_key = field.get("field_key")
            f_val = field.get("field_value")
            f_type = field.get("field_type_key", "")

            if not f_val:
                continue

            # 用户相关字段
            if f_type in ["user", "owner", "creator", "modifier"]:
                if isinstance(f_val, str):
                    users_to_fetch.add(f_val)
            elif f_type in ["multi_user", "role_owners"]:
                if isinstance(f_val, list):
                    for u in f_val:
                        if isinstance(u, str):
                            users_to_fetch.add(u)
            # 兼容 owner 字段 (可能不在 fields 中，而在根目录)
            elif f_key == "owner" and isinstance(f_val, str):
                users_to_fetch.add(f_val)

            # 关联工作项字段
            if f_type in ["work_item_related_select", "work_item_related_multi_select"]:
                if isinstance(f_val, list):
                    for wid in f_val:
                        if isinstance(wid, (int, str)) and str(wid).isdigit():
                            work_items_to_fetch.add(int(wid))
                elif isinstance(f_val, (int, str)) and str(f_val).isdigit():
                    work_items_to_fetch.add(int(f_val))

        # 根目录的 owner, created_by, updated_by
        for key in ["owner", "created_by", "updated_by"]:
            val = item.get(key)
            if val and isinstance(val, str):
                users_to_fetch.add(val)

        # 批量获取数据
        user_map = {}
        work_item_map = {}

        if users_to_fetch:
            # 使用缓存获取用户信息
            user_map = await self._get_users_with_cache(list(users_to_fetch))

        if work_items_to_fetch:
            # 首先使用缓存获取当前类型中的工作项
            cached_map, not_found_ids = await self._get_work_items_with_cache(
                list(work_items_to_fetch), project_key, type_key
            )
            work_item_map.update(cached_map)

            # 如果有未找到的工作项，尝试其他所有类型
            if not_found_ids:
                remaining_ids = set(not_found_ids)

                try:
                    # 获取项目中所有可用类型
                    try:
                        all_types = await self.meta.list_types(project_key)
                        target_types = {
                            name: key
                            for name, key in all_types.items()
                            if key != type_key  # 排除当前类型
                        }
                    except Exception as e:
                        logger.warning("Failed to list project types: %s", e)
                        target_types = {}

                    if target_types:
                        # 限制并发数，避免触发 API 限流
                        # 分批处理类型，每批 5 个
                        type_items = list(target_types.items())
                        batch_size = 5

                        for i in range(0, len(type_items), batch_size):
                            if not remaining_ids:
                                break

                            batch = type_items[i : i + batch_size]
                            search_tasks = [
                                self._try_fetch_type(
                                    project_key, t_key, list(remaining_ids)
                                )
                                for _t_name, t_key in batch
                            ]

                            results = await asyncio.gather(*search_tasks)

                            for items in results:
                                for related_item in items:
                                    related_id = related_item.get("id")
                                    related_name = related_item.get("name") or ""
                                    if related_id:
                                        work_item_map[related_id] = related_name
                                        # 存入缓存
                                        self._work_item_cache.set(
                                            str(related_id), related_name
                                        )
                                        remaining_ids.discard(related_id)

                        # 缓存仍未找到的 ID（跨类型查询后）
                        if remaining_ids:
                            logger.debug(
                                "Still not found after cross-type search: %s",
                                remaining_ids,
                            )
                            for remaining_id in remaining_ids:
                                self._work_item_cache.set(
                                    str(remaining_id), self._NOT_FOUND_MARKER
                                )

                except Exception as e:
                    logger.warning(
                        "Failed to fetch related items from other types: %s", e
                    )

        # 第二遍遍历: 构建可读字段并添加 field_name
        readable_fields = {}

        # 处理 fields 列表
        for field in fields:
            f_key = field.get("field_key")
            f_val = field.get("field_value")
            f_type = field.get("field_type_key", "")
            f_alias = field.get("field_alias")

            if f_key is None:
                continue

            # 确定字段名称
            # 优先级: metadata_manager 缓存中的 field_name > field_alias > field_key
            # 原因: metadata_manager 中存储的是 API 返回的 field_name，最准确
            field_name = None
            try:
                # 优先从 metadata_manager 缓存中获取 field_name
                field_name = await self.meta.get_field_name(
                    project_key, type_key, f_key
                )
            except Exception as e:
                logger.debug("Failed to get field_name for %s: %s", f_key, e)

            # 如果缓存中没有，使用 field_alias 作为备选
            if not field_name:
                field_name = f_alias

            # 最后兜底：使用 field_key
            if not field_name:
                field_name = f_key

            # 确保是字符串
            if field_name is None:
                field_name = str(f_key) if f_key else "unknown"

            # 为字段对象添加 field_name（直接修改以保持引用一致性）
            field["field_name"] = field_name

            readable_val = f_val

            # 用户字段处理（根据类型或字段键判断）
            user_field_keys = [
                "owner",
                "creator",
                "modifier",
                "assignee",
                "created_by",
                "updated_by",
            ]
            is_user_field = f_type in ["user", "owner", "creator", "modifier"] or (
                f_type == "unknown" and f_key in user_field_keys
            )

            # 转换值
            if f_val is not None:
                if is_user_field:
                    if isinstance(f_val, str):
                        readable_val = user_map.get(f_val, f_val)
                    else:
                        # 使用提取方法处理非字符串值（如字典或列表）
                        readable_val = self._extract_readable_field_value(f_val)
                elif f_type == "multi_user":
                    if isinstance(f_val, list):
                        new_list = []
                        for u in f_val:
                            if isinstance(u, str):
                                new_list.append(user_map.get(u, u))
                            else:
                                new_list.append(self._extract_readable_field_value(u))
                        readable_val = new_list
                elif f_type == "role_owners":
                    # Parse role_owners structure: [{"role": "role_key", "owners": ["user_key"]}]
                    if isinstance(f_val, list):
                        readable_roles = []
                        for role_item in f_val:
                            if not isinstance(role_item, dict):
                                continue

                            role_key = role_item.get("role")
                            owners = role_item.get("owners")

                            # 防御性检查
                            if not role_key:
                                continue

                            if not isinstance(owners, list):
                                owners = []

                            # Resolve Role Name
                            role_name = role_key
                            try:
                                name = await self.meta.get_role_name(
                                    project_key, type_key, role_key
                                )
                                if name:
                                    role_name = name
                            except Exception as e:
                                logger.debug(
                                    f"Failed to resolve role name for key '{role_key}': {e}"
                                )

                            # Resolve Owner Names
                            owner_names = []
                            for u in owners:
                                owner_names.append(user_map.get(u, u))

                            readable_roles.append(
                                {"role": role_name, "owners": owner_names}
                            )
                        readable_val = readable_roles
                # 关联工作项
                elif f_type in [
                    "work_item_related_select",
                    "work_item_related_multi_select",
                ]:
                    if isinstance(f_val, list):
                        new_list = []
                        for wid in f_val:
                            if isinstance(wid, (int, str)) and str(wid).isdigit():
                                new_list.append(work_item_map.get(int(wid), wid))
                            else:
                                new_list.append(wid)
                        readable_val = new_list
                    elif isinstance(f_val, (int, str)) and str(f_val).isdigit():
                        readable_val = work_item_map.get(int(f_val), f_val)
                # 选项 (Select / MultiSelect)
                elif isinstance(f_val, dict) and ("label" in f_val or "name" in f_val):
                    readable_val = f_val.get("label") or f_val.get("name")
                elif isinstance(f_val, list) and f_val and isinstance(f_val[0], dict):
                    # MultiSelect 通常返回包含 label/value 的字典列表
                    # 如果是用户字段（已在上面处理过），跳过此处理
                    if not is_user_field:
                        new_list = []
                        for item in f_val:
                            if isinstance(item, dict):
                                new_list.append(
                                    item.get("label") or item.get("name") or item
                                )
                            else:
                                new_list.append(item)
                        readable_val = new_list

            readable_fields[field_name] = readable_val

        # 确保 enhanced 中的 fields 数组包含增强后的字段信息（含 field_name）
        enhanced["fields"] = fields

        # 处理根目录特殊字段
        for key in ["owner", "created_by", "updated_by"]:
            val = item.get(key)
            if val and isinstance(val, str):
                readable_fields[key] = user_map.get(val, val)

        enhanced["readable_fields"] = readable_fields

        # 为常用字段添加顶级可读别名
        common_fields = ["owner", "creator", "updater", "assignee"]
        for field in common_fields:
            if field in readable_fields:
                enhanced[f"readable_{field}"] = readable_fields[field]

        return enhanced

    def _extract_readable_field_value(self, field_value: Any) -> Any:
        """
        提取可读的字段值，特别处理用户相关字段

        Args:
            field_value: 原始字段值

        Returns:
            可读的字段值，如果无法提取则返回原始值
        """
        if field_value is None:
            return None

        # 如果是字典且包含 label 或 name 字段，优先返回这些
        if isinstance(field_value, dict):
            if "label" in field_value:
                return field_value["label"]
            if "name" in field_value:
                return field_value["name"]
            if "name_cn" in field_value:
                return field_value["name_cn"]
            # 如果字典中没有可读字段，返回整个字典（可能是复杂对象）
            return field_value

        # 如果是列表，处理每个元素
        if isinstance(field_value, list):
            # 空列表返回空列表
            if not field_value:
                return field_value

            # 单元素列表且元素是字典：尝试提取可读值
            if len(field_value) == 1 and isinstance(field_value[0], dict):
                single_item = field_value[0]
                # 尝试提取 name, name_cn, label
                for key in ["name", "name_cn", "label"]:
                    if key in single_item:
                        return single_item[key]
                # 如果没有可读键，返回整个字典
                return single_item

            # 多元素列表：处理每个元素
            readable_items = []
            for item in field_value:
                readable_item = self._extract_readable_field_value(item)
                if readable_item is not None:
                    readable_items.append(readable_item)
            return readable_items if readable_items else field_value

        # 其他类型直接返回
        return field_value

    async def update_issue(
        self,
        issue_id: int,
        name: Optional[str] = None,
        priority: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> List[UpdateResult]:
        """
        更新 Issue（容错模式）

        将更新任务委托给 batch_update_issues 以实现字段级容错。
        如果某些字段更新失败，会继续尝试其他字段，并返回详细的结果列表。

        Args:
            issue_id: Issue ID
            name: 标题（可选）
            priority: 优先级（可选）
            description: 描述（可选）
            status: 状态（可选）
            assignee: 负责人（可选）
            extra_fields: 额外字段字典（可选）
        """
        return await self.batch_update_issues(
            issue_ids=[issue_id],
            name=name,
            priority=priority,
            description=description,
            status=status,
            assignee=assignee,
            extra_fields=extra_fields,
        )

    async def delete_issue(self, issue_id: int) -> None:
        """删除 Issue"""
        project_key = await self._get_project_key()
        type_key = await self._get_type_key()
        await self.api.delete(project_key, type_key, issue_id)

    async def _resolve_update_fields(
        self,
        project_key: str,
        type_key: str,
        issue_id: int,
        name: Optional[str] = None,
        priority: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[UpdateResult]]:
        """将人类可读的字段解析为 API 所需的 field_key/value 结构。同时返回解析失败的字段结果。"""
        resolved_fields: List[Dict[str, Any]] = []
        failed_results: List[UpdateResult] = []

        async def add_field(
            f_name: str, f_value: Any, f_key: Optional[str] = None
        ) -> None:
            """
            添加字段到解析结果列表

            Args:
                f_name: 字段显示名称
                f_value: 字段值
                f_key: 字段 Key（如果为 None，则通过 meta.get_field_key 解析）
            """
            try:
                # 预先清洗字符串输入
                if isinstance(f_value, str):
                    f_value = f_value.strip()

                # 如果未提供 f_key，通过 meta 解析
                if f_key is None:
                    f_key = await self.meta.get_field_key(project_key, type_key, f_name)

                if f_key == "name":
                    resolved_fields.append(
                        {
                            "field_key": "name",
                            "field_value": f_value,
                            "field_name": f_name,
                        }
                    )
                    return

                # 检查字段类型和空值过滤
                field_type = await self.meta.get_field_type(
                    project_key, type_key, f_key
                )
                if f_value is None or (
                    isinstance(f_value, str) and not f_value.strip()
                ):
                    # 允许清空的字段类型列表（主要是文本类）
                    if field_type not in ["text", "textarea", "name"]:
                        logger.info(
                            "Skipping empty value for non-text field '%s'", f_name
                        )
                        return

                option_val = await self._resolve_field_value_for_update(
                    project_key, type_key, f_key, f_value
                )
                resolved_fields.append(
                    {
                        "field_key": f_key,
                        "field_value": option_val,
                        "field_name": f_name,
                    }
                )
            except Exception as e:
                logger.warning("Failed to resolve field '%s': %s", f_name, e)
                failed_results.append(
                    UpdateResult(
                        success=False,
                        issue_id=issue_id,
                        field_name=f_name,
                        message=f"字段解析失败: {e}",
                    )
                )

        # 处理固定字段（name 和 owner 使用固定的 field_key）
        if name is not None:
            await add_field("name", name, f_key="name")

        if description is not None:
            await add_field("description", description)

        if priority is not None:
            await add_field("priority", priority)

        if status is not None:
            await add_field("status", status)

        if assignee is not None:
            await add_field("assignee", assignee, f_key="owner")

        # 处理额外自定义字段
        if extra_fields:
            for f_name, f_value in extra_fields.items():
                if not await self._field_exists(project_key, type_key, f_name):
                    failed_results.append(
                        UpdateResult(
                            success=False,
                            issue_id=issue_id,
                            field_name=f_name,
                            message=f"字段 '{f_name}' 不存在",
                        )
                    )
                    continue
                await add_field(f_name, f_value)

        return resolved_fields, failed_results

    async def _perform_single_field_update(
        self,
        project_key: str,
        type_key: str,
        issue_id: int,
        field_name: str,
        field_key: str,
        resolved_value: Any,
    ) -> UpdateResult:
        """执行单个工作项的单个字段更新操作。已接收预解析数据。"""
        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries + 1):
            try:
                # 调用 API 进行更新，使用信号量限制并发
                async with self._api_semaphore:
                    await self.api.update(
                        project_key,
                        type_key,
                        issue_id,
                        [{"field_key": field_key, "field_value": resolved_value}],
                    )
                    await asyncio.sleep(0.1)

                return UpdateResult(
                    success=True,
                    issue_id=issue_id,
                    field_name=field_name,
                    message=f"字段 '{field_name}' 更新成功",
                )

            except Exception as e:
                is_429 = False
                if (
                    isinstance(e, httpx.HTTPStatusError)
                    and e.response.status_code == 429
                ):
                    is_429 = True
                elif "429" in str(e) and "Too Many Requests" in str(e):
                    is_429 = True

                if is_429 and attempt < max_retries:
                    delay = base_delay * (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        "Rate limit (429) hit. Retrying in %.2f seconds...", delay
                    )
                    await asyncio.sleep(delay)
                    continue

                logger.error(
                    "Failed to update issue %d field '%s': %s", issue_id, field_name, e
                )

                error_detail = str(e)
                # 增强的错误提取逻辑：直接从异常对象的 response 中解析
                if hasattr(e, "response") and e.response is not None:
                    try:
                        err_data = e.response.json()
                        api_msg = err_data.get("err_msg") or err_data.get("msg")
                        inner_err = err_data.get("err", {})
                        inner_msg = None
                        if isinstance(inner_err, dict):
                            inner_msg = inner_err.get("msg") or inner_err.get("err_msg")

                        if api_msg and inner_msg and api_msg != inner_msg:
                            error_detail = f"{api_msg}: {inner_msg}"
                        elif inner_msg:
                            error_detail = inner_msg
                        elif api_msg:
                            error_detail = api_msg

                        # 特殊处理：如果包含 "is illegal"，提示可能是权限或流程锁定
                        if "is illegal" in error_detail:
                            error_detail += " (字段可能被流程锁定、只读或权限不足)"
                    except Exception as parse_err:
                        logger.debug(
                            "Failed to parse API error response: %s", parse_err
                        )
                        # 如果解析失败，保留原始 str(e) 但去掉冗余的 URL 信息以保持整洁
                        if "for url" in error_detail:
                            error_detail = error_detail.split("for url")[0].strip()

                return UpdateResult(
                    success=False,
                    issue_id=issue_id,
                    field_name=field_name,
                    message=f"更新字段 '{field_name}' 失败: {error_detail}",
                )

        return UpdateResult(
            success=False,
            issue_id=issue_id,
            field_name=field_name,
            message="重试次数耗尽",
        )

    async def batch_update_issues(
        self,
        issue_ids: List[int],
        *,
        name: Optional[str] = None,
        priority: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> List[UpdateResult]:
        """批量更新多个工作项。采用乐观并发策略优化耗时。"""
        if not issue_ids:
            return []

        project_key = await self._get_project_key()
        type_key = await self._get_type_key()

        # 1. 预解析所有字段（仅解析一次）
        # 注意：这里解析失败的 issue_id 暂时用第一个，后续多 Issue 场景需要复制
        resolved_fields, base_failed_results = await self._resolve_update_fields(
            project_key,
            type_key,
            issue_ids[0],
            name,
            priority,
            description,
            status,
            assignee,
            extra_fields,
        )

        all_results = []
        # 为所有 Issue 复制解析失败的结果
        for issue_id in issue_ids:
            for fr in base_failed_results:
                all_results.append(fr._replace(issue_id=issue_id))

        if not resolved_fields:
            return all_results

        # 2. 乐观执行策略：如果只有一个 Issue，尝试一次性更新所有字段
        if len(issue_ids) == 1:
            issue_id = issue_ids[0]
            try:
                logger.info("Optimistic batch update for issue %d", issue_id)
                api_payload = [
                    {"field_key": f["field_key"], "field_value": f["field_value"]}
                    for f in resolved_fields
                ]

                async with self._api_semaphore:
                    await self.api.update(project_key, type_key, issue_id, api_payload)

                # 全部成功
                all_results.extend(
                    [
                        UpdateResult(
                            success=True,
                            issue_id=issue_id,
                            field_name=f["field_name"],
                            message="更新成功",
                        )
                        for f in resolved_fields
                    ]
                )
                return all_results
            except Exception as e:
                is_429 = "429" in str(e) or (
                    isinstance(e, httpx.HTTPStatusError)
                    and e.response.status_code == 429
                )
                if is_429:
                    logger.warning(
                        "Optimistic update hit rate limit (429), falling back to individual updates."
                    )
                else:
                    logger.warning(
                        "Optimistic update failed for issue %d: %s. Falling back to individual updates for fault tolerance.",
                        issue_id,
                        e,
                    )
                # 降级执行：进入下方的逐字段更新逻辑

        # 3. 逐字段更新（降级或多 Issue 路径）
        tasks = []
        for issue_id in issue_ids:
            for field in resolved_fields:
                tasks.append(
                    self._perform_single_field_update(
                        project_key,
                        type_key,
                        issue_id,
                        field["field_name"],
                        field["field_key"],
                        field["field_value"],
                    )
                )

        logger.info("Running %d individual update tasks", len(tasks))
        results = await asyncio.gather(*tasks)
        all_results.extend([res for res in results if isinstance(res, UpdateResult)])
        return all_results

    async def filter_issues(
        self,
        status: Optional[List[str]] = None,
        priority: Optional[List[str]] = None,
        owner: Optional[str] = None,
        page_num: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        过滤查询 Issues

        支持按状态、优先级、负责人进行过滤，自动将人类可读的值转换为 API 所需的 Key。

        Args:
            status: 状态列表（如 ["待处理", "进行中"]）
            priority: 优先级列表（如 ["P0", "P1"]）
            owner: 负责人（姓名或邮箱）
            page_num: 页码（从 1 开始）
            page_size: 每页数量

        Returns:
            {
                "items": [...],  # 工作项列表
                "total": 100,    # 总数
                "page_num": 1,
                "page_size": 20
            }

        示例:
            # 获取所有 P0 优先级的进行中任务
            result = await provider.filter_issues(
                status=["进行中"],
                priority=["P0"]
            )
        """
        project_key = await self._get_project_key()
        type_key = await self._get_type_key()

        # 构建搜索条件（使用辅助方法减少重复代码）
        conditions: List[Dict[str, Any]] = []

        # 处理状态过滤
        if status:
            condition = await self._build_filter_condition(
                project_key, type_key, "status", status
            )
            if condition:
                conditions.append(condition)

        # 处理优先级过滤
        if priority:
            condition = await self._build_filter_condition(
                project_key, type_key, "priority", priority
            )
            if condition:
                conditions.append(condition)

        # 处理负责人过滤（使用简化的辅助方法）
        if owner:
            condition = await self._build_owner_filter_condition(
                project_key, type_key, owner
            )
            if condition:
                conditions.append(condition)

        # 构建 search_group
        search_group = {
            "conjunction": "AND",
            "search_params": conditions,
            "search_groups": [],
        }

        logger.info("Filtering issues with conditions: %s", conditions)
        logger.debug("filter_issues: Built search_group: %s", search_group)

        # 调用 API
        result = await self.api.search_params(
            project_key=project_key,
            work_item_type_key=type_key,
            search_group=search_group,
            page_num=page_num,
            page_size=page_size,
        )

        # 使用辅助方法标准化返回结果
        items, pagination = self._normalize_api_result(result, page_num, page_size)

        return {
            "items": items,
            "total": pagination.get("total", len(items)),
            "page_num": pagination.get("page_num", page_num),
            "page_size": pagination.get("page_size", page_size),
        }

    async def get_tasks(
        self,
        name_keyword: Optional[str] = None,
        status: Optional[List[str]] = None,
        priority: Optional[List[str]] = None,
        owner: Optional[str] = None,
        related_to: Optional[int] = None,
        page_num: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        获取工作项列表（支持全量或按条件过滤）

        设计理念:
        - 无参数时返回全部工作项
        - 字段不存在时自动跳过该过滤条件
        - 支持多维度组合过滤
        - 如果提供 name_keyword，优先使用高效的 filter API
        - 支持按关联工作项 ID 过滤（客户端过滤）

        Args:
            name_keyword: 任务名称关键词（可选，支持模糊搜索）
            status: 状态列表（可选，如 ["待处理", "进行中"]）
            priority: 优先级列表（可选，如 ["P0", "P1"]）
            owner: 负责人（可选，姓名或邮箱）
            related_to: 关联工作项 ID（可选），用于查找与指定工作项关联的其他工作项
            page_num: 页码（从 1 开始）
            page_size: 每页数量

        Returns:
            {
                "items": [...],
                "total": 100,
                "page_num": 1,
                "page_size": 50
            }

        示例:
            # 获取全部工作项
            result = await provider.get_tasks()

            # 按名称关键词搜索
            result = await provider.get_tasks(name_keyword="SG06VA")

            # 按优先级过滤
            result = await provider.get_tasks(priority=["P0", "P1"])

            # 查找与指定工作项关联的工作项
            result = await provider.get_tasks(related_to=6181818812)
        """
        project_key = await self._get_project_key()
        type_key = await self._get_type_key()

        # 特殊处理：当只有 related_to 参数时，需要获取工作项进行客户端过滤
        # 因为关联字段不支持 API 级别的过滤
        # ⚠️ 安全加固：限制扫描深度，防止 DoS 攻击或资源耗尽
        if (
            related_to
            and not name_keyword
            and not status
            and not priority
            and not owner
        ):
            logger.warning(
                "⚠️ related_to filter without other conditions requires client-side scanning. "
                "This is an expensive operation. Consider adding name_keyword, status, or priority "
                "to narrow the search scope. Scanning for related_to=%s",
                related_to,
            )

            found_items: List[Dict[str, Any]] = []
            total_fetched = 0
            current_page = 1

            while (
                total_fetched < self._SCAN_MAX_TOTAL_ITEMS
                and current_page <= self._SCAN_MAX_PAGES
            ):
                # 确定本次并发请求的页码范围
                end_page = min(
                    current_page + self._SCAN_CONCURRENT_PAGES,
                    self._SCAN_MAX_PAGES + 1,
                )

                # 使用列表推导式构建并发任务
                tasks = [
                    self.api.filter(
                        project_key=project_key,
                        work_item_type_keys=[type_key],
                        page_num=p,
                        page_size=self._SCAN_BATCH_SIZE,
                    )
                    for p in range(current_page, end_page)
                ]

                logger.info(
                    "Fetching pages %d to %d concurrently...",
                    current_page,
                    end_page - 1,
                )

                # 并发执行请求
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 处理结果
                batch_items_count = 0
                should_stop = False
                has_error = False

                for i, result in enumerate(results):
                    result_page_num = current_page + i

                    if isinstance(result, Exception):
                        logger.error(
                            "Failed to fetch page %d: %s", result_page_num, result
                        )
                        has_error = True
                        continue

                    # 标准化返回结果（简化版，不需要完整 pagination）
                    items, _ = self._normalize_api_result(
                        result, result_page_num, self._SCAN_BATCH_SIZE
                    )

                    if not items:
                        should_stop = True
                        # 不break，继续处理其他成功页面的结果

                    batch_items_count += len(items)
                    total_fetched += len(items)

                    # 使用辅助方法过滤关联工作项
                    found_items.extend(
                        item
                        for item in items
                        if self._is_item_related_to(item, related_to)
                    )

                    # 如果某一页的数据少于 BATCH_SIZE，说明已经是最后一页
                    if len(items) < self._SCAN_BATCH_SIZE:
                        should_stop = True

                logger.debug(
                    "Fetched pages %d-%d: %d items, found %d related items so far",
                    current_page,
                    end_page - 1,
                    batch_items_count,
                    len(found_items),
                )

                if should_stop:
                    break

                # 如果出现错误但没有明确停止信号，也停止，防止数据不一致导致的问题
                if has_error:
                    logger.warning(
                        "Stopping fetch due to errors in page retrieval to ensure data consistency"
                    )
                    break

                current_page += self._SCAN_CONCURRENT_PAGES

            logger.info(
                "Fetched %d items, found %d items related to %s",
                total_fetched,
                len(found_items),
                related_to,
            )

            # 如果获取了大量数据但找到的关联项很少，记录警告
            if total_fetched > 200 and len(found_items) < 5:
                logger.warning(
                    "Low efficiency: fetched %d items but only found %d related items. "
                    "Consider using name_keyword to narrow search.",
                    total_fetched,
                    len(found_items),
                )

            return {
                "items": found_items,
                "total": len(found_items),
                "page_num": 1,
                "page_size": len(found_items),
                "hint": (
                    f"Found {len(found_items)} items related to {related_to} "
                    f"(scanned {total_fetched} items, max {self._SCAN_MAX_TOTAL_ITEMS}). "
                    "To search more items, add name_keyword, status, or priority filters."
                ),
            }

        # 如果提供了 name_keyword，优先使用 filter API（更高效）
        # filter API 支持 work_item_name 和 work_item_status，但不支持 priority/owner/related_to
        if name_keyword:
            logger.info("Using filter API for name keyword search: '%s'", name_keyword)

            # 准备 filter API 参数
            filter_kwargs = {}
            if name_keyword:
                filter_kwargs["work_item_name"] = name_keyword

            # filter API 支持 status，但需要转换为状态值
            if status:
                # 尝试解析状态值
                try:
                    field_key = await self.meta.get_field_key(
                        project_key, type_key, "status"
                    )
                    resolved_statuses = []
                    for s in status:
                        try:
                            val = await self._resolve_field_value(
                                project_key, type_key, field_key, s
                            )
                            resolved_statuses.append(val)
                        except Exception as e:
                            logger.warning("Failed to resolve status '%s': %s", s, e)
                    if resolved_statuses:
                        filter_kwargs["work_item_status"] = resolved_statuses
                        logger.info(
                            "Added status filter to filter API: %s", resolved_statuses
                        )
                except Exception as e:
                    logger.warning("Status field not available for filter API: %s", e)

            # filter API 不支持 priority、owner 和 related_to，记录警告
            if priority:
                logger.warning(
                    "Filter API does not support priority filter, "
                    "will filter results after retrieval"
                )
            if owner:
                logger.warning(
                    "Filter API does not support owner filter, "
                    "will filter results after retrieval"
                )
            if related_to:
                logger.warning(
                    "Filter API does not support related_to filter, "
                    "will filter results after retrieval"
                )

            # 1. 获取该类型的所有字段映射 (Name -> Key)
            # 这利用了 MetadataManager 的缓存机制，避免多次 API 调用
            try:
                all_fields_map = await self.meta.list_fields(project_key, type_key)
            except Exception as e:
                logger.warning("Filter API: Failed to list fields: %s", e)
                all_fields_map = {}

            # 定义业务逻辑需要的基础字段
            # 这些是代码逻辑依赖的字段（用于客户端过滤），无论用户是否传入过滤参数都需要获取
            needed_fields = {"priority", "status", "owner"}

            # 3. 解析字段 Key
            fields_to_fetch = []

            for name in needed_fields:
                # 优先尝试从全量 Map 中直接获取 (最快，O(1))
                if name in all_fields_map:
                    fields_to_fetch.append(all_fields_map[name])
                else:
                    # 如果 Map 中没有（例如字段名是中文 "优先级" 但我们需要 "priority"），
                    # 则委托给 MetadataManager 进行智能解析（支持模糊匹配、别名查找等）
                    try:
                        key = await self.meta.get_field_key(project_key, type_key, name)
                        fields_to_fetch.append(key)
                    except Exception as e:
                        # 某些非关键字段如果找不到，可以忽略，不影响整体流程
                        logger.debug(
                            "Filter API: Optional field '%s' not found: %s", name, e
                        )

            if fields_to_fetch:
                # 去重并赋值
                filter_kwargs["fields"] = list(set(fields_to_fetch))

            result = await self.api.filter(
                project_key=project_key,
                work_item_type_keys=[type_key],
                page_num=page_num,
                page_size=page_size,
                **filter_kwargs,
            )

            # 使用辅助方法标准化返回结果
            items, pagination = self._normalize_api_result(result, page_num, page_size)

            # 如果 filter API 不支持某些条件，在结果中进一步筛选
            if priority or owner or related_to:
                filtered_items = []
                for item in items:
                    # 检查优先级
                    if priority:
                        item_priority = self._extract_field_value(item, "priority")
                        if item_priority not in priority:
                            continue

                    # 检查负责人
                    if owner:
                        try:
                            user_key = await self.meta.get_user_key(owner)
                            item_owner_key = self._extract_field_value(item, "owner")
                            # 如果提取的是 user_key，直接比较
                            if item_owner_key and item_owner_key != user_key:
                                # 尝试匹配名称（owner 字段可能返回名称）
                                if owner.lower() not in (item_owner_key or "").lower():
                                    continue
                        except Exception as e:
                            logger.debug("Failed to filter by owner '%s': %s", owner, e)
                            # 如果无法解析 owner，跳过该过滤条件

                    # 使用辅助方法检查关联工作项
                    if related_to and not self._is_item_related_to(item, related_to):
                        continue

                    filtered_items.append(item)

                items = filtered_items
                logger.info(
                    "Filtered results: %d items after priority/owner/related_to filtering",
                    len(items),
                )

            logger.info(
                "Retrieved %d items (total: %d)", len(items), pagination.get("total", 0)
            )

            return {
                "items": items,
                "total": pagination.get("total", len(items)),
                "page_num": pagination.get("page_num", page_num),
                "page_size": pagination.get("page_size", page_size),
            }

        # 没有 name_keyword，使用 search_params API 进行复杂条件查询
        # 构建搜索条件（使用辅助方法减少重复代码）
        conditions: List[Dict[str, Any]] = []

        # 处理状态过滤
        if status:
            condition = await self._build_filter_condition(
                project_key, type_key, "status", status
            )
            if condition:
                conditions.append(condition)

        # 处理优先级过滤
        if priority:
            condition = await self._build_filter_condition(
                project_key, type_key, "priority", priority
            )
            if condition:
                conditions.append(condition)

        # 处理负责人过滤
        if owner:
            condition = await self._build_owner_filter_condition(
                project_key, type_key, owner
            )
            if condition:
                conditions.append(condition)

        # 构建 search_group
        search_group = {
            "conjunction": "AND",
            "search_params": conditions,
            "search_groups": [],
        }

        logger.info(
            "Querying tasks with %d conditions, page_num=%d, page_size=%d",
            len(conditions),
            page_num,
            page_size,
        )
        logger.debug("get_tasks: Built search_group: %s", search_group)

        # 构建需要返回的字段列表
        fields_to_fetch = []
        if status or priority or owner or related_to:
            # 我们需要这些字段进行客户端过滤或显示
            needed_fields = ["priority", "status", "owner"]
            for field_name in needed_fields:
                try:
                    field_key = await self.meta.get_field_key(
                        project_key, type_key, field_name
                    )
                    fields_to_fetch.append(field_key)
                except Exception as e:
                    logger.debug("Failed to get field key for '%s': %s", field_name, e)

        # 调用 API
        result = await self.api.search_params(
            project_key=project_key,
            work_item_type_key=type_key,
            search_group=search_group,
            page_num=page_num,
            page_size=page_size,
            fields=fields_to_fetch if fields_to_fetch else None,
        )

        # 使用辅助方法标准化返回结果
        items, pagination = self._normalize_api_result(result, page_num, page_size)

        logger.info(
            "Retrieved %d items (total: %d)", len(items), pagination.get("total", 0)
        )

        # 如果指定了 related_to，使用辅助方法进行客户端过滤
        # search_params API 不支持关联字段过滤
        if related_to:
            logger.info("Applying client-side related_to filter: %s", related_to)
            items = [
                item for item in items if self._is_item_related_to(item, related_to)
            ]
            logger.info(
                "Filtered results: %d items after related_to filtering", len(items)
            )

        return {
            "items": items,
            "total": pagination.get("total", len(items)),
            "page_num": pagination.get("page_num", page_num),
            "page_size": pagination.get("page_size", page_size),
        }

    async def list_available_options(self, field_name: str) -> Dict[str, str]:
        """
        列出字段的可用选项

        用于帮助用户了解可用的选项值。

        Args:
            field_name: 字段名称（如 "status", "priority"）

        Returns:
            {label: value} 字典
        """
        project_key = await self._get_project_key()
        type_key = await self._get_type_key()
        field_key = await self.meta.get_field_key(project_key, type_key, field_name)
        return await self.meta.list_options(project_key, type_key, field_key)

    def clear_user_cache(self) -> None:
        """
        清理用户缓存

        当用户信息发生变化时调用此方法
        """
        self._user_cache.clear()
        logger.info("Cleared user cache")

    def clear_work_item_cache(self) -> None:
        """
        清理工作项缓存

        当工作项信息发生变化时调用此方法
        """
        self._work_item_cache.clear()
        logger.info("Cleared work item cache")

    def clear_all_caches(self) -> None:
        """
        清理所有缓存
        """
        self._user_cache.clear()
        self._work_item_cache.clear()
        logger.info("Cleared all caches (user + work_item)")

    def invalidate_work_item_cache(self, work_item_id: int) -> None:
        """
        使特定工作项的缓存失效

        当工作项更新时调用此方法

        Args:
            work_item_id: 工作项 ID
        """
        key = str(work_item_id)
        if self._work_item_cache.delete(key):
            logger.info("Invalidated work item cache for ID: %d", work_item_id)
        else:
            logger.debug("Work item cache not found for ID: %d", work_item_id)

    def invalidate_user_cache(self, user_key: str) -> None:
        """
        使特定用户的缓存失效

        当用户信息更新时调用此方法

        Args:
            user_key: 用户 Key
        """
        if self._user_cache.delete(user_key):
            logger.info("Invalidated user cache for key: %s", user_key)
        else:
            logger.debug("User cache not found for key: %s", user_key)
