# 测试覆盖率分析与改进计划 (Test Planning Phase 2)

**版本**: v1.0  
**日期**: 2026-01-14  
**状态**: 进行中 ⏳

基于对 `tests/` 目录下全部测试用例的全面审查，评估当前测试套件的覆盖情况、模拟真实环境的能力，以及与 `src/` 代码中全部类方法的匹配度。

---

## 1. 测试覆盖率概览

### ✅ 已覆盖的核心场景（覆盖率 ≈ 85%）
| 模块层级 | 测试覆盖率 | 关键测试点 |
|----------|-----------|------------|
| **API 层** (`providers/project/api/`) | 优秀 | WorkItemAPI、FieldAPI、MetadataAPI、ProjectAPI、UserAPI 均有完整单元测试，包含正常流程、错误处理、参数验证 |
| **Manager 层** (`providers/project/managers/`) | 优秀 | MetadataManager 测试全面，涵盖缓存命中、名称解析、级联解析、单例模式等 |
| **Provider 层** (`providers/project/`) | 良好 | WorkItemProvider 测试覆盖 CRUD、过滤、分页、异常处理、边界条件 |
| **Core 核心模块** | 良好 | AuthManager、SimpleCache、ProjectClient 有主要功能测试 |
| **Schema 数据模型** | 良好 | Pydantic 模型验证测试 |
| **MCP Server 工具层** | 良好 | 所有 MCP 工具函数均有测试，验证 JSON 结构和错误传递 |
| **集成测试** | 基础 | 端到端 CRUD 生命周期测试（需真实飞书凭证） |

---

## 2. 缺失的测试场景与风险

### 2.1 认证层完整测试缺口
| 组件 | 缺失场景 | 风险等级 |
|------|----------|----------|
| **ProjectClient** | `close()` 方法资源释放 | 中 |
| | 更多网络异常场景（连接超时、SSL 错误等） | 中 |
| **AuthManager** | API 返回非标准格式时的错误处理 | 高 |
| | 令牌过期后的自动刷新验证 | 高 |
| | 无任何凭证时的明确错误提示 | 中 |
| **ProjectAuth** | `async_auth_flow` 完整路径覆盖 | 中 |

### 2.2 模拟真实环境集成测试不足
*   **当前问题**: 集成测试依赖真实飞书凭证，无法在 CI/CD 中自动运行。
*   **风险**: 无法持续验证飞书 API 契约变更。
*   **解决方案**: 增加基于 `respx` 的模拟集成测试，完全模拟飞书 API 行为。

### 2.3 边缘情况与错误处理覆盖不全
1.  **超大分页** (`page_size > 100`) 的行为验证
2.  **无效字段名、选项值**的中文错误提示测试
3.  **并发请求**下的缓存一致性验证
4.  **字段类型映射、选项值转换**的真实场景模拟

### 2.4 性能与稳定性测试缺失
1.  **重试机制的指数退避**验证
2.  **长时间运行**的内存泄漏检查（虽非重点）

---

## 3. 与 `src/` 代码的匹配度分析

### 3.1 类方法覆盖率
| 文件 | 类 | 方法总数 | 已测试方法 | 覆盖率 |
|------|-----|----------|------------|--------|
| `src/core/auth.py` | `AuthManager` | 2 | 1 | 50% |
| `src/core/project_client.py` | `ProjectClient` | 9 | 6 | 67% |
| `src/core/project_client.py` | `ProjectAuth` | 1 | 0 | 0% |
| `src/services/issue_service.py` | `IssueService` | 7 | 3 | 43% |

### 3.2 未覆盖的关键方法
*   `AuthManager.__init__` (初始化逻辑)
*   `ProjectAuth.async_auth_flow` (认证头注入)
*   `ProjectClient.close()` (资源释放)
*   `IssueService.__init__` (项目名称/密钥解析优先级)

---

## 4. 改进优先级与行动计划

### P0 (高优先级 - 立即执行)
1.  **增加 ProjectAuth 测试**
    *   验证 `X-PLUGIN-TOKEN` 和 `X-USER-KEY` 正确注入
    *   测试无凭证、凭证无效等边界情况
2.  **增加模拟集成测试**
    *   使用 `respx` 完全模拟飞书 API，不依赖真实凭证
    *   覆盖工作项 CRUD、字段解析、分页等核心流程

### P1 (中优先级 - 短期)
1.  **补充 AuthManager 边界测试**
    *   API 返回非标准格式（无 `code` 字段、嵌套结构错误）
    *   令牌过期后的自动刷新验证
2.  **完善 IssueService 初始化逻辑测试**
    *   项目名称/密钥的解析优先级
    *   默认配置的回退机制

### P2 (低优先级 - 长期)
1.  **性能与稳定性测试**
    *   重试机制的指数退避验证
    *   并发请求下的缓存一致性
2.  **属性测试 (Hypothesis)**
    *   验证输入边界和异常数据

---

## 5. 具体行动项

### Phase 1: 认证层增强 (预计 2-3 天)
- [ ] **Task 1.1**: 更新 `tests/unit/core/test_auth.py`
    - 增加 `AuthManager` 边界测试（API 返回非标准格式、令牌过期刷新）
    - 增加无任何凭证时的明确错误提示测试
- [ ] **Task 1.2**: 新增 `tests/unit/core/test_project_auth.py`
    - 完整测试 `ProjectAuth.async_auth_flow` 方法
    - 验证认证头注入逻辑
- [ ] **Task 1.3**: 更新 `tests/unit/core/test_client.py`
    - 增加 `ProjectClient.close()` 方法测试
    - 增加网络异常场景测试（连接超时、SSL 错误）

### Phase 2: 模拟集成测试 (预计 2-3 天)
- [ ] **Task 2.1**: 新增 `tests/integration/test_work_item_mock.py`
    - 使用 `respx` 完全模拟飞书 API
    - 覆盖工作项 CRUD、字段解析、分页等核心流程
    - 不依赖真实飞书凭证，可在 CI/CD 中自动运行
- [ ] **Task 2.2**: 更新 CI/CD 配置
    - 将模拟集成测试加入标准测试流水线
    - 保留真实环境集成测试为手动触发

### Phase 3: 边缘情况覆盖 (预计 1-2 天)
- [ ] **Task 3.1**: 更新 `tests/unit/providers/project/test_work_item_provider.py`
    - 增加超大分页 (`page_size > 100`) 行为验证
    - 增加无效字段名、选项值的中文错误提示测试
- [ ] **Task 3.2**: 更新 `tests/unit/services/test_issue_service.py`
    - 增加 `IssueService.__init__` 初始化逻辑测试
    - 增加并发请求下的缓存一致性验证

---

## 6. 预期收益

1.  **测试覆盖率提升**: 预计从 85% 提升至 95%+
2.  **CI/CD 可靠性**: 模拟集成测试可在任意环境自动运行
3.  **代码质量**: 更全面的边界情况覆盖，减少生产环境 bug
4.  **维护性**: 清晰的测试分层，便于后续功能扩展

---

## 7. 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 模拟测试可能与真实 API 行为有差异 | 定期运行真实环境集成测试进行对比验证 |
| 测试代码重复度增加 | 抽取公共 Fixture，保持 DRY 原则 |
| 测试执行时间增长 | 优化测试用例，避免不必要的重复请求 |

---

**备注**: 本计划作为 Test_Planning_1.md 的延续，聚焦于提升测试对实际使用环境的模拟能力和代码覆盖率。执行过程中需遵循项目现有的测试规范和代码风格。