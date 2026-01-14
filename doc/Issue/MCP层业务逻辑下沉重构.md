# MCP 层业务逻辑下沉重构

## 1. 问题描述

`mcp_server.py` 中存在多处违反项目架构原则的代码：

1. **DRY 违反**: `_extract_field_value` 和 `_simplify_work_item` 函数与 `WorkItemProvider` 中的实现完全重复
2. **业务逻辑越界**: `related_to` 智能解析逻辑（约 80 行）直接写在 MCP 工具函数中
3. **职责不清**: 辅助函数散落在 MCP 层，应归属于 Provider 或 utils 模块

根据 `AGENTS.md` 的分层要求：

> `mcp_server.py` 只与 `Provider` 抽象接口交互，不直接操作底层 SDK

---

## 2. 问题分析

### 2.1 重复代码

| 位置 | 函数 | 说明 |
|------|------|------|
| `mcp_server.py:65-80` | `_extract_field_value` | 与 `work_item_provider.py:80-104` 完全相同 |
| `mcp_server.py:83-91` | `_simplify_work_item` | 依赖上述函数，应由 Provider 提供 |

### 2.2 业务逻辑越界

`mcp_server.py:342-425` 中的 `related_to` 智能解析逻辑：

```python
# 当前位置: mcp_server.py (不应在此)
if related_to is not None:
    if isinstance(related_to, str):
        if related_to.isdigit():
            related_to_id = int(related_to)
        else:
            # 非数字字符串：按名称搜索工作项
            search_types = ["项目管理", "需求管理", "Issue管理", ...]
            for search_type in search_types:
                temp_provider = _create_provider(project, search_type)
                search_result = await temp_provider.get_tasks(...)
                # ... 60+ 行搜索逻辑
```

**问题**:
- MCP 层应只做参数透传和结果格式化
- 名称到 ID 的转换是业务逻辑，应在 Provider 层处理

### 2.3 功能冗余

`filter_tasks` 的功能是 `get_tasks` 的子集：

| 参数 | get_tasks | filter_tasks |
|------|-----------|--------------|
| status | ✓ | ✓ |
| priority | ✓ | ✓ |
| owner | ✓ | ✓ |
| name_keyword | ✓ | ✗ |
| work_item_type | ✓ | ✗ |
| related_to | ✓ | ✗ |

---

## 3. 解决方案

### 3.1 重构目标架构

```
重构前:                              重构后:
┌─────────────────────┐             ┌─────────────────────┐
│   mcp_server.py     │             │   mcp_server.py     │
│  - 辅助函数          │             │  - 纯接口定义        │
│  - related_to 解析   │    →       │  - 参数透传          │
│  - 数据简化          │             │  - 错误处理          │
└─────────────────────┘             └─────────────────────┘
                                              ↓
                                    ┌─────────────────────┐
                                    │ WorkItemProvider    │
                                    │  - resolve_related_to │
                                    │  - simplify_work_item │
                                    │  - 业务逻辑          │
                                    └─────────────────────┘
```

### 3.2 具体改动

1. **删除 mcp_server.py 中的重复函数**
   - 删除 `_extract_field_value`
   - 删除 `_simplify_work_item`

2. **在 WorkItemProvider 中添加公开方法**
   - `simplify_work_item(item: dict) -> dict`: 简化工作项数据
   - `resolve_related_to(related_to: Union[int, str], project: str) -> int`: 解析 related_to 参数

3. **简化 mcp_server.py 的 get_tasks**
   - 调用 `provider.resolve_related_to()` 处理名称到 ID 转换
   - 调用 `provider.simplify_work_item()` 简化返回数据

4. **简化 `_looks_like_project_key` 函数**
   - 当前实现过于复杂，实际只检测 `project_` 前缀

5. **评估 filter_tasks**
   - 保留但标记为可能废弃，或合并到 get_tasks

---

## 4. 验证计划

1. 运行现有测试确保功能不变
2. 验证 `get_tasks(related_to="SG06VA1")` 仍返回 33 个关联项
3. 验证 MCP 工具调用正常

---

## 5. 优先级

| 优先级 | 任务 | 状态 |
|--------|------|------|
| 高 | 删除重复代码 | 待处理 |
| 高 | related_to 解析逻辑下沉 | 待处理 |
| 高 | 添加 simplify_work_item 方法 | 待处理 |
| 中 | 评估 filter_tasks 冗余 | 待处理 |
| 低 | 简化 _looks_like_project_key | 待处理 |

---

**文档版本**: 1.1.0  
**日期**: 2026-01-14  
**状态**: ✅ 已完成 (Completed)

## 更新记录

- v1.0.0 (2026-01-14): 初始版本，记录问题分析与解决方案
- v1.1.0 (2026-01-14): 重构完成，所有 189 个单元测试通过
