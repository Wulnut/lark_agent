"""
API 测试共享 Fixtures

提供 API 测试中通用的 Mock 对象和辅助函数。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock


def create_mock_response(data: dict[str, Any]) -> MagicMock:
    """
    创建模拟 HTTP 响应对象。

    Args:
        data: 响应 JSON 数据

    Returns:
        配置好的 MagicMock 响应对象
    """
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp
