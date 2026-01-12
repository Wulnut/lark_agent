from typing import List, Dict
import httpx
from src.core.client import get_project_client
from src.providers.base import Provider
import logging

logger = logging.getLogger(__name__)


class ProjectItemProvider(Provider):
    def __init__(self, project_key: str):
        self.project_key = project_key
        self.client = get_project_client()

    async def fetch_active_tasks(self) -> List[Dict]:
        """
        [Future 模式] 异步获取所有进行中的任务
        """
        # 1. 构造请求参数 (RESTful)
        url = f"/open_api/{self.project_key}/work_item/filter"
        payload = {"work_item_status": ["in_progress"], "page_size": 50}

        # 2. 发起异步调用 (httpx)
        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
        except Exception as e:
            # Log error or re-raise
            logger.error(f"Error fetching tasks: {e}")
            return []

        data = response.json()

        # 3. 数据清洗
        return [{"id": i["id"], "name": i["name"]} for i in data.get("data", [])]
