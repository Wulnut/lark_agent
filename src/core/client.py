import lark_oapi as lark
import httpx
from typing import Optional
from src.core.config import settings

_lark_client = None
_project_client = None


def get_lark_client():
    global _lark_client
    if not _lark_client:
        _lark_client = (
            lark.Client.builder()
            .app_id(settings.LARK_APP_ID)
            .app_secret(settings.LARK_APP_SECRET)
            .log_level(lark.LogLevel.DEBUG)
            .build()
        )
    return _lark_client


class ProjectClient:
    def __init__(self, base_url="https://project.feishu.cn"):
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "X-PLUGIN-TOKEN": settings.FEISHU_PROJECT_USER_TOKEN or "",
            "X-USER-KEY": settings.FEISHU_PROJECT_USER_KEY or "",
        }
        self.client = httpx.AsyncClient(base_url=self.base_url, headers=self.headers)

    async def post(self, path: str, json: Optional[dict] = None):
        return await self.client.post(path, json=json)

    async def get(self, path: str, params: Optional[dict] = None):
        return await self.client.get(path, params=params)


def get_project_client():
    global _project_client
    if not _project_client:
        _project_client = ProjectClient()
    return _project_client
