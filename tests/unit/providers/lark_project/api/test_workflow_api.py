"""WorkflowAPI 测试模块

测试覆盖:
1. query_work_item_workflow - 获取指定工作项的 workflow/runtime 信息
2. get_transition_required_info - 获取流转前必填信息
3. state_change - 执行状态流转

单测范式:
- patch get_project_client 返回 AsyncMock
- 覆盖每个方法至少 success + err_code case
- 断言 path 与 payload
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.unit.providers.lark_project.api.conftest import create_mock_response


@pytest.fixture
def mock_client():
    with patch("src.providers.lark_project.api.workflow.get_project_client") as mock:
        client_instance = AsyncMock()
        mock.return_value = client_instance
        yield client_instance


@pytest.fixture
def api(mock_client):
    from src.providers.lark_project.api.workflow import WorkflowAPI

    return WorkflowAPI()


class TestQueryWorkflow:
    @pytest.mark.asyncio
    async def test_query_work_item_workflow_success(self, api, mock_client):
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": {"states": [], "transitions": []}}
        )

        result = await api.query_work_item_workflow(
            project_key="pk",
            work_item_type_key="tk",
            work_item_id=123,
        )

        assert result == {"states": [], "transitions": []}
        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/open_api/pk/work_item/tk/123/workflow/query"

    @pytest.mark.asyncio
    async def test_query_work_item_workflow_err_code(self, api, mock_client):
        mock_client.post.return_value = create_mock_response(
            {"err_code": 10001, "err_msg": "无权限"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.query_work_item_workflow(
                project_key="pk",
                work_item_type_key="tk",
                work_item_id=123,
            )

        assert "获取工作项工作流信息失败" in str(exc_info.value)
        assert "无权限" in str(exc_info.value)


class TestTransitionRequiredInfo:
    @pytest.mark.asyncio
    async def test_get_transition_required_info_success(self, api, mock_client):
        mock_client.post.return_value = create_mock_response(
            {"err_code": 0, "data": {"required_fields": []}}
        )

        result = await api.get_transition_required_info(
            project_key="pk",
            work_item_type_key="tk",
            work_item_id=123,
            state_key="s1",
            mode="",
        )

        assert result == {"required_fields": []}
        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/open_api/work_item/transition_required_info/get"
        assert call_args[1]["json"]["project_key"] == "pk"
        assert call_args[1]["json"]["work_item_id"] == 123
        assert call_args[1]["json"]["state_key"] == "s1"

    @pytest.mark.asyncio
    async def test_get_transition_required_info_err_code(self, api, mock_client):
        mock_client.post.return_value = create_mock_response(
            {"err_code": 10002, "err_msg": "参数错误"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.get_transition_required_info(
                project_key="pk",
                work_item_type_key="tk",
                work_item_id=123,
                state_key="s1",
                mode="",
            )

        assert "获取流转必填信息失败" in str(exc_info.value)
        assert "参数错误" in str(exc_info.value)


class TestStateChange:
    @pytest.mark.asyncio
    async def test_state_change_success(self, api, mock_client):
        mock_client.post.return_value = create_mock_response({"err_code": 0, "data": {}})

        await api.state_change(
            project_key="pk",
            work_item_type_key="tk",
            work_item_id=123,
            transition_id="t1",
            fields=[{"field_key": "k", "field_value": "v"}],
            role_owners=None,
        )

        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/open_api/pk/workflow/tk/123/node/state_change"
        assert call_args[1]["json"]["transition_id"] == "t1"
        assert call_args[1]["json"]["fields"][0]["field_key"] == "k"

    @pytest.mark.asyncio
    async def test_state_change_err_code(self, api, mock_client):
        mock_client.post.return_value = create_mock_response(
            {"err_code": 10003, "err_msg": "流转失败"}
        )

        with pytest.raises(Exception) as exc_info:
            await api.state_change(
                project_key="pk",
                work_item_type_key="tk",
                work_item_id=123,
                transition_id="t1",
                fields=[],
                role_owners=None,
            )

        assert "状态流转失败" in str(exc_info.value)
        assert "流转失败" in str(exc_info.value)
