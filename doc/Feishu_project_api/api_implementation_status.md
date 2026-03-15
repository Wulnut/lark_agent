# 飞书项目 Open API 开发状态统计

本文档基于 `Open API Template/开放能力open-api接口.postman_collection.json` 与 `src/providers/lark_project/api/` 目录下的源码进行对比统计。

## 统计概览

| 模块 | 总接口数 | 已开发 | 未开发 | 开发进度 |
| :--- | :---: | :---: | :---: | :---: |
| **插件鉴权** | 4 | 2 | 2 | 50% |
| **空间管理** | 2 | 2 | 0 | 100% |
| **空间配置** | 2 | 2 | 0 | 100% |
| **工作项配置** | 8 | 8 | 0 | 100% |
| **流程配置** | 3 | 3 | 0 | 100% |
| **工作流运行时** | 3 | 3 | 0 | 100% |
| **评论** | 4 | 4 | 0 | 100% |
| **空间关联** | 4 | 4 | 0 | 100% |
| **安全配置** | 2 | 0 | 2 | 0% |
| **附件管理** | 4 | 3 | 1 | 75% |
| **用户管理** | 6 | 5 | 1 | 83% |
| **视图管理** | 2 | 0 | 2 | 0% |
| **工作项管理** | 10 | 10 | 0 | 100% |
| **工时管理** | 2 | 2 | 0 | 100% |
| **总计** | **56** | **50** | **6** | **89%** |

> 注：插件鉴权中的 Token 获取与刷新已在 `src/core/auth.py` 中底层实现，不计入 api 目录的统计但视为已通过核心层支持。

---

## 接口明细

### 1. 插件鉴权 (Authentication)

底层统一处理：`src/core/auth.py`

| 接口名称 | 方法 | 路径 | 状态 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| 获取 plugin_token | POST | `/open_api/authen/plugin_token` | ✅ 已实现 | AuthManager 自动管理 |
| 刷新 token | POST | `/open_api/authen/refresh_token` | ✅ 已实现 | AuthManager 自动管理 |
| 获取 code | POST | `/open_api/authen/auth_code` | ❌ 未开发 | 通常用于前端/OAuth流程 |
| 获取 user_plugin_token | POST | `/open_api/authen/user_plugin_token` | ❌ 未开发 | 目前仅支持 Tenant 级别 Plugin Token |

### 2. 空间管理 (Projects)

源码文件：`src/providers/lark_project/api/project.py`

| 接口名称 | 方法 | 路径 | 状态 | 对应方法 |
| :--- | :--- | :--- | :--- | :--- |
| 获取空间列表 | POST | `/open_api/projects` | ✅ 已实现 | `ProjectAPI.list_projects` |
| 获取空间详情 | POST | `/open_api/projects/detail` | ✅ 已实现 | `ProjectAPI.get_project_details` |

### 3. 配置管理 (Configuration)

> 注：本节的「流程配置」仅包含流程定义/模板等配置类接口。
> 工作项的运行时流转能力（状态流转、必填字段查询、workflow/query）见下方「工作流运行时」。

#### 3.1 空间配置

源码文件：`src/providers/lark_project/api/metadata.py`

| 接口名称 | 方法 | 路径 | 状态 | 对应方法 |
| :--- | :--- | :--- | :--- | :--- |
| 获取空间下业务线详情 | GET | `/open_api/:project_key/business/all` | ✅ 已实现 | `MetadataAPI.get_business_lines` |
| 获取空间下工作项类型 | GET | `/open_api/:project_key/work_item/all-types` | ✅ 已实现 | `MetadataAPI.get_work_item_types` |

#### 3.2 工作项配置

源码文件：`src/providers/lark_project/api/metadata.py` & `src/providers/lark_project/api/field.py`

