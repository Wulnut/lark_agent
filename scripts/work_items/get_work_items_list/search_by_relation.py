"""
Description: 获取指定的关联工作项列表（单空间）- 动态获取项目
Usage:
    uv run scripts/work_items/get_work_items_list/search_by_relation.py
"""

import asyncio
import httpx
import json
import logging
import os
import sys

# 将项目根目录添加到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.core.config import settings
from src.core.project_client import get_project_client
from scripts.project_utils import get_project_key_by_name

# 配置日志
logging.basicConfig(level=settings.get_log_level(), format="%(levelname)s: %(message)s", stream=sys.stdout)


async def get_work_item_types(client, project_key: str):
    """获取工作项类型"""
    url = f"/open_api/{project_key}/work_item/all-types"
    response = await client.get(url)
    response.raise_for_status()
    data = response.json()
    if data.get("err_code") != 0:
        raise Exception(f"获取工作项类型失败: {data.get('err_msg')}")
    return data.get("data", [])


async def filter_work_items(client, project_key: str, work_item_type_keys: list[str], page_size: int = 5):
    """筛选工作项，用于找到一个工作项 ID"""
    url = f"/open_api/{project_key}/work_item/filter"
    payload = {
        "work_item_type_keys": work_item_type_keys,
        "page_num": 1,
        "page_size": page_size,
        "expand": {}
    }
    response = await client.post(url, json=payload)
    response.raise_for_status()
    data = response.json()
    if data.get("err_code") != 0:
        raise Exception(f"筛选失败: {data.get('err_msg')}")
    
    result = data.get("data")
    if isinstance(result, list):
        return {"work_items": result, "total": len(result)}
    return result if result else {"work_items": [], "total": 0}


async def search_by_relation(client, project_key: str, work_item_type_key: str, work_item_id: int, relation_type_key: str = ""):
    """获取关联工作项"""
    url = f"/open_api/{project_key}/work_item/{work_item_type_key}/{work_item_id}/search_by_relation"
    payload = {
        "relation_work_item_type_key": relation_type_key,
        "page_num": 1,
        "page_size": 10,
        "expand": {"need_workflow": True, "need_user_detail": True}
    }
    response = await client.post(url, json=payload)
    response.raise_for_status()
    data = response.json()
    if data.get("err_code") != 0:
        raise Exception(f"关联查询失败: {data.get('err_msg')}")
    return data.get("data", {})


async def main():
    client = get_project_client()
    project_name = "Project Management"
    
    print(f"正在动态查找项目空间: {project_name}...")
    try:
        project_key = await get_project_key_by_name(client, project_name)
        print(f"匹配到项目 Key: {project_key}")

        # 1. 获取类型
        work_item_types = await get_work_item_types(client, project_key)
        type_keys = [t.get("type_key") for t in work_item_types]
        target_type = type_keys[0]
        
        # 2. 获取一个实例 ID
        filter_result = await filter_work_items(client, project_key, [target_type])
        work_items = filter_result.get("work_items", [])
        if not work_items:
            print("未找到工作项实例")
            return
            
        instance = work_items[0]
        instance_id = instance.get("id")
        print(f"使用实例: {instance.get('name')} (ID: {instance_id})")

        # 3. 关联查询
        relation_type = "issue" if "issue" in type_keys else type_keys[1] if len(type_keys) > 1 else target_type
        print(f"查询关联类型: {relation_type}")
        result = await search_by_relation(client, project_key, target_type, instance_id, relation_type)
        
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except httpx.HTTPStatusError as e:
        print(f"\n[HTTP 错误]: {e}")
        print(f"[响应体]: {e.response.text}")
    except Exception as e:
        print(f"\n[失败]: {e}")


if __name__ == "__main__":
    asyncio.run(main())
