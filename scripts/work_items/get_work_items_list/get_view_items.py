"""
Description: 获取视图下工作项列表
Usage:
    uv run scripts/work_items/get_work_items_list/get_view_items.py --project "项目名称" --view "视图ID"

    API: POST /open_api/:project_key/view/:view_id

    示例:
        uv run scripts/work_items/get_work_items_list/get_view_items.py --project "主流程空间" --view "gky-05mHR"
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


async def get_view_work_items(client, project_key: str, view_id: str, page_num: int = 1, page_size: int = 50):
    """
    获取指定视图下的工作项列表
    API: POST /open_api/:project_key/view/:view_id
    
    Args:
        client: HTTP 客户端
        project_key: 项目空间 key
        view_id: 视图 ID
        page_num: 页码
        page_size: 每页数量
    """
    url = f"/open_api/{project_key}/view/{view_id}"
    
    payload = {
        "page_num": page_num,
        "page_size": page_size,
        "expand": {
            "need_workflow": True,
            "need_user_detail": True,
            "need_multi_text": True,
            "need_sub_task_parent": True
        },
        "quick_filter_id": ""  # 可选：快速筛选器 ID
    }

    response = await client.post(url, json=payload)
    response.raise_for_status()
    data = response.json()
    
    if data.get("err_code") != 0:
        raise Exception(f"获取视图工作项失败: {data.get('err_msg')}")
    
    result = data.get("data", {})
    # 兼容不同的返回格式
    if "total" not in result and "work_items" not in result:
        # 如果是列表格式
        if isinstance(result, list):
            return {"work_items": result, "total": len(result)}
        return {"work_items": [], "total": 0}
    return result


async def main():
    parser = argparse.ArgumentParser(description="获取视图下工作项列表")
    parser.add_argument("--project", type=str, required=True, help="项目名称（如 主流程空间）")
    parser.add_argument("--view", type=str, required=True, help="视图 ID（如 gky-05mHR）")
    parser.add_argument("--page-num", type=int, default=1, help="页码（默认1）")
    parser.add_argument("--page-size", type=int, default=50, help="每页数量（默认50）")
    args = parser.parse_args()
    
    client = get_project_client()
    
    try:
        # 动态获取项目 Key
        project_key = await get_project_key_by_name(client, args.project)
        print(f"项目名称: {args.project}")
        print(f"项目 Key: {project_key}")
        print(f"视图 ID: {args.view}")
        
        # 获取视图下的工作项
        print(f"\n[查询] 正在获取视图下的工作项列表...")
        result = await get_view_work_items(
            client, 
            project_key, 
            args.view,
            page_num=args.page_num,
            page_size=args.page_size
        )
        
        total = result.get("total", 0)
        items = result.get("work_items", [])
        
        print(f"\n[结果] 共 {total} 个工作项，返回 {len(items)} 个")
        
        # 显示简要列表
        if items:
            print("\n[工作项简览]:")
            for idx, item in enumerate(items[:10], 1):
                item_id = item.get("id", "N/A")
                name = item.get("name", "未命名")
                type_key = item.get("work_item_type_key", "unknown")
                status = item.get("work_item_status", {}).get("state_key", "unknown")
                print(f"  {idx}. [{item_id}] {name} (类型: {type_key}, 状态: {status})")
            if total > 10:
                print(f"  ... 还有 {total - 10} 个工作项")
        
        print(f"\n[完整数据]:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except httpx.HTTPStatusError as e:
        print(f"\n[HTTP 错误]: {e}")
        print(f"[响应体]: {e.response.text}")
    except Exception as e:
        print(f"\n[失败]: {e}")


if __name__ == "__main__":
    asyncio.run(main())
