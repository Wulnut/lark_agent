"""
Description: 按"关联项目"过滤 Issue 列表（客户端过滤方案）
    由于 search/params 不支持 work_item_related_multi_select 类型字段，
    采用客户端过滤：先获取全部 Issue，再按关联项目 ID 过滤
Usage:
    uv run scripts/work_items/get_work_items_list/filter_issues_by_project.py
    uv run scripts/work_items/get_work_items_list/filter_issues_by_project.py --project-name "AI耳机"
    uv run scripts/work_items/get_work_items_list/filter_issues_by_project.py --project-id 6645173426
"""

import argparse
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
ISSUE_TYPE_KEY = "670f3cdaddd89a6fa8f18e65"
PROJECT_MGMT_TYPE_KEY = "66baf93dbbde858d97564e56"
RELATED_PROJECT_FIELD_KEY = "field_3bf6c0"


async def filter_work_items_all_pages(client, project_key: str, work_item_type_keys: list[str], page_size: int = 100) -> list[dict]:
    """分页获取所有工作项"""
    all_items = []
    page_num = 1
    
    while True:
        url = f"/open_api/{project_key}/work_item/filter"
        payload = {
            "work_item_type_keys": work_item_type_keys,
            "page_num": page_num,
            "page_size": page_size,
            "expand": {"need_user_detail": True}
        }
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        if data.get("err_code") != 0:
            raise Exception(f"筛选失败: {data.get('err_msg')}")
        
        result = data.get("data")
        if isinstance(result, list):
            items = result
            total = len(result)
        else:
            items = result.get("work_items", []) if result else []
            total = result.get("total", 0) if result else 0
        
        all_items.extend(items)
        
        # 检查是否还有更多页
        if len(all_items) >= total or len(items) < page_size:
            break
        
        page_num += 1
        print(f"  已获取 {len(all_items)}/{total} 个...")
    
    return all_items


async def get_project_mapping(client, project_key: str) -> dict[int, str]:
    """获取项目管理工作项的 ID -> 名称 映射"""
    items = await filter_work_items_all_pages(client, project_key, [PROJECT_MGMT_TYPE_KEY], page_size=200)
    return {item.get("id"): item.get("name") for item in items}


def filter_issues_by_related_project(issues: list[dict], target_project_ids: set[int]) -> list[dict]:
    """按关联项目 ID 过滤 Issue"""
    filtered = []
    for issue in issues:
        fields = issue.get("fields", [])
        for field in fields:
            if field.get("field_key") == RELATED_PROJECT_FIELD_KEY:
                value = field.get("field_value")
                if value and isinstance(value, list):
                    # 检查是否有交集
                    if set(value) & target_project_ids:
                        filtered.append(issue)
                break
    return filtered


def extract_issue_summary(issue: dict, project_mapping: dict[int, str]) -> dict:
    """提取 Issue 摘要信息"""
    fields = issue.get("fields", [])
    
    # 提取关键字段
    priority = None
    related_projects = []
    owner = None
    
    for field in fields:
        field_key = field.get("field_key")
        value = field.get("field_value")
        
        if field_key == "priority" and value:
            priority = value.get("label") if isinstance(value, dict) else value
        elif field_key == RELATED_PROJECT_FIELD_KEY and value:
            if isinstance(value, list):
                related_projects = [project_mapping.get(v, str(v)) for v in value]
        elif field_key == "owner" and value:
            owner = value
    
    # 从 user_details 获取负责人名称
    owner_name = None
    if owner:
        for user in issue.get("user_details", []):
            if user.get("user_key") == owner:
                owner_name = user.get("name_cn") or user.get("name_en")
                break
    
    return {
        "id": issue.get("id"),
        "name": issue.get("name"),
        "priority": priority,
        "related_projects": related_projects,
        "owner": owner_name,
        "created_at": issue.get("created_at"),
        "status": issue.get("work_item_status", {}).get("state_key")
    }


