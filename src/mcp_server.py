"""
Author: liangyz liangyz@seirobotics.net
Date: 2026-01-12 15:48:38
LastEditors: liangyz liangyz@seirobotics.net
LastEditTime: 2026-01-14 12:44:01
FilePath: /lark_agent/src/mcp_server.py
Description:
    MCP Server - 飞书 Agent 工具接口

    提供给 LLM 调用的工具集，用于操作飞书项目中的工作项。

    工具列表:
    - list_projects: 列出所有可用项目
    - create_task: 创建工作项
    - get_tasks: 获取工作项列表（支持全量或过滤）
    - get_task_detail: 获取单个工作项完整详情
    - update_task: 更新工作项
    - get_task_options: 获取字段可用选项

    重要说明:
    - 所有工具都支持 project_name（项目名称）参数，会自动转换为 project_key
    - 如果用户提供的是项目名称（如 "SR6D2VA-7552-Lark"），系统会自动查找对应的 project_key
"""

import re
import json
import logging
import sys
from pathlib import Path
from typing import Optional, List, Any, Callable, TypeVar, cast
import functools
import httpx

from mcp.server.fastmcp import FastMCP

from src.core.config import settings
from src.core.context import user_key_context
from src.providers.lark_project.managers import MetadataManager
from src.providers.lark_project.work_item_provider import WorkItemProvider


def _mask_sensitive(value: str, visible_chars: int = 4) -> str:
    """对敏感信息进行脱敏处理，仅显示前几个字符"""
    if not value or len(value) <= visible_chars:
        return "***"
    return f"{value[:visible_chars]}***"


def _mask_project(project: Optional[str]) -> str:
    """对项目标识符进行脱敏"""
    if not project:
        return "(default)"
    if project.startswith("project_"):
        return f"project_{project[8:12]}***" if len(project) > 12 else "project_***"
    # 项目名称只显示前4个字符
    return _mask_sensitive(project)


# 业务错误关键词（应透传给用户）
_BUSINESS_ERROR_KEYWORDS = frozenset(
    [
        "工作项类型",
        "项目",
        "用户",
        "字段",
        "选项",
        "权限",
        "不存在",
        "未找到",
        "无效",
        "不允许",
        "不支持",
        "可用类型",
    ]
)

# 堆栈跟踪特征（应隐藏）
_STACK_TRACE_INDICATORS = ('File "', "line ", "Traceback", "at 0x")


def _mask_sensitive_in_error(error_msg: str) -> str:
    """
    对错误信息中的敏感数据进行脱敏

    替换可能暴露内部实现的敏感标识符，如 project_key、user_key、token 等。

    Args:
        error_msg: 原始错误信息

    Returns:
        脱敏后的错误信息
    """
    # 替换 project_key 格式 (project_ 后跟字母数字下划线)
    error_msg = re.sub(r"project_[a-zA-Z0-9_]+", "project_***", error_msg)
    # 替换 user_ 开头的标识符
    error_msg = re.sub(r"user_[a-zA-Z0-9_]+", "user_***", error_msg)
    # 替换可能的长十六进制密钥 (32位及以上)
    error_msg = re.sub(r"[a-fA-F0-9]{32,}", "***", error_msg)
    # 替换 token/secret/key 相关的敏感值 (case insensitive)
    error_msg = re.sub(
        r"(?i)(token|secret|key|authorization)[=:\s]+[^\s,;\"']+",
        r"\1=***",
        error_msg,
    )
    return error_msg


def _error_response(
    operation: str,
    error_msg: str,
    error_code: Optional[str] = None,
) -> str:
    """
    生成统一的错误响应 JSON

    Args:
        operation: 操作名称，如 "创建任务"、"获取列表"
        error_msg: 错误信息（会自动脱敏）
        error_code: 错误码（可选），如 "ERR_HTTP"、"ERR_VALIDATION"

    Returns:
        JSON 格式的错误响应字符串
    """
    safe_msg = _mask_sensitive_in_error(error_msg)
    response = {
        "success": False,
        "error": {
            "message": f"{operation}失败: {safe_msg}",
        },
    }
    if error_code:
        response["error"]["code"] = error_code
    return json.dumps(response, ensure_ascii=False, indent=2)


def _success_response(data: dict, message: Optional[str] = None) -> str:
    """
    生成统一的成功响应 JSON

    Args:
        data: 响应数据
        message: 可选的提示信息

    Returns:
        JSON 格式的成功响应字符串
    """
    response = {
        "success": True,
        "data": data,
    }
    if message:
        response["message"] = message
    return json.dumps(response, ensure_ascii=False, indent=2)


