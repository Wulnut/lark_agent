"""
Description: 验证 Provider Stack (API + Metadata + Business Logic)
    使用 WorkItemProvider 创建 Issue，完全依赖动态发现，无硬编码 ID。
Usage:
    uv run scripts/work_items/verify_provider_stack.py
"""

import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.config import settings
from src.providers.project.work_item_provider import WorkItemProvider

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

async def main():
    # 模拟用户配置
    PROJECT_NAME = "Project Management"
    ISSUE_TITLE = "[Provider测试] 动态发现验证"
    PRIORITY = "P2"
    
    print(f"初始化 Provider (Project: {PROJECT_NAME})...")
    provider = WorkItemProvider(PROJECT_NAME)
    
    try:
        print(f"正在创建 Issue: '{ISSUE_TITLE}' (Priority: {PRIORITY})...")
        
        # 调用业务接口
        issue_id = await provider.create_issue(
            name=ISSUE_TITLE,
            priority=PRIORITY,
            description="This issue was created using the full Provider stack with dynamic metadata discovery."
        )
        
        print(f"\n✅ 创建成功! Issue ID: {issue_id}")
        
        # 验证详情
        print(f"正在获取详情...")
        detail = await provider.get_issue_details(issue_id)
        print(f"Issue Name: {detail.get('name')}")
        
        # 清理
        print(f"正在清理 (删除)...")
        await provider.delete_issue(issue_id)
        print(f"✅ 清理完成")
        
    except Exception as e:
        print(f"\n❌ 失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
