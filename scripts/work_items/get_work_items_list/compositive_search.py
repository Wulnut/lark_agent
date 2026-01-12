"""
Description: 获取指定的工作项列表（全局搜索）- 动态获取项目
Usage:
    uv run scripts/work_items/get_work_items_list/compositive_search.py
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


async def compositive_search(client, project_keys: list[str], query: str):
    """全局搜索"""
    url = "/open_api/compositive_search"
    payload = {
        "project_keys": project_keys,
        "query": query,
        "query_type": "story",
        "page_num": 1,
        "page_size": 10
    }
    response = await client.post(url, json=payload)
    response.raise_for_status()
    data = response.json()
    if data.get("err_code") != 0:
        raise Exception(f"搜索失败: {data.get('err_msg')}")
    
    result = data.get("data")
    if isinstance(result, list):
        return {"items": result, "total": len(result)}
    return result if result else {"items": [], "total": 0}


async def main():
    client = get_project_client()
    project_name = "Project Management"
    
    print(f"正在动态查找项目空间: {project_name}...")
    try:
        project_key = await get_project_key_by_name(client, project_name)
        print(f"匹配到项目 Key: {project_key}")

        print(f"正在执行全局搜索 (关键词: '测试')...")
        result = await compositive_search(client, [project_key], "测试")
        
        print(f"\n[结果]: 共 {result.get('total')} 个")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except httpx.HTTPStatusError as e:
        print(f"\n[HTTP 错误]: {e}")
        response_data = e.response.json() if e.response.text else {}
        if response_data.get("err_code") == 20081:
            print("[提示]: 当前项目未启用全局搜索功能，或 query_type 不被支持")
        else:
            print(f"[响应体]: {e.response.text}")
    except Exception as e:
        print(f"\n[失败]: {e}")


if __name__ == "__main__":
    asyncio.run(main())