def _extract_safe_error_message(exc: Exception, max_length: int = 200) -> str:
    """
    从异常中提取安全的错误消息，移除堆栈跟踪

    Args:
        exc: 异常对象
        max_length: 最大返回长度

    Returns:
        安全的错误消息字符串
    """
    error_str = str(exc)

    # 移除堆栈跟踪：遇到堆栈特征时截断
    lines = error_str.split("\n")
    safe_lines = []
    for line in lines:
        stripped = line.strip()
        # 检测堆栈跟踪开始
        if stripped.startswith(('File "', "Traceback", "    at ")):
            break
        safe_lines.append(line)

    result = " ".join(safe_lines[:3]).strip()
    return result[:max_length] if len(result) > max_length else result


def _should_expose_error(error_msg: str) -> bool:
    """
    判断是否应该将错误信息透传给用户

    某些错误信息对用户有帮助（如可用类型列表），应该透传而非隐藏。
    包含堆栈跟踪的错误应该隐藏。

    Args:
        error_msg: 异常的字符串表示

    Returns:
        True: 应该透传给用户（脱敏后）
        False: 应该返回通用错误信息
    """
    # 检查是否包含堆栈跟踪（应该隐藏）
    if any(indicator in error_msg for indicator in _STACK_TRACE_INDICATORS):
        return False

    # 检查是否包含业务错误关键词
    return any(keyword in error_msg for keyword in _BUSINESS_ERROR_KEYWORDS)


# 在模块级别配置日志（确保在 logger 创建前配置）
# 检查是否已经配置过日志，避免重复配置
if not logging.root.handlers:
    log_dir = Path("log")
    if log_dir.exists() and log_dir.is_dir():
        log_file = log_dir / "agent.log"
        logging.basicConfig(
            level=settings.get_log_level(),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            filename=str(log_file),
            filemode="a",
            encoding="utf-8",
        )
    else:
        # 如果没有 log 目录，输出到 stderr
        logging.basicConfig(
            level=settings.get_log_level(),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            stream=sys.stderr,
        )

logger = logging.getLogger(__name__)
logger.debug("Logger initialized for module: %s", __name__)

# Initialize FastMCP server
mcp = FastMCP("Lark")


T = TypeVar("T")


def with_user_context(func: Callable[..., Any]) -> Callable[..., Any]:
    """装饰器：将参数中的 user_key 设置到全局上下文中"""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        user_key = kwargs.get("user_key")
        token = user_key_context.set(user_key)
        try:
            return await func(*args, **kwargs)
        finally:
            user_key_context.reset(token)

    return wrapper


def _is_project_key_format(identifier: str) -> bool:
    """判断是否为 project_key 格式（以 'project_' 开头）"""
    return bool(identifier and identifier.startswith("project_"))


def _normalize_string_param(value: Optional[str]) -> Optional[str]:
    """
    规范化字符串参数：将空字符串视为 None

    Args:
        value: 原始参数值

    Returns:
        规范化后的值（空字符串转为 None）
    """
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _validate_page_params(page_num: int, page_size: int) -> tuple[int, int]:
    """
    校验分页参数

    Args:
        page_num: 页码
        page_size: 每页数量

    Returns:
        校验后的 (page_num, page_size)

    Raises:
        ValueError: 参数无效
    """
    if page_num < 1:
        raise ValueError(f"page_num 必须大于 0，当前值: {page_num}")
    if page_size < 1:
        raise ValueError(f"page_size 必须大于 0，当前值: {page_size}")
    if page_size > 100:
        page_size = 100  # 自动修正为最大值
    return page_num, page_size


def _create_provider(
    project: Optional[str] = None, work_item_type: Optional[str] = None
) -> WorkItemProvider:
    """
    根据 project 参数创建 Provider

    自动判断传入的是 project_key 还是 project_name，并相应处理。
    如果未提供 project，则使用环境变量 FEISHU_PROJECT_KEY。

    Args:
        project: 项目标识符（可以是 project_key 或 project_name），可选
        work_item_type: 工作项类型名称（可选），如 "需求管理"、"Issue管理" 等

    Returns:
        WorkItemProvider 实例
    """
    # 规范化参数：将空字符串视为 None
    project = _normalize_string_param(project)
    work_item_type = _normalize_string_param(work_item_type)

    if not project:
        # 使用默认项目（从环境变量读取）
        logger.debug("Using default project from FEISHU_PROJECT_KEY")
        if work_item_type:
            return WorkItemProvider(work_item_type_name=work_item_type)
        return WorkItemProvider()

    if _is_project_key_format(project):
        logger.debug("Treating '%s' as project_key", _mask_project(project))
        if work_item_type:
            return WorkItemProvider(
                project_key=project, work_item_type_name=work_item_type
            )
        return WorkItemProvider(project_key=project)
    else:
        # 当作项目名称处理
        logger.debug("Treating '%s' as project_name", _mask_project(project))
        if work_item_type:
            return WorkItemProvider(
                project_name=project, work_item_type_name=work_item_type
            )
        return WorkItemProvider(project_name=project)


