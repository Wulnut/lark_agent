"""
Description: Issue 工作项增删改查 (CRUD) 操作脚本
    - query: 查询工作项详情
    - create: 创建新的 Issue
    - update: 更新 Issue 字段
    - delete: 删除 Issue
Usage:
    # 查询详情
    uv run scripts/work_items/crud/issue_crud.py query --id 6645173426
    
    # 创建 Issue
    uv run scripts/work_items/crud/issue_crud.py create --name "测试Issue" --priority P2
    
    # 更新 Issue
    uv run scripts/work_items/crud/issue_crud.py update --id 6645173426 --priority P1
    
    # 删除 Issue
    uv run scripts/work_items/crud/issue_crud.py delete --id 6645173426
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

# 优先级映射 (label -> value)
PRIORITY_MAP = {
    "P0": "option_1",
    "P1": "option_2", 
    "P2": "option_3",
    "P3": "ckzn_hjzp"
}

# 严重等级映射
SEVERITY_MAP = {
    "S0": "eksxs8v1e",  # 致命
    "S1": "plc96gige",  # 严重
    "S2": "7jtdy75ps",  # 中等
    "S3": "su96ntpvx",  # 轻微
    "S4": "q0x9trucs"   # 建议
}

# 复现概率映射
REPRODUCIBILITY_MAP = {
    "always": "zu3e6ao_p",       # 始终复现 100%
    "frequent": "7zn431sx3",     # 频繁复现 80%-99%
    "intermittent": "xyv47g4ox", # 间歇性复现 30%-80%
    "rarely": "_ha1n3n1x",       # 偶尔复现 <30%
    "once": "bxefpy56x",         # 仅一次
    "not": "4cmmsrxv1"           # 无法复现
}

# 功能模块映射
MODULE_MAP = {
    "Wireless": "zs6w4vm51",
    "Router": "yw7squpfr",
    "System": "2l3fbnlzo",
    "Linux": "m5_zyn702",
    "Hardware": "u82uh2ibe",
    "AV": "2058dqi_0",
    "APPS": "wukzsflqy"
}

# Android版本映射
ANDROID_MAP = {
    "ALL": "vge0l9__5",
    "10": "btnhduahr",
    "11": "trpqex1jz",
    "12": "4h5n9va8m",
    "13": "o1fa_v28n",
    "14": "kw65p2dot",
    "Linux": "8_9bxq1n1"
}


async def query_work_item(client, project_key: str, work_item_ids: list[int]) -> dict:
    """
    查询工作项详情
    POST /open_api/:project_key/work_item/:work_item_type_key/query
    """
    url = f"/open_api/{project_key}/work_item/{ISSUE_TYPE_KEY}/query"
    payload = {
        "work_item_ids": work_item_ids,
        "expand": {
            "need_workflow": False,
            "relation_fields_detail": True,
            "need_multi_text": True,
            "need_user_detail": True
        }
    }
    
    print(f"\n[请求] POST {url}")
    print(f"[Body] {json.dumps(payload, indent=2, ensure_ascii=False)}")
    
    response = await client.post(url, json=payload)
    
    if response.status_code != 200:
        print(f"[响应状态]: {response.status_code}")
        print(f"[响应体]: {response.text}")
        response.raise_for_status()
    
    data = response.json()
    if data.get("err_code") != 0:
        raise Exception(f"查询失败: {data.get('err_msg')}")
    
    return data.get("data", [])


async def create_work_item(
    client,
    project_key: str,
    name: str,
    priority: str = "P2",
    description: str = "",
    related_project_id: int | None = None,
    priority_value_override: object = None,
    minimal: bool = False
) -> int:
    """
    创建工作项
    POST /open_api/:project_key/work_item/create
    """
    url = f"/open_api/{project_key}/work_item/create"
    
    # 构建字段值
    field_value_pairs = []
    
    if not minimal:
        # 1. 优先级 (必填)
        p_val = priority_value_override if priority_value_override is not None else PRIORITY_MAP.get(priority, "option_3")
        
        # 临时调试：如果 override 为 "SKIP"，则跳过该字段
        if p_val != "SKIP":
            field_value_pairs.append({
                "field_key": "priority",
                "field_value": p_val
            })
        
        # 2. 描述 (必填)
        desc_val = description if description else "Auto created via API"
        field_value_pairs.append({
            "field_key": "description",
            "field_value": desc_val
        })
        
        # 3-10. 其他 Select 字段暂不传，依赖系统默认值
        # 这样可以避免 Option Key 校验失败
        
        # 11. 关联项目 (可选)
        if related_project_id:
            field_value_pairs.append({
                "field_key": "field_3bf6c0",
                "field_value": [related_project_id]
            })
    
    payload = {
        "work_item_type_key": ISSUE_TYPE_KEY,
        "name": name,
        "field_value_pairs": field_value_pairs
    }
    
    print(f"\n[请求] POST {url}")
    print(f"[Body] {json.dumps(payload, indent=2, ensure_ascii=False)}")
    
    response = await client.post(url, json=payload)
    
    if response.status_code != 200:
        print(f"[响应状态]: {response.status_code}")
        print(f"[响应体]: {response.text}")
        response.raise_for_status()
    
    data = response.json()
    print(f"[响应] {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    if data.get("err_code") != 0:
        raise Exception(f"创建失败: {data.get('err_msg')}")
    
    return data.get("data")  # 返回新创建的工作项 ID


async def update_work_item(
    client,
    project_key: str,
    work_item_id: int,
    priority: str | None = None,
    name: str | None = None,
    description: str | None = None
) -> bool:
    """
    更新工作项
    PUT /open_api/:project_key/work_item/:work_item_type_key/:work_item_id
    """
    url = f"/open_api/{project_key}/work_item/{ISSUE_TYPE_KEY}/{work_item_id}"
    
    update_fields = []
    
    # 更新名称
    if name:
        update_fields.append({
            "field_key": "name",
            "field_value": name
        })
    
    # 更新优先级
    if priority and priority in PRIORITY_MAP:
        update_fields.append({
            "field_key": "priority",
            "field_value": PRIORITY_MAP[priority]
        })
    
    # 更新描述
    if description:
        update_fields.append({
            "field_key": "description",
            "field_value": description
        })
    
    if not update_fields:
        print("没有需要更新的字段")
        return False
    
    payload = {
        "update_fields": update_fields
    }
    
    print(f"\n[请求] PUT {url}")
    print(f"[Body] {json.dumps(payload, indent=2, ensure_ascii=False)}")
    
    response = await client.put(url, json=payload)
    
    if response.status_code != 200:
        print(f"[响应状态]: {response.status_code}")
        print(f"[响应体]: {response.text}")
        response.raise_for_status()
    
    data = response.json()
    print(f"[响应] {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    if data.get("err_code") != 0:
        raise Exception(f"更新失败: {data.get('err_msg')}")
    
    return True


async def delete_work_item(client, project_key: str, work_item_id: int) -> bool:
    """
    删除工作项
    DELETE /open_api/:project_key/work_item/:work_item_type_key/:work_item_id
    """
    url = f"/open_api/{project_key}/work_item/{ISSUE_TYPE_KEY}/{work_item_id}"
    
    print(f"\n[请求] DELETE {url}")
    
    response = await client.delete(url)
    
    if response.status_code != 200:
        print(f"[响应状态]: {response.status_code}")
        print(f"[响应体]: {response.text}")
        response.raise_for_status()
    
    data = response.json()
    print(f"[响应] {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    if data.get("err_code") != 0:
        raise Exception(f"删除失败: {data.get('err_msg')}")
    
    return True


def format_work_item(item: dict) -> str:
    """格式化工作项输出"""
    lines = []
    lines.append(f"ID: {item.get('id')}")
    lines.append(f"名称: {item.get('name')}")
    lines.append(f"状态: {item.get('work_item_status', {}).get('state_key')}")
    lines.append(f"创建时间: {item.get('created_at')}")
    lines.append(f"更新时间: {item.get('updated_at')}")
    
    # 解析字段
    fields = item.get("fields", [])
    for field in fields:
        key = field.get("field_key")
        value = field.get("field_value")
        
        if key == "priority" and isinstance(value, dict):
            lines.append(f"优先级: {value.get('label')}")
        elif key == "description" and value:
            desc = value[:100] + "..." if len(str(value)) > 100 else value
            lines.append(f"描述: {desc}")
        elif key == "owner":
            # 从 user_details 获取名称
            for user in item.get("user_details", []):
                if user.get("user_key") == value:
                    lines.append(f"负责人: {user.get('name_cn') or user.get('name_en')}")
                    break
    
    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="Issue 工作项 CRUD 操作")
    subparsers = parser.add_subparsers(dest="command", help="操作类型")
    
    # 查询命令
    query_parser = subparsers.add_parser("query", help="查询工作项详情")
    query_parser.add_argument("--id", type=int, required=True, help="工作项 ID")
    
    # 创建命令
    create_parser = subparsers.add_parser("create", help="创建新的 Issue")
    create_parser.add_argument("--name", type=str, required=True, help="Issue 名称")
    create_parser.add_argument("--priority", type=str, default="P2", choices=["P0", "P1", "P2", "P3"], help="优先级")
    create_parser.add_argument("--description", type=str, default="", help="描述")
    create_parser.add_argument("--project-id", type=int, help="关联项目 ID")
    create_parser.add_argument("--debug-priority", type=str, help="调试用：覆盖优先级值，填 SKIP 则跳过")
    create_parser.add_argument("--minimal", action="store_true", help="仅传名称，测试默认值")
    
    # 更新命令
    update_parser = subparsers.add_parser("update", help="更新 Issue")
    update_parser.add_argument("--id", type=int, required=True, help="工作项 ID")
    update_parser.add_argument("--name", type=str, help="新名称")
    update_parser.add_argument("--priority", type=str, choices=["P0", "P1", "P2", "P3"], help="新优先级")
    update_parser.add_argument("--description", type=str, help="新描述")
    
    # 删除命令
    delete_parser = subparsers.add_parser("delete", help="删除 Issue")
    delete_parser.add_argument("--id", type=int, required=True, help="工作项 ID")
    delete_parser.add_argument("--confirm", action="store_true", help="确认删除")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    client = get_project_client()
    project_name = "Project Management"
    
    print(f"正在查找项目空间: {project_name}...")
    
    try:
        project_key = await get_project_key_by_name(client, project_name)
        print(f"匹配到项目 Key: {project_key}")
        
        if args.command == "query":
            print(f"\n=== 查询工作项 ID: {args.id} ===")
            items = await query_work_item(client, project_key, [args.id])
            
            if items:
                for item in items:
                    print("\n" + "=" * 60)
                    print(format_work_item(item))
                    print("=" * 60)
                    
                    # 保存完整结果
                    with open(f"work_item_{args.id}.json", "w", encoding="utf-8") as fp:
                        json.dump(item, fp, indent=2, ensure_ascii=False)
                    print(f"\n完整详情已保存到: work_item_{args.id}.json")
            else:
                print("未找到工作项")
        
        elif args.command == "create":
            print(f"\n=== 创建 Issue ===")
            print(f"名称: {args.name}")
            print(f"优先级: {args.priority}")
            
            new_id = await create_work_item(
                client,
                project_key,
                name=args.name,
                priority=args.priority,
                description=args.description,
                related_project_id=args.project_id,
                priority_value_override=args.debug_priority,
                minimal=args.minimal
            )
            
            print(f"\n创建成功! 新工作项 ID: {new_id}")
        
        elif args.command == "update":
            print(f"\n=== 更新 Issue ID: {args.id} ===")
            
            success = await update_work_item(
                client,
                project_key,
                work_item_id=args.id,
                name=args.name,
                priority=args.priority,
                description=args.description
            )
            
            if success:
                print("\n更新成功!")
        
        elif args.command == "delete":
            if not args.confirm:
                print(f"\n警告: 即将删除工作项 ID: {args.id}")
                print("请添加 --confirm 参数确认删除操作")
                return
            
            print(f"\n=== 删除 Issue ID: {args.id} ===")
            
            success = await delete_work_item(client, project_key, args.id)
            
            if success:
                print("\n删除成功!")
    
    except Exception as e:
        print(f"\n[错误]: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
