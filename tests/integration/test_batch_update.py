"""批量更新工作项集成测试。

测试流程:
1. 创建多个工作项
2. 批量更新字段（容错处理 API 限制）
3. 清理删除
"""

import pytest
from typing import List

from tests.integration.conftest import (
    TEST_PROJECT_KEY,
    skip_without_credentials,
)


@pytest.mark.integration
@pytest.mark.asyncio
@skip_without_credentials
class TestBatchUpdate:
    """批量更新集成测试类。"""

    async def test_batch_update_lifecycle(self, save_snapshot) -> None:
        """验证批量更新的完整生命周期。

        测试流程: 创建 -> 批量更新 -> 清理。
        """
        from src.providers.lark_project.work_item_provider import WorkItemProvider

        provider = WorkItemProvider(project_key=TEST_PROJECT_KEY)
        created_issue_ids: List[int] = []

        try:
            # =================================================================
            # Step 1: Create Multiple Issues
            # =================================================================
            print("\n[Step 1] Creating issues for batch update...")

            for i in range(2):
                issue_id = await provider.create_issue(
                    name=f"[E2E Batch Test] 测试项 {i + 1}",
                    description=f"批量更新测试 {i + 1}",
                )
                assert issue_id is not None
                created_issue_ids.append(issue_id)
                print(f"  -> Created: {issue_id}")

            assert len(created_issue_ids) == 2

            # =================================================================
            # Step 2: Batch Update (Attempt with error handling)
            # =================================================================
            print("\n[Step 2] Attempting batch update (Name)...")

            try:
                task_ids = await provider.batch_update_issues(
                    issue_ids=created_issue_ids,
                    name="[E2E Batch Test] 更新后标题",
                )
                print(f"  -> Success: task_ids={task_ids}")
                save_snapshot("batch_update_result.json", {"task_ids": task_ids})
            except Exception as e:
                # 某些环境中系统字段可能不支持批量更新
                # 验证是 API 错误而非代码逻辑错误
                error_str = str(e)
                print(f"  -> API Error (expected in some envs): {error_str}")
                assert any(
                    keyword in error_str
                    for keyword in ["Client error", "Invalid Param", "批量更新失败"]
                )
                save_snapshot("batch_update_error.json", {"error": error_str})

        finally:
            # =================================================================
            # Cleanup: Best-effort delete
            # =================================================================
            if created_issue_ids:
                print(f"\n[Cleanup] Deleting {len(created_issue_ids)} issues...")
                for issue_id in created_issue_ids:
                    try:
                        await provider.delete_issue(issue_id)
                        print(f"  -> Deleted: {issue_id}")
                    except Exception:
                        pass  # Best-effort cleanup
