"""
Author: liangyz liangyz@seirobotics.net
Date: 2026-01-12 15:48:38
LastEditors: liangyz liangyz@seirobotics.net
LastEditTime: 2026-01-27 12:42:57
FilePath: /lark_agent/main.py
Description:
    Lark Agent MCP Server 入口点

    支持同时启动:
    1. MCP Server (Stdio模式，供 Cursor/Claude 等调用) - 运行在主进程
    2. HTTP Server (API模式，供 n8n 等调用) - 运行在子进程
"""

import multiprocessing
from multiprocessing.synchronize import Event
import sys
import logging
from src.mcp_server import main as run_mcp_server
from src.http_server import main as run_http_server

# 配置日志
logger = logging.getLogger(__name__)

# HTTP 服务启动超时时间（秒）
HTTP_STARTUP_TIMEOUT = 5.0


def start_http_service(ready_event: Event | None = None):
    """
    在独立进程中启动 HTTP 服务
    
    Args:
        ready_event: 可选的 Event 对象，用于通知主进程服务已就绪
    """
    try:
        # 标记为就绪（在 uvicorn 启动前设置，因为 uvicorn.run 是阻塞的）
        # 注意：这只能表明进程启动成功，不能保证端口绑定成功
        if ready_event is not None:
            ready_event.set()
        
        # HTTP Server 内部使用 uvicorn.run，它是阻塞的
        run_http_server()
    except Exception as e:
        # 确保日志输出到 stderr，避免干扰 stdout (因为 stdout 是 MCP 的通信通道)
        sys.stderr.write(f"HTTP Server process failed: {e}\n")


def main():
    """主入口"""
    # 创建 Event 用于子进程就绪通知
    http_ready = multiprocessing.Event()
    
    # 1. 启动 HTTP Server (后台子进程)
    # 使用 name 方便调试，daemon=True 确保主进程退出时子进程也会被清理
    http_process = multiprocessing.Process(
        target=start_http_service,
        args=(http_ready,),
        name="Lark-HTTP-Server"
    )
    http_process.daemon = True
    http_process.start()
    
    # 等待子进程就绪或超时
    if not http_ready.wait(timeout=HTTP_STARTUP_TIMEOUT):
        sys.stderr.write(
            f"警告: HTTP Server 未能在 {HTTP_STARTUP_TIMEOUT} 秒内启动，继续启动 MCP Server\n"
        )
    
    # 检查子进程是否仍在运行
    if not http_process.is_alive():
        sys.stderr.write("警告: HTTP Server 进程已退出，可能启动失败\n")
    
    # 2. 启动 MCP Server (主进程，阻塞)
    # MCP Server 必须运行在主进程以正确处理标准输入输出 (Stdio)
    try:
        run_mcp_server()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.critical(f"MCP Server crashed: {e}", exc_info=True)
    finally:
        # 清理子进程
        if http_process.is_alive():
            http_process.terminate()
            http_process.join(timeout=1.0)

if __name__ == "__main__":
    # 设置启动方法为 spawn
    # 在 macOS/Windows 上是默认的，但在 Linux 上如果是 fork 可能会导致单例/锁继承问题
    # 显式设置 spawn 可以确保子进程拥有全新的内存空间，避免 MetadataManager 的 Lock 问题
    try:
        multiprocessing.set_start_method('spawn')
    except RuntimeError:
        pass
        
    main()
