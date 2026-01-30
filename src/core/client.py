"""
Author: liangyz liangyz@seirobotics.net
Date: 2026-01-12 15:48:30
LastEditors: liangyz liangyz@seirobotics.net
LastEditTime: 2026-01-15 21:46:00
FilePath: /lark_agent/src/core/client.py
"""

import logging
import threading

import lark_oapi as lark

from src.core.config import settings

logger = logging.getLogger(__name__)

_lark_client = None
_lark_client_lock = threading.Lock()  # 线程安全锁


def _mask_app_id(app_id: str) -> str:
    """对 app_id 进行脱敏处理，仅显示前 4 位"""
    if not app_id or len(app_id) <= 4:
        return "***"
    return f"{app_id[:4]}***"


def get_lark_client():
    """
    获取 Lark 客户端实例（线程安全）

    使用双重检查锁定模式，防止多线程/多协程并发时重复实例化。

    注意：需要配置 LARK_APP_ID 和 LARK_APP_SECRET 环境变量才能使用。
    如果未配置，会抛出 ValueError。

    Returns:
        lark.Client: Lark 客户端实例

    Raises:
        ValueError: 未配置必需的环境变量
    """
    global _lark_client

    # 快速路径：已初始化则直接返回
    if _lark_client is not None:
        logger.debug("Reusing existing Lark client instance")
        return _lark_client

    # 慢路径：使用锁保护初始化
    with _lark_client_lock:
        # 双重检查：防止等待锁期间其他线程已完成初始化
        if _lark_client is not None:
            logger.debug("Reusing existing Lark client instance (after lock)")
            return _lark_client

        if not settings.LARK_APP_ID or not settings.LARK_APP_SECRET:
            raise ValueError(
                "LARK_APP_ID 和 LARK_APP_SECRET 环境变量未配置。"
                "这些字段在使用 IM 功能时是必需的。"
                "请参考文档配置：https://github.com/Wulnut/lark_agent/blob/main/doc/安装使用指南.md"
            )

        # 脱敏日志：仅显示 app_id 前 4 位
        logger.info(
            "Initializing Lark client with app_id=%s",
            _mask_app_id(settings.LARK_APP_ID),
        )
        _lark_client = (
            lark.Client.builder()
            .app_id(settings.LARK_APP_ID)
            .app_secret(settings.LARK_APP_SECRET)
            .log_level(lark.LogLevel.DEBUG)
            .build()
        )
        logger.debug("Lark client initialized successfully")

    return _lark_client
