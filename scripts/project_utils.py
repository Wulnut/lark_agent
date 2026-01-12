import json
from src.core.config import settings

async def get_project_key_by_name(client, name: str) -> str:
    """
    通过空间名称动态获取 project_key
    """
    # 1. 获取所有项目 key
    list_url = "/open_api/projects"
    list_payload = {
        "user_key": settings.FEISHU_PROJECT_USER_KEY,
        "tenant_group_id": 0
    }
    list_resp = await client.post(list_url, json=list_payload)
    list_resp.raise_for_status()
    project_keys = list_resp.json().get("data", [])

    if not project_keys:
        raise Exception("未找到任何项目空间")

    # 2. 获取详情并匹配名称
    detail_url = "/open_api/projects/detail"
    detail_payload = {
        "project_keys": project_keys,
        "user_key": settings.FEISHU_PROJECT_USER_KEY
    }
    detail_resp = await client.post(detail_url, json=detail_payload)
    detail_resp.raise_for_status()
    data = detail_resp.json().get("data", {})

    for key, info in data.items():
        if isinstance(info, dict) and info.get("name") == name:
            return key

    raise Exception(f"未找到名称为 '{name}' 的项目空间")
