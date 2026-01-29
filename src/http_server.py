"""
HTTP API 包装器 - 将 MCP Server 包装成 HTTP 服务供 n8n 调用

启动方式:
    python -m src.http_server

API 端点:
    POST /call_tool
    请求体: {"tool_name": "list_projects", "parameters": {...}}
    返回: MCP 工具的执行结果
"""

import json
import logging
import sys
import os
from pathlib import Path
from typing import Any, Callable, Awaitable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# =============================================================================
# 日志配置：Stderr + File
# =============================================================================
# 1. 确保日志目录存在
log_dir = Path("log")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "agent.log"

# 2. 定义 Formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# 3. 定义 Handlers
# Stderr Handler (用于调试，且不污染 stdout)
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setFormatter(formatter)

# File Handler (用于持久化)
file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_handler.setFormatter(formatter)

# 4. 配置 Root Logger
# 先清除现有的 handlers
logging.getLogger().handlers.clear()
logging.basicConfig(
    level=logging.INFO,
    handlers=[stderr_handler, file_handler],
    force=True,  # 强制重新配置
)

# 5. 特别配置 Uvicorn Logger
# 确保 Uvicorn 的日志也去 stderr 和文件，而不是 stdout
for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
    logger_obj = logging.getLogger(logger_name)
    logger_obj.handlers = [stderr_handler, file_handler]
    logger_obj.propagate = False  # 防止双重打印

logger = logging.getLogger(__name__)
logger.info(f"Logging configured. Log file: {log_file.absolute()}")

from src.core.config import settings


# =============================================================================
# 工具注册表 - 集中管理所有可用工具
# =============================================================================
@dataclass
class ToolDefinition:
    """工具定义"""

    name: str
    description: str
    func: Callable[..., Awaitable[str]]


# 延迟导入工具函数，避免循环依赖
def _get_tool_registry() -> dict[str, ToolDefinition]:
    """获取工具注册表（延迟加载）"""
    from src.mcp_server import (
        list_projects,
        create_task,
        get_tasks,
        get_task_detail,
        update_task,
        get_task_options,
        batch_update_tasks,
    )

    return {
        "list_projects": ToolDefinition(
            name="list_projects",
            description="列出所有可用的飞书项目空间",
            func=list_projects,
        ),
        "create_task": ToolDefinition(
            name="create_task",
            description="在指定项目中创建新的工作项",
            func=create_task,
        ),
        "get_tasks": ToolDefinition(
            name="get_tasks",
            description="获取项目中的工作项列表，支持多种过滤条件",
            func=get_tasks,
        ),
        "get_task_detail": ToolDefinition(
            name="get_task_detail",
            description="获取单个工作项的完整详情",
            func=get_task_detail,
        ),
        "update_task": ToolDefinition(
            name="update_task",
            description="更新工作项的字段",
            func=update_task,
        ),
        "batch_update_tasks": ToolDefinition(
            name="batch_update_tasks",
            description="批量更新工作项字段",
            func=batch_update_tasks,
        ),
        "get_task_options": ToolDefinition(
            name="get_task_options",
            description="获取字段的可用选项列表",
            func=get_task_options,
        ),
    }


# 缓存注册表
_tool_registry: dict[str, ToolDefinition] | None = None


def get_tool_registry() -> dict[str, ToolDefinition]:
    """获取工具注册表（带缓存）"""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = _get_tool_registry()
    return _tool_registry


class ToolCallRequest(BaseModel):
    """工具调用请求模型"""

    tool_name: str
    parameters: dict[str, Any] = {}
    user_key: str | None = None


class ToolCallResponse(BaseModel):
    """工具调用响应模型"""

    success: bool
    data: Any = None
    error: str | None = None


# FastAPI 应用
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Starting HTTP wrapper for MCP Server")
    yield
    logger.info("Shutting down HTTP wrapper")


app = FastAPI(
    title="Lark MCP Server HTTP Wrapper",
    description="将飞书 MCP Server 包装成 HTTP API 供外部调用",
    version="0.1.0",
    lifespan=lifespan,
)


