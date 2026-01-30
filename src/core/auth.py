"""
Author: liangyz liangyz@seirobotics.net
Date: 2026-01-12 17:56:08
LastEditors: liangyz liangyz@seirobotics.net
LastEditTime: 2026-01-15 21:46:00
FilePath: /lark_agent/src/core/auth.py
"""

import logging
import time
from typing import Optional

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

# HTTP 请求超时配置（秒）
HTTP_TIMEOUT = 10.0


def _mask_token(token: str, visible_chars: int = 4) -> str:
    """对 token 进行脱敏处理，仅显示前几个字符"""
    if not token or len(token) <= visible_chars:
        return "***"
    return f"{token[:visible_chars]}***"


class AuthManager:
    def __init__(self):
        self._plugin_token: Optional[str] = None
        self._expiry_time: float = 0
        self.base_url = settings.FEISHU_PROJECT_BASE_URL

    def _clear_token_cache(self) -> None:
        """清空 token 缓存"""
        self._plugin_token = None
        self._expiry_time = 0
        logger.debug("Token cache cleared")

    async def get_plugin_token(self) -> Optional[str]:
        """
        Get a valid plugin token.
        Returns the manually configured token if present,
        otherwise fetches and caches a new one using plugin credentials.

        Returns:
            Plugin token string, or None if authentication fails.

        Raises:
            None - 所有异常都会被捕获并返回 None
        """
        # 1. Check if a static token is provided (backward compatibility)
        if settings.FEISHU_PROJECT_USER_TOKEN:
            # 安全警告：静态令牌无法检查过期状态，可能导致服务不可用
            logger.warning(
                "Using static FEISHU_PROJECT_USER_TOKEN. "
                "Token expiration cannot be verified - if API calls fail, "
                "please check if the token has expired."
            )
            return settings.FEISHU_PROJECT_USER_TOKEN

        # 2. Check if plugin credentials are provided
        if (
            not settings.FEISHU_PROJECT_PLUGIN_ID
            or not settings.FEISHU_PROJECT_PLUGIN_SECRET
        ):
            logger.error(
                "No Feishu Project authentication credentials found (Token or Plugin ID/Secret)"
            )
            return None

        # 3. Check cache
        if self._plugin_token and time.time() < self._expiry_time:
            logger.debug(
                "Using cached token (expires in %.0f seconds)",
                self._expiry_time - time.time(),
            )
            return self._plugin_token

        # 4. Fetch new token from API
        try:
            async with httpx.AsyncClient(
                trust_env=False, timeout=httpx.Timeout(HTTP_TIMEOUT)
            ) as client:
                url = f"{self.base_url}/open_api/authen/plugin_token"
                payload = {
                    "plugin_id": settings.FEISHU_PROJECT_PLUGIN_ID,
                    "plugin_secret": settings.FEISHU_PROJECT_PLUGIN_SECRET,
                }
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()

                # 调试：打印响应状态（不打印完整响应体，避免泄露 token）
                logger.debug(
                    "Plugin token API response: code=%s, has_data=%s",
                    data.get("code"),
                    "data" in data,
                )

                # 检查响应格式：可能是 {"code": 0, "data": {...}} 或直接返回 token
                code = data.get("code")
                if code is not None and code != 0:
                    logger.error(
                        "Auth failed: %s (code %d)",
                        data.get("msg", "Unknown error"),
                        code,
                    )
                    self._clear_token_cache()
                    return None

                # The response structure based on common Lark patterns:
                # { "code": 0, "data": { "plugin_token": "...", "expire": 7200 } }
                # 或者直接返回: { "plugin_token": "...", "expire": 7200 }
                auth_data = data.get("data", data)
                self._plugin_token = auth_data.get("plugin_token") or auth_data.get(
                    "token"
                )

                if not self._plugin_token:
                    logger.error(
                        "Plugin token not found in response. Response keys: %s",
                        list(data.keys()),
                    )
                    self._clear_token_cache()
                    return None

                # Buffer of 60 seconds
                expires_in = (
                    auth_data.get("expire") or auth_data.get("expire_time") or 7200
                )
                self._expiry_time = time.time() + expires_in - 60

                # 脱敏日志：仅显示 token 前 4 位
                logger.info(
                    "Successfully refreshed Feishu Project plugin token: %s (expires in %d seconds)",
                    _mask_token(self._plugin_token),
                    expires_in,
                )
                return self._plugin_token

        except httpx.TimeoutException as e:
            logger.error(
                "Plugin token request timed out after %.1f seconds: %s", HTTP_TIMEOUT, e
            )
            self._clear_token_cache()
            return None
        except httpx.HTTPStatusError as e:
            logger.error(
                "Plugin token request failed with HTTP status %d: %s",
                e.response.status_code,
                e,
            )
            self._clear_token_cache()
            return None
        except httpx.RequestError as e:
            logger.error("Plugin token request failed (network error): %s", e)
            self._clear_token_cache()
            return None
        except (ValueError, KeyError) as e:
            logger.error("Plugin token response parsing failed: %s", e)
            self._clear_token_cache()
            return None


# Singleton instance
auth_manager = AuthManager()
