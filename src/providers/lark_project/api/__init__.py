"""
飞书项目 API 层 - 原子能力封装

该模块提供飞书项目 Open API 的原子接口封装。

层级依赖拓扑:
- L0: ProjectAPI (基础空间接口，无依赖)
- L1: MetadataAPI (依赖 project_key)
- L2: FieldAPI (依赖 project_key, work_item_type_key)
- L3: WorkItemAPI (依赖 project_key, work_item_type_key, field_key 等)
- L-User: UserAPI (用户相关，独立层)

使用示例:
    from src.providers.lark_project.api import ProjectAPI, WorkItemAPI

    project_api = ProjectAPI()
    projects = await project_api.list_projects()

    work_item_api = WorkItemAPI()
    items = await work_item_api.filter(project_key="xxx", work_item_type_keys=["story"])
"""

from .project import ProjectAPI
from .metadata import MetadataAPI
from .field import FieldAPI
from .work_item import WorkItemAPI
from .user import UserAPI

__all__ = [
    "ProjectAPI",
    "MetadataAPI",
    "FieldAPI",
    "WorkItemAPI",
    "UserAPI",
]
