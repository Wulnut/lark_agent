"""
更新工作项的 eMMC(Flash) 容量字段

Usage:
    uv run scripts/update_emmc_capacity.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.providers.project.work_item_provider import WorkItemProvider


async def main():
    """查询并更新工作项"""
    work_item_name_keyword = "SR6D2VA-7552-Lark"
    work_item_type = "项目管理"
    field_name = "eMMC(Flash) 容量"  # 注意：字段名称是 "eMMC(Flash) 容量"，不是 "eMMC(Flash) 容量:"
    field_value = "512G"
    
    from src.providers.project.managers import MetadataManager
    
    # 获取所有项目
    meta = MetadataManager.get_instance()
    projects = await meta.list_projects()
    
    print(f"正在所有项目中搜索包含 '{work_item_name_keyword}' 的工作项...")
    print(f"工作项类型: {work_item_type}")
    print(f"字段: {field_name} = {field_value}\n")
    
    found_items = []
    
    # 在所有项目中搜索
    for project_name, project_key in projects.items():
        print(f"搜索项目: {project_name} ({project_key})...")
        try:
            provider = WorkItemProvider(
                project_key=project_key,
                work_item_type_name=work_item_type
            )
            
            # 按名称关键词搜索
            result = await provider.get_tasks(
                name_keyword=work_item_name_keyword,
                page_num=1,
                page_size=100
            )
            
            items = result.get("items", [])
            if items:
                print(f"  找到 {len(items)} 个工作项")
                for item in items:
                    item["project_name"] = project_name
                    item["project_key"] = project_key
                    found_items.append(item)
            else:
                print(f"  未找到匹配的工作项")
        except Exception as e:
            print(f"  搜索失败: {e}")
        print()
    
    if not found_items:
        print("没有找到匹配的工作项")
        return
    
    # 显示找到的工作项
    print(f"\n找到 {len(found_items)} 个工作项:")
    for idx, item in enumerate(found_items, 1):
        print(f"{idx}. 项目: {item.get('project_name')}, ID: {item.get('id')}, 名称: {item.get('name')}")
    
    # 更新所有找到的工作项
    print(f"\n正在更新所有工作项的 '{field_name}' 字段为 '{field_value}'...")
    
    success_count = 0
    fail_count = 0
    
    for item in found_items:
        issue_id = item.get("id")
        item_name = item.get("name")
        project_key = item.get("project_key")
        
        try:
            provider = WorkItemProvider(
                project_key=project_key,
                work_item_type_name=work_item_type
            )
            await provider.update_issue(
                issue_id=issue_id,
                extra_fields={field_name: field_value}
            )
            print(f"✓ 成功更新工作项 {issue_id} ({item_name})")
            success_count += 1
        except Exception as e:
            print(f"✗ 更新工作项 {issue_id} ({item_name}) 失败: {e}")
            fail_count += 1
    
    print(f"\n更新完成: 成功 {success_count} 个，失败 {fail_count} 个")
    
    items = result.get("items", [])
    total = result.get("total", 0)
    
    print(f"\n找到 {total} 个工作项")
    
    if not items:
        print("没有找到工作项，无法更新")
        return
    
    # 显示工作项列表
    print("\n工作项列表:")
    for idx, item in enumerate(items, 1):
        print(f"{idx}. ID: {item.get('id')}, 名称: {item.get('name')}")
    
    # 更新所有工作项
    print(f"\n正在更新所有工作项的 '{field_name}' 字段为 '{field_value}'...")
    
    success_count = 0
    fail_count = 0
    
    for item in items:
        issue_id = item.get("id")
        item_name = item.get("name")
        
        try:
            await provider.update_issue(
                issue_id=issue_id,
                extra_fields={field_name: field_value}
            )
            print(f"✓ 成功更新工作项 {issue_id} ({item_name})")
            success_count += 1
        except Exception as e:
            print(f"✗ 更新工作项 {issue_id} ({item_name}) 失败: {e}")
            fail_count += 1
    
    print(f"\n更新完成: 成功 {success_count} 个，失败 {fail_count} 个")


if __name__ == "__main__":
    asyncio.run(main())