@mcp.tool()
@with_user_context
async def list_projects(user_key: Optional[str] = None) -> str:
    """
    列出所有可用的飞书项目空间。

    当你不知道项目的 project_key 时，先调用此工具获取项目列表。
    返回的列表包含项目名称和对应的 project_key。

    Args:
        user_key: (可选) 飞书用户标识符 (X-USER-KEY)，用于以特定用户身份进行操作。

    Returns:
        JSON 格式的项目列表，格式为 {project_name: project_key}。
        失败时返回错误信息。

    Examples:
        # 查看有哪些项目可用
        list_projects()
    """
    try:
        logger.info("Listing all available projects")
        meta = MetadataManager.get_instance()
        projects = await meta.list_projects()

        logger.info("Retrieved %d projects", len(projects))
        return json.dumps(
            {
                "count": len(projects),
                "projects": projects,
                "hint": "使用项目名称或 project_key 都可以调用其他工具",
            },
            ensure_ascii=False,
            indent=2,
        )
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.error("Failed to list projects: %s", e, exc_info=True)
        return f"获取项目列表失败: {str(e)}"
    except Exception as e:
        # 提取安全的错误信息，移除堆栈跟踪
        error_msg = _extract_safe_error_message(e)
        if _should_expose_error(error_msg):
            # 透传前进行敏感信息脱敏
            return f"获取项目列表失败: {_mask_sensitive_in_error(error_msg)}"
        # 捕获其他未知异常，但记录完整信息以便调试
        logger.critical("Unexpected error listing projects: %s", e, exc_info=True)
        return "获取项目列表失败: 系统内部错误"


@mcp.tool()
@with_user_context
async def create_task(
    name: str,
    project: Optional[str] = None,
    work_item_type: Optional[str] = None,
    priority: str = "P2",
    description: str = "",
    assignee: Optional[str] = None,
    user_key: Optional[str] = None,
) -> str:
    """
    在指定项目中创建新的工作项（任务/Issue）。

    这是创建飞书项目工作项的主要工具。系统会自动处理字段值的转换
    （如将 "P0" 转换为对应的选项 Key）。

    Args:
        name: 工作项标题，必填。
        project: 项目标识符（可选）。可以是:
                - 项目名称（如 "SR6D2VA-7552-Lark"）
                - project_key（如 "project_xxx"）
                如不指定，则使用环境变量 FEISHU_PROJECT_KEY 配置的默认项目。
        work_item_type: 工作项类型名称（可选），如 "需求管理"、"Issue管理"、"项目管理" 等名。
                       如不指定，默认使用项目中的第一个可用类型。
        priority: 优先级，可选值: P0(最高), P1, P2(默认), P3(最低)。
        description: 工作项描述，支持纯文本。
        assignee: 负责人的姓名或邮箱。如不指定则为空。
        user_key: (可选) 飞书用户标识符 (X-USER-KEY)，用于以特定用户身份进行操作。

    Returns:
        成功时返回 "创建成功，Issue ID: xxx"。
        失败时返回错误信息。

    Examples:
        # 使用默认项目创建任务
        create_task(name="修复登录页面崩溃问题", priority="P0")

        # 指定项目和工作项类型创建任务
        create_task(
            project="SR6D2VA-7552-Lark",
            work_item_type="Issue管理",
            name="修复登录页面崩溃问题",
            priority="P0",
            assignee="张三"
        )
    """
    try:
        # 日志脱敏：不记录完整的项目标识符和任务名称
        logger.info(
            "Creating task: project=%s, work_item_type=%s, name_len=%d, priority=%s, has_assignee=%s",
            _mask_project(project),
            work_item_type,
            len(name) if name else 0,
            priority,
            bool(assignee),
        )
        provider = _create_provider(project, work_item_type)
        issue_id = await provider.create_issue(
            name=name,
            priority=priority,
            description=description,
            assignee=assignee,
        )
        logger.info("Task created successfully: issue_id=%s", issue_id)
        return f"创建成功，Issue ID: {issue_id}"
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.error(
            "Failed to create task: project=%s, error=%s",
            _mask_project(project),
            e,
            exc_info=True,
        )
        return f"创建失败: {str(e)}"
    except Exception as e:
        error_msg = _extract_safe_error_message(e)
        if _should_expose_error(error_msg):
            return f"创建失败: {_mask_sensitive_in_error(error_msg)}"
        logger.critical(
            "Unexpected error creating task: project=%s, error=%s",
            _mask_project(project),
            e,
            exc_info=True,
        )
        return "创建失败: 系统内部错误"


