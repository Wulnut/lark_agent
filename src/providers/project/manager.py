from typing import List, Dict, Optional
from src.providers.project.api import WorkItemAPI


class ProjectManager:
    def __init__(self, project_key: str, api_client: Optional[WorkItemAPI] = None):
        self.project_key = project_key
        self.api = api_client or WorkItemAPI()

    async def get_active_tasks(self) -> List[Dict]:
        """
        Get all active tasks (in_progress) for the project.
        Returns a simplified list of dictionaries.
        """
        # Call API
        resp = await self.api.filter_work_items(
            project_key=self.project_key, status=["in_progress"], page_size=50
        )

        if not resp.is_success or not resp.data:
            # For now, simplistic error handling: return empty list
            # In real world, we might log this or raise exception
            return []

        # Simplify Data
        tasks = []
        for item in resp.data.items:
            tasks.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "type": item.work_item_type_key,
                    # Add more fields mapping if needed
                }
            )

        return tasks

    async def create_task(
        self, name: str, type_key: str = "task", template_id: Optional[int] = None
    ) -> int:
        """
        Create a task and return its ID.
        """
        resp = await self.api.create_work_item(
            project_key=self.project_key,
            name=name,
            type_key=type_key,
            template_id=template_id,
        )

        if not resp.is_success:
            raise Exception(f"Failed to create task: {resp.msg} (code {resp.code})")

        if resp.data is None:
            raise Exception("Failed to create task: No data returned")

        return resp.data
