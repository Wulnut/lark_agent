#!/bin/bash
cd /home/liangyz/ai_tool/project_management_mcp
nohup uv run lark-agent-http > /dev/null 2>&1 &
echo $! > http_server.pid
echo "HTTP server started in background, PID: $(cat http_server.pid)"
