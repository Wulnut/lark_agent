"""API 包导出测试

目的：确保 src.providers.lark_project.api 的 __init__.py 正确导出新增 API 类。

说明：
- 若导出被误删，业务侧 `from ...api import CommentAPI` 会在运行时失败，且容易漏测。
"""

from __future__ import annotations


def test_api_package_exports_should_include_comment_and_workflow_api():
    from src.providers.lark_project.api import CommentAPI, WorkflowAPI

    assert CommentAPI is not None
    assert WorkflowAPI is not None
