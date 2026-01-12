"""
Description: 获取指定的工作项列表（跨空间）- 动态获取项目
Usage:
    uv run scripts/work_items/get_work_items_list/filter_across_project.py
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


async def filter_across_project(client, project_keys: list[str], work_item_type_key: str):
    """跨空间筛选"""
    url = "/open_api/work_items/filter_across_project"
    payload = {
        "project_keys": project_keys,
        "work_item_type_key": work_item_type_key,
        "page_num": 1,
        "page_size": 10
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
        target_type = "story" if "story" in type_keys else type_keys[0]
        
        # 2. 跨空间筛选（仅包含目标空间演示）
        print(f"跨空间查询类型: {target_type}")
        result = await filter_across_project(client, [project_key], target_type)
        
        print(f"\n[结果]: 共 {result.get('total')} 个")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"\n[错误]: {e}")


if __name__ == "__main__":
    asyncio.run(main())
