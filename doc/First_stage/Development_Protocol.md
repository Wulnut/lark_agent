# 开发协议与工作流 (Development Protocol)

## 1. 核心原则 (Core Principles)

*   **Bottom-Up Development**: 自下而上。先配置 -> 再核心 -> 再模型 -> 再接口 -> 最后业务逻辑与 MCP。
*   **Docker-First**: 所有开发与测试必须在 Docker 容器中通过验证，确保环境一致性。
*   **Test-Driven Development (TDD)**: 
    *   无测试，不提交。
    *   先写测试 (Red) -> 再实现功能 (Green) -> 重构 (Refactor)。
    *   每个接口必须包含：正常路径 (Happy Path) + 异常路径 (Edge Cases/Errors)。

## 2. 技术栈 (Test Stack)

*   **Runner**: `pytest`
*   **Async Support**: `pytest-asyncio` (处理异步函数测试)
*   **HTTP Mock**: `respx` (用于 mock `httpx` 请求，实现无 Token 接口测试)
*   **Environment**: `Docker` + `uv`

## 3. 开发阶段规划 (Phases)

### Phase 1: 环境与基础架构 (Environment) [Completed]
*   配置 `pyproject.toml` (添加测试依赖)。
*   构建 `Dockerfile` & `docker-compose.yml`。
*   建立 `tests/` 目录结构。

### Phase 2: 核心网络层 (Core Networking) [Completed]
*   **Target**: `src/core/client.py`, `src/core/config.py`
*   **Tests**: 
    *   `tests/core/test_config.py`: 验证 env 加载。
    *   `tests/core/test_client.py`: 验证 Token 注入、超时重试、状态码异常捕获。

### Phase 3: 数据模型层 (Data Schemas) [Completed]
*   **Target**: `src/schemas/*.py`
*   **Tests**: 
    *   `tests/schemas/test_models.py`: 验证 Pydantic 模型校验与序列化。

### Phase 4: API 原子封装 (API Wrappers) [Completed]
*   **Target**: `src/providers/project/api.py` (纯 API 调用，无业务逻辑)
*   **Tests**: 
    *   `tests/providers/project/test_api_raw.py`: 使用 `respx` 模拟飞书 JSON 回包，验证 URL 构建和 HTTP 方法正确性。

### Phase 5: 业务逻辑层 (Business Logic) [Completed]
*   **Target**: `src/providers/project/manager.py` (数据清洗、聚合)
*   **Tests**: 
    *   `tests/providers/project/test_manager.py`: 验证数据清洗逻辑（如字段映射、结果过滤）。

### Phase 6: MCP 集成 (Integration) [Completed]
*   **Target**: `main.py`
*   **Tests**: 
    *   `tests/test_main.py`: 验证 MCP 工具注册元数据。

## 4. 常用指令

```bash
# 在 Docker 中运行所有测试
docker compose run --rm agent pytest

# 运行特定模块测试并显示详细日志
docker compose run --rm agent pytest tests/core/test_client.py -v
```