@mcp.tool()
@with_user_context
async def get_tasks(
    project: Optional[str] = None,
    work_item_type: Optional[str] = None,
    name_keyword: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    owner: Optional[str] = None,
    related_to: Optional[str] = None,
    page_num: int = 1,
    page_size: int = 50,
    user_key: Optional[str] = None,
) -> str:
    """
    获取项目中的工作项列表（支持全量获取或按条件过滤）。

    这是通用的任务获取工具，具备以下特性：
    1. 无过滤参数时，返回项目的全部工作项
    2. 支持按任务名称关键词进行高效搜索（推荐）
    3. 支持按状态、优先级、负责人进行灵活过滤
    4. 支持按关联工作项 ID 或名称过滤（查找与指定工作项关联的项）
    5. 如果项目不存在某个字段（如状态），会自动跳过该过滤条件
    6. 支持指定工作项类型（如 "需求管理"、"Issue管理"、"项目管理" 等）

    Args:
        project: 项目标识符（可选）。可以是:
                - 项目名称（如 "Project Management"）
                - project_key（如 "project_xxx"）
                如不指定，则使用环境变量 FEISHU_PROJECT_KEY 配置的默认项目。
        work_item_type: 工作项类型名称（可选），如 "需求管理"、"Issue管理"、"项目管理" 等。
                       如果不指定，默认使用 "问题管理" 类型。
        name_keyword: 任务名称关键词（可选，支持模糊搜索，推荐使用）。
                      例如："SG06VA" 可以搜索所有包含该关键词的任务。
        status: 状态过滤（多个用逗号分隔），如 "待处理,进行中"（可选）。
        priority: 优先级过滤（多个用逗号分隔），如 "P0,P1"（可选）。
        owner: 负责人过滤（姓名或邮箱）（可选）。
        related_to: 关联工作项 ID 或名称（可选）。用于查找与指定工作项关联的其他工作项。
                   - 如果是整数或数字字符串，直接作为工作项 ID 使用
                   - 如果是非数字字符串，自动搜索该名称对应的工作项（精确匹配优先）
                   例如：related_to="SG06VA1" 或 related_to=6288163810
        page_num: 页码，从 1 开始（默认 1）。
        page_size: 每页数量（默认 50，最大 100）。
        user_key: (可选) 飞书用户标识符 (X-USER-KEY)，用于以特定用户身份进行操作。

    Returns:
        JSON 格式的工作项列表，包含 id, name, status, priority, owner。
        失败时返回错误信息。

    Examples:
        # 获取默认项目的全部工作项
        get_tasks()

        # 获取"需求管理"类型的工作项
        get_tasks(project="Project Management", work_item_type="需求管理")

        # 按名称关键词搜索（推荐，高效）
        get_tasks(name_keyword="SG06VA")

        # 获取指定优先级的任务
        get_tasks(priority="P0,P1")

        # 查找与指定工作项关联的工作项（通过名称）
        get_tasks(related_to="SG06VA1", work_item_type="Issue管理")

        # 查找与指定工作项关联的工作项（通过 ID）
        get_tasks(
            project="Project Management",
            work_item_type="需求管理",
            related_to=6181818812
        )

        # 指定项目并组合多个条件过滤
        get_tasks(
            project="Project Management",
            work_item_type="需求管理",
            name_keyword="SG06VA",
            status="进行中",
            priority="P0"
        )
    """
    try:
        # 参数校验
        try:
            page_num, page_size = _validate_page_params(page_num, page_size)
        except ValueError as e:
            return _error_response("获取任务列表", str(e), "ERR_VALIDATION")

        logger.info(
            "Getting tasks: project=%s, work_item_type=%s, has_name_keyword=%s, status=%s, priority=%s, has_owner=%s, has_related_to=%s, page=%d/%d",
            _mask_project(project),
            work_item_type,
            bool(name_keyword),
            status,
            priority,
            bool(owner),
            bool(related_to),
            page_num,
            page_size,
        )
        provider = _create_provider(project, work_item_type)

        # 智能解析 related_to 参数（委托给 Provider）
        related_to_id = None
        if related_to is not None:
            try:
                related_to_id = await provider.resolve_related_to(related_to, project)
            except ValueError as e:
                return _error_response("解析关联工作项", str(e), "ERR_VALIDATION")

        # 解析逗号分隔的过滤条件
        status_list = [s.strip() for s in status.split(",")] if status else None
        priority_list = [p.strip() for p in priority.split(",")] if priority else None

        result = await provider.get_tasks(
            name_keyword=name_keyword,
            status=status_list,
            priority=priority_list,
            owner=owner,
            related_to=related_to_id,
            page_num=page_num,
            page_size=page_size,
        )

        # 确保 result 是字典类型
        if not isinstance(result, dict):
            logger.error("Unexpected result type: %s, value: %s", type(result), result)
            return "获取任务列表失败: 返回数据格式错误"

        # 构建字段映射（字段名称 -> 字段Key）
        field_mapping = {}
        try:
            project_key = await provider._get_project_key()
            type_key = await provider._get_type_key()
            # 尝试获取常用字段的Key
            for field_name in ["priority", "status", "owner"]:
                try:
                    field_key = await provider.meta.get_field_key(
                        project_key, type_key, field_name
                    )
                    field_mapping[field_name] = field_key
                    logger.debug("Field mapping %s -> %s", field_name, field_key)
                except Exception as e:
                    logger.debug("Field '%s' not found: %s", field_name, e)
        except Exception as e:
            logger.warning("Failed to build field mapping: %s", e)

        # 简化返回结果
        simplified = await provider.simplify_work_items(
            result.get("items", []), field_mapping
        )

        logger.info(
            "Retrieved %d tasks (total: %d)", len(simplified), result.get("total", 0)
        )

        return json.dumps(
            {
                "total": result.get("total", 0),
                "page_num": result.get("page_num", page_num),
                "page_size": result.get("page_size", page_size),
                "items": simplified,
            },
            ensure_ascii=False,
            indent=2,
        )
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.error(
            "Failed to get tasks: project=%s, error=%s",
            _mask_project(project),
            e,
            exc_info=True,
        )
        return f"获取任务列表失败: {str(e)}"
    except Exception as e:
        error_msg = _extract_safe_error_message(e)
        if _should_expose_error(error_msg):
            return f"获取任务列表失败: {_mask_sensitive_in_error(error_msg)}"
        logger.critical(
            "Unexpected error getting tasks: project=%s, error=%s",
            _mask_project(project),
            e,
            exc_info=True,
        )
        return "获取任务列表失败: 系统内部错误"


