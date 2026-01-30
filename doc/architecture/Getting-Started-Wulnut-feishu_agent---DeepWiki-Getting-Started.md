# Getting Started

> **Relevant source files**
> * [.env.example](https://github.com/Wulnut/lark_agent/blob/e9d158cb/.env.example)
> * [AGENTS.md](https://github.com/Wulnut/lark_agent/blob/e9d158cb/AGENTS.md)
> * [README.md](https://github.com/Wulnut/lark_agent/blob/e9d158cb/README.md)
> * [doc/Planning/Planning_1.md](https://github.com/Wulnut/lark_agent/blob/e9d158cb/doc/Planning/Planning_1.md)
> * [doc/Planning/Progress.md](https://github.com/Wulnut/lark_agent/blob/e9d158cb/doc/Planning/Progress.md)
> * [pyproject.toml](https://github.com/Wulnut/lark_agent/blob/e9d158cb/pyproject.toml)
> * [src/__init__.py](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/__init__.py)
> * [src/core/cache.py](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/core/cache.py)
> * [src/core/client.py](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/core/client.py)
> * [src/core/config.py](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/core/config.py)
> * [src/schemas/project.py](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/schemas/project.py)
> * [tests/conftest.py](https://github.com/Wulnut/lark_agent/blob/e9d158cb/tests/conftest.py)
> * [tests/unit/core/test_config.py](https://github.com/Wulnut/lark_agent/blob/e9d158cb/tests/unit/core/test_config.py)

This page provides a comprehensive guide to installing, configuring, and running the Lark Agent MCP Server. It covers the essential steps to get the server operational and integrated with AI assistants like Cursor or Claude Desktop. For detailed architecture information, see [Architecture](/Wulnut/lark_agent/3-architecture). For specific MCP tool usage, see [MCP Tools Reference](/Wulnut/lark_agent/5-mcp-tools-reference).

---

## Prerequisites

Before installing the Lark Agent, ensure you have:

| Requirement | Version | Purpose |
| --- | --- | --- |
| Python | 3.11+ | Runtime environment |
| uv | Latest | Package manager (recommended) |
| Feishu Project Access | N/A | API credentials required |
| Lark App Credentials | N/A | Optional, only for IM features |

**Required Credentials:**

* `FEISHU_PROJECT_USER_KEY`: Your Feishu Project user key
* Either `FEISHU_PROJECT_USER_TOKEN` (static token) or `FEISHU_PROJECT_PLUGIN_ID` + `FEISHU_PROJECT_PLUGIN_SECRET` (plugin authentication, preferred)

**Optional Credentials** (only needed for instant messaging features):

* `LARK_APP_ID` and `LARK_APP_SECRET`: Lark application credentials

Sources: [README.md L183-L186](https://github.com/Wulnut/lark_agent/blob/e9d158cb/README.md#L183-L186)

 [src/core/config.py L14-L34](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/core/config.py#L14-L34)

 [.env.example L1-L28](https://github.com/Wulnut/lark_agent/blob/e9d158cb/.env.example#L1-L28)

---

## Installation Methods

The Lark Agent supports two installation methods. For detailed instructions, see [Installation](/Wulnut/lark_agent/2.1-installation).

### Method 1: Tool Install (Recommended)

The `uv tool install` method provides the simplest installation experience:

```python
# Install directly from GitHub
uv tool install --from git+https://github.com/Wulnut/lark_agent lark-agent

# The command becomes globally available
lark-agent
```

After installation, the `lark-agent` command is automatically added to your system PATH, as defined in [pyproject.toml L21-L22](https://github.com/Wulnut/lark_agent/blob/e9d158cb/pyproject.toml#L21-L22)

### Method 2: From Source

For development or customization:

```markdown
# Clone repository
git clone https://github.com/Wulnut/lark_agent.git
cd lark_agent

# Install dependencies
uv sync

# Run directly
uv run main.py
```

**Installation Flow Diagram:**

```mermaid
flowchart TD

START["User Initiates Installation"]
UV_TOOL["uv tool install<br>--from git+https://..."]
UV_FETCH["Fetch pyproject.toml<br>from GitHub"]
UV_BUILD["Build Package<br>hatchling backend"]
UV_INSTALL["Install to<br>~/.local/bin/"]
SCRIPT_REG["Register Script<br>lark-agent = src.mcp_server:main"]
CLONE["git clone"]
UV_SYNC["uv sync<br>Install dependencies"]
UV_RUN["uv run main.py<br>Direct execution"]
MAIN_PY["main.py<br>Entry point"]
MULTIPROC["Multiprocessing Setup"]
HTTP_CHILD["HTTP Server Child Process<br>daemon=True"]
MCP_MAIN["MCP Server Main Process<br>run_mcp_server()"]

START --> UV_TOOL
START --> CLONE
SCRIPT_REG --> MAIN_PY
UV_RUN --> MAIN_PY

subgraph subGraph2 ["Common Initialization"]
    MAIN_PY
    MULTIPROC
    HTTP_CHILD
    MCP_MAIN
    MAIN_PY --> MULTIPROC
    MULTIPROC --> HTTP_CHILD
    MULTIPROC --> MCP_MAIN
end

subgraph subGraph1 ["Method 2: From Source"]
    CLONE
    UV_SYNC
    UV_RUN
    CLONE --> UV_SYNC
    UV_SYNC --> UV_RUN
end

subgraph subGraph0 ["Method 1: Tool Install"]
    UV_TOOL
    UV_FETCH
    UV_BUILD
    UV_INSTALL
    SCRIPT_REG
    UV_TOOL --> UV_FETCH
    UV_FETCH --> UV_BUILD
    UV_BUILD --> UV_INSTALL
    UV_INSTALL --> SCRIPT_REG
end
```

Sources: [README.md L169-L223](https://github.com/Wulnut/lark_agent/blob/e9d158cb/README.md#L169-L223)

 [pyproject.toml L1-L44](https://github.com/Wulnut/lark_agent/blob/e9d158cb/pyproject.toml#L1-L44)

---

## Configuration

Configuration is managed through environment variables loaded by the `Settings` class. For detailed configuration options, see [Configuration](/Wulnut/lark_agent/2.2-configuration).

### Configuration Loading Flow

The system uses `pydantic-settings` to load configuration from multiple sources with priority:

```mermaid
flowchart TD

ENV_FILE[".env File<br>(project root)"]
ENV_VARS["Environment Variables<br>(system/shell)"]
GH_SECRETS["GitHub Secrets<br>(CI/CD)"]
SETTINGS_CLASS["Settings class<br>src/core/config.py:14"]
LARK_FIELDS["LARK_APP_ID<br>LARK_APP_SECRET<br>LARK_ENCRYPT_KEY<br>LARK_VERIFICATION_TOKEN"]
PROJ_FIELDS["FEISHU_PROJECT_BASE_URL<br>FEISHU_PROJECT_USER_TOKEN<br>FEISHU_PROJECT_USER_KEY<br>FEISHU_PROJECT_PLUGIN_ID<br>FEISHU_PROJECT_PLUGIN_SECRET"]
PROJ_KEYS["FEISHU_PROJECT_KEY<br>FEISHU_TEST_PROJECT_KEY"]
LOG_FIELD["LOG_LEVEL"]
AUTH_MGR["AuthManager<br>src/core/auth.py"]
LARK_CLIENT["LarkClient<br>src/core/client.py"]
PROJ_CLIENT["ProjectClient<br>src/core/project_client.py"]

ENV_FILE --> SETTINGS_CLASS
ENV_VARS --> SETTINGS_CLASS
LARK_FIELDS --> LARK_CLIENT
PROJ_FIELDS --> AUTH_MGR
PROJ_KEYS --> PROJ_CLIENT
LOG_FIELD --> AUTH_MGR

subgraph Consumers ["Consumers"]
    AUTH_MGR
    LARK_CLIENT
    PROJ_CLIENT
end

subgraph subGraph1 ["Settings Singleton"]
    SETTINGS_CLASS
    LARK_FIELDS
    PROJ_FIELDS
    PROJ_KEYS
    LOG_FIELD
    SETTINGS_CLASS --> LARK_FIELDS
    SETTINGS_CLASS --> PROJ_FIELDS
    SETTINGS_CLASS --> PROJ_KEYS
    SETTINGS_CLASS --> LOG_FIELD
end

subgraph subGraph0 ["Configuration Sources"]
    ENV_FILE
    ENV_VARS
    GH_SECRETS
    GH_SECRETS --> ENV_VARS
end
```

### Minimal Configuration

Create a `.env` file in the project root:

```markdown
# Feishu Project API Configuration (Required)
FEISHU_PROJECT_USER_KEY=your_user_key

# Option 1: Static Token (Backward Compatible)
FEISHU_PROJECT_USER_TOKEN=your_static_token

# Option 2: Plugin Authentication (Preferred)
FEISHU_PROJECT_PLUGIN_ID=your_plugin_id
FEISHU_PROJECT_PLUGIN_SECRET=your_plugin_secret

# Optional: Lark IM Features
LARK_APP_ID=your_app_id
LARK_APP_SECRET=your_app_secret

# Optional: Logging
LOG_LEVEL=INFO
```

The `Settings` class automatically validates required fields on initialization [src/core/config.py L14-L54](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/core/config.py#L14-L54)

**Authentication Priority:**

1. Static token (`FEISHU_PROJECT_USER_TOKEN`) is checked first
2. If not found, plugin credentials are used to fetch a dynamic token
3. Tokens are cached with a 60-second expiry buffer

Sources: [.env.example L1-L28](https://github.com/Wulnut/lark_agent/blob/e9d158cb/.env.example#L1-L28)

 [src/core/config.py L14-L54](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/core/config.py#L14-L54)

---

## Client Integration

The Lark Agent exposes two interfaces for client integration. For detailed client configuration, see [Client Integration](/Wulnut/lark_agent/2.3-client-integration).

### Interface Architecture

```mermaid
flowchart TD

CURSOR["Cursor IDE"]
CLAUDE["Claude Desktop"]
N8N["n8n Workflow"]
BROWSER["Web Browser"]
MAIN_FUNC["main()<br>src/mcp_server.py"]
HTTP_PROC["HTTP Server Process<br>multiprocessing.Process<br>daemon=True"]
MCP_PROC["MCP Server Process<br>Main Thread<br>Blocking stdio"]
HTTP_API["http_server.py<br>FastAPI<br>Port 8002"]
MCP_STDIO["FastMCP<br>stdio transport<br>JSON-RPC"]
TOOLS["6 MCP Tools:<br>list_projects<br>create_task<br>get_tasks<br>get_task_detail<br>update_task<br>get_task_options"]

CURSOR --> MCP_STDIO
CLAUDE --> MCP_STDIO
N8N --> HTTP_API
BROWSER --> HTTP_API
HTTP_PROC --> HTTP_API
MCP_PROC --> MCP_STDIO
MCP_STDIO --> TOOLS
HTTP_API --> TOOLS

subgraph subGraph3 ["Registered Tools"]
    TOOLS
end

subgraph subGraph2 ["Interface Handlers"]
    HTTP_API
    MCP_STDIO
end

subgraph subGraph1 ["MCP Server Process"]
    MAIN_FUNC
    HTTP_PROC
    MCP_PROC
    MAIN_FUNC --> HTTP_PROC
    MAIN_FUNC --> MCP_PROC
end

subgraph subGraph0 ["Client Applications"]
    CURSOR
    CLAUDE
    N8N
    BROWSER
end
```

### MCP Client Configuration

**Cursor IDE** (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "lark-agent": {
      "command": "lark-agent"
    }
  }
}
```

**Claude Desktop** (macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "lark-agent": {
      "command": "lark-agent"
    }
  }
}
```

**From Source Configuration:**

```json
{
  "mcpServers": {
    "lark-agent": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/lark_agent",
        "main.py"
      ]
    }
  }
}
```

Sources: [README.md L228-L309](https://github.com/Wulnut/lark_agent/blob/e9d158cb/README.md#L228-L309)

---

## Quick Start Workflow

This section demonstrates a complete startup and verification workflow.

### Step-by-Step Startup

```mermaid
sequenceDiagram
  participant User
  participant Shell
  participant main.py
  participant HTTP Server Process
  participant MCP Server Process
  participant Settings Singleton
  participant AuthManager

  User->>Shell: lark-agent
  Shell->>main.py: Execute main()
  main.py->>Settings Singleton: Load configuration from .env
  Settings Singleton-->>main.py: Config loaded
  main.py->>HTTP Server Process: spawn(http_child_process, daemon=True)
  HTTP Server Process->>HTTP Server Process: Start FastAPI on port 8002
  HTTP Server Process-->>main.py: Process started
  main.py->>MCP Server Process: run_mcp_server() (blocking)
  MCP Server Process->>Settings Singleton: Get credentials
  Settings Singleton-->>MCP Server Process: Credentials
  MCP Server Process->>AuthManager: Initialize AuthManager
  AuthManager->>AuthManager: Check token strategy
  AuthManager-->>MCP Server Process: Ready
  MCP Server Process->>MCP Server Process: Register 6 MCP tools
  MCP Server Process->>MCP Server Process: Start stdio transport
  note over MCP Server Process: Server ready, waiting for client
```

### First Request Flow

```mermaid
sequenceDiagram
  participant AI Assistant
  participant MCP Server
  participant _create_provider()
  participant MetadataManager
  participant ProjectAPI
  participant Feishu API

  AI Assistant->>MCP Server: list_projects
  MCP Server->>_create_provider(): Create provider instance
  _create_provider()->>MetadataManager: get_instance()
  MetadataManager-->>_create_provider(): MetadataManager singleton
  MCP Server->>ProjectAPI: list_projects()
  ProjectAPI->>Feishu API: POST /project/api/list
  Feishu API-->>ProjectAPI: Project list JSON
  ProjectAPI->>MetadataManager: Cache projects (TTL=3600s)
  ProjectAPI-->>MCP Server: Parsed project dict
  MCP Server-->>AI Assistant: {"ProjectA": "project_xxx", "ProjectB": "project_yyy"}
```

Sources: [src/mcp_server.py L1-L400](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/mcp_server.py#L1-L400)

---

## Verification Steps

After installation and configuration, verify the server is working correctly.

### 1. Check Server Startup

When the server starts successfully, you should see:

```
INFO - Starting Lark Agent MCP Server
INFO - HTTP API server will be available at http://localhost:8002
INFO - MCP server running in stdio mode
```

Logs are written to `log/agent.log` for stdio mode.

### 2. Verify HTTP API (Optional)

If the HTTP server is enabled, test the API:

```markdown
# Check API documentation
curl http://localhost:8002/docs

# Test list projects endpoint
curl -X POST http://localhost:8002/list_projects
```

### 3. Test MCP Tools

In your AI assistant (Cursor/Claude), try:

```yaml
User: "List all available Feishu projects"
AI: Calls list_projects tool
Expected: Returns project name to project_key mapping
```

```sql
User: "Create a task named 'Test MCP Integration' with P2 priority"
AI: Calls create_task tool
Expected: Returns success message with issue_id
```

### 4. Verify Configuration Loading

Check that credentials are loaded correctly:

```javascript
# Run test script to validate configuration
uv run python -c "from src.core.config import settings; print(f'User Key: {settings.FEISHU_PROJECT_USER_KEY[:4]}***')"
```

**Common Issues:**

| Issue | Solution |
| --- | --- |
| `FEISHU_PROJECT_USER_KEY` not set | Verify `.env` file exists in project root |
| Authentication failures | Check token validity or plugin credentials |
| Import errors | Run `uv sync` to install dependencies |
| Port 8002 in use | Change port in HTTP server configuration |

Sources: [README.md L224-L227](https://github.com/Wulnut/lark_agent/blob/e9d158cb/README.md#L224-L227)

 [tests/conftest.py L1-L110](https://github.com/Wulnut/lark_agent/blob/e9d158cb/tests/conftest.py#L1-L110)

---

## Server Initialization Details

Understanding the initialization process helps troubleshoot startup issues.

### Singleton Initialization Order

```mermaid
flowchart TD

START["Application Start"]
SETTINGS["Settings<br>src/core/config.py:54<br>Thread-safe instance"]
CACHE["SimpleCache<br>src/core/cache.py:16<br>TTL-based cache"]
AUTH_MGR["AuthManager<br>src/core/auth.py<br>Token management"]
CHECK_TOKEN["Token Strategy?"]
STATIC["Use Static Token"]
PLUGIN["Fetch Plugin Token"]
PROJ_CLIENT["ProjectClient<br>src/core/project_client.py<br>httpx + retry"]
LARK_CLIENT["LarkClient<br>src/core/client.py<br>lark-oapi wrapper"]
META_MGR["MetadataManager<br>Cascading cache L1-L5"]

START --> SETTINGS
SETTINGS --> AUTH_MGR
STATIC --> PROJ_CLIENT
PLUGIN --> PROJ_CLIENT
SETTINGS --> LARK_CLIENT
PROJ_CLIENT --> META_MGR

subgraph subGraph3 ["Phase 4: Managers"]
    META_MGR
end

subgraph subGraph2 ["Phase 3: HTTP Clients"]
    PROJ_CLIENT
    LARK_CLIENT
end

subgraph subGraph1 ["Phase 2: Authentication"]
    AUTH_MGR
    CHECK_TOKEN
    STATIC
    PLUGIN
    AUTH_MGR --> CHECK_TOKEN
    CHECK_TOKEN --> STATIC
    CHECK_TOKEN --> PLUGIN
end

subgraph subGraph0 ["Phase 1: Core Singletons"]
    SETTINGS
    CACHE
    SETTINGS --> CACHE
end
```

### Tool Registration Process

When the MCP server initializes, it registers six tools using the `@mcp.tool()` decorator:

1. **`list_projects`** [src/mcp_server.py](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/mcp_server.py#LNaN-LNaN) : Returns project name to key mapping
2. **`create_task`** [src/mcp_server.py](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/mcp_server.py#LNaN-LNaN) : Creates a new work item
3. **`get_tasks`** [src/mcp_server.py](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/mcp_server.py#LNaN-LNaN) : Lists work items with filtering
4. **`get_task_detail`** [src/mcp_server.py](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/mcp_server.py#LNaN-LNaN) : Gets full work item details with readable fields
5. **`update_task`** [src/mcp_server.py](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/mcp_server.py#LNaN-LNaN) : Updates work item fields
6. **`get_task_options`** [src/mcp_server.py](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/mcp_server.py#LNaN-LNaN) : Discovers available field options

Each tool creates a fresh `WorkItemProvider` instance via `_create_provider()` [src/mcp_server.py](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/mcp_server.py#LNaN-LNaN)

 to ensure context isolation between requests.

Sources: [src/mcp_server.py L1-L400](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/mcp_server.py#L1-L400)

 [src/core/auth.py L1-L150](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/core/auth.py#L1-L150)

 [src/core/project_client.py L1-L200](https://github.com/Wulnut/lark_agent/blob/e9d158cb/src/core/project_client.py#L1-L200)

---

## Next Steps

After completing the getting started workflow:

1. **Explore MCP Tools**: See [MCP Tools Reference](/Wulnut/lark_agent/5-mcp-tools-reference) for detailed tool documentation
2. **Understand Architecture**: Read [Architecture](/Wulnut/lark_agent/3-architecture) to learn about the four-layer design
3. **Customize Configuration**: See [Configuration](/Wulnut/lark_agent/2.2-configuration) for advanced options
4. **Development**: See [Development Guide](/Wulnut/lark_agent/6-development-guide) if you plan to contribute or extend the codebase

For troubleshooting common issues, see [Troubleshooting](/Wulnut/lark_agent/8-troubleshooting).

Sources: [README.md L1-L393](https://github.com/Wulnut/lark_agent/blob/e9d158cb/README.md#L1-L393)

 [doc/Planning/Progress.md L1-L110](https://github.com/Wulnut/lark_agent/blob/e9d158cb/doc/Planning/Progress.md#L1-L110)