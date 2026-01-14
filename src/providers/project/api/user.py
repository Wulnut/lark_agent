"""
UserAPI - 用户相关原子能力层
负责用户信息相关的原子接口封装

对应 Postman 集合:
- 用户 > 获取用户信息 > 获取空间下团队成员: GET /open_api/:project_key/teams/all
- 用户 > 获取用户信息 > 获取用户详情: POST /open_api/user/query
- 用户 > 获取用户信息 > 搜索租户内的用户列表: POST /open_api/user/search
- 用户 > 获取用户信息 > 查询用户组成员: POST /open_api/:project_key/user_groups/members/page
"""

import logging
from typing import Dict, List, Optional, Any
from src.core.project_client import get_project_client, ProjectClient

logger = logging.getLogger(__name__)


class UserAPI:
    """
    飞书项目用户 API 封装 (Base API Layer)

    职责: 严格对应 Postman 集合中的用户相关原子接口
    """

    def __init__(self, client: Optional[ProjectClient] = None):
        self.client = client or get_project_client()

    async def get_team_members(self, project_key: str) -> List[Dict]:
        """
        获取空间下团队成员

        对应 Postman: 用户 > 获取用户信息 > 获取空间下团队成员
        API: GET /open_api/:project_key/teams/all

        Args:
            project_key: 项目空间 Key

        Returns:
            团队成员列表

        Raises:
            Exception: API 调用失败时抛出异常
        """
        url = f"/open_api/{project_key}/teams/all"

        logger.debug("Getting team members: project_key=%s", project_key)

        resp = await self.client.get(url)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "获取团队成员失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"获取团队成员失败: {err_msg}")

        members = data.get("data", [])
        logger.info("Retrieved %d team members", len(members))
        return members

    async def query_users(
        self,
        user_keys: Optional[List[str]] = None,
        emails: Optional[List[str]] = None,
        out_ids: Optional[List[str]] = None,
        tenant_key: Optional[str] = None,
    ) -> List[Dict]:
        """
        获取用户详情

        对应 Postman: 用户 > 获取用户信息 > 获取用户详情
        API: POST /open_api/user/query

        Args:
            user_keys: 用户 Key 列表
            emails: 邮箱列表
            out_ids: 外部 ID 列表
            tenant_key: 租户 Key

        Returns:
            用户详情列表

        Raises:
            Exception: API 调用失败时抛出异常
        """
        url = "/open_api/user/query"
        payload: Dict[str, Any] = {}

        if user_keys:
            payload["user_keys"] = user_keys
        if emails:
            payload["emails"] = emails
        if out_ids:
            payload["out_ids"] = out_ids
        if tenant_key:
            payload["tenant_key"] = tenant_key

        logger.debug("Querying users: user_keys=%s, emails=%s", user_keys, emails)

        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "获取用户详情失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"获取用户详情失败: {err_msg}")

        users = data.get("data", [])
        logger.info("Retrieved %d users", len(users))
        return users

    async def search_users(
        self, query: str, project_key: Optional[str] = None
    ) -> List[Dict]:
        """
        搜索租户内的用户列表

        对应 Postman: 用户 > 获取用户信息 > 搜索租户内的用户列表
        API: POST /open_api/user/search

        Args:
            query: 搜索关键词 (用户名、邮箱等)
            project_key: 项目空间 Key (可选，限定搜索范围)

        Returns:
            匹配的用户列表

        Raises:
            Exception: API 调用失败时抛出异常
        """
        url = "/open_api/user/search"
        payload: Dict[str, Any] = {"query": query}

        if project_key:
            payload["project_key"] = project_key

        logger.debug("Searching users: query=%s, project_key=%s", query, project_key)

        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "搜索用户失败: err_code=%s, err_msg=%s", data.get("err_code"), err_msg
            )
            raise Exception(f"搜索用户失败: {err_msg}")

        users = data.get("data", [])
        logger.info("Found %d users matching query '%s'", len(users), query)
        return users

    async def get_user_group_members(
        self,
        project_key: str,
        user_group_type: str,
        user_group_ids: List[str],
        page_num: int = 1,
        page_size: int = 10,
    ) -> Dict:
        """
        查询用户组成员

        对应 Postman: 用户 > 获取用户信息 > 查询用户组成员
        API: POST /open_api/:project_key/user_groups/members/page

        Args:
            project_key: 项目空间 Key
            user_group_type: 用户组类型
            user_group_ids: 用户组 ID 列表
            page_num: 页码
            page_size: 每页数量

        Returns:
            分页的用户组成员数据

        Raises:
            Exception: API 调用失败时抛出异常
        """
        url = f"/open_api/{project_key}/user_groups/members/page"
        payload = {
            "user_group_type": user_group_type,
            "user_group_ids": user_group_ids,
            "page_num": page_num,
            "page_size": page_size,
        }

        logger.debug(
            "Getting user group members: project_key=%s, group_type=%s, group_ids=%s",
            project_key,
            user_group_type,
            user_group_ids,
        )

        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "查询用户组成员失败: err_code=%s, err_msg=%s",
                data.get("err_code"),
                err_msg,
            )
            raise Exception(f"查询用户组成员失败: {err_msg}")

        result = data.get("data", {})
        logger.debug("Retrieved user group members successfully")
        return result

    async def create_user_group(
        self, project_key: str, name: str, users: List[str]
    ) -> Dict:
        """
        创建自定义用户组

        对应 Postman: 用户 > 更新用户信息 > 创建自定义用户组
        API: POST /open_api/:project_key/user_group

        Args:
            project_key: 项目空间 Key
            name: 用户组名称
            users: 用户 Key 列表

        Returns:
            创建结果

        Raises:
            Exception: API 调用失败时抛出异常
        """
        url = f"/open_api/{project_key}/user_group"
        payload = {"name": name, "users": users}

        logger.info(
            "Creating user group: project_key=%s, name=%s, users=%s",
            project_key,
            name,
            users,
        )

        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_code") != 0:
            err_msg = data.get("err_msg", "Unknown error")
            logger.error(
                "创建用户组失败: err_code=%s, err_msg=%s", data.get("err_code"), err_msg
            )
            raise Exception(f"创建用户组失败: {err_msg}")

        result = data.get("data", {})
        logger.info("User group created successfully")
        return result