| 接口名称 | 方法 | 路径 | 状态 | 对应方法 |
| :--- | :--- | :--- | :--- | :--- |
| 获取工作项基础信息配置 | GET | `/open_api/:project_key/work_item/type/:key` | ✅ 已实现 | `MetadataAPI.get_work_item_type_config` |
| 更新工作项基础信息配置 | PUT | `/open_api/:project_key/work_item/type/:key` | ✅ 已实现 | `MetadataAPI.update_work_item_type_config` |
| 获取字段信息 | POST | `/open_api/:project_key/field/all` | ✅ 已实现 | `FieldAPI.get_all_fields` |
| 创建自定义字段 | POST | `/open_api/:project_key/field/:type/create` | ✅ 已实现 | `FieldAPI.create_field` |
| 更新自定义字段 | PUT | `/open_api/:project_key/field/:type` | ✅ 已实现 | `FieldAPI.update_field` |
| 获取工作项关系列表 | GET | `/open_api/:project_key/work_item/relation` | ✅ 已实现 | `FieldAPI.get_work_item_relations` |
| 新增工作项关系 | POST | `/open_api/work_item/relation/create` | ✅ 已实现 | `FieldAPI.create_work_item_relation` |
| 更新工作项关系 | POST | `/open_api/work_item/relation/update` | ✅ 已实现 | `FieldAPI.update_work_item_relation` |

#### 3.3 流程与安全配置

源码文件：`src/providers/lark_project/api/metadata.py`

| 接口名称 | 方法 | 路径 | 状态 | 对应方法 |
| :--- | :--- | :--- | :--- | :--- |
| 获取工作项下的流程模板列表 | GET | `/open_api/:project_key/template_list/:key` | ✅ 已实现 | `MetadataAPI.get_workflow_templates` |
| 获取流程列表 | GET | `/open_api/:project_key/workflow/:key` | ✅ 已实现 | `MetadataAPI.get_workflows` |
| 获取流程详情 | GET | `/open_api/:project_key/workflow/:key/:id` | ✅ 已实现 | `MetadataAPI.get_workflow_detail` |
| 获取角色列表 | GET | `/open_api/:project_key/role/all` | ✅ 已实现 | `RoleAPI.get_roles` |
| 查询角色成员 | POST | `/open_api/:project_key/role/member/query` | ✅ 已实现 | `RoleAPI.query_role_members` |

### 4. 附件管理 (Assignments)

源码文件：暂无

| 接口名称 | 方法 | 路径 | 状态 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| 添加附件 | POST | `.../file/upload` | ❌ 未开发 | |
| 文件上传 | POST | `/open_api/:project_key/file/upload` | ✅ 已实现 | `AttachmentAPI.upload_file` |
| 下载附件 | POST | `/open_api/file/download` | ✅ 已实现 | `AttachmentAPI.download_file` |
| 删除附件 | POST | `/open_api/file/delete` | ✅ 已实现 | `AttachmentAPI.delete_file` |

### 5. 用户管理 (User)

源码文件：`src/providers/lark_project/api/user.py`

| 接口名称 | 方法 | 路径 | 状态 | 对应方法 |
| :--- | :--- | :--- | :--- | :--- |
| 获取空间下团队成员 | GET | `/open_api/:project_key/teams/all` | ✅ 已实现 | `UserAPI.get_team_members` |
| 获取用户详情 | POST | `/open_api/user/query` | ✅ 已实现 | `UserAPI.query_users` |
| 搜索租户内的用户列表 | POST | `/open_api/user/search` | ✅ 已实现 | `UserAPI.search_users` |
| 查询用户组成员 | POST | `/open_api/:project_key/user_groups/members/page` | ✅ 已实现 | `UserAPI.get_user_group_members` |
| 创建自定义用户组 | POST | `/open_api/:project_key/user_group` | ✅ 已实现 | `UserAPI.create_user_group` |
| 更新自定义用户组 | POST | `/open_api/:project_key/user_group/update` | ❌ 未开发 | |

### 6. 工作项管理 (Work Items)

源码文件：`src/providers/lark_project/api/work_item.py`

### 7. 评论 (Comments)

源码文件：`src/providers/lark_project/api/comment.py`

| 接口名称 | 方法 | 路径 | 状态 | 对应方法 |
| :--- | :--- | :--- | :--- | :--- |
| 创建评论 | POST | `/open_api/:project_key/work_item/:key/:id/comment/create` | ✅ 已实现 | `CommentAPI.create` |
| 获取评论列表 | GET | `/open_api/:project_key/work_item/:key/:id/comments` | ✅ 已实现 | `CommentAPI.list` |
| 更新评论 | PUT | `/open_api/:project_key/work_item/:key/:id/comment/:comment_id` | ✅ 已实现 | `CommentAPI.update` |
| 删除评论 | DELETE | `/open_api/:project_key/work_item/:key/:id/comment/:comment_id` | ✅ 已实现 | `CommentAPI.delete` |

