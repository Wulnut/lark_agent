from typing import List, Optional, Any, Dict
from src.core.client import ProjectClient, get_project_client
from src.schemas.project import BaseResponse, WorkItemListData, WorkItem


class WorkItemAPI:
    def __init__(self, client: Optional[ProjectClient] = None):
        self.client = client or get_project_client()

    async def filter_work_items(
        self, project_key: str, status: Optional[List[str]] = None, page_size: int = 50
    ) -> BaseResponse[WorkItemListData]:
        """
        Filter work items in a project.
        API: POST /open_api/:project_key/work_item/filter
        """
        url = f"/open_api/{project_key}/work_item/filter"
        payload: Dict[str, Any] = {
            "page_size": page_size,
        }
        if status:
            payload["work_item_status"] = status

        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        return BaseResponse[WorkItemListData].model_validate(resp.json())

    async def create_work_item(
        self,
        project_key: str,
        name: str,
        type_key: str,
        template_id: Optional[int] = None,
    ) -> BaseResponse[int]:
        """
        Create a new work item.
        API: POST /open_api/:project_key/work_item/create
        """
        url = f"/open_api/{project_key}/work_item/create"
        payload: Dict[str, Any] = {"name": name, "work_item_type_key": type_key}
        if template_id:
            payload["template_id"] = template_id

        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        # The create response data is usually just the ID
        return BaseResponse[int].model_validate(resp.json())
