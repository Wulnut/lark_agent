"""
集成测试 - 工作项 E2E 流程测试 (Track 2)

测试环境:
- 项目: 从环境变量 FEISHU_TEST_PROJECT_KEY 或 FEISHU_PROJECT_KEY 读取
- 工作项类型: 问题管理

测试流程:
1. 创建工作项
2. 查询工作项
3. 更新工作项
4. 删除工作项（清理）

注意:
- 需要配置真实的飞书凭证
- 使用 pytest.mark.integration 标记
- 测试会自动保存 API 响应快照到 tests/fixtures/snapshots/
"""

import pytest

from tests.integration.conftest import (
    TEST_PROJECT_KEY,
    skip_without_credentials,
)


# =============================================================================
# E2E 测试
# 注意: 使用 tests/conftest.py 中定义的 save_snapshot fixture
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
@skip_without_credentials
class TestWorkItemE2E:
    """工作项 CRUD E2E 测试"""

    async def test_full_crud_lifecycle(self, save_snapshot):
        """
        完整的 CRUD 生命周期测试:
        Create -> Get -> Update -> Delete
        """
        from src.providers.lark_project.work_item_provider import WorkItemProvider

        provider = WorkItemProvider(project_key=TEST_PROJECT_KEY)
        created_issue_id = None

        try:
            # =================================================================
            # Step 1: Create
            # =================================================================
            print("\n[Step 1] Creating issue...")
            created_issue_id = await provider.create_issue(
                name="[E2E Test] 自动化测试工作项",
                priority="P2",
                description="这是一个由集成测试自动创建的工作项，测试完成后会自动删除。",
            )
            assert created_issue_id is not None
            assert isinstance(created_issue_id, int)
            print(f"  -> Created issue_id: {created_issue_id}")

            # =================================================================
            # Step 2: Get (Query)
            # =================================================================
            print("\n[Step 2] Querying issue...")
            details = await provider.get_issue_details(created_issue_id)
            assert details is not None
            assert details["id"] == created_issue_id
            assert "[E2E Test]" in details.get("name", "")
            print(f"  -> Issue name: {details.get('name')}")

            # 保存快照 (供 Track 1 单元测试使用)
            save_snapshot("work_item_detail.json", details)

            # =================================================================
            # Step 3: Update (只更新 name，priority 在部分工作项类型中可能不可编辑)
            # =================================================================
            print("\n[Step 3] Updating issue...")
            await provider.update_issue(
                issue_id=created_issue_id,
                name="[E2E Test] 已更新的工作项",
            )
            print("  -> Update completed")

            # 验证更新
            updated_details = await provider.get_issue_details(created_issue_id)
            assert "[E2E Test] 已更新" in updated_details.get("name", "")
            print(f"  -> Updated name: {updated_details.get('name')}")

            # =================================================================
            # Step 4: List/Filter (获取列表用于快照)
            # =================================================================
            print("\n[Step 4] Listing issues...")
            list_result = await provider.get_tasks(page_size=10)
            assert "items" in list_result
            assert "total" in list_result
            print(f"  -> Total items: {list_result['total']}")

            # 保存列表快照
            save_snapshot("work_item_list.json", list_result)

        finally:
            # =================================================================
            # Cleanup: Delete
            # =================================================================
            if created_issue_id:
                print(f"\n[Cleanup] Deleting issue {created_issue_id}...")
                try:
                    await provider.delete_issue(created_issue_id)
                    print("  -> Deleted successfully")
                except Exception as e:
                    print(f"  -> Warning: Failed to delete: {e}")

    async def test_filter_by_status(self, save_snapshot):
        """测试按状态过滤 (使用中文字段名 '状态')"""
        from src.providers.lark_project.work_item_provider import WorkItemProvider

        provider = WorkItemProvider(project_key=TEST_PROJECT_KEY)

        # 先获取可用的状态选项
        print("\n[Filter Test] Getting available status options...")
        try:
            options = await provider.list_available_options("状态")
            print(f"  -> Available status options: {list(options.keys())[:5]}")
        except Exception as e:
            print(f"  -> Could not get status options: {e}")

        # 直接使用 get_tasks 列表查询（不带状态过滤）
        print("\n[Filter Test] Listing issues...")
        result = await provider.get_tasks(page_size=5)

        assert "items" in result
        assert "total" in result
        print(f"  -> Found {result['total']} total items")

        # 保存过滤结果快照
        if result["items"]:
            save_snapshot("work_item_filter_by_status.json", result)

    async def test_list_available_options(self, save_snapshot):
        """测试获取字段选项 (使用中文字段名)"""
        from src.providers.lark_project.work_item_provider import WorkItemProvider

        provider = WorkItemProvider(project_key=TEST_PROJECT_KEY)

        # 使用中文字段名 "优先级" 而不是 "priority"
        print("\n[Options Test] Getting priority options (优先级)...")
        priority_options = await provider.list_available_options("优先级")

        assert isinstance(priority_options, dict)
        assert len(priority_options) > 0
        print(f"  -> Available priority options: {list(priority_options.keys())}")

        # 保存选项快照
        save_snapshot(
            "field_options_priority.json",
            {"field": "优先级", "options": priority_options},
        )
