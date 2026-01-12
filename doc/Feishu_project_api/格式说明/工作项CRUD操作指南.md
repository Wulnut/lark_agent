# 工作项 CRUD 操作指南

本文档总结了如何使用飞书项目 Open API 进行工作项的增删改查（CRUD）操作，基于实际调试经验编写。

## 1. 核心 API 路径

| 操作 | HTTP 方法 | 路径 | 说明 |
|------|----------|------|------|
| **查询详情** | POST | `/open_api/{project_key}/work_item/{type_key}/query` | 支持批量查询、字段展开 |
| **创建** | POST | `/open_api/{project_key}/work_item/create` | 需提供必填字段 |
| **更新** | PUT | `/open_api/{project_key}/work_item/{type_key}/{id}` | 支持部分字段更新 |
| **删除** | DELETE | `/open_api/{project_key}/work_item/{type_key}/{id}` | 物理删除（慎用） |

## 2. 字段处理注意事项

### 必填字段与默认值
- 创建工作项时，虽然元数据 (`meta`) 显示有很多必填字段，但实际上大多数系统字段（如复现概率、严重等级等）都有默认值。
- **推荐策略**: 创建时仅传递真正需要设置的字段（如 `name`, `description`），其他字段依赖系统默认值。

### Select 类型字段陷阱
- `priority` (优先级) 等 Select 类型字段在 API 调用时可能会报 `Invalid Param` 错误，即使传递了正确的 Option Key。
- 这可能是由于项目配置或权限限制导致。
- **建议**: 如果遇到报错，先尝试不传该字段，创建后再尝试更新；或者只传递 `name` 等文本字段。

### 关联项目字段
- 字段类型: `work_item_related_multi_select`
- 字段 Key: `field_3bf6c0` (示例)
- 值格式: `[123456]` (关联工作项 ID 的列表)

## 3. Python 实现示例

完整实现参考 `scripts/work_items/crud/issue_crud.py`。

### 3.1 查询详情

```python
async def query_work_item(client, project_key, work_item_ids):
    url = f"/open_api/{project_key}/work_item/{ISSUE_TYPE_KEY}/query"
    payload = {
        "work_item_ids": work_item_ids,
        "expand": {
            "need_workflow": False,
            "relation_fields_detail": True,  # 获取关联字段详情
            "need_multi_text": True,         # 获取富文本内容
            "need_user_detail": True         # 获取用户信息
        }
    }
    response = await client.post(url, json=payload)
    return response.json().get("data", [])
```

### 3.2 创建工作项

```python
async def create_work_item(client, project_key, name, description):
    url = f"/open_api/{project_key}/work_item/create"
    
    field_value_pairs = [
        {"field_key": "description", "field_value": description}
    ]
    
    payload = {
        "work_item_type_key": ISSUE_TYPE_KEY,
        "name": name,
        "field_value_pairs": field_value_pairs
    }
    response = await client.post(url, json=payload)
    return response.json().get("data")
```

### 3.3 更新工作项

```python
async def update_work_item(client, project_key, work_item_id, name=None):
    url = f"/open_api/{project_key}/work_item/{ISSUE_TYPE_KEY}/{work_item_id}"
    
    update_fields = []
    if name:
        update_fields.append({"field_key": "name", "field_value": name})
        
    payload = {"update_fields": update_fields}
    response = await client.put(url, json=payload)
    return response.json()
```

### 3.4 删除工作项

```python
async def delete_work_item(client, project_key, work_item_id):
    url = f"/open_api/{project_key}/work_item/{ISSUE_TYPE_KEY}/{work_item_id}"
    response = await client.delete(url)
    return response.json()
```

## 4. 调试脚本使用

已提供 `scripts/work_items/crud/issue_crud.py` 脚本进行 CLI 测试：

```bash
# 查询
uv run scripts/work_items/crud/issue_crud.py query --id 12345

# 创建 (最小化模式)
uv run scripts/work_items/crud/issue_crud.py create --name "测试Issue" --minimal

# 更新
uv run scripts/work_items/crud/issue_crud.py update --id 12345 --description "新描述"

# 删除
uv run scripts/work_items/crud/issue_crud.py delete --id 12345 --confirm
```

## 5. 常见错误码

| 错误码 | 描述 | 原因/解决 |
|--------|------|----------|
| 20006 | Invalid Param | 字段值非法。Select 类型字段值需为 Option Key，或字段不可写。 |
| 20068 | Search Param Is Not Support | `search/params` 不支持该字段类型（如关联字段）。改用客户端过滤。 |