@mcp.tool()
@with_user_context
async def get_task_detail(
    issue_id: int,
    project: Optional[str] = None,
    work_item_type: Optional[str] = None,
    user_key: Optional[str] = None,
) -> str:
    """
    获取单个工作项的完整详情。

    当你需要查看工作项的所有字段信息时使用此工具。
    返回的详情包含所有可用字段（包括自定义字段）。
    用户相关字段（如负责人、创建者等）会自动转换为人名以提高可读性。

    Args:
        issue_id: 工作项 ID，必填。
        project: 项目标识符（可选）。可以是:
                - 项目名称（如 "SR6D2VA-7552-Lark"）
                - project_key（如 "project_xxx"）
                如不指定，则使用环境变量 FEISHU_PROJECT_KEY 配置的默认项目。
        work_item_type: 工作项类型名称（可选），如 "需求管理"、"Issue管理"、"项目管理" 等。
                       如不指定，默认使用项目中的第一个可用类型。
        user_key: (可选) 飞书用户标识符 (X-USER-KEY)，用于以特定用户身份进行操作。

    Returns:
        JSON 格式的完整工作项详情。
        失败时返回错误信息。

    Examples:
        # 获取工作项详情（使用默认项目）
        get_task_detail(issue_id=12345)

        # 指定项目和工作项类型
        get_task_detail(
            issue_id=12345,
            project="SR6D2VA-7552-Lark",
            work_item_type="Issue管理"
        )
    """
    try:
        logger.info(
            "Getting task detail: project=%s, work_item_type=%s, issue_id=%s",
            _mask_project(project),
            work_item_type,
            issue_id,
        )
        provider = _create_provider(project, work_item_type)
        detail = await provider.get_readable_issue_details(issue_id)

        logger.info("Retrieved task detail successfully: issue_id=%s", issue_id)
        return json.dumps(detail, ensure_ascii=False, indent=2)
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.error(
            "Failed to get task detail: issue_id=%s, error=%s",
            issue_id,
            e,
            exc_info=True,
        )
        return f"获取工作项详情失败: {str(e)}"
    except Exception as e:
        error_msg = _extract_safe_error_message(e)
        if _should_expose_error(error_msg):
            return f"获取工作项详情失败: {_mask_sensitive_in_error(error_msg)}"
        logger.critical(
            "Unexpected error getting task detail: issue_id=%s, error=%s",
            issue_id,
            e,
            exc_info=True,
        )
        return "获取工作项详情失败: 系统内部错误"


