from typing import Optional, Dict, Any
from src.providers.project.work_item_provider import WorkItemProvider
import logging

logger = logging.getLogger(__name__)


class IssueService:
    """
    Issue 业务服务 (Application Layer)
    负责处理与 Issue 相关的业务场景，管理配置上下文，调度 Provider。
    """

    def __init__(
        self, project_name: Optional[str] = None, project_key: Optional[str] = None
    ):
        # 优先使用传入的 project_name/key，否则使用配置中的默认值
        self.project_name = project_name

        # 如果两者都未提供，尝试使用默认配置 (假设 settings 有 DEFAULT_PROJECT_NAME)
        if not project_name and not project_key:
            self.project_name = "Project Management"  # Fallback default
            logger.warning(
                "No project specified, using fallback default: %s", self.project_name
            )
        else:
            logger.info(
                "Initializing IssueService with project_name=%s, project_key=%s",
                project_name,
                project_key,
            )

        self.provider = WorkItemProvider(
            project_name=self.project_name, project_key=project_key
        )
        logger.debug("IssueService initialized successfully")

    async def create_issue(
        self,
        title: str,
        priority: str = "P2",
        description: str = "",
        assignee: Optional[str] = None,
    ) -> str:
        """
        创建一个 Issue
        :return: 成功消息，包含 Issue ID
        """
        logger.info(
            "Creating issue: title=%s, priority=%s, assignee=%s",
            title,
            priority,
            assignee,
        )

        # 可以在这里处理更多的业务逻辑，如参数校验、默认值注入等
        # 例如：如果 assignee 为空，尝试从环境读取默认经办人
        if not assignee:
            logger.debug("No assignee specified")
            # assignee = settings.DEFAULT_ASSIGNEE
            pass

        try:
            issue_id = await self.provider.create_issue(
                name=title,
                priority=priority,
                description=description,
                assignee=assignee,
            )
            logger.info("Issue created successfully: id=%s", issue_id)
            return f"Successfully created issue. ID: {issue_id}"
        except Exception as e:
            logger.error("Failed to create issue: %s", e, exc_info=True)
            raise Exception(f"Failed to create issue: {str(e)}")

    async def get_issue(self, issue_id: int) -> Dict[str, Any]:
        """获取 Issue 详情"""
        logger.debug("Getting issue details: id=%d", issue_id)
        try:
            issue = await self.provider.get_issue_details(issue_id)
            logger.info("Retrieved issue details successfully: id=%d", issue_id)
            return issue
        except Exception as e:
            logger.error(
                "Failed to get issue details: id=%d, error=%s",
                issue_id,
                e,
                exc_info=True,
            )
            raise

    # 未来可以在这里添加更复杂的业务方法，如 "report_bug", "plan_feature" 等
