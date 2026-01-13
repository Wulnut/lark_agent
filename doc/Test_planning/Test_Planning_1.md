# 测试现状分析与改进计划 (Test Planning Phase 1)

## 1. 现状分析 (Current Status Analysis)

经过对 `tests/` 目录下的核心测试文件（`test_client.py`, `test_work_item_provider.py`, `test_models.py`, `test_mcp_server.py`）的深度分析，评估如下：

### 1.1 优点 (Strengths)
*   **基础设施完善**: 采用了 `pytest` + `pytest-asyncio` 的标准异步测试框架。
*   **Mock 机制成熟**: 熟练使用 `respx` 模拟 HTTP 请求，使用 `unittest.mock` 隔离层级依赖。
*   **覆盖率尚可**: 核心的 CRUD 操作（增删改查）在 Provider 和 Server 层都有对应的 Happy Path 测试。
*   **重试机制测试**: `ProjectClient` 的重试逻辑（5xx 重试，4xx 不重试）覆盖较好。

### 1.2 弱点与风险 (Weaknesses & Risks)
*   **过度依赖 Mock (Over-mocking)**:
    *   Provider 层测试大量 Mock 了 `WorkItemAPI` and `MetadataManager`。虽然隔离了单元，但如果 API 的真实返回值结构发生微小变化（例如分页字段嵌套变了），测试依然通过，但生产环境会崩。
    *   测试数据（Fixtures）主要是“手工构造”的理想化 JSON，缺乏真实 Feishu API 返回的复杂性（如动态字段 `field_value_pairs` 的多种格式）。
*   **Schema 验证薄弱**:
    *   `test_models.py` 仅验证了最基础的字段存在性。对于边界情况（如必填字段缺失、类型错误、字段为 `null` vs 不存在）缺乏覆盖。
*   **断言脆弱 (Fragile Assertions)**:
    *   MCP Server 层测试大量使用字符串包含断言（如 `assert "创建成功" in result`）。如果文案调整，测试将误报失败。
*   **缺乏负面测试 (Lack of Negative Testing)**:
    *   大多数测试集中在“成功路径”。对于 `MetadataManager` 解析失败、API 鉴权失败、网络超时、部分字段更新失败等场景覆盖不足。

## 2. 改进目标 (Improvement Goals)

本次测试改进的核心目标是：**从“验证代码写了”转向“验证业务逻辑正确且健壮”**。

### 2.1 增强 Schema 验证
*   引入更严格的数据校验测试，确保 Pydantic Model 能正确处理 Feishu API 的各种边缘数据。
*   测试 `field_value_pairs` 的多态性（字符串、对象、数组）。

### 2.2 强化 Provider 逻辑
*   增加 `MetadataManager` 缓存失效或解析错误的测试场景。
*   模拟 API 返回的“脏数据”，验证 Provider 的清洗逻辑是否健壮。

### 2.3 规范化断言
*   MCP 层测试应解析返回的 JSON 字符串，验证结构化数据，而非匹配自然语言文案。

## 3. 具体的改进计划 (Action Items)

我们将分阶段执行以下改进：

### 阶段一：Schema & Model 增强 (Immediate)
*   [x] **任务**: 更新 `tests/schemas/test_models.py`
    *   增加 `WorkItem` 解析的边界测试（missing fields, wrong types）。
    *   针对 `Pagination` 结构增加测试（处理 `total` 缺失或为字符串的情况）。
    *   测试 `BaseResponse` 处理非标准错误码的情况。

### 阶段二：Provider 深度测试 (Short-term)
*   [x] **任务**: 更新 `tests/providers/project/test_work_item_provider.py`
    *   **异常流测试**: 模拟 `get_project_key` 找不到项目时的报错处理。
    *   **复杂字段测试**: 测试 `create_issue` 时传入复杂类型的字段值（如人员列表、多选标签）。
    *   **分页边界**: 测试 `get_tasks` 在最后一页、空页时的行为。

### 阶段三：断言重构 (Medium-term)
*   [x] **任务**: 重构 `tests/test_mcp_server.py`
    *   移除 `assert "成功" in result` 风格的代码。
    *   改为 `response = json.loads(result); assert response["code"] == 0`。

### 阶段四：引入真实数据快照 (Optional/Advanced)
*   [x] **任务**: 考虑引入 `vcrpy` 或保留一份真实的 Feishu API 响应 JSON 作为测试 Fixture，而不是手动构造 `dict`。
    *   已建立 `tests/fixtures/snapshots/` 目录。
    *   已通过集成测试生成真实快照：`work_item_detail.json`, `work_item_list.json` 等。

## 4. 执行策略
1.  优先执行 **阶段一** 和 **阶段三**，因为它们成本低且收益高（防止低级错误）。
2.  **阶段二** 随功能迭代逐步补充。

## 5. 新增测试策略：双轨制测试 (Dual-Track Testing Strategy)

为解决“测试数据失真”和“缺乏真实环境验证”的问题，我们引入双轨制测试策略：

### Track 1: 基于真实快照的单元测试 (Snapshot-based Unit Testing)
*   **目标**: 解决手动构造 Mock 数据过于理想化的问题。
*   **方法**:
    *   建立 `tests/fixtures/snapshots/` 目录，存储从真实飞书接口抓取的复杂 JSON 响应。
    *   使用 `respx` 或 Mock 加载这些 JSON 文件作为返回值。
    *   确保覆盖各种边缘数据结构（如不同类型的 `field_value_pairs`）。
*   **运行环境**: 本地 CI/CD 环境，无需真实鉴权。

### Track 2: 真实环境集成测试 (Live Integration Testing)
*   **目标**: 验证端到端流程的正确性，确保 API 契约未变。
*   **方法**:
    *   在飞书项目中创建一个专用的“主流程测试空间 (Test Workspace)”。
    *   编写集成测试用例，真实调用飞书 API 进行 CRUD 操作。
    *   使用 `pytest.mark.integration` 标记此类测试。
    *   测试流程应包含：创建 -> 验证 -> 清理（Teardown），防止污染测试环境。
*   **运行环境**: 仅在手动触发或特定流水线中运行，需要配置真实的 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`。

此计划已作为指导原则，后续测试代码提交需遵循此标准。

## 6. 执行进度更新 (Progress Update - 2026/01/14)

### 6.1 已完成工作
1.  **测试架构重构**:
    *   建立了 `tests/unit` (159 个用例) 和 `tests/integration` (3 个用例) 的分离结构。
    *   实现了 `snapshot_loader` 和 `snapshot_saver` fixture，打通了 Track 2 到 Track 1 的数据闭环。
2.  **集成测试落地**:
    *   配置了 `FEISHU_TEST_PROJECT_KEY` 专用环境变量，确保测试隔离。
    *   解决了单例 `ProjectClient` 在异步测试中的 Event Loop 问题。
    *   适配了飞书项目 API 的特性（中文字段名支持、API 返回 List 兼容）。
3.  **CI/CD 集成**:
    *   GitHub Actions 增加了 `integration-test` job，支持手动触发 (`workflow_dispatch`)。

### 6.2 遗留/注意事项
*   **字段权限**: 部分工作项类型（如“问题管理”）的 `priority` 字段可能受工作流控制，不可直接通过 API 更新，测试中已做规避。
*   **环境隔离**: 运行集成测试时，必须确保使用测试专用的 Project Key，避免污染生产数据。
