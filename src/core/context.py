from contextvars import ContextVar
from typing import Optional

# 定义一个 ContextVar 来存储当前请求的 user_key
user_key_context: ContextVar[Optional[str]] = ContextVar("user_key", default=None)
