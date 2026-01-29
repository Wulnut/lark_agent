#!/bin/bash
if [ -f http_server.pid ]; then
    PID=$(cat http_server.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "HTTP server is running (PID: $PID)"
        curl -s http://localhost:8002/health || echo "Server not responding"
    else
        echo "HTTP server is not running (stale PID file)"
    fi
else
    echo "HTTP server is not running"
fi