@mcp.tool()
@with_user_context
async def update_task(
    issue_id: int,
    project: Optional[str] = None,
    work_item_type: Optional[str] = None,
    name: Optional[str] = None,
    priority: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    assignee: Optional[str] = None,
    field_name: Optional[str] = None,
    field_value: Optional[str] = None,
    fields_json: Optional[str] = None,
    user_key: Optional[str] = None,
) -> str:
    """
    更新工作项的字段。

    可以同时更新多个字段，这些字段可以通过 fields_json 一次性传入。

    Args:
        issue_id: 要更新的工作项 ID。
        project: 项目标识符（可选）。
        work_item_type: 工作项类型名称（可选）。
        name: 新标题（可选）。
        priority: 新优先级（可选）。
        description: 新描述（可选）。
        status: 新状态（可选）。
        assignee: 新负责人（可选）。
        field_name: 单个自定义字段名称（可选）。
        field_value: 单个自定义字段值（可选）。
        fields_json: JSON 格式的字段字典（可选），用于批量更新多个自定义字段。
                     例如: '{"Soc Vendor": "Amlogic", "DDR 大小": "128MB"}'
        user_key: (可选) 飞书用户标识符 (X-USER-KEY)，用于以特定用户身份进行操作。

    Returns:
        成功时返回 "更新成功"。
    """
    try:
        # 构建 extra_fields
        extra_fields = {}
        if field_name and field_value is not None:
            extra_fields[field_name] = field_value

        if fields_json:
            try:
                json_fields = json.loads(fields_json)
                if isinstance(json_fields, dict):
                    extra_fields.update(json_fields)
                else:
                    return "更新失败: fields_json 必须是 JSON 对象"
            except json.JSONDecodeError:
                return "更新失败: fields_json 格式错误"

        if not extra_fields:
            extra_fields = None

        logger.info(
            "Updating task: project=%s, work_item_type=%s, issue_id=%s, has_name=%s, priority=%s, status=%s, has_assignee=%s, extra_fields_keys=%s",
            _mask_project(project),
            work_item_type,
            issue_id,
            bool(name),
            priority,
            status,
            bool(assignee),
            list(extra_fields.keys()) if extra_fields else [],
        )
        provider = _create_provider(project, work_item_type)
        results = await provider.update_issue(
            issue_id=issue_id,
            name=name,
            priority=priority,
            description=description,
            status=status,
            assignee=assignee,
            extra_fields=extra_fields,
        )

        if not results:
            return _error_response("更新任务", "未提供任何有效字段进行更新", "ERR_NO_FIELDS")

        # 统计结果
        success_count = sum(1 for r in results if r.success)
        total_count = len(results)

        # 序列化结果以便返回
        serialized_results = [
            {"field": r.field_name, "success": r.success, "message": r.message}
            for r in results
        ]

        if success_count == total_count:
            logger.info("Task updated successfully: issue_id=%s", issue_id)
            return _success_response(
                data={"issue_id": issue_id, "results": serialized_results},
                message=f"更新成功，共 {total_count} 个字段",
            )
        elif success_count > 0:
            logger.warning(
                "Task partially updated: issue_id=%s, %d/%d success",
                issue_id,
                success_count,
                total_count,
            )
            return _success_response(
                data={"issue_id": issue_id, "results": serialized_results},
                message=f"部分更新成功: {success_count}/{total_count} 个字段成功",
            )
        else:
            logger.error("Task update failed: issue_id=%s, all fields failed", issue_id)
            # 如果全部失败，构建更详细的错误信息
            fail_reasons = "; ".join([r.message for r in results if not r.success])
            return _error_response(
                operation="更新任务",
                error_msg=f"更新全部失败 (0/{total_count} 成功): {fail_reasons}",
                error_code="ERR_UPDATE_FAILED",
            )
    except (httpx.HTTPError, ValueError, KeyError) as e:
        error_detail = str(e)
        # 尝试提取更详细的 HTTP 错误响应体
        if isinstance(e, httpx.HTTPStatusError) and e.response is not None:
            try:
                err_json = e.response.json()
                if isinstance(err_json, dict) and "err_msg" in err_json:
                    # 飞书通常返回 {"err_msg": "...", "err": {"msg": "..."}}
                    api_msg = err_json.get("err_msg")
                    inner_msg = err_json.get("err", {}).get("msg")
                    full_msg = f"{api_msg}: {inner_msg}" if inner_msg else api_msg
                    error_detail = f"{e}; API Error: {full_msg}"
                else:
                    error_detail = f"{e}; Body: {e.response.text}"
            except Exception:
                # 如果解析失败，保留原始错误
                pass
        elif isinstance(e, ValueError) and "无法更新字段" in str(e):
            # 如果是自定义字段解析失败，提取更简洁的错误信息
            match = re.search(r"无法更新字段 '(.*?)': (.*)", str(e))
            if match:
                field_name = match.group(1)
                reason = match.group(2)
                error_detail = f"无法更新字段 '{field_name}': {reason}"
            else:
                error_detail = str(e)

        logger.error(
            "Failed to update task: project=%s, issue_id=%s, error=%s",
            _mask_project(project),
            issue_id,
            error_detail,
            exc_info=True,
        )
        return f"更新失败: {error_detail}"
    except Exception as e:
        error_msg = _extract_safe_error_message(e)
        if _should_expose_error(error_msg):
            return f"更新失败: {_mask_sensitive_in_error(error_msg)}"
        logger.critical(
            "Unexpected error updating task: project=%s, issue_id=%s, error=%s",
            _mask_project(project),
            issue_id,
            _extract_safe_error_message(e),
            exc_info=True,
        )
        return "更新失败: 系统内部错误"


