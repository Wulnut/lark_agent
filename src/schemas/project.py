from typing import List, Optional, Generic, TypeVar, Any
from pydantic import BaseModel, Field

T = TypeVar("T")


class Pagination(BaseModel):
    total: int = 0
    page_num: int = 1
    page_size: int = 20


class WorkItem(BaseModel):
    id: int
    name: str
    project_key: str
    work_item_type_key: str
    template_id: Optional[int] = None

    # Allow extra fields for forward compatibility
    model_config = {"extra": "ignore"}


class WorkItemListData(BaseModel):
    # Matches the structure inside "data" for list endpoints
    # Typically: { "data": [...], "pagination": {...} } inside the outer response data?
    # Or is the outer response { data: [..], pagination: .. }?
    # Based on standard Feishu OAPI: { code: 0, data: { ... } }
    # So this class represents the 'data' content.
    # However, for Work Item Filter, the doc says:
    # { "data": [...], "pagination": {...} }
    # So 'data' key here is actually the list of items.

    items: List[WorkItem] = Field(alias="data", default_factory=list)
    pagination: Optional[Pagination] = None


class BaseResponse(BaseModel, Generic[T]):
    code: int
    msg: str = ""
    data: Optional[T] = None

    @property
    def is_success(self) -> bool:
        return self.code == 0
