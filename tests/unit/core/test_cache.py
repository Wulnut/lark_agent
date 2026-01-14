"""
SimpleCache 单元测试
"""

import time
import threading
import pytest
from src.core.cache import SimpleCache


class TestSimpleCache:
    """SimpleCache 测试类"""

    def test_set_and_get(self):
        """测试基本的存取功能"""
        cache = SimpleCache(ttl=3600)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent_key(self):
        """测试获取不存在的 key"""
        cache = SimpleCache(ttl=3600)
        assert cache.get("nonexistent") is None

    def test_cache_expiry(self):
        """测试缓存过期"""
        cache = SimpleCache(ttl=1)  # 1秒过期
        cache.set("key1", "value1")

        # 立即获取应该能获取到
        assert cache.get("key1") == "value1"

        # 等待过期
        time.sleep(1.1)

        # 过期后应该返回 None
        assert cache.get("key1") is None

    def test_cache_overwrite(self):
        """测试覆盖已有值"""
        cache = SimpleCache(ttl=3600)
        cache.set("key1", "value1")
        cache.set("key1", "value2")
        assert cache.get("key1") == "value2"

    def test_clear(self):
        """测试清空缓存"""
        cache = SimpleCache(ttl=3600)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_different_value_types(self):
        """测试不同类型的值"""
        cache = SimpleCache(ttl=3600)

        # 字符串
        cache.set("str", "hello")
        assert cache.get("str") == "hello"

        # 数字
        cache.set("int", 123)
        assert cache.get("int") == 123

        # 列表
        cache.set("list", [1, 2, 3])
        assert cache.get("list") == [1, 2, 3]

        # 字典
        cache.set("dict", {"a": 1})
        assert cache.get("dict") == {"a": 1}

        # None - 注意: 无法区分存储的 None 值和 key 不存在/已过期
        cache.set("none", None)
        assert cache.get("none") is None

    def test_default_ttl(self):
        """测试默认 TTL"""
        cache = SimpleCache()  # 默认 3600 秒
        assert cache.ttl == 3600

    # =========================================================================
    # 边界条件测试
    # =========================================================================

    def test_empty_string_key(self):
        """测试空字符串作为 key"""
        cache = SimpleCache(ttl=3600)
        cache.set("", "value")
        assert cache.get("") == "value"

    def test_very_long_key(self):
        """测试超长 key"""
        cache = SimpleCache(ttl=3600)
        long_key = "k" * 10000
        cache.set(long_key, "value")
        assert cache.get(long_key) == "value"

    def test_unicode_key(self):
        """测试 Unicode key"""
        cache = SimpleCache(ttl=3600)
        cache.set("中文键", "中文值")
        assert cache.get("中文键") == "中文值"
        cache.set("🔑", "emoji_value")
        assert cache.get("🔑") == "emoji_value"

    def test_concurrent_access(self):
        """测试并发访问安全性"""
        cache = SimpleCache(ttl=3600)
        errors = []

        def writer():
            try:
                for i in range(100):
                    cache.set(f"key_{i}", i)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(100):
                    cache.get(f"key_{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 应该没有任何异常
        assert errors == []

    def test_zero_ttl(self):
        """测试 TTL 为 0 时立即过期"""
        cache = SimpleCache(ttl=0)
        cache.set("key", "value")
        # TTL=0 意味着立即过期
        assert cache.get("key") is None

    def test_large_value(self):
        """测试存储大对象"""
        cache = SimpleCache(ttl=3600)
        large_list = list(range(100000))
        cache.set("large", large_list)
        assert cache.get("large") == large_list
