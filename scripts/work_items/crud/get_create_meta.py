"""
Description: 获取创建 Issue 所需的元数据（必填字段、字段选项等）
Usage:
    uv run scripts/work_items/crud/get_create_meta.py
"""

import asyncio
import json
import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.core.config import settings
from src.core.project_client import get_project_client
from scripts.project_utils import get_project_key_by_name

logging.basicConfig(level=settings.get_log_level(), format="%(levelname)s: %(message)s", stream=sys.stdout)

ISSUE_TYPE_KEY = "670f3cdaddd89a6fa8f18e65"


async def main():
    client = get_project_client()
    project_name = "Project Management"
    
    print(f"正在查找项目空间: {project_name}...")
    project_key = await get_project_key_by_name(client, project_name)
    print(f"匹配到项目 Key: {project_key}")
    
    # 获取创建元数据
    url = f"/open_api/{project_key}/work_item/{ISSUE_TYPE_KEY}/meta"
    print(f"\n[请求] GET {url}")
    
    response = await client.get(url)
    
    if response.status_code != 200:
        print(f"[响应状态]: {response.status_code}")
        print(f"[响应体]: {response.text}")
        return
    
    data = response.json()
    print(f"[err_code]: {data.get('err_code')}")
    
    if data.get("err_code") != 0:
        print(f"[错误]: {data.get('err_msg')}")
        return
    
    meta = data.get("data", {})
    
    # 保存完整元数据
    with open("issue_create_meta.json", "w", encoding="utf-8") as fp:
        json.dump(meta, fp, indent=2, ensure_ascii=False)
    print(f"\n完整元数据已保存到: issue_create_meta.json")
    
    # 显示必填字段
    fields = meta.get("fields", [])
    print(f"\n共 {len(fields)} 个字段")
    
    print("\n=== 必填字段 ===")
    for f in fields:
        if f.get("is_required"):
            print(f"  {f.get('field_key')}: {f.get('field_name')} ({f.get('field_type_key')})")
            if f.get("options"):
                print(f"    选项: {[o.get('label') for o in f.get('options', [])[:5]]}")
    
    print("\n=== priority 字段详情 ===")
    for f in fields:
        if f.get("field_key") == "priority":
            print(json.dumps(f, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