def _normalize_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    """
    标准化工具参数类型

    将 JSON 中可能传为字符串的数值参数转换为正确类型。
    """
    # 需要转换为 int 的参数名列表
    int_fields = {"issue_id", "page_num", "page_size"}
    # 列表类型的 int 字段
    list_int_fields = {"issue_ids"}

    normalized = {}
    for key, value in parameters.items():
        if key in int_fields and isinstance(value, str):
            try:
                # 尝试转换，如果是空字符串则忽略（或保持原样，视业务逻辑而定）
                if value.strip():
                    normalized[key] = int(value)
                else:
                    normalized[key] = value
            except ValueError:
                normalized[key] = value
        elif key in list_int_fields and isinstance(value, list):
            # 处理 ID 列表，确保每个元素都是 int
            try:
                normalized[key] = [int(v) for v in value]
            except (ValueError, TypeError):
                normalized[key] = value
        else:
            normalized[key] = value
    return normalized


async def call_mcp_tool(tool_name: str, parameters: dict[str, Any]) -> Any:
    """
    调用 MCP 工具
    """
    try:
        logger.info(f"Calling MCP tool: {tool_name} with params: {parameters}")

        # 从注册表获取工具
        registry = get_tool_registry()
        tool_def = registry.get(tool_name)

        if tool_def is None:
            available = list(registry.keys())
            raise ValueError(f"不支持的工具: {tool_name}。支持的工具: {available}")

        # 标准化参数类型（字符串 -> int 等）
        normalized_params = _normalize_parameters(parameters)

        # 调用工具函数
        result = await tool_def.func(**normalized_params)

        # 解析结果（MCP 工具通常返回字符串）
        if isinstance(result, str):
            try:
                # 尝试解析 JSON 响应
                return json.loads(result)
            except json.JSONDecodeError:
                # 如果不是 JSON，返回原始字符串
                return {"message": result}
        else:
            return result

    except Exception as e:
        logger.error(f"Error calling tool {tool_name}: {e}", exc_info=True)
        raise


@app.post("/call_tool", response_model=ToolCallResponse)
async def call_tool(request: ToolCallRequest):
    """
    调用 MCP 工具的 HTTP 接口
    """
    try:
        # 从注册表获取可用工具列表
        registry = get_tool_registry()

        if request.tool_name not in registry:
            allowed_tools = list(registry.keys())
            raise HTTPException(
                status_code=400,
                detail=f"不支持的工具: {request.tool_name}。支持的工具: {allowed_tools}",
            )

        # 将 user_key 注入到参数中
        if request.user_key:
            request.parameters["user_key"] = request.user_key

        # 调用 MCP 工具
        result = await call_mcp_tool(request.tool_name, request.parameters)

        return ToolCallResponse(success=True, data=result)

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Internal error: {e}", exc_info=True)
        return ToolCallResponse(success=False, error=f"调用工具失败: {str(e)}")


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "service": "lark-mcp-http-wrapper"}


@app.get("/tools")
async def list_available_tools():
    """获取可用工具列表"""
    # 从注册表动态生成工具列表
    registry = get_tool_registry()
    tools = [
        {"name": tool_def.name, "description": tool_def.description}
        for tool_def in registry.values()
    ]

    return {"tools": tools, "count": len(tools)}


def main():
    """启动 HTTP 包装器服务器"""
    import uvicorn

    # 强制将 stdout 重定向到 stderr，防止任何库（如 uvicorn）污染 stdout
    original_stdout = sys.stdout
    sys.stdout = sys.stderr

    logger.info("Starting HTTP wrapper server on http://localhost:8002")

    try:
        # 启动 uvicorn
        # log_config=None 告诉 uvicorn 不要使用默认配置，而是继承我们上面配置好的 logging
        uvicorn.run(
            "src.http_server:app",
            host="0.0.0.0",
            port=8002,
            reload=False,
            log_config=None,
        )
    finally:
        sys.stdout = original_stdout


if __name__ == "__main__":
    main()
