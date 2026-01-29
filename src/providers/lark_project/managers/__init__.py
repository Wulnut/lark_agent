"""
飞书项目 Manager 层 - 业务编排与缓存管理

该模块提供基于原子 API 的高层业务能力封装。

核心组件:
- MetadataManager: 级联缓存管理器，实现 Name -> Key 的多级映射
"""

from .metadata_manager import MetadataManager

__all__ = [
    "MetadataManager",
]
