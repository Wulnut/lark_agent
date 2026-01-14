import pytest
from pydantic import ValidationError
from src.schemas.project import BaseResponse, WorkItemListData, WorkItem, Pagination


# =============================================================================
# WorkItem 边界测试
# =============================================================================


class TestWorkItemBoundary:
    """WorkItem 模型边界测试"""

    @pytest.mark.parametrize(
        "missing_field,raw_data",
        [
            pytest.param(
                "id",
                {"name": "Task", "project_key": "P1", "work_item_type_key": "task"},
                id="missing_id",
            ),
            pytest.param(
                "name",
                {"id": 123, "project_key": "P1", "work_item_type_key": "task"},
                id="missing_name",
            ),
        ],
    )
    def test_missing_required_field(self, missing_field: str, raw_data: dict):
        """测试缺少必填字段时抛出 ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            WorkItem.model_validate(raw_data)
        assert missing_field in str(exc_info.value)

    def test_wrong_type_for_id(self):
        """测试 id 类型错误（字符串而非整数）"""
        raw = {
            "id": "not_an_int",
            "name": "Task",
            "project_key": "P1",
            "work_item_type_key": "task",
        }
        with pytest.raises(ValidationError) as exc_info:
            WorkItem.model_validate(raw)
        assert "id" in str(exc_info.value)

    def test_field_value_pairs_various_formats(self):
        """测试 field_value_pairs 的多种格式（字符串、对象、数组）"""
        raw = {
            "id": 123,
            "name": "Task",
            "project_key": "P1",
            "work_item_type_key": "task",
            "field_value_pairs": [
                {"field_key": "status", "field_value": "进行中"},  # 字符串
                {
                    "field_key": "priority",
                    "field_value": {"label": "P0", "value": "opt_p0"},
                },  # 对象
                {
                    "field_key": "owner",
                    "field_value": [{"name": "张三", "user_key": "u1"}],
                },  # 数组
            ],
        }
        item = WorkItem.model_validate(raw)
        assert len(item.field_value_pairs) == 3
        # 验证各种格式都被保留
        assert item.field_value_pairs[0]["field_value"] == "进行中"
        assert item.field_value_pairs[1]["field_value"]["label"] == "P0"
        assert item.field_value_pairs[2]["field_value"][0]["name"] == "张三"

    def test_empty_field_value_pairs(self):
        """测试 field_value_pairs 为空列表"""
        raw = {
            "id": 123,
            "name": "Task",
            "project_key": "P1",
            "work_item_type_key": "task",
            "field_value_pairs": [],
        }
        item = WorkItem.model_validate(raw)
        assert item.field_value_pairs == []

    def test_field_value_pairs_missing(self):
        """测试 field_value_pairs 字段不存在时使用默认值"""
        raw = {
            "id": 123,
            "name": "Task",
            "project_key": "P1",
            "work_item_type_key": "task",
        }
        item = WorkItem.model_validate(raw)
        assert item.field_value_pairs == []


# =============================================================================
# Pagination 边界测试
# =============================================================================


class TestPaginationBoundary:
    """Pagination 模型边界测试"""

    def test_default_values(self):
        """测试 Pagination 默认值"""
        pagination = Pagination()
        assert pagination.total == 0
        assert pagination.page_num == 1
        assert pagination.page_size == 20

    def test_total_as_string_coercion(self):
        """测试 total 为字符串时的类型转换（Pydantic 会自动转换）"""
        raw = {"total": "100", "page_num": 1, "page_size": 20}
        pagination = Pagination.model_validate(raw)
        assert pagination.total == 100
        assert isinstance(pagination.total, int)

    def test_total_as_invalid_string(self):
        """测试 total 为无效字符串时抛出错误"""
        raw = {"total": "invalid", "page_num": 1, "page_size": 20}
        with pytest.raises(ValidationError):
            Pagination.model_validate(raw)

    def test_negative_total(self):
        """测试 total 为负数（Pydantic 默认允许，但业务上可能需要限制）"""
        raw = {"total": -1, "page_num": 1, "page_size": 20}
        # 当前模型允许负数，测试验证这一行为
        pagination = Pagination.model_validate(raw)
        assert pagination.total == -1

    def test_partial_pagination(self):
        """测试只提供部分字段时使用默认值"""
        raw = {"total": 50}
        pagination = Pagination.model_validate(raw)
        assert pagination.total == 50
        assert pagination.page_num == 1
        assert pagination.page_size == 20


# =============================================================================
# BaseResponse 边界测试
# =============================================================================


class TestBaseResponseBoundary:
    """BaseResponse 模型边界测试"""

    def test_non_zero_error_code(self):
        """测试非零错误码"""
        raw = {"code": 99999, "msg": "Unknown Error", "data": None}
        resp = BaseResponse[WorkItemListData].model_validate(raw)
        assert not resp.is_success
        assert resp.code == 99999

    def test_negative_error_code(self):
        """测试负数错误码"""
        raw = {"code": -1, "msg": "System Error", "data": None}
        resp = BaseResponse[WorkItemListData].model_validate(raw)
        assert not resp.is_success
        assert resp.code == -1

    def test_missing_msg_field(self):
        """测试 msg 字段缺失时使用默认值"""
        raw = {"code": 0, "data": None}
        resp = BaseResponse[WorkItemListData].model_validate(raw)
        assert resp.msg == ""

    def test_data_with_missing_pagination(self):
        """测试 data 中 pagination 缺失"""
        raw = {
            "code": 0,
            "msg": "success",
            "data": {
                "data": [
                    {
                        "id": 1,
                        "name": "Task",
                        "project_key": "P1",
                        "work_item_type_key": "task",
                    }
                ],
                # pagination 字段缺失
            },
        }
        resp = BaseResponse[WorkItemListData].model_validate(raw)
        assert resp.is_success
        assert len(resp.data.items) == 1
        assert resp.data.pagination is None

    def test_data_with_empty_items(self):
        """测试 data.items 为空列表"""
        raw = {
            "code": 0,
            "msg": "success",
            "data": {
                "data": [],
                "pagination": {"total": 0, "page_num": 1, "page_size": 20},
            },
        }
        resp = BaseResponse[WorkItemListData].model_validate(raw)
        assert resp.is_success
        assert len(resp.data.items) == 0
        assert resp.data.pagination.total == 0


# =============================================================================
# 原有测试（保留）
# =============================================================================


def test_base_response_parsing():
    raw = {
        "code": 0,
        "msg": "success",
        "data": {
            "data": [
                {
                    "id": 123,
                    "name": "Task 1",
                    "project_key": "P1",
                    "work_item_type_key": "task",
                }
            ],
            "pagination": {"total": 1, "page_num": 1, "page_size": 20},
        },
    }

    resp = BaseResponse[WorkItemListData].model_validate(raw)

    assert resp.is_success
    assert resp.data is not None
    assert len(resp.data.items) == 1
    assert resp.data.items[0].name == "Task 1"
    assert resp.data.pagination.total == 1


def test_work_item_parsing():
    raw = {
        "id": 999,
        "name": "Bug Fix",
        "project_key": "PROJ",
        "work_item_type_key": "bug",
        "unknown_field": "ignore_me",
    }

    item = WorkItem.model_validate(raw)
    assert item.id == 999
    assert item.name == "Bug Fix"
    # Ensure extra fields are ignored
    assert not hasattr(item, "unknown_field")


def test_error_response():
    raw = {"code": 1001, "msg": "Invalid Token", "data": None}

    resp = BaseResponse[WorkItemListData].model_validate(raw)
    assert not resp.is_success
    assert resp.code == 1001
    assert resp.data is None
