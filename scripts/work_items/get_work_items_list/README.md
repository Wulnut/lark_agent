# 获取工作项列表 API 脚本说明

该目录包含 5 个用于获取飞书项目工作项列表的测试脚本，涵盖了单空间筛选、跨空间筛选、复杂参数搜索、全局搜索及关联项查询等核心场景。

## 目录结构

```text
scripts/work_items/get_work_items_list/
├── filter_single_project.py  # 单空间筛选
├── filter_across_project.py  # 跨空间筛选
├── search_params.py          # 复杂参数搜索
├── compositive_search.py     # 全局搜索
└── search_by_relation.py     # 关联工作项搜索
```

## 脚本详情与验证状态

| 脚本文件 | API 接口 | 功能描述 | 验证结果 |
| :--- | :--- | :--- | :--- |
| `filter_single_project.py` | `POST /open_api/:project_key/work_item/filter` | 获取单个项目空间内特定类型的工作项列表。 | ✅ 成功 |
| `filter_across_project.py` | `POST /open_api/work_items/filter_across_project` | 在多个项目空间中联合查询工作项。 | ✅ 成功 |
| `search_params.py` | `POST /open_api/:project_key/work_item/:work_item_type_key/search/params` | 使用复杂嵌套条件进行高级搜索。 | ✅ 成功 |
| `compositive_search.py` | `POST /open_api/compositive_search` | 全局关键词搜索。 | ⚠️ 需项目后台配置 |
| `search_by_relation.py` | `POST /open_api/:project_key/work_item/:work_item_type_key/:work_item_id/search_by_relation` | 获取与特定工作项存在关联关系的列表。 | ⚠️ 需配置关联关系 |

## 使用方式

在项目根目录下，使用 `uv` 运行脚本：

```bash
# 示例：运行单空间筛选脚本
uv run scripts/work_items/get_work_items_list/filter_single_project.py
```

## 注意事项

1.  **认证信息**：脚本自动从 `src.core.config` 获取 `user_key` 和插件 Token。
2.  **API 响应格式**：飞书项目 API 的返回结果可能是 `dict`（包含 `work_items` 和 `total`）也可能是直接的 `list`（仅包含列表）。脚本已对此做了兼容处理。
3.  **配置限制**：
    *   `compositive_search.py`：如果返回 `Query type is not supported`，请在飞书项目管理后台检查是否启用了该类型的搜索功能。
    *   `search_by_relation.py`：如果返回 `RelationKey Not Exist`，请在后台配置工作项类型（如 Story 与 Issue）之间的关联关系。
