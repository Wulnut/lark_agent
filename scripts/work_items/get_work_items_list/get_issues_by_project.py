"""
Description: 获取指定项目的 Issue 列表（支持任意项目名称）
Usage:
    uv run scripts/work_items/get_work_items_list/get_issues_by_project.py --project "项目名称"

    API: POST /open_api/:project_key/work_item/filter

    示例:
        uv run scripts/work_items/get_work_items_list/get_issues_by_project.py --project "SG06VA1"
        uv run scripts/work_items/get_work_items_list/get_issues_by_project.py --project "Project Management"
"""

import asyncio
import httpx
import json
import logging
import os
import sys
import argparse

# 将项目根目录添加到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.core.config import settings
from src.core.project_client import get_project_client
from scripts.project_utils import get_project_key_by_name

# 配置日志
logging.basicConfig(level=settings.get_log_level(), format="%(levelname)s: %(message)s", stream=sys.stdout)


async def filter_issues(client, project_key: str, page_size: int = 50):
    """获取指定项目的所有 Issue"""
    url = f"/open_api/{project_key}/work_item/filter"
    
    payload = {
        "work_item_type_keys": ["issue"],
        "page_num": 1,
        "page_size": page_size,
        "expand": {
            "need_workflow": True,
            "need_user_detail": True,
            "need_multi_text": True
        }
    }

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
    parser = argparse.ArgumentParser(description="获取指定项目的 Issue 列表")
    parser.add_argument("--project", type=str, required=True, help="项目名称（如 SG06VA1）")
    parser.add_argument("--page-size", type=int, default=50, help="每页数量（默认50）")
    args = parser.parse_args()
    
    client = get_project_client()
    project_name = args.project
    
    print(f"正在查找项目: {project_name}...")
    try:
        # 动态获取项目 Key
        project_key = await get_project_key_by_name(client, project_name)
        print(f"匹配到项目 Key: {project_key}")
        print(f"项目名称: {project_name}")
        
        # 获取 Issue 列表
        print(f"\n[查询] 正在获取 {project_name} 的 Issue 列表...")
        result = await filter_issues(client, project_key, page_size=args.page_size)
        
        total = result.get("total", 0)
        items = result.get("work_items", [])
        
        print(f"\n[结果] 共 {total} 个 Issue，返回 {len(items)} 个")
        
        # 显示简要列表
        if items:
            print("\n[Issue 列表简览]:")
            for idx, item in enumerate(items[:10], 1):
                item_id = item.get("id", "N/A")
                name = item.get("name", "未命名")
                status = item.get("work_item_status", {}).get("state_key", "unknown")
                print(f"  {idx}. [{item_id}] {name} (状态: {status})")
            if total > 10:
                print(f"  ... 还有 {total - 10} 个 Issue")
        
        print(f"\n[完整数据]:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except httpx.HTTPStatusError as e:
        print(f"\n[HTTP 错误]: {e}")
        print(f"[响应体]: {e.response.text}")
    except Exception as e:
        print(f"\n[失败]: {e}")


if __name__ == "__main__":
    asyncio.run(main())
