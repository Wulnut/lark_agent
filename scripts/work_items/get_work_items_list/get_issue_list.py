"""
Description: 获取 Issue 管理工作项列表
    1. 先获取空间下所有工作项类型
    2. 找到 "Issue管理" 的 type_key
    3. 使用该 type_key 筛选工作项列表
Usage:
    uv run scripts/work_items/get_work_items_list/get_issue_list.py
"""

import asyncio
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


async def get_work_item_types(client, project_key: str) -> list[dict]:
    """获取空间下所有工作项类型"""
    url = f"/open_api/{project_key}/work_item/all-types"
    response = await client.get(url)
    response.raise_for_status()
    data = response.json()
    if data.get("err_code") != 0:
        raise Exception(f"获取工作项类型失败: {data.get('err_msg')}")
    return data.get("data", [])


def find_issue_type_key(work_item_types: list[dict], target_name: str = "Issue管理") -> str | None:
    """从工作项类型列表中找到指定名称的 type_key"""
    for item in work_item_types:
        if item.get("name") == target_name:
            return item.get("type_key")
    return None


async def filter_work_items(
    client,
    project_key: str,
    work_item_type_keys: list[str],
    page_num: int = 1,
    page_size: int = 50
) -> dict:
    """筛选指定类型的工作项列表"""
    url = f"/open_api/{project_key}/work_item/filter"
    payload = {
        "work_item_type_keys": work_item_type_keys,
        "page_num": page_num,
        "page_size": page_size,
        "expand": {"need_user_detail": True}
    }
    response = await client.post(url, json=payload)
    
    # 捕获详细错误
    if response.status_code != 200:
        print(f"[响应状态]: {response.status_code}")
        print(f"[响应体]: {response.text}")
        response.raise_for_status()
    
    data = response.json()
    if data.get("err_code") != 0:
        raise Exception(f"筛选工作项失败: {data.get('err_msg')}")
    
    result = data.get("data")
    if isinstance(result, list):
        return {"work_items": result, "total": len(result)}
    return result if result else {"work_items": [], "total": 0}


async def main():
    client = get_project_client()
    project_name = "Project Management"
    issue_type_name = "Issue管理"
    
    print(f"正在动态查找项目空间: {project_name}...")
    
    try:
        # 1. 获取 project_key
        project_key = await get_project_key_by_name(client, project_name)
        print(f"匹配到项目 Key: {project_key}")
        
        # 2. 获取所有工作项类型
        print(f"\n[步骤 1] 获取工作项类型...")
        work_item_types = await get_work_item_types(client, project_key)
        print(f"共获取到 {len(work_item_types)} 个工作项类型:")
        for t in work_item_types:
            print(f"  - {t.get('name')}: {t.get('type_key')}")
        
        # 3. 找到 Issue管理 的 type_key
        print(f"\n[步骤 2] 查找 '{issue_type_name}' 的 type_key...")
        issue_type_key = find_issue_type_key(work_item_types, issue_type_name)
        
        if not issue_type_key:
            print(f"未找到名称为 '{issue_type_name}' 的工作项类型")
            print("可用类型:", [t.get("name") for t in work_item_types])
            return
        
        print(f"找到 type_key: {issue_type_key}")
        
        # 4. 使用 type_key 筛选工作项
        print(f"\n[步骤 3] 筛选 Issue 列表...")
        result = await filter_work_items(client, project_key, [issue_type_key])
        
        total = result.get("total", 0)
        work_items = result.get("work_items", [])
        print(f"\n[结果]: 共 {total} 个 Issue，本页返回 {len(work_items)} 个")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"\n[错误]: {e}")


if __name__ == "__main__":
    asyncio.run(main())