@mcp.tool()
@with_user_context
async def batch_update_tasks(
    issue_ids: Optional[List[int]] = None,
    issue_id: Optional[int] = None,
    project: Optional[str] = None,
    work_item_type: Optional[str] = None,
    name: Optional[str] = None,
    priority: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    assignee: Optional[str] = None,
    field_name: Optional[str] = None,
    field_value: Optional[str] = None,
    user_key: Optional[str] = None,
) -> str:
    """批量更新工作项字段（支持单个或多个工作项）。

    Args:
        issue_ids: 要更新的工作项 ID 列表。
        issue_id: 单个工作项 ID（与 issue_ids 二选一，方便单项操作）。
        project: 项目标识符（名称或 Key）。
        work_item_type: 工作项类型名称。
        name: 新标题。
        priority: 新优先级（如 P0, P1, P2）。
        description: 新描述。
        status: 新状态。
        assignee: 新负责人（姓名或邮箱）。
        field_name: 自定义字段名称，需配合 field_value 使用。
        field_value: 自定义字段值。
        user_key: (可选) 飞书用户标识符 (X-USER-KEY)，用于以特定用户身份进行操作。

    Returns:
        JSON 格式结果，包含 success 状态和后台任务 ID 列表。
    """
    try:
        # 合并并去重（保持插入顺序）
        combined = (issue_ids or []) + ([issue_id] if issue_id is not None else [])
        target_ids = list(dict.fromkeys(combined))

        if not target_ids:
            return json.dumps(
                {"success": False, "error": "必须提供 issue_ids 或 issue_id"},
                ensure_ascii=False,
            )

        extra_fields = (
            {field_name: field_value}
            if field_name and field_value is not None
            else None
        )

        logger.info(
            "Batch updating tasks: project=%s, count=%d, fields=[name=%s, priority=%s, status=%s, assignee=%s]",
            _mask_project(project),
            len(target_ids),
            bool(name),
            priority,
            status,
            bool(assignee),
        )

        provider = _create_provider(project, work_item_type)
        results = await provider.batch_update_issues(
            issue_ids=target_ids,
            name=name,
            priority=priority,
            description=description,
            status=status,
            assignee=assignee,
            extra_fields=extra_fields,
        )

        logger.info("Batch update completed: %d results", len(results))

        # 序列化 UpdateResult 对象为字典
        serialized_results = [
            {
                "success": r.success,
                "issue_id": r.issue_id,
                "field_name": r.field_name,
                "message": r.message,
            }
            for r in results
        ]

        # 统计成功操作数
        success_count = sum(1 for r in results if r.success)

        return json.dumps(
            {
                "success": True,
                "message": f"批量更新完成，成功 {success_count}/{len(results)} 个操作",
                "data": {
                    "results": serialized_results,
                    "issue_count": len(target_ids),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.error(
            "Failed to batch update tasks: project=%s, error=%s",
            _mask_project(project),
            e,
            exc_info=True,
        )
        return f"批量更新失败: {str(e)}"
    except Exception as e:
        error_msg = _extract_safe_error_message(e)
        if _should_expose_error(error_msg):
            return f"批量更新失败: {_mask_sensitive_in_error(error_msg)}"
        logger.critical(
            "Unexpected error batch updating tasks: project=%s, error=%s",
            _mask_project(project),
            e,
            exc_info=True,
        )
        return "批量更新失败: 系统内部错误"


@mcp.tool()
@with_user_context
async def get_task_options(
    field_name: str,
    project: Optional[str] = None,
    work_item_type: Optional[str] = None,
    user_key: Optional[str] = None,
) -> str:
    """
    获取字段的可用选项列表。

    当你不确定某个字段有哪些可选值时，使用此工具查询。
    这对于了解状态流转、优先级选项等非常有用。

    Args:
        field_name: 字段名称，如 "status", "priority"。
        project: 项目标识符（可选）。可以是项目名称或 project_key。
                如不指定，则使用环境变量 FEISHU_PROJECT_KEY 配置的默认项目。
        work_item_type: 工作项类型名称（可选），如 "需求管理"、"Issue管理"、"项目管理" 等。
                       如不指定，默认使用项目中的第一个可用类型。
        user_key: (可选) 飞书用户标识符 (X-USER-KEY)，用于以特定用户身份进行操作。

    Returns:
        JSON 格式的选项列表，格式为 {label: value}。
        失败时返回错误信息。

    Examples:
        # 查看状态字段有哪些可选值（使用默认项目）
        get_task_options(field_name="status")

        # 查看优先级字段有哪些可选值
        get_task_options(field_name="priority")

        # 指定工作项类型查看选项
        get_task_options(field_name="status", project="Project Management", work_item_type="需求管理")
    """
    try:
        logger.info(
            "Getting task options: project=%s, work_item_type=%s, field_name=%s",
            _mask_project(project),
            work_item_type,
            field_name,
        )
        provider = _create_provider(project, work_item_type)
        options = await provider.list_available_options(field_name)

        logger.info("Retrieved %d options for field '%s'", len(options), field_name)
        return json.dumps(
            {"field": field_name, "options": options},
            ensure_ascii=False,
            indent=2,
        )
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.error(
            "Failed to get options: project=%s, field_name=%s, error=%s",
            _mask_project(project),
            field_name,
            e,
            exc_info=True,
        )
        return f"获取选项失败: {str(e)}"
    except Exception as e:
        error_msg = _extract_safe_error_message(e)
        if _should_expose_error(error_msg):
            return f"获取选项失败: {_mask_sensitive_in_error(error_msg)}"
        logger.critical(
            "Unexpected error getting options: project=%s, field_name=%s, error=%s",
            _mask_project(project),
            field_name,
            e,
            exc_info=True,
        )
        return "获取选项失败: 系统内部错误"


def main():
    """
    MCP Server 入口点

    用于通过 uv tool install 安装后的命令行调用
    """
    # 日志已在模块级别配置，这里只需要记录启动信息
    logger.info("Starting MCP Server (Lark Agent)")
    logger.info("Log level: %s", settings.LOG_LEVEL)

    # 检查日志输出位置
    root_logger = logging.getLogger()
    handlers = root_logger.handlers
    if handlers:
        handler = handlers[0]
        if isinstance(handler, logging.FileHandler):
            logger.info("Logging to file: %s", handler.baseFilename)
        elif isinstance(handler, logging.StreamHandler):
            logger.info(
                "Logging to stream: %s",
                handler.stream.name if hasattr(handler.stream, "name") else "stderr",
            )

    # 运行 MCP server
    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("MCP Server stopped by user")
    except Exception as e:
        logger.critical("MCP Server crashed: %s", e, exc_info=True)
        raise


if __name__ == "__main__":
    main()