async def main():
    parser = argparse.ArgumentParser(description="按关联项目过滤 Issue 列表")
    parser.add_argument("--project-name", type=str, help="关联项目名称（模糊匹配）")
    parser.add_argument("--project-id", type=int, help="关联项目 ID")
    parser.add_argument("--list-projects", action="store_true", help="列出所有可用的关联项目")
    args = parser.parse_args()
    
    client = get_project_client()
    project_name = "Project Management"
    
    print(f"正在查找项目空间: {project_name}...")
    
    try:
        # 1. 获取 project_key
        project_key = await get_project_key_by_name(client, project_name)
        print(f"匹配到项目 Key: {project_key}")
        
        # 2. 获取项目管理工作项映射
        print(f"\n[步骤 1] 获取关联项目列表...")
        project_mapping = await get_project_mapping(client, project_key)
        print(f"共 {len(project_mapping)} 个可关联项目")
        
        # 如果只是列出项目
        if args.list_projects:
            print("\n可用的关联项目列表:")
            for pid, pname in sorted(project_mapping.items(), key=lambda x: x[1]):
                print(f"  ID: {pid} - {pname}")
            return
        
        # 3. 确定目标项目 ID
        target_project_ids = set()
        target_project_names = []
        
        if args.project_id:
            target_project_ids.add(args.project_id)
            target_project_names.append(project_mapping.get(args.project_id, str(args.project_id)))
        elif args.project_name:
            # 模糊匹配项目名称
            for pid, pname in project_mapping.items():
                if args.project_name.lower() in pname.lower():
                    target_project_ids.add(pid)
                    target_project_names.append(pname)
        else:
            # 默认使用使用最多的项目作为示例
            print("\n未指定过滤条件，显示使用统计...")
            
            # 获取所有 Issue，统计关联项目使用情况
            print(f"\n[步骤 2] 获取所有 Issue...")
            all_issues = await filter_work_items_all_pages(client, project_key, [ISSUE_TYPE_KEY])
            print(f"共 {len(all_issues)} 个 Issue")
            
            # 统计
            usage_count = {}
            for issue in all_issues:
                for field in issue.get("fields", []):
                    if field.get("field_key") == RELATED_PROJECT_FIELD_KEY:
                        value = field.get("field_value")
                        if value and isinstance(value, list):
                            for v in value:
                                usage_count[v] = usage_count.get(v, 0) + 1
                        break
            
            print("\n关联项目使用统计（Top 15）:")
            sorted_usage = sorted(usage_count.items(), key=lambda x: x[1], reverse=True)[:15]
            for pid, count in sorted_usage:
                pname = project_mapping.get(pid, f"Unknown({pid})")
                print(f"  {pname}: {count} 个 Issue")
            
            print("\n提示: 使用以下命令按关联项目过滤:")
            print("  --project-name <名称>  按名称模糊匹配")
            print("  --project-id <ID>      按 ID 精确匹配")
            print("  --list-projects        列出所有可用项目")
            return
        
        if not target_project_ids:
            print(f"未找到匹配的项目: {args.project_name or args.project_id}")
            return
        
        print(f"\n目标关联项目: {target_project_names} (IDs: {target_project_ids})")
        
        # 4. 获取所有 Issue
        print(f"\n[步骤 2] 获取所有 Issue...")
        all_issues = await filter_work_items_all_pages(client, project_key, [ISSUE_TYPE_KEY])
        print(f"共 {len(all_issues)} 个 Issue")
        
        # 5. 客户端过滤
        print(f"\n[步骤 3] 按关联项目过滤...")
        filtered_issues = filter_issues_by_related_project(all_issues, target_project_ids)
        print(f"匹配到 {len(filtered_issues)} 个 Issue")
        
        # 6. 输出结果
        print("\n" + "=" * 80)
        print(f"过滤结果: 关联项目 = {target_project_names}")
        print("=" * 80)
        
        for issue in filtered_issues:
            summary = extract_issue_summary(issue, project_mapping)
            print(f"\n[{summary['id']}] {summary['name']}")
            print(f"  状态: {summary['status']} | 优先级: {summary['priority']} | 负责人: {summary['owner']}")
            print(f"  关联项目: {', '.join(summary['related_projects'])}")
        
        # 保存结果
        output_file = "filtered_issues.json"
        output_data = [extract_issue_summary(i, project_mapping) for i in filtered_issues]
        with open(output_file, "w", encoding="utf-8") as fp:
            json.dump(output_data, fp, indent=2, ensure_ascii=False)
        print(f"\n结果已保存到: {output_file}")
        
    except Exception as e:
        print(f"\n[错误]: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
