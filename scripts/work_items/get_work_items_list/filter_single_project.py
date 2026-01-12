"""
Description: 获取指定的工作项列表（单空间）- 动态获取项目
Usage:
    uv run scripts/work_items/get_work_items_list/filter_single_project.py
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
    """获取空间下所有工作项类型"""
    url = f"/open_api/{project_key}/work_item/all-types"
    response = await client.get(url)
    response.raise_for_status()
    data = response.json()
    if data.get("err_code") != 0:
        raise Exception(f"获取工作项类型失败: {data.get('err_msg')}")
    return data.get("data", [])


async def filter_work_items(client, project_key: str, work_item_type_keys: list[str], page_num: int = 1, page_size: int = 10):
    """筛选工作项"""
    url = f"/open_api/{project_key}/work_item/filter"
    payload = {
        "work_item_type_keys": work_item_type_keys,
        "page_num": page_num,
        "page_size": page_size,
        "expand": {"need_workflow": True, "need_user_detail": True}
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

        # 1. 获取工作项类型
        work_item_types = await get_work_item_types(client, project_key)
        if not work_item_types:
            print("该空间没有工作项类型")
            return
            
        type_keys = [t.get("type_key") for t in work_item_types]
        print(f"工作项类型: {type_keys[:5]}...")
        
        # 2. 筛选第一个类型的工作项
        target_type = type_keys[0]
        print(f"正在筛选类型: {target_type}")
        result = await filter_work_items(client, project_key, [target_type])
        
        print(f"\n[结果]: 共 {result.get('total')} 个，本页返回 {len(result.get('work_items', []))} 个")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"\n[错误]: {e}")


if __name__ == "__main__":
    asyncio.run(main())
