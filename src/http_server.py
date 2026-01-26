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
from typing import Any, Callable, Awaitable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.core.config import settings

# 配置日志
logging.basicConfig(level=settings.get_log_level())
logger = logging.getLogger(__name__)


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
    lifespan=lifespan
)


async def call_mcp_tool(tool_name: str, parameters: dict[str, Any]) -> Any:
    """
    调用 MCP 工具

    Args:
        tool_name: 工具名称
        parameters: 工具参数

    Returns:
        工具执行结果

    Raises:
        ValueError: 工具不存在或参数错误
        Exception: 工具执行异常
    """
    try:
        logger.info(f"Calling MCP tool: {tool_name} with params: {parameters}")

        # 从注册表获取工具
        registry = get_tool_registry()
        tool_def = registry.get(tool_name)
        
        if tool_def is None:
            available = list(registry.keys())
            raise ValueError(f"不支持的工具: {tool_name}。支持的工具: {available}")
        
        # 调用工具函数
        result = await tool_def.func(**parameters)

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

    请求体示例:
    {
        "tool_name": "list_projects",
        "parameters": {}
    }

    或

    {
        "tool_name": "create_task",
        "parameters": {
            "name": "测试任务",
            "project": "my_project",
            "priority": "P1"
        }
    }
    """
    try:
        # 从注册表获取可用工具列表
        registry = get_tool_registry()
        
        if request.tool_name not in registry:
            allowed_tools = list(registry.keys())
            raise HTTPException(
                status_code=400,
                detail=f"不支持的工具: {request.tool_name}。支持的工具: {allowed_tools}"
            )

        # 调用 MCP 工具
        result = await call_mcp_tool(request.tool_name, request.parameters)

        return ToolCallResponse(success=True, data=result)

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Internal error: {e}", exc_info=True)
        return ToolCallResponse(
            success=False,
            error=f"调用工具失败: {str(e)}"
        )


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

    return {
        "tools": tools,
        "count": len(tools)
    }


def main():
    """启动 HTTP 包装器服务器"""
    import uvicorn

    # 启动服务器
    logger.info("Starting HTTP wrapper server on http://localhost:8002")
    logger.info("API docs available at: http://localhost:8002/docs")

    uvicorn.run(
        "src.http_server:app",
        host="0.0.0.0",
        port=8002,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()