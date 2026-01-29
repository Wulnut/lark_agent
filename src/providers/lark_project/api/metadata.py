"""
MetadataAPI - L2 原子能力层
负责空间配置相关的原子接口封装

对应 Postman 集合:
- 配置 > 空间配置 > 获取空间下工作项类型: GET /open_api/:project_key/work_item/all-types
- 配置 > 空间配置 > 获取空间下业务线详情: GET /open_api/:project_key/business/all
"""

import logging
from typing import Dict, List, Optional
from src.core.project_client import get_project_client, ProjectClient

logger = logging.getLogger(__name__)


class MetadataAPI:
    """
    飞书项目元数据 API 封装 (L2 - Base API Layer)

    职责: 严格对应 Postman 集合中的空间配置相关原子接口
    依赖: L1 (需要 project_key)
    """

    def __init__(self, client: Optional[ProjectClient] = None):
        self.client = client or get_project_client()

    async def get_work_item_types(self, project_key: str) -> List[Dict]:
        """
        获取空间下工作项类型

        对应 Postman: 配置 > 空间配置 > 获取空间下工作项类型
        API: GET /open_api/:project_key/work_item/all-types

        Args:
            project_key: 项目空间 Key

        Returns:
            工作项类型列表，每项包含 {name, type_key, ...}

        Raises:
            Exception: API 调用失败时抛出异常
        """
        url = f"/open_api/{project_key}/work_item/all-types"

        logger.debug("Getting work item types: project_key=%s", project_key)

        resp = await self.client.get(url)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "获取工作项类型失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"获取工作项类型失败: {err_msg}")

        types = data.get("data", [])
        logger.info("Retrieved %d work item types", len(types))
        return types

    async def get_business_lines(self, project_key: str) -> List[Dict]:
        """
        获取空间下业务线详情

        对应 Postman: 配置 > 空间配置 > 获取空间下业务线详情
        API: GET /open_api/:project_key/business/all

        Args:
            project_key: 项目空间 Key

        Returns:
            业务线列表，每项包含 {id, name, ...}

        Raises:
            Exception: API 调用失败时抛出异常
        """
        url = f"/open_api/{project_key}/business/all"

        logger.debug("Getting business lines: project_key=%s", project_key)

        resp = await self.client.get(url)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "获取业务线详情失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"获取业务线详情失败: {err_msg}")

        business_lines = data.get("data", [])
        logger.info("Retrieved %d business lines", len(business_lines))
        return business_lines

    async def get_work_item_type_config(
        self, project_key: str, work_item_type_key: str
    ) -> Dict:
        """
        获取工作项基础信息配置

        对应 Postman: 配置 > 工作项配置 > 获取工作项基础信息配置
        API: GET /open_api/:project_key/work_item/type/:work_item_type_key

        Args:
            project_key: 项目空间 Key
            work_item_type_key: 工作项类型 Key

        Returns:
            工作项类型配置信息

        Raises:
            Exception: API 调用失败时抛出异常
        """
        url = f"/open_api/{project_key}/work_item/type/{work_item_type_key}"

        logger.debug(
            "Getting work item type config: project_key=%s, type_key=%s",
            project_key,
            work_item_type_key,
        )

        resp = await self.client.get(url)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "获取工作项类型配置失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"获取工作项类型配置失败: {err_msg}")

        config = data.get("data", {})
        logger.debug("Retrieved work item type config successfully")
        return config

    async def get_workflow_templates(
        self, project_key: str, work_item_type_key: str
    ) -> List[Dict]:
        """
        获取工作项下的流程模板列表

        对应 Postman: 配置 > 流程配置 > 获取工作项下的流程模板列表
        API: GET /open_api/:project_key/template_list/:work_item_type_key

        Args:
            project_key: 项目空间 Key
            work_item_type_key: 工作项类型 Key

        Returns:
            流程模板列表

        Raises:
            Exception: API 调用失败时抛出异常
        """
        url = f"/open_api/{project_key}/template_list/{work_item_type_key}"

        logger.debug(
            "Getting workflow templates: project_key=%s, type_key=%s",
            project_key,
            work_item_type_key,
        )

        resp = await self.client.get(url)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "获取流程模板列表失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"获取流程模板列表失败: {err_msg}")

        templates = data.get("data", [])
        logger.info("Retrieved %d workflow templates", len(templates))
        return templates
