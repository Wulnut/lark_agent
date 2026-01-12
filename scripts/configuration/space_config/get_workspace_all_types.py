"""
Description: 获取指定空间下所有工作项类型 - 动态获取
Usage:
    uv run scripts/configuration/space_config/get_workspace_all_types.py
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
logging.basicConfig(
    level=settings.get_log_level(),
    format="%(levelname)s: %(message)s",
    stream=sys.stdout,
)


async def get_work_item_types(client, project_key: str):
    """获取工作项类型"""
    url = f"/open_api/{project_key}/work_item/all-types"
    response = await client.get(url)
    response.raise_for_status()
    data = response.json()
    if data.get("err_code") != 0:
        raise Exception(f"获取工作项类型失败: {data.get('err_msg')}")
    return data.get("data", [])


async def main():
    client = get_project_client()
    project_name = "Project Management"
    
    print(f"正在动态查找项目空间: {project_name}...")
    try:
        project_key = await get_project_key_by_name(client, project_name)
        print(f"匹配到项目 Key: {project_key}")
        
        print(f"\n[步骤 1] 正在获取 {project_key} 的工作项类型...")
        work_item_types = await get_work_item_types(client, project_key)

        print(f"\n[状态码]: 200")
        print(f"共获取到 {len(work_item_types)} 个工作项类型")
        print("[返回结果]:")
        print(json.dumps(work_item_types, indent=2, ensure_ascii=False))

    except httpx.HTTPStatusError as e:
        print(f"\n[HTTP 错误]: {e}")
        print(f"[响应体]: {e.response.text}")
    except Exception as e:
        print(f"\n[失败]: {e}")


if __name__ == "__main__":
    asyncio.run(main())
