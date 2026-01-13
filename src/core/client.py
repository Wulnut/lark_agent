"""
Author: liangyz liangyz@seirobotics.net
Date: 2026-01-12 15:48:30
LastEditors: liangyz liangyz@seirobotics.net
LastEditTime: 2026-01-13 23:54:53
FilePath: /feishu_agent/src/core/client.py
"""

import logging

import lark_oapi as lark

from src.core.config import settings

logger = logging.getLogger(__name__)

_lark_client = None


def get_lark_client():
    global _lark_client
    if not _lark_client:
        logger.info("Initializing Lark client with app_id=%s", settings.LARK_APP_ID)
        _lark_client = (
            lark.Client.builder()
            .app_id(settings.LARK_APP_ID)
            .app_secret(settings.LARK_APP_SECRET)
            .log_level(lark.LogLevel.DEBUG)
            .build()
        )
        logger.debug("Lark client initialized successfully")
    else:
        logger.debug("Reusing existing Lark client instance")
    return _lark_client
