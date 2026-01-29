"""
Author: liangyz liangyz@seirobotics.net
Date: 2026-01-12 17:56:08
LastEditors: liangyz liangyz@seirobotics.net
LastEditTime: 2026-01-13 23:57:21
FilePath: /feishu_agent/src/core/project_client.py
"""

import logging
from typing import Optional

import threading

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.core.auth import auth_manager
from src.core.config import settings
from src.core.context import user_key_context

logger = logging.getLogger(__name__)

_project_client = None
_project_client_lock = threading.Lock()  # 线程安全锁

# 定义可重试的异常类型
RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.ConnectTimeout,
)


def _should_retry_response(response: httpx.Response) -> bool:
    """检查响应是否需要重试（5xx 服务端错误）"""
    return response.status_code >= 500


class RetryableHTTPError(Exception):
    """可重试的 HTTP 错误"""

    def __init__(self, response: httpx.Response):
        self.response = response
        super().__init__(f"HTTP {response.status_code}: {response.text[:200]}")


class TokenError(Exception):
    """Token 获取失败错误（可重试）"""

    pass


class ProjectAuth(httpx.Auth):
    """
    Custom Auth for Feishu Project API.
    Handles dynamic injection of X-PLUGIN-TOKEN and X-USER-KEY.
    """

    async def async_auth_flow(self, request: httpx.Request):
        token = await auth_manager.get_plugin_token()
        if not token:
            # 抛出异常以触发重试
            raise TokenError("Failed to retrieve plugin token")

        request.headers["X-PLUGIN-TOKEN"] = token

        # 优先使用上下文中的 user_key，其次使用配置文件中的
        user_key = user_key_context.get() or settings.FEISHU_PROJECT_USER_KEY
        if user_key:
            request.headers["X-USER-KEY"] = user_key

        yield request


class ProjectClient:
    """
    飞书项目 API 异步客户端

    特性:
    - 自动注入认证头 (X-PLUGIN-TOKEN, X-USER-KEY)
    - 自动重试机制 (网络错误、超时、5xx 错误、认证失败)
    - 指数退避策略
    """

    # 重试配置
    MAX_RETRIES = 3
    RETRY_MIN_WAIT = 1  # 最小等待时间（秒）
    RETRY_MAX_WAIT = 10  # 最大等待时间（秒）

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.FEISHU_PROJECT_BASE_URL
        logger.info("Initializing ProjectClient with base_url=%s", self.base_url)
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Content-Type": "application/json"},
            auth=ProjectAuth(),
            timeout=httpx.Timeout(30.0),  # 30秒超时
            trust_env=False,  # 禁用环境变量代理，避免 socksio 依赖问题
        )
        logger.debug("ProjectClient initialized successfully")

    def _get_retry_decorator(self):
        """获取重试装饰器配置"""
        return retry(
            stop=stop_after_attempt(self.MAX_RETRIES),
            wait=wait_exponential(
                multiplier=1, min=self.RETRY_MIN_WAIT, max=self.RETRY_MAX_WAIT
            ),
            retry=retry_if_exception_type(
                RETRYABLE_EXCEPTIONS + (RetryableHTTPError, TokenError)
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> httpx.Response:
        """
        带重试的请求方法

        Args:
            method: HTTP 方法 (GET, POST, PUT, DELETE)
            path: API 路径
            json: 请求体 (可选)
            params: 查询参数 (可选)

        Returns:
            httpx.Response

        Raises:
            RetryableHTTPError: 5xx 错误（会触发重试）
            httpx.HTTPStatusError: 其他 HTTP 错误
        """

        @self._get_retry_decorator()
        async def _do_request():
            logger.debug("Making %s request to %s", method, path)
            if method == "GET":
                response = await self.client.get(path, params=params)
            elif method == "POST":
                logger.debug("POST payload: %s", json)
                response = await self.client.post(path, json=json)
            elif method == "PUT":
                logger.debug("PUT payload: %s", json)
                response = await self.client.put(path, json=json)
            elif method == "DELETE":
                response = await self.client.delete(path)
            else:
                logger.error("Unsupported HTTP method: %s", method)
                raise ValueError(f"Unsupported HTTP method: {method}")

            logger.debug("Response status: %d from %s", response.status_code, path)

            # 5xx 错误触发重试
            if _should_retry_response(response):
                logger.warning(
                    "Received %d from %s, will retry...", response.status_code, path
                )
                raise RetryableHTTPError(response)

            if response.status_code >= 400:
                logger.error(
                    "HTTP error %d from %s: %s",
                    response.status_code,
                    path,
                    response.text[:200],
                )
            else:
                logger.info(
                    "Request successful: %s %s -> %d",
                    method,
                    path,
                    response.status_code,
                )

            return response

        return await _do_request()

    async def post(self, path: str, json: Optional[dict] = None) -> httpx.Response:
        """POST 请求（带自动重试）"""
        return await self._request_with_retry("POST", path, json=json)

    async def get(self, path: str, params: Optional[dict] = None) -> httpx.Response:
        """GET 请求（带自动重试）"""
        return await self._request_with_retry("GET", path, params=params)

    async def put(self, path: str, json: Optional[dict] = None) -> httpx.Response:
        """PUT 请求（带自动重试）"""
        return await self._request_with_retry("PUT", path, json=json)

    async def delete(self, path: str) -> httpx.Response:
        """DELETE 请求（带自动重试）"""
        return await self._request_with_retry("DELETE", path)

    async def close(self):
        """关闭客户端连接"""
        logger.info("Closing ProjectClient connection")
        await self.client.aclose()
        logger.debug("ProjectClient connection closed")


def get_project_client() -> ProjectClient:
    """
    获取全局单例客户端（线程安全）

    使用双重检查锁定模式，防止多线程/多协程并发时重复实例化。

    Returns:
        ProjectClient: 项目 API 客户端实例
    """
    global _project_client

    # 快速路径：已初始化则直接返回
    if _project_client is not None:
        logger.debug("Reusing existing ProjectClient singleton instance")
        return _project_client

    # 慢路径：使用锁保护初始化
    with _project_client_lock:
        # 双重检查：防止等待锁期间其他线程已完成初始化
        if _project_client is not None:
            logger.debug(
                "Reusing existing ProjectClient singleton instance (after lock)"
            )
            return _project_client

        logger.debug("Creating new ProjectClient singleton instance")
        _project_client = ProjectClient()

    return _project_client
