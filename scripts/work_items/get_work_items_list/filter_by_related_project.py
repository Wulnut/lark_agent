"""
Description: 按"关联项目"字段过滤 Issue 列表
    1. 获取 Issue管理 的字段定义，找到"关联项目"(field_3bf6c0)
    2. 获取关联项目的可选值（关联的工作项列表）
    3. 使用 search/params 按关联项目过滤
Usage:
    uv run scripts/work_items/get_work_items_list/filter_by_related_project.py
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

# 常量定义
ISSUE_TYPE_KEY = "670f3cdaddd89a6fa8f18e65"  # Issue管理的 type_key
RELATED_PROJECT_FIELD_KEY = "field_3bf6c0"   # 关联项目的 field_key


async def get_work_item_types(client, project_key: str) -> list[dict]:
    """获取空间下所有工作项类型"""
    url = f"/open_api/{project_key}/work_item/all-types"
    response = await client.get(url)
    response.raise_for_status()
    data = response.json()
    if data.get("err_code") != 0:
        raise Exception(f"获取工作项类型失败: {data.get('err_msg')}")
    return data.get("data", [])


async def get_fields(client, project_key: str, work_item_type_key: str) -> list[dict]:
    """获取指定工作项类型的所有字段定义"""
    url = f"/open_api/{project_key}/field/all"
    payload = {"work_item_type_key": work_item_type_key}
    response = await client.post(url, json=payload)
    response.raise_for_status()
    data = response.json()
    if data.get("err_code") != 0:
        raise Exception(f"获取字段失败: {data.get('err_msg')}")
    return data.get("data", [])


async def filter_work_items_simple(client, project_key: str, work_item_type_keys: list[str], page_size: int = 100) -> dict:
    """简单筛选工作项，用于获取关联项目的值"""
    url = f"/open_api/{project_key}/work_item/filter"
    payload = {
        "work_item_type_keys": work_item_type_keys,
        "page_num": 1,
        "page_size": page_size,
        "expand": {}
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


async def search_by_params(
    client,
    project_key: str,
    type_key: str,
    field_key: str,
    operator: str,
    value,
    page_num: int = 1,
    page_size: int = 50
) -> dict:
    """使用 search/params 进行复杂条件搜索"""
    url = f"/open_api/{project_key}/work_item/{type_key}/search/params"
    payload = {
        "search_group": {
            "conjunction": "AND",
            "search_params": [
                {
                    "field_key": field_key,
                    "operator": operator,
                    "value": value
                }
            ],
            "search_groups": []
        },
        "page_num": page_num,
        "page_size": page_size
    }
    
    print(f"\n[请求 URL]: {url}")
    print(f"[请求体]: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    
    response = await client.post(url, json=payload)
    
    if response.status_code != 200:
        print(f"[响应状态]: {response.status_code}")
        print(f"[响应体]: {response.text}")
        response.raise_for_status()
    
    data = response.json()
    if data.get("err_code") != 0:
        raise Exception(f"搜索失败: {data.get('err_msg')} (err_code: {data.get('err_code')})")
    
    result = data.get("data")
    if isinstance(result, list):
        return {"work_items": result, "total": len(result)}
    return result if result else {"work_items": [], "total": 0}


async def get_work_item_detail(client, project_key: str, type_key: str, work_item_id: int) -> dict:
    """获取工作项详情"""
    url = f"/open_api/{project_key}/work_item/{type_key}/{work_item_id}"
    response = await client.get(url)
    response.raise_for_status()
    data = response.json()
    if data.get("err_code") != 0:
        raise Exception(f"获取详情失败: {data.get('err_msg')}")
    return data.get("data", {})


async def main():
    client = get_project_client()
    project_name = "Project Management"
    
    print(f"正在查找项目空间: {project_name}...")
    
    try:
        # 1. 获取 project_key
        project_key = await get_project_key_by_name(client, project_name)
        print(f"匹配到项目 Key: {project_key}")
        
        # 2. 获取 Issue 列表，提取关联项目的值
        print(f"\n[步骤 1] 获取 Issue 列表，分析关联项目字段...")
        result = await filter_work_items_simple(client, project_key, [ISSUE_TYPE_KEY], page_size=50)
        work_items = result.get("work_items", [])
        
        # 收集所有不同的关联项目 ID
        related_project_ids = set()
        sample_items = []
        
        for item in work_items:
            fields = item.get("fields", [])
            for field in fields:
                if field.get("field_key") == RELATED_PROJECT_FIELD_KEY:
                    value = field.get("field_value")
                    if value:
                        if isinstance(value, list):
                            for v in value:
                                related_project_ids.add(v)
                        else:
                            related_project_ids.add(value)
                        sample_items.append({
                            "issue_name": item.get("name"),
                            "related_project_ids": value
                        })
                    break
        
        print(f"\n发现 {len(related_project_ids)} 个不同的关联项目 ID:")
        for pid in list(related_project_ids)[:10]:
            print(f"  - {pid}")
        
        print(f"\n关联项目示例:")
        for s in sample_items[:5]:
            print(f"  Issue: {s['issue_name'][:50]}...")
            print(f"  关联项目 ID: {s['related_project_ids']}")
            print()
        
        # 3. 选择一个关联项目 ID 进行过滤测试
        if related_project_ids:
            target_project_id = list(related_project_ids)[0]
            print(f"\n[步骤 2] 使用 search/params 按关联项目过滤...")
            print(f"目标关联项目 ID: {target_project_id}")
            
            # 尝试使用 IN 操作符
            try:
                filter_result = await search_by_params(
                    client,
                    project_key,
                    ISSUE_TYPE_KEY,
                    RELATED_PROJECT_FIELD_KEY,
                    "IN",
                    [target_project_id]
                )
                
                print(f"\n[过滤结果]: 共 {filter_result.get('total', 0)} 个匹配的 Issue")
                filtered_items = filter_result.get("work_items", [])
                for item in filtered_items[:5]:
                    print(f"  - {item.get('name', 'N/A')}")
                    
            except Exception as e:
                print(f"[过滤失败]: {e}")
                print("\n尝试其他操作符...")
                
                # 尝试 EQ 操作符
                try:
                    filter_result = await search_by_params(
                        client,
                        project_key,
                        ISSUE_TYPE_KEY,
                        RELATED_PROJECT_FIELD_KEY,
                        "EQ",
                        target_project_id
                    )
                    print(f"\n[EQ 过滤结果]: 共 {filter_result.get('total', 0)} 个")
                except Exception as e2:
                    print(f"[EQ 也失败]: {e2}")
        else:
            print("未找到任何关联项目数据")
        
    except Exception as e:
        print(f"\n[错误]: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
