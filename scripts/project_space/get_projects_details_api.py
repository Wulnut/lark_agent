'''
Description: get projects details from feishu project api
Usage:
    uv run scripts/project_space/get_projects_details_api.py

    This script will first get the list of projects, then fetch detailed
    information for each project from the Feishu Project API.
    It will print the detailed project information to the console.

    The script will use the .env file to get the token and user key.
    The script will use the project client to get the list and details.
    The script will print the detailed project information to the console.
'''

import asyncio
import httpx
import json
import logging
import os
import sys

# 将项目根目录添加到 Python 路径，确保能找到 src 目录
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.config import settings
from src.core.project_client import get_project_client

# 1. 配置日志到控制台，方便你看到授权过程
logging.basicConfig(
    level=settings.get_log_level(),
    format="%(levelname)s: %(message)s",
    stream=sys.stdout,
)


async def get_project_list(client):
    """
    获取项目空间列表
    """
    projects_url = "/open_api/projects"
    projects_payload = {
        "user_key": settings.FEISHU_PROJECT_USER_KEY,
        "tenant_group_id": 0,
        "asset_key": "",
        "order": [""]
    }

    response = await client.post(projects_url, json=projects_payload)
    response.raise_for_status()
    data = response.json()

    if data.get("err_code") != 0:
        raise Exception(f"获取项目列表失败: {data.get('err_msg')}")

    project_keys = data.get("data", [])
    print(f"获取到 {len(project_keys)} 个项目空间")

    return project_keys


async def get_project_details(client, project_keys):
    """
    获取项目空间详细信息
    """
    details_url = "/open_api/projects/detail"
    details_payload = {
        "user_key": settings.FEISHU_PROJECT_USER_KEY,
        "project_keys": project_keys,
        "simple_names": [],
    }

    response = await client.post(details_url, json=details_payload)
    response.raise_for_status()
    data = response.json()

    if data.get("err_code") != 0:
        raise Exception(f"获取项目详情失败: {data.get('err_msg')}")

    return data.get("data", [])


async def main():
    """
    演示如何调用飞书项目接口获取项目详细信息
    """
    # 获取已经封装好的客户端 (单例)
    # 它会自动读取 .env 并处理 Token 续期
    client = get_project_client()

    # 打印配置信息（调试用）
    print(f"FEISHU_PROJECT_USER_KEY 已设置: {bool(settings.FEISHU_PROJECT_USER_KEY)}")
    print(f"FEISHU_PROJECT_PLUGIN_ID 已设置: {bool(settings.FEISHU_PROJECT_PLUGIN_ID)}")

    print("\n--- 正在调用 API ---")

    try:
        # 第一步：获取项目空间列表
        print("\n[步骤 1] 获取项目空间列表...")
        project_keys = await get_project_list(client)
        print(f"项目 Keys: {project_keys}")

        # 第二步：获取每个项目的详细信息
        print("\n[步骤 2] 获取项目详细信息...")
        project_details = await get_project_details(client, project_keys)

        print(f"\n[状态码]: 200")
        print("[返回结果]:")
        print(json.dumps(project_details, indent=2, ensure_ascii=False))

    except httpx.HTTPStatusError as e:
        print(f"\n[调用失败]: {e}")
        print(f"[响应体]: {e.response.text}")
    except Exception as e:
        print(f"\n[调用失败]: {e}")


if __name__ == "__main__":
    # 使用 asyncio 运行异步主函数
    asyncio.run(main())