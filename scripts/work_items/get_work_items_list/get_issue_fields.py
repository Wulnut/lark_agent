"""
Description: 获取 Issue管理 工作项类型的所有字段定义
    用于找到"关联项目"字段的 field_key
Usage:
    uv run scripts/work_items/get_work_items_list/get_issue_fields.py
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


async def get_work_item_types(client, project_key: str) -> list[dict]:
    """获取空间下所有工作项类型"""
    url = f"/open_api/{project_key}/work_item/all-types"
    response = await client.get(url)
    response.raise_for_status()
    data = response.json()
    if data.get("err_code") != 0:
        raise Exception(f"获取工作项类型失败: {data.get('err_msg')}")
    return data.get("data", [])


def find_type_key_by_name(work_item_types: list[dict], target_name: str) -> str | None:
    """从工作项类型列表中找到指定名称的 type_key"""
    for item in work_item_types:
        if item.get("name") == target_name:
            return item.get("type_key")
    return None


async def get_fields(client, project_key: str, work_item_type_key: str) -> list[dict]:
    """获取指定工作项类型的所有字段定义"""
    url = f"/open_api/{project_key}/field/all"
    payload = {
        "work_item_type_key": work_item_type_key
    }
    response = await client.post(url, json=payload)
    
    if response.status_code != 200:
        print(f"[响应状态]: {response.status_code}")
        print(f"[响应体]: {response.text}")
        response.raise_for_status()
    
    data = response.json()
    if data.get("err_code") != 0:
        raise Exception(f"获取字段失败: {data.get('err_msg')}")
    return data.get("data", [])


async def main():
    client = get_project_client()
    project_name = "Project Management"
    issue_type_name = "Issue管理"
    
    print(f"正在动态查找项目空间: {project_name}...")
    
    try:
        # 1. 获取 project_key
        project_key = await get_project_key_by_name(client, project_name)
        print(f"匹配到项目 Key: {project_key}")
        
        # 2. 获取所有工作项类型，找到 Issue管理
        print(f"\n[步骤 1] 获取工作项类型...")
        work_item_types = await get_work_item_types(client, project_key)
        issue_type_key = find_type_key_by_name(work_item_types, issue_type_name)
        
        if not issue_type_key:
            print(f"未找到 '{issue_type_name}' 类型")
            return
        
        print(f"Issue管理 type_key: {issue_type_key}")
        
        # 3. 获取该类型的所有字段
        print(f"\n[步骤 2] 获取 Issue管理 的字段定义...")
        fields = await get_fields(client, project_key, issue_type_key)
        
        print(f"\n共获取到 {len(fields)} 个字段")
        print("\n" + "=" * 80)
        print("字段列表（重点关注 work_item_related 类型）:")
        print("=" * 80)
        
        # 分类显示字段
        related_fields = []
        select_fields = []
        other_fields = []
        
        for f in fields:
            field_type = f.get("field_type_key", "")
            field_info = {
                "field_key": f.get("field_key"),
                "field_name": f.get("field_name"),
                "field_type_key": field_type,
                "field_alias": f.get("field_alias", ""),
            }
            
            if "work_item_related" in field_type:
                related_fields.append(field_info)
            elif field_type == "select" or field_type == "multi_select":
                field_info["options"] = f.get("options", [])[:3]  # 只取前3个选项
                select_fields.append(field_info)
            else:
                other_fields.append(field_info)
        
        # 1. 显示关联类型字段（重点）
        print("\n【关联类型字段】(work_item_related_*) - 关联项目可能在这里:")
        print("-" * 80)
        for f in related_fields:
            print(f"  field_key: {f['field_key']}")
            print(f"  field_name: {f['field_name']}")
            print(f"  field_type: {f['field_type_key']}")
            print(f"  field_alias: {f['field_alias']}")
            print()
        
        # 2. 显示选择类型字段
        print("\n【选择类型字段】(select/multi_select):")
        print("-" * 80)
        for f in select_fields:
            options_str = ", ".join([o.get("label", "") for o in f.get("options", [])])
            print(f"  {f['field_key']}: {f['field_name']} ({f['field_type_key']})")
            if options_str:
                print(f"    选项: {options_str}...")
        
        # 3. 保存完整结果到文件
        output_file = "issue_fields.json"
        with open(output_file, "w", encoding="utf-8") as fp:
            json.dump(fields, fp, indent=2, ensure_ascii=False)
        print(f"\n完整字段定义已保存到: {output_file}")
        
    except Exception as e:
        print(f"\n[错误]: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
