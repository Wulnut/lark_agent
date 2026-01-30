# Lark Agent 技术方案

## 1. 通用规则 (General Rules)

- **开发协议**: 严格遵循 [Development Protocol](First_stage/Development_Protocol.md) 中定义的 Bottom-Up 和 TDD 流程。
- 始终使用中文回复用户，但技术专有名词可保留英文（如 API、Python、DTO 等）
- 使用项目既有风格，不引入新风格，包括代码、文档或交互，默认延用项目中已有的格式、缩进、命名习惯
- 尽可能少地输出内容，仅提供高信息密度回复，禁止无效寒暄、过度铺垫，只输出对当前任务有直接帮助的信息

---

## 2. 项目愿景 (Project Vision)

构建一个从 **飞书项目 (Lark Project)** 起步，逐步演进为具备 **Workflow 编排** 与 **自主推理能力 (Agent)** 的企业级 AI 助手生态。

---

## 3. 核心技术栈 (Technical Stack)

* **语言**: Python 3.11+ (严格使用类型注解 Type Hints)
* **依赖管理**: `uv` (使用 `pyproject.toml` 和 `uv.lock`)
* **飞书 SDK**: `lark-oapi` & `httpx` (通用能力使用官方 SDK；飞书项目采用自定义异步客户端)
* **协议层**: MCP (Model Context Protocol) 使用 `FastMCP` 框架
* **环境**: Docker (基于 `python:3.11-slim-bookworm`)
* **异步模型**: 基于 `asyncio` 的 Future/Promise 模式
* **严格文档规范**: 所以开发计划都需要更新到doc目录中，并严格按照doc目录中的要求进行实际开发

---

## 4. 项目结构规范 (Project Structure)

我们要建立一个 **分层清晰、模块化、高内聚低耦合** 的架构。

### 4.1 目录组织

```text
src/
├── core/           # 基础设施 (Config, Auth, Client)
│   ├── project_client.py  # 飞书项目专用客户端
│   ├── client.py          # 通用 SDK 客户端
│   └── ...
├── providers/      # 业务逻辑 (Service Layer)
│   ├── base.py     # 抽象基类
│   ├── common/     # 通用能力 (IM, Base, Drive)
│   └── project/    # 飞书项目模块
│       ├── api/        # [Data Layer] 纯 API 调用
│       ├── services/   # [Service Layer] 元数据与配置服务
│       └── items.py    # [Provider] 业务编排 (待重构)
├── schemas/        # 数据模型 (Pydantic), 用于精简 API 返回值
└── mcp_server.py   # MCP 接口层: 注册 Tool 与 Resource
```

### 4.2 分层架构设计

| 层级 | 职责 | 关键组件 |
|------|------|----------|
| **Interface Layer (MCP)** | 暴露工具给 LLM，处理输入验证 | `mcp_server.py`, `tools/` |
| **Service Layer (Providers)** | 编排业务逻辑，处理配置与动态映射 | `WorkItemProvider`, `MetadataService` |
| **Data Layer (Repository/API)** | 纯粹的 API 调用与数据转换 | `ProjectAPI`, `SpaceAPI` |
| **Infrastructure Layer (Core)** | 底层设施，鉴权，HTTP 客户端 | `ProjectClient`, `Auth`, `Config` |

### 4.3 OOP 与 Provider 模式

* **封装**: 所有飞书接口调用必须封装在 `Provider` 类中
* **解耦**: 使用 **Provider 模式**。`mcp_server.py` 只与 `Provider` 抽象接口交互，不直接操作底层 SDK
* **精简**: Provider 必须对飞书原始 JSON 进行数据清洗，仅向 Agent 返回核心业务字段，以节省 Token

---

## 5. 开发规划 (Roadmap)

### Phase 1: 基础设施重构 (Infrastructure Refactoring)
- [ ] **Core**: 完善 `ProjectClient` (Retry, Logging)。
- [ ] **API Layer**: 将 `src/providers/project/api.py` 拆分为独立模块，覆盖 CRUD 和 Filter 接口。
- [ ] **Test**: 为 `ProjectClient` 和 API Layer 编写 Mock 测试。

### Phase 2: 元数据服务 (Metadata Service)
- [ ] **Service**: 实现 `MetadataService`，支持 Project/Type/Field/User 的动态发现与缓存。
- [ ] **Test**: 编写 `MetadataService` 的单元测试 (Mock API 响应)。

### Phase 3: 业务逻辑层 (Business Logic)
- [ ] **Provider**: 重构 `WorkItemProvider`，集成 `MetadataService`，实现无硬编码的 CRUD。
- [ ] **Provider**: 实现高级过滤逻辑 (包含关联字段的客户端过滤)。
- [ ] **Schema**: 定义完整的 Pydantic 模型。
- [ ] **Test**: 编写 Provider 的集成测试 (针对真实/Mock环境)。

### Phase 4: MCP 接口层 (Interface)
- [ ] **Tools**: 将 Provider 方法注册为 MCP Tools。
- [ ] **Validation**: 在 Tool 层进行输入验证。
- [ ] **Test**: 测试 MCP Tool 的调用链路。

---

## 6. 测试策略

每个模块必须包含对应的测试：

1.  **Unit Tests**: 针对 Util, Schema, Helper 函数。
2.  **Mock Tests**: 针对 API Client, Metadata Service（Mock HTTP 响应）。
3.  **Integration Tests**: 针对 Provider 层，连接真实飞书环境（需配置测试租户 Credentials）。

---

## 7. 通用开发原则 (Development Principles)

- **可测试性**：编写可测试的代码，组件应保持单一职责
- **DRY 原则**：避免重复代码，提取共用逻辑到单独的函数或类
- **代码简洁**：保持代码简洁明了，遵循 KISS 原则（保持简单直接）
- **命名规范**：使用描述性的变量、函数和类名，反映其用途和含义
- **注释文档**：为复杂逻辑添加注释，编写清晰的文档说明功能和用法
- **风格一致**：遵循项目或语言的官方风格指南和代码约定
- **利用生态**：优先使用成熟的库和工具，避免不必要的自定义实现
- **架构设计**：考虑代码的可维护性、可扩展性和性能需求
- **版本控制**：编写有意义的提交信息，保持逻辑相关的更改在同一提交中
- **异常处理**：正确处理边缘情况和错误，提供有用的错误信息

---

## 8. 开发守则 (Development Rules)

### 8.1 异步优先 (Async First)

* 所有的 API 请求必须使用异步方法
* 示例: 使用 `client.im.v1.message.acreate()` 而不是 `create()`
* 处理多个并发请求时，使用 `asyncio.gather()`

### 8.2 错误处理

* 不允许直接抛出飞书 SDK 的原始异常
* 必须在 Provider 层捕获异常，并返回人类/Agent 可读的中文错误提示

### 8.3 文档注释 (Docstrings)

* 每个 `mcp.tool()` 必须包含极其详尽的 Docstring
* **Docstring 必须描述**: 1. 工具的功能；2. 参数的业务含义；3. 预期返回的结果

---

## 9. 可用 Skills

本项目配置了以下按需加载的 Skills（位于 `.opencode/skill/`）：

| Skill | 描述 |
|-------|------|
| `python-dev` | Python 编码规则和最佳实践 |
| `typescript-dev` | TypeScript 编码规则和最佳实践 |
| `cpp-dev` | 现代 C++ (C++17/20) 编码规则 |
| `git-commit` | Git 提交规范和分支管理 |
| `gitflow` | Gitflow 工作流规则 |
| `document` | Markdown 文档编写规范 |
| `riper-5` | RIPER-5 严格模式协议 |
