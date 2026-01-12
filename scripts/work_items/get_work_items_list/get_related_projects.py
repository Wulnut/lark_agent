"""
Description: 获取"关联项目"字段的可选值列表
    1. 获取字段定义，找到关联项目字段关联的目标工作项类型
    2. 获取目标类型的工作项列表，建立 ID -> 名称 映射
    3. 展示可用于过滤的关联项目列表
Usage:
    uv run scripts/work_items/get_work_items_list/get_related_projects.py
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


async def filter_work_items(client, project_key: str, work_item_type_keys: list[str], page_size: int = 200) -> list[dict]:
    """筛选工作项"""
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
        return result
    return result.get("work_items", []) if result else []


async def get_relation_rules(client, project_key: str) -> list[dict]:
    """获取空间关联规则列表"""
    url = f"/open_api/{project_key}/relation/rules"
    response = await client.get(url)
    response.raise_for_status()
    data = response.json()
    if data.get("err_code") != 0:
        raise Exception(f"获取关联规则失败: {data.get('err_msg')}")
    return data.get("data", [])


async def main():
    client = get_project_client()
    project_name = "Project Management"
    
    print(f"正在查找项目空间: {project_name}...")
    
    try:
        # 1. 获取 project_key
        project_key = await get_project_key_by_name(client, project_name)
        print(f"匹配到项目 Key: {project_key}")
        
        # 2. 获取工作项类型列表
        print(f"\n[步骤 1] 获取工作项类型列表...")
        work_item_types = await get_work_item_types(client, project_key)
        type_map = {t.get("type_key"): t.get("name") for t in work_item_types}
        
        print(f"共 {len(work_item_types)} 个类型")
        
        # 3. 获取 Issue管理 的字段定义，分析关联项目字段
        print(f"\n[步骤 2] 分析关联项目字段配置...")
        fields = await get_fields(client, project_key, ISSUE_TYPE_KEY)
        
        related_field = None
        for f in fields:
            if f.get("field_key") == RELATED_PROJECT_FIELD_KEY:
                related_field = f
                break
        
        if related_field:
            print(f"\n关联项目字段配置:")
            print(f"  field_key: {related_field.get('field_key')}")
            print(f"  field_name: {related_field.get('field_name')}")
            print(f"  field_type: {related_field.get('field_type_key')}")
            
            # 查看是否有 work_item_type_key 配置
            related_type_key = related_field.get("work_item_type_key")
            compound_fields = related_field.get("compound_fields", [])
            
            print(f"  work_item_type_key: {related_type_key}")
            print(f"  compound_fields: {compound_fields}")
            
            # 完整字段定义
            print(f"\n完整字段定义:")
            print(json.dumps(related_field, indent=2, ensure_ascii=False))
        
        # 4. 获取空间关联规则
        print(f"\n[步骤 3] 获取空间关联规则...")
        try:
            rules = await get_relation_rules(client, project_key)
            print(f"共 {len(rules)} 条关联规则:")
            for rule in rules:
                print(f"  - {rule.get('name', 'N/A')}: {json.dumps(rule, ensure_ascii=False)[:200]}...")
        except Exception as e:
            print(f"获取关联规则失败: {e}")
        
        # 5. 获取 Issue 列表，统计关联项目使用情况
        print(f"\n[步骤 4] 统计 Issue 中的关联项目使用情况...")
        issues = await filter_work_items(client, project_key, [ISSUE_TYPE_KEY], page_size=200)
        
        # 收集关联项目 ID 及使用次数
        related_project_count = {}
        for item in issues:
            fields = item.get("fields", [])
            for field in fields:
                if field.get("field_key") == RELATED_PROJECT_FIELD_KEY:
                    value = field.get("field_value")
                    if value and isinstance(value, list):
                        for v in value:
                            related_project_count[v] = related_project_count.get(v, 0) + 1
                    break
        
        print(f"\n关联项目 ID 使用统计（共 {len(related_project_count)} 个不同项目）:")
        sorted_projects = sorted(related_project_count.items(), key=lambda x: x[1], reverse=True)
        for pid, count in sorted_projects[:15]:
            print(f"  ID: {pid} - 被 {count} 个 Issue 关联")
        
        # 6. 尝试获取这些关联项目的详情（它们可能是"项目管理"类型的工作项）
        print(f"\n[步骤 5] 查找关联项目的详情...")
        
        # 找到"项目管理"类型
        project_mgmt_type_key = None
        for t in work_item_types:
            if t.get("name") == "项目管理":
                project_mgmt_type_key = t.get("type_key")
                break
        
        if project_mgmt_type_key:
            print(f"找到 项目管理 类型: {project_mgmt_type_key}")
            
            # 获取项目管理的工作项列表
            project_items = await filter_work_items(client, project_key, [project_mgmt_type_key], page_size=100)
            
            # 建立 ID -> 名称 映射
            project_id_to_name = {item.get("id"): item.get("name") for item in project_items}
            
            print(f"\n项目管理工作项列表（共 {len(project_items)} 个）:")
            for item in project_items[:20]:
                item_id = item.get("id")
                item_name = item.get("name")
                used_count = related_project_count.get(item_id, 0)
                mark = " ★" if used_count > 0 else ""
                print(f"  ID: {item_id} - {item_name}{mark} (被关联 {used_count} 次)")
            
            # 保存映射
            output_data = {
                "project_key": project_key,
                "issue_type_key": ISSUE_TYPE_KEY,
                "related_project_field_key": RELATED_PROJECT_FIELD_KEY,
                "project_mgmt_type_key": project_mgmt_type_key,
                "project_id_to_name": project_id_to_name,
                "usage_stats": related_project_count
            }
            
            with open("related_projects_mapping.json", "w", encoding="utf-8") as fp:
                json.dump(output_data, fp, indent=2, ensure_ascii=False)
            print(f"\n映射已保存到: related_projects_mapping.json")
        else:
            print("未找到 项目管理 类型")
        
    except Exception as e:
        print(f"\n[错误]: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