### 8. 工作流运行时 (Workflow Runtime)

源码文件：`src/providers/lark_project/api/workflow.py`

| 接口名称 | 方法 | 路径 | 状态 | 对应方法 |
| :--- | :--- | :--- | :--- | :--- |
| 查询工作项工作流信息 | POST | `/open_api/:project_key/work_item/:key/:id/workflow/query` | ✅ 已实现 | `WorkflowAPI.query_work_item_workflow` |
| 获取流转前必填信息 | POST | `/open_api/work_item/transition_required_info/get` | ✅ 已实现 | `WorkflowAPI.get_transition_required_info` |
| 执行状态流转 | POST | `/open_api/:project_key/workflow/:key/:id/node/state_change` | ✅ 已实现 | `WorkflowAPI.state_change` |

### 9. 空间关联 (Relations)

源码文件：`src/providers/lark_project/api/relation.py`

| 接口名称 | 方法 | 路径 | 状态 | 对应方法 |
| :--- | :--- | :--- | :--- | :--- |
| 获取关联规则 | POST | `/open_api/:project_key/relation/rules` | ✅ 已实现 | `RelationAPI.rules` |
| 获取关联工作项列表 | POST | `/open_api/:project_key/relation/:key/:id/work_item_list` | ✅ 已实现 | `RelationAPI.work_item_list` |
| 批量绑定关联 | POST | `/open_api/:project_key/relation/:key/:id/batch_bind` | ✅ 已实现 | `RelationAPI.batch_bind` |
| 删除关联 | DELETE | `/open_api/:project_key/relation/:key/:id` | ✅ 已实现 | `RelationAPI.delete` |

| 接口名称 | 方法 | 路径 | 状态 | 对应方法 |
| :--- | :--- | :--- | :--- | :--- |
| 创建工作项 | POST | `/open_api/:project_key/work_item/create` | ✅ 已实现 | `WorkItemAPI.create` |
| 批量获取工作项详情 | POST | `/open_api/:project_key/work_item/:key/query` | ✅ 已实现 | `WorkItemAPI.query` |
| 更新工作项 | PUT | `/open_api/:project_key/work_item/:key/:id` | ✅ 已实现 | `WorkItemAPI.update` |
| 删除工作项 | DELETE | `/open_api/:project_key/work_item/:key/:id` | ✅ 已实现 | `WorkItemAPI.delete` |
| 基础筛选 | POST | `/open_api/:project_key/work_item/filter` | ✅ 已实现 | `WorkItemAPI.filter` |
| 复杂条件搜索 | POST | `/open_api/:project_key/work_item/:key/search/params` | ✅ 已实现 | `WorkItemAPI.search_params` |
| 获取创建元数据 | GET | `/open_api/:project_key/work_item/:key/meta` | ✅ 已实现 | `WorkItemAPI.get_create_meta` |
| 批量更新工作项 | POST | `/open_api/work_item/batch_update` | ✅ 已实现 | `WorkItemAPI.batch_update` |
| 获取工作项操作记录 | GET | `/open_api/:project_key/work_item/:key/:id/operate-history` | ✅ 已实现 | `WorkItemAPI.get_operate_history` |
| 关联工作项搜索 | POST | `/open_api/:project_key/work_item/:key/:id/search_by_relation` | ✅ 已实现 | `WorkItemAPI.search_by_relation` |
| 查询工时 | POST | `/open_api/work_item/man_hour/query` | ✅ 已实现 | `WorkItemAPI.query_man_hour` |
| 更新实际工时 | POST | `/open_api/work_item/actual_time/update` | ✅ 已实现 | `WorkItemAPI.update_actual_time` |

### 7. 视图管理 (Views)

源码文件：暂无

| 接口名称 | 方法 | 路径 | 状态 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| 更新条件视图 | POST | `/open_api/view/v1/update_condition_view` | ❌ 未开发 | |
| 获取视图详情 | GET | `/open_api/view/v1/detail` | ❌ 未开发 | |
