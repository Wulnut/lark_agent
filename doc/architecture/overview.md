# Lark Agent 架构设计文档

## 1. 总体架构

本项目采用**分层架构**与**能力者模式 (Provider Pattern)** 相结合的设计，旨在构建一个可扩展、易维护的飞书 AI 助手生态。系统从飞书项目（Lark Project）起步，逐步演进为具备 Workflow 编排与自主推理能力的企业级 AI 助手。

### 1.1 架构层次

```
┌─────────────────────────────────────────────────┐
│                MCP Interface Layer              │
│  (mcp_server.py: FastMCP 工具注册与暴露)         │
└─────────────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────┐
│            Service Layer (业务编排层)            │
│  (services/: 复杂业务逻辑，协调多个 Provider)     │
└─────────────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────┐
│          Provider Layer (能力抽象层)             │
│  (providers/: 封装业务能力，清洗数据，处理异常)   │
└─────────────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────┐
│             Core Layer (核心基础设施)            │
│  (core/: 认证、缓存、HTTP 客户端、配置管理)       │
└─────────────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────┐
│                External APIs                     │
│  1. Lark Open API (通用接口)                     │
│  2. Feishu Project API (项目专用接口)            │
└─────────────────────────────────────────────────┘
```

### 1.2 核心设计理念

- **关注点分离**: 每层有明确的职责边界。
- **异步优先**: 全链路使用 `async/await`，支持高并发。
- **数据精简**: 严格清洗 API 响应，仅向 AI 返回必要字段以节省 Token。
- **可测试性**: 每层可独立测试，支持依赖注入。

### 1.3 提供者层 (Provider Layer) - 深度细分

依据飞书项目 API 极强的**元数据依赖性**（例如：创建工作项前必须经过 4 级转换），我们将提供者层进一步细分为“原子能力”与“业务逻辑”两个子层，并遵循严格的依赖拓扑。

#### 1.3.1 原子能力层 (Base API Layer - `src/providers/project/api/`)
- **职责**: 严格对应 Postman 集合中的原子接口，负责协议封装、请求发送与原始错误处理。
- **依赖拓扑 (Dependency Topology)**:
  - **L0 (Auth)**: `auth.py` -> 获取 `plugin_token`。
  - **L1 (Project)**: `project.py` -> 依赖 L0，获取 `project_key` (空间识别)。
  - **L2 (Metadata)**: `metadata.py` -> 依赖 L1，获取 `work_item_type_key` (类型识别)。
  - **L3 (Field)**: `field.py` -> 依赖 L2，获取 `field_key` 与 `option_key` (字段与枚举识别)。
  - **L4 (Action)**: `work_item.py` -> 依赖 L1-L3，执行最终的 CRUD 操作。

#### 1.3.2 业务逻辑层 (Logic Provider Layer - `src/providers/project/`)
- **职责**: 串联原子接口，处理复杂的依赖链条，提供**“名称到 ID”**的动态转换，解决硬编码问题。
- **核心原则**:
  - **零硬编码 (Zero Hardcoding)**: 严禁在代码中写死 UUID/Key，所有参数通过名称动态匹配。
  - **级联缓存 (Cascaded Cache)**: 维护 `Name -> Key` 的级联关系映射，减少重复 API 请求，提升性能。
- **核心组件**:
  - `MetadataProvider`: **系统的基石**。负责自动发现项目空间、工作项类型、字段名及枚举选项，并实现懒加载缓存。
  - `WorkItemProvider`: 调用 `MetadataProvider` 获取上下文，再调度 `WorkItemAPI` 执行具体操作。
  - `UserProvider`: 提供基于邮箱或姓名的用户定位与 Key 转换。

## 2. 详细目录结构与依赖关系

### 2.1 目录组织
```text
src/
├── core/               # 基础设施：认证中心、单例客户端、全局配置
├── providers/          # 能力者层
│   └── project/
│       ├── api/        # [Base API Layer] 原子接口封装
│       │   ├── auth.py      # L0
│       │   ├── project.py   # L1
│       │   ├── metadata.py  # L2
│       │   ├── field.py     # L3
│       │   └── work_item.py # L4
│       ├── metadata.py # [Logic Layer] 元数据解析与级联缓存
│       └── work_item_provider.py # [Logic Layer] 业务能力提供者
├── services/           # [Service Layer] 跨领域业务场景编排 (使用 Base API 或 Provider)
├── schemas/            # 强类型数据模型 (Pydantic)
└── mcp_server.py       # MCP 协议出口与工具注册
```

### 2.2 API 级联依赖拓扑 (Cascading Dependencies)

系统的所有操作必须遵循以下单向依赖链条，Base API 为上层编排提供确定性的参数输入：

| 层级 | 模块 | 输入 (Input) | 产出 (Output) | 编排用途 |
| :--- | :--- | :--- | :--- | :--- |
| **L0** | Auth | AppID, Secret | `plugin_token` | 全局调用凭证 |
| **L1** | Project | 项目名称 | `project_key` | 锁定操作空间 |
| **L2** | Type | `project_key`, 类型名 | `type_key` | 确定工作项模版 |
| **L3** | Field | `type_key`, 字段名 | `field_key`, `option_map` | 确定属性映射关系 |
| **L4** | Action | L1+L2+L3 的 Keys | 工作项 ID / 结果 | 执行业务目标 |

**设计要求**: Service 层在编排复杂逻辑时，应优先通过 `MetadataProvider` 完成 L1-L3 的级联转换，确保传给 L4 的参数是协议准确的。

## 3. 核心组件详解

### 3.1 核心层 (Core Layer)

#### 3.1.1 配置管理 (`config.py`)
- 使用 `pydantic-settings` 管理环境变量。
- 统一配置入口，支持多环境切换。

#### 3.1.2 认证管理 (`auth.py`)
- **双重认证**: 支持标准 Lark OAuth2 和飞书项目插件 Token 认证。
- 自动处理令牌刷新、缓存与过期预判。

#### 3.1.3 HTTP 客户端
- `client.py`: Lark Open API 官方 SDK 封装。
- `project_client.py`: 飞书项目专用异步客户端，自动注入认证头。

### 3.2 服务层 (Service Layer)
- `issue_service.py`: 封装“任务创建”、“Bug 报告”等高层业务动作，调度多个 Provider 完成复杂任务。

## 4. 演进路线图

### 4.1 Stage 1: 飞书项目 MCP 落地 ✅ (当前)
- [x] 分层 Provider 架构。
- [x] 元数据动态解析与缓存。
- [x] 基础工作项 CRUD。

### 4.2 Stage 2: 引入 Workflow 编排
- 引入 `LangGraph` 进行逻辑编排，支持复杂业务闭环。

### 4.3 Stage 3: 完整 Agent 化
- 自主决策、自然语言交互与任务规划。

## 5. 质量保证

- **测试策略**: 坚持“原子接口必测，业务路径覆盖”的原则。
- **Token 优化**: 严格执行数据清洗，仅向 Agent 返回核心业务字段。

---
*文档版本: 1.1 | 更新时间: 2026-01-13 | 深度细分 Provider 架构*
