"""
Author: liangyz liangyz@seirobotics.net
Date: 2026-01-12 17:29:11
LastEditors: liangyz liangyz@seirobotics.net
LastEditTime: 2026-01-13 23:56:11
FilePath: /feishu_agent/src/core/cache.py
"""

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SimpleCache:
    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        logger.debug("SimpleCache initialized with TTL=%d seconds", ttl)

    def set(self, key: str, value: Any):
        expiry_time = time.time() + self.ttl
        self._cache[key] = {"value": value, "expiry": expiry_time}
        logger.debug("Cache set: key=%s, expires_at=%s", key, expiry_time)

    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            logger.debug("Cache miss: key=%s", key)
            return None

        item = self._cache[key]
        current_time = time.time()
        if current_time > item["expiry"]:
            logger.debug(
                "Cache expired: key=%s, expired_at=%s, current_time=%s",
                key,
                item["expiry"],
                current_time,
            )
            del self._cache[key]
            return None

        logger.debug("Cache hit: key=%s", key)
        return item["value"]

    def clear(self):
        cache_size = len(self._cache)
        self._cache.clear()
        logger.info("Cache cleared: removed %d entries", cache_size)
