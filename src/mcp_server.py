"""
Author: liangyz liangyz@seirobotics.net
Date: 2026-01-12 15:48:38
LastEditors: liangyz liangyz@seirobotics.net
LastEditTime: 2026-01-14 12:44:01
FilePath: /feishu_agent/src/mcp_server.py
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
from typing import Optional

import httpx

from mcp.server.fastmcp import FastMCP

from src.core.config import settings
from src.providers.project.managers import MetadataManager
from src.providers.project.work_item_provider import WorkItemProvider


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

    替换可能暴露内部实现的敏感标识符，如 project_key、user_key 等。

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
    return error_msg


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


def _is_project_key_format(identifier: str) -> bool:
    """判断是否为 project_key 格式（以 'project_' 开头）"""
    return bool(identifier and identifier.startswith("project_"))


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
    if not project:
        # 使用默认项目（从环境变量读取）
        logger.debug("Using default project from FEISHU_PROJECT_KEY")
        if work_item_type:
            return WorkItemProvider(work_item_type_name=work_item_type)
        return WorkItemProvider()

    if _is_project_key_format(project):
        logger.debug("Treating '%s' as project_key", project)
        if work_item_type:
            return WorkItemProvider(
                project_key=project, work_item_type_name=work_item_type
            )
        return WorkItemProvider(project_key=project)
    else:
        # 当作项目名称处理
        logger.debug("Treating '%s' as project_name", project)
        if work_item_type:
            return WorkItemProvider(
                project_name=project, work_item_type_name=work_item_type
            )
        return WorkItemProvider(project_name=project)


@mcp.tool()
async def list_projects() -> str:
    """
    列出所有可用的飞书项目空间。

    当你不知道项目的 project_key 时，先调用此工具获取项目列表。
    返回的列表包含项目名称和对应的 project_key。

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
async def create_task(
    name: str,
    project: Optional[str] = None,
    work_item_type: Optional[str] = None,
    priority: str = "P2",
    description: str = "",
    assignee: Optional[str] = None,
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
        work_item_type: 工作项类型名称（可选），如 "需求管理"、"Issue管理"、"项目管理" 等。
                       如不指定，默认使用项目中的第一个可用类型。
        priority: 优先级，可选值: P0(最高), P1, P2(默认), P3(最低)。
        description: 工作项描述，支持纯文本。
        assignee: 负责人的姓名或邮箱。如不指定则为空。

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
                return str(e)

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
            page_size=min(page_size, 100),
        )

        # 确保 result 是字典类型
        if not isinstance(result, dict):
            logger.error("Unexpected result type: %s, value: %s", type(result), result)
            return "获取任务列表失败: 返回数据格式错误"

        # 简化返回结果
        simplified = provider.simplify_work_items(result.get("items", []))

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
async def get_task_detail(
    issue_id: int,
    project: Optional[str] = None,
    work_item_type: Optional[str] = None,
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
            "Getting task detail: project=%s, work_item_type=%s, issue_id=%d",
            _mask_project(project),
            work_item_type,
            issue_id,
        )
        provider = _create_provider(project, work_item_type)
        detail = await provider.get_readable_issue_details(issue_id)

        logger.info("Retrieved task detail successfully: issue_id=%d", issue_id)
        return json.dumps(detail, ensure_ascii=False, indent=2)
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.error(
            "Failed to get task detail: issue_id=%d, error=%s",
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
            "Unexpected error getting task detail: issue_id=%d, error=%s",
            issue_id,
            e,
            exc_info=True,
        )
        return "获取工作项详情失败: 系统内部错误"


@mcp.tool()
async def update_task(
    issue_id: int,
    project: Optional[str] = None,
    work_item_type: Optional[str] = None,
    name: Optional[str] = None,
    priority: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    assignee: Optional[str] = None,
) -> str:
    """
    更新工作项的字段。

    可以同时更新多个字段，只需提供要更新的字段值即可。
    未提供的字段将保持不变。

    Args:
        issue_id: 要更新的工作项 ID。
        project: 项目标识符（可选）。可以是项目名称或 project_key。
                如不指定，则使用环境变量 FEISHU_PROJECT_KEY 配置的默认项目。
        work_item_type: 工作项类型名称（可选），如 "需求管理"、"Issue管理"、"项目管理" 等。
                       如不指定，默认使用项目中的第一个可用类型。
        name: 新标题（可选）。
        priority: 新优先级（可选），如 "P0", "P1" 等。
        description: 新描述（可选）。
        status: 新状态（可选），如 "进行中", "已完成" 等。
        assignee: 新负责人（可选），姓名或邮箱。

    Returns:
        成功时返回 "更新成功"。
        失败时返回错误信息。

    Examples:
        # 将任务标记为进行中（使用默认项目）
        update_task(issue_id=12345, status="进行中")

        # 提升任务优先级并更换负责人
        update_task(issue_id=12345, priority="P0", assignee="李四")

        # 指定工作项类型更新
        update_task(issue_id=12345, work_item_type="需求管理", status="已完成")
    """
    try:
        logger.info(
            "Updating task: project=%s, work_item_type=%s, issue_id=%d, has_name=%s, priority=%s, status=%s, has_assignee=%s",
            _mask_project(project),
            work_item_type,
            issue_id,
            bool(name),
            priority,
            status,
            bool(assignee),
        )
        provider = _create_provider(project, work_item_type)
        await provider.update_issue(
            issue_id=issue_id,
            name=name,
            priority=priority,
            description=description,
            status=status,
            assignee=assignee,
        )
        logger.info("Task updated successfully: issue_id=%d", issue_id)
        return f"更新成功，Issue ID: {issue_id}"
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.error(
            "Failed to update task: project=%s, issue_id=%d, error=%s",
            _mask_project(project),
            issue_id,
            e,
            exc_info=True,
        )
        return f"更新失败: {str(e)}"
    except Exception as e:
        error_msg = _extract_safe_error_message(e)
        if _should_expose_error(error_msg):
            return f"更新失败: {_mask_sensitive_in_error(error_msg)}"
        logger.critical(
            "Unexpected error updating task: project=%s, issue_id=%d, error=%s",
            _mask_project(project),
            issue_id,
            e,
            exc_info=True,
        )
        return "更新失败: 系统内部错误"


@mcp.tool()
async def get_task_options(
    field_name: str,
    project: Optional[str] = None,
    work_item_type: Optional[str] = None,
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
