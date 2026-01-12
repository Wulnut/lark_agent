import pytest
from src.schemas.project import BaseResponse, WorkItemListData, WorkItem, Pagination


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
