"""
Description: 获取 Issue 列表及条件匹配
Usage:
    uv run scripts/work_items/get_work_items_list/filter_issues.py

    API: POST /open_api/:project_key/work_item/filter
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


async def filter_issues(
    client, 
    project_key: str,
    name_keyword: str = "",
    priority: str = "",
    page_num: int = 1, 
    page_size: int = 20
):
    """
    获取 Issue 列表（支持条件筛选）
    
    Args:
        project_key: 项目空间 key
        name_keyword: Issue 名称关键词（模糊搜索）
        priority: 优先级（如 P0, P1, P2, P3）
        page_num: 页码
        page_size: 每页数量
    """
    url = f"/open_api/{project_key}/work_item/filter"
    
    payload = {
        "work_item_type_keys": ["issue"],  # 指定筛选 issue 类型
        "page_num": page_num,
        "page_size": page_size,
        "expand": {
            "need_workflow": True,
            "need_user_detail": True,
            "need_multi_text": True
        }
    }
    
    # 可选：按名称关键词筛选
    if name_keyword:
        payload["work_item_name"] = name_keyword
    
    # 可选：按优先级筛选
    if priority:
        # 注意：需要将 P0, P1 等映射为实际值
        priority_map = {"P0": "0", "P1": "1", "P2": "2", "P3": "3"}
        payload["priorities"] = [priority_map.get(priority.upper(), priority)]

    response = await client.post(url, json=payload)
    response.raise_for_status()
    data = response.json()
    
    if data.get("err_code") != 0:
        raise Exception(f"筛选 Issue 失败: {data.get('err_msg')}")
    
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
        
        # 演示1：获取所有 Issue
        print("\n[演示1] 获取所有 Issue（前20条）...")
        result_all = await filter_issues(client, project_key)
        print(f"共 {result_all.get('total')} 个 Issue，本页返回 {len(result_all.get('work_items', []))} 个")
        
        # 演示2：按关键词搜索
        if result_all.get("total", 0) > 0:
            # 取第一个 Issue 的名称中的关键词演示搜索
            first_name = result_all["work_items"][0].get("name", "")
            if len(first_name) > 5:
                keyword = first_name[:3]  # 取前3个字符作为示例
                print(f"\n[演示2] 搜索包含关键词 '{keyword}' 的 Issue...")
                result_filtered = await filter_issues(client, project_key, name_keyword=keyword)
                print(f"找到 {result_filtered.get('total')} 个匹配项")
        
        # 演示3：按优先级筛选（取消注释可使用）
        # print("\n[演示3] 筛选 P1 级别的 Issue...")
        # result_priority = await filter_issues(client, project_key, priority="P1")
        # print(f"共 {result_priority.get('total')} 个 P1 Issue")
        
        print("\n[完整结果]:")
        print(json.dumps(result_all, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"\n[错误]: {e}")


if __name__ == "__main__":
    asyncio.run(main())
