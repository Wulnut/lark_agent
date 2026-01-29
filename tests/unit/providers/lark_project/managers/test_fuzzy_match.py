
import pytest
from src.providers.lark_project.managers.metadata_manager import MetadataManager

class TestFuzzyMatch:
    """测试模糊匹配逻辑"""

    def setup_method(self):
        self.manager = MetadataManager()
        # 模拟选项映射 {label: value}
        self.options = {
            "512 MB": "val_512mb",
            "1 GB": "val_1gb",
            "2 GB": "val_2gb",
            "32 GB": "val_32gb",
            "512 GB": "val_512gb",
            "1 TB": "val_1tb",
            "进行中": "val_doing",
            "待处理": "val_todo"
        }

    def test_exact_match(self):
        """测试精确匹配（虽然主要逻辑在 get_option_value，但 fuzzy match 也可以处理归一化情况）"""
        # 注意：MetadataManager._fuzzy_match_option 负责处理归一化后的匹配
        assert self.manager._fuzzy_match_option("32 GB", self.options) == "val_32gb"

    def test_case_insensitive_match(self):
        """测试忽略大小写和空格"""
        assert self.manager._fuzzy_match_option("32gb", self.options) == "val_32gb"
        assert self.manager._fuzzy_match_option("32 GB", self.options) == "val_32gb"
        assert self.manager._fuzzy_match_option("32Gb", self.options) == "val_32gb"

    def test_unit_completion(self):
        """测试单位补全"""
        assert self.manager._fuzzy_match_option("32g", self.options) == "val_32gb"
        assert self.manager._fuzzy_match_option("512g", self.options) == "val_512gb"
        assert self.manager._fuzzy_match_option("1t", self.options) == "val_1tb"
        # 即使输入是大写 G
        assert self.manager._fuzzy_match_option("32G", self.options) == "val_32gb"

    def test_unique_substring(self):
        """测试唯一子串匹配"""
        # "1" 同时出现在 "1 GB" 和 "1 TB" 中 -> 歧义，应返回 None
        assert self.manager._fuzzy_match_option("1", self.options) is None

        # "32" 只出现在 "32 GB" 中 -> 匹配成功
        assert self.manager._fuzzy_match_option("32", self.options) == "val_32gb"

        # "进行" 只出现在 "进行中" 中
        assert self.manager._fuzzy_match_option("进行", self.options) == "val_doing"

    def test_no_match(self):
        """测试无匹配情况"""
        assert self.manager._fuzzy_match_option("999 GB", self.options) is None
        assert self.manager._fuzzy_match_option("xyz", self.options) is None
